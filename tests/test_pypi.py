from datetime import datetime, timezone
import pytest

from sandbox.pypi import dependency_names, normalize, pick_version, wheel_supports

UTC = timezone.utc


@pytest.mark.parametrize("name,ok", [
    ("pkg-1.0-py3-none-any.whl", True),
    ("pkg-1.0-py2.py3-none-any.whl", True),
    ("pkg-1.0-cp311-cp311-manylinux_2_17_x86_64.whl", True),
    ("pkg-1.0-cp39-abi3-manylinux2014_x86_64.whl", True),     # abi3 from an OLDER python still works
    ("pkg-1.0-cp312-abi3-manylinux2014_x86_64.whl", False),   # abi3 from a NEWER python does not
    ("pkg-1.0-cp312-cp312-manylinux2014_x86_64.whl", False),
    ("pkg-1.0-cp311-cp311-win_amd64.whl", False),
    ("pkg-1.0-cp311-cp311-macosx_11_0_arm64.whl", False),
    ("pkg-1.0.tar.gz", False),
])
def test_wheel_supports_python_311_on_linux(name, ok):
    assert wheel_supports(name, "3.11") is ok


def _file(version, uploaded, *, wheel="py3-none-any", yanked=False, requires_python=None, kind="bdist_wheel"):
    fname = f"pkg-{version}-{wheel}.whl" if kind == "bdist_wheel" else f"pkg-{version}.tar.gz"
    return {"filename": fname, "packagetype": kind, "yanked": yanked, "requires_python": requires_python,
            "upload_time_iso_8601": uploaded}


PROJECT = {"releases": {
    "1.0.0": [_file("1.0.0", "2024-01-01T00:00:00.000000Z")],
    "1.1.0": [_file("1.1.0", "2024-06-01T00:00:00.000000Z")],
    "1.2.0": [_file("1.2.0", "2024-09-01T00:00:00.000000Z", yanked=True)],
    "2.0.0rc1": [_file("2.0.0rc1", "2024-10-01T00:00:00.000000Z")],
    "2.0.0": [_file("2.0.0", "2025-01-01T00:00:00.000000Z", requires_python=">=3.12")],
    "2.1.0": [_file("2.1.0", "2025-02-01T00:00:00.000000Z", kind="sdist")],
    "garbage-version": [],
}}


def test_pick_version_skips_yanked_prerelease_sdist_only_and_wrong_python():
    assert pick_version(PROJECT, python="3.11") == "1.1.0"


def test_pick_version_matches_the_docs_snapshot_date():
    assert pick_version(PROJECT, python="3.11", as_of=datetime(2024, 3, 1, tzinfo=UTC)) == "1.0.0"


def test_pick_version_returns_none_when_nothing_existed_yet():
    assert pick_version(PROJECT, python="3.11", as_of=datetime(2023, 1, 1, tzinfo=UTC)) is None


def test_pick_version_allows_newer_release_on_newer_python():
    assert pick_version(PROJECT, python="3.12") == "2.0.0"


def test_normalize():
    assert normalize("Fast_API.Core") == "fast-api-core"


def test_dependency_names_respect_markers_and_extras():
    release = {"info": {"requires_dist": [
        "starlette<1,>=0.40",
        "uvicorn; extra == 'standard'",
        "tomli; python_version < '3.11'",
        "pywin32; sys_platform == 'win32'",
        "Typing_Extensions>=4",
    ]}}
    assert dependency_names(release, extras=set(), python="3.11") == {"starlette", "typing-extensions"}
    assert "uvicorn" in dependency_names(release, extras={"standard"}, python="3.11")
    assert "tomli" in dependency_names(release, extras=set(), python="3.10")