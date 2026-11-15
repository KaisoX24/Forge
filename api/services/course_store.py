import re
import threading
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from models.course import Course,step_id
from models.data_models import ObjectivePlan

_COURSE_KEY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

class CourseNotFound(KeyError):
    pass

class CourseStore:
    """Courses live as one JSON file each: <directory>/<course_key>.json.
    The file name is the key the API uses; Course.id inside is not consulted."""

    def __init__(self,directory:str|Path):
        self.directory=Path(directory)
        self._locks:defaultdict[str,threading.Lock]=defaultdict(threading.Lock)
        self._guard=threading.Lock()

    def _path(self,course_key:str) -> Path:
        if not _COURSE_KEY.match(course_key):
            raise CourseNotFound(course_key)
        return self.directory / f"{course_key}.json"

    def keys(self) ->list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json") if _COURSE_KEY.match(p.stem))

    def get(self,course_key:str) ->Course:
        path=self._path(course_key)
        if path.exists():
            return Course.load(path)
        raise CourseNotFound(course_key)

    @contextmanager
    def edit(self,course_key:str) -> Generator[Course,None,None]:
        "Read, change and save one course while holding its lock. Nothing is saved on error."
        with self._guard:
            lock=self._locks[course_key]

        with lock:
            course=self.get(course_key)
            yield course
            course.save(self._path(course_key))

def module_step_ids(course:Course) -> list[list[str]]:
    "Step ids per module, in course order (what module_unlocked needs)."
    return [[step_id(m, s) for s in range(len(module.steps))]
            for m, module in enumerate(course.curriculum.modules)]

def find_step(course: Course, sid: str) -> tuple[int, int, ObjectivePlan]:
    "(module index, step index, plan) for a step id."
    for m, module in enumerate(course.curriculum.modules):
        for s, plan in enumerate(module.steps):
            if step_id(m, s) == sid:
                return m, s, plan
    raise KeyError(sid)