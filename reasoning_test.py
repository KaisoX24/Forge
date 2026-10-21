from retrieval.retriever import Retriever
from retrieval.retrieval_tool import RetrievalTool
from planner.curriculum_planner import CurriculumPlanner


def main():
    retriever = Retriever()

    retrieval_tool = RetrievalTool(retriever)

    planner = CurriculumPlanner(
        model_name="qwen3.5:9b",
        retrieval=retrieval_tool
    )

    technology = "FastAPI"

    print(f"Creating curriculum for: {technology}")
    print("=" * 80)

    curriculum = planner.create_curriculum(technology)

    print("\nCURRICULUM")
    print("=" * 80)

    for index, module in enumerate(curriculum.modules, start=1):
        print(f"\nMODULE {index}: {module.title}")
        print("-" * 80)

        print("\nObjectives:")
        for objective in module.objectives:
            print(f"  - {objective}")

        print("\nDocumentation Requirements:")
        for requirement in module.documentation_requirements:
            print(f"  - {requirement}")

        print()


if __name__ == "__main__":
    main()