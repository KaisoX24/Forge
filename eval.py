import argparse
import logging
import time
from collections import Counter
from pathlib import Path

from planner.curriculum_planner import CurriculumPlanner, PlannerError
from planner.doc_outline import DocOutline
from retrieval.retriever import Retriever
from retrieval.retrieval_tool import RetrievalTool

class _EventCounter(logging.Handler):
    """Counts repair-loop rejections and skipped modules, without hiding the log."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.rejected = 0
        self.skipped = 0

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if " rejected: " in message:
            self.rejected += 1
        elif message.startswith("Skipping module"):
            self.skipped += 1


def run_eval(planner: CurriculumPlanner, technology: str, runs: int) -> list[dict]:
    counter = _EventCounter()
    logging.getLogger().addHandler(counter)
    results = []
    try:
        for run in range(1, runs + 1):
            print(f"\n=== RUN {run}/{runs} ===")
            counter.rejected = counter.skipped = 0
            started = time.perf_counter()
            record = {"outcome": "ok", "modules": 0, "steps": 0}
            try:
                curriculum = planner.create_curriculum(technology)
            except PlannerError as exc:
                record["outcome"] = "planner_error"
                print(f"[FAILED] {exc}")
            except Exception as exc:
                record["outcome"] = f"crash: {type(exc).__name__}"
                print(f"[CRASH] {type(exc).__name__}: {exc}")
            else:
                record["modules"] = len(curriculum.modules)
                record["steps"] = sum(len(m.steps) for m in curriculum.modules)
                print(f"[OK] {record['modules']} modules, {record['steps']} steps")
                for i, module in enumerate(curriculum.modules, 1):
                    print(f"  {i}. {module.title}")
                    for step in module.steps:
                        print(f"       - {step.objective}")
            record["seconds"] = time.perf_counter() - started
            record["rejected"] = counter.rejected
            record["skipped"] = counter.skipped
            results.append(record)
    finally:
        logging.getLogger().removeHandler(counter)
    return results


def print_summary(results: list[dict]) -> None:
    total = len(results)
    outcomes = Counter(r["outcome"] for r in results)
    print("\n" + "=" * 60)
    print("OUTCOMES")
    for name, count in outcomes.most_common():
        print(f"  {name:<22} {count}/{total}")

    ok = [r for r in results if r["outcome"] == "ok"]
    print("\nREPAIR LOOP")
    print(f"  runs that needed >=1 repair   {sum(1 for r in results if r['rejected'])}/{total}")
    print(f"  total rejected attempts       {sum(r['rejected'] for r in results)}")
    print(f"  runs with a skipped module    {sum(1 for r in results if r['skipped'])}/{total}")

    print("\nQUALITY (successful runs)")
    if ok:
        print(f"  avg modules                   {sum(r['modules'] for r in ok) / len(ok):.1f}")
        print(f"  avg steps                     {sum(r['steps'] for r in ok) / len(ok):.1f}")
    else:
        print("  no successful runs")
    print(f"\nTIME  avg {sum(r['seconds'] for r in results) / total:.1f}s per run")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--tech", default="FastAPI")
    parser.add_argument("--docs", default="raw_docs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="    %(levelname)s %(message)s")
    retriever=Retriever()
    retriever_tool=RetrievalTool(retriever)
    planner = CurriculumPlanner(args.model, outline=DocOutline.from_raw_docs(Path(args.docs)),retrieval=retriever_tool)
    print_summary(run_eval(planner, args.tech, args.runs))


if __name__ == "__main__":
    main()