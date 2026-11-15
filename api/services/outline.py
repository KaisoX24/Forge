from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.course import CourseSummary,CourseOutline,ModuleSummary,StepSummary
from api.services.course_store import module_step_ids
from api.services.progress import DONE_STATUSES,module_unlocked
from api.storage.models import StepState
from models.course import Course

def _statuses(session:Session,key:str) -> dict[str,str]:
    rows=session.execute(
        select(StepState.step_id,StepState.status).where(StepState.course_id==key)
    )
    return {step_id:status for step_id,status in rows}

def _percent(course:Course,statuses:dict[str,str]) -> int:
    total=len(course.step_ids)
    done=sum(statuses.get(sid) in DONE_STATUSES for sid in course.step_ids)
    return round(100*done/total) if total else 0

def build_summary(session:Session,key:str,course:Course) -> CourseSummary:
    return CourseSummary(
        key=key,
        title=course.title,
        framework=course.framework,
        progress_percent=_percent(course,_statuses(session,key))
    )

def build_outline(session:Session,key:str,course:Course) -> CourseOutline:
    statuses=_statuses(session,key)
    step_ids=module_step_ids(course)
    modules=[]
    for m,module in enumerate(course.curriculum.modules):
        steps=[]
        for plan,sid in zip(module.steps,step_ids[m]):
            lesson_status=course.status_of(sid)
            lesson=course.lessons.get(sid)
            steps.append(
                StepSummary(
                    id=sid,
                    title=lesson.title if lesson else plan.objective,
                    lesson=lesson_status,
                    has_exercise=lesson.exercise is not None if lesson else plan.graded,
                    progress=statuses.get(sid, "open")
                )
            )
        modules.append(
            ModuleSummary(
                index=m,title=module.title,steps=steps,
                unlocked=module_unlocked(session, key, step_ids, m)
            )
        )
    return CourseOutline(
        key=key,title=course.title,framework=course.framework,
        progress_percent=_percent(course,statuses),modules=modules
    )