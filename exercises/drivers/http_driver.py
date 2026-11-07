_HTTP_DRIVER = r'''
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


payload = json.loads(__PAYLOAD__)

report = {
    "fatal": None,
    "cases": [],
}

process = None
stdout_log = None
stderr_log = None


def _json_equal(actual, expected):
    """Compare JSON values without Python's bool/int equality ambiguity."""
    if type(actual) is not type(expected):
        return False

    if isinstance(actual, dict):
        return (
            actual.keys() == expected.keys()
            and all(
                _json_equal(actual[key], expected[key])
                for key in actual
            )
        )

    if isinstance(actual, list):
        return (
            len(actual) == len(expected)
            and all(
                _json_equal(a, b)
                for a, b in zip(actual, expected)
            )
        )

    return actual == expected


def _read_log(handle):
    if handle is None:
        return ""

    handle.flush()

    try:
        with open(handle.name, "r", encoding="utf-8", errors="replace") as log:
            return log.read()[-4000:]
    except OSError:
        return ""


def _stop_process():
    if process is None or process.poll() is not None:
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    except ProcessLookupError:
        pass


try:
    project_root = Path(
        tempfile.mkdtemp(prefix="forge_http_", dir="/tmp")
    ).resolve()

    for filename, source in payload["files"].items():
        relative_path = PurePosixPath(filename)

        if (
            relative_path.is_absolute()
            or "\\" in filename
            or ".." in relative_path.parts
        ):
            raise ValueError(f"Invalid project path: {filename!r}")

        destination = project_root.joinpath(*relative_path.parts)

        if not destination.resolve().is_relative_to(project_root):
            raise ValueError(f"Project path escapes root: {filename!r}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")

    execution = payload["execution"]
    host = execution["host"]
    port = execution["port"]

    base_url = f"http://{host}:{port}"

    suite_deadline = time.monotonic() + payload["suite_timeout"]

    stdout_log = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir="/tmp",
    )
    stderr_log = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir="/tmp",
    )

    process = subprocess.Popen(
        execution["command"],
        cwd=project_root,
        stdout=stdout_log,
        stderr=stderr_log,
        start_new_session=True,
    )

    readiness_deadline = min(
        suite_deadline,
        time.monotonic() + 5,
    )

    ready = False

    while time.monotonic() < readiness_deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Application exited during startup.\n"
                + _read_log(stderr_log)
            )

        try:
            with socket.create_connection(
                (host, port),
                timeout=0.2,
            ):
                ready = True
                break
        except OSError:
            time.sleep(0.05)

    if not ready:
        raise RuntimeError(
            "Application did not become reachable before the startup deadline.\n"
            + _read_log(stderr_log)
        )

    for case in payload["cases"]:
        remaining = suite_deadline - time.monotonic()

        if remaining <= 0:
            report["fatal"] = "HTTP evaluation suite timed out."
            break

        if process.poll() is not None:
            report["fatal"] = (
                "Application process exited during evaluation.\n"
                + _read_log(stderr_log)
            )
            break

        url = base_url + case["path"]

        body = None
        if case["json_body_present"]:
            body = json.dumps(case["json_body"]).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=body,
            headers=case["headers"],
            method=case["method"],
        )

        try:
            try:
                response = urllib.request.urlopen(
                    request,
                    timeout=remaining,
                )
            except urllib.error.HTTPError as exc:
                response = exc

            with response:
                status_code = response.status
                response_bytes = response.read()

            response_text = response_bytes.decode(
                "utf-8",
                errors="replace",
            )

        except Exception as exc:
            report["cases"].append({
                "label": case["label"],
                "passed": False,
                "status_code": None,
                "response_text": None,
                "response_json": None,
                "response_is_json": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

            report["fatal"] = (
                "HTTP request failed; the remaining suite cannot continue."
            )
            break

        response_is_json = False
        response_json = None

        try:
            response_json = json.loads(response_text)
            response_is_json = True
        except (ValueError, TypeError):
            pass

        failures = []

        if status_code != case["expected_status"]:
            failures.append(
                f"Expected status {case['expected_status']}, "
                f"received {status_code}."
            )

        if case["expected_json_present"]:
            if not response_is_json:
                failures.append("Response body is not valid JSON.")
            elif not _json_equal(
                response_json,
                case["expected_json"],
            ):
                failures.append("Response JSON did not match expected JSON.")

        if case["expected_text"] is not None:
            if response_text != case["expected_text"]:
                failures.append("Response text did not match expected text.")

        report["cases"].append({
            "label": case["label"],
            "passed": not failures,
            "status_code": status_code,
            "response_text": response_text,
            "response_json": response_json,
            "response_is_json": response_is_json,
            "error": "; ".join(failures) if failures else None,
        })

except Exception as exc:
    report["fatal"] = f"{type(exc).__name__}: {exc}"

finally:
    _stop_process()

    if stdout_log is not None:
        stdout_log.close()

    if stderr_log is not None:
        stderr_log.close()

    sys.stdout.write(
        "\n" + "__MARKER__" + json.dumps(report) + "\n"
    )
'''