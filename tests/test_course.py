import os
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
import json
from models.course import Course, step_id
from models.data_models import Curriculum, EnvironmentSpec, Module, ObjectivePlan
from models.lesson_generation_models import DocRef, Exercise, FunctionCase, FunctionExecutionConfig, Lesson, TextBlock


def plan(n: int) -> ObjectivePlan:
    return ObjectivePlan(objective=f"Learn thing number {n} well", requirements=[f"The docs explain thing {n} clearly"])


def make_course(**kw) -> Course:
    curriculum = Curriculum(modules=[
        Module(title="Basics", steps=[plan(1), plan(2)]),
        Module(title="Requests", steps=[plan(3), plan(4), plan(5)]),
    ])
    base = dict(id="c1", title="FastAPI", framework="fastapi",
                docs_as_of=datetime(2026, 10, 29, tzinfo=timezone.utc),
                env=EnvironmentSpec(packages={"fastapi[standard]": "0.115.0"}), curriculum=curriculum)
    return Course(**{**base, **kw})


def make_lesson(lid: str, *, expected=1, title="A lesson") -> Lesson:
    exercise = Exercise(
        title="Add numbers", description="Add two numbers", instructions=["Write add()", "Return the sum"],
        difficulty="easy", files={"main.py": "def add(a, b):\n    pass\n"},
        execution=FunctionExecutionConfig(function_name="add"),
        cases=[FunctionCase(label="basic", inputs=[1, 2], expected=expected)],
        hints=["Use +", "Return it"], explanation="Because.")
    return Lesson(id=lid, title=title, summary="s", you_will_learn=["a", "b", "c"],
                  blocks=[TextBlock(body="hello")],
                  docs=[DocRef(label="Docs", url="https://x", grounding="grounded", coverage=0.9)],
                  exercise=exercise)

def no_exercise(lid: str) -> Lesson:
    return make_lesson(lid).model_copy(update={"exercise": None})


# ids
def test_step_ids_follow_module_and_step_order():
    assert make_course().step_ids == ["m1-s1", "m1-s2", "m2-s1", "m2-s2", "m2-s3"]


def test_step_id_is_one_based():
    assert step_id(0, 0) == "m1-s1" and step_id(1, 2) == "m2-s3"


# add / update
def test_new_course_has_every_step_pending():
    c = make_course()
    assert c.lessons == {} and c.pending_ids == c.step_ids


def test_upsert_adds_a_lesson_and_shrinks_pending():
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s2"))
    assert "m1-s2" in c.lessons and "m1-s2" not in c.pending_ids and len(c.pending_ids) == 4


def test_upsert_replaces_an_existing_lesson_without_duplicating():
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s1", title="First draft"))
    c.upsert_lesson(make_lesson("m1-s1", title="Revised"))
    assert len(c.lessons) == 1 and c.lessons["m1-s1"].title == "Revised"


def test_upsert_rejects_an_id_that_is_not_a_step():
    c = make_course()
    with pytest.raises(ValueError, match="not a step"):
        c.upsert_lesson(make_lesson("m9-s9"))
    assert c.lessons == {}


def test_lessons_can_be_generated_out_of_order():
    c = make_course()
    c.upsert_lesson(make_lesson("m2-s3"))
    c.upsert_lesson(make_lesson("m1-s1"))
    assert c.pending_ids == ["m1-s2", "m2-s1", "m2-s2"]


# integrity on construction / load 
def test_constructor_rejects_a_lesson_under_an_unknown_step():
    with pytest.raises(ValidationError, match="not a step"):
        make_course(lessons={"m7-s1": make_lesson("m7-s1")})


def test_constructor_rejects_a_key_that_disagrees_with_the_lesson_id():
    with pytest.raises(ValidationError, match="says its id"):
        make_course(lessons={"m1-s1": make_lesson("m1-s2")})


# persistence 
def test_save_then_load_gives_an_equal_course(tmp_path):
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s1"))
    c.save(tmp_path / "course.json")
    assert Course.load(tmp_path / "course.json") == c


def test_env_survives_a_round_trip_with_the_same_identity(tmp_path):
    c = make_course()
    c.save(tmp_path / "course.json")
    assert Course.load(tmp_path / "course.json").env.env_id == c.env.env_id


def test_adding_a_lesson_later_updates_the_saved_file(tmp_path):
    path = tmp_path / "course.json"
    c = make_course(); c.save(path)
    c = Course.load(path)
    c.upsert_lesson(make_lesson("m2-s1")); c.save(path)
    assert list(Course.load(path).lessons) == ["m2-s1"]


def test_failed_save_leaves_the_previous_file_untouched(tmp_path, monkeypatch):
    path = tmp_path / "course.json"
    c = make_course(); c.save(path)
    before = path.read_text(encoding="utf-8")
    c.upsert_lesson(make_lesson("m1-s1"))

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        c.save(path)

    assert path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "course.json.tmp").exists()


def test_unserialisable_value_fails_loudly_and_keeps_the_old_file(tmp_path):
    path = tmp_path / "course.json"
    c = make_course(); c.save(path)
    before = path.read_text(encoding="utf-8")
    c.upsert_lesson(make_lesson("m1-s1", expected=object()))
    with pytest.raises(Exception):
        c.save(path)
    assert path.read_text(encoding="utf-8") == before


def test_tuple_expected_value_comes_back_as_a_list(tmp_path):
    "Documents WHY expected values must be JSON types: anything else changes on the way through."
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s1", expected=(1, 2)))
    c.save(tmp_path / "course.json")
    assert Course.load(tmp_path / "course.json").lessons["m1-s1"].exercise.cases[0].expected == [1, 2]

def test_failed_step_is_not_reported_as_pending():
    c = make_course()
    c.record_failure("m1-s1", "lesson", "model returned invalid JSON 3 times", attempts=3)
    assert "m1-s1" not in c.pending_ids and c.failed_ids == ["m1-s1"]
    assert c.status_of("m1-s1") == "failed"


def test_status_of_covers_all_three_states():
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s1"))
    c.record_failure("m1-s2", "lesson", "boom")
    assert [c.status_of(s) for s in ("m1-s1", "m1-s2", "m2-s1")] == ["ready", "failed", "pending"]


def test_status_of_rejects_an_unknown_step():
    with pytest.raises(ValueError):
        make_course().status_of("m9-s9")


def test_successful_regeneration_clears_a_lesson_failure():
    c = make_course()
    c.record_failure("m1-s1", "lesson", "boom")
    c.upsert_lesson(make_lesson("m1-s1"))
    assert c.failures == {} and c.status_of("m1-s1") == "ready"


def test_failed_regeneration_keeps_the_previous_good_lesson():
    c = make_course()
    c.upsert_lesson(make_lesson("m1-s1", title="Good one"))
    c.record_failure("m1-s1", "lesson", "regeneration crashed")
    assert c.lessons["m1-s1"].title == "Good one"
    assert c.failed_ids == ["m1-s1"]


def test_exercise_failure_keeps_the_lesson_text_and_flags_the_step():
    c = make_course()
    c.upsert_lesson(no_exercise("m1-s1"))
    c.record_failure("m1-s1", "exercise", "reference solution crashed on case 2", attempts=3)
    assert c.lessons["m1-s1"].exercise is None and c.status_of("m1-s1") == "failed"


def test_exercise_failure_is_cleared_only_once_an_exercise_exists():
    c = make_course()
    c.upsert_lesson(no_exercise("m1-s1"))
    c.record_failure("m1-s1", "exercise", "no good exercise")
    c.upsert_lesson(no_exercise("m1-s1"))
    assert "m1-s1" in c.failures
    c.upsert_lesson(make_lesson("m1-s1"))              
    assert c.failures == {}


def test_exercise_failure_requires_an_existing_lesson():
    with pytest.raises(ValueError, match="no lesson"):
        make_course().record_failure("m1-s1", "exercise", "x")


def test_failure_for_an_unknown_step_is_rejected():
    with pytest.raises(ValueError, match="not a step"):
        make_course().record_failure("m9-s9", "lesson", "x")


def test_a_new_failure_replaces_the_old_one_for_that_step():
    c = make_course()
    c.record_failure("m1-s1", "lesson", "first", attempts=1)
    c.record_failure("m1-s1", "lesson", "second", attempts=3)
    assert len(c.failures) == 1 and c.failures["m1-s1"].reason == "second" and c.failures["m1-s1"].attempts == 3


def test_long_error_messages_are_truncated_not_rejected():
    c = make_course()
    c.record_failure("m1-s1", "lesson", "x" * 5000)
    assert len(c.failures["m1-s1"].reason) == 500


def test_failed_ids_come_back_in_course_order():
    c = make_course()
    c.record_failure("m2-s2", "lesson", "a")
    c.record_failure("m1-s2", "lesson", "b")
    assert c.failed_ids == ["m1-s2", "m2-s2"]


def test_failures_survive_save_and_load(tmp_path):
    c = make_course()
    c.record_failure("m1-s1", "lesson", "boom", attempts=2)
    c.save(tmp_path / "course.json")
    back = Course.load(tmp_path / "course.json")
    assert back == c and back.failed_ids == ["m1-s1"]


def test_a_course_file_saved_before_failures_existed_still_loads(tmp_path):
    path = tmp_path / "course.json"
    make_course().save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("failures")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert Course.load(path).failures == {}


def test_loading_rejects_a_file_with_an_exercise_failure_but_no_lesson(tmp_path):
    path = tmp_path / "course.json"
    c = make_course(); c.save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["failures"] = {"m1-s1": {"stage": "exercise", "reason": "x", "attempts": 1,
                                  "failed_at": "2026-10-31T00:00:00+00:00"}}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="no lesson"):
        Course.load(path)