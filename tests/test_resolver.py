from datetime import datetime, timezone

import pytest

from models.data_models import DocScan
from sandbox.pypi import PyPI, PyPIError
from sandbox.resolver import resolve_environment

WHEEL = lambda v: {"filename": f"x-{v}-py3-none-any.whl", "packagetype": "bdist_wheel", "yanked": False,
                   "requires_python": None, "upload_time_iso_8601": "2024-01-01T00:00:00.000000Z"}


def project(name, versions=("1.0.0",), summary="s"):
    return {"info": {"name": name, "summary": summary}, "releases": {v: [WHEEL(v)] for v in versions}}


def release(requires=(), extras=()):
    return {"info": {"requires_dist": list(requires), "provides_extra": list(extras)}}


class FakeIndex:
    def __init__(self, projects, releases):
        self.projects, self.releases, self.calls = projects, releases, []

    def __call__(self, url):
        self.calls.append(url)
        parts = url.removeprefix("https://pypi.org/pypi/").removesuffix("/json").split("/")
        return self.projects.get(parts[0]) if len(parts) == 1 else self.releases.get((parts[0], parts[1]))


@pytest.fixture
def index():
    return FakeIndex(
        projects={
            "webfw": project("webfw", ("1.0.0", "2.0.0")),
            "validator": project("validator"),
            "http-lib": project("http-lib"),
            "helper": project("helper", summary="Totally unrelated package"),
            "pillow": project("pillow"),
        },
        releases={
            ("webfw", "2.0.0"): release(["http-lib>=1", "validator; extra == 'standard'"], ["standard"]),
            ("validator", "1.0.0"): release(),
            ("pillow", "1.0.0"): release(),
        },
    )


def run(index, scan, **kw):
    return resolve_environment(scan, PyPI(index), as_of=datetime(2030, 1, 1, tzinfo=timezone.utc), **kw)


def status(report, subject):
    return next(d.status for d in report.decisions if d.subject == subject)


def test_hint_becomes_pin_with_extras(index):
    r = run(index, DocScan(imports={}, install_hints={"webfw[standard]": ["a.md"]}))
    assert r.pins == {"webfw[standard]": "2.0.0"}


def test_import_covered_by_hint_and_dependency_is_not_pinned(index):
    scan = DocScan(imports={"webfw": ["a.md"], "http_lib": ["a.md"]}, install_hints={"webfw>=1": ["a.md"]})
    r = run(index, scan)
    assert status(r, "webfw>=1") == "hinted"       
    assert status(r, "webfw") == "covered"
    assert status(r, "http_lib") == "dependency"
    assert r.pins == {"webfw": "2.0.0"}            


def test_extras_only_dependency_needs_the_extra(index):
    scan = DocScan(imports={"validator": ["a.md"]}, install_hints={"webfw": ["a.md"]})
    assert status(run(index, scan), "validator") == "needs_review"       
    scan = DocScan(imports={"validator": ["a.md"]}, install_hints={"webfw[standard]": ["a.md"]})
    assert status(run(index, scan), "validator") == "dependency"         


def test_unvouched_name_on_pypi_is_held_back_not_installed(index):
    r = run(index, DocScan(imports={"helper": ["a.md"]}, install_hints={}))
    assert status(r, "helper") == "needs_review"
    assert r.pins == {}


def test_human_approval_promotes_needs_review(index):
    r = run(index, DocScan(imports={"helper": ["a.md"]}, install_hints={}), approve=frozenset({"helper"}))
    assert status(r, "helper") == "approved" and r.pins == {"helper": "1.0.0"}


def test_curated_alias_is_trusted(index):
    r = run(index, DocScan(imports={"PIL": ["a.md"]}, install_hints={}))
    assert status(r, "PIL") == "alias" and r.pins == {"pillow": "1.0.0"}


def test_name_unknown_to_pypi_is_unresolved(index):
    assert status(run(index, DocScan(imports={"nope": ["a.md"]}, install_hints={})), "nope") == "unresolved"


def test_unknown_extra_is_dropped_but_package_kept(index):
    r = run(index, DocScan(imports={}, install_hints={"webfw[bogus,standard]": ["a.md"]}))
    assert r.pins == {"webfw[standard]": "2.0.0"}
    assert status(r, "webfw[bogus]") == "unresolved"


def test_invalid_requirement_string_is_reported_not_raised(index):
    r = run(index, DocScan(imports={}, install_hints={"not a req!!": ["a.md"]}))
    assert status(r, "not a req!!") == "unresolved"


def test_pin_follows_docs_snapshot_date(index):
    index.projects["webfw"]["releases"]["2.0.0"][0]["upload_time_iso_8601"] = "2025-06-01T00:00:00.000000Z"
    r = resolve_environment(DocScan(imports={}, install_hints={"webfw": ["a.md"]}), PyPI(index),
                            as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert r.pins == {"webfw": "1.0.0"}


def test_network_failure_is_an_error_not_a_silent_empty_result():
    def down(url):
        raise PyPIError("offline")
    with pytest.raises(PyPIError):
        resolve_environment(DocScan(imports={}, install_hints={"webfw": ["a.md"]}), PyPI(down))