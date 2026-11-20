# Forge

**Turn a framework's documentation into an interactive, hands-on course, generated and graded entirely on your own machine.**

Watching tutorials gives you roughly 10–15% retention; writing the code yourself gets you to 40–50%. Platforms like DataCamp do hands-on learning well, but they are paid and closed. Forge is the local alternative: point it at a Python framework's docs, and a local LLM writes the lessons and exercises. You solve them in an in-browser editor, and your code is run against tests inside a locked-down Docker sandbox.

> **Status:** Work in progress. . See [Roadmap](#roadmap) for what is not built yet.

## How it works

```
Docs ──► Ingestion ──► Curriculum planner ──► Step generator ──► Sandbox verify ──► Course JSON
 (crawl)  (chunk +      (modules + steps,     (lesson, then      (reference must     (cached on
          embed →        grounded in the       exercise, with     pass, starter       disk)
          Chroma)        docs outline)         retrieval)         must fail)
                                                                         │
                         Web UI (React) ◄── FastAPI ◄── Grader ◄── Docker sandbox
                         Monaco editor      progress     (run / submit)   (no network,
                                            in SQLite                      capped CPU/RAM)
```

1. **Ingestion.** Crawls the framework's documentation (crawl4ai), splits it into chunks, embeds them with `nomic-embed-text` and stores them in a local Chroma database. The scrape date is recorded, so a course always says which docs it was built from.
2. **Planning.** The local LLM produces an ordered curriculum of modules and steps, with structured output and a repair loop on validation errors.
3. **Step generation.** When a learner enters a module, each step is generated with two model calls: a lesson, then an exercise. Retrieval supplies the real docs and the model only writes. The exercise model sees the concept and key points, but not the lesson's example code.
4. **Exercise verification.** Exercises are built in three stages (reference solution → starter code → test cases) and checked in the sandbox before a learner ever sees them (see [Exercise verification](#exercise-verification)).
5. **Grading.** *Run* executes the visible test cases; *Submit* executes all of them, including hidden ones. Hidden cases only report pass or fail.
6. **Progress.** Attempts, revealed hints, drafts and passed flags are stored in SQLite. Earlier material must be completed before later steps unlock.

### Exercise verification

A small local model is reliable only when each call does one small thing, so anything that can be checked in code is checked in code:

- The **reference solution** must compile and give deterministic output.
- The **starter code must fail** the tests, and an AST guard rejects starter == reference.
- **Case variety:** a lazy constant answer (such as `return True`) cannot pass the test set.
- **Case pruning:** cases the reference itself fails are dropped, as long as at least 3 remain.
- Every import in the reference must resolve against the course's installed packages.
- Failed generations retry up to 5 times, with the temperature rising on later attempts.

Two exercise targets exist for now: `function` (call a function with inputs, compare outputs) and `http` (start the learner's app in the sandbox and send requests to it).

## Requirements

| Needs | Why |
|---|---|
| Python 3.13+ and [uv](https://docs.astral.sh/uv/) | Backend and pipeline |
| Node.js (developed on 26.x) | Web UI |
| [Docker](https://docs.docker.com/get-docker/) | Sandbox for running exercise code |
| [Ollama](https://ollama.com/) | Local LLM and embeddings |

Developed on Windows 11 with an RTX 3060 (12 GB VRAM) and 16 GB RAM, where generating one step takes a few seconds. The goal is that ordinary hardware is enough, so the default model is a small one.

## Quick start

```bash
# 1. Models
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# 2. Backend dependencies
uv sync

# 3. Choose the model (see "Configuration" below), then start the API
uv run uvicorn api.main:create_app --factory --reload

# 4. In a second terminal, start the UI
cd web
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to the backend on port 8000.

The first run builds a Docker image for the course's environment (Python plus the pinned packages), which takes a minute or two.

For a single-process setup, build the UI once (`npm run build`). FastAPI then serves `web/dist` itself at <http://localhost:8000>.

## Configuration

**Model.** Forge reads `~/.forge/settings.json`. For a local Ollama model:

```json
{ "provider": "ollama", "model": "qwen3.5:9b" }
```

Supported providers are `ollama`, `openai`, `anthropic` and `google_genai`. API keys for hosted providers are stored in your OS keychain (via `keyring`), never in the file. The model name is just a config value, so you can swap it without touching code.

**Paths.** Courses live in `data/courses/`, learner progress in `data/learner.db`, the vector store in `data/chroma/`, and scraped docs in `raw_docs/`. All are set in `config.py`.

## Creating a course

The repository ships with a generated FastAPI course (5 modules, 17 steps, built from the FastAPI tutorial docs). To build your own, or to regenerate steps from the command line:

```bash
# Generate the first 3 steps of module 2 (plans the course first if it doesn't exist yet)
uv run python generate_steps.py --module 2 --steps 3

# Generate exactly one step
uv run python generate_steps.py --module 2 --step 1
```

From the UI, generating a module and regenerating a step run as background jobs with live progress over SSE. Regenerating a step resets that step's learner state but keeps the old attempts.

Pointing Forge at a different framework mostly means redoing the **ingestion layer**: a URL list (see `course_sources.py`), `ingestion/doc_scraper.py`, and the planner entry point. The HTTP exercise path is still FastAPI-specific; see [`ideas.md`](ideas.md) for the planned framework profiles.

## HTTP API

All routes live under `/api`. Interactive docs are at `/docs` while the backend is running.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/courses` | List courses |
| `GET /api/courses/{cid}` | Course outline with learner progress |
| `GET /api/courses/{cid}/steps/{sid}` | Lesson, public exercise and learner state in one response |
| `POST /api/courses/{cid}/modules/{index}/generate` | Generate a module; returns a `job_id` |
| `POST /api/courses/{cid}/steps/{sid}/regenerate` | Regenerate one step |
| `GET /api/jobs/{job_id}` | Job status |
| `GET /api/courses/{cid}/jobs` | Jobs for a course |
| `PUT …/steps/{sid}/draft` | Autosave the learner's code |
| `POST …/steps/{sid}/run` | Run the visible test cases |
| `POST …/steps/{sid}/submit` | Run all cases and record the attempt |
| `POST …/steps/{sid}/hints/next` | Reveal the next hint |
| `POST …/steps/{sid}/complete` | Mark the step complete |
| `POST …/steps/{sid}/give-up` | Unlock the solution (after N failed submits) |
| `GET …/steps/{sid}/solution` | The reference solution; locked until passed or given up |

Hidden test cases never leave the server: the public schema excludes them.

## Sandbox and safety

Learner code never runs in the host process. Each run happens in a container from a warm pool, which avoids the 1–3 s cold start of spinning up a fresh container per submission. Containers are reset between runs and are created with:

- no network (`network_disabled`)
- non-root user (`1000:1000`) and `cap_drop=all`
- read-only root filesystem, with a small `noexec` tmpfs at `/tmp`
- memory cap (256 MB by default), half a CPU, and `pids_limit=50` against fork bombs
- dependencies baked into the image, with no `pip install` at run time

## Project layout

```
api/            FastAPI app: routers, schemas, services (grader, jobs, generation), SQLite storage
ingestion/      Doc scraping, chunking, embeddings, Chroma vector store
retrieval/      Retriever and the retrieval tool used by the generators
planner/        Curriculum planner and doc outline
lessons/        Step generator (lesson, then exercise)
exercises/      Verification checks, starter/reference handling, function and HTTP drivers
sandbox/        Docker image builder, warm container pool, dependency resolver
reasoning/      LLM factory, structured-output helpers, and the prompt files (system_messages/)
models/         Course and exercise data models
web/            React + TypeScript + Vite UI (Tailwind, Monaco, TanStack Query)
data/           Generated courses, learner database, vector store
tests/          pytest suite
```

## Development

```bash
uv run pytest                 # unit tests (no Docker or Ollama needed for most)
cd web && npm run lint        # oxlint
cd web && npm run gen:api     # regenerate TypeScript API types from the running backend
```

`tests/integration/` and `tests/check_container.py` need Docker. After changing a prompt or the pipeline, regenerate the FastAPI course and compare pass counts and `FAILED GENERATION ATTEMPT` entries in the logs; that is the informal regression benchmark.

## Roadmap

Built : planner, lessons, three-stage exercise generation with verification, function and HTTP exercise types, the full API layer, and a first React UI with a module celebration and a generation animation.

Planned (details and reasoning in [`ideas.md`](ideas.md)):

- **More libraries and frameworks:** per-framework profiles for the HTTP path (Flask, Starlette), and output conversion for data libraries (numpy, pandas).
- **Manual exercise type** for steps that cannot run in a sandbox (network, API keys, GPU), with self-rating, and as a fallback when generation fails.
- **Spaced repetition (FSRS-6)** to review weak or failed exercises.
- **Pipeline quality:** a review script, a regression benchmark, per-stage model routing.
- **Desktop app** with Tauri around the existing React UI.
- Later: more exercise categories (CLI, app), search, settings screen, multi-user support.

Out of scope for v1: non-Python languages (the sandbox, test harness and AST tooling all assume Python).

## License

[MIT](LICENSE) © 2026 Pramit Acharjya
