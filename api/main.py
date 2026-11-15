from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors.errors import registry_error_handlers
from api.services.course_store import CourseStore
from api.services.grader_registry import GraderRegistry
from api.services.jobs import JobService
from api.services.job_worker import JobWorker
from api.storage.db import init_db,make_engine,make_session_factory
from api.routers import courses,exercises,jobs
from config import COURSES_DIR,LEARNER_DB_URL

DEV_ORIGINS = ["http://localhost:5173","http://127.0.0.1:5173"]

def create_app(
    courses_dir: str | Path = COURSES_DIR,
    db_url: str = LEARNER_DB_URL,
    registry: GraderRegistry | None = None,
    make_generator: Callable | None = None,
    start_worker: bool = True,
    cors_origins: list[str] = DEV_ORIGINS,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Path(courses_dir).mkdir(parents=True, exist_ok=True)
        engine = make_engine(db_url)
        init_db(engine)
        factory = make_session_factory(engine)
        app.state.session_factory = factory
        app.state.jobs = JobService(factory)
        generator_factory = make_generator
        if generator_factory is None:
            from api.services.generation import make_generator_factory
            generator_factory = make_generator_factory(app.state.registry)
        app.state.worker = JobWorker(jobs=app.state.jobs, store=app.state.store,
                                     session_factory=factory, make_generator=generator_factory)
        if start_worker:
            app.state.worker.start()
        yield
        app.state.worker.stop()
        app.state.registry.close()
        engine.dispose()

    app=FastAPI(title="Forge",lifespan=lifespan,description="Interactive Learning platform for python framework/libraries")
    app.include_router(courses.router)
    app.include_router(exercises.router)
    app.include_router(jobs.router)
    app.state.store=CourseStore(courses_dir)
    app.state.registry=registry or GraderRegistry()

    app.add_middleware(
        CORSMiddleware,allow_origins=cors_origins,
        allow_methods=["*"],allow_headers=["*"]
    )
    registry_error_handlers(app)

    @app.get("/api/health")
    def health():
        return {'status':'online'}

    return app

    