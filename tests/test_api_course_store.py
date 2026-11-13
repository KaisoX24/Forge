import shutil
import threading
from pathlib import Path

import pytest

from api.services.course_store import CourseNotFound, CourseStore, find_step, module_step_ids

SOURCE = Path("data/course_v3.json")


@pytest.fixture
def store(tmp_path):
    shutil.copy(SOURCE, tmp_path / "demo.json")
    return CourseStore(tmp_path)


def test_keys_and_get(store):
    assert store.keys() == ["demo"]
    assert store.get("demo").title


def test_unknown_or_unsafe_keys_are_not_found(store):
    for key in ["nope", "../demo", "demo/../x", "", "a b"]:
        with pytest.raises(CourseNotFound):
            store.get(key)


def test_module_step_ids_and_find_step(store):
    course = store.get("demo")
    modules = module_step_ids(course)
    assert modules[0][0] == "m1-s1" and sum(map(len, modules)) == len(course.step_ids)
    m, s, plan = find_step(course, modules[1][0])
    assert (m, s) == (1, 0) and plan.objective
    with pytest.raises(KeyError):
        find_step(course, "m99-s1")


def test_edit_saves_on_success_and_not_on_error(store):
    with store.edit("demo") as course:
        course.title = "Renamed"
    assert store.get("demo").title == "Renamed"
    with pytest.raises(RuntimeError):
        with store.edit("demo") as course:
            course.title = "Never saved"
            raise RuntimeError("boom")
    assert store.get("demo").title == "Renamed"


def test_concurrent_edits_do_not_lose_updates(store):
    def bump():
        for _ in range(10):
            with store.edit("demo") as course:
                course.schema_version += 1
    start = store.get("demo").schema_version
    threads = [threading.Thread(target=bump) for _ in range(4)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert store.get("demo").schema_version == start + 40