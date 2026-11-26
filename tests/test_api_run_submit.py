import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas.results import CaseResult, RunResult
from api.services.generation import progress as P
from api.services.course_store import CourseStore, module_step_ids
from exercises.case_runner import HarnessError
from models.lesson_generation_models import Lesson
from tests.test_api_step_page import make_exercise

SOURCE = Path("data/smoke_course_v2.json")
URL = "/api/courses/demo/steps/m1-s2"
CODE = {"files": {"main.py": "def add(a, b):\n    return a + b\n"}}


def run_result(status="passed", passed=3, total=3):
    cases = [CaseResult(label="c", passed=status == "passed", visible=True, inputs="add(1, 2)",
                        expected="3", got="3")]
    return RunResult(status=status, cases=cases, passed_count=passed, total=total)


class FakeGrader:
    def __init__(self, db_path):
        self.db_path = db_path
        self.calls = []
        self.next = run_result()
        self.boom = None

    def grade(self, exercise, files, *, visible_only):
        self.calls.append(visible_only)
        # Proof that no write lock is held while grading: a second connection can write.
        conn = sqlite3.connect(self.db_path, timeout=0.3)
        conn.execute("INSERT OR REPLACE INTO drafts VALUES ('probe', 'probe', '{}', datetime('now'))")
        conn.commit()
        conn.close()
        if self.boom:
            raise self.boom
        return self.next


class FakeRegistry:
    def __init__(self, grader):
        self.grader = grader

    def for_course(self, key, env):
        return self.grader

    def close(self):
        pass


@pytest.fixture
def client(tmp_path):
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(SOURCE, courses / "demo.json")
    store = CourseStore(courses)
    ids = module_step_ids(store.get("demo"))
    with store.edit("demo") as course:
        course.lessons["m1-s2"] = Lesson.model_validate({
            "id": "m1-s2", "title": "L", "summary": "s", "you_will_learn": ["a", "b", "c"],
            "blocks": [{"type": "text", "body": "hi"}], "docs": [], "exercise": make_exercise()})
    db = tmp_path / "l.db"
    grader = FakeGrader(db)
    app = create_app(courses_dir=courses, db_url=f"sqlite:///{db}", registry=FakeRegistry(grader))
    with TestClient(app, raise_server_exceptions=False) as c:
        c.grader, c.ids = grader, ids
        yield c


def page(client):
    return client.get(URL).json()


def test_run_grades_visible_cases_only_and_records_nothing_but_the_draft(client):
    r = client.post(f"{URL}/run", json=CODE)
    assert r.status_code == 200 and r.json()["status"] == "passed"
    assert client.grader.calls == [True]
    p = page(client)
    assert p["progress"]["attempts"] == 0 and p["progress"]["status"] == "open"
    assert "return a + b" in p["exercise"]["files"]["main.py"]


def test_submit_records_the_attempt_and_solves_the_step(client):
    r = client.post(f"{URL}/submit", json=CODE).json()
    assert (r["attempt_no"], r["solved"], r["status"]) == (1, True, "passed")
    assert client.grader.calls == [False]
    p = page(client)
    assert p["progress"]["status"] == "solved" and p["progress"]["solution_unlocked"]
    assert p["progress"]["last_attempt"]["passed_count"] == 3


def test_failed_and_error_submits_count_toward_giving_up(client):
    client.grader.next = run_result("failed", 1, 3)
    results = [client.post(f"{URL}/submit", json=CODE).json() for _ in range(P.GIVE_UP_AFTER - 1)]
    assert not any(r["give_up_available"] for r in results)
    client.grader.next = RunResult(status="error", message="boom", cases=[], passed_count=0, total=3)
    last = client.post(f"{URL}/submit", json=CODE).json()
    assert last["attempt_no"] == P.GIVE_UP_AFTER and last["give_up_available"]


def test_runner_down_returns_503_records_no_attempt_but_keeps_the_draft(client):
    client.grader.boom = HarnessError("docker down")
    assert client.post(f"{URL}/submit", json=CODE).status_code == 503
    p = page(client)
    assert p["progress"]["attempts"] == 0
    assert "return a + b" in p["exercise"]["files"]["main.py"]


def test_bad_files_and_locked_modules_never_reach_the_grader(client):
    assert client.post(f"{URL}/run", json={"files": {"../x.py": "1"}}).status_code == 422
    locked = client.ids[1][0]
    assert client.post(f"/api/courses/demo/steps/{locked}/submit", json=CODE).status_code == 403
    assert client.post("/api/courses/demo/steps/m1-s3/submit", json=CODE).status_code == 404
    assert client.grader.calls == []