from collections.abc import Callable

from api.services.grader_registry import GraderRegistry
from exercises.verify import make_verifier
from exercises.import_check import make_import_checker
from lessons.step_generator import StepGenerator
from models.course import Course
from reasoning.model import get_llm
from functools import lru_cache

GENERATION_MODEL= "qwen3.5:9b"

@lru_cache(maxsize=1)
def _default_retrieval():
    "Built on first use and then kept: loading the embedding model is slow."
    from retrieval.retrieval_tool import RetrievalTool
    from retrieval.retriever import Retriever
    return RetrievalTool(Retriever())


def make_generator_factory(
    registry: GraderRegistry,
    *,
    model: str = GENERATION_MODEL,
    retrieval_factory: Callable[[], object] = _default_retrieval,
):
    """The verifier shares the course's sandbox pool with the grader, and on_stage reports progress to the job."""

    def make(course_key: str, course: Course, on_stage: Callable[[str, str], None]) -> StepGenerator:
        retrieval = retrieval_factory()
        pool = registry.pool_for(course_key, course.env)
        return StepGenerator(
            get_llm(model),
            retrieve=retrieval.retrieve,
            verify=make_verifier(pool, course.env),
            packages=list(course.env.packages),
            on_stage=on_stage,
            check_imports=make_import_checker(pool,list(course.env.packages))
        )

    return make  