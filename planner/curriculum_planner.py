from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING,TypeVar
from langchain.messages import SystemMessage,HumanMessage
from pydantic import BaseModel
if TYPE_CHECKING:
    from retrieval.retrieval_tool import RetrievalTool
from pathlib import Path
from models.data_models import(
    Curriculum,
    CurriculumOutline,
    Module,
    ModuleDetail,
    ModuleOutline,
)
from planner.doc_outline import DocOutline
from reasoning.model import get_llm
from reasoning.structured import StructuredResult


logger=logging.getLogger(__name__)
T=TypeVar("T",bound=BaseModel)

_PROMPT_DIR = Path(__file__).parent.parent / "reasoning" / "system_messages"
_STOPWORDS = {"and", "the", "in", "with", "for", "of", "to", "a", "an", "using", "basics", "intro"}
_VAGUE_STARTS = ("understand", "learn", "know", "be familiar", "become familiar","explain", "describe", "discuss")

class PlannerError(RuntimeError):
    "A planning call could not produce valid output within its attempt budget."

def _words(title: str, extra_stop: set[str]) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    return {t for t in tokens if t not in _STOPWORDS and t not in extra_stop}

def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0

class CurriculumPlanner:
    def __init__(
        self,
        model_name: str,
        *,
        outline:DocOutline,
        retrieval:"RetrievalTool|None"=None,
        llm=None,
        min_modules:int=3,
        max_modules:int=5,
        max_attempts:int=3,
        section_char_budget:int=6000,
    ):
        self.model_name=model_name
        self.outline=outline
        self.min_modules = min_modules
        self.max_modules = max_modules
        self.max_attempts = max_attempts
        self.section_char_budget = section_char_budget
        self.retrieval = retrieval

        self.structured_result=StructuredResult(
            llm=llm or get_llm(model_name),
            error_cls=PlannerError,
            max_attempts=self.max_attempts
        )

        self.outline_prompt = (_PROMPT_DIR / "curriculum_outline.txt").read_text(encoding="utf-8")
        self.detail_prompt = (_PROMPT_DIR / "module_detail.txt").read_text(encoding="utf-8")

    def _module_range(self) -> tuple[int, int]:
        "How many modules the docs can honestly support (about 2 sections each)."
        hi = max(1, min(self.max_modules, len(self.outline) // 2))
        lo = min(self.min_modules, hi)
        return lo, hi

    def _validate_outline(self, outline: CurriculumOutline, technology: str) -> None:
        "Vaidates Models outline and collects all problems so all can be fixed in 1 retry"
        problems: list[str] = []
        valid = self.outline.valid_ids
        lo, hi = self._module_range()

        if not lo <= len(outline.modules) <= hi:
            wanted = f"exactly {lo}" if lo == hi else f"between {lo} and {hi}"
            problems.append(f"Return {wanted} modules, not {len(outline.modules)}.")

        owner: dict[int, str] = {}
        reported: set[int] = set()
        for module in outline.modules:
            unknown = [i for i in module.section_ids if i not in valid]
            if unknown:
                problems.append(
                    f"Module '{module.title}' uses unknown section IDs {unknown}. "
                    f"Valid IDs are {min(valid)} to {max(valid)}."
                )
            for i in module.section_ids:
                if i in owner and owner[i] != module.title and i not in reported:
                    problems.append(
                        f"Section {i} is in both '{owner[i]}' and '{module.title}'. "
                        "Each section may belong to only one module."
                    )
                    reported.add(i)
                owner.setdefault(i, module.title)

        stop = _words(technology, set())
        mods = outline.modules
        for a in range(len(mods)):
            for b in range(a + 1, len(mods)):
                if _jaccard(_words(mods[a].title, stop), _words(mods[b].title, stop)) >= 0.6:
                    problems.append(
                        f"Modules '{mods[a].title}' and '{mods[b].title}' overlap too much. "
                        "Merge them or make their topics clearly different."
                    )

        if problems:
            raise ValueError("\n".join(f"- {p}" for p in problems))

    def _plan_outline(self, technology: str) -> CurriculumOutline:
        "Creates the Outline for the Modules"
        lo, hi = self._module_range()
        count = f"exactly {lo}" if lo == hi else f"between {lo} and {hi}"
        messages = [
            SystemMessage(content=self.outline_prompt),
            HumanMessage(
                content=f"Technology: {technology}\n"
                f"Create {count} modules.\n\n"
                f"Documentation outline:\n{self.outline.render()}"
            ),
        ]
        return self.structured_result.call(
            CurriculumOutline,
            messages,
            label="outline",
            validate=lambda o: self._validate_outline(o, technology),
        )

    @staticmethod
    def _validate_detail(detail: ModuleDetail) -> None:
        "Validates details so there are no vague requirement or objectives in module"
        problems = []
        objectives=[step.objective for step in detail.steps]
        for objective in objectives:
            if objective.lower().startswith(_VAGUE_STARTS):
                problems.append(
                    f"Objective '{objective}' is vague. Start with an action verb for something "
                    "the learner can do in code (Define, Write, Declare, Convert, Validate, Fix)."
                )
        if len({o.lower() for o in objectives}) != len(objectives):
            problems.append("Objectives must all be different.")
        requirements=[r.lower() for step in detail.steps for r in step.requirements]
        if len(set(requirements))!= len(requirements):
            problems.append("Requirements must all be different across steps.")
        if problems:
            raise ValueError("\n".join(f"- {p}" for p in problems))

    def _plan_module(
        self,
        technology: str,
        module: ModuleOutline,
        index: int,
        total: int,
        earlier_titles: list[str],
    ) -> ModuleDetail:
        earlier = "; ".join(earlier_titles) if earlier_titles else "none (this is the first module)"
        docs = self.outline.text_for(module.section_ids, self.section_char_budget)
        messages = [
            SystemMessage(content=self.detail_prompt),
            HumanMessage(
                content=f"Course: {technology}\n"
                f"Module {index} of {total}: {module.title}\n"
                f"Earlier modules: {earlier}\n\n"
                f"Documentation for this module:\n{docs}"
            ),
        ]
        return self.structured_result.call(
            ModuleDetail,
            messages,
            label=f"module {index}",
            validate=self._validate_detail,
        )

    def create_curriculum(self, technology: str) -> Curriculum:
        "Creates the Curriculum based on the the module and outline"
        outline = self._plan_outline(technology)

        modules: list[Module] = []
        titles: list[str] = []
        for index, planned in enumerate(outline.modules, start=1):
            try:
                detail = self._plan_module(technology, planned, index, len(outline.modules), titles)
            except PlannerError as exc:
                logger.warning("Skipping module %d (%s): %s", index, planned.title, exc)
                continue
            modules.append(
                Module(
                    title=planned.title,
                    steps=detail.steps,
                    source_sections=self.outline.sources_for(planned.section_ids),
                )
            )
            titles.append(planned.title)

        if not modules:
            raise PlannerError("No module could be generated.")
        return Curriculum(modules=modules)

    def grounding_report(self, curriculum: Curriculum) -> dict[str, list[tuple[str, int]]]:
        """For every documentation requirement, how many chunks does retrieval find?

        A requirement with 0 hits means the knowledge base cannot back it up.
        This check runs in code, so the model is never asked to judge it.
        """
        if self.retrieval is None:
            raise PlannerError("grounding_report needs a retrieval tool.")
        return {
            module.title: [
                (step.objective, requirement, len(self.retrieval.retrieve(requirement)))
                for step in module.steps
                for requirement in step.requirements
            ]
            for module in curriculum.modules
        }