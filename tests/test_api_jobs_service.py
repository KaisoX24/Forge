import pytest

from api.services.jobs import JobService
from api.storage.db import init_db, make_engine, make_session_factory


@pytest.fixture
def jobs(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    return JobService(make_session_factory(engine))


def test_enqueue_module_creates_a_queued_job(jobs):
    job = jobs.enqueue_module("demo", 1, total_steps=4)
    assert (job.kind, job.status, job.module_index, job.total_steps, job.done_steps) == ("module", "queued", 1, 4, 0)
    assert job.results == [] and job.regenerate is False
    assert jobs.get(job.id).id == job.id


def test_the_same_active_target_returns_the_existing_job(jobs):
    first = jobs.enqueue_module("demo", 1, 4)
    assert jobs.enqueue_module("demo", 1, 4).id == first.id
    assert jobs.enqueue_module("demo", 2, 4).id != first.id          # other module
    assert jobs.enqueue_module("other", 1, 4).id != first.id         # other course
    step = jobs.enqueue_step("demo", "m1-s2")
    assert step.kind == "step" and step.regenerate and step.total_steps == 1
    assert jobs.enqueue_step("demo", "m1-s2").id == step.id
    assert jobs.enqueue_step("demo", "m1-s3").id != step.id


def test_claim_is_first_in_first_out_and_marks_running(jobs):
    a = jobs.enqueue_module("demo", 0, 3)
    b = jobs.enqueue_module("demo", 1, 3)
    assert jobs.claim_next().id == a.id and jobs.get(a.id).status == "running"
    assert jobs.claim_next().id == b.id
    assert jobs.claim_next() is None


def test_progress_and_results_are_visible_through_get(jobs):
    job = jobs.enqueue_module("demo", 0, 2)
    jobs.claim_next()
    jobs.set_progress(job.id, "m1-s1", "starter")
    view = jobs.get(job.id)
    assert (view.current_step, view.current_stage) == ("m1-s1", "starter")
    jobs.finish_step(job.id, "m1-s1", "ready")
    jobs.finish_step(job.id, "m1-s2", "exercise_failed", "starter never differed")
    view = jobs.get(job.id)
    assert view.done_steps == 2 and view.current_step is None and view.current_stage is None
    assert [(r.step_id, r.status) for r in view.results] == [("m1-s1", "ready"), ("m1-s2", "exercise_failed")]
    assert view.results[1].reason == "starter never differed"
    jobs.complete(job.id)
    assert jobs.get(job.id).status == "done"


def test_failed_job_keeps_a_trimmed_error_and_a_finished_job_no_longer_blocks_enqueue(jobs):
    job = jobs.enqueue_module("demo", 0, 2)
    jobs.claim_next()
    jobs.fail(job.id, "x" * 2000)
    done = jobs.get(job.id)
    assert done.status == "failed" and len(done.error) == 500
    assert jobs.enqueue_module("demo", 0, 2).id != job.id            # a new job is allowed


def test_list_for_course_and_active_filter(jobs):
    a = jobs.enqueue_module("demo", 0, 2)
    jobs.enqueue_module("demo", 1, 2)
    jobs.enqueue_module("other", 0, 2)
    jobs.claim_next()
    jobs.complete(a.id)
    assert len(jobs.list_for_course("demo")) == 2
    assert [j.module_index for j in jobs.list_for_course("demo", active_only=True)] == [1]


def test_recover_interrupted_fails_running_jobs_and_leaves_queued_ones(jobs):
    running = jobs.enqueue_module("demo", 0, 2)
    queued = jobs.enqueue_module("demo", 1, 2)
    jobs.claim_next()
    jobs.set_progress(running.id, "m1-s1", "lesson")
    assert jobs.recover_interrupted() == 1
    view = jobs.get(running.id)
    assert view.status == "failed" and view.error == "Interrupted by a restart." and view.current_step is None
    assert jobs.get(queued.id).status == "queued"
    assert jobs.recover_interrupted() == 0