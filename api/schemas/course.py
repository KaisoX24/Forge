from typing import Literal
from pydantic import BaseModel

_LESSON_STATUS=Literal["pending", "ready", "failed"]
_PROGRESS_STATUS=Literal["open", "solved", "gave_up", "completed"]

class StepSummary(BaseModel):
    id:str
    title:str
    lesson:_LESSON_STATUS
    has_exercise:bool
    progress:_PROGRESS_STATUS

class ModuleSummary(BaseModel):
    index:int
    title:str
    unlocked:bool
    steps:list[StepSummary]

class CourseSummary(BaseModel):
    key:str
    title:str
    framework:str
    progress_percent:int

class CourseOutline(CourseSummary):
    modules:list[ModuleSummary]