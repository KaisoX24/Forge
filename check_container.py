"""Run the case runner inside your REAL sandbox container.

    python check_container.py

Each check prints PASS/FAIL with a reason. Nothing here calls a model.
"""
from exercises.case_runner import HarnessError, grade, run_cases


def run_checks(run_script) -> list[tuple[str, bool, str]]:
    results = []

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    # 1. basic round trip (also proves bytes output from exec_run is decoded)
    rep = run_cases(run_script, "def total(xs):\n    return sum(xs)\n", "total", [[[1, 2, 3]], [[]], [[5]]])
    check("basic values", [c.value for c in rep.cases] == [6, 0, 5], str([c.value for c in rep.cases]))

    # 2. noisy code: prints, stderr output and unicode must not break parsing
    noisy = ("import sys\n"
             "def f(x):\n"
             "    print('hello \u2713')\n"
             "    print('warn', file=sys.stderr)\n"
             "    return x * 2\n")
    rep = run_cases(run_script, noisy, "f", [[2]])
    check("noisy output", rep.fatal is None and rep.cases[0].value == 4, str(rep))

    # 3. one crashing case must not hide the others
    rep = run_cases(run_script, "def f(x):\n    return 10 // x\n", "f", [[2], [0], [5]])
    check("crash isolation", [c.ok for c in rep.cases] == [True, False, True], str([c.error for c in rep.cases]))

    # 4. SIGALRM: an infinite loop in ONE case becomes a per-case timeout
    loop = "def f(x):\n    while x == 0:\n        pass\n    return x\n"
    rep = run_cases(run_script, loop, "f", [[1], [0], [2]], case_timeout=1)
    check("per-case timeout (SIGALRM)", [c.ok for c in rep.cases] == [True, False, True]
          and "Timeout" in (rep.cases[1].error or ""), str([c.error for c in rep.cases]))

    # 5. load errors are reported, not crashed
    rep = run_cases(run_script, "def f(:\n", "f", [[1]])
    check("syntax error reported", bool(rep.fatal) and "SyntaxError" in rep.fatal, str(rep.fatal))

    # 6. grading separates wrong answers from errors
    rep = run_cases(run_script, "def f(x):\n    return x + 1\n", "f", [[1], [2]])
    graded = grade(rep, [2, 99])
    check("grade wrong_output", graded[0]["passed"] and graded[1].get("reason") == "wrong_output", str(graded))

    # 7. INFORMATIONAL: is pydantic in the image? (python:3.11-slim does not ship it)
    rep = run_cases(run_script, "def f():\n    import pydantic\n    return pydantic.VERSION\n", "f", [[]])
    have = rep.cases[0].ok
    check("pydantic available (informational)", True,
          f"yes, version {rep.cases[0].value}" if have else f"NO -> {rep.cases[0].error}")
    return results


def main() -> None:
    from sandbox.container_pool import ContainerPool
    from sandbox.sandbox import SandBox

    with ContainerPool(pool_size=1) as pool:
        def run_script(code):
            return SandBox(pool, code, timeout_seconds=15).sandbox_instance()

        try:
            results = run_checks(run_script)
        except HarnessError as exc:
            print("HARNESS ERROR (the sandbox run itself failed):", exc)
            return
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name:<34} {detail[:90]}")


if __name__ == "__main__":
    main()