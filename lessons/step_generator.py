from __future__ import annotations

from pathlib import Path
from typing import Callable
from langchain.messages import HumanMessage,SystemMessage
from lessons.docs_context import docs_budget,prepare_step_docs
from lessons.generator import StepOutcome,lesson_message,validate_lesson_draft,lesson_from_draft,GenerationError,exercise_message
from models.course import Course,step_id
from models.data_models import RetrievedDocument
from models.lesson_generation_models import Exercise,ExerciseDraft,Label,Lesson,LessonDraft
from reasoning.structured import StructuredResult

Verify = Callable[[ExerciseDraft], Exercise]
Retrieve = Callable[[str], list[RetrievedDocument]]
_PROMPT_DIR=Path(__file__).parent.parent/'reasoning'/'system_messages'

class StepGenerator:
    def __init__(self, llm, *, retrieve: Retrieve, verify: Verify, packages: list[str] | None = None,
                 num_ctx: int = 8192, num_predict: int = 2048, max_attempts: int = 3,
                 prompt_dir: Path | None = None):
        self.retrieve = retrieve
        self.verify = verify
        self.packages = list(packages or [])
        self.max_attempts = max_attempts
        self.budget = docs_budget(num_ctx=num_ctx, num_predict=num_predict)
        self.structured = StructuredResult(llm, max_attempts=max_attempts, error_cls=GenerationError)
        prompts = prompt_dir or _PROMPT_DIR
        self.lesson_prompt = (prompts / "lesson.txt").read_text(encoding="utf-8")
        self.exercise_prompts = {
            "function": (prompts / "function_exercise.txt").read_text(encoding="utf-8"),
            "http": (prompts / "http_exercise.txt").read_text(encoding="utf-8"),
        }

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

        exercise_target=step.exercise_target

        if exercise_target is None:
            exercise_target='function'

        exercise_prompt=self.exercise_prompts.get(exercise_target)

        label = _label_of(lesson)
        try:
            exercise = self.structured.call(
                ExerciseDraft,
                [SystemMessage(content=exercise_prompt),
                 HumanMessage(content=exercise_message(step.objective, lesson, self.packages))],
                label=f"exercise {sid}", validate=self.verify)
        except GenerationError as exc:
            course.record_failure(sid, "exercise", str(exc), attempts=self.max_attempts)
            return StepOutcome(sid, "exercise_failed", label, str(exc))

        course.upsert_lesson(lesson.model_copy(update={"exercise": exercise}))
        return StepOutcome(sid, "ready", label)


def _label_of(lesson: Lesson) -> Label | None:
    return lesson.docs[0].grounding if lesson.docs else "unproved"