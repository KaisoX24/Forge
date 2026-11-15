import logging

from fastapi import APIRouter

from api.deps import DbSession,Store
from api.schemas.course import CourseOutline,CourseSummary
from api.schemas.step import StepPage
from api.services.access import require_open_step
from api.services.outline import build_outline,build_summary
from api.services.step_page import build_step_page

router = APIRouter(prefix="/api/courses", tags=["courses"])
log = logging.getLogger(__name__)

@router.get("",response_model=list[CourseSummary])
def list_courses(store:Store,session:DbSession):
    summaries=[]
    for key in store.keys():
        try:
            summaries.append(build_summary(session,key,store.get(key)))
        except Exception:
            log.exception("Skipping course %r: could not be loaded", key)
    return summaries

@router.get("/{course_key}",response_model=CourseOutline)
def get_outline(course_key:str,store:Store,session:DbSession):
    return build_outline(session, course_key, store.get(course_key))

@router.get("/{course_key}/steps/{step_id}", response_model=StepPage)
def get_step(course_key: str, step_id: str, store: Store, session: DbSession):
    course = store.get(course_key)
    require_open_step(session, course_key, course, step_id)
    return build_step_page(session, course_key, course, step_id)