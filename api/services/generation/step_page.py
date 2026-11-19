from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.step import LastAttempt, PublicExercise, PublicLesson, StepPage, StepProgress
from api.services.course_store import find_step
from api.services.generation.progress import _GIVE_UP_AFTER, load_draft, solution_unlocked
from api.storage.models import Attempt, StepState
from models.course import Course


def build_step_page(session: Session, key: str, course: Course, sid: str) -> StepPage:
    module_index,step_index,plan=find_step(course,sid)
    state=session.get(StepState,(key,sid)) or StepState(
        course_id=key, step_id=sid, generation=1, status="open",
        hints_revealed=0, failed_submits=0
    )

    mine=(Attempt.course_id==key,Attempt.step_id==sid,
          Attempt.generation==state.generation)

    attempts = session.scalar(select(func.count()).select_from(Attempt).where(*mine))
    last = session.scalars(
        select(Attempt).where(*mine).order_by(Attempt.attempt_no.desc()).limit(1)).first()
    unlocked = solution_unlocked(state)

    lesson=course.lessons.get(sid)
    exercise=None
    if lesson is not None and lesson.exercise is not None:
        exercise=PublicExercise.from_exercise(
            lesson.exercise,hints_revealed=state.hints_revealed,solved=unlocked,
            files=load_draft(session,key,sid)
        )

    order=course.step_ids
    position=order.index(sid)
    return StepPage(
        course_key=key, step_id=sid, module_index=module_index, step_index=step_index,
        objective=plan.objective,
        lesson_status=course.status_of(sid),
        lesson=PublicLesson.from_lesson(lesson) if lesson else None,
        exercise=exercise,
        progress=StepProgress(
            status=state.status, hints_revealed=state.hints_revealed, attempts=attempts,
            last_attempt=None if last is None else LastAttempt(
                attempt_no=last.attempt_no, status=last.status,
                passed_count=last.passed_count, total=last.total),
            give_up_available=state.status == "open" and state.failed_submits >= _GIVE_UP_AFTER,
            solution_unlocked=unlocked),
        previous_step_id=order[position - 1] if position > 0 else None,
        next_step_id=order[position + 1] if position + 1 < len(order) else None,
    )
