import pytest

from api.services.grader import Grader
from exercises.case_runner import CaseOutcome, HarnessError, RunReport
from models.lesson_generation_models import Exercise, FunctionCase, FunctionExecutionConfig


def make_exercise():
    cases = [FunctionCase(label=f"c{i}", inputs=[i, 1], expected=i + 1, visible=i < 2)
             for i in range(4)]
    return Exercise(title="Add", description="Add two numbers.",
                    instructions=["Take two numbers.", "Return the sum."], difficulty="easy",
                    files={"main.py": "def add(a, b):\n    pass\n"},
                    execution=FunctionExecutionConfig(entry_file="main.py", function_name="add"),
                    cases=cases, hints=["h1", "h2"], explanation="Plain addition.")


def fake_function_runner(values=None, fatal=None, boom=False):
    def run(files, entry_file, function_name, inputs):
        if boom:
            raise HarnessError("docker down")
        if fatal:
            return RunReport(fatal=fatal, cases=[])
        vals = values if values is not None else [a + b for a, b in inputs]
        return RunReport(fatal=None, cases=[CaseOutcome(ok=True, value=v) for v in vals])
    return run


def grader(**kw):
    return Grader(fake_function_runner(**kw), run_http=None)


def test_submit_runs_all_cases_and_hides_hidden_details():
    ex = make_exercise()
    result = grader().grade(ex, ex.files, visible_only=False)
    assert (result.status, result.passed_count, result.total) == ("passed", 4, 4)
    hidden = [c for c in result.cases if not c.visible]
    assert len(hidden) == 2 and all(c.got is None and c.expected is None for c in hidden)


def test_run_tests_only_runs_visible_cases():
    ex = make_exercise()
    result = grader().grade(ex, ex.files, visible_only=True)
    assert result.total == 2 and all(c.visible for c in result.cases)


def test_wrong_answers_are_failed_not_error():
    ex = make_exercise()
    result = grader(values=[0, 0, 0, 0]).grade(ex, ex.files, visible_only=False)
    assert result.status == "failed" and result.passed_count == 0


def test_load_error_becomes_error_result_without_paths():
    ex = make_exercise()
    result = grader(fatal='File "/tmp/forge_ab12/main.py", line 3\nSyntaxError: oops') \
        .grade(ex, ex.files, visible_only=False)
    assert result.status == "error" and result.cases == [] and result.total == 4
    assert "/tmp" not in result.message and "SyntaxError: oops" in result.message


def test_infrastructure_failure_propagates_and_bad_paths_return_error():
    ex = make_exercise()
    with pytest.raises(HarnessError):
        grader(boom=True).grade(ex, ex.files, visible_only=False)
    assert grader().grade(ex, {"../evil.py": "x"}, visible_only=False).status == "error"