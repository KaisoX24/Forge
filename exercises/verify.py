from __future__ import annotations

from typing import Callable

from exercises.case_runner import RunReport,grade,run_cases
from exercises.checks import check_starter_fails,reference_outputs,verify_reference_run
from exercises.starter import make_starter
from models.data_models import EnvironmentSpec
from models.lesson_generation_models import Case,Exercise,ExerciseDraft
from sandbox.sandbox import SandBox

Runner=Callable[[str,str,list[list]],RunReport]
RUN_TIMEOUT_SECONDS=20

def _sandbox_runner(pool) -> Runner:
    def runner(source:str,function_name:str,inputs:list[list])->RunReport:
        run_script=lambda code:SandBox(pool,code,timeout_seconds=RUN_TIMEOUT_SECONDS).sandbox_instance()
        return run_cases(run_script,source,function_name,inputs)
    return runner

def make_verifier(pool, env: EnvironmentSpec, *, visible_cases: int = 2,
                  runner: Runner | None = None) -> Callable[[ExerciseDraft], Exercise]:

    if not 1<=visible_cases<=2:
        raise ValueError("visible_cases must be 1 or 2, so every exercise keeps at least one hidden case")

    run=runner or _sandbox_runner(pool)
    packages=list(env.packages)

    def verify(draft:ExerciseDraft) ->Exercise:
        labels=[t.label for t in draft.tests]
        inputs=[t.inputs for t in draft.tests]

        starter=make_starter(draft.reference_solution,draft.function_name)

        first=run(draft.reference_solution,draft.function_name,inputs)
        reference_outputs(first,labels,inputs,packages)
        second=run(draft.reference_solution,draft.function_name,inputs)
        expected=verify_reference_run(first,labels,inputs,second_report=second,available_packages=packages)

        check_starter_fails(grade(run(starter, draft.function_name, inputs), expected))

        cases=[Case(label=label, inputs=args, expected=want, visible=n < visible_cases)
                 for n, (label, args, want) in enumerate(zip(labels, inputs, expected))]

        return Exercise.from_draft(draft,starter_code=starter,cases=cases)

    return verify