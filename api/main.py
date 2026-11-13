from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors.errors import registry_error_handlers
from api.services.course_store import CourseStore
from api.services.grader_registry import GraderRegistry
from api.storage.db import init_db,make_engine,make_session_factory

DEV_ORIGINS = ["http://localhost:5173","http://127.0.0.1:5173"]

def create_app(
    courses_dir: str | Path = "data/courses",
    db_url: str = "sqlite:///data/learner.db",
    registry: GraderRegistry | None = None,
    cors_origins: list[str] = DEV_ORIGINS,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app:FastAPI):
        engine=make_engine(db_url)
        init_db(engine)
        app.state.session_factory=make_session_factory(engine)
        yield
        app.state.registry.close()
        engine.dispose()

    app=FastAPI(title="Forge",lifespan=lifespan,description="Interactive Learning platform for python framework/libraries")
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

    