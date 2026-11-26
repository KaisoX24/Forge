import shutil
from pathlib import Path

import pytest

from api.services.generation import progress as P
from api.services.course_store import CourseStore, module_step_ids
from api.services.generation.outline import build_outline, build_summary
from api.storage.db import init_db, make_engine, make_session_factory, session_scope
from models.lesson_generation_models import Lesson

SOURCE = Path("data/course_v3.json")


@pytest.fixture
def course(tmp_path):
    shutil.copy(SOURCE, tmp_path / "demo.json")
    return CourseStore(tmp_path).get("demo")


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    with session_scope(make_session_factory(engine)) as s:
        yield s


def test_fresh_outline_unlocks_only_the_first_module(course, session):
    outline = build_outline(session, "demo", course)
    assert outline.progress_percent == 0
    assert [m.unlocked for m in outline.modules] == [True] + [False] * (len(outline.modules) - 1)
    assert all(step.progress == "open" for m in outline.modules for step in m.steps)
    assert len(outline.modules) == len(course.curriculum.modules)


def test_steps_without_a_lesson_show_their_objective(course, session):
    step = build_outline(session, "demo", course).modules[0].steps[1]
    assert step.lesson == "pending" and step.title == course.curriculum.modules[0].steps[1].objective


def test_finishing_a_module_unlocks_the_next_and_moves_progress(course, session):
    ids = module_step_ids(course)
    for sid in ids[0]:
        P.mark_completed(session, "demo", sid)
    session.flush()
    outline = build_outline(session, "demo", course)
    assert [m.unlocked for m in outline.modules][:3] == [True, True, False]
    assert outline.progress_percent == round(100 * len(ids[0]) / len(course.step_ids))
    assert build_summary(session, "demo", course).progress_percent == outline.progress_percent


def test_a_ready_lesson_supplies_its_own_title(course, session):
    sid = module_step_ids(course)[0][1]
    course.lessons[sid] = Lesson.model_validate({
        "id": sid, "title": "Hello lesson", "summary": "s", "you_will_learn": ["a", "b", "c"],
        "blocks": [{"type": "text", "body": "hi"}], "docs": [], "exercise": None})
    step = build_outline(session, "demo", course).modules[0].steps[1]
    assert (step.lesson, step.title, step.has_exercise) == ("ready", "Hello lesson", False)


def test_progress_of_another_course_key_does_not_leak(course, session):
    for sid in module_step_ids(course)[0]:
        P.mark_completed(session, "other", sid)
    session.flush()
    assert build_outline(session, "demo", course).progress_percent == 0