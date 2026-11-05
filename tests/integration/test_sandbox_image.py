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


def test_case_runner_checks_pass_inside_the_custom_image(pool):
    results = run_checks(lambda code: SandBox(pool, code, timeout_seconds=15).sandbox_instance())
    failed = [(n, d) for n, ok, d in results if not ok]
    assert not failed, failed


def test_declared_package_is_importable_in_the_image(pool):
    out = SandBox(pool, "import pydantic; print(pydantic.VERSION)").sandbox_instance()
    assert out.success and out.stdout.strip() == version("pydantic")


def test_network_is_still_disabled(pool):
    code = "import socket; socket.create_connection(('1.1.1.1', 53), timeout=2)"
    assert not SandBox(pool, code).sandbox_instance().success


def test_files_do_not_leak_between_runs(pool):
    write = "open('/tmp/leak.txt','w').write('x')"
    read = "import os; print(os.path.exists('/tmp/leak.txt'))"
    assert SandBox(pool, write).sandbox_instance().success
    assert SandBox(pool, read).sandbox_instance().stdout.strip() == "False"


def test_root_filesystem_is_read_only(pool):
    assert not SandBox(pool, "open('/usr/leak.txt','w')").sandbox_instance().success


def test_background_process_never_survives_into_the_next_run(pool):
    spawn = "import subprocess; subprocess.Popen(['sleep','600'])"
    count = "import os; print(len([p for p in os.listdir('/proc') if p.isdigit()]))"
    SandBox(pool, spawn).sandbox_instance()
    assert int(SandBox(pool, count).sandbox_instance().stdout.strip()) <= 3

def test_reference_passes_and_starter_fails_in_the_container(pool):
    from exercises.case_runner import grade, run_cases
    from exercises.checks import check_starter_fails
    from exercises.starter import make_starter

    run = lambda code: SandBox(pool, code, timeout_seconds=20).sandbox_instance()
    reference = "def add(a, b):\n    return a + b\n"
    inputs = [[1, 2], [5, 5], [0, 0]]

    ref_report = run_cases(run, reference, "add", inputs)
    expected = [o.value for o in ref_report.cases]
    assert expected == [3, 10, 0]
    assert all(g["passed"] for g in grade(ref_report, expected))

    starter_graded = grade(run_cases(run, make_starter(reference, "add"), "add", inputs), expected)
    assert not any(g["passed"] for g in starter_graded)
    check_starter_fails(starter_graded)


def test_print_only_exercise_is_rejected_in_the_container(pool):
    from exercises.case_runner import grade, run_cases
    from exercises.checks import check_starter_fails
    from exercises.starter import make_starter

    run = lambda code: SandBox(pool, code, timeout_seconds=20).sandbox_instance()
    reference = "def show(x):\n    print(x)\n"
    inputs = [["a"], ["b"]]
    expected = [o.value for o in run_cases(run, reference, "show", inputs).cases]       # [None, None]
    starter_graded = grade(run_cases(run, make_starter(reference, "show"), "show", inputs), expected)
    with pytest.raises(ValueError, match="already passes"):
        check_starter_fails(starter_graded)

def test_set_ordering_is_caught_as_nondeterministic_in_the_container(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = lambda code: SandBox(pool, code, timeout_seconds=20).sandbox_instance()
    ref = "def uniq(words):\n    return list(set(words))\n"
    words = ["pear", "apple", "fig", "kiwi", "plum", "lime", "date", "peach", "mango", "grape"]
    inputs = [[words]]
    first, second = run_cases(run, ref, "uniq", inputs), run_cases(run, ref, "uniq", inputs)
    with pytest.raises(ValueError, match="different results"):
        verify_reference_run(first, ["many fruits"], inputs, second_report=second)


def test_a_stable_reference_passes_both_runs_in_the_container(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = lambda code: SandBox(pool, code, timeout_seconds=20).sandbox_instance()
    ref = "def uniq(words):\n    return sorted(set(words))\n"
    inputs = [[["b", "a", "b", "c"]]]
    first, second = run_cases(run, ref, "uniq", inputs), run_cases(run, ref, "uniq", inputs)
    assert verify_reference_run(first, ["dupes"], inputs, second_report=second) == [["a", "b", "c"]]


def test_a_missing_module_is_reported_with_the_installed_packages(pool):
    from exercises.case_runner import run_cases
    from exercises.checks import verify_reference_run

    run = lambda code: SandBox(pool, code, timeout_seconds=20).sandbox_instance()
    report = run_cases(run, "import numpy\n\ndef f(x):\n    return x\n", "f", [[1]])
    with pytest.raises(ValueError, match="standard library") as exc:
        verify_reference_run(report, ["a"], [[1]], available_packages=["pydantic"])
    assert "numpy" in str(exc.value) and "pydantic" in str(exc.value)