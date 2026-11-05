import pytest

from exercises.case_runner import CaseOutcome, HarnessError, RunReport
from exercises.checks import StarterError
from exercises.starter import make_starter
from exercises.verify import make_verifier
from models.data_models import EnvironmentSpec
from models.lesson_generation_models import CaseDraft, Exercise, ExerciseDraft

REFERENCE = "def is_even(n):\n    return n % 2 == 0\n"
STARTER = make_starter(REFERENCE, "is_even")
ENV = EnvironmentSpec(packages={"pydantic": "2.9.0"})


def rep(*values, fatal=None):
    return RunReport(fatal=fatal, cases=[CaseOutcome(ok=True, value=v) for v in values])


def crashed(error):
    return CaseOutcome(ok=False, error=error)


class ScriptedRunner:
    "Answers reference runs from a queue, and starter runs with a fixed report. Records every call."
    def __init__(self, *reference_reports, starter=None):
        self.reference_reports = list(reference_reports)
        self.starter = starter if starter is not None else rep(None, None, None)
        self.calls: list[str] = []

    def __call__(self, source, function_name, inputs):
        self.calls.append("reference" if source == REFERENCE else "starter" if source == STARTER else "other")
        return self.reference_reports.pop(0) if source == REFERENCE else self.starter


def make_draft(**over) -> ExerciseDraft:
    base = dict(
        title="Even or odd", description="Say whether a number is even.",
        instructions=["Write is_even(n)", "Return True for even numbers"], difficulty="easy",
        function_name="is_even", reference_solution=REFERENCE,
        tests=[CaseDraft(label="typical even", inputs=[2]), CaseDraft(label="odd", inputs=[3]),
               CaseDraft(label="zero", inputs=[0])],
        hints=["Use the % operator", "n % 2 is 0 for even numbers"], explanation="Even numbers divide by 2.")
    return ExerciseDraft(**{**base, **over})


def verifier(runner, **kw):
    return make_verifier(None, ENV, runner=runner, **kw)


GOOD = lambda: ScriptedRunner(rep(True, False, True), rep(True, False, True))


def test_good_draft_becomes_a_finished_exercise():
    ex = verifier(GOOD())(make_draft())
    assert isinstance(ex, Exercise)
    assert ex.function_name == "is_even" and ex.solution == REFERENCE
    assert ex.starter_code == STARTER and "return" not in ex.starter_code
    assert [(c.label, c.inputs, c.expected) for c in ex.cases] == [
        ("typical even", [2], True), ("odd", [3], False), ("zero", [0], True)]


def test_everything_the_learner_needs_is_carried_over_from_the_draft():
    ex = verifier(GOOD())(make_draft())
    assert ex.title == "Even or odd" and ex.difficulty == "easy"
    assert ex.hints == ["Use the % operator", "n % 2 is 0 for even numbers"]
    assert ex.explanation == "Even numbers divide by 2."


def test_each_case_gets_the_reference_output_for_ITS_OWN_inputs():
    "Asymmetric on purpose: [True, False, False] reversed would be a different list."
    draft = make_draft(tests=[CaseDraft(label="typical even", inputs=[2]), CaseDraft(label="odd", inputs=[3]),
                              CaseDraft(label="large odd", inputs=[7])])
    ex = verifier(ScriptedRunner(rep(True, False, False), rep(True, False, False)))(draft)
    assert [(c.label, c.inputs, c.expected) for c in ex.cases] == [
        ("typical even", [2], True), ("odd", [3], False), ("large odd", [7], False)]


def test_the_result_survives_a_json_round_trip():
    ex = verifier(GOOD())(make_draft())
    assert Exercise.model_validate_json(ex.model_dump_json()) == ex


# how many sandbox runs, and in what order
def test_a_good_draft_costs_two_reference_runs_and_one_starter_run():
    runner = GOOD()
    verifier(runner)(make_draft())
    assert runner.calls == ["reference", "reference", "starter"]


def test_a_crash_on_the_first_run_skips_the_second_run():
    runner = ScriptedRunner(RunReport(None, [CaseOutcome(True, True), crashed("ZeroDivisionError"), CaseOutcome(True, True)]))
    with pytest.raises(ValueError, match="crashed"):
        verifier(runner)(make_draft())
    assert runner.calls == ["reference"]


def test_static_problems_never_reach_the_sandbox():
    for bad in (make_draft(function_name="is_odd"),
                make_draft(reference_solution="async def is_even(n):\n    return n % 2 == 0\n")):
        runner = GOOD()
        with pytest.raises(ValueError):
            verifier(runner)(bad)
        assert runner.calls == []


def test_the_starter_is_not_run_when_the_reference_is_flaky():
    runner = ScriptedRunner(rep(True, False, True), rep(False, False, True))
    with pytest.raises(ValueError, match="different results"):
        verifier(runner)(make_draft())
    assert runner.calls == ["reference", "reference"]


# problems the model hears about
def test_unloadable_reference():
    with pytest.raises(ValueError, match="could not be loaded: SyntaxError"):
        verifier(ScriptedRunner(rep(fatal="SyntaxError: invalid syntax")))(make_draft())


def test_all_outputs_identical():
    with pytest.raises(ValueError, match="same result"):
        verifier(ScriptedRunner(rep(True, True, True), rep(True, True, True)))(make_draft())


def test_duplicate_test_inputs():
    draft = make_draft(tests=[CaseDraft(label="case a", inputs=[2]), CaseDraft(label="case b", inputs=[3]),
                              CaseDraft(label="case c", inputs=[2])])
    with pytest.raises(ValueError, match="identical inputs"):
        verifier(ScriptedRunner(rep(True, False, True), rep(True, False, True)))(draft)


def test_starter_that_already_passes_everything():
    runner = ScriptedRunner(rep(None, True, None), rep(None, True, None), starter=rep(None, True, None))
    with pytest.raises(ValueError, match="already passes every test case"):
        verifier(runner)(make_draft())


def test_a_missing_module_message_lists_the_courses_installed_packages():
    runner = ScriptedRunner(rep(fatal="ModuleNotFoundError: No module named 'numpy'"))
    with pytest.raises(ValueError, match="pydantic"):
        verifier(runner)(make_draft())


# problems that are NOT the model's fault must not look like it 
def test_a_starter_that_cannot_load_is_our_bug_and_not_a_value_error():
    runner = ScriptedRunner(rep(True, False, True), rep(True, False, True), starter=rep(fatal="NameError: Item"))
    with pytest.raises(StarterError):
        verifier(runner)(make_draft())


def test_sandbox_infrastructure_errors_pass_straight_through():
    def broken(source, function_name, inputs):
        raise HarnessError("Sandbox run failed: docker down")
    with pytest.raises(HarnessError):
        verifier(broken)(make_draft())


#  visibility
def test_by_default_the_first_two_cases_are_visible_and_the_rest_hidden():
    draft = make_draft(tests=[CaseDraft(label=f"case {i}", inputs=[i]) for i in range(5)])
    ex = verifier(ScriptedRunner(rep(True, False, True, False, True), rep(True, False, True, False, True),
                                 starter=rep(*[None] * 5)))(draft)
    assert [c.visible for c in ex.cases] == [True, True, False, False, False]


def test_a_minimum_size_exercise_still_has_a_hidden_case():
    assert [c.visible for c in verifier(GOOD())(make_draft()).cases] == [True, True, False]


def test_one_visible_case_is_allowed():
    ex = verifier(GOOD(), visible_cases=1)(make_draft())
    assert [c.visible for c in ex.cases] == [True, False, False]


@pytest.mark.parametrize("n", [0, 3, -1, 10])
def test_visible_cases_outside_1_or_2_is_rejected_up_front(n):
    with pytest.raises(ValueError, match="hidden"):
        make_verifier(None, ENV, visible_cases=n, runner=GOOD())


def test_a_print_only_exercise_is_told_to_return_a_value():
    runner = ScriptedRunner(rep(None, None, None), rep(None, None, None))
    with pytest.raises(ValueError, match="RETURN a computed value"):
        verifier(runner)(make_draft())