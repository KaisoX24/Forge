import argparse
import logging
from pathlib import Path

from lessons.step_generator import StepGenerator
from exercises.verify import make_verifier
from models.course import Course
from planner.curriculum_planner import CurriculumPlanner
from planner.doc_outline import DocOutline
from reasoning.model import get_llm
from retrieval.retriever import Retriever
from retrieval.retrieval_tool import RetrievalTool
from sandbox import ContainerPool
from sandbox.resolver import docs_as_of, spec_from_docs

COURSE_PATH = Path("data/smoke_course.json")


def load_or_plan(args) -> Course:
    if COURSE_PATH.exists():
        return Course.load(COURSE_PATH)
    raw = Path(args.docs)
    env, _report = spec_from_docs(raw)
    curriculum = CurriculumPlanner(args.model, outline=DocOutline.from_raw_docs(raw)).create_curriculum("FastAPI")
    course = Course(id="fastapi-smoke", title="FastAPI", framework="fastapi",
                    docs_as_of=docs_as_of(raw), env=env, curriculum=curriculum)
    COURSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    course.save(COURSE_PATH)
    return course


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--docs", default="raw_docs")
    parser.add_argument("--module", type=int, default=1, help="1-based module number")
    parser.add_argument("--steps", type=int, default=1, help="how many steps from the start of the module")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="    %(levelname)s %(message)s")

    course = load_or_plan(args)
    retrieval = RetrievalTool(Retriever())
    with ContainerPool(pool_size=2, spec=course.env) as pool:
        generator = StepGenerator(get_llm(args.model), retrieve=retrieval.retrieve,
                                  verify=make_verifier(pool, course.env), packages=list(course.env.packages))
        module_index = args.module - 1
        for step_index in range(min(args.steps, len(course.curriculum.modules[module_index].steps))):
            outcome = generator.generate_step(course, module_index, step_index)
            course.save(COURSE_PATH)                       # save after every step
            print(f"\n{outcome.step_id}: {outcome.status}  grounding={outcome.grounding}  {outcome.reason or ''}")

    for sid, lesson in course.lessons.items():
        print(f"\n===== {sid}: {lesson.title}\n{lesson.summary}")
        if lesson.exercise:
            print(f"--- exercise: {lesson.exercise.title} ({lesson.exercise.function_name})")
            print(lesson.exercise.starter_code)
    print(f"\nSaved to {COURSE_PATH}")


if __name__ == "__main__":
    main()
