import pytest

from api.services import generation as G


class Spy:
    "Records how the factory built things; stands in for StepGenerator, get_llm and make_verifier."
    def __init__(self):
        self.generators, self.llm_models, self.verifier_args = [], [], []


@pytest.fixture
def spy(monkeypatch):
    s = Spy()

    class FakeGenerator:
        def __init__(self, llm, **kwargs):
            self.llm, self.kwargs = llm, kwargs
            s.generators.append(self)

    monkeypatch.setattr(G, "StepGenerator", FakeGenerator)
    monkeypatch.setattr(G, "get_llm", lambda model: s.llm_models.append(model) or f"llm:{model}")
    monkeypatch.setattr(G, "make_verifier",
                        lambda pool, env: s.verifier_args.append((pool, env)) or "verifier")
    return s


class FakeRegistry:
    def pool_for(self, key, env):
        return f"pool:{key}"


class FakeEnv:
    packages = ("fastapi", "pydantic")


class FakeCourse:
    env = FakeEnv()


def test_factory_wires_pool_verifier_packages_and_stage_callback(spy):
    built = []
    retrieval = type("R", (), {"retrieve": staticmethod(lambda q: [])})()
    make = G.make_generator_factory(FakeRegistry(), model="m1",
                                    retrieval_factory=lambda: built.append(1) or retrieval)
    stages = []
    gen = make("demo", FakeCourse(), lambda sid, stage: stages.append((sid, stage)))
    assert gen.llm == "llm:m1" and spy.verifier_args == [("pool:demo", FakeCourse.env)]
    assert gen.kwargs["verify"] == "verifier" and gen.kwargs["packages"] == ["fastapi", "pydantic"]
    assert gen.kwargs["retrieve"] is retrieval.retrieve
    gen.kwargs["on_stage"]("m1-s1", "lesson")
    assert stages == [("m1-s1", "lesson")]


def test_default_retrieval_is_built_once_and_not_at_import(monkeypatch):
    import sys
    import types

    built = []

    class FakeRetriever:
        def __init__(self):
            built.append("retriever")

    class FakeTool:
        def __init__(self, retriever):
            self.retriever = retriever

    monkeypatch.setitem(sys.modules, "retrieval", types.ModuleType("retrieval"))
    monkeypatch.setitem(sys.modules, "retrieval.retriever", types.SimpleNamespace(Retriever=FakeRetriever))
    monkeypatch.setitem(sys.modules, "retrieval.retrieval_tool", types.SimpleNamespace(RetrievalTool=FakeTool))
    G._default_retrieval.cache_clear()
    assert built == []                              # nothing built just by importing the module
    first, second = G._default_retrieval(), G._default_retrieval()
    assert first is second and built == ["retriever"]
    G._default_retrieval.cache_clear()