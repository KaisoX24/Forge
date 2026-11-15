import json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from api.storage.models import Job


class StepResult(BaseModel):
    step_id: str
    status: Literal["ready", "lesson_failed", "exercise_failed", "skipped"]
    reason: str | None = None


class JobView(BaseModel):
    id: str
    course_key: str
    kind: Literal["module", "step"]
    module_index: int | None
    step_id: str | None
    regenerate: bool
    status: Literal["queued", "running", "done", "failed"]
    total_steps: int
    done_steps: int
    current_step: str | None
    current_stage: str | None
    results: list[StepResult]
    error: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, job: Job) -> "JobView":
        return cls(
            id=job.id, course_key=job.course_id, kind=job.kind, module_index=job.module_index,
            step_id=job.step_id, regenerate=job.regenerate, status=job.status,
            total_steps=job.total_steps, done_steps=job.done_steps,
            current_step=job.current_step, current_stage=job.current_stage,
            results=[StepResult(**r) for r in json.loads(job.results_json)],
            error=job.error, created_at=job.created_at,
        )