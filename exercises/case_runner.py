"""Runs a function against many inputs inside ONE sandbox execution."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from models.data_models import ExecutionResult

_MARKER = "__FORGE_RESULT__"

# This text is the script that runs INSIDE the sandbox.
_DRIVER = r'''
import json, signal, sys

payload = json.loads(__PAYLOAD__)
report = {"fatal": None, "cases": []}


class _CaseTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _CaseTimeout()


try:
    namespace = {"__name__": "learner_code"}
    exec(compile(payload["source"], "<code>", "exec"), namespace)
    func = namespace[payload["function"]]
except BaseException as exc:
    report["fatal"] = f"{type(exc).__name__}: {exc}"
    func = None

if func is not None:
    signal.signal(signal.SIGALRM, _on_alarm)
    for args in payload["inputs"]:
        try:
            signal.alarm(payload["case_timeout"])
            value = func(*args)
            signal.alarm(0)
            json.dumps(value)
            report["cases"].append({"ok": True, "value": value})
        except _CaseTimeout:
            report["cases"].append({"ok": False, "error": "TimeoutError: case took too long"})
        except BaseException as exc:
            signal.alarm(0)
            report["cases"].append({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

sys.stdout.write("\n" + "__MARKER__" + json.dumps(report) + "\n")
'''


@dataclass(frozen=True)
class CaseOutcome:
    ok: bool
    value: Any = None
    error: str | None = None


@dataclass(frozen=True)
class RunReport:
    fatal: str | None 
    cases: list[CaseOutcome]


class HarnessError(RuntimeError):
    """The sandbox run itself failed (timeout, daemon down, crash outside the driver)."""


def build_script(source: str, function_name: str, inputs: list[list], case_timeout: int = 2) -> str:
    payload = json.dumps(
        {"source": source, "function": function_name, "inputs": inputs, "case_timeout": case_timeout}
    )
    return _DRIVER.replace("__PAYLOAD__", repr(payload)).replace("__MARKER__", _MARKER)


def parse_report(stdout: str | bytes) -> RunReport:
    text = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout
    for line in reversed(text.splitlines()):
        if line.startswith(_MARKER):
            data = json.loads(line[len(_MARKER):])
            cases = [CaseOutcome(c["ok"], c.get("value"), c.get("error")) for c in data["cases"]]
            return RunReport(fatal=data["fatal"], cases=cases)
    raise HarnessError("The driver produced no result line (the code may have called exit() or crashed).")


def run_cases(
    run_script: Callable[[str], ExecutionResult],
    source: str,
    function_name: str,
    inputs: list[list],
    case_timeout: int = 2,
) -> RunReport:
    """run_script is e.g. `lambda code: SandBox(pool, code).sandbox_instance()`."""
    result = run_script(build_script(source, function_name, inputs, case_timeout))
    if not result.success:
        raise HarnessError(f"Sandbox run failed: {result.error_type} {result.stderr}")
    return parse_report(result.stdout)


def grade(report: RunReport, expected: list[Any]) -> list[dict]:
    """One entry per case: passed, plus what is needed to build a hint."""
    if report.fatal:
        return [{"passed": False, "reason": "load_error", "detail": report.fatal}]
    graded = []
    for outcome, want in zip(report.cases, expected):
        if not outcome.ok:
            graded.append({"passed": False, "reason": "error", "detail": outcome.error})
        elif outcome.value == want:
            graded.append({"passed": True})
        else:
            graded.append({"passed": False, "reason": "wrong_output", "got": outcome.value, "expected": want})
    return graded