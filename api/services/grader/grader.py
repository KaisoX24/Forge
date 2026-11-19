from __future__ import annotations

from api.schemas.results import CaseResult,RunResult
from api.services.generation.render import clean_text,render_function_case,render_http_case
from exercises.verify import HttpRunner,Runner,_sandbox_http_runner,_sandbox_runner
from exercises.case_runner import HarnessError
from models.lesson_generation_models import (
    Exercise,
    FunctionExecutionConfig,
    _validate_project_files,
    FunctionCase,
    HttpCase
)
from models.data_models import ExecutionError

def _tail(text:str,lines:int=3,limit:int=400) -> str:
    "The last lines of the learner's own error"
    kept="\n".join(clean_text(text).strip().splitlines()[-lines:])
    return kept if len(kept) <= limit else kept[:limit] + "…"

def _result(rows:list[CaseResult]) ->RunResult:
    passed=sum(row.passed for row in rows)
    return RunResult(status="passed" if rows and passed == len(rows) else "failed",
                     cases=rows, passed_count=passed, total=len(rows))

def _error(total:int,message:str) -> RunResult:
    "No per-case results could be produced."
    return RunResult(status="error", message=message, cases=[], passed_count=0, total=total)

class Grader:
    def __init__(self,run_function:Runner,run_http:HttpRunner):
        self._run_function=run_function
        self._run_http=run_http

    @classmethod
    def from_pool(cls,pool) -> "Grader":
        return cls(_sandbox_runner(pool),_sandbox_http_runner(pool))

    def grade(self,exercise:Exercise,files:dict[str,str],*,
              visible_only:bool) -> RunResult:

        cases=[c for c in exercise.cases if c.visible] if visible_only else list(exercise.cases)
        try:
            files=_validate_project_files(files)
        except ValueError as exc:
            return _error(len(cases), f"Your files were rejected: {exc}")
        try:
            if isinstance(exercise.execution, FunctionExecutionConfig):
                return self._grade_function(exercise, files, cases)
            return self._grade_http(exercise, files, cases)
        except HarnessError as exc:
            if not exc.learner_fault:
                raise
            reason = ("Your code took too long to run. Check for an infinite loop."
                      if exc.error_type is ExecutionError.TIMEOUT else
                      "Your code stopped the test runner before it finished "
                      "(an exit() call, a crash, or code that runs at import time).")
            return _error(len(cases), reason)

    def _grade_function(self, exercise:Exercise, files:dict[str,str], cases:list[FunctionCase]) -> RunResult:
        ex = exercise.execution
        report = self._run_function(files, ex.entry_file, ex.function_name,
                                    [c.inputs for c in cases])
        if report.fatal:
            return _error(len(cases), f"Your code could not be loaded:\n{_tail(report.fatal)}")
        if len(report.cases) != len(cases):
            return _error(len(cases), "The runner returned an unexpected number of results.")
        return _result([render_function_case(c, o, ex.function_name)
                        for c, o in zip(cases, report.cases)])

    def _grade_http(self, exercise:Exercise, files:dict[str,str], cases:list[HttpCase]) -> RunResult:
        report = self._run_http(files, exercise.execution, cases)
        if report.fatal:
            return _error(len(cases), f"Your app could not be started or reached:\n{_tail(report.fatal)}")
        if [o.label for o in report.cases] != [c.label for c in cases]:
            return _error(len(cases), "The runner returned an unexpected number of results.")
        return _result([render_http_case(c, o) for c, o in zip(cases, report.cases)])