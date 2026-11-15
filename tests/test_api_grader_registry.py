import pytest

from api.services.grader_registry import GraderRegistry


class FakePool:
    created = []

    def __init__(self, spec, size):
        self.spec, self.size, self.open = spec, size, False
        FakePool.created.append(self)

    def __enter__(self):
        self.open = True
        return self

    def __exit__(self, *exc):
        self.open = False


class BrokenPool(FakePool):
    def __enter__(self):
        raise RuntimeError("docker is not running")


@pytest.fixture(autouse=True)
def _reset():
    FakePool.created = []


def registry(**kw):
    return GraderRegistry(pool_factory=FakePool, grader_factory=lambda pool: ("grader", pool), **kw)


def test_pool_starts_lazily_and_is_reused():
    reg = registry()
    assert FakePool.created == []
    first = reg.for_course("a", "env-a")
    assert reg.for_course("a", "env-a") is first
    assert len(FakePool.created) == 1 and FakePool.created[0].open


def test_least_recently_used_pool_is_closed_to_make_room():
    reg = registry(max_pools=1)
    reg.for_course("a", "env-a")
    reg.for_course("b", "env-b")
    a, b = FakePool.created
    assert not a.open and b.open


def test_recent_use_protects_a_pool_when_two_are_allowed():
    reg = registry(max_pools=2)
    reg.for_course("a", "env-a"); reg.for_course("b", "env-b")
    reg.for_course("a", "env-a")        # a is now the most recent
    reg.for_course("c", "env-c")        # b is evicted, not a
    a, b, c = FakePool.created
    assert a.open and not b.open and c.open


def test_failed_start_leaves_nothing_behind_and_can_be_retried():
    reg = GraderRegistry(pool_factory=BrokenPool, grader_factory=lambda p: p)
    with pytest.raises(RuntimeError):
        reg.for_course("a", "env-a")
    reg2 = registry()
    reg2.for_course("a", "env-a")       # a healthy factory works afterwards
    assert FakePool.created[-1].open


def test_close_shuts_every_pool():
    reg = registry(max_pools=2)
    reg.for_course("a", "env-a"); reg.for_course("b", "env-b")
    reg.close()
    assert not any(p.open for p in FakePool.created)

def test_pool_for_returns_the_pool_the_grader_was_built_from():
    reg = registry()
    pool = reg.pool_for("a", "env-a")
    assert reg.for_course("a", "env-a") == ("grader", pool)
    assert len(FakePool.created) == 1