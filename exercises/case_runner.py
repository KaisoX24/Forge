from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from models.data_models import ExecutionResult,ExecutionError
from exercises.drivers.function_driver import _DRIVER
_MARKER = "__FORGE_RESULT__"


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
    """The sandbox run itself failed (timeout, daemon down, crash outside the driver).
    error_type says whose fault it was; learner_fault is the summary."""

    def __init__(self, message: str, error_type: ExecutionError | None = None):
        super().__init__(message)
        self.error_type = error_type

    @property
    def learner_fault(self) -> bool:
        "exit() or a crash before reporting (None), a timeout, or a crash in their code."
        return self.error_type in (None, ExecutionError.TIMEOUT, ExecutionError.RUNTIME_ERROR)


def build_script(
    files: dict[str, str],
    entry_file: str,
    function_name: str,
    inputs: list[list],
    case_timeout: int = 2,
) -> str:
    payload = json.dumps({
        "files": files,
        "entry_file": entry_file,
        "function": function_name,
        "inputs": inputs,
        "case_timeout": case_timeout,
    })

    return (
        _DRIVER
        .replace("__PAYLOAD__", repr(payload))
        .replace("__MARKER__", _MARKER)
    )


def parse_report(stdout: str | bytes) -> RunReport:
    text = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout

    for line in reversed(text.splitlines()):
        if line.startswith(_MARKER):
            data = json.loads(line[len(_MARKER):])
            cases = [
                CaseOutcome(c["ok"], c.get("value"), c.get("error"))
                for c in data["cases"]
            ]
            return RunReport(fatal=data["fatal"], cases=cases)

    raise HarnessError(
        "The driver produced no result line "
        "(the code may have called exit() or crashed)."
    )


def run_cases(
    run_script: Callable[[str], ExecutionResult],
    files: dict[str, str],
    entry_file: str,
    function_name: str,
    inputs: list[list],
    case_timeout: int = 2,
) -> RunReport:
    """Run all cases against a function in a complete project."""
    result = run_script(
        build_script(files, entry_file, function_name, inputs, case_timeout)
    )

    if not result.success:
        raise HarnessError(
            f"Sandbox run failed: {result.error_type} {result.stderr}",
            result.error_type,
        )

    return parse_report(result.stdout)

def json_equal(actual: Any, expected: Any) -> bool:
    "bool is not a number; 1 and 1.0 are equal; lists and dicts compare recursively."
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            json_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def grade(report: RunReport, expected: list[Any]) -> list[dict]:
    """One entry per case: passed, plus what is needed to build a hint."""
    if report.fatal:
        return [{
            "passed": False,
            "reason": "load_error",
            "detail": report.fatal,
        }]

    graded = []

    for outcome, want in zip(report.cases, expected):
        if not outcome.ok:
            graded.append({
                "passed": False,
                "reason": "error",
                "detail": outcome.error,
            })
        elif json_equal(outcome.value,want):
            graded.append({"passed": True})
        else:
            graded.append({
                "passed": False,
                "reason": "wrong_output",
                "got": outcome.value,
                "expected": want,
            })

    return graded
