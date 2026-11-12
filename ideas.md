# Forge: ideas and planned work

Written after the three-stage exercise pipeline reached zero failures on the FastAPI
smoke course. Nothing here is built yet. Items are ordered roughly by value for effort.

## Where things stand

Works today:

- Planner, lesson generator, three-stage exercise generation (reference -> starter -> cases).
- Verification: starter must fail, reference must be deterministic, case variety (60% rule),
  case pruning (drop cases the reference fails if >= 3 remain), AST guard against
  starter == reference, `compile()` check on the reference.
- Two exercise targets: `function` and `http` (FastAPI only).
- Retries: 5 attempts, temperature rising on later attempts.

Principle learned: a small local model is reliable only when each call does one small
thing. Anything that can be derived or checked in code should be, not left to a prompt.

## 1. Support more libraries and frameworks

### 1.1 Framework profiles for the HTTP path

Hard-coded to FastAPI today: the `uvicorn main:app` command, the `app` variable, the
FastAPI examples in the `http_*` prompts, and `_HTTP_HINTS` in `_pick_target`.

Idea: a small profile per framework, and make the `http_*` prompts templates.

```python
PROFILES = {
    "fastapi": {"command": [...], "app_name": "...", "http_hints": (...)},
    "flask":   {"command": [...], "app_name": "...", "http_hints": (...)},
}
```

- The course JSON already has a `framework` field to select the profile.
- Prompts use placeholders such as `{command}` and `{app_name}`.
- Libraries with no profile use the function path only.
- Django needs a whole project with settings; treat it as a later, separate problem.
- Build this only after one non-FastAPI course shows what really has to vary.

### 1.2 Output conversion for data libraries

`_jsonable` in the function driver handles sets, tuples, dicts, objects with `model_dump`
and date-like objects. Add as needed:

- numpy arrays -> `.tolist()`, numpy scalars -> `.item()`
- pandas DataFrame -> `.to_dict(orient="records")`, Series -> `.to_dict()`
- decimals, paths, bytes -> strings

Add these when a pandas or numpy course hits them, not before.

### 1.3 Which libraries fit (judged from the design, not yet tested)

| Fit | Examples |
|---|---|
| Should work now (function path) | stdlib modules, pydantic, attrs, marshmallow, jsonschema, PyYAML, more-itertools, toolz, Jinja2, BeautifulSoup/lxml on HTML strings |
| Small additions needed | numpy, pandas (1.2), sympy (return `str(expr)`), SQLAlchemy Core or in-memory SQLite, dateutil/arrow (no "now"), Pillow (tiny in-memory images) |
| Needs a framework profile | Flask, Starlette, Litestar, Bottle; Django later |
| Poor fit for sandbox exercises | asyncio/aiohttp (async rejected), requests and anything networked, click/typer/rich/textual (print output), pytest/unittest (need a "write tests" exercise type), tkinter/pygame/matplotlib, scikit-learn/torch/tensorflow |

First test course suggestion: Jinja2 or jsonschema (pure function path, least new work).
Second: pandas (exercises output conversion).

## 2. Manual exercise type

For steps that cannot run in the sandbox (network, API keys, GPU, heavy installs, e.g.
parts of langchain). The learner runs the task on their own machine, compares with a
reference, and rates themselves Again / Hard / Good / Easy for the FSRS scheduler.

Design notes:

- Third value for `exercise_target`: `"manual"`.
- No `cases` and no `execution`. Carries `criteria`: a short list of what the learner
  should observe when it works.
- Stages: reference (stage 1) and starter (stage 2) stay. Stage 3 writes `criteria`
  instead of test cases.
- Show the reference solution and the criteria BEFORE the rating, so the self-assessment
  is against a concrete target and not from memory.

Verification without running anything (to catch hallucinated APIs, which are the main
risk because nothing executes):

- `compile()` the reference.
- Every import resolves in the sandbox's installed packages.
- Every imported name exists (`import` + `getattr`).
- The task must cite the documentation section it came from (reuse the existing
  retrieval and grounding).

Also use it as the fallback: when exercise generation fails after all retries, produce a
manual exercise instead of recording a failure, or instead of `graded: false`.

Do not assume everything in a "heavy" library has to be manual. Some libraries ship fake
or offline test doubles (langchain's fake chat models, for example), so prompt templates,
output parsers and chain composition can still use the function path. Only steps that
truly need a real service should be manual.

Open question: how the FSRS scheduler accepts a rating, which decides how this type
plugs in. Build it after the learner-facing layer exists.

## 3. Pipeline quality

- **Review script.** Print each step's objective next to its starter and read them all.
  Passing verification proves an exercise runs, not that it teaches the objective.
  Turn repeated problems into prompt rules or code checks.
- **Regression benchmark.** Keep the FastAPI course as a fixed test. After any prompt or
  code change, regenerate all modules and compare the pass count and the number of
  `FAILED GENERATION ATTEMPT` blocks in the logs.
- **`removed` field in `StarterDraft`.** A first field where the model names the exact
  line or construct it removed, so it decides before writing files. Add only if starters
  keep removing the wrong thing.
- **Outer reference retry.** If stage 3 fails because the reference is broken (could not
  be evaluated, crashed), regenerate the reference too instead of only re-rolling cases.
- **Planner check for setup steps.** Force `graded=False` when the objective starts with
  verbs like Install, Initialize or Run, if the prompt tie-break is not enough.
- **Docs grounding for setup steps.** Setup lessons cited unrelated documentation
  sections (all marked weak). Check the retrieval for those steps.
- **Per-stage model routing.** The stages are separate calls, so a stronger model can be
  used for only the hardest stage (probably the reference) when a step keeps failing.
- **Logging.** Keep raw model responses, the starter and reference printouts, and the
  `Actual response` text in HTTP failures; they made most fixes quick.

## 4. Cleanup

- Delete the unused `function_exercise.txt` and `http_exercise.txt` prompts.
- Delete the unused `VerifiedCase` in `lesson_generation_models.py`.
- Add a `--force` flag to `generate_steps.py` so a step can be regenerated without
  editing the course JSON.
- Remove stale `Dropped cases` noise if it gets too chatty; keep the warning itself.

## 5. Suggested order

1. Commit the current state and tag it.
2. Count retries and pruned cases from the logs; read those exercises first.
3. Run the review on a freshly generated course.
4. Generate a course for a pure-Python library and note what breaks.
5. Generate a pandas course (output conversion).
6. Build framework profiles when a second web framework is wanted.
7. Build the manual exercise type once the learner-facing layer and FSRS flow exist.

## Known limits

- A starter can pass verification while removing the wrong thing; only review catches it.
- Pruning can drop the case that tested the objective; the starter-must-fail check is the
  only safeguard, so read the `Dropped cases` warnings during review.
- Expected values for function exercises come from the reference, so a wrong reference
  produces tests that agree with it.
