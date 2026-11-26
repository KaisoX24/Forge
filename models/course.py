from __future__ import annotations

import os
from datetime import datetime,timezone
from typing import Literal
from pathlib import Path
from pydantic import Field,BaseModel,model_validator,HttpUrl,field_validator

from models.data_models import Curriculum,EnvironmentSpec
from models.lesson_generation_models import Lesson

class GenerationFailure(BaseModel):
    "Retry on Lessson Failure"
    stage:Literal['lesson','exercise']
    reason:str
    attempts:int=Field(ge=1)
    failed_at:datetime

def step_id(module_index:int,step_index:int)->str:
    "Generates the step id for the lesson : m1-s1"
    return f"m{module_index+1}-s{step_index+1}"

class CourseSources(BaseModel):
    name:str
    docs_url:HttpUrl
    page_list:list[HttpUrl]=Field(default_factory=list)
    selector:str|None=None

    @field_validator("name")
    @classmethod
    def validate_name(cls,value:str) ->str:
        value=value.strip()
        if not value:
            raise ValueError("Source name cannot be empty")
        return value


class Course(BaseModel):
    schema_version: int = 1
    id: str
    title: str
    framework: str
    docs_as_of: datetime                      
    env: EnvironmentSpec                       
    curriculum: Curriculum                     
    lessons: dict[str, Lesson] = Field(default_factory=dict)
    failures: dict[str, GenerationFailure] = Field(default_factory=dict)


    @property
    def step_ids(self) -> list[str]:
        return [step_id(m, s) for m, module in enumerate(self.curriculum.modules) 
                for s in range(len(module.steps))]

    @property
    def pending_ids(self) -> list[str]:
        "Steps that have no lesson yet, in course order."
        return [sid for sid in self.step_ids if sid not in self.lessons and sid not in self.failures]

    @property
    def failed_ids(self) -> list[str]:
        "Steps whose last generation failed."
        return [sid for sid in self.step_ids if sid in self.failures]

    def status_of(self,sid:str) -> Literal["pending", "ready", "failed"]:
        if sid not in set(self.step_ids):
            raise ValueError(f"{sid!r} is not a step of this curriculum")
        
        return "failed" if sid in self.failures else "ready" if sid in self.lessons else "pending"
    
    @model_validator(mode='after')
    def _lesson_match_curriculum(self) -> "Course":
        valid=set(self.step_ids)
        for key,lesson in self.lessons.items():
            if key not in valid:
                raise ValueError(f"lesson key {key!r} is not a step of this curriculum")
            if lesson.id !=key:
                raise ValueError(f"lesson stored under {key!r} says its id is {lesson.id!r}")

        for key, failure in self.failures.items():
            if key not in valid:
                raise ValueError(f"failure key {key!r} is not a step of this curriculum")
            if failure.stage == "exercise" and key not in self.lessons:
                raise ValueError(f"exercise failure recorded for {key!r}, which has no lesson")
            
        return self

    def upsert_lesson(self, lesson: Lesson) -> None:
        "Add the lesson, or replace the one already stored under the same step id."
        if lesson.id not in set(self.step_ids):
            raise ValueError(f"{lesson.id!r} is not a step of this curriculum")
        self.lessons[lesson.id] = lesson
        failure=self.failures.get(lesson.id)
        if failure and (failure.stage == "lesson" or lesson.exercise is not None):
            del self.failures[lesson.id]

    def record_failure(self, sid: str, stage: Literal["lesson", "exercise"], reason: str,
                       attempts: int = 1, *, now: datetime | None = None) -> None:
        "Flag a step as failed. An older good lesson under the same id is kept, never deleted."
        if sid not in set(self.step_ids):
            raise ValueError(f"{sid!r} is not a step of this curriculum")
        if stage == "exercise" and sid not in self.lessons:
            raise ValueError(f"cannot record an exercise failure for {sid!r}: it has no lesson")
        self.failures[sid] = GenerationFailure(
            stage=stage, reason=reason.strip()[:500], attempts=attempts,
            failed_at=now or datetime.now(timezone.utc))


    def save(self,path:Path|str) -> None:
        "Writes atomically: a crash mid-write leaves the previous file intact."

        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+".tmp")
        try:
            with tmp.open('w',encoding='utf-8')as f:
                f.write(self.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp,path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path: str | Path) -> "Course":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))