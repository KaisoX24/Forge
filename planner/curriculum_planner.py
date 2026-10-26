from __future__ import annotations
import logging
import re
from typing import Callable,TypeVar
from langchain.messages import AIMessage,SystemMessage,HumanMessage
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
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

def _describe_error(err: BaseException) -> str:
    "Short, model-readable description of why parsing failed."
    cause = err.__cause__
    errors = getattr(cause, "errors", None)
    if callable(errors):
        lines = []
        for e in errors():
            where = ".".join(str(p) for p in e["loc"]) or "output"
            lines.append(f"- {where}: {e['msg']}")
        return "The JSON did not match the required format:\n" + "\n".join(lines)
    text = str(err)
    if "Invalid json" in text:
        return "The reply was not valid JSON."
    return text[:400]

class CurriculumPlanner:
    def __init__(
        self,
        model_name: str,
        *,
        outline:DocOutline,
        retrieval:RetrievalTool|None=None,
        min_modules:int=3,
        max_modules:int=5,
        max_attempts:int=3,
        section_char_budget:int=6000,
    ):
        self.outline=outline
        self.min_modules = min_modules
        self.max_modules = max_modules
        self.max_attempts = max_attempts
        self.section_char_budget = section_char_budget
        self.retrieval = retrieval
        self.llm = get_llm(model_name)
        self.retrieval_tool = retrieval.as_tool()

        self.llm_with_tools = self.llm.bind_tools(
            [self.retrieval_tool]
        )

        self.outline_prompt = (_PROMPT_DIR / "curriculum_outline.txt").read_text(encoding="utf-8")
        self.detail_prompt = (_PROMPT_DIR / "module_detail.txt").read_text(encoding="utf-8")

    def _call_structured(
        self,
        schema: type[T],
        messages: list[BaseMessage],
        *,
        label: str,
        validate: Callable[[T], None] | None = None,
    ) -> T:
        structured = self.llm.with_structured_output(schema, include_raw=True)
        feedback:list[BaseMessage]=[]
        last_problem = "no attempt was made"

        for attempt in range(1, self.max_attempts + 1):
            try:
            # Runs for max 3 iterations if any error occurs store the detail and pass it to llm for retry
                result = structured.invoke(list(messages)+feedback)
            except Exception as e:
                last_problem = f"model call failed: {type(exc).__name__}: {exc}"
                logger.warning("%s attempt %d failed: %s", label, attempt, last_problem)
                continue

            raw, parsed, error = result.get("raw"), result.get("parsed"), result.get("parsing_error")
            self._log_attempt(label, attempt, raw)

            problem = None
            if parsed is None:
                problem = _describe_error(error) if error else "The reply was empty."
            elif validate is not None:
                try:
                    validate(parsed)
                except ValueError as exc:
                    problem = str(exc)

            if problem is None:
                return parsed

            logger.warning("%s attempt %d rejected: %s", label, attempt, problem.replace("\n", " | "))
            last_problem=problem

            previous = self._text(raw)
            if parsed is None and previous.strip():
                feedback = [
                    AIMessage(content=previous),
                    HumanMessage(content=f"Your previous reply was rejected:\n{problem}\n\n"
                                         "Reply again with corrected JSON only."),
                ]
            else:
                feedback = [
                    HumanMessage(content=f"A previous attempt was rejected for this reason:\n{problem}\n\n"
                                         "Avoid it. Reply with the JSON only.")
                ]

        raise PlannerError(f"{label}: gave up after {self.max_attempts} attempts. Last problem: {problem}")

    @staticmethod
    def _text(raw) -> str:
        # Handles Extraction of messages from the llms response
        content = getattr(raw, "content", "")
        return content if isinstance(content, str) else str(content)

    def _log_attempt(self, label: str, attempt: int, raw) -> None:
        # Basic Diagonostic for evaluation
        meta = getattr(raw, "response_metadata", None) or {}
        prompt_tokens = meta.get("prompt_eval_count")
        output_tokens = meta.get("eval_count")
        done_reason = meta.get("done_reason")
        logger.info(
            "%s attempt %d: done_reason=%s prompt_tokens=%s output_tokens=%s empty=%s",
            label, attempt, done_reason, prompt_tokens, output_tokens, not self._text(raw).strip(),
        )
        num_ctx = getattr(self.llm, "num_ctx", None)
        if prompt_tokens and num_ctx and prompt_tokens >= 0.9 * num_ctx:
            logger.warning("%s: prompt used %s of %s context tokens; truncation is likely", label, prompt_tokens, num_ctx)
        if done_reason == "length":
            logger.warning("%s: generation stopped at the token limit before finishing", label)

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
        return self._call_structured(
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
        return self._call_structured(
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