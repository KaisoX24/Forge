import pytest

from exercises.case_runner import CaseOutcome, RunReport, grade, json_equal


@pytest.mark.parametrize("actual, expected, same", [
    (1, True, False), (0, False, False), (True, True, True),
    (1, 1.0, True), ("1", 1, False), (None, None, True),
    ([1, True], [1, 1], False), ({"a": [True]}, {"a": [True]}, True),
    ({"a": 1}, {"a": 1, "b": 2}, False), ([1, 2], [2, 1], False),
])
def test_json_equal(actual, expected, same):
    assert json_equal(actual, expected) is same


def test_grade_no_longer_accepts_a_number_for_a_bool():
    report = RunReport(fatal=None, cases=[CaseOutcome(ok=True, value=1),
                                          CaseOutcome(ok=True, value=True)])
    graded = grade(report, [True, True])
    assert [g["passed"] for g in graded] == [False, True]
    assert graded[0]["reason"] == "wrong_output"