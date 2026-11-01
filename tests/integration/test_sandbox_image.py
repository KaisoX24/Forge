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