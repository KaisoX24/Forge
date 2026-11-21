from collections.abc import Callable

from api.services.grader.grader_registry import GraderRegistry
from exercises.verify import make_verifier
from exercises.import_check import make_import_checker
from lessons.step_generator import StepGenerator
from models.course import Course
from api.services.reasoning_models.model_factory import get_model,resolve_limits
from functools import lru_cache


@lru_cache(maxsize=1)
def _default_retrieval():
    "Built on first use and then kept: loading the embedding model is slow."
    from retrieval.retrieval_tool import RetrievalTool
    from retrieval.retriever import Retriever
    return RetrievalTool(Retriever())


def make_generator_factory(
    registry: GraderRegistry,
    *,
    retrieval_factory: Callable[[], object] = _default_retrieval,
):
    """The verifier shares the course's sandbox pool with the grader, and on_stage reports progress to the job."""

    def make(course_key: str, course: Course, on_stage: Callable[[str, str], None]) -> StepGenerator:
        retrieval = retrieval_factory()
        pool = registry.pool_for(course_key, course.env)
        limits=resolve_limits()
        return StepGenerator(
            get_model(limits),
            retrieve=retrieval.retrieve,
            verify=make_verifier(pool, course.env),
            packages=list(course.env.packages),
            on_stage=on_stage,
            num_ctx=limits.num_ctx,
            num_predict=limits.num_predict,
            check_imports=make_import_checker(pool,list(course.env.packages))
        )

    return make