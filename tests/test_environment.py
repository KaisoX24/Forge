import pytest
from pydantic import ValidationError

from models.data_models import DocScan, EnvironmentSpec
from sandbox.environment import normalize_install_hint, propose_packages, render_dockerfile, scan_docs


# EnvironmentSpec identity
def test_env_id_ignores_package_and_apt_order():
    a = EnvironmentSpec(apt=["libpq5", "curl"], packages={"fastapi": "0.115.0", "pydantic": "2.9.0"})
    b = EnvironmentSpec(apt=["curl", "libpq5"], packages={"pydantic": "2.9.0", "fastapi": "0.115.0"})
    assert a.env_id == b.env_id


def test_env_id_changes_when_a_version_changes():
    a = EnvironmentSpec(packages={"fastapi": "0.115.0"})
    b = EnvironmentSpec(packages={"fastapi": "0.115.1"})
    assert a.env_id != b.env_id


@pytest.mark.parametrize("bad", [">=0.1", "latest", "", "1.0; rm -rf /"])
def test_unpinned_or_hostile_versions_are_rejected(bad):
    with pytest.raises(ValidationError):
        EnvironmentSpec(packages={"fastapi": bad})


# Dockerfile rendering 
def test_dockerfile_is_deterministic_and_pinned():
    spec = EnvironmentSpec(packages={"pydantic": "2.9.0", "fastapi": "0.115.0"})
    text = render_dockerfile(spec)
    assert text == render_dockerfile(spec)
    assert text.startswith("FROM python:3.11-slim")
    assert "fastapi==0.115.0 pydantic==2.9.0" in text
    assert "--only-binary=:all:" in text
    assert "apt-get" not in text


def test_dockerfile_installs_apt_before_pip():
    text = render_dockerfile(EnvironmentSpec(apt=["curl"], packages={"x": "1"}))
    assert text.index("apt-get") < text.index("pip install")


# Doc scanning (self-contained: no host-environment dependence) 
def _scan(tmp_path, markdown: str) -> DocScan:
    (tmp_path / "page.md").write_text(markdown, encoding="utf-8")
    return scan_docs(tmp_path, stdlib=frozenset({"json", "os"}))


def test_scan_finds_python_imports_and_ignores_stdlib(tmp_path):
    scan = _scan(tmp_path, "```python\nimport json\nfrom fastapi import FastAPI\nimport pydantic as pd\n```\n")
    assert set(scan.imports) == {"fastapi", "pydantic"}


def test_scan_ignores_non_python_fences_and_prose(tmp_path):
    scan = _scan(tmp_path, "import requests\n```bash\nimport nope\n```\n")
    assert scan.imports == {}


def test_scan_ignores_modules_the_docs_define_themselves(tmp_path):
    (tmp_path / "main.py").write_text("")
    scan = _scan(tmp_path, "```python\nfrom main import app\nimport fastapi\n```\n")
    assert set(scan.imports) == {"fastapi"}


def test_scan_collects_install_hints(tmp_path):
    scan = _scan(tmp_path, '```bash\n$ pip install "fastapi[standard]" httpx\n```\n')
    assert {"fastapi[standard]", "httpx"} <= set(scan.install_hints)


@pytest.mark.parametrize("hint,name", [("fastapi[standard]", "fastapi"), ("pydantic>=2", "pydantic"), ("httpx", "httpx")])
def test_install_hint_normalisation(hint, name):
    assert normalize_install_hint(hint) == name


def test_propose_packages_uses_hints_even_if_not_installed_on_host():
    scan = DocScan(imports={}, install_hints={"definitely-not-installed-here": ["a.md"]})
    assert propose_packages(scan) == ["definitely-not-installed-here"]


# extras, canonical names, quoting 
@pytest.mark.parametrize("raw,canonical", [
    ("FastAPI", "fastapi"),
    ("Fast_API", "fast-api"),
    ("zope.interface", "zope-interface"),
    ("fastapi[standard]", "fastapi[standard]"),
    ("Fast_API[ Standard , ALL ]", "fast-api[all,standard]"),
    ("fastapi[standard,standard]", "fastapi[standard]"),
])
def test_canonical_requirement(raw, canonical):
    from models.data_models import canonical_requirement
    assert canonical_requirement(raw) == canonical


@pytest.mark.parametrize("bad", ["", "-leading-dash", "has space", "name[", "name[]]", "a;b", "x[y]z", "$(rm -rf /)"])
def test_canonical_requirement_rejects_garbage(bad):
    from models.data_models import canonical_requirement
    with pytest.raises(ValueError):
        canonical_requirement(bad)


def test_spec_normalises_package_names_and_extras():
    spec = EnvironmentSpec(packages={"Fast_API[Standard]": "0.1.0"})
    assert spec.packages == {"fast-api[standard]": "0.1.0"}


def test_spec_with_equivalent_spellings_has_one_identity():
    a = EnvironmentSpec(packages={"Fast_API[standard]": "1.0"})
    b = EnvironmentSpec(packages={"fast-api[standard]": "1.0"})
    assert a.env_id == b.env_id and a.image_tag == b.image_tag


def test_spec_rejects_two_spellings_with_conflicting_pins():
    with pytest.raises(ValidationError, match="conflicting pins"):
        EnvironmentSpec(packages={"Fast_API": "1.0", "fast-api": "2.0"})


def test_spec_accepts_two_spellings_with_the_same_pin():
    assert EnvironmentSpec(packages={"Fast_API": "1.0", "fast-api": "1.0"}).packages == {"fast-api": "1.0"}


def test_spec_dedupes_and_sorts_apt():
    assert EnvironmentSpec(apt=["curl", "libpq5", "curl"]).apt == ["curl", "libpq5"]


def test_spec_packages_are_stored_sorted():
    assert list(EnvironmentSpec(packages={"zeta": "1", "alpha": "1"}).packages) == ["alpha", "zeta"]


def test_dockerfile_quotes_extras_so_the_shell_cannot_glob_them():
    text = render_dockerfile(EnvironmentSpec(packages={"fastapi[standard]": "0.115.0", "pydantic": "2.9.0"}))
    assert "'fastapi[standard]==0.115.0'" in text     
    assert " pydantic==2.9.0" in text                  


def test_dockerfile_for_empty_spec_has_no_install_step():
    assert render_dockerfile(EnvironmentSpec()) == "FROM python:3.11-slim\n"