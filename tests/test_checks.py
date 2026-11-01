import pytest

from exercises.case_runner import CaseOutcome, HarnessError, RunReport
from exercises.checks import check_distinct_inputs, check_variety, reference_outputs, verify_reference_run


def report(*values, fatal=None):
    return RunReport(fatal=fatal, cases=[CaseOutcome(ok=True, value=v) for v in values])


def crashed(error):
    return CaseOutcome(ok=False, error=error)


LABELS = ["typical even", "odd", "zero"]
INPUTS = [[2], [3], [0]]


def test_good_run_returns_the_outputs_to_store_as_expected():
    assert verify_reference_run(report(True, False, True), LABELS, INPUTS) == [True, False, True]


# reference failures 
def test_unloadable_reference_is_reported_with_the_reason():
    with pytest.raises(ValueError, match="could not be loaded: SyntaxError: invalid syntax"):
        reference_outputs(report(fatal="SyntaxError: invalid syntax"), LABELS, INPUTS)


def test_every_crashed_case_is_listed_so_one_retry_can_fix_them_all():
    rep = RunReport(fatal=None, cases=[CaseOutcome(True, True), crashed("ZeroDivisionError: x"), crashed("KeyError: 'a'")])
    with pytest.raises(ValueError) as exc:
        reference_outputs(rep, LABELS, INPUTS)
    msg = str(exc.value)
    assert "'odd'" in msg and "ZeroDivisionError" in msg and "'zero'" in msg and "KeyError" in msg
    assert "'typical even'" not in msg


def test_driver_result_count_mismatch_is_an_infrastructure_error_not_the_models_fault():
    with pytest.raises(HarnessError):
        reference_outputs(report(True, False), LABELS, INPUTS)
    assert not issubclass(HarnessError, ValueError)


# ---------- variety ----------
def test_identical_outputs_are_rejected():
    with pytest.raises(ValueError, match="same result"):
        check_variety(LABELS, INPUTS, [True, True, True])


def test_the_message_tells_the_model_what_it_got_and_what_to_do():
    with pytest.raises(ValueError) as exc:
        check_variety(LABELS, INPUTS, [True, True, True])
    msg = str(exc.value)
    assert "(true)" in msg 
    assert "'typical even'" in msg and "inputs [2] -> true" in msg   
    assert "different" in msg and "opposite" in msg   


def test_a_false_output_is_perfectly_valid_variety_is_what_matters():
    check_variety(LABELS, INPUTS, [True, False, True])           
    with pytest.raises(ValueError):
        check_variety(LABELS, INPUTS, [False, False, False]) 


def test_mostly_one_value_with_a_single_different_one_is_accepted():
    check_variety(["a"] * 5, [[i] for i in range(5)], [True, True, True, True, False])


def test_unhashable_outputs_are_compared_correctly():
    check_variety(LABELS, INPUTS, [[1], [2], [1]])
    with pytest.raises(ValueError):
        check_variety(LABELS, INPUTS, [{"a": 1}, {"a": 1}, {"a": 1}])


def test_one_and_true_count_as_different_results():
    check_variety(["a", "b"], [[1], [2]], [1, True])


def test_a_single_case_cannot_be_compared_so_it_is_not_rejected():
    check_variety(["only"], [[1]], [True])


def test_long_outputs_and_many_cases_keep_the_feedback_short():
    n = 20
    with pytest.raises(ValueError) as exc:
        check_variety([f"c{i}" for i in range(n)], [["x" * 500]] * n, ["y" * 500] * n)
    msg = str(exc.value)
    assert msg.count("\n- ") == 6            
    assert len(msg) < 1200 and "..." in msg


# duplicate inputs 
def test_duplicate_inputs_name_both_cases():
    with pytest.raises(ValueError, match="'a' and 'c' use identical inputs"):
        check_distinct_inputs(["a", "b", "c"], [[0], [1], [0]])


def test_same_values_in_different_structure_are_not_duplicates():
    check_distinct_inputs(["a", "b"], [[1], ["1"]])


def test_example_C_from_the_design_discussion_is_caught_by_the_combined_check():
    with pytest.raises(ValueError, match="identical inputs"):
        verify_reference_run(report(True, True, True), LABELS, [[0], [0], [0]])


def test_checks_run_in_order_crash_before_duplicates_before_variety():
    rep = RunReport(fatal=None, cases=[crashed("boom"), CaseOutcome(True, 1), CaseOutcome(True, 1)])
    with pytest.raises(ValueError, match="crashed"):
        verify_reference_run(rep, LABELS, [[0], [0], [0]])