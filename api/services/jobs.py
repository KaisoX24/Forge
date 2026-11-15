import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session,sessionmaker

from api.schemas.job import JobView
from api.storage.db import session_scope
from api.storage.models import Job

ACTIVE=("queued","running")


class JobService:
    def __init__(self,factory:sessionmaker[Session]):
        self._factory=factory

    def enqueue_module(self,course_key:str,module_index:int,total_steps:int) -> JobView:
        "Queue a module. If the same module is already queued or running, return that job."
        with session_scope(self._factory) as s:
            existing = s.scalars(select(Job).where(
                Job.course_id == course_key, Job.kind == "module",
                Job.module_index == module_index, Job.status.in_(ACTIVE))).first()
            if existing is not None:
                return JobView.from_row(existing)
            job = Job(id=uuid.uuid4().hex,course_id=course_key,kind="module",
                      module_index=module_index,total_steps=total_steps)
            s.add(job)
            s.flush()
            return JobView.from_row(job)

    def enqueue_step(self,course_key:str,step_id:str,*,regenerate:bool=True) -> JobView:
        "Queue one step (a regeneration by default)."
        with session_scope(self._factory) as s:
            existing=s.scalars(select(Job).where(
                Job.course_id == course_key, Job.kind == "step",
                Job.step_id == step_id, Job.status.in_(ACTIVE))).first()

            if existing is not None:
                return JobView.from_row(existing)

            job=Job(id=uuid.uuid4().hex, course_id=course_key, kind="step", step_id=step_id,
                      regenerate=regenerate, total_steps=1)

            s.add(job)
            s.flush()
            return JobView.from_row(job)

    def get(self,job_id:str) ->JobView|None:
        with session_scope(self._factory) as s:
            job = s.get(Job, job_id)
            return None if job is None else JobView.from_row(job)

    def list_for_course(self, course_key:str,*,active_only:bool=False) -> list[JobView]:
        with session_scope(self._factory) as s:
            query = select(Job).where(Job.course_id == course_key)
            if active_only:
                query = query.where(Job.status.in_(ACTIVE))
            rows = s.scalars(query.order_by(Job.created_at.desc())).all()
            return [JobView.from_row(job) for job in rows]

    def claim_next(self) -> JobView | None:
        "Oldest queued job, marked running. None if nothing is waiting."
        with session_scope(self._factory) as s:
            job = s.scalars(select(Job).where(Job.status == "queued")
                            .order_by(Job.created_at, Job.id).limit(1)).first()

            if job is None: return None

            job.status='running'
            return JobView.from_row(job)

    def set_progress(self,job_id:str,step_id:str,stage:str) -> None:
        with session_scope(self._factory) as s:
            job = s.get(Job, job_id)
            if job is not None:
                job.current_step, job.current_stage = step_id, stage


    def finish_step(self, job_id: str, step_id: str, status: str, reason: str | None = None) -> None:
        with session_scope(self._factory) as s:
            job = s.get(Job, job_id)
            if job is None:
                return
            results:list=json.loads(job.results_json)
            results.append({"step_id": step_id, "status": status, "reason": reason})
            job.results_json = json.dumps(results)
            job.done_steps = len(results)
            job.current_step = job.current_stage = None

    def complete(self, job_id: str) -> None:
        self._finish(job_id, "done", None)

    def fail(self, job_id: str, error: str) -> None:
        self._finish(job_id, "failed", error[:500])

    def _finish(self, job_id: str, status: str, error: str | None) -> None:
        with session_scope(self._factory) as s:
            job = s.get(Job, job_id)
            if job is not None:
                job.status, job.error = status, error
                job.current_step = job.current_stage = None

    def recover_interrupted(self) -> int:
        """At startup: a job still marked running was cut off by a crash or restart.
        Mark it failed so it doesn't look alive; queued jobs simply stay queued."""
        with session_scope(self._factory) as s:
            stuck = s.scalars(select(Job).where(Job.status == "running")).all()
            for job in stuck:
                job.status, job.error = "failed", "Interrupted by a restart."
                job.current_step = job.current_stage = None
            return len(stuck)