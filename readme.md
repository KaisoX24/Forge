# The FORGE Interactive Learning Platform — Project Plan

## 1. Problem Statement

People learning a new tech stack or framework watch tutorial after tutorial, but passive
watching only yields ~10-15% retention. Actively implementing what you learn pushes retention
up to ~40-50%. Platforms like DataCamp already do interactive, hands-on learning well — but
they're paid and closed.

**Goal:** a locally-run tool that takes a framework/technology and generates a full interactive
course for it — modules with objectives, and hands-on exercises the learner implements and gets
graded on immediately, instead of just watching.

Using a **local LLM** (not API calls) is a deliberate choice — this avoids rate limits, which
would otherwise be a hard blocker for a tool that needs to generate large volumes of curriculum
and exercise content.

---

## 2. Scope

### v1 (this plan)
- **Python frameworks only.** The sandbox, test harness, and AST tooling all assume a Python
  runtime — "any framework" (JS, Rust, etc.) is explicitly out of scope for v1, not just
  deprioritized. Multi-language support is a real architectural expansion, not a config flag.
- One framework at a time, hardcoded per run
- Local LLM generates: curriculum (modules + objectives), exercises, hints, feedback
- RAG grounding against that framework's real docs (reduces hallucinated/outdated APIs)
- Sandboxed code execution for grading (pass/fail against test cases)
- Simple local web UI (FastAPI + Monaco editor)
- Spaced repetition (FSRS-6) review of completed/failed exercises — note: this is a genuine
  adaptation of the existing flashcard-app FSRS-6 pattern, not a drop-in port. "Review" here
  means re-attempting a similar exercise, a different review action than flashcard recall.

### Explicitly deferred to later versions
- Multi-framework generalization
- User accounts / multi-user support
- AST-based grading (detecting hardcoded answers, code quality checks)
- Live test-output streaming via WebSockets
- Polished UI/UX pass
- Support for languages beyond Python (new sandbox runtime + test harness per language)

---

## 3. Things to Learn Before / During Build

This is new territory beyond your existing LLM-app-building experience — budget real time for
these, especially the first one.

### 3.1 Sandboxed code execution (highest priority — security-critical)
- Docker fundamentals: images, containers, resource limits (`--memory`, `--cpus`)
- Execution timeouts / killing runaway processes
- Disabling network access for containers (`--network none`)
- Read-only filesystem mounts where possible
- Alternatives worth knowing about: `firejail`, gVisor (lighter-weight sandboxing)

### 3.2 RAG / embeddings (new territory — you've done structured output, not retrieval)
- Chunking strategies for documentation (by heading, fixed token windows, etc.)
- Local embedding models via Ollama (e.g. `nomic-embed-text`)
- Vector stores: start with Chroma (simplest), FAISS as an alternative
- Retrieval quality basics: top-k tuning, re-ranking (can skip re-ranking for v1)

### 3.3 Local LLM selection for structured output reliability
- Smaller models (7B) are less reliable at strictly following a Pydantic schema —
  test multiple models against your actual schemas before committing
- Code-tuned models tend to perform better here than general chat models at similar size
  (e.g. `qwen2.5-coder`, `deepseek-coder` family via Ollama)
- Understand quantization tradeoffs (Q4 vs Q8) for your available hardware

### 3.4 FastAPI + Monaco integration
- Serving Monaco via CDN in a plain HTML/JS frontend (no need for React/Vue for v1)
- FastAPI endpoint design for submitting code and returning grading results
- Basic understanding of WebSockets (even if v1 uses simple polling, know the upgrade path)

### 3.5 AST parsing (optional, later)
- Python's `ast` module — for eventually detecting hardcoded/gamed solutions
- Not needed for v1's pass/fail-against-tests grading

---

## 4. Architecture

```
┌─────────────────────┐
│   Doc Ingestion      │  scrape framework docs/GitHub → chunk → embed → store in Chroma
└──────────┬───────────┘
           │
┌─────────────────────┐
│  Curriculum Planner   │  local LLM + Pydantic structured output → ordered modules + objectives
└──────────┬───────────┘
           │
┌─────────────────────┐
│  Exercise Generator   │  per module, grounded via RAG retrieval → problem + starter code + tests
└──────────┬───────────┘
           │
┌─────────────────────┐
│   Sandbox Runner      │  Docker container, resource-capped → executes user code vs test cases
└──────────┬───────────┘
           │
┌─────────────────────┐
│  Grader / Feedback    │  pass/fail + LLM-generated targeted hint (not full answer)
└──────────┬───────────┘
           │
┌─────────────────────┐
│  SQLite + FSRS-6      │  tracks completion, schedules spaced review of weak/failed exercises
└──────────────────────┘
```

**UI layer:** FastAPI backend serving a single-page frontend with the Monaco editor embedded,
talking to the backend via REST endpoints for submit/run/grade.

**Two important correctness/reliability additions to the pipeline above:**

- **Reference-solution self-check.** When the exercise generator produces a problem + test
  cases, it must *also* produce a reference solution. Run that reference solution through the
  sandbox against the generated tests before ever showing the exercise to the user. If the
  reference solution fails its own tests, discard and regenerate — otherwise a bad test case
  will fail a learner's *correct* code and they'll debug a phantom bug for no reason.
- **Structured-output retry/repair loop.** Any LLM generation step (curriculum, exercise,
  hints) needs a bounded retry loop: on Pydantic validation failure, feed the validation error
  back to the model and ask it to correct the output, capped at N attempts (e.g. 3) before
  falling back to a simpler/smaller generation task. Without this, one flaky generation
  crashes the whole pipeline.

**Generation strategy:** generate lazily, not eagerly. Build the curriculum *outline* up front
(cheap), but generate each module's actual exercise only when the learner reaches it — this
saves compute and avoids generating content for modules a learner may never get to.

**Caching:** persist generated curricula keyed by framework name + doc scrape date/version,
rather than regenerating from scratch on every run. Regenerating is wasteful and makes each
run non-reproducible.

---

## 5. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| LLM serving | Ollama | already familiar; local, no API limits |
| LLM (curriculum/exercises) | `qwen2.5-coder` or `deepseek-coder` family | test against your schemas first |
| Embeddings | `nomic-embed-text` (via Ollama) | local, avoids API calls |
| Vector store | Chroma | simplest to start with |
| Structured output | Pydantic + LangChain | existing pattern from IdeaGen/DiagramGen |
| Sandboxing | Docker | resource limits, no network, **warm container pool** (see below) |
| Backend | FastAPI | already comfortable with this |
| Frontend | Plain HTML/JS + Monaco Editor (via CDN) | no framework overhead needed for v1 |
| Persistence | SQLite | existing pattern from DSA/flashcard apps |
| Spaced repetition | FSRS-6 | reuse existing implementation pattern |

---

## 6. Security Considerations

- **Never execute user-submitted code on the host process.** Container or nothing.
- **Resource limits per run:** memory cap (e.g. 256MB), CPU shares, wall-clock timeout (5-10s).
- **Process limit (`--pids-limit`):** without this, a fork bomb inside the container can hang
  the host — this is a real gap in a naive Docker setup, not a theoretical one.
- **Run as non-root inside the container, with `--cap-drop=ALL`.**
- **No network egress** from the execution container.
- **Warm container pool instead of spin-up-per-run.** Cold-starting a fresh Docker container
  per submission adds 1-3+ seconds of latency before the user's code even runs — bad for a
  tight write-code-get-feedback loop. Keep a pool of N pre-started containers, reset/wipe their
  filesystem state between runs instead of destroying and respawning. This is a meaningfully
  different implementation than naive per-run spin-up, so design for it from the start rather
  than retrofitting later.
- **Pre-baked images per framework** for dependencies rather than allowing arbitrary
  `pip install` at exercise-run time.
- **Prompt injection awareness:** if user input (e.g. custom framework name) feeds into
  LLM prompts, template/validate it rather than raw string concatenation, to avoid the LLM
  being coaxed into generating malicious "starter code."
- **Doc/framework versioning:** pin the scrape date and framework version used to build the
  RAG index, and surface it to the user (e.g. "generated against FastAPI docs as of X"). Without
  this, outdated APIs get taught silently as the framework evolves, with no way to trace why.
- **Structured logging from day one** for all LLM inputs/outputs — needed to debug bad
  generations, and far more expensive to retrofit later than to build in now.

---

## 7. Phased Build Plan

1. **Pick one framework** to target first (ideally one you're actively learning) — Python only
2. **Sandbox runner** — build and stress-test in isolation first, before any LLM is involved.
   Include the full security list from Section 6 (pids-limit, non-root, no network, resource
   caps) and the **warm container pool** from the start, not as a later optimization.
   Prove safe execution + pass/fail grading against hardcoded test cases.
3. **RAG ingestion** — scrape and embed that framework's docs, pinning scrape date/version
   (can run in parallel with step 2)
4. **Curriculum planner** — structured output, 4-5 modules, tightly hardcoded schema, with the
   **retry/repair loop** on validation failure built in from the start
5. **Exercise generator** — one exercise per module, grounded in retrieved doc chunks, with the
   **reference-solution self-check** (generate + sandbox-verify a reference solution before
   ever surfacing the exercise) and lazy generation (only when the learner reaches the module)
6. **Curriculum/exercise caching** — persist generated content keyed by framework + doc version
7. **Wire grader → hint system** — connect sandbox output to LLM-generated targeted hints
8. **FSRS-6 review layer** — adapt (not port) spaced repetition for "re-attempt a similar
   exercise" as the review action
9. **UI** — FastAPI + Monaco, wiring all of the above together into a usable flow

Steps 2 and 3 don't depend on each other and can be built in parallel. Structured logging
(Section 6) should be present from step 2 onward, not added later.

---

## 8. Future Improvements (Post-v1)

- Generalize curriculum generation to arbitrary frameworks (better RAG robustness needed)
- AST-based grading for code quality / anti-gaming detection
- WebSocket-based live test execution streaming
- Multi-language support beyond Python
- Polished UI/UX pass
- Possible multi-user support if turned into something shareable
