from typing import Literal
from pydantic import BaseModel

from models.lesson_generation_models import Exercise

_TARGETS=Literal['function','http']

class PublicExercise(BaseModel):
    "Public Exercise Field for the frontend side of the app"
    title:str
    description:str
    instructions:list[str]
    difficulty:str
    target:_TARGETS
    files:dict[str,str]
    hint_count:int
    hints:list[str]
    explanation:str | None

    @classmethod
    def from_exercise(cls, exercise: Exercise, *, hints_revealed: int,
                      solved: bool) -> "PublicExercise":
        return cls(
            title=exercise.title,
            description=exercise.description,
            instructions=exercise.instructions,
            difficulty=exercise.difficulty,
            target=exercise.execution.target,
            files=exercise.files,
            hint_count=len(exercise.hints),
            hints=exercise.hints[:hints_revealed],
            explanation=exercise.explanation if solved else None,
        )