import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from lessons.generator import StepOutcome
from models.course import step_id
from models.lesson_generation_models import Lesson

SOURCE = Path("data/smoke_course_v2.json")


def lesson(sid, title):
    return Lesson.model_validate({"id": sid, "title": title, "summary": "s",
                                  "you_will_learn": ["a", "b", "c"],
                                  "blocks": [{"type": "text", "body": "hi"}],
                                  "docs": [], "exercise": None})


class FakeGenerator:
    def __init__(self, on_stage):
        self.on_stage = on_stage

    def generate_step(self, course, m, s, *, force=False):
        sid = step_id(m, s)
        self.on_stage(sid, "lesson")
        course.upsert_lesson(lesson(sid, ("NEW " if force else "GEN ") + sid))
        return StepOutcome(sid, "ready")


@pytest.fixture
def make_client(tmp_path):
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(SOURCE, courses / "demo.json")

    def build(start_worker):
        app = create_app(courses_dir=courses, db_url=f"sqlite:///{tmp_path / 'l.db'}",
                         make_generator=lambda key, course, on_stage: FakeGenerator(on_stage),
                         start_worker=start_worker)
        return TestClient(app, raise_server_exceptions=False)
    return build


def test_generate_module_queues_dedupes_and_the_worker_finishes_it(make_client):
    with make_client(start_worker=False) as client:
        first = client.post("/api/courses/demo/modules/0/generate")
        assert first.status_code == 202
        body = first.json()
        assert body["status"] == "queued" and body["kind"] == "module" and body["total_steps"] == 3
        assert client.post("/api/courses/demo/modules/0/generate").json()["id"] == body["id"]
        assert client.get(f"/api/jobs/{body['id']}").json()["status"] == "queued"
        assert [j["id"] for j in client.get("/api/courses/demo/jobs?active=true").json()] == [body["id"]]
        client.app.state.worker.run_next()
        done = client.get(f"/api/jobs/{body['id']}").json()
        assert done["status"] == "done" and done["done_steps"] == 3
        assert client.get("/api/courses/demo/jobs?active=true").json() == []
        assert client.get("/api/courses/demo/steps/m1-s2").json()["lesson"]["title"] == "GEN m1-s2"


def test_the_background_thread_picks_up_a_job_without_manual_help(make_client):
    with make_client(start_worker=True) as client:
        job_id = client.post("/api/courses/demo/modules/0/generate").json()["id"]
        deadline = time.time() + 10
        while time.time() < deadline and client.get(f"/api/jobs/{job_id}").json()["status"] != "done":
            time.sleep(0.05)
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"


def test_regenerate_needs_an_open_step_and_swaps_the_content(make_client):
    with make_client(start_worker=False) as client:
        locked = client.get("/api/courses/demo").json()["modules"][1]["steps"][0]["id"]
        assert client.post(f"/api/courses/demo/steps/{locked}/regenerate").status_code == 403
        r = client.post("/api/courses/demo/steps/m1-s2/regenerate")
        assert r.status_code == 202 and r.json()["kind"] == "step" and r.json()["regenerate"]
        client.app.state.worker.run_next()
        page = client.get("/api/courses/demo/steps/m1-s2").json()
        assert page["lesson"]["title"] == "NEW m1-s2"


def test_unknown_things_are_404(make_client):
    with make_client(start_worker=False) as client:
        assert client.post("/api/courses/demo/modules/99/generate").status_code == 404
        assert client.post("/api/courses/demo/modules/-1/generate").status_code == 404
        assert client.post("/api/courses/nope/modules/0/generate").status_code == 404
        assert client.post("/api/courses/demo/steps/m99-s9/regenerate").status_code == 404
        assert client.get("/api/jobs/doesnotexist").status_code == 404
        assert client.get("/api/courses/nope/jobs").status_code == 404