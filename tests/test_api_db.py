import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from api.storage.db import init_db, make_engine, make_session_factory, session_scope
from api.storage.models import Draft, StepState


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    return make_session_factory(engine)


def test_init_creates_tables_and_is_repeatable(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    init_db(engine)   # running it twice must be harmless
    assert {"step_state", "attempts", "drafts"} <= set(inspect(engine).get_table_names())


def test_new_step_state_has_sensible_defaults(factory):
    with session_scope(factory) as s:
        s.add(StepState(course_id="c", step_id="m1-s1"))
    with session_scope(factory) as s:
        row = s.get(StepState, ("c", "m1-s1"))
        assert (row.generation, row.status, row.hints_revealed, row.failed_submits) == (1, "open", 0, 0)
        assert row.updated_at is not None


def test_error_inside_session_scope_rolls_back(factory):
    with pytest.raises(RuntimeError):
        with session_scope(factory) as s:
            s.add(Draft(course_id="c", step_id="s1", files_json="{}"))
            s.flush()
            raise RuntimeError("boom")
    with session_scope(factory) as s:
        assert s.scalars(select(Draft)).all() == []


def test_status_values_are_constrained(factory):
    with pytest.raises(IntegrityError):
        with session_scope(factory) as s:
            s.add(StepState(course_id="c", step_id="s1", status="banana"))

def test_job_defaults_and_status_constraint(factory):
    from api.storage.models import Job
    with session_scope(factory) as s:
        s.add(Job(id="j1", course_id="c", kind="module", module_index=0))
    with session_scope(factory) as s:
        job = s.get(Job, "j1")
        assert (job.status, job.total_steps, job.done_steps, job.results_json, job.regenerate) == ("queued", 0, 0, "[]", False)
        assert job.step_id is None and job.current_stage is None and job.error is None
    with pytest.raises(IntegrityError):
        with session_scope(factory) as s:
            s.add(Job(id="j2", course_id="c", kind="step", status="paused"))