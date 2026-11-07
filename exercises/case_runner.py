from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from models.data_models import ExecutionResult
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
    """The sandbox run itself failed (timeout, daemon down, crash outside the driver)."""


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
            f"Sandbox run failed: {result.error_type} {result.stderr}"
        )

    return parse_report(result.stdout)


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
        elif outcome.value == want:
            graded.append({"passed": True})
        else:
            graded.append({
                "passed": False,
                "reason": "wrong_output",
                "got": outcome.value,
                "expected": want,
            })

    return graded
