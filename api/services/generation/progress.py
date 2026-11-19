from sqlalchemy import func,select
from sqlalchemy.orm import Session
import json
from api.storage.models import StepState,Attempt,Draft,CourseProgress
from api.schemas.results import RunResult,SubmitResult
from models.lesson_generation_models import _validate_project_files

DONE_STATUSES=("solved", "gave_up", "completed")

_GIVE_UP_AFTER=5

MAX_DRAFT_BYTES=200_000


# Read State
def get_state(session:Session,course_id:str,step_id:str)->StepState:
    "The learner's state for a step"
    state=session.get(StepState,(course_id,step_id))
    if state is None:
        state=StepState(
            course_id=course_id,
            step_id=step_id
        )
        session.add(state)
        session.flush()
    return state

def is_done(state:StepState):
    return state.status in DONE_STATUSES

def _previous_done(session:Session,course_id:str,modules:list[list[str]],
                   module_index:int) -> bool:
    "True when every step of the module before this one is done right now."
    prev = modules[module_index - 1]
    done = session.scalar(
        select(func.count()).select_from(StepState).where(
            StepState.course_id == course_id,
            StepState.step_id.in_(prev),
            StepState.status.in_(DONE_STATUSES),
        )
    )
    return done == len(prev)

def unlock_mark(session:Session,course_id:str,modules:list[list[str]])->int:
    """The furthest module index the learner has earned. It only ever goes up, so
    regenerating an earlier step can never take an unlocked module away."""

    row=session.get(CourseProgress,course_id)
    reached=row.max_unlocked if row else 0
    for m in range(1,len(modules)):
        if _previous_done(session,course_id,modules,m):
            reached=max(reached,m)

    if row is None:
        session.add(CourseProgress(course_id=course_id, max_unlocked=reached))
    elif reached>row.max_unlocked:
        row.max_unlocked=reached
    return reached

def module_unlocked(session:Session,course_id:str,modules:list[list[str]],
                    module_index:int) ->bool:
    "A module is open once the module before it has been finished, and stays open."
    return module_index <= unlock_mark(session, course_id, modules)

# Write State

def solution_unlocked(state:StepState) ->bool:
    return state.status in ("solved", "gave_up")


def record_submit(session:Session,course_id:str,step_id:str,run:RunResult,
                  give_up_after:int=_GIVE_UP_AFTER) -> SubmitResult:
    """Store one Submit and update the step. The caller passes a result from a run
    of ALL cases. Only an open step changes; later submits are kept as history."""

    state=get_state(session,course_id,step_id)
    attempt_no=1+session.scalar(
        select(func.count()).select_from(Attempt).where(
            Attempt.course_id==course_id,
            Attempt.step_id==step_id,
            Attempt.generation==state.generation,
        )
    )
    session.add(Attempt(course_id=course_id, step_id=step_id, generation=state.generation,
                        attempt_no=attempt_no, status=run.status,
                        passed_count=run.passed_count, total=run.total))

    if run.status == "passed" and state.status in ("open", "gave_up"):
        state.status = "solved"
    elif state.status == "open":
        state.failed_submits += 1

    return SubmitResult(
        **run.model_dump(),
        attempt_no=attempt_no,
        solved=state.status=='solved',
        give_up_available=state.status=='open' and state.failed_submits>=give_up_after
    )

def reveal_next_hint(session:Session,course_id:str,step_id:str,hint_count:int) -> int:
    "Reveal one more hint Returns how many are revealed."
    state=get_state(session,course_id,step_id)
    state.hints_revealed=min(state.hints_revealed+1,hint_count)
    return state.hints_revealed

def give_up(session: Session, course_id: str, step_id: str,
            give_up_after: int = _GIVE_UP_AFTER) -> bool:
    "True if the step is now given up; False if not allowed yet (or not open)."
    state = get_state(session, course_id, step_id)
    if state.status != "open" or state.failed_submits < give_up_after:
        return False
    state.status = "gave_up"
    return True

def mark_completed(session:Session,course_id:str,step_id:str,*,has_exercise:bool) -> bool:
    """Finish a lesson-only step. A step with an exercise must be solved or given up
    instead, so this refuses it. True if the step is now completed."""
    if has_exercise:
        return False
    state=get_state(session,course_id,step_id)
    if state.status=="open":
        state.status="completed"
    return state.status=="completed"

def regenerate_step(session:Session,course_id:str,step_id:str) -> int:
    """The step's content was replaced: start the learner's state fresh and drop the draft.
    Old attempts stay as history under their own generation. Returns the new generation."""
    state=get_state(session,course_id,step_id)
    state.generation+=1
    state.status="open"
    state.hints_revealed=0
    state.failed_submits=0

    draft=session.get(Draft,(course_id,step_id))
    if draft is not None:
        session.delete(draft)
    return state.generation

def save_draft(session:Session,course_id:str,step_id:str,files:dict[str,str]) -> None:
    "Autosave the editor's files. Raises ValueError for unsafe paths or too much code."
    files=_validate_project_files(files)
    payload=json.dumps(files,ensure_ascii=False)
    if len(payload.encode("utf-8"))>MAX_DRAFT_BYTES:
        raise ValueError(f"Draft is larger than {MAX_DRAFT_BYTES // 1000} KB.")

    draft=session.get(Draft,(course_id,step_id))
    if draft is None:
        session.add(Draft(course_id=course_id,step_id=step_id,files_json=payload))
    else:
        draft.files_json=payload

def load_draft(session:Session,course_id:str,step_id:str) -> dict[str,str] | None:
    "The learner's saved files, or None if they never edited the starter."
    draft=session.get(Draft,(course_id,step_id))
    return None if draft is None else json.loads(draft.files_json)
