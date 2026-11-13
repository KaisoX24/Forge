import pytest
from docker.errors import DockerException
from fastapi import APIRouter
from fastapi.testclient import TestClient

from api.deps import DbSession, Store
from api.errors.errors import Conflict, Locked, NotFound, Unavailable
from api.main import create_app
from api.storage.models import Draft
from exercises.case_runner import HarnessError


@pytest.fixture
def app(tmp_path):
    (tmp_path / "courses").mkdir()
    app = create_app(courses_dir=tmp_path / "courses", db_url=f"sqlite:///{tmp_path / 'l.db'}")
    router = APIRouter()

    @router.get("/t/{kind}")
    def boom(kind: str, store: Store):
        raise {"nf": NotFound("no step"), "lock": Locked("locked"), "conflict": Conflict("early"),
               "down": Unavailable("down"), "harness": HarnessError("x"),
               "docker": DockerException("daemon off")}[kind] if kind != "course" else store.get("nope")

    @router.post("/t/save")
    def save(session: DbSession):
        session.add(Draft(course_id="c", step_id="s", files_json="{}"))

    @router.post("/t/save-then-fail")
    def save_then_fail(session: DbSession):
        session.add(Draft(course_id="c", step_id="s2", files_json="{}"))
        session.flush()
        raise Conflict("nope")

    @router.get("/d/drafts")
    def drafts(session: DbSession):
        return [d.step_id for d in session.query(Draft).all()]

    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:   # runs startup/shutdown
        yield c


def test_health_and_startup_created_the_database(client):
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("kind, status", [("nf", 404), ("lock", 403), ("conflict", 409),
                                          ("down", 503), ("harness", 503), ("docker", 503),
                                          ("course", 404)])
def test_errors_map_to_http_codes(client, kind, status):
    response = client.get(f"/t/{kind}")
    assert response.status_code == status and "detail" in response.json()


def test_infrastructure_errors_do_not_leak_details(client):
    assert "daemon off" not in client.get("/t/docker").text


def test_session_commits_on_success_and_rolls_back_on_error(client):
    assert client.post("/t/save").status_code == 200
    assert client.post("/t/save-then-fail").status_code == 409
    assert client.get("/d/drafts").json() == ["s"]


def test_cors_allows_the_vite_dev_server(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"