from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import Literal

from lessons.docs_context import StepDocs
from models.course import Course
from models.data_models import ObjectivePlan
from models.lesson_generation_models import (
    CalloutBlock,CodeBlock,KeyPointsBlock,Label,Lesson,LessonDraft,TextBlock,
    ReferenceDraft,StarterDraft
)

logger=logging.getLogger(__name__)

MAX_EARLIER_STEPS=8


class GenerationError(RuntimeError):
    "A model stage could not produce valid output within its attempt budget."

@dataclass(frozen=True)
class StepOutcome:
    step_id:str
    status:Literal["ready", "lesson_failed", "exercise_failed", "skipped"]
    grounding:Label | None = None
    reason:str | None = None

# lesson stage

_SHELL_PREFIXES = ("uv ", "pip ", "pip3 ", "python ", "python3 ", "cd ", "mkdir ",
                   "source ", "export ", "uvicorn ", "fastapi ", "curl ", "$ ", "#")

def _looks_like_shell(code: str) -> bool:
    lines = [l.strip() for l in code.splitlines() if l.strip()]
    return bool(lines) and all(l.startswith(_SHELL_PREFIXES) for l in lines)

def validate_lesson_draft(draft:LessonDraft) -> None:
    "The example is never run, but it must at least be Python the learner can read."
    code=draft.example_code
    if "```" in code:
        raise ValueError("example_code must be plain Python code, without markdown fences.")

    if not code.strip():
        raise ValueError("example_code is empty. Give a small complete Python example.")

    if draft.example_language == "python" and _looks_like_shell(code):
        return draft.model_copy(update={"example_language": "bash"})

    if draft.example_language !='python':
        return

    try:
        ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"example_code is not valid Python ({exc.msg} on line {exc.lineno}). Fix it.") from exc


def lesson_from_draft(sid:str,objective:str,draft:LessonDraft,docs:StepDocs) -> Lesson:
    return Lesson(
        id=sid,title=objective,summary=draft.summary,you_will_learn=list(draft.you_will_learn),
        blocks=[
            TextBlock(heading=draft.concept_heading,body=draft.concept_text),
            KeyPointsBlock(items=draft.key_points),
            CodeBlock(title=draft.example_title,language=draft.example_language,code=draft.example_code),
            CalloutBlock(kind='tip',text=draft.tip)
        ],
        docs=docs.refs
    )

def earlier_steps_text(course: Course, sid: str) -> str:
    "Only titles and 'you will learn' bullets of earlier ready steps, never their full text or examples."
    ids = course.step_ids
    done = [i for i in ids[:ids.index(sid)] if i in course.lessons][-MAX_EARLIER_STEPS:]
    if not done:
        return "none (this is the first step)"
    return "\n".join(f"- {course.lessons[i].title}: " + "; ".join(course.lessons[i].you_will_learn) for i in done)

def lesson_message(course: Course, module_title: str, module_index: int, step: ObjectivePlan,
                   sid: str, docs: StepDocs) -> str:
    requirements = "\n".join(f"- {r}" for r in step.requirements)
    return (f"Course: {course.title}\n"
            f"Module {module_index + 1}: {module_title}\n"
            f"Step objective: {step.objective}\n"
            f"Questions this lesson must answer:\n{requirements}\n\n"
            f"Earlier steps (do not repeat them):\n{earlier_steps_text(course, sid)}\n\n"
            f"Documentation:\n{docs.text or '(no documentation was found for this step)'}")

# exercise stage

def lesson_brief(lesson:Lesson) -> str:
    "What the exercise model sees of the lesson: the concept and key points, NOT the example code."
    parts:list[str]=[]
    for block in lesson.blocks:
        if isinstance(block,TextBlock): parts.append(f"{block.heading or 'Concept'}: {block.body}")
        elif isinstance(block,KeyPointsBlock): parts.extend(f"- {k.title}: {k.text}" for k in block.items)

    return "\n".join(parts)

def exercise_message(objective: str, lesson: Lesson, packages: list[str]) -> str:
    installed = ", ".join(packages) if packages else "none (standard library only)"
    return (f"Step objective: {objective}\n\n"
            f"The lesson the learner just read:\n{lesson_brief(lesson)}\n\n"
            f"Installed packages in the grader: {installed}")

def _project_text(files: dict[str, str]) -> str:
    return "\n\n".join(f"--- {path} ---\n{code}" for path, code in files.items())

def starter_message(objective: str, lesson: Lesson, packages: list[str],
                    reference: ReferenceDraft) -> str:
    "Stage 2 input: the usual context plus the finished reference."
    return (exercise_message(objective, lesson, packages) + "\n\n"
            f"Reference solution:\n{_project_text(reference.reference_files)}\n\n"
            f"Execution settings:\n{reference.execution.model_dump_json()}")


def cases_message(objective: str, lesson: Lesson, packages: list[str],
                  reference: ReferenceDraft, starter: StarterDraft) -> str:
    "Stage 3 input: the reference, plus the starter the cases must tell apart from it."
    return (starter_message(objective, lesson, packages, reference) + "\n\n"
            f"The learner's starter:\n{_project_text(starter.files)}")