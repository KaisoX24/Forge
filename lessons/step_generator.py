from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
import ast
import logging

from langchain.messages import HumanMessage,SystemMessage

from lessons.docs_context import docs_budget,prepare_step_docs
from lessons.generator import (
    StepOutcome,lesson_message,validate_lesson_draft,lesson_from_draft,
    GenerationError,exercise_message,starter_message,cases_message)
from models.course import Course,step_id
from models.data_models import RetrievedDocument
from models.lesson_generation_models import (
    Exercise,ExerciseDraft,Label,
    Lesson,LessonDraft,ReferenceDraft,StarterDraft,CasesDraft)
from reasoning.structured import StructuredResult

Verify = Callable[[ExerciseDraft], Exercise]
Retrieve = Callable[[str], list[RetrievedDocument]]
logger=logging.getLogger(__name__)
_PROMPT_DIR=Path(__file__).parent.parent/'reasoning'/'system_messages'
_HTTP_HINTS = ("endpoint", "route", "path operation", "get request", "post request",
               "httpexception", "status code", "query parameter", "path parameter",
               "depends", "dependenc")
_REFERENCE_FAULTS = (
    "The reference application could not be evaluated",
    "The reference solution could not be loaded",
    "The reference solution gave different results",
)

def _is_reference_fault(error_text: str) -> bool:
    return any(marker in error_text for marker in _REFERENCE_FAULTS)

def retry_on_reference_fault(attempt, rounds: int = 2):
    """attempt(previous_problem) -> result. If it fails because the reference itself is broken,
    try again (up to `rounds` in total), telling the next attempt what went wrong."""
    problem = None
    for _ in range(rounds):
        try:
            return attempt(problem)
        except GenerationError as exc:
            if not _is_reference_fault(str(exc)):
                raise
            problem = str(exc)
    raise GenerationError(problem)

def _pick_target(objective: str, planned: str | None) -> str:
    "Endpoint-style objectives can only be proven over HTTP, whatever the planner said."
    if any(h in objective.lower() for h in _HTTP_HINTS):
        return "http"
    return planned or "function"

def _top_names(source: str) -> set[str]:
    return {n.name for n in ast.parse(source).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

def _check_reference(ref: ReferenceDraft, check_imports=None) -> None:
    "Syntax for every file, the entry function for function exercises, and imports for all."
    for path, code in ref.reference_files.items():
        if path.endswith(".py"):
            try:
                compile(code, path, "exec")
            except SyntaxError as exc:
                raise ValueError(f"{path} is not valid Python: {exc.msg} (line {exc.lineno}). Fix it.")

    ex = ref.execution
    if ex.target == 'function':
        source = ref.reference_files.get(ex.entry_file)
        if source is None:
            raise ValueError(f"entry_file {ex.entry_file!r} is not one of the reference files.")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise ValueError(f"The reference is not valid Python: {exc}")
        defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        if ex.function_name not in defs:
            raise ValueError(
                f"function_name {ex.function_name!r} is not a top-level regular `def` in "
                f"{ex.entry_file}. It defines these functions: {defs}. Add a function with that "
                "name that takes plain values, builds the class inside, and returns a dict.")

    if check_imports is not None:
        problems = check_imports(ref.reference_files)
        if problems:
            raise ValueError("The reference imports names that do not exist in this environment:\n"
                             + "\n".join(f"- {p}" for p in problems) + "\nFix these imports.")

def _check_starter(ref: ReferenceDraft, starter: StarterDraft) -> None:
    same = starter.files.keys() == ref.reference_files.keys()
    try:
        for path, code in ref.reference_files.items():
            if path in starter.files:
                missing = _top_names(code) - _top_names(starter.files[path])
                if missing:
                    raise ValueError(
                        f"The starter in {path} removed {sorted(missing)}. Never delete a "
                        "function or class: keep its def/class line with the same name and "
                        "parameters, and replace only the body with `pass` and a TODO.")
        same = same and all(
            ast.dump(ast.parse(starter.files[p])) == ast.dump(ast.parse(ref.reference_files[p]))
            for p in starter.files)
    except SyntaxError:
        return
    if same:
        raise ValueError("The starter is the same code as the reference apart from comments. "
                         "Remove the behaviour the objective teaches.")

class StepGenerator:
    def __init__(self, llm, *, retrieve: Retrieve, verify: Verify, packages: list[str] | None = None,
                 num_ctx: int = 8192, num_predict: int = 2048, max_attempts: int = 5,
                 on_stage:Callable[[str,str],None]|None=None,prompt_dir: Path | None = None,
                 check_imports: Callable[[dict[str, str]], list[str]] | None = None):
        self.retrieve = retrieve
        self.verify = verify
        self.packages = list(packages or [])
        self._check_imports=check_imports
        self.max_attempts = max_attempts
        self.budget = docs_budget(num_ctx=num_ctx, num_predict=num_predict)
        self.structured = StructuredResult(llm, max_attempts=max_attempts, error_cls=GenerationError)
        prompts = prompt_dir or _PROMPT_DIR
        self.lesson_prompt = (prompts / "lesson.txt").read_text(encoding="utf-8")
        self.stage_prompts = {
            target: {stage: (prompts / f"{target}_{stage}.txt").read_text(encoding="utf-8")
                    for stage in ("reference", "starter", "cases")}
            for target in ("function", "http")
        }
        self._on_stage=on_stage



    @staticmethod
    def _merge(ref: ReferenceDraft, starter: StarterDraft, cases: CasesDraft) -> ExerciseDraft:
        return ExerciseDraft.model_validate(
            {**ref.model_dump(), **starter.model_dump(), **cases.model_dump(exclude_unset=True)})

    def _stage(self, sid: str, stage: str) -> None:
        "Tell whoever is watching which stage a step is in. A bad callback never breaks generation."
        if self._on_stage is not None:
            try:
                self._on_stage(sid, stage)
            except Exception:
                logger.exception("on_stage callback failed") 

    def _generate_reference(self, sid: str, target: str, objective: str, lesson: Lesson,
                            previous_problem: str | None) -> ReferenceDraft:
        prompts = self.stage_prompts[target]
        self._stage(sid, "reference")
        message = exercise_message(objective, lesson, self.packages)
        if previous_problem:
            message += ("\n\nYour previous reference solution failed when it was run:\n"
                        + previous_problem[-600:]
                        + "\nWrite a corrected reference that fixes this error.")
        return self.structured.call(
            ReferenceDraft,
            [SystemMessage(content=prompts["reference"]), HumanMessage(content=message)],
            label=f"reference {sid}",
            validate=lambda r: _check_reference(r, self._check_imports))

    def _starter_and_cases(self, sid: str, target: str, objective: str, lesson: Lesson,ref:ReferenceDraft) -> Exercise:
        prompts = self.stage_prompts[target]
        problem = None
        for _ in range(2):
            note = ""
            self._stage(sid, "starter")
            if problem:
                note = ("\n\nYour previous starter was rejected:\n" + problem[:600] +
                        "\nFix that problem. Keep every def and class name from the reference.")
            starter = self.structured.call(
                StarterDraft,
                [SystemMessage(content=prompts["starter"]),
                HumanMessage(content=starter_message(objective, lesson, self.packages, ref) + note)],
                label=f"starter {sid}",
                validate=lambda s: _check_starter(ref, s))
            
            try:
                self._stage(sid, "cases")
                return self.structured.call(
                    CasesDraft,
                    [SystemMessage(content=prompts["cases"]),
                    HumanMessage(content=cases_message(objective, lesson, self.packages, ref, starter))],
                    label=f"cases {sid}",
                    validate=lambda cases: self.verify(self._merge(ref, starter, cases)))
            except GenerationError as exc:
                text=str(exc)
                if ("already passes" not in text
                        and "starter application could not be evaluated" not in text):
                    raise
                problem = text
        raise GenerationError(problem)

    def _generate_exercise(self, sid: str, target: str, objective: str, lesson: Lesson) -> Exercise:
        def attempt(previous_problem: str | None) -> Exercise:
            ref = self._generate_reference(sid, target, objective, lesson, previous_problem)
            return self._starter_and_cases(sid, target, objective, lesson, ref)
        return retry_on_reference_fault(attempt)

    def generate_step(self, course: Course, module_index: int, step_index: int, *,
                      force: bool = False) -> StepOutcome:
        """Lesson, then exercise. A lesson stays saved even if its exercise fails; a failed exercise is
        retried alone next time. Sandbox/infrastructure errors are NOT recorded as step failures."""
        module = course.curriculum.modules[module_index]
        step = module.steps[step_index]
        sid = step_id(module_index, step_index)
        failure = course.failures.get(sid)
        lesson = course.lessons.get(sid)

        if lesson is not None and failure is None and not force and (lesson.exercise is not None or not step.graded):
            return StepOutcome(sid, "skipped")

        resume_exercise = lesson is not None and failure is not None and failure.stage == "exercise" and not force

        if not resume_exercise:
            docs = prepare_step_docs(step, self.retrieve, budget_tokens=self.budget)
            self._stage(sid,"lesson")
            try:
                draft = self.structured.call(
                    LessonDraft,
                    [SystemMessage(content=self.lesson_prompt),
                     HumanMessage(content=lesson_message(course, module.title, module_index, step, sid, docs))],
                    label=f"lesson {sid}", validate=validate_lesson_draft)
            except GenerationError as exc:
                course.record_failure(sid, "lesson", str(exc), attempts=self.max_attempts)
                return StepOutcome(sid, "lesson_failed", docs.grounding.label, str(exc))
            lesson = lesson_from_draft(sid, step.objective, draft, docs)
            course.upsert_lesson(lesson)

        if not step.graded:
            return StepOutcome(sid, "ready", _label_of(lesson))

        exercise_target=_pick_target(step.objective,step.exercise_target)


        label = _label_of(lesson)
        try:
            exercise = self._generate_exercise(sid, exercise_target, step.objective, lesson)
        except GenerationError as exc:
            course.record_failure(sid, "exercise", str(exc), attempts=self.max_attempts)
            return StepOutcome(sid, "exercise_failed", label, str(exc))

        course.upsert_lesson(lesson.model_copy(update={"exercise": exercise}))
        return StepOutcome(sid, "ready", label)


def _label_of(lesson: Lesson) -> Label | None:
    return lesson.docs[0].grounding if lesson.docs else "unproved"