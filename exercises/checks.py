from __future__ import annotations

import json
from typing import Any

from exercises.case_runner import HarnessError,RunReport

_MAX_ROWS=6

class StarterError(RuntimeError):
    "The starter code we derived did not even load: a bug on our side, never the model's fault."

def _show(value: Any, limit: int = 60) -> str:
    text = json.dumps(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."

def _key(value:Any) -> str:
    return json.dumps(value,sort_keys=True)

def reference_outputs(report:RunReport,labels:list[str],inputs: list[list])->list[Any]:
    "The reference's output for every case, or a ValueError listing everything that went wrong."
    if report.fatal:
        raise ValueError(f"The reference solution could not be loaded: {report.fatal}")
    if len(report.cases)!=len(inputs):
        raise HarnessError(f"Driver returned {len(report.cases)} results for {len(inputs)} cases.")

    problems=[
        f"- case {label!r} with inputs {_show(args)} crashed: {outcome.error}"
        for label, args, outcome in zip(labels, inputs, report.cases) if not outcome.ok
    ]

    if problems:
        raise ValueError("The reference solution crashed on its own test cases:\n" + "\n".join(problems))

    return [outcome.value for outcome in report.cases]

def check_distinct_inputs(labels: list[str], inputs: list[list]) -> None:
    seen: dict[str, str] = {}
    for label, args in zip(labels, inputs):
        first = seen.setdefault(_key(args), label)
        if first != label:
            raise ValueError(
                f"Cases {first!r} and {label!r} use identical inputs {_show(args)}. "
                "Every test case must use different inputs.")

def check_variety(labels:list[str],inputs:list[list],outputs:list[Any]) ->None:
    "Reject test sets where one constant answer would pass every case."

    if len(outputs) < 2 or len({_key(o) for o in outputs}) >= 2:
        return
    
    rows = "\n".join(f"- {l!r}: inputs {_show(i)} -> {_show(o)}"
                     for l, i, o in list(zip(labels, inputs, outputs))[:_MAX_ROWS])
    raise ValueError(
        f"All {len(outputs)} test cases give the same result ({_show(outputs[0])}), so a solution that "
        "always returns that value would pass every test. Change or add test inputs so that different "
        "inputs have different correct results (for example an input whose correct answer is the "
        f"opposite).\n{rows}")

def verify_reference_run(report: RunReport, labels: list[str], inputs: list[list]) -> list[Any]:
    "All checks in order. Returns the outputs to store as `expected`, or raises ValueError."
    outputs = reference_outputs(report, labels, inputs)
    check_distinct_inputs(labels, inputs)
    check_variety(labels, inputs, outputs)
    return outputs

def check_starter_fails(graded: list[dict]) -> None:
    "Run on the STARTER code. At least one case must fail."
    if not graded:
        return
    if graded[0].get("reason") == "load_error":
        raise StarterError(f"The derived starter code could not be loaded: {graded[0].get('detail')}")
    if all(g["passed"] for g in graded):
        raise ValueError(
            "The starter code (an empty function that returns None) already passes every test case. "
            "Every test must require real work: the function must RETURN a computed value that the "
            "tests compare, not print something or change something and return nothing.")