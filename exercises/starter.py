from __future__ import annotations

import ast
import builtins
import copy

def _signature_nodes(func: ast.FunctionDef) -> list[ast.AST]:
    a = func.args
    every_arg = [*a.posonlyargs, *a.args, *a.kwonlyargs, *(x for x in (a.vararg, a.kwarg) if x)]
    return [*(x.annotation for x in every_arg if x.annotation), *a.defaults,
            *(d for d in a.kw_defaults if d is not None), *([func.returns] if func.returns else [])]

def _names_used(nodes: list[ast.AST]) -> set[str]:
    return {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}

def _defined_at_top_level(tree: ast.Module, skip: str) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name != skip:
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
    return names

def _kept_imports(tree: ast.Module, used: set[str]) -> list[ast.stmt]:
    kept: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            kept.append(node)
        elif isinstance(node, ast.Import):
            names = [a for a in node.names if (a.asname or a.name.split(".")[0]) in used]
            if names:
                kept.append(ast.Import(names=names))
        elif isinstance(node, ast.ImportFrom):
            names = [a for a in node.names if (a.asname or a.name) in used]
            if names:
                kept.append(ast.ImportFrom(module=node.module, names=names, level=node.level))
    return kept

def _make_function_starter(reference: str, function_name: str) -> str:
    try:
        tree = ast.parse(reference)
    except SyntaxError as exc:
        raise ValueError(f"The reference solution has a syntax error: {exc}") from exc

    functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    func = functions.get(function_name)
    if func is None:
        defined = sorted(n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        raise ValueError(
            f"The reference solution does not define a function named {function_name!r}. "
            f"It defines: {defined or 'nothing'}. Make function_name match a top-level `def`.")
    if isinstance(func, ast.AsyncFunctionDef):
        raise ValueError(f"{function_name!r} is an `async def`, which cannot be tested by calling it. "
                         "Write a regular `def` that returns its result.")

    used = _names_used(_signature_nodes(func))
    local = sorted(used & _defined_at_top_level(tree, skip=function_name) - set(vars(builtins)))
    if local:
        raise ValueError(
            f"The signature of {function_name!r} uses {local}, which the reference solution defines "
            "itself, so the learner's starter code would not have it. Use only built-in types or "
            "imported names in the signature (parameters, defaults, annotations).")

    stub = copy.deepcopy(func)
    stub.decorator_list = []
    first = func.body[0]
    has_doc = isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
        and isinstance(first.value.value, str)
    stub.body = [*([first] if has_doc else []), ast.Pass()]

    module = ast.Module(body=[*_kept_imports(tree, used), stub], type_ignores=[])
    text = ast.unparse(ast.fix_missing_locations(module)).rstrip()
    return text + "  # TODO: write your solution here\n" if text.endswith("pass") else text + "\n"


def make_starter(
    reference_files: dict[str, str],
    starter_files: dict[str, str],
    *,
    entry_file: str,
    function_name: str,
) -> dict[str, str]:
    if entry_file not in reference_files:
        raise ValueError(
            f"The reference project does not contain the entry file {entry_file!r}."
        )
    if entry_file not in starter_files:
        raise ValueError(
            f"The starter project does not contain the entry file {entry_file!r}."
        )

    project = dict(starter_files)
    project[entry_file] = _make_function_starter(
        reference_files[entry_file],
        function_name,
    )
    return project
