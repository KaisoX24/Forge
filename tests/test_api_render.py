from api.services.render import render_function_case, render_http_case
from exercises.case_runner import CaseOutcome
from models.data_models import HttpCaseOutcome
from models.lesson_generation_models import FunctionCase, HttpCase


def _fcase(visible=True):
    return FunctionCase(label="ints", inputs=[1, 2], expected=3, visible=visible)


def test_function_pass_shows_call_expected_and_got():
    r = render_function_case(_fcase(), CaseOutcome(ok=True, value=3), "add")
    assert (r.passed, r.inputs, r.expected, r.got) == (True, "add(1, 2)", "3", "3")


def test_function_wrong_value_fails():
    r = render_function_case(_fcase(), CaseOutcome(ok=True, value=4), "add")
    assert not r.passed and r.got == "4"


def test_function_crash_shows_last_line_without_sandbox_path():
    err = 'Traceback...\n  File "/tmp/forge_x1/main.py", line 2\nTypeError: bad operand'
    r = render_function_case(_fcase(), CaseOutcome(ok=False, error=err), "add")
    assert not r.passed and r.got == "error: TypeError: bad operand"
    err2 = "NameError in /tmp/forge_x1/main.py"
    assert "/tmp" not in render_function_case(
        _fcase(), CaseOutcome(ok=False, error=err2), "add").got


def test_hidden_case_reveals_nothing():
    r = render_function_case(_fcase(visible=False), CaseOutcome(ok=True, value=3), "add")
    assert r.passed and r.inputs is None and r.expected is None and r.got is None


def test_http_pass_and_fail_rows():
    case = HttpCase(label="get item", method="GET", path="/items/5",
                    expected_status=200, expected_json={"item_id": 5})
    ok = render_http_case(case, HttpCaseOutcome(
        label="get item", passed=True, status_code=200,
        response_json={"item_id": 5}, response_is_json=True))
    assert ok.passed and ok.inputs == "GET /items/5"
    assert ok.expected == '200 {"item_id": 5}' and ok.got == '200 {"item_id": 5}'
    bad = render_http_case(case, HttpCaseOutcome(
        label="get item", passed=False, status_code=422,
        response_text="oops", response_is_json=False))
    assert not bad.passed and bad.got == '422 "oops"'


def test_http_no_response():
    case = HttpCase(label="x", method="GET", path="/", expected_status=200)
    r = render_http_case(case, HttpCaseOutcome(label="x", passed=False,
                                               error="connection refused"))
    assert r.got == "no response: connection refused"

def test_function_number_does_not_pass_for_a_bool():
    case = FunctionCase(label="even", inputs=[2], expected=True)
    assert not render_function_case(case, CaseOutcome(ok=True, value=1), "is_even").passed
    assert render_function_case(case, CaseOutcome(ok=True, value=True), "is_even").passed