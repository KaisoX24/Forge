import pytest

import sandbox.container_pool as cp
from models.data_models import EnvironmentSpec


class FakeContainers:
    def __init__(self):
        self.runs = []

    def run(self, **kwargs):
        self.runs.append(kwargs)
        return object()


class FakeImages:
    def get(self, tag):
        return object()          


class FakeClient:
    def __init__(self):
        self.containers, self.images = FakeContainers(), FakeImages()


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(cp.docker, "from_env", lambda: fake)
    monkeypatch.setattr(cp.atexit, "register", lambda *a, **k: None)
    return fake


def test_pool_runs_containers_from_the_specs_image_and_memory(client):
    spec = EnvironmentSpec(packages={"pydantic": "2.9.0"}, memory_mb=384)
    cp.ContainerPool(pool_size=2, spec=spec)
    assert len(client.containers.runs) == 2
    for run in client.containers.runs:
        assert run["image"] == spec.image_tag
        assert run["mem_limit"] == "384m"


def test_pool_without_a_spec_keeps_the_old_defaults(client):
    cp.ContainerPool(pool_size=1)
    run = client.containers.runs[0]
    assert run["image"] == EnvironmentSpec().image_tag
    assert run["mem_limit"] == "256m"


def test_every_container_keeps_all_isolation_settings(client):
    cp.ContainerPool(pool_size=1)
    run = client.containers.runs[0]
    assert run["network_disabled"] is True
    assert run["cap_drop"] == ["all"]
    assert run["user"] == "1000:1000"
    assert run["pids_limit"] == 50
    assert run["read_only"] is True
    assert run["tmpfs"]["/tmp"].startswith("size=")
    assert run["environment"]["HOME"] == "/tmp"


def test_replacing_a_container_creates_exactly_one_with_the_same_settings(client):
    pool = cp.ContainerPool(pool_size=3, spec=EnvironmentSpec(memory_mb=300))
    pool.get_container()                  
    client.containers.runs.clear()
    pool._create_container(replace=True) 
    assert len(client.containers.runs) == 1
    assert client.containers.runs[0]["mem_limit"] == "300m"
    assert client.containers.runs[0]["image"] == pool.image


def test_image_is_built_once_up_front_not_per_container(client, monkeypatch):
    built = []
    monkeypatch.setattr(cp, "ensure_image", lambda spec, c: built.append(spec) or spec.image_tag)
    cp.ContainerPool(pool_size=4)
    assert len(built) == 1