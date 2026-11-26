import shutil
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select

from api.schemas.results import RunResult
from api.services.generation import progress as P
from api.services.course_store import CourseStore
from api.services.job.job_worker import JobWorker
from api.services.job.jobs import JobService
from api.storage.db import init_db, make_engine, make_session_factory, session_scope
from api.storage.models import Attempt, StepState
from exercises.case_runner import HarnessError
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
    "Stands in for StepGenerator: writes a lesson, reports stages, returns scripted outcomes."

    def __init__(self, on_stage):
        self.on_stage = on_stage
        self.calls, self.status, self.raise_on, self.observe, self.seen = [], {}, {}, None, []
        self.active = self.peak = 0

    def generate_step(self, course, m, s, *, force=False):
        sid = step_id(m, s)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            self.calls.append((sid, force))
            self.on_stage(sid, "lesson")
            if self.observe:
                self.seen.append(self.observe())
            time.sleep(0.01)
            if sid in self.raise_on:
                raise self.raise_on[sid]
            status = self.status.get(sid, "ready")
            if status == "skipped":
                return StepOutcome(sid, "skipped")
            course.upsert_lesson(lesson(sid, ("NEW " if force else "GEN ") + sid))
            return StepOutcome(sid, status, None, None if status == "ready" else "boom")
        finally:
            self.active -= 1


@pytest.fixture
def env(tmp_path):
    courses = tmp_path / "courses"
    courses.mkdir()
    shutil.copy(SOURCE, courses / "demo.json")
    store = CourseStore(courses)
    engine = make_engine(f"sqlite:///{tmp_path / 'l.db'}")
    init_db(engine)
    factory = make_session_factory(engine)
    jobs = JobService(factory)
    made = []

    def make_generator(key, course, on_stage):
        gen = FakeGenerator(on_stage)
        gen.observe = lambda: jobs.list_for_course(key, active_only=True)[0]
        made.append(gen)
        return gen

    worker = JobWorker(jobs=jobs, store=store, session_factory=factory,
                       make_generator=make_generator, idle_seconds=0.05)
    return type("Env", (), dict(store=store, jobs=jobs, worker=worker, factory=factory, made=made))


def module_ids(env, m=0):
    course = env.store.get("demo")
    return [step_id(m, s) for s in range(len(course.curriculum.modules[m].steps))]


def test_module_job_generates_every_step_in_order_and_saves_each(env):
    ids = module_ids(env)
    job = env.jobs.enqueue_module("demo", 0, len(ids))
    assert env.worker.run_next() is True
    view = env.jobs.get(job.id)
    assert view.status == "done" and view.done_steps == len(ids) and view.current_step is None
    assert [r.step_id for r in view.results] == ids and all(r.status == "ready" for r in view.results)
    course = env.store.get("demo")
    assert all(course.lessons[sid].title == f"GEN {sid}" for sid in ids)
    assert [c[0] for c in env.made[0].calls] == ids and not any(c[1] for c in env.made[0].calls)


def test_stage_progress_is_visible_while_a_step_is_running(env):
    env.jobs.enqueue_module("demo", 0, 3)
    env.worker.run_next()
    first = env.made[0].seen[0]
    assert first.status == "running" and first.current_step == "m1-s1" and first.current_stage == "lesson"


def test_a_failed_step_is_recorded_and_the_job_carries_on(env):
    ids = module_ids(env)
    job = env.jobs.enqueue_module("demo", 0, len(ids))
    original = env.worker._make_generator

    def scripted(key, course, on_stage):
        gen = original(key, course, on_stage)
        gen.status = {ids[0]: "skipped", ids[1]: "exercise_failed"}
        return gen
    env.worker._make_generator = scripted
    env.worker.run_next()
    view = env.jobs.get(job.id)
    assert view.status == "done"
    assert [(r.step_id, r.status) for r in view.results][:3] == [
        (ids[0], "skipped"), (ids[1], "exercise_failed"), (ids[2], "ready")]
    assert view.results[1].reason == "boom"


def test_runner_down_fails_the_job_but_keeps_finished_steps(env):
    ids = module_ids(env)
    job = env.jobs.enqueue_module("demo", 0, len(ids))
    original = env.worker._make_generator

    def scripted(key, course, on_stage):
        gen = original(key, course, on_stage)
        gen.raise_on = {ids[1]: HarnessError("docker down")}
        return gen
    env.worker._make_generator = scripted
    env.worker.run_next()
    view = env.jobs.get(job.id)
    assert view.status == "failed" and view.error == "The code runner is unavailable."
    assert view.done_steps == 1
    course = env.store.get("demo")
    assert course.lessons[ids[0]].title == f"GEN {ids[0]}" and ids[1] not in course.lessons


def test_regeneration_success_swaps_content_and_resets_progress_but_keeps_history(env):
    sid = "m1-s2"
    with env.store.edit("demo") as course:
        course.upsert_lesson(lesson(sid, "OLD"))
    with session_scope(env.factory) as s:
        P.record_submit(s, "demo", sid, RunResult(status="failed", cases=[], passed_count=0, total=3))
    job = env.jobs.enqueue_step("demo", sid)
    env.worker.run_next()
    assert env.jobs.get(job.id).status == "done"
    assert env.store.get("demo").lessons[sid].title == "NEW m1-s2"
    assert env.made[0].calls == [(sid, True)]
    with session_scope(env.factory) as s:
        state = s.get(StepState, ("demo", sid))
        assert (state.generation, state.status, state.failed_submits) == (2, "open", 0)
        assert s.scalar(select(func.count()).select_from(Attempt)) == 1       # history kept


def test_failed_regeneration_changes_nothing(env):
    sid = "m1-s2"
    with env.store.edit("demo") as course:
        course.upsert_lesson(lesson(sid, "OLD"))
    original = env.worker._make_generator

    def scripted(key, course, on_stage):
        gen = original(key, course, on_stage)
        gen.status = {sid: "exercise_failed"}
        return gen
    env.worker._make_generator = scripted
    job = env.jobs.enqueue_step("demo", sid)
    env.worker.run_next()
    view = env.jobs.get(job.id)
    assert view.status == "done" and view.results[0].status == "exercise_failed"
    assert env.store.get("demo").lessons[sid].title == "OLD"
    with session_scope(env.factory) as s:
        assert s.get(StepState, ("demo", sid)) is None


def test_unknown_course_fails_the_job_and_an_empty_queue_returns_false(env):
    assert env.worker.run_next() is False
    job = env.jobs.enqueue_module("ghost", 0, 3)
    env.worker.run_next()
    assert env.jobs.get(job.id).status == "failed"


def test_the_thread_runs_jobs_one_at_a_time_in_order(env):
    first = env.jobs.enqueue_module("demo", 0, 3)
    second = env.jobs.enqueue_module("demo", 1, 3)
    env.worker.start()
    env.worker.notify()
    deadline = time.time() + 10
    while time.time() < deadline and not all(
            env.jobs.get(j.id).status == "done" for j in (first, second)):
        time.sleep(0.05)
    env.worker.stop()
    assert env.jobs.get(first.id).status == env.jobs.get(second.id).status == "done"
    assert max(g.peak for g in env.made) == 1
    assert env.made[0].calls[0][0].startswith("m1-") and env.made[1].calls[0][0].startswith("m2-")