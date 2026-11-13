import json
import re
from typing import Any

from api.schemas.results import CaseResult
from exercises.case_runner import CaseOutcome,json_equal
from models.data_models import HttpCaseOutcome
from models.lesson_generation_models import FunctionCase,HttpCase

_SANDBOX_PATH=re.compile(r"/tmp/[\w.\-]+/")

def _show(value:Any) ->str:
    "one-line JSON for a value"

    try:
        return json.dumps(value,ensure_ascii=False,default=repr)
    except (TypeError,ValueError):
        return repr(value)

def clean_text(text:str) -> str:
    "Cleans the sandbox temp path so the learner can see proper file name"
    return _SANDBOX_PATH.sub("",text)

def render_function_case(case:FunctionCase,outcome:CaseOutcome,
                         function_name:str) -> CaseResult:
    "Renders a CaseResult for Function cases for UI"
    args=", ".join(_show(a) for a in case.inputs)

    if outcome.ok:
        got=_show(outcome.value)
        passed=json_equal(outcome.value,case.expected)

    else:
        lines=(outcome.error or "unknown error").strip().splitlines()
        got=f"error: {clean_text(lines[-1] if lines else "unknown error")}"
        passed=False

    return CaseResult(
        label=case.label,
        passed=passed,
        visible=case.visible,
        inputs=f"{function_name}({args})",
        expected=_show(case.expected),
        got=got
    )

def render_http_case(case:HttpCase,outcome:HttpCaseOutcome) -> CaseResult:
    request=f"{case.method} {case.path}"
    if case.json_body is not None:
        request+=f" {_show(case.json_body)}"

    expected=str(case.expected_status)

    if case.expected_json is not None:
        expected+=f" {_show(case.expected_json)}"
    elif case.expected_text:
        expected+=f" {_show(case.expected_text)}"

    if outcome.status_code is None:
        got=f"no response: {clean_text(outcome.error or "request failed")}"
    else:
        body=outcome.response_json if outcome.response_is_json else outcome.response_text
        got=str(outcome.status_code)+(f" {_show(body)}" if body not in (None, "") else "")

    return CaseResult(
        label=case.label,
        passed=outcome.passed,
        visible=case.visible,
        inputs=request,
        expected=expected,
        got=got
    )