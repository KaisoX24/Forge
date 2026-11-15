import argparse
import logging
from pathlib import Path

from lessons.step_generator import StepGenerator
from exercises.verify import make_verifier
from models.course import Course
from models.lesson_generation_models import (
    FunctionCase,
    FunctionExecutionConfig,
    HttpCase,
    HttpExecutionConfig,
)
from planner.curriculum_planner import CurriculumPlanner
from planner.doc_outline import DocOutline
from reasoning.model import get_llm
from retrieval.retriever import Retriever
from retrieval.retrieval_tool import RetrievalTool
from sandbox import ContainerPool
from sandbox.resolver import docs_as_of, spec_from_docs
from config import COURSES_DIR


COURSE_PATH = COURSES_DIR/"fastapi.json"


def load_or_plan(args) -> Course:
    course_path = Path(args.course)

    if course_path.exists():
        return Course.load(course_path)

    raw = Path(args.docs)
    env, _report = spec_from_docs(raw)

    curriculum = CurriculumPlanner(
        args.model,
        outline=DocOutline.from_raw_docs(raw),
    ).create_curriculum("FastAPI")

    course = Course(
        id="fastapi-smoke",
        title="FastAPI",
        framework="fastapi",
        docs_as_of=docs_as_of(raw),
        env=env,
        curriculum=curriculum,
    )

    course_path.parent.mkdir(parents=True, exist_ok=True)
    course.save(course_path)

    return course


def print_exercise(exercise) -> None:
    execution = exercise.execution

    print(f"--- exercise: {exercise.title} [{execution.target}]")
    print(f"Description: {exercise.description}")

    if isinstance(execution, FunctionExecutionConfig):
        print(f"Entry point: {execution.entry_file}:{execution.function_name}")

        for case in exercise.cases:
            if isinstance(case, FunctionCase):
                print(f"  Case: {case.label} | inputs={case.inputs}")

    elif isinstance(execution, HttpExecutionConfig):
        print(f"Command: {' '.join(execution.command)}")
        print(f"Server: {execution.host}:{execution.port}")

        for case in exercise.cases:
            if isinstance(case, HttpCase):
                print(
                    f"  Case: {case.label} | "
                    f"{case.method} {case.path} | "
                    f"status={case.expected_status}"
                )

    print("\nStarter project:")

    for filename, content in exercise.files.items():
        print(f"\n===== {filename} =====")
        print(content)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--docs", default="raw_docs")
    parser.add_argument("--course", default=str(COURSE_PATH))

    parser.add_argument(
        "--module",
        type=int,
        default=1,
        help="1-based module number",
    )
    parser.add_argument(
        "--step",
        type=int,
        help="1-based step number; generates only this step",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="how many steps to generate from the start of the module",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    course = load_or_plan(args)

    if not 1 <= args.module <= len(course.curriculum.modules):
        parser.error(f"Module must be between 1 and {len(course.curriculum.modules)}")

    module_index = args.module - 1
    module = course.curriculum.modules[module_index]

    if args.step is not None:
        if not 1 <= args.step <= len(module.steps):
            parser.error(f"Step must be between 1 and {len(module.steps)}")

        step_indices = [args.step - 1]
    else:
        if args.steps < 1:
            parser.error("--steps must be at least 1")

        step_indices = range(min(args.steps, len(module.steps)))

    retrieval = RetrievalTool(Retriever())

    with ContainerPool(pool_size=2, spec=course.env) as pool:
        generator = StepGenerator(
            get_llm(args.model),
            retrieve=retrieval.retrieve,
            verify=make_verifier(pool, course.env),
            packages=list(course.env.packages),
        )

        for step_index in step_indices:
            outcome = generator.generate_step(
                course,
                module_index,
                step_index,
            )

            course.save(Path(args.course))

            print(
                f"\n{outcome.step_id}: {outcome.status} "
                f"grounding={outcome.grounding} "
                f"{outcome.reason or ''}"
            )

            lesson = course.lessons.get(outcome.step_id)
            if lesson is not None:
                print(f"\n===== {outcome.step_id}: {lesson.title}")
                print(lesson.summary)

                if lesson.exercise is not None:
                    print_exercise(lesson.exercise)

    print(f"\nSaved to {args.course}")


if __name__ == "__main__":
    main()
