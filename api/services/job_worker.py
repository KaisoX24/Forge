import logging
import threading
from collections.abc import Callable

from docker.errors import DockerException
from sqlalchemy.orm import sessionmaker,Session

from api.schemas.job import JobView
from api.services import progress as P
from api.services.course_store import CourseStore,find_step
from api.services.jobs import JobService
from api.storage.db import session_scope
from exercises.case_runner import HarnessError
from lessons.generator import StepOutcome
from models.course import Course,step_id
from sandbox.image_builder import ImageBuildError

log=logging.getLogger(__name__)

GeneratorFactory = Callable[[str, Course, Callable[[str, str], None]], object]

class _KeepOld(Exception):
    "Raised inside a regeneration to abandon the new content without saving it."

def _describe(exc: Exception) -> str:
    if isinstance(exc, (HarnessError, DockerException, ImageBuildError)):
        return "The code runner is unavailable."
    return f"{type(exc).__name__}: {exc}"

class JobWorker:
    "Runs queued jobs one at a time on a single background thread."

    def __init__(self,*,jobs:JobService,store:CourseStore,
                 session_factory:sessionmaker[Session],make_generator:GeneratorFactory,
                 idle_seconds:float=2.0):

        self._jobs=jobs
        self._store=store
        self._session_factory=session_factory
        self._make_generator=make_generator
        self._idle=idle_seconds
        self._wake=threading.Event()
        self._stop=threading.Event()
        self._thread:threading.Thread | None = None


    def start(self) -> None:
        self._jobs.recover_interrupted()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        "A generation in progress can't be interrupted; if it outlives the timeout it is cut off."
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def notify(self) -> None:
        "Call after enqueueing so the worker doesn't wait out its idle sleep."
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self.run_next():
                self._wake.wait(self._idle)
                self._wake.clear()

    def run_next(self) -> bool:
        "Claim and run the oldest queued job. False if nothing was waiting."
        job = self._jobs.claim_next()
        if job is None:
            return False
        try:
            self._run_job(job)
            self._jobs.complete(job.id)
        except Exception as exc:
            log.exception("Job %s failed", job.id)
            self._jobs.fail(job.id, _describe(exc))
        return True

    def _run_job(self,job:JobView) -> None:
        course=self._store.get(job.course_key)
        generator=self._make_generator(
            job.course_key,course,lambda sid,stage:self._jobs.set_progress(job.id, sid, stage)
        )
        if job.kind=='module':
            for s in range(len(course.curriculum.modules[job.module_index].steps)):
                outcome = self._generate_and_save(job.course_key, generator, job.module_index, s)
                self._record(job, outcome)

        else:
            m, s, _ = find_step(course, job.step_id)
            if job.regenerate:
                self._record(job, self._regenerate(job.course_key, generator, m, s))
            else:
                self._record(job, self._generate_and_save(job.course_key, generator, m, s))

    def _record(self, job: JobView, outcome: StepOutcome) -> None:
        self._jobs.finish_step(job.id, outcome.step_id, outcome.status, outcome.reason)

    def _generate_and_save(self, key: str, generator, m: int, s: int) -> StepOutcome:
        "One step = one load-generate-save, so finished steps are readable straight away."
        with self._store.edit(key) as course:
            return generator.generate_step(course, m, s, force=False)

    def _regenerate(self, key: str, generator, m: int, s: int) -> StepOutcome:
        """The old content stays live until the new step is fully ready. If the new one is not
        ready nothing is saved; if it is, the learner's progress starts over (new generation)."""
        outcome = None
        try:
            with self._store.edit(key) as course:
                outcome = generator.generate_step(course, m, s, force=True)
                if outcome.status != "ready":
                    raise _KeepOld
        except _KeepOld:
            return outcome
        with session_scope(self._session_factory) as session:
            P.regenerate_step(session, key, step_id(m, s))
        return outcome