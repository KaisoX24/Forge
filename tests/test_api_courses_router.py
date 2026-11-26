import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services.course_store import CourseStore, module_step_ids
from models.lesson_generation_models import Lesson
from tests.test_api_step_page import SECRET_SOLUTION, HIDDEN_EXPECTED, make_exercise

SOURCE = Path("data/courses/fastapi.json")


@pytest.fixture
def client(tmp_path):
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(SOURCE, courses / "demo.json")
    store = CourseStore(courses)
    sid = module_step_ids(store.get("demo"))[0][1]
    with store.edit("demo") as course:
        course.lessons[sid] = Lesson.model_validate({
            "id": sid, "title": "A lesson", "summary": "s", "you_will_learn": ["a", "b", "c"],
            "blocks": [{"type": "text", "body": "hi"}], "docs": [], "exercise": make_exercise()})
    app = create_app(courses_dir=courses, db_url=f"sqlite:///{tmp_path / 'l.db'}")
    with TestClient(app, raise_server_exceptions=False) as c:
        c.app_ = app
        yield c


def test_list_and_outline(client):
    listing = client.get("/api/courses").json()
    assert [c["key"] for c in listing] == ["demo"] and listing[0]["progress_percent"] == 0
    outline = client.get("/api/courses/demo").json()
    assert outline["modules"][0]["unlocked"] and not outline["modules"][1]["unlocked"]


def test_a_broken_course_file_is_skipped_not_fatal(client, tmp_path):
    (tmp_path / "courses" / "broken.json").write_text("{not json")
    assert [c["key"] for c in client.get("/api/courses").json()] == ["demo"]


def test_step_page_over_http_hides_secrets(client):
    r = client.get("/api/courses/demo/steps/m1-s2")
    assert r.status_code == 200
    body = r.text
    assert r.json()["exercise"]["title"] == "Add"
    for secret in (SECRET_SOLUTION, "SECRET_SOLUTION_MARKER", HIDDEN_EXPECTED, "reference_files"):
        assert secret not in body


def test_api_contract_never_mentions_hidden_fields(client):
    spec = client.app_.openapi()
    contract = json.dumps(spec)
    for name in ("reference_files", "expected_json"):
        assert name not in contract
    # RunResult/SubmitResult legitimately have a `cases` list (per-case results, hidden ones blanked),
    # so check the exercise schema itself rather than the whole file.
    exercise = spec["components"]["schemas"]["PublicExercise"]["properties"]
    for name in ("cases", "execution", "evaluation", "reference_files"):
        assert name not in exercise


def test_locked_module_and_missing_things(client):
    outline = client.get("/api/courses/demo").json()
    locked_step = outline["modules"][1]["steps"][0]["id"]
    assert client.get(f"/api/courses/demo/steps/{locked_step}").status_code == 403
    assert client.get("/api/courses/demo/steps/m99-s9").status_code == 404
    assert client.get("/api/courses/nope").status_code == 404
    assert client.get("/api/courses/..%2Fdemo").status_code == 404