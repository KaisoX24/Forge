from fastapi import APIRouter

from api.deps import DbSession, Jobs, Store, Worker
from api.errors.errors import NotFound
from api.schemas.job import JobView
from api.services.access import require_open_step

router=APIRouter(tags=['jobs'])

@router.post("/api/courses/{course_key}/modules/{module_index}/generate",
             response_model=JobView, status_code=202)
def generate_module(course_key: str, module_index: int, store: Store, jobs: Jobs, worker: Worker):
    "Queue generation for a module (0-based index). Already queued or running: same job back."
    course = store.get(course_key)
    if not 0 <= module_index < len(course.curriculum.modules):
        raise NotFound("Module not found.")
    steps = len(course.curriculum.modules[module_index].steps)
    job = jobs.enqueue_module(course_key, module_index, steps)
    worker.notify()
    return job

@router.post("/api/courses/{course_key}/steps/{step_id}/regenerate",
             response_model=JobView, status_code=202)
def regenerate_step(course_key: str, step_id: str, store: Store, session: DbSession,
                    jobs: Jobs, worker: Worker):
    "Queue a new lesson and exercise for one step. The current ones stay until the new ones are ready."
    course = store.get(course_key)
    require_open_step(session, course_key, course, step_id)
    job = jobs.enqueue_step(course_key, step_id)
    worker.notify()
    return job


@router.get("/api/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str, jobs: Jobs):
    job = jobs.get(job_id)
    if job is None:
        raise NotFound("Job not found.")
    return job


@router.get("/api/courses/{course_key}/jobs", response_model=list[JobView])
def list_jobs(course_key: str, store: Store, jobs: Jobs, active: bool = False):
    store.get(course_key)
    return jobs.list_for_course(course_key, active_only=active)