import ast
import subprocess
import sys

import pytest
import signal
from exercises.case_runner import build_script, grade, parse_report
from exercises.checks import StarterError, check_starter_fails
from exercises.starter import _make_function_starter, make_starter

REF = "def add(a, b):\n    return a + b\n"
needs_sigalrm = pytest.mark.skipif(
    not hasattr(signal, "SIGALRM"), reason="driver uses SIGALRM (not available on Windows)")

def run_locally(source, function, inputs):
    "Runs the REAL driver script with a local interpreter (no Docker) and returns the parsed report."
    proc = subprocess.run([sys.executable, "-c", build_script(source, function, inputs)],
                          capture_output=True, text=True, timeout=30,)
    return parse_report(proc.stdout)


# what the starter contains 
def test_starter_keeps_the_signature_and_has_no_solution():
    starter = _make_function_starter(REF, "add")
    assert "def add(a, b):" in starter and "return" not in starter and "pass" in starter


def test_starter_is_always_valid_python_and_returns_none():
    starter = _make_function_starter(REF, "add")
    ast.parse(starter)
    ns: dict = {}
    exec(starter, ns)
    assert ns["add"](1, 2) is None


def test_starter_keeps_docstring_annotations_and_defaults():
    ref = 'def total(items: list[int], scale: int = 2) -> int:\n    """Add up the items."""\n    return sum(items) * scale\n'
    starter = _make_function_starter(ref, "total")
    assert '"""Add up the items."""' in starter
    assert "items: list[int]" in starter and "-> int" in starter and "=2" in starter.replace(" ", "")


def test_helpers_constants_and_comments_are_dropped():
    ref = "LIMIT = 3\n\ndef _h(x):\n    return x\n\ndef f(x):\n    # secret approach\n    return _h(x)\n"
    starter = _make_function_starter(ref, "f")
    assert "LIMIT" not in starter and "_h" not in starter and "secret" not in starter


def test_decorators_are_dropped_because_they_may_need_names_the_learner_does_not_have():
    starter = _make_function_starter("@cache\ndef f(x):\n    return x\n", "f")
    assert "@cache" not in starter
    exec(starter, {})                                     


def test_only_imports_the_signature_needs_are_kept():
    ref = "import re\nfrom typing import List, Optional\n\ndef f(x: List[int]):\n    return re.sub('a', 'b', 'a')\n"
    starter = _make_function_starter(ref, "f")
    assert "from typing import List" in starter and "Optional" not in starter and "import re" not in starter


def test_future_annotations_import_is_kept():
    starter = _make_function_starter("from __future__ import annotations\n\ndef f(x: Foo):\n    return x\n", "f")
    assert starter.startswith("from __future__ import annotations")


def test_aliased_imports_are_kept_under_their_alias():
    starter = _make_function_starter("import numpy as np\n\ndef f(x: np.ndarray):\n    return x\n", "f")
    assert "import numpy as np" in starter


#  problems the model must fix 
def test_missing_function_lists_what_is_defined():
    with pytest.raises(ValueError, match=r"does not define a function named 'adder'.*\['add'\]"):
        _make_function_starter(REF, "adder")


def test_async_functions_are_rejected_with_advice():
    with pytest.raises(ValueError, match="async def"):
        _make_function_starter("async def f():\n    return 1\n", "f")


def test_signature_using_a_class_the_reference_defines_is_rejected():
    ref = "class Item:\n    pass\n\ndef f(x: Item):\n    return x\n"
    with pytest.raises(ValueError, match=r"\['Item'\]"):
        _make_function_starter(ref, "f")


def test_default_using_a_module_constant_is_rejected():
    with pytest.raises(ValueError, match=r"\['DEFAULT'\]"):
        _make_function_starter("DEFAULT = 5\n\ndef f(x=DEFAULT):\n    return x\n", "f")


def test_builtin_names_in_the_signature_are_fine():
    _make_function_starter("def f(x: list, y: dict = None) -> bool:\n    return True\n", "f")


def test_syntax_error_in_reference_is_reported():
    with pytest.raises(ValueError, match="syntax error"):
        _make_function_starter("def f(:\n", "f")


# the 'must fail once' rule 
def graded(*passed, load_error=None):
    if load_error:
        return [{"passed": False, "reason": "load_error", "detail": load_error}]
    return [{"passed": p} if p else {"passed": False, "reason": "wrong_output", "got": None, "expected": 1} for p in passed]


def test_one_failing_case_is_enough():
    check_starter_fails(graded(False, False, False))
    check_starter_fails(graded(True, True, False))


def test_starter_that_passes_everything_is_rejected_with_advice():
    with pytest.raises(ValueError, match="already passes every test case") as exc:
        check_starter_fails(graded(True, True, True))
    assert "RETURN" in str(exc.value)


def test_a_starter_that_does_not_load_is_our_bug_not_the_models():
    with pytest.raises(StarterError, match="could not be loaded"):
        check_starter_fails(graded(load_error="NameError: Item"))
    assert not issubclass(StarterError, ValueError)


def test_no_cases_means_nothing_to_check():
    check_starter_fails([])


# end to end with the real driver
@needs_sigalrm
def test_reference_passes_and_starter_fails_through_the_real_driver():
    inputs = [[1, 2], [5, 5], [0, 0]]
    reference_report = run_locally(REF, "add", inputs)
    expected = [o.value for o in reference_report.cases]
    assert expected == [3, 10, 0]

    assert all(g["passed"] for g in grade(reference_report, expected))              # reference solves it
    starter_graded = grade(run_locally(_make_function_starter(REF, "add"), "add", inputs), expected)
    assert not any(g["passed"] for g in starter_graded)                              # starter does not
    check_starter_fails(starter_graded)

@needs_sigalrm
def test_a_print_only_exercise_is_caught_because_its_starter_already_passes():
    ref = "def show(x):\n    print(x)\n"
    inputs = [["a"], ["b"]]
    expected = [o.value for o in run_locally(ref, "show", inputs).cases]            # [None, None]
    starter_graded = grade(run_locally(_make_function_starter(ref, "show"), "show", inputs), expected)
    with pytest.raises(ValueError, match="already passes"):
        check_starter_fails(starter_graded)


def test_project_starter_replaces_only_the_entry_file():
    reference_files = {
        "main.py": "def add(a, b):\\n    return a + b\\n",
        "helpers.py": "def internal_helper():\\n    return 'reference secret'\\n",
    }
    starter_files = {
        "main.py": "old generated entry file",
        "helpers.py": "def internal_helper():\\n    return 'learner scaffold'\\n",
        "README.md": "# Add numbers",
    }

    project = make_starter(
        reference_files,
        starter_files,
        entry_file="main.py",
        function_name="add",
    )

    assert set(project) == set(starter_files)
    assert "def add(a, b):" in project["main.py"]
    assert "return" not in project["main.py"]
    assert project["helpers.py"] == starter_files["helpers.py"]
    assert project["README.md"] == starter_files["README.md"]
    assert "reference secret" not in str(project)


def test_project_starter_does_not_mutate_input_mappings():
    reference_files = {"main.py": "def add(a, b):\\n    return a + b\\n"}
    starter_files = {"main.py": "placeholder", "helpers.py": "VALUE = 1\\n"}

    result = make_starter(
        reference_files,
        starter_files,
        entry_file="main.py",
        function_name="add",
    )

    assert starter_files["main.py"] == "placeholder"
    assert result is not starter_files


def test_project_starter_requires_entry_file_in_both_projects():
    with pytest.raises(ValueError, match="reference project"):
        make_starter(
            {},
            {"main.py": "pass"},
            entry_file="main.py",
            function_name="add",
        )

    with pytest.raises(ValueError, match="starter project"):
        make_starter(
            {"main.py": "def add(a, b):\\n    return a + b\\n"},
            {},
            entry_file="main.py",
            function_name="add",
        )
