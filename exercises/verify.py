from __future__ import annotations

from typing import Callable

from exercises.case_runner import RunReport,grade,run_cases
from exercises.checks import check_starter_fails,reference_outputs,verify_reference_run
from exercises.starter import make_starter
from models.data_models import EnvironmentSpec
from models.lesson_generation_models import (
    Exercise,
    ExerciseDraft,
    FunctionCase,
    FunctionEvaluationConfig,
    FunctionExecutionConfig,
    HttpExecutionConfig,
)
from sandbox.sandbox import SandBox

Runner=Callable[[str,str,list[list]],RunReport]
RUN_TIMEOUT_SECONDS=20

def _sandbox_runner(pool) -> Runner:
    def runner(files:dict[str,str],entry_file:str,function_name:str,inputs:list[list])->RunReport:
        run_script=lambda code:SandBox(pool,code,timeout_seconds=RUN_TIMEOUT_SECONDS).sandbox_instance()
        return run_cases(run_script,files,entry_file,function_name,inputs)
    return runner

def _verify_function(draft:ExerciseDraft,run:Runner,packages:list[str],visible_cases:int) ->Exercise:
    execution=draft.execution
    evaluation=draft.evaluation

    if not isinstance(execution, FunctionExecutionConfig):
        raise TypeError("Function verification requires function execution config.")

    if not isinstance(evaluation, FunctionEvaluationConfig):
        raise TypeError("Function verification requires function evaluation config.")

    entry_file=execution.entry_file
    function_name=execution.function_name

    labels=[case.label for case in evaluation.cases]
    inputs=[case.inputs for case in evaluation.cases]

    starter_files=make_starter(
        draft.reference_files,
        draft.files,
        entry_file=entry_file,
        function_name=function_name
    )

    reference_source=draft.reference_files[entry_file]
    starter_source=starter_files[entry_file]

    first=run(reference_source,function_name,inputs)

    reference_outputs(first,labels,inputs,packages)

    second = run(reference_source, function_name, inputs)

    expected = verify_reference_run(
        first,
        labels,
        inputs,
        second_report=second,
        available_packages=packages,
    )

    starter_report=run(starter_source,function_name,inputs)
    check_starter_fails(
        grade(starter_report,expected)
    )

    cases=[
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
        cases=cases
    )
    

def make_verifier(pool, env: EnvironmentSpec, *, visible_cases: int = 2,
                  runner: Runner | None = None) -> Callable[[ExerciseDraft], Exercise]:

    if not 1<=visible_cases<=2:
        raise ValueError("visible_cases must be 1 or 2, so every exercise keeps at least one hidden case")

    run=runner or _sandbox_runner(pool)
    packages=list(env.packages)

    def verify(draft:ExerciseDraft) ->Exercise:
        if isinstance(draft.execution,FunctionExecutionConfig):
            return _verify_function(
                draft,
                run,
                packages,
                visible_cases,
            )

        if isinstance(draft.execution, HttpExecutionConfig):
            raise NotImplementedError(
                "HTTP exercise verification is not implemented yet."
            )

        raise ValueError(
            f"Unsupported execution target: {draft.execution.target!r}"
        )

    return verify