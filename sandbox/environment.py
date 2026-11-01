from __future__ import annotations

import re
import sys
import shlex
from collections import defaultdict
from pathlib import Path
from models.data_models import EnvironmentSpec,DocScan
from importlib.metadata import packages_distributions

IMPORT_TO_DIST=packages_distributions()

_FENCE = re.compile(r"^\s*```+\s*([A-Za-z0-9_+-]*)")
_IMPORT = re.compile(r"^\s*import\s+(.+)")
_DOTTED = re.compile(r"[A-Za-z_][\w.]*")
_FROM = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\s")
_INSTALL = re.compile(r"(?:pip3?|python3? -m pip|uv(?: pip)?)\s+(?:install|add)\s+(.+)")
_PY_LANGS = {"", "python", "py", "python3"}

ALIASES = {
    "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn", "cv2": "opencv-python-headless",
    "bs4": "beautifulsoup4", "dotenv": "python-dotenv", "jwt": "pyjwt", "jose": "python-jose",
    "multipart": "python-multipart", "dateutil": "python-dateutil", "attr": "attrs",
}

def render_dockerfile(spec:EnvironmentSpec) -> str:
    "Render for the Docker image file with the necessary dependecies"

    lines=[f'FROM python:{spec.python}-slim']
    if spec.apt:
        lines.append("RUN apt-get update && apt-get install -y --no-install-recommends "
                     + " ".join(sorted(spec.apt)) + " && rm -rf /var/lib/apt/lists/*")

    if spec.packages:
        pins = " ".join(shlex.quote(f"{n}=={v}") for n, v in sorted(spec.packages.items()))
        lines.append(f"RUN pip install --no-cache-dir --only-binary=:all: {pins}")

    return "\n".join(lines)+"\n"

def _find_local_modules(raw_docs_dir:Path)->set[str]:
    modules=set()

    for path in raw_docs_dir.rglob("*.py"):
        modules.add(path.stem)
    return modules

def scan_docs(raw_docs_dir:Path,*,stdlib:frozenset[str]|None=None) ->DocScan:
    "Scans and creates a DocScan containing necessary libraries for the Course"
    stdlib=stdlib if stdlib is not None else frozenset(sys.stdlib_module_names) | {"__future__"}
    local_modules=_find_local_modules(raw_docs_dir)
    imports:dict[str,set[str]]=defaultdict(set)
    hints:dict[str,set[str]]=defaultdict(set)

    for md in sorted(raw_docs_dir.glob("*.md")):
        in_fence,lang=False,""
        for line in md.read_text(encoding='utf-8').splitlines():
            fence=_FENCE.match(line)
            if fence:
                in_fence,lang=(not in_fence),fence.group(1).lower()
                continue
            if not in_fence:
                continue

            install=_INSTALL.search(line)
            if install:
                for token in install.group(1).split():
                    token=token.strip("\"'")
                    if token and not token.startswith("-"):
                        hints[token].add(md.name)

            if lang not in _PY_LANGS:
                continue
            names: list[str] = []
            if (m := _FROM.match(line)):
                names = [m.group(1)]
            elif (m := _IMPORT.match(line)):
                items = (part.split(" as ")[0].split("#")[0].strip() for part in m.group(1).split(","))
                names = [i for i in items if _DOTTED.fullmatch(i)]
            for dotted in names:
                top = dotted.split(".")[0]
                if top not in stdlib and top not in local_modules:
                    imports[top].add(md.name)

    return DocScan(
        imports={k:sorted(v) for k,v in sorted(imports.items())},
        install_hints={k:sorted(v) for k,v in sorted(hints.items())})

def resolve_import(import_name:str) ->str|None:
    if import_name in ALIASES:
        return ALIASES[import_name]

    distributions=IMPORT_TO_DIST.get(import_name)
    if not distributions:
        return None

    return distributions[0]

def normalize_install_hint(hint: str) -> str:
    return re.split(r"[\[=<>!~; ]", hint, maxsplit=1)[0]

def propose_packages(scan: DocScan) -> list[str]:
    "Candidate distribution names (UNPINNED)."
    packages:set[str]=set()
    for hint in scan.install_hints:
        packages.add(normalize_install_hint(hint))

    for import_name in scan.imports:
        package=resolve_import(import_name)

        if package:
            packages.add(package)

    return sorted(packages)