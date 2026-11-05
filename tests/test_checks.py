import pytest

from exercises.case_runner import CaseOutcome, HarnessError, RunReport
from exercises.checks import check_distinct_inputs, check_variety, reference_outputs, verify_reference_run,check_deterministic


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


def test_one_value_dominating_four_or_more_cases_is_rejected():
    with pytest.raises(ValueError, match="4 of 5 test cases give the same result"):
        check_variety(["a"] * 5, [[i] for i in range(5)], [True, True, True, True, False])
    with pytest.raises(ValueError, match="3 of 4"):
        check_variety(list("abcd"), [[i] for i in range(4)], [False, False, False, True])


def test_a_balanced_set_is_accepted_at_the_limit():
    check_variety(list("abcde"), [[i] for i in range(5)], [True, True, True, False, False])   # 60% is allowed
    check_variety(list("abcd"), [[i] for i in range(4)], [True, True, False, False])


def test_three_cases_are_not_checked_for_dominance():
    check_variety(["a", "b", "c"], [[1], [2], [3]], [True, True, False])


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

# determinism


def test_two_identical_runs_pass():
    check_deterministic(LABELS, INPUTS, [True, False, True], report(True, False, True))


def test_different_results_between_runs_are_rejected_with_the_common_causes():
    with pytest.raises(ValueError, match="different results when run twice") as exc:
        check_deterministic(LABELS, INPUTS, [True, False, True], report(True, True, True))
    msg = str(exc.value)
    assert "random" in msg and "sorted(" in msg and "time" in msg      # tells the model what to look for


def test_only_the_cases_that_differ_are_listed_with_both_values():
    with pytest.raises(ValueError) as exc:
        check_deterministic(LABELS, INPUTS, [1, 2, 3], report(1, 99, 3))
    msg = str(exc.value)
    assert "'odd'" in msg and "first run 2, second run 99" in msg
    assert "'typical even'" not in msg and "'zero'" not in msg


def test_a_second_run_that_crashes_counts_as_non_deterministic():
    rep = RunReport(fatal=None, cases=[CaseOutcome(True, 1), crashed("KeyError: 'x'"), CaseOutcome(True, 3)])
    with pytest.raises(ValueError, match="second time .* not deterministic") as exc:
        check_deterministic(LABELS, INPUTS, [1, 2, 3], rep)
    assert "KeyError" in str(exc.value)


def test_a_second_run_that_cannot_load_counts_as_non_deterministic():
    with pytest.raises(ValueError, match="not deterministic"):
        check_deterministic(LABELS, INPUTS, [1, 2, 3], report(fatal="ImportError: flaky"))


def test_list_order_matters_because_that_is_what_set_ordering_bugs_look_like():
    with pytest.raises(ValueError, match="different results"):
        check_deterministic(["a"], [[0]], [["x", "y"]], report(["y", "x"]))


def test_one_and_true_count_as_different_between_runs():
    with pytest.raises(ValueError):
        check_deterministic(["a"], [[0]], [1], report(True))


def test_many_differing_cases_keep_the_message_short():
    n = 20
    labels = [f"c{i}" for i in range(n)]
    with pytest.raises(ValueError) as exc:
        check_deterministic(labels, [[i] for i in range(n)], list(range(n)), report(*[i + 1000 for i in range(n)]))
    assert str(exc.value).count("\n- ") == 6


def test_verify_runs_the_determinism_check_when_given_a_second_run():
    with pytest.raises(ValueError, match="different results"):
        verify_reference_run(report(True, False, True), LABELS, INPUTS, second_report=report(True, True, True))


def test_verify_without_a_second_run_behaves_as_before():
    assert verify_reference_run(report(True, False, True), LABELS, INPUTS) == [True, False, True]


def test_determinism_is_checked_before_variety_so_the_model_hears_the_root_cause():
    with pytest.raises(ValueError, match="different results"):          # not "same result"
        verify_reference_run(report(1, 1, 1), LABELS, INPUTS, second_report=report(2, 2, 2))


# modules that are not installed 
PKGS = ["fastapi[standard]", "pydantic"]


def test_unloadable_reference_because_of_a_missing_module_lists_what_is_installed():
    with pytest.raises(ValueError) as exc:
        reference_outputs(report(fatal="ModuleNotFoundError: No module named 'numpy'"), LABELS, INPUTS, PKGS)
    msg = str(exc.value)
    assert "No module named 'numpy'" in msg and "fastapi[standard], pydantic" in msg and "standard library" in msg


def test_a_case_level_missing_module_also_gets_the_hint_once():
    rep = RunReport(fatal=None, cases=[crashed("ModuleNotFoundError: No module named 'numpy'"),
                                       crashed("ModuleNotFoundError: No module named 'numpy'"), CaseOutcome(True, 1)])
    with pytest.raises(ValueError) as exc:
        reference_outputs(rep, LABELS, INPUTS, PKGS)
    assert str(exc.value).count("standard library") == 1


def test_other_errors_get_no_installed_packages_hint():
    with pytest.raises(ValueError) as exc:
        reference_outputs(report(fatal="SyntaxError: invalid syntax"), LABELS, INPUTS, PKGS)
    assert "installed" not in str(exc.value)


def test_no_hint_when_the_caller_does_not_pass_the_package_list():
    with pytest.raises(ValueError) as exc:
        reference_outputs(report(fatal="ModuleNotFoundError: No module named 'numpy'"), LABELS, INPUTS)
    assert "installed" not in str(exc.value)


def test_an_environment_with_no_extra_packages_says_so():
    with pytest.raises(ValueError, match="packages are installed: none"):
        reference_outputs(report(fatal="ModuleNotFoundError: No module named 'x'"), LABELS, INPUTS, [])


def test_verify_passes_the_package_list_through():
    with pytest.raises(ValueError, match="fastapi"):
        verify_reference_run(report(fatal="ModuleNotFoundError: No module named 'x'"), LABELS, INPUTS,
                             available_packages=PKGS)

# exercises whose function only prints or mutates
def test_all_none_outputs_get_return_a_value_advice_not_change_the_inputs_advice():
    with pytest.raises(ValueError) as exc:
        check_variety(LABELS, INPUTS, [None, None, None])
    msg = str(exc.value)
    assert "returns None" in msg and "RETURN" in msg and "print" in msg
    assert "Change or add test inputs" not in msg


def test_a_constant_that_is_not_none_still_gets_the_change_the_inputs_advice():
    with pytest.raises(ValueError, match="Change or add test inputs"):
        check_variety(LABELS, INPUTS, [0, 0, 0])


def test_none_mixed_with_real_values_is_fine():
    check_variety(LABELS, INPUTS, [None, 1, None])