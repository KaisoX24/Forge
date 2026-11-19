from sqlalchemy.orm import Session

from api.errors.errors import Locked, NotFound
from api.services.course_store import find_step, module_step_ids
from api.services.generation.progress import module_unlocked
from models.course import Course
from models.data_models import ObjectivePlan


def require_open_step(session: Session, key: str, course: Course,
                      sid: str) -> tuple[int, int, ObjectivePlan]:
    """The one gate every step route goes through: the step must exist and its module
    must be unlocked. Returns (module index, step index, plan)."""
    try:
        module_index, step_index, plan = find_step(course, sid)
    except KeyError:
        raise NotFound("Step not found.")
    if not module_unlocked(session, key, module_step_ids(course), module_index):
        raise Locked("Finish the previous module to open this one.")
    return module_index, step_index, plan