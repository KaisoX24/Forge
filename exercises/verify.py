from __future__ import annotations

from typing import Callable
import logging

from exercises.case_runner import RunReport, grade, run_cases
from exercises.checks import check_starter_fails,reference_outputs,verify_reference_run
from exercises.starter import make_starter
from exercises.http_runner import run_http_cases
from models.data_models import EnvironmentSpec, ExecutionResult, HttpRunReport
from models.lesson_generation_models import (
    Exercise,
    ExerciseDraft,
    FunctionCase,
    FunctionEvaluationConfig,
    FunctionExecutionConfig,
    HttpExecutionConfig,
    HttpEvaluationConfig,
    HttpCase
)

logger=logging.getLogger(__name__)


Runner = Callable[[dict[str, str], str, str, list[list]],RunReport]
HttpRunner = Callable[[dict[str, str], HttpExecutionConfig, list],HttpRunReport]

RUN_TIMEOUT_SECONDS = 20
MIN_KEPT_CASES = 3

def _sandbox_runner(pool) -> Runner:
    from sandbox.sandbox import SandBox

    def runner(files: dict[str, str],entry_file: str,function_name: str,inputs: list[list]) -> RunReport:
        run_script = lambda code: SandBox(pool,code,timeout_seconds=RUN_TIMEOUT_SECONDS).sandbox_instance()

        return run_cases(
            run_script,
            files,
            entry_file,
            function_name,
            inputs,
        )

    return runner

def _sandbox_http_runner(pool) -> HttpRunner:
    from sandbox.sandbox import SandBox

    def runner(files, execution, cases) -> HttpRunReport:
        def run_script(code: str,timeout_seconds: int) -> ExecutionResult:
            return SandBox(pool,code,timeout_seconds=timeout_seconds).sandbox_instance()

        return run_http_cases(
            files,
            execution,
            cases,
            run_script=run_script,
        )

    return runner

def _prune_crashing_cases(run:Runner,draft:ExerciseDraft,labels:list[str],
                          inputs:list[list],first:RunReport) -> tuple[list[str], list[list], RunReport]:
    "Drop cases the reference crashes on, if enough good ones remain."
    if first.fatal or len(first.cases) != len(inputs):
        return labels,inputs,first

    keep=[i for i,outcome in enumerate(first.cases) if outcome.ok]
    if len(keep)==len(inputs) or len(keep) < MIN_KEPT_CASES:
        return labels,inputs,first

    logging.warning("Dropped cases the reference crashes on: %s",
                    [labels[i] for i in range(len(inputs)) if i not in keep])

    labels=[labels[i] for i in keep]
    inputs=[inputs[i] for i in keep]

    execution=draft.execution
    first=run(draft.reference_files,execution.entry_file,execution.function_name,inputs)
    return labels,inputs,first


def _verify_function(draft: ExerciseDraft,run: Runner,packages: list[str],visible_cases: int) -> Exercise:

    execution = draft.execution
    evaluation = draft.evaluation

    if not isinstance(execution, FunctionExecutionConfig):
        raise TypeError(
            "Function verification requires function execution config."
        )

    if not isinstance(evaluation, FunctionEvaluationConfig):
        raise TypeError(
            "Function verification requires function evaluation config."
        )

    entry_file = execution.entry_file
    function_name = execution.function_name

    labels = [case.label for case in evaluation.cases]
    inputs = [case.inputs for case in evaluation.cases]

    starter_files = make_starter(
        draft.reference_files,
        draft.files,
        entry_file=entry_file,
        function_name=function_name,
    )

    first = run(draft.reference_files,entry_file,function_name,inputs)

    labels,inputs,first=_prune_crashing_cases(run,draft,labels,inputs,first)

    reference_outputs(first, labels, inputs, packages)

    second = run(draft.reference_files,entry_file,function_name,inputs)

    expected = verify_reference_run(
        first,
        labels,
        inputs,
        second_report=second,
        available_packages=packages,
    )

    starter_report = run(starter_files,entry_file,function_name,inputs)

    graded = grade(starter_report, expected)

    if starter_report.fatal:
        check_starter_fails(graded)

    if len(starter_report.cases) != len(expected):
        raise ValueError(
            "The starter runner returned an unexpected number of results: "
            f"{len(starter_report.cases)} for {len(expected)} cases."
        )

    check_starter_fails(graded)

    cases = [
        FunctionCase(
            label=label,
            inputs=args,
            expected=want,
            visible=index < visible_cases,
        )
        for index, (label, args, want) in enumerate(
            zip(labels, inputs, expected)
        )
    ]

    return Exercise.from_draft(
        draft,
        cases=cases,
    )


def _verify_http(
    draft: ExerciseDraft,
    run: HttpRunner,
    visible_cases: int,
) -> Exercise:
    execution = draft.execution
    evaluation = draft.evaluation

    if not isinstance(execution, HttpExecutionConfig):
        raise TypeError(
            "HTTP verification requires HTTP execution config."
        )

    if not isinstance(evaluation, HttpEvaluationConfig):
        raise TypeError(
            "HTTP verification requires HTTP evaluation config."
        )

    reference = run(
        draft.reference_files,
        execution,
        evaluation.cases,
    )

    if reference.fatal:
        raise ValueError(
            "The reference application could not be evaluated: "
            f"{reference.fatal}"
        )

    expected_labels = [case.label for case in evaluation.cases]
    actual_labels = [outcome.label for outcome in reference.cases]

    if len(reference.cases) != len(evaluation.cases):
            raise ValueError(
                "The HTTP runner returned an unexpected number of reference results: "
                f"{len(reference.cases)} for {len(evaluation.cases)} cases."
            )

    if actual_labels != expected_labels:
        raise ValueError("HTTP runner returned results in an unexpected order.")

    failures = [
        f"- {outcome.label!r}: "
        f"{outcome.error or 'response did not match expectations'}"
        + (f" Actual response: {outcome.response_text[:300]}"
        if outcome.response_text else "")
        for outcome in reference.cases
        if not outcome.passed
    ]

    if failures:
        failed = {o.label for o in reference.cases if not o.passed}
        good = [c for c in evaluation.cases if c.label not in failed]
        if len(good) < MIN_KEPT_CASES:
            raise ValueError(
                "The reference application failed its own HTTP cases:\n"
                + "\n".join(failures)
            )
        logger.warning("Dropped cases the reference fails: %s", sorted(failed))
        evaluation = evaluation.model_copy(update={"cases": good})
        draft = draft.model_copy(update={"evaluation": evaluation})
        expected_labels = [c.label for c in good]

    starter = run(
        draft.files,
        execution,
        evaluation.cases,
    )

    if starter.fatal:
        raise ValueError(
            "The starter application could not be evaluated. Starter projects "
            "must launch successfully before their behavior can be checked: "
            f"{starter.fatal}"
        )

    if len(starter.cases) != len(evaluation.cases):
        raise ValueError(
            "The HTTP runner returned an unexpected number of starter results: "
            f"{len(starter.cases)} for {len(evaluation.cases)} cases."
        )

    starter_labels = [outcome.label for outcome in starter.cases]

    if starter_labels != expected_labels:
        raise ValueError(
            "HTTP runner returned starter results in an unexpected order."
        )

    if all(outcome.passed for outcome in starter.cases):
        raise ValueError(
            "The starter application already passes every HTTP case. "
            "At least one case must require the learner to implement behavior."
        )

    cases = [
        HttpCase(
            **case.model_dump(exclude_unset=True),
            visible=index < visible_cases,
        )
        for index, case in enumerate(evaluation.cases)
    ]

    return Exercise.from_draft(
        draft,
        cases=cases,
    )


def make_verifier(
    pool,
    env: EnvironmentSpec,
    *,
    visible_cases: int = 2,
    runner: Runner | None = None,
    http_runner: HttpRunner | None = None,
) -> Callable[[ExerciseDraft], Exercise]:

    if not 1 <= visible_cases <= 2:
        raise ValueError(
            "visible_cases must be 1 or 2, so every exercise keeps at least one hidden case"
        )

    packages = list(env.packages)

    def verify(draft: ExerciseDraft) -> Exercise:
        if isinstance(draft.execution, FunctionExecutionConfig):
            function_run = runner or _sandbox_runner(pool)

            return _verify_function(
                draft,
                function_run,
                packages,
                visible_cases,
            )

        if isinstance(draft.execution, HttpExecutionConfig):
            http_run = http_runner or _sandbox_http_runner(pool)

            return _verify_http(
                draft,
                http_run,
                visible_cases,
            )

        raise ValueError(
            f"Unsupported execution target: {draft.execution.target!r}"
        )

    return verify