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

> Status: Story Architect, Character Architect, Decision Detector, Timeline Generator,
> Character Memory, and Storyboard Agents are complete and live-verified. Remaining
> agents (Prompt Director, Video, Voice, Music, Editor) are built incrementally, one
> at a time, on top of this foundation.

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

### Try the Timeline Generator Agent

Unlike the other three, this one needs a `project_id` too (timelines are modeled as
the root container of a *project's* branch graph) and a `decision_id` from the
Decision Detector step above:

```bash
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"title": "My Project", "premise": "..."}'
# -> {"id": "<project_id>", ...}

curl -X POST http://localhost:8000/v1/timelines/generate-branches \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<project_id>", "story_id": "<story_id>", "decision_id": "<decision_id from /v1/decision/generate above>"}'
```

This expands every `branch_candidate` on that decision into a concrete `Branch` row -
name, summary, a short script excerpt of the immediate aftermath, and the specific
fields (`affected_characters`, `affected_locations`, `emotional_impact`,
`ending_divergence`, `narrative_impact`) that the pre-existing Butterfly Score engine
(`app/services/timeline_scoring_service.py`, built before this agent) reads to compute
each branch's `butterfly_score`/`probability`/`confidence_score` - so scores stop being
structural-baseline-only the moment this agent runs. A `Timeline` and its root
`Branch` are created automatically on first use for a given (`project_id`, `story_id`)
pair. Or run the standalone demo, which runs the full pipeline built so far end to end
(it creates its own demo Project, so no setup is needed):

```bash
docker compose exec api python -m app.demo.timeline_generator
```

The branches this creates are ordinary `Branch` rows - inspect them with the
already-existing `GET /v1/branches?timeline_id=` or `GET /v1/timelines/{id}/tree`
endpoints, no new read endpoints were needed.

### Try the Character Memory Agent

Unlike the other four, this one takes only a `branch_id` - it resolves its own
character roster and branch context from already-persisted rows:

```bash
curl -X POST http://localhost:8000/v1/character-memory/generate \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "<branch_id from /v1/timelines/generate-branches above>"}'
```

This loads the branch's timeline, finds every `Character` row for that timeline's
`story_id`, and for each one resolves what changed in this specific universe
(`knowledge_state`, `emotional_state`, `relationship_changes`, `goal_shift`,
`physical_state`) plus a `drift_severity`/`drift_warning` judgment against that
character's locked `canonical_traits` - flagging when a branch pushes a character to
act in a way that contradicts who they fundamentally are. Persists one
`CharacterBranchState` row per (character, branch) pair; re-running for the same
branch updates the existing rows instead of duplicating them. A story with no
characters yet (Character Architect hasn't run) is a valid state - it returns an
empty result without spending an LLM call. Or run the standalone demo, which runs the
full pipeline built so far end to end (it creates its own demo Project):

```bash
docker compose exec api python -m app.demo.character_memory
```

The states this creates are ordinary `CharacterBranchState` rows, readable via
`GET /v1/character-memory?branch_id=` or `GET /v1/character-memory?character_id=` -
this agent owns its own router prefix since there's no pre-existing generic CRUD
resource for character/branch consistency records to share with, unlike Timeline
Generator.

### Try the Storyboard Agent

Also takes only a `branch_id` - it resolves the StoryBible, branch script
(`decision_summary.delta_script`), and per-character state (from Character Memory,
if it's run yet) on its own:

```bash
curl -X POST http://localhost:8000/v1/storyboard/generate \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "<branch_id from /v1/timelines/generate-branches above>"}'
```

This produces an ordered, contiguous shot list (`scene`, `shot_number`, `description`,
`camera`, `duration_seconds`, `characters_present`) and persists it as a `storyboard`
`Version` snapshot (per `ARCHITECTURE.md` §4.12's polymorphic version-history table,
built for this agent since nothing previously needed it) rather than a bespoke table -
re-running for the same branch adds a new `version_number` instead of overwriting
history, since re-storyboarding is an explicitly named regeneration case in that
table's own design. A `Movie` row is lazily get-or-created for the branch and moved to
`storyboarding` status, with `shot_count` written into its `metadata`. Or run the
standalone demo, which runs the full pipeline built so far end to end (it creates its
own demo Project):

```bash
docker compose exec api python -m app.demo.storyboard
```

The storyboards this creates are readable via `GET /v1/storyboard?branch_id=`
(version history, most recent first) or `GET /v1/storyboard/{version_id}`.

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
│   │                              character_branch_state, decision_point, timeline,
│   │                              branch, movie, version, asset, job, agent_log,
│   │                              prompt_history, enums, mixins (timestamps/soft-delete).
│   │                              story.project_id and character.project_id are both
│   │                              nullable (agents generate them standalone, before any
│   │                              Project exists); character.story_id and
│   │                              decision_point.story_id link generated rows back to
│   │                              the Story they were built from. character_branch_state
│   │                              has first-class drift_severity (enum) + drift_warning
│   │                              columns (queryable) alongside a state_diff JSONB blob
│   │                              for the descriptive fields, and a unique(character_id,
│   │                              branch_id) constraint. version is the polymorphic
│   │                              regeneration-history table from ARCHITECTURE.md §4.12
│   │                              (entity_type/entity_id/version_number/snapshot) - no
│   │                              FK on entity_id (it points at whichever table
│   │                              entity_type names) or created_by (no `users` table
│   │                              exists in this build; mirrors Project.owner_id).
│   └── migrations/                Alembic migrations (initial schema, butterfly-score
│                                   fields, nullable story.project_id + generation_metadata,
│                                   nullable character.project_id + story_id + generation_metadata,
│                                   new decision_points table, new character_branch_states
│                                   table, new versions table)
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
│                                  timeline_generator_service.py is the first to persist through
│                                  pre-existing, already-tested business logic (branch_service.py's
│                                  create(), which already handles depth, the sibling cap, and
│                                  butterfly-score recompute) rather than writing rows directly -
│                                  it also lazily get-or-creates the Timeline + root Branch for a
│                                  (project_id, story_id) pair on first use. character_memory_service.py
│                                  takes only a branch_id and resolves its own roster + branch
│                                  context from already-persisted rows; reruns for the same branch
│                                  update the existing CharacterBranchState rows instead of
│                                  duplicating them (the table's unique(character_id, branch_id)
│                                  constraint would otherwise reject a second insert).
│                                  storyboard_service.py also takes only a branch_id, gracefully
│                                  falling back to "not yet resolved" defaults for any character
│                                  Character Memory hasn't processed for that branch yet; it
│                                  persists through version_repository.py's generic Version table
│                                  rather than a bespoke one, and lazily get-or-creates the branch's
│                                  Movie row, moving it to `storyboarding` status.
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
│   └── timeline_generator/         Fourth agent — expands one detected decision into
│       │                            concrete universes
│       ├── agent.py                 TimelineGeneratorAgent: identical shape to the other
│       │                            three agents (ChatOpenAI + PydanticOutputParser +
│       │                            self-driven repair loop)
│       ├── schema.py                TimelineGeneratorRequest (StoryBible + one DecisionPoint
│       │                            in) + BranchDraft (name, summary,
│       │                            initial_divergent_state, delta_script, plus the five
│       │                            scoring fields below) + TimelineGenerationResult
│       ├── validators.py            Hard check: exactly one BranchDraft per
│       │                            branch_candidate, matched by candidate_label - this
│       │                            mapping is load-bearing for persistence, so a mismatch
│       │                            retries the agent rather than warning. Thin
│       │                            affected_characters / blank ending_divergence warn only.
│       └── prompts/v1/               system.txt, developer.txt, output_instructions.txt
│   └── character_memory/           Fifth agent — resolves per-character continuity for
│       │                            one branch and flags drift against canonical_traits
│       ├── agent.py                 CharacterMemoryAgent: identical shape to the other
│       │                            four agents (ChatOpenAI + PydanticOutputParser +
│       │                            self-driven repair loop), but temperature=0.4 - this
│       │                            is a consistency-checking task, not a creative one
│       ├── schema.py                CharacterMemoryRequest (BranchContext + canonical
│       │                            CharacterMemoryProfile roster in) + CharacterStateDiff
│       │                            (knowledge_state, emotional_state,
│       │                            relationship_changes, goal_shift, physical_state, plus
│       │                            drift_severity/drift_warning) + CharacterMemoryResult
│       ├── validators.py            Hard checks: exactly one CharacterStateDiff per
│       │                            input character, matched by character_name (mirrors
│       │                            Timeline Generator's candidate_label mapping); any
│       │                            drift_severity != "none" without a drift_warning
│       │                            retries the agent. Thin state_diff content / a stray
│       │                            drift_warning on drift_severity="none" warn only.
│       └── prompts/v1/               system.txt, developer.txt, output_instructions.txt
│   └── storyboard/                 Sixth agent — breaks one branch into an ordered,
│       │                            filmable shot list
│       ├── agent.py                 StoryboardAgent: identical shape to the other five
│       │                            agents (ChatOpenAI + PydanticOutputParser +
│       │                            self-driven repair loop), temperature=0.7 - a
│       │                            creative-but-grounded middle ground between
│       │                            Character Memory's 0.4 and Timeline Generator's 0.8
│       ├── schema.py                StoryboardRequest (StoryBible + branch
│       │                            name/summary/delta_script + CharacterStateSummary[]
│       │                            in) + Shot (scene, shot_number, description, camera,
│       │                            duration_seconds, characters_present) +
│       │                            StoryboardResult
│       ├── validators.py            Hard checks: at least one shot (unlike Decision
│       │                            Detector, zero is never valid here), and
│       │                            shot_number values must be unique and contiguous
│       │                            from 1 - this ordering is load-bearing for Prompt
│       │                            Director/Video Generation's per-shot fan-out.
│       │                            characters_present naming an unknown roster member,
│       │                            or a single shot's duration_seconds being
│       │                            unrealistically long, warn only.
│       └── prompts/v1/               system.txt, developer.txt, output_instructions.txt
│
├── graphs/
│   └── story_creation_graph.py     LangGraph StateGraph: START -> story_architect ->
│                                   character_architect -> decision_detector -> END. Each
│                                   downstream node reads the story node's StoryBible
│                                   directly out of graph state. Timeline Generator,
│                                   Character Memory, and Storyboard are deliberately NOT
│                                   in this graph - all three persist real DB side
│                                   effects (a Project/Timeline/Branch graph,
│                                   CharacterBranchState rows, and storyboard Version
│                                   rows, respectively, all keyed off a branch_id), which
│                                   doesn't fit this graph's pure-in-memory-agent-chaining
│                                   design; all three are invoked via their own service
│                                   instead. Future LLM-only agents extend this graph;
│                                   DB-writing agents follow that service-only pattern -
│                                   these three are also the first three nodes of the
│                                   not-yet-built movie_production_graph per
│                                   ARCHITECTURE.md §5.1.
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
    ├── decision_detector.py         python -m app.demo.decision_detector — chains
    │                                Story Architect into Decision Detector against
    │                                the live API and pretty-prints the resulting forks
    ├── timeline_generator.py        python -m app.demo.timeline_generator — runs the
    │                                full pipeline built so far (Story -> Decision ->
    │                                Timeline) against a real DB session (creates its
    │                                own demo Project), prints the created branches
    │                                with their computed butterfly scores
    ├── character_memory.py          python -m app.demo.character_memory — runs the
    │                                full pipeline built so far (Story -> Character ->
    │                                Decision -> Timeline -> Character Memory) against a
    │                                real DB session (creates its own demo Project),
    │                                prints each character's resolved state_diff +
    │                                drift judgment for the first generated branch
    └── storyboard.py                python -m app.demo.storyboard — runs the full
                                     pipeline built so far (Story -> Character ->
                                     Decision -> Timeline -> Character Memory ->
                                     Storyboard) against a real DB session (creates its
                                     own demo Project), prints the ordered shot list for
                                     the first generated branch
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
│                                    TimelineGenerationResult/CharacterMemoryResult/
│                                    StoryboardResult/AgentRunResult builders, reused
│                                    across agents/services/routers/graph tests
├── agents/                          Unit tests per agent: schema validation, semantic
│                                    validators, agent retry/repair logic (mocked LLM), +
│                                    one live test per agent gated behind RUN_LIVE_API_TESTS=1
├── graphs/                          LangGraph node wiring test (story_architect ->
│                                    character_architect -> decision_detector, all 3 mocked;
│                                    timeline_generator is intentionally not part of this graph)
├── services/                        Service-layer tests against a real transactional DB.
│                                    test_timeline_generator_service.py also exercises the
│                                    pre-existing branch_service.py/timeline_scoring_service.py
│                                    it persists through (sibling cap, score recompute, depth)
└── routers/                         Full HTTP lifecycle tests (generate -> get -> list
                                     -> delete -> 404) via the ASGI test client
```

Run the suite:

```bash
docker compose exec api pytest                                   # full suite
docker compose exec api pytest --cov=app --cov-report=term-missing  # with coverage
RUN_LIVE_API_TESTS=1 docker compose exec -e RUN_LIVE_API_TESTS=1 api pytest tests/agents/test_story_architect_live.py tests/agents/test_character_architect_live.py tests/agents/test_decision_detector_live.py tests/agents/test_timeline_generator_live.py tests/agents/test_character_memory_live.py tests/agents/test_storyboard_live.py
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
| POST | `/v1/timelines/generate-branches` | Run the Timeline Generator Agent on a `decision_id`; persists and returns one `Branch` per `branch_candidate`, with scores computed |
| POST | `/v1/character-memory/generate` | Run the Character Memory Agent on a `branch_id`; persists and returns one `CharacterStateRead` per character in that branch's story |
| GET | `/v1/character-memory/{id}` | Fetch one persisted character/branch state by id |
| GET | `/v1/character-memory?branch_id=&character_id=` | Cursor-paginated list of persisted states, optionally filtered by branch and/or character |
| DELETE | `/v1/character-memory/{id}` | Soft-delete a persisted character/branch state |
| POST | `/v1/storyboard/generate` | Run the Storyboard Agent on a `branch_id`; persists a new `storyboard` Version and returns its ordered shot list |
| GET | `/v1/storyboard/{version_id}` | Fetch one persisted storyboard version by id |
| GET | `/v1/storyboard?branch_id=` | Cursor-paginated version history for a branch's storyboard, most recent first |
| DELETE | `/v1/storyboard/{version_id}` | Soft-delete a persisted storyboard version |
| `/v1/projects`, `/v1/stories`, `/v1/timelines`, `/v1/branches`, `/v1/movies`, `/v1/characters`, `/v1/assets`, `/v1/jobs`, `/v1/agent-logs`, `/v1/prompt-history` | Generic CRUD endpoints for the underlying domain model (project-scoped resources used by the broader pipeline as more agents come online) - `GET /v1/branches?timeline_id=` and `GET /v1/timelines/{id}/tree` are how you read back what Timeline Generator created, no new read endpoints needed |

### Example: generate a story, then its cast, its forks, and its branches

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
# -> {"story_id": "<story_id>", "decisions": [{"id": "<decision_id>", "beat_index": 0, "branch_candidates": [...]}], ...}

curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"title": "...", "premise": "..."}'
# -> {"id": "<project_id>", ...}

curl -X POST http://localhost:8000/v1/timelines/generate-branches \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<project_id>", "story_id": "<story_id>", "decision_id": "<decision_id>"}'
# -> {"timeline_id": "<timeline_id>", "branches": [{"id": "<branch_id>", "butterfly_score": 65, ...}, ...], ...}

curl -X POST http://localhost:8000/v1/character-memory/generate \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "<branch_id>"}'
# -> {"branch_id": "<branch_id>", "states": [{"character_name": "...", "drift_severity": "none", ...}, ...], ...}

curl -X POST http://localhost:8000/v1/storyboard/generate \
  -H "Content-Type: application/json" \
  -d '{"branch_id": "<branch_id>"}'
# -> {"branch_id": "<branch_id>", "version_number": 1, "shots": [{"shot_number": 1, "scene": "...", ...}, ...], ...}
```

Story generate returns a `StoryGenerateResponse`: the full 21-field `StoryBible`, plus
generation provenance (`model`, `prompt_version`, `latency_ms`, `attempts`, token counts).
Character generate returns a `CharacterGenerateResponse`: one full `CharacterProfileRead`
per cast member (role, physical/voice descriptors, backstory, arc, relationships, ...).
Decision generate returns a `DecisionGenerateResponse`: zero or more `DecisionPointRead`
entries (each with 2-4 `branch_candidates`, every candidate carrying a `label`,
`description`, `tone_shift`, and `divergence_summary`). Timeline generate-branches
returns a `TimelineGenerateBranchesResponse`: the resolved `timeline_id` plus one
`BranchRead` per candidate - the existing `BranchRead` shape already has
`butterfly_score`/`probability`/`confidence_score`/`stability_explanation`, now
populated with real values instead of structural-baseline ones. Character Memory
generate returns a `CharacterMemoryGenerateResponse`: the resolved `story_id` plus one
`CharacterStateRead` per character in that story (`state_diff`, `drift_severity`,
`drift_warning`). Storyboard generate returns a `StoryboardGenerateResponse`: the
resolved `movie_id` and `version_id`/`version_number` plus the ordered `shots` list
(`scene`, `shot_number`, `description`, `camera`, `duration_seconds`,
`characters_present`). All six share the same generation-provenance shape (`model`,
`prompt_version`, `latency_ms`, `attempts`, token counts) - Character Memory's is all
zero/`"n/a"` in the one case where it skips the LLM call entirely (a story with no
characters yet).

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

- Only the **Story Architect**, **Character Architect**, **Decision Detector**,
  **Timeline Generator**, **Character Memory**, and **Storyboard** Agents are
  implemented end-to-end so far. Downstream agents (Prompt Director, Video, Voice,
  Music, Editor) are designed in `ARCHITECTURE.md` but not yet built — they're added
  one at a time, each following the Story Architect's reference pattern in
  `app/agents/`.
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
- `DecisionDetectorAgent` only detects forks - it does not create `branches` rows.
  `TimelineGeneratorAgent` does that, by expanding ALL of a decision's
  `branch_candidates` into concrete `Branch` rows in one call. A `DecisionList` with
  zero decisions is a valid, expected result for a linear story and is never treated
  as an error.
- `TimelineGeneratorAgent` requires an explicit `project_id`, unlike the other three
  agents which can run fully standalone against just a `story_id`. This is a real
  schema constraint, not an oversight: `Timeline.project_id` is `NOT NULL` by design
  (`ARCHITECTURE.md` models a timeline as "the root container of a *project's* branch
  graph"), and that constraint was deliberately left alone rather than weakened to
  match the other agents' standalone-friendly pattern.
- Per `ARCHITECTURE.md`'s "fan-out per decision" framing, a full pipeline run would call
  Timeline Generator once per detected decision automatically. This build calls it
  once per `decision_id` you explicitly pass in - there's no orchestration yet that
  loops over every decision in a `DecisionList` and fans out automatically, and no
  handling yet for the "zero decisions -> single-branch linear timeline" finalization
  case beyond the root branch that's lazily created on first use.
- `CharacterMemoryAgent` resolves drift purely via the LLM's judgment against
  `canonical_traits` text - `ARCHITECTURE.md` also specifies Qdrant-backed embedding
  similarity checks across sibling branches for consistency, which isn't wired up in
  this build (no Qdrant integration exists yet; `Character.embedding_id` stays unset).
- `CharacterMemoryAgent` runs once per `branch_id` you explicitly pass in - like
  Timeline Generator, there's no orchestration yet that automatically runs it for
  every newly created branch. Re-running it for the same branch updates the existing
  `CharacterBranchState` rows in place rather than creating duplicates or erroring on
  the table's unique constraint.
- `StoryboardAgent` works correctly with no `CharacterMemoryAgent` run yet for a given
  branch - characters Character Memory hasn't resolved fall back to "Not yet resolved
  for this branch." text rather than blocking storyboarding on a prior agent run, since
  ARCHITECTURE.md doesn't make that ordering a hard dependency.
- `StoryboardAgent` runs once per `branch_id` you explicitly pass in, same as the other
  branch-scoped agents - no automatic per-branch orchestration yet. Re-running it adds
  a new `storyboard` `Version` (`version_number` increments) rather than overwriting
  the previous one, since the `versions` table is explicitly designed for regeneration
  history; this is the one branch-scoped agent so far where reruns are additive rather
  than in-place updates.
- The Celery `worker` binds to every queue in a single process for this build
  (per the approved design doc); splitting into dedicated per-queue worker pools is a
  `docker-compose.yml` change, not a code change.
