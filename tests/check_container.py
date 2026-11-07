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



def run_http_checks(run_script) -> list[tuple[str, bool, str]]:
    """Exercise the HTTP runner against a real local application in Docker."""
    from exercises.http_runner import run_http_cases
    from models.lesson_generation_models import (
        HttpCaseDraft,
        HttpExecutionConfig,
    )

    results = []

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    files = {
        "app.py": (
            "import json\n"
            "import subprocess\n"
            "from http.server import BaseHTTPRequestHandler, "
            "ThreadingHTTPServer\n"
            "from storage import items\n"
            "\n"
            "# A child process lets the integration test exercise process-group cleanup.\n"
            "subprocess.Popen(['python', '-c', 'import time; time.sleep(600)'])\n"
            "\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    def _send(self, status, value, content_type='application/json'):\n"
            "        if content_type == 'application/json':\n"
            "            body = json.dumps(value).encode()\n"
            "        else:\n"
            "            body = value.encode()\n"
            "        self.send_response(status)\n"
            "        self.send_header('Content-Type', content_type)\n"
            "        self.send_header('Content-Length', str(len(body)))\n"
            "        self.end_headers()\n"
            "        self.wfile.write(body)\n"
            "\n"
            "    def do_POST(self):\n"
            "        if self.path != '/items':\n"
            "            return self._send(404, {'detail': 'not found'})\n"
            "        length = int(self.headers.get('Content-Length', '0'))\n"
            "        item = json.loads(self.rfile.read(length))\n"
            "        items.append(item)\n"
            "        self._send(201, {'items': items})\n"
            "\n"
            "    def do_GET(self):\n"
            "        if self.path == '/items':\n"
            "            return self._send(200, {'items': items})\n"
            "        if self.path == '/null':\n"
            "            return self._send(200, None)\n"
            "        if self.path == '/text':\n"
            "            return self._send(200, 'hello from forge', 'text/plain')\n"
            "        return self._send(404, {'detail': 'not found'})\n"
            "\n"
            "server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)\n"
            "server.serve_forever()\n"
        ),
        "storage.py": "items = []\n",
    }

    execution = HttpExecutionConfig(
        command=["python", "app.py"],
        host="127.0.0.1",
        port=8765,
    )

    cases = [
        # Deliberately wrong expected JSON: the next case must still run.
        HttpCaseDraft(
            label="create item",
            method="POST",
            path="/items",
            json_body={"name": "Ada"},
            headers={"Content-Type": "application/json"},
            expected_status=201,
            expected_json={"items": []},
        ),
        HttpCaseDraft(
            label="shared state",
            method="GET",
            path="/items",
            expected_status=200,
            expected_json={"items": [{"name": "Ada"}]},
        ),
        HttpCaseDraft(
            label="explicit null",
            method="GET",
            path="/null",
            expected_status=200,
            expected_json=None,
        ),
        HttpCaseDraft(
            label="plain text",
            method="GET",
            path="/text",
            expected_status=200,
            expected_text="hello from forge",
        ),
        HttpCaseDraft(
            label="not found",
            method="GET",
            path="/missing",
            expected_status=404,
            expected_json={"detail": "not found"},
        ),
    ]

    report = run_http_cases(
        files,
        execution,
        cases,
        run_script=run_script,
    )

    check(
        "HTTP suite completes",
        report.fatal is None,
        str(report.fatal),
    )
    check(
        "HTTP assertion failure is isolated",
        len(report.cases) == 5
        and not report.cases[0].passed
        and report.cases[1].passed,
        str([(case.label, case.passed, case.error) for case in report.cases]),
    )
    check(
        "multi-file app and shared state",
        len(report.cases) >= 2
        and report.cases[1].response_json == {"items": [{"name": "Ada"}]},
        str(report.cases[1] if len(report.cases) >= 2 else report.cases),
    )
    check(
        "explicit JSON null",
        len(report.cases) >= 3
        and report.cases[2].passed
        and report.cases[2].response_is_json
        and report.cases[2].response_json is None,
        str(report.cases[2] if len(report.cases) >= 3 else report.cases),
    )
    check(
        "text and non-2xx responses",
        len(report.cases) == 5
        and report.cases[3].passed
        and report.cases[3].response_text == "hello from forge"
        and report.cases[4].passed
        and report.cases[4].status_code == 404,
        str([(case.label, case.status_code, case.response_text, case.error)
             for case in report.cases]),
    )

    # A process that exits during startup must be surfaced as a suite failure.
    failed_start = run_http_cases(
        {"unused.py": "value = 1\n"},
        HttpExecutionConfig(
            command=["python", "missing_app.py"],
            host="127.0.0.1",
            port=8766,
        ),
        cases[:3],
        run_script=run_script,
    )
    check(
        "application startup failure is fatal",
        bool(failed_start.fatal) and not failed_start.cases,
        str(failed_start),
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

        def run_http_script(code, timeout_seconds):
            return SandBox(
                pool,
                code,
                timeout_seconds=timeout_seconds,
            ).sandbox_instance()

        try:
            results = run_checks(run_script)
            results.extend(run_http_checks(run_http_script))
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
