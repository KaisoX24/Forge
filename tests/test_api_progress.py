import pytest
from sqlalchemy import select

from api.schemas.results import RunResult
from api.services.generation import progress as P
from api.storage.db import init_db, make_engine, make_session_factory, session_scope
from api.storage.models import Attempt

PASS = RunResult(status="passed", cases=[], passed_count=5, total=5)
FAIL = RunResult(status="failed", cases=[], passed_count=2, total=5)
FILES = {"main.py": "x = 1\n"}


@pytest.fixture
def session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'learner.db'}")
    init_db(engine)
    with session_scope(make_session_factory(engine)) as s:
        yield s


def test_new_step_starts_open_and_not_done(session):
    state = P.get_state(session, "c", "m1-s1")
    assert (state.status, state.generation, P.is_done(state)) == ("open", 1, False)


def test_module_unlock_needs_every_previous_step_done(session):
    modules = [["m1-s1", "m1-s2"], ["m2-s1"]]
    assert P.module_unlocked(session, "c", modules, 0)
    assert not P.module_unlocked(session, "c", modules, 1)
    P.mark_completed(session, "c", "m1-s1")
    session.flush()
    assert not P.module_unlocked(session, "c", modules, 1)
    P.record_submit(session, "c", "m1-s2", PASS)
    session.flush()
    assert P.module_unlocked(session, "c", modules, 1)
    assert not P.module_unlocked(session, "other-course", modules, 1)


def test_given_up_step_counts_as_done_for_unlocking(session):
    for _ in range(P._GIVE_UP_AFTER):
        P.record_submit(session, "c", "m1-s1", FAIL)
    assert P.give_up(session, "c", "m1-s1")
    session.flush()
    assert P.module_unlocked(session, "c", [["m1-s1"], ["m2-s1"]], 1)


def test_failed_submits_count_and_give_up_becomes_available(session):
    for i in range(1, P._GIVE_UP_AFTER + 1):
        result = P.record_submit(session, "c", "s", FAIL)
        assert result.attempt_no == i and not result.solved
        assert result.give_up_available == (i == P._GIVE_UP_AFTER)


def test_error_results_count_as_failed_submits(session):
    err = RunResult(status="error", message="boom", cases=[], passed_count=0, total=5)
    P.record_submit(session, "c", "s", err)
    assert P.get_state(session, "c", "s").failed_submits == 1


def test_pass_solves_and_unlocks_solution(session):
    assert not P.solution_unlocked(P.get_state(session, "c", "s"))
    result = P.record_submit(session, "c", "s", PASS)
    assert result.solved and not result.give_up_available
    assert P.solution_unlocked(P.get_state(session, "c", "s"))


def test_give_up_is_refused_too_early_and_only_works_once(session):
    assert not P.give_up(session, "c", "s")
    for _ in range(P._GIVE_UP_AFTER):
        P.record_submit(session, "c", "s", FAIL)
    assert P.give_up(session, "c", "s")
    assert not P.give_up(session, "c", "s")
    assert P.solution_unlocked(P.get_state(session, "c", "s"))


def test_late_pass_after_giving_up_becomes_solved_late_failure_changes_nothing(session):
    for _ in range(P._GIVE_UP_AFTER):
        P.record_submit(session, "c", "s", FAIL)
    P.give_up(session, "c", "s")
    P.record_submit(session, "c", "s", FAIL)
    state = P.get_state(session, "c", "s")
    assert (state.status, state.failed_submits) == ("gave_up", P._GIVE_UP_AFTER)
    assert P.record_submit(session, "c", "s", PASS).solved
    assert P.get_state(session, "c", "s").status == "solved"


def test_solved_step_is_not_changed_by_later_failures(session):
    P.record_submit(session, "c", "s", PASS)
    P.record_submit(session, "c", "s", FAIL)
    state = P.get_state(session, "c", "s")
    assert (state.status, state.failed_submits) == ("solved", 0)


def test_hints_never_go_past_the_hint_count(session):
    assert [P.reveal_next_hint(session, "c", "s", 2) for _ in range(4)] == [1, 2, 2, 2]


def test_mark_completed_only_moves_an_open_step(session):
    P.mark_completed(session, "c", "intro")
    assert P.get_state(session, "c", "intro").status == "completed"
    P.record_submit(session, "c", "s", PASS)
    P.mark_completed(session, "c", "s")
    assert P.get_state(session, "c", "s").status == "solved"


def test_regenerate_resets_state_keeps_history_and_restarts_numbering(session):
    for _ in range(3):
        P.record_submit(session, "c", "s", FAIL)
    P.reveal_next_hint(session, "c", "s", 2)
    P.save_draft(session, "c", "s", FILES)
    assert P.regenerate_step(session, "c", "s") == 2
    state = P.get_state(session, "c", "s")
    assert (state.generation, state.status, state.hints_revealed, state.failed_submits) == (2, "open", 0, 0)
    assert P.load_draft(session, "c", "s") is None
    assert P.record_submit(session, "c", "s", FAIL).attempt_no == 1
    session.flush()
    kept = session.scalars(select(Attempt).where(Attempt.step_id == "s")).all()
    assert sorted((a.generation, a.attempt_no) for a in kept) == [(1, 1), (1, 2), (1, 3), (2, 1)]


def test_draft_round_trip_and_overwrite(session):
    assert P.load_draft(session, "c", "s") is None
    P.save_draft(session, "c", "s", FILES)
    P.save_draft(session, "c", "s", {"main.py": "x = 2\n"})
    assert P.load_draft(session, "c", "s") == {"main.py": "x = 2\n"}


def test_draft_rejects_unsafe_paths_and_oversized_code(session, monkeypatch):
    with pytest.raises(ValueError):
        P.save_draft(session, "c", "s", {"../evil.py": "x"})
    monkeypatch.setattr(P, "MAX_DRAFT_BYTES", 50)
    with pytest.raises(ValueError):
        P.save_draft(session, "c", "s", {"main.py": "x = 1\n" * 50})
    assert P.load_draft(session, "c", "s") is None