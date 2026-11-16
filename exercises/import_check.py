import ast
from pathlib import PurePosixPath
from typing import Iterator,NamedTuple
import json
import logging
from collections.abc import Callable
from models.data_models import ExecutionResult

class Import(NamedTuple):
    module:str
    name:str|None
    file:str
    line:int

log=logging.getLogger(__name__)

_MARKER="__IMPORT_CHECK__"
IMPORT_CHECK_TIMEOUT_SECONDS=20
MAX_REPORTED=5
_GUARDS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}

STDLIB_CANDIDATES = ["typing", "typing_extensions", "collections", "collections.abc", "functools",
                     "itertools", "dataclasses", "enum", "pathlib", "datetime", "contextlib",
                     "abc", "json", "re", "asyncio", "inspect", "types"]

_SCRIPT = '''
import difflib, importlib, json
import importlib.metadata
payload = json.loads(__PAYLOAD__)
hints = list(payload["hints"])
wanted = {p.lower().replace("_", "-") for p in payload["packages"]}
try:
    for top_level, owners in importlib.metadata.packages_distributions().items():
        if any(o.lower().replace("_", "-") in wanted for o in owners) and top_level not in hints:
            hints.append(top_level)                # e.g. beautifulsoup4 -> bs4, pyyaml -> yaml
except Exception:
    pass
problems = []
for index, (module, name) in enumerate(payload["pairs"]):
    try:
        mod = importlib.import_module(module)
    except Exception as exc:
        problems.append({"index": index, "kind": "module", "error": type(exc).__name__ + ": " + str(exc)})
        continue
    if name is None or hasattr(mod, name):
        continue
    try:
        importlib.import_module(module + "." + name)      # a submodule counts as importable
        continue
    except Exception:
        pass
    where = []
    for other in hints:
        if other == module:
            continue
        try:
            if hasattr(importlib.import_module(other), name):
                where.append(other)
        except Exception:
            pass
    close = difflib.get_close_matches(name, [n for n in dir(mod) if not n.startswith("_")], n=3)
    problems.append({"index": index, "kind": "name", "where": where, "close": close})
print("__MARKER__" + json.dumps(problems))
'''

def _catches_import_error(handler:ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    caught=handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(n, ast.Name) and n.id in _GUARDS for n in caught)

def _import_nodes(node:ast.AST,guarded:bool=False) -> Iterator[tuple[ast.AST, bool]]:
    "Every import statement, and whether it sits in a try that tolerates a failed import."
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield node, guarded
    elif isinstance(node, ast.Try):
        inside=guarded or any(_catches_import_error(h) for h in node.handlers)
        for child in node.body:
            yield from _import_nodes(child, inside)
        for part in (node.handlers, node.orelse, node.finalbody):
            for child in part:
                yield from _import_nodes(child, guarded)
    else:
        for child in ast.iter_child_nodes(node):
            yield from _import_nodes(child, guarded)

def _local_names(files: dict[str, str]) -> set[str]:
    "Top-level names that are the project's own files."
    names = set()
    for path in files:
        parts = PurePosixPath(path).parts
        names.add(parts[0] if len(parts) > 1 else PurePosixPath(path).stem)
    return names

def imports_of(files: dict[str, str]) -> list[Import]:
    "The imports a project needs from OUTSIDE itself, deduplicated, in order of appearance."
    local=_local_names(files)
    found:list[Import] = []
    seen:set[tuple[str, str | None]] = set()

    def add(module: str, name: str | None, path: str, line: int) -> None:
        if (module, name) not in seen:
            seen.add((module, name))
            found.append(Import(module, name, path, line))

    for path, source in files.items():
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node, guarded in _import_nodes(tree):
            if guarded:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in local:
                        add(alias.name, None, path, node.lineno)
            elif node.level == 0 and node.module and node.module != "__future__" \
                    and node.module.split(".")[0] not in local:
                for alias in node.names:
                    add(node.module, None if alias.name == "*" else alias.name, path, node.lineno)
    return found

def build_check_script(imports: list[Import], hint_modules: list[str],
                       packages: list[str] | None = None) -> str:
    payload = json.dumps({"pairs": [[i.module, i.name] for i in imports],
                          "hints": hint_modules, "packages": list(packages or [])})
    return _SCRIPT.replace("__PAYLOAD__", repr(payload)).replace("__MARKER__", _MARKER)

def _describe(imp:Import,problem:dict) -> str:
    where=f"{imp.file} line {imp.line}"

    if problem['kind']=='module':
        return f"{where}: cannot import module '{imp.module}' ({problem['error']})."

    text = f"{where}: '{imp.name}' cannot be imported from '{imp.module}'."
    if problem["where"]:
        text += f" It is available from: {', '.join(problem['where'])}."
    if problem["close"]:
        text += f" Similar names in '{imp.module}': {', '.join(problem['close'])}."
    return text

def check_imports(run_script: Callable[[str], ExecutionResult], imports: list[Import],
                  hint_modules: list[str] | None = None,
                  packages: list[str] | None = None) -> list[str]:
    """Problems with the imports, as messages a model can act on"""
    if not imports:
        return []
    script = build_check_script(imports, STDLIB_CANDIDATES + list(hint_modules or []),packages)
    result = run_script(script)
    line = next((l for l in reversed(result.stdout.splitlines()) if l.startswith(_MARKER)), None)
    if not result.success or line is None:
        log.warning("Import check could not run: %s", result.stderr[-300:])
        return []
    problems = json.loads(line[len(_MARKER):])
    return [_describe(imports[p["index"]], p) for p in problems[:MAX_REPORTED]]

def make_import_checker(pool,packages: list[str] | None = None) -> Callable[[dict[str, str]], list[str]]:
    "files -> problems, running the check in the course's own sandbox (same packages as the learner)."
    from sandbox.sandbox import SandBox

    def run_script(code: str) -> ExecutionResult:
        return SandBox(pool, code, timeout_seconds=IMPORT_CHECK_TIMEOUT_SECONDS).sandbox_instance()

    return lambda files: check_imports(run_script, imports_of(files), packages=packages)