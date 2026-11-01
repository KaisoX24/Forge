from __future__ import annotations
import json
import re
import urllib.error,urllib.parse,urllib.request
from datetime import datetime
from typing import Callable
from packaging.requirements import InvalidRequirement,Requirement
from packaging.specifiers import InvalidSpecifier,SpecifierSet
from packaging.version import InvalidVersion,Version

Fetch = Callable[[str], "dict | None"]

class PyPIError(RuntimeError):
    "PyPI could not be reached or answered unexpectedly (NOT 'project not found')."

def normalize(name:str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

def http_fetch(url: str, timeout: float = 15) -> dict | None:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "forge-env-resolver"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None           
        raise PyPIError(f"PyPI answered {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PyPIError(f"cannot reach PyPI ({url}): {exc}") from exc

class PyPI:
    def __init__(self,fetch:Fetch=http_fetch,base_url:str="https://pypi.org/pypi"):
        self._fetch, self._base, self._cache = fetch, base_url, {}

    def _get(self,url:str) ->dict | None:
        if url not in self._cache:
            self._cache[url] = self._fetch(url)
        return self._cache[url]

    def project(self, name: str) -> dict | None:
        return self._get(f"{self._base}/{urllib.parse.quote(normalize(name))}/json")

    def release(self, name: str, version: str) -> dict | None:
        return self._get(f"{self._base}/{urllib.parse.quote(normalize(name))}/{urllib.parse.quote(version)}/json")

_WHEEL = re.compile(r"^(?P<name>.+?)-(?P<ver>[^-]+)(?:-(?P<build>\d[^-]*))?-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$")

def wheel_supports(filename: str, python: str) -> bool:
    """Can pip use this wheel on CPython `python` (e.g. '3.11') inside a Linux image?
    (CPU architecture is deliberately NOT checked: pip is the final judge at build time.)"""
    m = _WHEEL.match(filename)
    if not m:
        return False
    if m["plat"] != "any" and "linux" not in m["plat"]:
        return False
    minor = int(python.split(".")[1])
    for tag in m["py"].split("."):
        if tag in ("py3", f"py3{minor}", f"cp3{minor}"):
            return True
        if m["abi"] == "abi3" and tag.startswith("cp3") and tag[3:].isdigit() and int(tag[3:]) <= minor:
            return True
    return False

def _python_ok(requires_python: str | None, python: str) -> bool:
    if not requires_python:
        return True
    try:
        return SpecifierSet(requires_python).contains(f"{python}.99")
    except InvalidSpecifier:
        return True

def pick_version(project: dict, *, python: str, as_of: datetime | None = None) -> str | None:
    """Newest stable, non-yanked release with a wheel usable on `python`,"""
    best: Version | None = None
    for text, files in (project.get("releases") or {}).items():
        try:
            version = Version(text)
        except InvalidVersion:
            continue
        if version.is_prerelease or version.is_devrelease:
            continue
        usable = [
            f for f in files
            if not f.get("yanked") and f.get("packagetype") == "bdist_wheel"
            and wheel_supports(f["filename"], python) and _python_ok(f.get("requires_python"), python)
        ]
        if not usable:
            continue
        if as_of is not None:
            times = [datetime.fromisoformat(f["upload_time_iso_8601"]) for f in files if f.get("upload_time_iso_8601")]
            if not times or min(times) > as_of:
                continue
        if best is None or version > best:
            best = version
    return str(best) if best else None

_LINUX_ENV = {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix",
              "implementation_name": "cpython", "platform_python_implementation": "CPython"}

def dependency_names(release: dict, *, extras: set[str], python: str) -> set[str]:
    env = {**_LINUX_ENV, "python_version": python, "python_full_version": f"{python}.0"}
    names: set[str] = set()
    for line in (release.get("info") or {}).get("requires_dist") or []:
        try:
            req = Requirement(line)
        except InvalidRequirement:
            continue
        if req.marker is None or any(req.marker.evaluate({**env, "extra": e}) for e in (extras | {""})):
            names.add(normalize(req.name))
    return names