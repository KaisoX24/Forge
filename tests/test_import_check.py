import subprocess
import sys
import pytest
from exercises.import_check import Import, imports_of,build_check_script,check_imports
from models.data_models import ExecutionResult



def pairs(files):
    return [(i.module, i.name) for i in imports_of(files)]


def test_plain_and_from_imports_with_file_and_line():
    files = {"main.py": "import os\nfrom fastapi import FastAPI, Depends, Annotated\n"}
    assert imports_of(files) == [
        Import("os", None, "main.py", 1),
        Import("fastapi", "FastAPI", "main.py", 2),
        Import("fastapi", "Depends", "main.py", 2),
        Import("fastapi", "Annotated", "main.py", 2),
    ]


def test_relative_future_and_star_imports():
    files = {"main.py": "from __future__ import annotations\nfrom . import x\nfrom .y import z\n"
                        "from json import *\nimport a.b.c\n"}
    assert pairs(files) == [("json", None), ("a.b.c", None)]


def test_the_projects_own_modules_are_not_checked():
    files = {"main.py": "import helpers\nfrom pkg.sub import thing\nfrom helpers import f\nimport os\n",
             "helpers.py": "x = 1\n", "pkg/__init__.py": "", "pkg/sub.py": "thing = 1\n"}
    assert pairs(files) == [("os", None)]


def test_optional_imports_are_skipped_but_other_try_blocks_are_not():
    files = {"main.py": (
        "try:\n    import ujson\nexcept ImportError:\n    ujson = None\n"
        "try:\n    import a\nexcept (KeyError, ModuleNotFoundError):\n    pass\n"
        "try:\n    import b\nexcept:\n    pass\n"
        "try:\n    import c\nexcept ValueError:\n    pass\n"
        "try:\n    pass\nexcept ImportError:\n    import d\n")}
    assert pairs(files) == [("c", None), ("d", None)]


def test_imports_inside_functions_and_classes_are_found():
    files = {"main.py": "def f():\n    import json\nclass C:\n    from typing import List\n"}
    assert pairs(files) == [("json", None), ("typing", "List")]


def test_duplicates_across_files_are_reported_once():
    files = {"a.py": "from typing import List\n", "b.py": "from typing import List\nimport os\n"}
    assert pairs(files) == [("typing", "List"), ("os", None)]


def test_broken_and_non_python_files_are_ignored():
    files = {"main.py": "def (:\n", "README.md": "import fake\n", "ok.py": "import os\n"}
    assert pairs(files) == [("os", None)]

def host_python(script: str) -> ExecutionResult:
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    return ExecutionResult(success=done.returncode == 0, stdout=done.stdout, stderr=done.stderr)


def problems(source: str, **kw):
    return check_imports(host_python, imports_of({"main.py": source}), **kw)


def test_valid_imports_give_no_problems():
    assert problems("import os\nfrom typing import Annotated, List\nfrom json import dumps\n") == []


def test_a_name_that_lives_elsewhere_is_reported_with_where_to_find_it():
    [message] = problems("from json import Annotated\n")
    assert "main.py line 1: 'Annotated' cannot be imported from 'json'" in message
    assert "It is available from:" in message and "typing" in message


def test_the_real_fastapi_mistake():
    pytest.importorskip("fastapi")
    [message] = problems("from fastapi import FastAPI, Depends, Annotated\n")
    assert "'Annotated' cannot be imported from 'fastapi'" in message and "typing" in message


def test_a_typo_gets_close_matches_and_submodules_count_as_importable():
    [message] = problems("from typing import Annotatedd\n")
    assert "Similar names in 'typing': Annotated" in message
    assert problems("from os import path\nfrom xml import etree\n") == []


def test_a_missing_module_is_reported():
    [message] = problems("import definitely_not_installed_xyz\n")
    assert "cannot import module 'definitely_not_installed_xyz'" in message and "ModuleNotFoundError" in message


def test_extra_hint_modules_are_searched():
    [message] = problems("from json import Counter\n", hint_modules=["collections"])
    assert "collections" in message


def test_the_check_never_blocks_when_it_cannot_run():
    broken = lambda script: ExecutionResult(success=False, stderr="docker exploded")
    assert check_imports(broken, imports_of({"main.py": "import os\n"})) == []
    silent = lambda script: ExecutionResult(success=True, stdout="no marker here")
    assert check_imports(silent, imports_of({"main.py": "import os\n"})) == []
    assert check_imports(broken, []) == []


def test_at_most_five_problems_are_reported():
    source = "".join(f"import missing_mod_{i}\n" for i in range(9))
    assert len(problems(source)) == 5


def test_the_script_is_valid_python_with_the_placeholders_filled():
    script = build_check_script(imports_of({"m.py": "from a import b\n"}), ["typing"])
    compile(script, "check", "exec")
    assert "__IMPORT_CHECK__" in script and "__PAYLOAD__" not in script