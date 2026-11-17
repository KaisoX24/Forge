from typing import Literal
from pydantic import BaseModel

from models.lesson_generation_models import Exercise,Block,Lesson

_TARGETS=Literal['function','http']

class PublicExercise(BaseModel):
    "Public Exercise Field for the frontend side of the app"
    title:str
    description:str
    instructions:list[str]
    difficulty:str
    target:_TARGETS
    files:dict[str,str]
    starter_files:dict[str,str]
    hint_count:int
    hints:list[str]
    explanation:str | None

    @classmethod
    def from_exercise(cls, exercise: Exercise, *, hints_revealed: int,
                      solved: bool,files:dict[str,str]|None=None) -> "PublicExercise":
        return cls(
            title=exercise.title,
            description=exercise.description,
            instructions=exercise.instructions,
            difficulty=exercise.difficulty,
            target=exercise.execution.target,
            files=files if files is not None else exercise.files,
            starter_files=exercise.files,
            hint_count=len(exercise.hints),
            hints=exercise.hints[:hints_revealed],
            explanation=exercise.explanation if solved else None,
        )

class PublicDoc(BaseModel):
    label:str
    url:str

class PublicLesson(BaseModel):
    title:str
    summary:str
    you_will_learn:list[str]
    blocks:list[Block]
    docs:list[PublicDoc]

    @classmethod
    def from_lesson(cls,lesson:Lesson) -> "PublicLesson":
        return cls(title=lesson.title, summary=lesson.summary,
                   you_will_learn=lesson.you_will_learn, blocks=lesson.blocks,
                   docs=[PublicDoc(label=d.label, url=d.url) for d in lesson.docs])

class LastAttempt(BaseModel):
    attempt_no:int
    status:Literal["passed", "failed", "error"]
    passed_count:int
    total:int

class StepProgress(BaseModel):
    status: Literal["open", "solved", "gave_up", "completed"]
    hints_revealed:int
    attempts:int
    last_attempt:LastAttempt | None
    give_up_available:bool
    solution_unlocked:bool

class StepPage(BaseModel):
    course_key: str
    step_id: str
    module_index: int
    step_index: int
    objective: str
    lesson_status: Literal["pending", "ready", "failed"]
    lesson: PublicLesson | None
    exercise: PublicExercise | None
    progress: StepProgress
    previous_step_id: str | None
    next_step_id: str | None