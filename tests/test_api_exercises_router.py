import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas.results import RunResult
from api.services import progress as P
from api.services.course_store import CourseStore, module_step_ids
from api.storage.db import session_scope
from models.lesson_generation_models import Lesson
from tests.test_api_step_page import SECRET_SOLUTION, make_exercise

SOURCE = Path("data/smoke_course_v2.json")
FAIL = RunResult(status="failed", cases=[], passed_count=1, total=3)
BASE = "/api/courses/demo/steps"
GOOD = {"files": {"main.py": "def add(a, b):\n    return a + b\n"}}


def _lesson(sid, exercise):
    return Lesson.model_validate({"id": sid, "title": "L", "summary": "s",
                                  "you_will_learn": ["a", "b", "c"],
                                  "blocks": [{"type": "text", "body": "hi"}],
                                  "docs": [], "exercise": exercise})


@pytest.fixture
def client(tmp_path):
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(SOURCE, courses / "demo.json")
    store = CourseStore(courses)
    ids = module_step_ids(store.get("demo"))
    with store.edit("demo") as course:
        course.lessons[ids[0][1]] = _lesson(ids[0][1], make_exercise())     # m1-s2: exercise
        course.lessons[ids[0][2]] = _lesson(ids[0][2], None)                # m1-s3: lesson only
    app = create_app(courses_dir=courses, db_url=f"sqlite:///{tmp_path / 'l.db'}")
    with TestClient(app, raise_server_exceptions=False) as c:
        c.app_ = app
        c.ids = ids
        yield c


def fail_submits(client, n, sid="m1-s2"):
    with session_scope(client.app_.state.session_factory) as s:
        for _ in range(n):
            P.record_submit(s, "demo", sid, FAIL)


def test_draft_is_saved_validated_and_returned_on_the_page(client):
    assert client.put(f"{BASE}/m1-s2/draft", json=GOOD).status_code == 204
    files = client.get(f"{BASE}/m1-s2").json()["exercise"]["files"]
    assert "return a + b" in files["main.py"]
    assert client.put(f"{BASE}/m1-s2/draft", json={"files": {"../evil.py": "x"}}).status_code == 422


def test_hints_are_revealed_one_at_a_time_and_clamped(client):
    counts = [len(client.post(f"{BASE}/m1-s2/hints/next").json()["hints"]) for _ in range(3)]
    assert counts == [1, 2, 2]


def test_complete_only_works_for_lesson_only_steps(client):
    assert client.post(f"{BASE}/m1-s3/complete").json() == {"status": "completed"}
    assert client.post(f"{BASE}/m1-s2/complete").status_code == 409


def test_solution_is_locked_until_give_up_then_available(client):
    assert client.get(f"{BASE}/m1-s2/solution").status_code == 403
    assert client.post(f"{BASE}/m1-s2/give-up").status_code == 409
    fail_submits(client, P.GIVE_UP_AFTER)
    assert client.post(f"{BASE}/m1-s2/give-up").json() == {"status": "gave_up"}
    solution = client.get(f"{BASE}/m1-s2/solution")
    assert solution.status_code == 200 and solution.json()["files"]["main.py"] == SECRET_SOLUTION
    assert client.post(f"{BASE}/m1-s2/give-up").status_code == 409     # only once


def test_steps_without_an_exercise_and_locked_modules_are_refused(client):
    assert client.post(f"{BASE}/m1-s3/hints/next").status_code == 404
    assert client.get(f"{BASE}/m1-s3/solution").status_code == 404
    locked = client.ids[1][0]
    assert client.put(f"{BASE}/{locked}/draft", json=GOOD).status_code == 403
    assert client.post(f"{BASE}/{locked}/hints/next").status_code == 403