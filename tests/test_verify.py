import pytest
from pydantic import ValidationError
from models.lesson_generation_models import (
    Exercise, ExerciseDraft, FunctionCase, FunctionCaseDraft, FunctionEvaluationConfig,
    FunctionExecutionConfig, HttpCase, HttpCaseDraft, HttpEvaluationConfig, HttpExecutionConfig,
)

FUNCTION_FILES = {"main.py": "def add(a, b):\n    return a + b\n"}
REFERENCE_FILES = {"main.py": "def add(a, b):\n    return a + b\n"}
FUNCTION_CASES = [
    FunctionCaseDraft(label="positive values", inputs=[2, 3]),
    FunctionCaseDraft(label="negative values", inputs=[-2, -3]),
    FunctionCaseDraft(label="zero", inputs=[0, 0]),
]

def make_draft(**overrides):
    base = dict(title="Add numbers", description="Return the sum of two numbers.",
        instructions=["Implement add(a, b).", "Return the sum."], difficulty="easy",
        files=FUNCTION_FILES, reference_files=REFERENCE_FILES,
        execution=FunctionExecutionConfig(function_name="add"),
        evaluation=FunctionEvaluationConfig(cases=FUNCTION_CASES),
        hints=["Use the + operator.", "Return the calculated value."],
        explanation="The + operator adds two numbers.")
    return ExerciseDraft(**{**base, **overrides})

def test_function_draft_accepts_new_project_contract():
    draft=make_draft()
    assert draft.execution.target == draft.evaluation.target == "function"
    assert draft.execution.entry_file == "main.py"
    assert len(draft.evaluation.cases) == 3

def test_execution_and_evaluation_targets_must_match():
    with pytest.raises(ValidationError, match="targets must match"):
        make_draft(execution=HttpExecutionConfig(command=["python", "main.py"]))

@pytest.mark.parametrize("files", [{}, {"../outside.py":"x"}, {"/absolute.py":"x"}, {"folder\\\\file.py":"x"}, {"folder/":"x"}])
def test_project_file_paths_must_be_safe_and_nonempty(files):
    with pytest.raises(ValidationError): make_draft(files=files)

def test_function_entry_file_must_exist_in_starter_and_reference():
    with pytest.raises(ValidationError, match="starter project"):
        make_draft(files={"other.py":"pass"})
    with pytest.raises(ValidationError, match="reference project"):
        make_draft(reference_files={"other.py":"pass"})

def http_cases():
    return [
        HttpCaseDraft(label="health check", method="GET", path="/health", expected_status=200),
        HttpCaseDraft(label="create item", method="POST", path="/items", json_body={"name":"pen"}, expected_status=201),
        HttpCaseDraft(label="missing item", method="GET", path="/items/999", expected_status=404),
    ]

def test_http_draft_uses_typed_execution_and_evaluation_configs():
    draft=make_draft(files={"main.py":"from app import app"}, reference_files={"main.py":"from app import app"},
        execution=HttpExecutionConfig(command=["python","main.py"]), evaluation=HttpEvaluationConfig(cases=http_cases()))
    assert draft.execution.target == draft.evaluation.target == "http"
    assert draft.execution.command == ["python","main.py"]
    assert [case.method for case in draft.evaluation.cases] == ["GET","POST","GET"]

def test_http_execution_rejects_empty_command_at_draft_validation():
    with pytest.raises(ValidationError, match="launch command"):
        make_draft(files={"main.py":"from app import app"}, reference_files={"main.py":"from app import app"},
            execution=HttpExecutionConfig(command=[]), evaluation=HttpEvaluationConfig(cases=http_cases()))

def test_http_case_rejects_invalid_method_and_status():
    with pytest.raises(ValidationError): HttpCaseDraft(label="bad method", method="OPTIONS", path="/", expected_status=200)
    with pytest.raises(ValidationError): HttpCaseDraft(label="bad status", method="GET", path="/", expected_status=99)

def test_evaluation_configs_require_three_to_six_cases():
    with pytest.raises(ValidationError): FunctionEvaluationConfig(cases=FUNCTION_CASES[:2])
    with pytest.raises(ValidationError): FunctionEvaluationConfig(cases=FUNCTION_CASES*3)

def test_exercise_from_draft_excludes_private_reference_data():
    draft=make_draft()
    cases=[FunctionCase(label=c.label, inputs=c.inputs, expected=v, visible=i<2)
           for i,(c,v) in enumerate(zip(draft.evaluation.cases,[5,-5,0]))]
    exercise=Exercise.from_draft(draft,cases=cases)
    assert exercise.files == draft.files and exercise.execution == draft.execution
    assert exercise.cases == cases and exercise.hints == draft.hints
    assert exercise.explanation == draft.explanation
    assert not hasattr(exercise,"reference_files") and not hasattr(exercise,"evaluation")

def test_finished_function_exercise_json_round_trip():
    draft=make_draft()
    exercise=Exercise.from_draft(draft,cases=[FunctionCase(label=c.label,inputs=c.inputs,expected=v)
        for c,v in zip(draft.evaluation.cases,[5,-5,0])])
    assert Exercise.model_validate_json(exercise.model_dump_json()) == exercise

def test_http_cases_can_be_used_in_finished_exercise_and_round_trip():
    draft=make_draft(files={"main.py":"from app import app"}, reference_files={"main.py":"from app import app"},
        execution=HttpExecutionConfig(command=["python","main.py"]), evaluation=HttpEvaluationConfig(cases=http_cases()))
    cases=[HttpCase(label=c.label,method=c.method,path=c.path,expected_status=c.expected_status) for c in draft.evaluation.cases]
    exercise=Exercise.from_draft(draft,cases=cases)
    assert exercise.execution.target == "http" and exercise.cases == cases
    assert Exercise.model_validate_json(exercise.model_dump_json()) == exercise

def test_exercise_from_draft_keeps_reference_files_but_drops_evaluation():
    draft=make_draft()
    cases=[FunctionCase(label=c.label, inputs=c.inputs, expected=v, visible=i<2)
           for i,(c,v) in enumerate(zip(draft.evaluation.cases,[5,-5,0]))]
    exercise=Exercise.from_draft(draft,cases=cases)
    assert exercise.files == draft.files and exercise.execution == draft.execution
    assert exercise.cases == cases and exercise.hints == draft.hints
    assert exercise.explanation == draft.explanation
    assert exercise.reference_files == draft.reference_files
    assert not hasattr(exercise,"evaluation")

