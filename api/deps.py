from collections.abc import Generator
from typing import Annotated

from fastapi import Depends,Request
from sqlalchemy.orm import Session

from api.services.course_store import CourseStore
from api.services.grader_registry import GraderRegistry
from api.services.job_worker import JobWorker
from api.services.jobs import JobService
from api.storage.db import session_scope

def get_store(request:Request) -> CourseStore:
    return request.app.state.store

def get_jobs(request: Request) -> JobService:
    return request.app.state.jobs

def get_worker(request: Request) -> JobWorker:
    return request.app.state.worker

def get_registry(request:Request) -> GraderRegistry:
    return request.app.state.registry

def get_session(request: Request) -> Generator[Session, None, None]:
    "Yields ones session per request"
    with session_scope(request.app.state.session_factory) as session:
        yield session

Store=Annotated[CourseStore,Depends(get_store)]
Jobs = Annotated[JobService, Depends(get_jobs)]
Worker = Annotated[JobWorker, Depends(get_worker)]
Registry=Annotated[GraderRegistry,Depends(get_registry)]
DbSession=Annotated[Session,Depends(get_session)]
