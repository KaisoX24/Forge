from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from packaging.requirements import InvalidRequirement,Requirement
from models.data_models import DocScan,EnvironmentSpec,canonical_requirement
from sandbox.environment import ALIASES,scan_docs
from sandbox.pypi import PyPI,dependency_names,normalize,pick_version

Status = Literal["hinted", "alias", "approved", "dependency", "covered", "needs_review", "unresolved"]

@dataclass(frozen=True)
class Decision:
    subject: str
    status: Status
    dist: str | None = None
    version: str | None = None
    detail: str = ""

@dataclass
class ResolutionReport:
    pins:dict[str,str]=field(default_factory=dict)
    decisions:list[Decision]=field(default_factory=list)
    as_of:datetime|None=None

    def with_status(self, *statuses: Status) -> list[Decision]:
        return [d for d in self.decisions if d.status in statuses]

def docs_as_of(raw_docs_dir: Path) -> datetime | None:
    "The newest scraped_at in the manifest: the moment the docs snapshot was taken."
    path = Path(raw_docs_dir) / "manifest.json"
    if not path.exists():
        return None
    stamps = [datetime.fromisoformat(e["scraped_at"]) for e in json.loads(path.read_text()).values() if e.get("scraped_at")]
    return max(stamps).astimezone(timezone.utc) if stamps else None

def resolve_environment(scan: DocScan, pypi: PyPI, *, python: str = "3.11",
                        as_of: datetime | None = None, aliases: dict[str, str] = ALIASES,
                        approve: frozenset[str] = frozenset()) -> ResolutionReport:
    report = ResolutionReport(as_of=as_of)
    add = report.decisions.append
    roots: dict[str, set[str]] = {}

    for hint, pages in scan.install_hints.items():
        try:
            req = Requirement(hint)
        except InvalidRequirement:
            add(Decision(hint, "unresolved", detail="not a valid requirement string")); continue
        name = normalize(req.name)
        if pypi.project(name) is None:
            add(Decision(hint, "unresolved", name, detail="no such project on PyPI")); continue
        roots.setdefault(name, set()).update(normalize(e) for e in req.extras)
        add(Decision(hint, "hinted", name, detail=f"`pip install` shown in {', '.join(pages)}"))

    pending: list[tuple[str, str]] = []
    for top in scan.imports:
        dist = normalize(aliases.get(top, top))
        if dist in roots:
            add(Decision(top, "covered", dist, detail="already requested by an install hint")); continue
        if (top in aliases or dist in approve) and pypi.project(dist) is not None:
            roots[dist] = set()
            add(Decision(top, "alias" if top in aliases else "approved", dist)); continue
        pending.append((top, dist))

    deps: dict[str, set[str]] = {}
    for dist, extras in list(roots.items()):
        version = pick_version(pypi.project(dist), python=python, as_of=as_of)
        if version is None:
            add(Decision(dist, "unresolved", dist, detail=f"no stable wheel for Python {python} released by {as_of}"))
            del roots[dist]; continue
        release = pypi.release(dist, version) or {}
        offered = {normalize(e) for e in (release.get("info") or {}).get("provides_extra") or []}
        bad = {e for e in extras if offered and e not in offered}
        for e in sorted(bad):
            add(Decision(f"{dist}[{e}]", "unresolved", dist, version, "extra not provided by this version; dropped"))
        keep = extras - bad
        report.pins[canonical_requirement(f"{dist}[{','.join(sorted(keep))}]" if keep else dist)] = version
        deps[dist] = dependency_names(release, extras=keep, python=python)

    for top, dist in pending:
        owner = next((r for r, d in deps.items() if dist in d), None)
        if owner:
            add(Decision(top, "dependency", dist, detail=f"installed by {owner}")); continue
        project = pypi.project(dist)
        if project is None:
            add(Decision(top, "unresolved", dist, detail="no PyPI project with this name (probably defined by the docs)"))
        else:
            info = project.get("info") or {}
            add(Decision(top, "needs_review", dist,
                         detail=f"PyPI has '{dist}': {info.get('summary') or 'no summary'} -- not vouched for by the docs"))
    return report


def spec_from_docs(raw_docs_dir: Path, pypi: PyPI | None = None, *, python: str = "3.11",
                   approve: frozenset[str] = frozenset(), memory_mb: int = 256,
                   ) -> tuple[EnvironmentSpec, ResolutionReport]:
    raw_docs_dir = Path(raw_docs_dir)
    report = resolve_environment(scan_docs(raw_docs_dir), pypi or PyPI(), python=python,
                                 as_of=docs_as_of(raw_docs_dir), approve=approve)
    return EnvironmentSpec(python=python, packages=report.pins, memory_mb=memory_mb), report