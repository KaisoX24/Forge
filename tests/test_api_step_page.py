import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from api.schemas.results import RunResult
from api.services import progress as P
from api.services.course_store import CourseStore, module_step_ids
from api.services.step_page import build_step_page
from api.storage.db import init_db, make_engine, make_session_factory, session_scope
from api.storage.models import StepState
from models.lesson_generation_models import (
    Exercise, FunctionCase, FunctionExecutionConfig, Lesson)

SOURCE = Path("data/smoke_course_v2.json")
SECRET_SOLUTION = "def add(a, b): return SECRET_SOLUTION_MARKER"
HIDDEN_EXPECTED = "HIDDEN_EXPECTED_MARKER"
FAIL = RunResult(status="failed", cases=[], passed_count=1, total=3)
PASS = RunResult(status="passed", cases=[], passed_count=3, total=3)


def make_exercise() -> Exercise:
    cases = [FunctionCase(label="shown", inputs=[1, 2], expected=3, visible=True),
             FunctionCase(label="hidden one", inputs=[2, 2], expected=HIDDEN_EXPECTED, visible=False),
             FunctionCase(label="hidden two", inputs=[3, 3], expected=6, visible=False)]
    return Exercise(title="Add", description="Add two numbers.",
                    instructions=["Take two numbers.", "Return the sum."], difficulty="easy",
                    files={"main.py": "def add(a, b):\n    pass\n"},
                    execution=FunctionExecutionConfig(entry_file="main.py", function_name="add"),
                    cases=cases, hints=["hint one", "hint two"], explanation="EXPLANATION_MARKER",
                    reference_files={"main.py": SECRET_SOLUTION})


@pytest.fixture
def course(tmp_path):
    shutil.copy(SOURCE, tmp_path / "demo.json")
    course = CourseStore(tmp_path).get("demo")
    sid = module_step_ids(course)[0][1]
    course.lessons[sid] = Lesson.model_validate({
        "id": sid, "title": "A lesson", "summary": "s", "you_will_learn": ["a", "b", "c"],
        "blocks": [{"type": "text", "body": "hi"}], "docs": [], "exercise": make_exercise()})
    return course


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    with session_scope(make_session_factory(engine)) as s:
        yield s


def sid_of(course):
    return module_step_ids(course)[0][1]


def page(session, course):
    return build_step_page(session, "demo", course, sid_of(course))


def test_page_never_contains_the_solution_or_hidden_expected_values(session, course):
    for _ in range(P.GIVE_UP_AFTER - 1):
        P.record_submit(session, "demo", sid_of(course), FAIL)
    text = page(session, course).model_dump_json()
    for secret in (SECRET_SOLUTION, "SECRET_SOLUTION_MARKER", HIDDEN_EXPECTED, "hidden one",
                   "reference_files", "cases"):
        assert secret not in text


def test_explanation_and_extra_hints_stay_hidden_until_earned(session, course):
    p = page(session, course)
    assert p.exercise.explanation is None and p.exercise.hints == [] and p.exercise.hint_count == 2
    P.reveal_next_hint(session, "demo", sid_of(course), 2)
    session.flush()
    assert page(session, course).exercise.hints == ["hint one"]
    P.record_submit(session, "demo", sid_of(course), PASS)
    session.flush()
    p = page(session, course)
    assert p.exercise.explanation == "EXPLANATION_MARKER" and p.progress.solution_unlocked


def test_saved_draft_replaces_the_starter_files(session, course):
    assert page(session, course).exercise.files == {"main.py": "def add(a, b):\n    pass\n"}
    P.save_draft(session, "demo", sid_of(course), {"main.py": "def add(a, b):\n    return a + b\n"})
    session.flush()
    assert "return a + b" in page(session, course).exercise.files["main.py"]


def test_progress_reports_counts_and_give_up_availability(session, course):
    assert page(session, course).progress.last_attempt is None
    for _ in range(P.GIVE_UP_AFTER):
        P.record_submit(session, "demo", sid_of(course), FAIL)
    session.flush()
    progress = page(session, course).progress
    assert progress.attempts == P.GIVE_UP_AFTER and progress.give_up_available
    assert (progress.last_attempt.attempt_no, progress.last_attempt.passed_count) == (P.GIVE_UP_AFTER, 1)


def test_viewing_a_page_creates_no_rows_and_navigation_ids_are_correct(session, course):
    ids = module_step_ids(course)[0]
    p = page(session, course)
    assert (p.previous_step_id, p.next_step_id) == (ids[0], ids[2])
    first = build_step_page(session, "demo", course, ids[0])
    assert first.previous_step_id is None and first.next_step_id == ids[1]
    last = course.step_ids[-1]
    assert build_step_page(session, "demo", course, last).next_step_id is None
    assert session.scalar(select(func.count()).select_from(StepState)) == 0


def test_unknown_step_is_a_key_error(session, course):
    with pytest.raises(KeyError):
        build_step_page(session, "demo", course, "m99-s1")