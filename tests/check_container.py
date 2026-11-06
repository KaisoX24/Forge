from exercises.case_runner import HarnessError, grade, run_cases


def run_checks(run_script) -> list[tuple[str, bool, str]]:
    results = []

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    def run_project(
        files: dict[str, str],
        entry_file: str,
        function_name: str,
        inputs: list[list],
        case_timeout: int = 2,
    ):
        return run_cases(
            run_script,
            files,
            entry_file,
            function_name,
            inputs,
            case_timeout=case_timeout,
        )

    # 1. Basic single-file round trip.
    rep = run_project(
        {
            "main.py": "def total(xs):\n    return sum(xs)\n",
        },
        "main.py",
        "total",
        [[[1, 2, 3]], [[]], [[5]]],
    )
    check(
        "basic values",
        rep.fatal is None
        and [c.value for c in rep.cases] == [6, 0, 5],
        str([c.value for c in rep.cases]),
    )

    # 2. Noisy code: prints, stderr and unicode must not break parsing.
    noisy = (
        "import sys\n"
        "def f(x):\n"
        "    print('hello \u2713')\n"
        "    print('warn', file=sys.stderr)\n"
        "    return x * 2\n"
    )
    rep = run_project(
        {"main.py": noisy},
        "main.py",
        "f",
        [[2]],
    )
    check(
        "noisy output",
        rep.fatal is None
        and rep.cases[0].value == 4,
        str(rep),
    )

    # 3. One crashing case must not hide the others.
    rep = run_project(
        {
            "main.py": (
                "def f(x):\n"
                "    return 10 // x\n"
            ),
        },
        "main.py",
        "f",
        [[2], [0], [5]],
    )
    check(
        "crash isolation",
        [c.ok for c in rep.cases] == [True, False, True],
        str([c.error for c in rep.cases]),
    )

    # 4. SIGALRM: an infinite loop in ONE case becomes a per-case timeout.
    loop = (
        "def f(x):\n"
        "    while x == 0:\n"
        "        pass\n"
        "    return x\n"
    )
    rep = run_project(
        {"main.py": loop},
        "main.py",
        "f",
        [[1], [0], [2]],
        case_timeout=1,
    )
    check(
        "per-case timeout (SIGALRM)",
        [c.ok for c in rep.cases] == [True, False, True]
        and "Timeout" in (rep.cases[1].error or ""),
        str([c.error for c in rep.cases]),
    )

    # 5. Load errors are reported, not crashed.
    rep = run_project(
        {"main.py": "def f(:\n"},
        "main.py",
        "f",
        [[1]],
    )
    check(
        "syntax error reported",
        bool(rep.fatal) and "SyntaxError" in rep.fatal,
        str(rep.fatal),
    )

    # 6. Grading separates wrong answers from errors.
    rep = run_project(
        {
            "main.py": (
                "def f(x):\n"
                "    return x + 1\n"
            ),
        },
        "main.py",
        "f",
        [[1], [2]],
    )
    graded = grade(rep, [2, 99])
    check(
        "grade wrong_output",
        graded[0]["passed"]
        and graded[1].get("reason") == "wrong_output",
        str(graded),
    )

    # 7. Root-level helper imports.
    rep = run_project(
        {
            "main.py": (
                "from helpers import calculate\n"
                "\n"
                "def process(x):\n"
                "    return calculate(x)\n"
            ),
            "helpers.py": (
                "def calculate(x):\n"
                "    return x * 3\n"
            ),
        },
        "main.py",
        "process",
        [[2], [5]],
    )
    check(
        "root-level helper import",
        rep.fatal is None
        and [c.value for c in rep.cases] == [6, 15],
        str(rep),
    )

    # 8. Nested regular package with relative imports.
    rep = run_project(
        {
            "app/__init__.py": "",
            "app/main.py": (
                "from .helpers import calculate\n"
                "\n"
                "def process(x):\n"
                "    return calculate(x)\n"
            ),
            "app/helpers.py": (
                "def calculate(x):\n"
                "    return x + 10\n"
            ),
        },
        "app/main.py",
        "process",
        [[1], [5]],
    )
    check(
        "nested package relative import",
        rep.fatal is None
        and [c.value for c in rep.cases] == [11, 15],
        str(rep),
    )

    # 9. Namespace package imports (without __init__.py).
    rep = run_project(
        {
            "src/myapp/main.py": (
                "from .helpers import calculate\n"
                "\n"
                "def process(x):\n"
                "    return calculate(x)\n"
            ),
            "src/myapp/helpers.py": (
                "def calculate(x):\n"
                "    return x ** 2\n"
            ),
        },
        "src/myapp/main.py",
        "process",
        [[3], [4]],
    )
    check(
        "namespace package import",
        rep.fatal is None
        and [c.value for c in rep.cases] == [9, 16],
        str(rep),
    )

    # 10. Lazy imports inside the tested function.
    rep = run_project(
        {
            "main.py": (
                "def process(x):\n"
                "    from helpers import calculate\n"
                "    return calculate(x)\n"
            ),
            "helpers.py": (
                "def calculate(x):\n"
                "    return x * 5\n"
            ),
        },
        "main.py",
        "process",
        [[2], [3]],
    )
    check(
        "lazy helper import",
        rep.fatal is None
        and [c.value for c in rep.cases] == [10, 15],
        str(rep),
    )

    # 11. All cases share the same loaded module and its state.
    rep = run_project(
        {
            "main.py": (
                "counter = 0\n"
                "\n"
                "def process():\n"
                "    global counter\n"
                "    counter += 1\n"
                "    return counter\n"
            ),
        },
        "main.py",
        "process",
        [[], [], []],
    )
    check(
        "shared module state",
        rep.fatal is None
        and [c.value for c in rep.cases] == [1, 2, 3],
        str(rep),
    )

    # 12. Missing entry files are reported as fatal errors.
    rep = run_project(
        {
            "main.py": "def process():\n    return 1\n",
        },
        "missing.py",
        "process",
        [[]],
    )
    check(
        "missing entry file",
        bool(rep.fatal) and "does not exist" in rep.fatal,
        str(rep.fatal),
    )

    # 13. Invalid project paths are rejected.
    rep = run_project(
        {
            "main.py": "def process():\n    return 1\n",
            "../outside.py": "value = 1\n",
        },
        "main.py",
        "process",
        [[]],
    )
    check(
        "path traversal rejected",
        bool(rep.fatal) and "Invalid project path" in rep.fatal,
        str(rep.fatal),
    )

    # 14. Missing functions are reported as fatal errors.
    rep = run_project(
        {
            "main.py": (
                "def another_function():\n"
                "    return 1\n"
            ),
        },
        "main.py",
        "process",
        [[]],
    )
    check(
        "missing function reported",
        bool(rep.fatal)
        and "does not define a callable" in rep.fatal,
        str(rep.fatal),
    )

    # 15. INFORMATIONAL: is pydantic in the image?
    # python:3.11-slim does not ship it by default.
    rep = run_project(
        {
            "main.py": (
                "def f():\n"
                "    import pydantic\n"
                "    return pydantic.VERSION\n"
            ),
        },
        "main.py",
        "f",
        [[]],
    )

    have = bool(rep.cases) and rep.cases[0].ok

    check(
        "pydantic available (informational)",
        True,
        (
            f"yes, version {rep.cases[0].value}"
            if have
            else (
                f"NO -> {rep.cases[0].error}"
                if rep.cases
                else f"NO -> {rep.fatal}"
            )
        ),
    )

    return results


def main() -> None:
    from sandbox.container_pool import ContainerPool
    from sandbox.sandbox import SandBox

    with ContainerPool(pool_size=1) as pool:

        def run_script(code):
            return SandBox(
                pool,
                code,
                timeout_seconds=15,
            ).sandbox_instance()

        try:
            results = run_checks(run_script)
        except HarnessError as exc:
            print(
                "HARNESS ERROR (the sandbox run itself failed):",
                exc,
            )
            return

    for name, passed, detail in results:
        print(
            f"{'PASS' if passed else 'FAIL'}  "
            f"{name:<34} {detail[:90]}"
        )


if __name__ == "__main__":
    main()
