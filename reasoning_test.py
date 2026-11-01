# from pathlib import Path
# from statistics import median
# from course_sources import FASTAPI_URLS
# from planner.curriculum_planner import CurriculumPlanner
# from planner.doc_outline import DocOutline
# from retrieval.retriever import Retriever
# from retrieval.retrieval_tool import RetrievalTool
# from exercises.grounding import ground_module
# outline = DocOutline.from_raw_docs(Path("raw_docs"), order=FASTAPI_URLS)
# retriever=Retriever()
# retriever_tool=RetrievalTool(retriever)

# planner = CurriculumPlanner("qwen3.5:9b", outline=outline,retrieval=retriever_tool)
# curriculum = planner.create_curriculum("FastAPI")

# retriever = Retriever(distance_threshold=float("inf"))


# def best_distance(query: str) -> float | None:
#     hits = retriever.retrieve(query, top_k=5)
#     return min((h.distance for h in hits), default=None)


# for module in curriculum.modules:
#     g=ground_module(module,lambda q:retriever.retrieve(q,top_k=5))
#     print(f"{module.title}: {g.label}  {g.counts}")
#     for item in g.items:
#         print(f"   {item.label:<9} cov={item.coverage:.2f}  {item.requirement[:70]}")


# from pathlib import Path
# from sandbox.environment import scan_docs,propose_packages

# scan=scan_docs(Path('raw_docs'))
# print(scan.imports.keys())
# print(scan.install_hints)
# print(propose_packages(scan))