from __future__ import annotations

import json
from typing import Callable

from models.lesson_generation_models import (
    HttpCaseDraft,
    HttpExecutionConfig,
)
from models.data_models import (
    ExecutionError,
    ExecutionResult,
    HttpCaseOutcome,
    HttpRunReport
)
from exercises.drivers.http_driver import _HTTP_DRIVER


_MARKER = "__FORGE_HTTP_REPORT__"

HTTP_SUITE_TIMEOUT_SECONDS = 12
HTTP_SANDBOX_TIMEOUT_SECONDS = 20

ScriptRunner = Callable[[str, int], ExecutionResult]

def build_http_script(
    files: dict[str, str],
    execution: HttpExecutionConfig,
    cases: list[HttpCaseDraft],
    suite_timeout_seconds: int,
) -> str:
    """Build the Python driver executed inside the sandbox."""

    if suite_timeout_seconds <= 0:
        raise ValueError("Suite timeout must be greater than zero.")

    serialized_cases = []

    for case in cases:
        case_data = case.model_dump()

        # Preserve the distinction between omitted fields and explicit null.
        case_data["json_body_present"] = (
            "json_body" in case.model_fields_set
        )
        case_data["expected_json_present"] = (
            "expected_json" in case.model_fields_set
        )

        serialized_cases.append(case_data)

    payload = json.dumps({
        "files": files,
        "execution": execution.model_dump(),
        "cases": serialized_cases,
        "suite_timeout": suite_timeout_seconds,
    })

    return (
        _HTTP_DRIVER
        .replace("__PAYLOAD__", repr(payload))
        .replace("__MARKER__", _MARKER)
    )

def _parse_http_report(stdout: str) -> HttpRunReport:
    """Extract and validate the HTTP report emitted by the driver."""

    marker_index = stdout.rfind(_MARKER)

    if marker_index == -1:
        raise ValueError("HTTP driver did not produce a report.")

    report_text = stdout[
        marker_index + len(_MARKER):
    ].strip()

    if not report_text:
        raise ValueError("HTTP driver produced an empty report.")

    report_data = json.loads(report_text)

    if not isinstance(report_data, dict):
        raise ValueError("HTTP driver report must be a JSON object.")

    cases_data = report_data.get("cases")

    if not isinstance(cases_data, list):
        raise ValueError("HTTP driver report contains invalid cases.")

    cases = [
        HttpCaseOutcome(**case)
        for case in cases_data
    ]

    return HttpRunReport(
        fatal=report_data.get("fatal"),
        cases=cases,
    )


def run_http_cases(
    files: dict[str, str],
    execution: HttpExecutionConfig,
    cases: list[HttpCaseDraft],
    *,
    run_script: ScriptRunner,
) -> HttpRunReport:
    """Execute an HTTP evaluation suite inside the sandbox."""

    script = build_http_script(
        files,
        execution,
        cases,
        suite_timeout_seconds=HTTP_SUITE_TIMEOUT_SECONDS,
    )

    result = run_script(
        script,
        HTTP_SANDBOX_TIMEOUT_SECONDS,
    )

    if not result.success:
        if result.error_type == ExecutionError.TIMEOUT:
            message = "HTTP sandbox execution timed out."
        else:
            message = (
                f"HTTP sandbox execution failed: "
                f"{result.error_type or 'unknown error'}"
            )

        if result.stderr:
            message += f"\n{result.stderr}"

        return HttpRunReport(
            fatal=message,
            cases=[],
        )

    try:
        return _parse_http_report(result.stdout)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return HttpRunReport(
            fatal=f"Could not parse HTTP execution report: {exc}",
            cases=[],
        )