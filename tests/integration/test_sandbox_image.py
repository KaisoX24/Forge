
from importlib.metadata import version

import docker
import pytest

from tests.check_container import run_checks
from models.data_models import EnvironmentSpec
from sandbox.container_pool import ContainerPool
from sandbox.sandbox import SandBox

pytestmark = pytest.mark.docker


def _daemon_up() -> bool:
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def pool():
    if not _daemon_up():
        pytest.skip("Docker daemon not available")

    spec = EnvironmentSpec(packages={"pydantic": version("pydantic")})

    with ContainerPool(pool_size=1, spec=spec) as p:
        yield p


def _runner(pool, timeout_seconds=20):
    return lambda code: SandBox(
        pool,
        code,
        timeout_seconds=timeout_seconds,
    ).sandbox_instance()


def test_case_runner_checks_pass_inside_the_custom_image(pool):
    results = run_checks(_runner(pool, timeout_seconds=15))

    failed = [
        (name, detail)
        for name, passed, detail in results
        if not passed
    ]

    assert not failed, failed


def test_declared_package_is_importable_in_the_image(pool):
    out = SandBox(
        pool,
        "import pydantic; print(pydantic.VERSION)",
    ).sandbox_instance()

    assert out.success
    assert out.stdout.strip() == version("pydantic")


def test_network_is_still_disabled(pool):
    code = (
        "import socket; "
        "socket.create_connection(('1.1.1.1', 53), timeout=2)"
    )

    assert not SandBox(pool, code).sandbox_instance().success


def test_files_do_not_leak_between_runs(pool):
    write = "open('/tmp/leak.txt', 'w').write('x')"
    read = "import os; print(os.path.exists('/tmp/leak.txt'))"

    assert SandBox(pool, write).sandbox_instance().success

    result = SandBox(pool, read).sandbox_instance()

    assert result.success
    assert result.stdout.strip() == "False"


def test_root_filesystem_is_read_only(pool):
    assert not SandBox(
        pool,
        "open('/usr/leak.txt', 'w')",
    ).sandbox_instance().success


def test_background_process_never_survives_into_the_next_run(pool):
    spawn = "import subprocess; subprocess.Popen(['sleep', '600'])"
    count = (
        "import os; "
        "print(len([p for p in os.listdir('/proc') if p.isdigit()]))"
    )

    SandBox(pool, spawn).sandbox_instance()

    result = SandBox(pool, count).sandbox_instance()

    assert result.success
    assert int(result.stdout.strip()) <= 3


def test_case_runner_executes_multi_file_project(pool):
    run = _runner(pool)

    files = {
        "app/__init__.py": "",
        "app/main.py": (
            "from .helpers import calculate\n"
            "\n"
            "def process(value):\n"
            "    return calculate(value)\n"
        ),
        "app/helpers.py": (
            "def calculate(value):\n"
            "    return value * 10\n"
        ),
    }

    from exercises.case_runner import run_cases

    report = run_cases(
        run,
        files,
        "app/main.py",
        "process",
        [[2], [5], [8]],
    )

    assert report.fatal is None
    assert [case.value for case in report.cases] == [20, 50, 80]
    assert all(case.ok for case in report.cases)


def test_reference_passes_and_starter_fails_in_the_container(pool):
    from exercises.case_runner import grade, run_cases
    from exercises.checks import check_starter_fails
    from exercises.starter import make_starter

    run = _runner(pool)

    reference_files = {
        "main.py": (
            "def add(a, b):\n"
            "    return a + b\n"
        ),
    }

    starter_files = {
        "main.py": reference_files["main.py"],
    }

    inputs = [[1, 2], [5, 5], [0, 0]]

    ref_report = run_cases(
        run,
        reference_files,
        "main.py",
        "add",
        inputs,
    )

    assert ref_report.fatal is None
    assert all(case.ok for case in ref_report.cases)

    expected = [case.value for case in ref_report.cases]

    assert expected == [3, 10, 0]
    assert all(
        result["passed"]
        for result in grade(ref_report, expected)
    )

    generated_starter = make_starter(
        reference_files,
        starter_files,
        entry_file="main.py",
        function_name="add",
    )

    starter_report = run_cases(
        run,
        generated_starter,
        "main.py",
        "add",
        inputs,
    )

    starter_graded = grade(starter_report, expected)

    assert not any(result["passed"] for result in starter_graded)

    check_starter_fails(starter_graded)


def test_print_only_exercise_is_rejected_in_the_container(pool):
    from exercises.case_runner import grade, run_cases
    from exercises.checks import check_starter_fails
    from exercises.starter import make_starter

    run = _runner(pool)

    reference_files = {
        "main.py": (
            "def show(x):\n"
            "    print(x)\n"
        ),
    }

    starter_files = {
        "main.py": reference_files["main.py"],
    }

    inputs = [["a"], ["b"]]

    reference_report = run_cases(
        run,
        reference_files,
        "main.py",
        "show",
        inputs,
    )

    assert reference_report.fatal is None

    expected = [
        outcome.value
        for outcome in reference_report.cases
    ]

    assert expected == [None, None]

    generated_starter = make_starter(
        reference_files,
        starter_files,
        entry_file="main.py",
        function_name="show",
    )

    starter_report = run_cases(
        run,
        generated_starter,
        "main.py",
        "show",
        inputs,
    )

    starter_graded = grade(starter_report, expected)

    with pytest.raises(ValueError, match="already passes"):
        check_starter_fails(starter_graded)


def test_set_ordering_is_caught_as_nondeterministic_in_the_container(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = _runner(pool)

    files = {
        "main.py": (
            "def uniq(words):\n"
            "    return list(set(words))\n"
        ),
    }

    words = [
        "pear",
        "apple",
        "fig",
        "kiwi",
        "plum",
        "lime",
        "date",
        "peach",
        "mango",
        "grape",
    ]

    inputs = [[words]]

    first = run_cases(
        run,
        files,
        "main.py",
        "uniq",
        inputs,
    )

    second = run_cases(
        run,
        files,
        "main.py",
        "uniq",
        inputs,
    )

    with pytest.raises(ValueError, match="different results"):
        verify_reference_run(
            first,
            ["many fruits"],
            inputs,
            second_report=second,
        )


def test_a_stable_reference_passes_both_runs_in_the_container(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = _runner(pool)

    files = {
        "main.py": (
            "def uniq(words):\n"
            "    return sorted(set(words))\n"
        ),
    }

    inputs = [[["b", "a", "b", "c"]]]

    first = run_cases(
        run,
        files,
        "main.py",
        "uniq",
        inputs,
    )

    second = run_cases(
        run,
        files,
        "main.py",
        "uniq",
        inputs,
    )

    assert verify_reference_run(
        first,
        ["dupes"],
        inputs,
        second_report=second,
    ) == [["a", "b", "c"]]


def test_a_missing_module_is_reported_with_the_installed_packages(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = _runner(pool)

    files = {
        "main.py": (
            "import numpy\n"
            "\n"
            "def f(x):\n"
            "    return x\n"
        ),
    }

    report = run_cases(
        run,
        files,
        "main.py",
        "f",
        [[1]],
    )

    with pytest.raises(ValueError, match="standard library") as exc:
        verify_reference_run(
            report,
            ["a"],
            [[1]],
            available_packages=["pydantic"],
        )

    assert "numpy" in str(exc.value)
    assert "pydantic" in str(exc.value)
