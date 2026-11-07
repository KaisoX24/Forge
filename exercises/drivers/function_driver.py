_DRIVER = r'''
import importlib
import json
import signal
import sys
import tempfile
from pathlib import Path, PurePosixPath

payload = json.loads(__PAYLOAD__)
report = {"fatal": None, "cases": []}


class _CaseTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _CaseTimeout()


def _load_project():
    files = payload["files"]
    entry_file = payload["entry_file"]

    if not isinstance(files, dict) or not files:
        raise ValueError("Project files must be a non-empty dictionary.")

    if not isinstance(entry_file, str) or not entry_file:
        raise ValueError("Entry file must be a non-empty string.")

    validated_files = {}

    for filename, source in files.items():
        if not isinstance(filename, str) or not filename:
            raise ValueError("Project filenames must be non-empty strings.")

        if not isinstance(source, str):
            raise ValueError(
                f"Source for {filename!r} must be a string."
            )

        if "\\" in filename:
            raise ValueError(
                f"Invalid project path: {filename!r}"
            )

        raw_parts = filename.split("/")

        if any(part in ("", ".", "..") for part in raw_parts):
            raise ValueError(
                f"Invalid project path: {filename!r}"
            )

        path = PurePosixPath(filename)

        if path.is_absolute():
            raise ValueError(
                f"Absolute project paths are not allowed: {filename!r}"
            )

        validated_files[path] = source

    entry_path = PurePosixPath(entry_file)

    if entry_path not in validated_files:
        raise ValueError(
            f"Entry file {entry_file!r} does not exist in the project."
        )

    if entry_path.suffix != ".py":
        raise ValueError("The entry file must be a Python (.py) file.")

    module_parts = list(entry_path.parts[:-1])

    if entry_path.name == "__init__.py":
        if not module_parts:
            raise ValueError(
                "A root-level __init__.py cannot be used as an entry file."
            )
    else:
        module_parts.append(entry_path.stem)

    if not all(part.isidentifier() for part in module_parts):
        raise ValueError(
            f"Entry file path does not form a valid Python module name: "
            f"{entry_file!r}"
        )

    module_name = ".".join(module_parts)

    project_root = Path(
        tempfile.mkdtemp(prefix="forge_project_", dir="/tmp")
    ).resolve()

    for relative_path, source in validated_files.items():
        destination = project_root.joinpath(*relative_path.parts)

        if not destination.resolve().is_relative_to(project_root):
            raise ValueError(
                f"Project path escapes its root: {str(relative_path)!r}"
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")

    sys.path.insert(0, str(project_root))
    importlib.invalidate_caches()

    module = importlib.import_module(module_name)

    function = getattr(module, payload["function"], None)

    if not callable(function):
        raise ValueError(
            f"Entry module {module_name!r} does not define a "
            f"callable named {payload['function']!r}."
        )

    return function


try:
    func = _load_project()
except Exception as exc:
    report["fatal"] = f"{type(exc).__name__}: {exc}"
    func = None

if func is not None:
    signal.signal(signal.SIGALRM, _on_alarm)

    for args in payload["inputs"]:
        try:
            signal.alarm(payload["case_timeout"])

            value = func(*args)

            json.dumps(value)

            report["cases"].append({
                "ok": True,
                "value": value,
            })

        except _CaseTimeout:
            report["cases"].append({
                "ok": False,
                "error": "TimeoutError: case took too long",
            })

        except Exception as exc:
            report["cases"].append({
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

        finally:
            signal.alarm(0)

sys.stdout.write(
    "\n" + "__MARKER__" + json.dumps(report) + "\n"
)
'''