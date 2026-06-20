# Butterfly Director AI

An AI system that turns a single story premise into a **branching multiverse of fully
generated short films**. A user supplies a premise, target runtime, and optional
genre/style; a pipeline of specialized AI agents (Story Architect → Character Architect
→ ... → Editing) expands that premise into a structured story bible, a branching
timeline of decision points ("butterfly" moments), and ultimately rendered video,
voiceover, and music for every branch — orchestrated through LangGraph and backed by
Alibaba Cloud's DashScope models (Qwen for text, Wan for video, CosyVoice for voice).

This repo is the backend (`apps/api`). Agents are built one at a time, each following
the same reference pattern established by the **Story Architect Agent** (the first one
shipped). See `ARCHITECTURE.md` for the full system design and `docs/design/` for the
approved design decisions.

> Status: Story Architect, Character Architect, and Decision Detector Agents are
> complete and live-verified. Remaining agents (Timeline Generator, Character Memory,
> Storyboard, Prompt Director, Video, Voice, Music, Editor) are built incrementally,
> one at a time, on top of this foundation.

---

## Quick start (run it locally)

**Prerequisites:** Docker Desktop, and a DashScope API key (Alibaba Cloud Model Studio,
international workspace) if you want to actually generate content rather than just
browse the API.

```bash
# 1. Copy the env template and fill in your DashScope key
cp .env.example .env
# edit .env -> DASHSCOPE_API_KEY=sk-...

# 2. Build and start everything (postgres, redis, api, celery worker, celery beat)
docker compose up -d --build

# 3. Check it's healthy
curl http://localhost:8000/v1/health
# -> {"status":"ok"}
```

Then open **http://localhost:8000/docs** for the interactive Swagger UI — every
endpoint can be called directly from the browser.

### Try the Story Architect Agent

```bash
curl -X POST http://localhost:8000/v1/story/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A retired thief is recruited for one last job: steal back a memory that was stolen from her own mind.",
    "target_runtime_minutes": 8,
    "genre": "neo-noir sci-fi"
  }'
```

This calls the live DashScope `qwen-plus` model, validates the response into a
strongly-typed `StoryBible`, persists it, and returns it (takes ~20-30s). Or run the
standalone demo script directly inside the API container:

```bash
docker compose exec api python -m app.demo.story_architect
```

### Try the Character Architect Agent

Feed a previously generated story's id in to get a full cast built from it:

```bash
curl -X POST http://localhost:8000/v1/character/generate \
  -H "Content-Type: application/json" \
  -d '{"story_id": "<id from /v1/story/generate above>"}'
```

This fetches the persisted `StoryBible`, runs the Character Architect Agent against the
live DashScope `qwen-plus` model, and persists one `Character` row per cast member
(protagonist, antagonist if one exists, and one per supporting-character summary). Or
run the standalone demo, which chains Story Architect -> Character Architect end to end:

```bash
docker compose exec api python -m app.demo.character_architect
```

### Try the Decision Detector Agent

Feed the same story id in to find its branch points:

```bash
curl -X POST http://localhost:8000/v1/decision/generate \
  -H "Content-Type: application/json" \
  -d '{"story_id": "<id from /v1/story/generate above>"}'
```

This fetches the persisted `StoryBible`, runs the Decision Detector Agent against the
live DashScope `qwen-plus` model, and persists one `DecisionPoint` row per genuine fork
it finds (each with 2-4 mutually exclusive `branch_candidates`). An empty result is
valid and expected for a linear story - it means there's nothing to branch on. Or run
the standalone demo, which chains Story Architect -> Decision Detector end to end:

```bash
docker compose exec api python -m app.demo.decision_detector
```

### Stopping / resetting

```bash
docker compose down          # stop containers, keep the postgres volume (data persists)
docker compose down -v       # stop and wipe the database volume too
```

---

## Services (docker-compose)

| Service    | Image / build         | Purpose                                                            | Port |
|------------|------------------------|---------------------------------------------------------------------|------|
| `postgres` | `postgres:16-alpine`   | Primary datastore                                                  | 5432 |
| `redis`    | `redis:7-alpine`       | Celery broker/result backend + API rate-limit counters             | 6379 |
| `api`      | `apps/api/Dockerfile`  | FastAPI app; runs `alembic upgrade head` then `uvicorn` on startup | 8000 |
| `worker`   | `apps/api/Dockerfile`  | Celery worker bound to all task queues (see below)                  | —    |
| `beat`     | `apps/api/Dockerfile`  | Celery beat scheduler for periodic/maintenance tasks                | —    |

All four app-level env vars (`DATABASE_URL`, `REDIS_URL`, `CELERY_*`) are overridden by
`docker-compose.yml` to point at the in-network service names — `.env` only needs your
DashScope key and any other values you want to override from their defaults.

---

## Repository layout

```
.
├── ARCHITECTURE.md              Full system design: agents, data model, provider strategy
├── docker-compose.yml           postgres + redis + api + worker + beat
├── .env.example                 All configurable environment variables, documented inline
├── docs/design/                 Approved design decision docs (one per major design discussion)
└── apps/api/                    The FastAPI backend (everything below is rooted here)
```

### `apps/api/` — backend service

```
apps/api/
├── Dockerfile                   python:3.12-slim, installs requirements.txt, runs uvicorn
├── alembic.ini                  Alembic migration runner config
├── pyproject.toml                ruff + mypy(strict) + pytest config
├── requirements.txt              Pinned runtime dependencies
├── requirements-dev.txt          + pytest, pytest-asyncio, pytest-cov, ruff, mypy
├── app/                          Application code (see below)
└── tests/                        Test suite (see below)
```

### `app/` — application code

```
app/
├── main.py                       create_app(): FastAPI instance, middleware stack, lifespan
│                                  (verifies DB + Redis connectivity on boot), router mount
│
├── config/
│   ├── settings.py                Settings (pydantic-settings) — every env var the app reads
│   ├── logging.py                 structlog configuration (JSON or console)
│   └── constants.py               Shared constants (e.g. request-id header name)
│
├── core/
│   ├── deps.py                    FastAPI dependencies: get_db, pagination, settings
│   ├── exceptions.py               Domain exceptions (AgentOutputInvalidError,
│   │                                ProviderUnavailableError, NotFoundError, etc.)
│   ├── pagination.py                Cursor-pagination helpers
│   ├── security.py                  Password hashing / JWT helpers (auth is built but
│   │                                 disabled by default — AUTH_ENABLED=false)
│   └── middleware/
│       ├── auth.py                  AuthContextMiddleware (no-ops when auth disabled)
│       ├── error_handler.py         Uniform JSON error responses for all raised exceptions
│       ├── logging_middleware.py    Structured request/response logging
│       ├── rate_limit.py            Redis-backed sliding-window rate limiter
│       └── request_id.py            Generates/propagates X-Request-ID
│
├── db/
│   ├── base.py                    Async SQLAlchemy engine/session factory
│   ├── models/                    SQLAlchemy ORM models: project, story, character,
│   │                              decision_point, timeline, branch, movie, asset, job,
│   │                              agent_log, prompt_history, enums, mixins (timestamps/
│   │                              soft-delete). story.project_id and character.project_id
│   │                              are both nullable (agents generate them standalone,
│   │                              before any Project exists); character.story_id and
│   │                              decision_point.story_id link generated rows back to
│   │                              the Story they were built from.
│   └── migrations/                Alembic migrations (initial schema, butterfly-score
│                                   fields, nullable story.project_id + generation_metadata,
│                                   nullable character.project_id + story_id + generation_metadata,
│                                   new decision_points table)
│
├── repositories/                  One repository per model — thin async CRUD wrappers
│                                  over SQLAlchemy (BaseRepository[Model] generic base)
│
├── schemas/                       Pydantic request/response DTOs per resource (API-facing
│                                  shapes, distinct from the agent-internal schemas below)
│
├── services/                      Business logic layer — one per resource, called by routers.
│                                  story_architect_service.py is the reference implementation:
│                                  runs the agent, persists the result + AgentLog audit trail.
│                                  character_architect_service.py and decision_detector_service.py
│                                  follow the same shape but persist N rows (one roster /
│                                  one decision list) per agent run - decision_detector_service.py
│                                  correctly persists zero rows when the agent finds no forks.
│
├── routers/v1/                    FastAPI routers, one per resource, mounted under /v1
│
├── agents/                        AI agents — the core of the system. Each agent is fully
│   │                              self-contained: schema, prompts, validators, run logic.
│   ├── base/                      Shared reference shape every agent follows:
│   │   ├── base_agent.py           BaseAgent ABC — run(request) -> AgentRunResult[Output]
│   │   ├── agent_result.py         AgentRunResult[T]: output, model, prompt_version,
│   │   │                           latency_ms, attempts, token counts, raw snapshot
│   │   └── prompt_loader.py        Loads versioned prompt files (prompts/<version>/<file>)
│   ├── story_architect/            First agent built — the reference implementation
│   │   ├── agent.py                 StoryArchitectAgent: calls Qwen via ChatOpenAI
│   │   │                            (DashScope OpenAI-compatible endpoint), parses with
│   │   │                            PydanticOutputParser, self-driven repair/retry loop
│   │   │                            (up to 3 attempts) on malformed/invalid output
│   │   ├── schema.py                StoryRequest (input) + StoryBible (21-field
│   │   │                            strongly-typed output contract)
│   │   ├── validators.py            Semantic checks beyond field types (runtime-vs-request
│   │   │                            tolerance is a hard fail; genre/hooks mismatches warn)
│   │   └── prompts/v1/               system.txt, developer.txt, output_instructions.txt
│   │                                (versioned — future prompt changes ship as v2/, v3/...)
│   ├── character_architect/        Second agent — consumes a StoryBible, never raw text
│   │   ├── agent.py                 CharacterArchitectAgent: identical shape to
│   │   │                            StoryArchitectAgent (ChatOpenAI + PydanticOutputParser
│   │   │                            + self-driven repair loop)
│   │   ├── schema.py                CharacterRequest (StoryBible in) + CharacterProfile
│   │   │                            (deep per-character contract: physical_description and
│   │   │                            voice_profile are written to be used directly as video/
│   │   │                            voice generation prompt fragments) + CharacterRoster
│   │   │                            (exactly one protagonist enforced; duplicate names
│   │   │                            rejected)
│   │   ├── validators.py            Semantic checks vs the source StoryBible (antagonist
│   │   │                            expected-but-missing, supporting-character count
│   │   │                            mismatch, characters with no relationships — all warn,
│   │   │                            never hard-fail; the protagonist/duplicate-name rules
│   │   │                            are hard-enforced in schema.py instead)
│   │   └── prompts/v1/               system.txt, developer.txt, output_instructions.txt
│   └── decision_detector/          Third agent — finds the story's genuine fork points
│       ├── agent.py                 DecisionDetectorAgent: identical shape to the other
│       │                            two agents (ChatOpenAI + PydanticOutputParser +
│       │                            self-driven repair loop)
│       ├── schema.py                DecisionDetectorRequest (StoryBible in) + BranchCandidate
│       │                            (label/description/tone_shift/divergence_summary) +
│       │                            DecisionPoint (beat_index, description, source_hook,
│       │                            branch_candidates[]) + DecisionList (unique beat_index
│       │                            enforced; an EMPTY list is valid - a linear story with
│       │                            no forks is a legitimate, common output, not an error)
│       ├── validators.py            Settings-driven hard check: each decision's candidate
│       │                            count must fall within
│       │                            [decision_branch_candidates_min, _max] (default 2-4,
│       │                            bounds fan-out cost) - violating this retries the agent.
│       │                            Everything else (story_hooks left unmapped, decisions
│       │                            not in ascending beat_index order) is a warning only.
│       └── prompts/v1/               system.txt, developer.txt (interpolates the configured
│                                    min/max into the prompt), output_instructions.txt
│
├── graphs/
│   └── story_creation_graph.py     LangGraph StateGraph: START -> story_architect ->
│                                   character_architect -> decision_detector -> END. Each
│                                   downstream node reads the story node's StoryBible
│                                   directly out of graph state. Future agents (Timeline
│                                   Generator, ...) extend this same graph.
│
├── integrations/
│   ├── qwen_client.py               Low-level DashScope/Qwen HTTP client
│   ├── redis_client.py              Shared Redis connection pool (singleton)
│   └── providers/                   Strategy pattern: business logic depends only on these
│       │                            interfaces, never on a vendor SDK directly
│       ├── base.py                   VideoGenerationProvider / VoiceGenerationProvider /
│       │                             MusicGenerationProvider abstract interfaces
│       ├── wan_video_provider.py     Alibaba Wan (text-to-video)
│       ├── dashscope_tts_provider.py  Alibaba CosyVoice (text-to-speech)
│       ├── happyhorse_provider.py    Generic vendor-agnostic HTTP adapter (drop in
│       │                             Runway/Kling/Veo/ElevenLabs/PlayHT later with no
│       │                             code changes elsewhere — disabled until configured)
│       └── factory.py                Reads Settings.*_provider and returns the right
│                                     concrete provider instance
│
├── workers/
│   ├── celery_app.py                 Celery application instance
│   ├── queues.py                     Named queues (story, timeline, storyboard, video,
│   │                                 voice, music, editing, maintenance) — one worker
│   │                                 process binds to all of them today; splitting into
│   │                                 dedicated pools later is a compose change, not code
│   └── tasks/maintenance_tasks.py    Scheduled housekeeping tasks (run by `beat`)
│
└── demo/
    ├── story_architect.py           python -m app.demo.story_architect — standalone
    │                                script that calls the live agent and pretty-prints
    │                                the resulting StoryBible + generation metadata
    ├── character_architect.py       python -m app.demo.character_architect — chains
    │                                Story Architect into Character Architect against
    │                                the live API and pretty-prints the resulting roster
    └── decision_detector.py         python -m app.demo.decision_detector — chains
                                     Story Architect into Decision Detector against
                                     the live API and pretty-prints the resulting forks
```

### `tests/` — test suite (pytest, async, 100% coverage on shipped agent modules)

```
tests/
├── conftest.py                     Shared fixtures:
│                                    - db_session: real Postgres session wrapped in a
│                                      SAVEPOINT that's always rolled back, so tests can
│                                      call session.commit() like real services do
│                                      without persisting anything
│                                    - client: httpx AsyncClient over an ASGITransport,
│                                      wired to db_session via dependency override
│                                    - autouse fixture resetting the Redis connection
│                                      pool between tests (pool is bound to whichever
│                                      event loop created it; pytest-asyncio gives each
│                                      test its own loop)
├── factories.py                    Shared fake StoryBible/CharacterRoster/DecisionList/
│                                    AgentRunResult builders, reused across agents/services/
│                                    routers/graph tests
├── agents/                          Unit tests per agent: schema validation, semantic
│                                    validators, agent retry/repair logic (mocked LLM), +
│                                    one live test per agent gated behind RUN_LIVE_API_TESTS=1
├── graphs/                          LangGraph node wiring test (story_architect ->
│                                    character_architect -> decision_detector, all 3 mocked)
├── services/                        Service-layer tests against a real transactional DB
└── routers/                         Full HTTP lifecycle tests (generate -> get -> list
                                     -> delete -> 404) via the ASGI test client
```

Run the suite:

```bash
docker compose exec api pytest                                   # full suite
docker compose exec api pytest --cov=app --cov-report=term-missing  # with coverage
RUN_LIVE_API_TESTS=1 docker compose exec -e RUN_LIVE_API_TESTS=1 api pytest tests/agents/test_story_architect_live.py tests/agents/test_character_architect_live.py tests/agents/test_decision_detector_live.py
```

`pytest` isn't installed in the running `api`/`worker`/`beat` images by default (only
`requirements.txt` is baked in) — install dev deps once per container if you haven't:
`docker compose exec api pip install -q -r requirements-dev.txt`.

---

## API reference

Interactive docs: **http://localhost:8000/docs** (Swagger UI) or
**http://localhost:8000/redoc**. Raw schema: **http://localhost:8000/openapi.json**.

All routes are mounted under `/v1`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | Liveness check |
| POST | `/v1/story/generate` | Run the Story Architect Agent on a premise; persists and returns a `StoryBible` |
| GET | `/v1/story/{id}` | Fetch a previously generated `StoryBible` by id |
| GET | `/v1/story` | Cursor-paginated list of generated story bibles |
| DELETE | `/v1/story/{id}` | Soft-delete a generated story bible |
| POST | `/v1/character/generate` | Run the Character Architect Agent on a `story_id`; persists and returns the full cast |
| GET | `/v1/character/{id}` | Fetch one generated character profile by id |
| GET | `/v1/character?story_id=` | Cursor-paginated list of generated characters, optionally filtered by story |
| DELETE | `/v1/character/{id}` | Soft-delete a generated character |
| POST | `/v1/decision/generate` | Run the Decision Detector Agent on a `story_id`; persists and returns the detected forks (possibly empty) |
| GET | `/v1/decision/{id}` | Fetch one detected decision point by id |
| GET | `/v1/decision?story_id=` | Cursor-paginated list of detected decision points, optionally filtered by story |
| DELETE | `/v1/decision/{id}` | Soft-delete a detected decision point |
| `/v1/projects`, `/v1/stories`, `/v1/timelines`, `/v1/branches`, `/v1/movies`, `/v1/characters`, `/v1/assets`, `/v1/jobs`, `/v1/agent-logs`, `/v1/prompt-history` | Generic CRUD endpoints for the underlying domain model (project-scoped resources used by the broader pipeline as more agents come online) |

### Example: generate a story, then its cast, then its forks

```bash
curl -X POST http://localhost:8000/v1/story/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "...", "target_runtime_minutes": 10, "genre": "drama"}'
# -> {"id": "<story_id>", "story_bible": {...}, ...}

curl -X POST http://localhost:8000/v1/character/generate \
  -H "Content-Type: application/json" \
  -d '{"story_id": "<story_id>"}'
# -> {"story_id": "<story_id>", "characters": [{...protagonist...}, {...}], ...}

curl -X POST http://localhost:8000/v1/decision/generate \
  -H "Content-Type: application/json" \
  -d '{"story_id": "<story_id>"}'
# -> {"story_id": "<story_id>", "decisions": [{"beat_index": 0, "branch_candidates": [...]}], ...}
```

Story generate returns a `StoryGenerateResponse`: the full 21-field `StoryBible`, plus
generation provenance (`model`, `prompt_version`, `latency_ms`, `attempts`, token counts).
Character generate returns a `CharacterGenerateResponse`: one full `CharacterProfileRead`
per cast member (role, physical/voice descriptors, backstory, arc, relationships, ...).
Decision generate returns a `DecisionGenerateResponse`: zero or more `DecisionPointRead`
entries (each with 2-4 `branch_candidates`, every candidate carrying a `label`,
`description`, `tone_shift`, and `divergence_summary`). All three share the same
generation-provenance shape (`model`, `prompt_version`, `latency_ms`, `attempts`, token
counts).

---

## Configuration (`.env`)

See `.env.example` for the full, documented list. The essentials:

- `DASHSCOPE_API_KEY` — required for any agent to actually generate content. One key
  covers Qwen (text), Wan (video), and CosyVoice (voice) — get it from the Alibaba
  Cloud Model Studio console (international workspace).
- `QWEN_MODEL`, `WAN_MODEL`, `COSYVOICE_MODEL` — model selection per capability.
- `VIDEO_PROVIDER`, `VOICE_PROVIDER`, `MUSIC_PROVIDER` — Strategy-pattern vendor
  selection (`wan`/`happyhorse`, `dashscope`/`happyhorse`, `happyhorse`/`none`).
- `DECISION_BRANCH_CANDIDATES_MIN` / `_MAX` (default 2/4) — bounds how many branch
  candidates the Decision Detector Agent may produce per decision point, to cap
  multiverse fan-out cost downstream.
- `AUTH_ENABLED` — auth middleware exists but is off by default for this build.
- Database/Redis/Celery URLs — only matter if running the API outside docker-compose;
  compose overrides them to point at the in-network `postgres`/`redis` services.

---

## Known limitations

- Only the **Story Architect**, **Character Architect**, and **Decision Detector**
  Agents are implemented end-to-end so far. Downstream agents (Timeline Generator,
  Character Memory, Storyboard, Prompt Director, Video, Voice, Music, Editor) are
  designed in `ARCHITECTURE.md` but not yet built — they're added one at a time, each
  following the Story Architect's reference pattern in `app/agents/`.
- `GET /v1/story`, `GET /v1/story/{id}`, `GET /v1/character`, and `GET /v1/character/{id}`
  all assume every row was created by their respective agent (so `world_bible` /
  `canonical_traits`+`voice_profile` deserialize into the expected typed shape). A story
  or character created via the older generic `/v1/stories` or `/v1/characters` endpoints
  has a different shape and isn't handled by these paths — `_to_profile_read` defends
  against missing keys with defaults, but the result would be mostly-empty fields.
  `decision_points` has no equivalent generic CRUD endpoint, so this particular gap
  doesn't apply to it.
- `langchain.output_parsers.OutputFixingParser` does not exist in the pinned
  langchain 1.x line — all three agents' repair/retry loop is hand-rolled in `agent.py`
  instead, and is the pattern future agents should follow.
- `CharacterArchitectAgent` enforces exactly one protagonist and rejects duplicate names
  as hard schema-level failures (triggers the retry loop); a missing antagonist (when the
  StoryBible names one) or a supporting-character count that doesn't match
  `supporting_characters_summary` only produce non-fatal warnings, since an LLM may
  reasonably merge or split characters the summary didn't fully anticipate.
- One `CharacterArchitectAgent.run()` call produces and persists the whole cast in a
  single LLM round-trip; there's no per-character regeneration endpoint yet (e.g. to fix
  just one character without regenerating the rest). The same is true of
  `DecisionDetectorAgent` and the whole decision list.
- `DecisionDetectorAgent` only detects forks - it does not create `branches` rows. Per
  `ARCHITECTURE.md`'s pipeline, that's the Timeline Generator agent's job (not yet
  built), which will take a `DecisionPoint` + a chosen `branch_candidate` and turn it
  into a concrete branch. A `DecisionList` with zero decisions is a valid, expected
  result for a linear story and is never treated as an error.
- The Celery `worker` binds to every queue in a single process for this build
  (per the approved design doc); splitting into dedicated per-queue worker pools is a
  `docker-compose.yml` change, not a code change.
