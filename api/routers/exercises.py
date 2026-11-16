from fastapi import APIRouter

from api.deps import DbSession,Store,Registry
from api.errors.errors import Conflict,Invalid,Locked,NotFound
from api.schemas.exercise import FilesRequest,HintsResponse,SolutionResponse,StepStatus
from api.schemas.results import RunResult,SubmitResult
from api.services import progress as P
from api.services.access import require_open_step
from api.storage.models import StepState
from models.lesson_generation_models import Exercise
from models.course import Course

router=APIRouter(prefix="/api/courses/{course_key}/steps/{step_id}", tags=["exercise"])

def _load_exercise(course_key:str,step_id:str,store:Store,
                   session:DbSession) -> tuple[Course, Exercise]:
    "The course and the step's exercise, after the shared existence and module-lock checks."
    course = store.get(course_key)
    require_open_step(session, course_key, course, step_id)
    lesson = course.lessons.get(step_id)
    if lesson is None or lesson.exercise is None:
        raise NotFound("This step has no exercise.")
    return course, lesson.exercise


def _open_exercise(course_key:str,step_id:str,store:Store,session:DbSession) -> Exercise:
    return _load_exercise(course_key,step_id,store,session)[1]

@router.put('/draft',status_code=204)
def put_draft(course_key:str,step_id:str,body:FilesRequest,store:Store,session:DbSession) -> None:
    _open_exercise(course_key,step_id,store,session)
    try:
        P.save_draft(session,course_key,step_id,body.files)
    except ValueError as exc:
        raise Invalid(str(exc))

@router.post('/hints/next',response_model=HintsResponse)
def next_hint(course_key:str,step_id:str,store:Store,session:DbSession) -> HintsResponse:
    exercise= _open_exercise(course_key,step_id,store,session)
    revealed=P.reveal_next_hint(session,course_key,step_id,len(exercise.hints))
    return HintsResponse(hint_count=len(exercise.hints), hints=exercise.hints[:revealed])

@router.post("/complete", response_model=StepStatus)
def complete(course_key:str,step_id:str,store:Store,session:DbSession) -> StepStatus:
    "For lesson-only steps: Next marks the step done."
    course = store.get(course_key)
    require_open_step(session, course_key, course, step_id)
    lesson = course.lessons.get(step_id)
    if lesson is None:
        raise Conflict("The lesson is not ready yet.")
    if lesson.exercise is not None:
        raise Conflict("This step has an exercise to solve.")
    P.mark_completed(session, course_key, step_id, has_exercise=False)
    return StepStatus(status=P.get_state(session, course_key, step_id).status)

@router.post("/give-up", response_model=StepStatus)
def give_up(course_key: str, step_id: str, store: Store, session: DbSession) ->StepStatus:
    _open_exercise(course_key, step_id, store, session)
    if not P.give_up(session, course_key, step_id):
        raise Conflict("Giving up is not available yet.")
    return StepStatus(status="gave_up")


@router.get("/solution", response_model=SolutionResponse)
def get_solution(course_key: str, step_id: str, store: Store, session: DbSession) -> SolutionResponse:
    exercise = _open_exercise(course_key, step_id, store, session)
    state = session.get(StepState, (course_key, step_id))
    if state is None or not P.solution_unlocked(state):
        raise Locked("Solve the exercise or give up to see the solution.")
    if not exercise.reference_files:
        raise NotFound("No solution is stored for this exercise.")
    return SolutionResponse(files=exercise.reference_files)

def _save_draft_now(session:DbSession,course_key:str,step_id:str,files:dict[str, str]) -> None:
    """Save the learner's code and COMMIT"""
    try:
        P.save_draft(session, course_key, step_id, files)
    except ValueError as exc:
        raise Invalid(str(exc))
    session.commit()


@router.post("/run", response_model=RunResult)
def run_tests(course_key: str, step_id: str, body: FilesRequest,
              store: Store, session: DbSession, registry: Registry):
    "Run Tests: visible cases only. Nothing is recorded except the draft."
    course, exercise = _load_exercise(course_key, step_id, store, session)
    _save_draft_now(session, course_key, step_id, body.files)
    grader = registry.for_course(course_key, course.env)
    return grader.grade(exercise, body.files, visible_only=True)


@router.post("/submit", response_model=SubmitResult)
def submit(course_key: str, step_id: str, body: FilesRequest,
           store: Store, session: DbSession, registry: Registry):
    """Submit: all cases. Order: (1) save the draft and commit, (2) grade with no write lock
    held, (3) record the attempt. If the runner itself is down, nothing is recorded."""
    course, exercise = _load_exercise(course_key, step_id, store, session)
    _save_draft_now(session, course_key, step_id, body.files)
    grader = registry.for_course(course_key, course.env)
    result = grader.grade(exercise, body.files, visible_only=False)
    return P.record_submit(session, course_key, step_id, result)