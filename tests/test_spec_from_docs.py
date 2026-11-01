import json
from datetime import timezone

import pytest

from sandbox.pypi import PyPI, PyPIError
from sandbox.resolver import docs_as_of, spec_from_docs

from test_resolver import FakeIndex, project, release


def write_docs(tmp_path, pages: dict[str, str], scraped_at="2025-06-01T00:00:00+00:00"):
    manifest = {}
    for i, (fname, body) in enumerate(pages.items()):
        (tmp_path / fname).write_text(body, encoding="utf-8")
        manifest[fname] = {"url": f"https://docs.example/{fname}", "scraped_at": scraped_at,
                           "title": fname, "position": i}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))


PAGE = """# Intro

```bash
$ pip install "webfw[standard]"
```

```python
from webfw import App
from http_lib import get
from backend import utils      # an example module the docs define themselves
```
"""


@pytest.fixture
def index():
    return FakeIndex(
        projects={
            "webfw": project("webfw", ("1.0.0", "2.0.0")),
            "http-lib": project("http-lib"),
            "validator": project("validator"),
            "backend": project("backend", summary="Backend Utility Tools"),   # the real-world look-alike
        },
        releases={
            ("webfw", "2.0.0"): release(["http-lib>=1", "validator; extra == 'standard'"], ["standard"]),
            ("webfw", "1.0.0"): release(["http-lib>=1"], ["standard"]),
        },
    )


def test_full_flow_pins_hinted_package_with_extras(tmp_path, index):
    write_docs(tmp_path, {"intro.md": PAGE})
    spec, report = spec_from_docs(tmp_path, PyPI(index))
    assert spec.packages == {"webfw[standard]": "2.0.0"}


def test_look_alike_package_is_reported_and_never_installed(tmp_path, index):
    write_docs(tmp_path, {"intro.md": PAGE})
    spec, report = spec_from_docs(tmp_path, PyPI(index))
    held = {d.subject: d.status for d in report.with_status("needs_review", "unresolved")}
    assert held == {"backend": "needs_review"}
    assert "backend" not in spec.packages


def test_dependency_import_is_accepted_without_its_own_pin(tmp_path, index):
    write_docs(tmp_path, {"intro.md": PAGE})
    _, report = spec_from_docs(tmp_path, PyPI(index))
    assert [d.dist for d in report.with_status("dependency")] == ["http-lib"]


def test_approving_a_held_back_package_installs_it(tmp_path, index):
    write_docs(tmp_path, {"intro.md": PAGE})
    spec, _ = spec_from_docs(tmp_path, PyPI(index), approve=frozenset({"backend"}))
    assert "backend" in spec.packages


def test_versions_are_chosen_as_of_the_scrape_date(tmp_path, index):
    index.projects["webfw"]["releases"]["2.0.0"][0]["upload_time_iso_8601"] = "2025-09-01T00:00:00.000000Z"
    write_docs(tmp_path, {"intro.md": PAGE}, scraped_at="2025-06-01T00:00:00+00:00")
    spec, _ = spec_from_docs(tmp_path, PyPI(index))
    assert spec.packages == {"webfw[standard]": "1.0.0"}       # 2.0.0 did not exist when the docs were scraped


def test_same_docs_always_produce_the_same_environment_identity(tmp_path, index):
    write_docs(tmp_path, {"intro.md": PAGE})
    a, _ = spec_from_docs(tmp_path, PyPI(index))
    b, _ = spec_from_docs(tmp_path, PyPI(index))
    assert a.env_id == b.env_id


def test_pypi_outage_aborts_instead_of_producing_an_empty_environment(tmp_path):
    write_docs(tmp_path, {"intro.md": PAGE})
    def down(url):
        raise PyPIError("offline")
    with pytest.raises(PyPIError):
        spec_from_docs(tmp_path, PyPI(down))


def test_docs_without_any_dependencies_give_the_default_environment(tmp_path, index):
    write_docs(tmp_path, {"intro.md": "# Intro\n\nJust prose.\n"})
    spec, report = spec_from_docs(tmp_path, PyPI(index))
    assert spec.packages == {} and report.decisions == []


def test_docs_as_of_is_the_newest_scrape_time(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "a.md": {"url": "u", "scraped_at": "2025-01-01T00:00:00+00:00"},
        "b.md": {"url": "v", "scraped_at": "2025-03-05T10:00:00+00:00"},
    }))
    got = docs_as_of(tmp_path)
    assert (got.year, got.month, got.day) == (2025, 3, 5) and got.tzinfo == timezone.utc


def test_docs_as_of_is_none_without_a_manifest(tmp_path):
    assert docs_as_of(tmp_path) is None