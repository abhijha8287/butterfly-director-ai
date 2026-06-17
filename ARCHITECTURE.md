# Butterfly Director AI — System Architecture

Version 1.0 · Architecture-only deliverable (no implementation code)

---

## 0. Product Summary

Butterfly Director AI turns a single story premise into a **branching multiverse of fully generated short films**. A user submits an idea; the system identifies the pivotal decisions inside that story, forks a new timeline (universe) at each decision, and independently produces a complete short movie (script → storyboard → shots → video → voice → music → edit) for every branch. The result is explored as an interactive graph — Git-branch semantics applied to narrative, rendered as a Netflix-grade media library.

Three product pillars drive every architecture decision below:

1. **Branch identity is permanent.** A timeline/branch is a first-class, versioned entity — never a transient render. Anything generated against it must be reproducible and auditable.
2. **Agents are isolated, replaceable units of cognition.** Each agent in the pipeline owns one concern, communicates through typed contracts, and can be swapped (e.g. Wan → another video model) without touching neighboring agents.
3. **Generation is asynchronous and resumable by default.** Every expensive step (LLM call, video render, TTS, mix) is a Celery job with persisted state, so a crashed worker never loses the user's place in a multiverse.

---

## 1. Complete Folder Structure

### 1.1 Repository Layout (monorepo)

```
butterfly-director-ai/
├── apps/
│   ├── web/                         # Next.js 15 frontend
│   └── api/                         # FastAPI backend
├── packages/
│   ├── shared-types/                # OpenAPI-generated TS types + Pydantic-mirrored enums (source of truth: api/schemas)
│   └── prompt-templates/            # Versioned prompt templates shared by agents (jinja2 + json schema)
├── infra/
│   ├── docker/
│   ├── nginx/
│   ├── migrations/                  # Alembic migrations (mirrors apps/api/app/db/migrations)
│   └── scripts/                     # seed, backup, restore, oss-bootstrap
├── docs/
│   ├── architecture/                # this document + ADRs
│   ├── api/                         # generated OpenAPI spec snapshots
│   └── runbooks/
├── docker-compose.yml
├── docker-compose.override.yml      # local dev overrides
├── .env.example
└── README.md
```

### 1.2 Backend — `apps/api/`

```
apps/api/
├── app/
│   ├── main.py                       # FastAPI app factory, router mounting, lifespan
│   ├── config/
│   │   ├── settings.py               # pydantic-settings, env-driven
│   │   ├── logging.py                # structlog/loguru configuration
│   │   └── constants.py
│   ├── core/
│   │   ├── security.py               # password hashing, JWT issuance/verification
│   │   ├── deps.py                   # FastAPI Depends() providers (db session, current_user, rate-limiter)
│   │   ├── exceptions.py             # domain exception hierarchy
│   │   ├── pagination.py
│   │   └── middleware/
│   │       ├── request_id.py
│   │       ├── error_handler.py
│   │       ├── auth.py               # modular, toggled via FEATURE_AUTH_ENABLED
│   │       ├── rate_limit.py
│   │       └── logging_middleware.py
│   ├── db/
│   │   ├── base.py                   # SQLAlchemy Base / async engine / session factory
│   │   ├── models/                   # one file per aggregate (see §4)
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── timeline.py
│   │   │   ├── branch.py
│   │   │   ├── movie.py
│   │   │   ├── character.py
│   │   │   ├── asset.py
│   │   │   ├── prompt.py
│   │   │   ├── job.py
│   │   │   ├── agent_log.py
│   │   │   ├── version.py
│   │   │   └── event.py
│   │   ├── migrations/               # Alembic env + versions/
│   │   └── seed/
│   ├── repositories/                 # one repository per aggregate, pure data access
│   │   ├── base_repository.py
│   │   ├── user_repository.py
│   │   ├── project_repository.py
│   │   ├── timeline_repository.py
│   │   ├── branch_repository.py
│   │   ├── movie_repository.py
│   │   ├── character_repository.py
│   │   ├── asset_repository.py
│   │   ├── job_repository.py
│   │   └── agent_log_repository.py
│   ├── schemas/                      # Pydantic request/response/DTO models
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── timeline.py
│   │   ├── branch.py
│   │   ├── movie.py
│   │   ├── character.py
│   │   ├── asset.py
│   │   ├── job.py
│   │   ├── agent_io.py               # typed contracts each agent consumes/produces
│   │   └── common.py                 # Page[T], ErrorResponse, etc.
│   ├── services/                     # business orchestration, agent-agnostic
│   │   ├── auth_service.py
│   │   ├── project_service.py
│   │   ├── timeline_service.py       # graph mutation, branch creation, merge/prune
│   │   ├── story_service.py          # kicks off Story Architect + Decision Detector
│   │   ├── movie_service.py          # orchestrates storyboard → prompt → video → voice → music → edit
│   │   ├── character_service.py
│   │   ├── storage_service.py        # OSS abstraction (presigned URLs, multipart upload)
│   │   ├── video_service.py          # Wan/HappyHorse client abstraction + provider routing
│   │   ├── voice_service.py
│   │   ├── music_service.py
│   │   ├── notification_service.py   # websocket/event push to frontend
│   │   └── billing_service.py        # stub, modular, off by default
│   ├── routers/                      # thin HTTP layer, versioned
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── projects.py
│   │       ├── timelines.py
│   │       ├── branches.py
│   │       ├── movies.py
│   │       ├── characters.py
│   │       ├── assets.py
│   │       ├── jobs.py
│   │       ├── agents.py             # introspection: agent run logs, retries
│   │       ├── events.py             # SSE/websocket endpoint for live job updates
│   │       └── health.py
│   ├── agents/                       # see §5 — one folder per agent, isolated
│   │   ├── base/
│   │   │   ├── base_agent.py         # Agent ABC: run(), validate_input(), validate_output()
│   │   │   ├── agent_context.py      # shared context object passed through LangGraph
│   │   │   └── agent_registry.py
│   │   ├── story_architect/
│   │   ├── decision_detector/
│   │   ├── timeline_generator/
│   │   ├── character_memory/
│   │   ├── storyboard/
│   │   ├── prompt_director/
│   │   ├── video_generation/
│   │   ├── voice/
│   │   ├── music/
│   │   └── editor/
│   ├── graphs/                       # LangGraph state-machine definitions
│   │   ├── story_creation_graph.py   # Story Architect → Decision Detector → Timeline Generator
│   │   ├── movie_production_graph.py # Character Memory → Storyboard → Prompt Director → Video → Voice → Music → Editor
│   │   └── state.py                  # shared TypedDict/Pydantic graph state
│   ├── workers/                      # Celery app + tasks
│   │   ├── celery_app.py
│   │   ├── queues.py                 # queue name constants + routing table
│   │   ├── tasks/
│   │   │   ├── story_tasks.py
│   │   │   ├── timeline_tasks.py
│   │   │   ├── movie_tasks.py
│   │   │   ├── video_tasks.py
│   │   │   ├── voice_tasks.py
│   │   │   ├── music_tasks.py
│   │   │   ├── editor_tasks.py
│   │   │   └── maintenance_tasks.py  # cleanup, retries, OSS lifecycle
│   │   └── callbacks.py              # success/failure hooks → job_repository + notification_service
│   ├── integrations/                 # outbound third-party clients
│   │   ├── qwen_client.py
│   │   ├── wan_client.py
│   │   ├── happyhorse_client.py
│   │   ├── oss_client.py
│   │   ├── qdrant_client.py
│   │   └── redis_client.py
│   └── utils/
│       ├── retry.py
│       ├── prompt_loader.py
│       ├── media_probe.py            # ffprobe wrappers for duration/codec checks
│       └── ids.py                    # ULID/UUID generation
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

### 1.3 Frontend — `apps/web/` (folder structure only, per spec)

```
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── projects/
│   │   │   ├── page.tsx                       # project list
│   │   │   ├── new/page.tsx                   # Create Project Wizard entry
│   │   │   └── [projectId]/
│   │   │       ├── page.tsx                   # project overview
│   │   │       ├── timeline/page.tsx          # Timeline Explorer (React Flow canvas)
│   │   │       ├── story-editor/page.tsx
│   │   │       ├── characters/page.tsx        # Character Manager
│   │   │       └── movies/[movieId]/page.tsx  # Movie Player
│   │   └── settings/
│   │       ├── page.tsx
│   │       ├── account/page.tsx
│   │       └── billing/page.tsx
│   ├── api/                                   # Next.js route handlers (BFF passthrough/streaming proxy only)
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ui/                                    # shadcn/ui primitives
│   ├── timeline/
│   │   ├── TimelineCanvas.tsx
│   │   ├── nodes/
│   │   │   ├── UniverseNode.tsx
│   │   │   ├── MovieNode.tsx
│   │   │   ├── DecisionNode.tsx
│   │   │   └── BranchEdge.tsx
│   │   ├── TimelineMinimap.tsx
│   │   └── TimelineControls.tsx
│   ├── movie-player/
│   ├── story-editor/
│   ├── character-manager/
│   ├── wizard/
│   │   └── steps/
│   ├── shared/
│   └── layout/
├── hooks/
│   ├── useTimelineGraph.ts
│   ├── useMovieGeneration.ts
│   ├── useJobStream.ts                        # SSE/websocket subscription hook
│   └── useAgentStatus.ts
├── lib/
│   ├── api-client.ts                          # typed fetch wrapper (uses packages/shared-types)
│   ├── websocket-client.ts
│   └── utils.ts
├── store/                                     # Zustand
│   ├── timelineStore.ts
│   ├── projectStore.ts
│   ├── playerStore.ts
│   ├── wizardStore.ts
│   └── uiStore.ts
├── styles/
├── types/
├── public/
├── next.config.ts
├── tailwind.config.ts
└── Dockerfile
```

---

## 2. System Architecture

### 2.1 Layered View

```
┌──────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js)                                                 │
│  Dashboard · Timeline Explorer (React Flow) · Movie Player ·       │
│  Story Editor · Character Manager · Wizard · Settings              │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ REST (CRUD) + SSE/WebSocket (live job/agent events)
┌───────────────────────────────▼────────────────────────────────────┐
│ FastAPI Backend                                                     │
│  Routers → Services → Repositories → PostgreSQL                    │
│  Middleware: request-id, auth (modular), rate-limit, error-handler │
│  Storage Service ↔ Alibaba OSS · Timeline Service ↔ graph mutation  │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ enqueue (Celery) / direct invoke (sync graph compile)
┌───────────────────────────────▼────────────────────────────────────┐
│ LangGraph Multi-Agent Orchestration                                  │
│  story_creation_graph:  Story Architect → Decision Detector →       │
│                          Timeline Generator                          │
│  movie_production_graph: Character Memory → Storyboard →            │
│       Prompt Director → Video Generation → Voice → Music → Editor   │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ provider calls
┌───────────────────────────────▼────────────────────────────────────┐
│ Video Generation Pipeline                                            │
│  Qwen (text/reasoning) · Wan (video) · HappyHorse (video/voice)      │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ persist
┌───────────────────────────────▼────────────────────────────────────┐
│ Databases                                                            │
│  PostgreSQL (system of record) · Redis (cache/queue/pubsub) ·        │
│  Qdrant (character/lore embeddings for consistency retrieval)        │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ rendered graph + media URLs
┌───────────────────────────────▼────────────────────────────────────┐
│ Timeline Graph (client-rendered from /timelines/{id}/graph)          │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Request/Response Topology

- **Synchronous path**: all CRUD (projects, characters, settings, listing timelines) → Router → Service → Repository → Postgres → response. P99 target < 200ms.
- **Asynchronous path**: anything that calls an LLM or video model → Router enqueues a Celery task (or triggers a LangGraph run inside a worker), returns `202 Accepted` + `job_id` immediately. Frontend subscribes to `/v1/events/jobs/{job_id}` (SSE) for progress.
- **Fan-out path**: Timeline Generator Agent can produce N branches from one decision → N independent `movie_production_graph` runs are enqueued in parallel, each tracked as its own `Job` row, all linked to the same `decision_id`.

---

## 3. Module Responsibilities

| Module | Responsibility | Must NOT do |
|---|---|---|
| `routers/` | Parse/validate HTTP I/O, map to service calls, set status codes | Contain business logic or DB queries |
| `services/` | Orchestrate use cases, enforce business rules, call repositories/agents/integrations | Know about HTTP (no `Request`/`Response` objects), no raw SQL |
| `repositories/` | CRUD + query composition against SQLAlchemy models | Contain business rules, never call other repositories' transactions implicitly |
| `schemas/` | Define and validate shape of data crossing boundaries (HTTP and agent I/O) | Contain logic beyond validators |
| `db/models/` | Define persistence shape + relationships | Contain business logic |
| `agents/*` | Implement one cognitive responsibility behind `BaseAgent.run(context) -> AgentResult` | Call repositories directly — agents talk to the graph/service layer only, never touch Postgres directly (keeps agents portable/testable) |
| `graphs/` | Wire agents into LangGraph state machines, define conditional edges (e.g., "if decision_count == 0, skip Timeline Generator") | Implement agent logic inline |
| `workers/tasks/` | Celery task wrappers: idempotency keys, retry policy, status updates | Implement business/agent logic — tasks call services/graphs |
| `integrations/` | Thin typed clients for Qwen/Wan/HappyHorse/OSS/Qdrant/Redis with retry+timeout | Contain prompt construction or business rules |
| `core/middleware` | Cross-cutting concerns (auth, logging, rate limit, error shaping) | Contain feature logic |
| `storage_service` | Single point of truth for all OSS reads/writes, key naming, presigned URL issuance | Be bypassed by any other module performing direct OSS calls |
| `timeline_service` | All graph topology mutations (create branch, attach decision, prune, merge metadata) | Generate creative content itself |
| `video_service` | Provider-agnostic façade choosing Wan vs HappyHorse per project config/fallback policy | Hardcode a single provider into callers |

---

## 4. Database Design (PostgreSQL)

All tables: `id UUID PK DEFAULT gen_random_uuid()`, `created_at`, `updated_at` (trigger-maintained), soft-delete via `deleted_at NULLABLE` unless noted. Foreign keys `ON DELETE RESTRICT` unless noted.

### 4.1 `users`
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| email | citext | unique, indexed |
| password_hash | text | nullable (OAuth-only accounts) |
| display_name | text | |
| role | enum(`owner`,`admin`,`member`,`viewer`) | default `member` |
| auth_provider | enum(`local`,`google`,`github`) | |
| is_active | boolean | default true |
| last_login_at | timestamptz | |

### 4.2 `projects`
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| owner_id | uuid | FK→users.id |
| title | text | |
| premise | text | the original story idea |
| genre | text | |
| tone | text | |
| status | enum(`draft`,`generating`,`ready`,`archived`) | |
| settings | jsonb | per-project generation config (video provider, voice profile, aspect ratio) |

### 4.3 `timelines`
A *timeline* is the root container of a project's branch graph (typically one per project, but modeled separately to allow multi-timeline projects later).
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK→projects.id |
| root_branch_id | uuid | FK→branches.id, nullable until root created |
| title | text | |
| world_bible | jsonb | output of Story Architect: world/characters/lore/genre/tone snapshot |
| status | enum(`pending`,`active`,`completed`) | |

### 4.4 `branches`
The graph node/edge unit. Self-referencing for tree/DAG structure.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| timeline_id | uuid | FK→timelines.id |
| parent_branch_id | uuid | FK→branches.id, nullable (root) |
| decision_id | uuid | FK→events.id (the decision event that spawned this branch), nullable for root |
| name | text | e.g. "Universe 3: Time Loop Collapse" |
| summary | text | |
| depth | integer | denormalized for fast graph layout |
| position | jsonb | `{x, y}` cached React Flow layout hint |
| status | enum(`pending`,`producing`,`completed`,`failed`,`pruned`) | |
| is_canonical | boolean | default false; marks the "main" branch |

### 4.5 `movies`
One produced film per branch (1:1, but modeled separately for versioning/re-renders).
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| branch_id | uuid | FK→branches.id, unique |
| title | text | |
| duration_seconds | integer | |
| status | enum(`queued`,`storyboarding`,`rendering`,`scoring`,`assembling`,`completed`,`failed`) | |
| final_asset_id | uuid | FK→assets.id, nullable until assembled |
| metadata | jsonb | shot count, resolution, codec, model versions used |

### 4.6 `characters`
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK→projects.id |
| name | text | |
| description | text | |
| visual_reference_asset_id | uuid | FK→assets.id, nullable |
| voice_profile | jsonb | TTS voice id/params |
| embedding_id | text | pointer to Qdrant point id (consistency vector) |
| canonical_traits | jsonb | locked traits that must not drift across branches |

### 4.7 `character_branch_states` (join — character consistency per branch)
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| character_id | uuid | FK→characters.id |
| branch_id | uuid | FK→branches.id |
| state_diff | jsonb | what changed for this character in this universe |
| unique(character_id, branch_id) | | |

### 4.8 `assets`
Generic media row — every image/video/audio file the system owns.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK→projects.id |
| owner_type | enum(`movie`,`character`,`shot`,`voice`,`music`,`storyboard`) | |
| owner_id | uuid | polymorphic reference, indexed |
| kind | enum(`image`,`video`,`audio`,`json`) | |
| oss_key | text | full object key, unique |
| oss_bucket | text | |
| mime_type | text | |
| size_bytes | bigint | |
| duration_seconds | numeric | nullable, for audio/video |
| checksum_sha256 | text | |

### 4.9 `prompts`
Every prompt sent to an external model, kept for audit/replay/cost analysis.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| branch_id | uuid | FK→branches.id |
| agent_name | text | which agent issued it |
| stage | enum(`story`,`storyboard`,`shot_prompt`,`video`,`voice`,`music`) | |
| provider | enum(`qwen`,`wan`,`happyhorse`) | |
| input_payload | jsonb | |
| rendered_prompt | text | |
| response_payload | jsonb | nullable until completed |
| token_usage | jsonb | nullable |

### 4.10 `jobs`
Celery task tracking, decoupled from Celery's own result backend so the API can query without touching Celery internals.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| celery_task_id | text | unique, indexed |
| job_type | enum(`story_generation`,`decision_detection`,`timeline_branch`,`storyboard`,`video_render`,`voice_synthesis`,`music_generation`,`editing`) | |
| branch_id | uuid | FK→branches.id, nullable (story-level jobs reference timeline_id instead) |
| timeline_id | uuid | FK→timelines.id, nullable |
| status | enum(`queued`,`running`,`succeeded`,`failed`,`retrying`,`cancelled`) | |
| progress_pct | smallint | 0–100 |
| attempt | smallint | default 1 |
| error_message | text | nullable |
| started_at | timestamptz | |
| finished_at | timestamptz | |

### 4.11 `agent_logs`
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| job_id | uuid | FK→jobs.id, nullable |
| branch_id | uuid | FK→branches.id, nullable |
| agent_name | text | indexed |
| input_snapshot | jsonb | |
| output_snapshot | jsonb | |
| latency_ms | integer | |
| status | enum(`success`,`error`,`validation_failed`) | |
| error_detail | text | nullable |

### 4.12 `versions`
Tracks regenerations of any creative artifact (re-render a branch, re-storyboard, edit a script) without losing history.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| entity_type | enum(`timeline`,`branch`,`movie`,`character`,`storyboard`) | |
| entity_id | uuid | polymorphic, indexed |
| version_number | integer | |
| snapshot | jsonb | full state at this version |
| created_by | uuid | FK→users.id |
| unique(entity_type, entity_id, version_number) | | |

### 4.13 `events`
Append-only domain event log — decisions, branch creation, job completion, user actions. Doubles as the source for `decision_id` references and for the activity feed.
| column | type | notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK→projects.id |
| branch_id | uuid | FK→branches.id, nullable |
| event_type | enum(`decision_detected`,`branch_created`,`movie_completed`,`job_failed`,`character_drift_detected`,`user_edit`) | |
| payload | jsonb | |
| actor_type | enum(`agent`,`user`,`system`) | |
| actor_id | text | agent name or user id |

### 4.14 Indices & Constraints (key ones)
- `branches(timeline_id, parent_branch_id)` composite index — graph traversal.
- `assets(owner_type, owner_id)` composite index — polymorphic lookups.
- `jobs(status, job_type)` partial index where `status IN ('queued','running')` — worker dashboards.
- `events(project_id, created_at DESC)` — activity feed pagination.
- `agent_logs(agent_name, created_at DESC)` — per-agent observability.

---

## 5. Agent Responsibilities (LangGraph Multi-Agent System)

Every agent folder under `apps/api/app/agents/<name>/` follows the same internal shape:

```
<agent_name>/
├── agent.py        # class XAgent(BaseAgent): run(context) -> AgentResult
├── prompts/         # versioned prompt templates (jinja2)
├── schema.py        # Pydantic input/output contract for this agent only
└── validators.py     # output validation / repair logic
```

`BaseAgent` contract: `validate_input(ctx) -> None`, `run(ctx) -> AgentResult`, `validate_output(result) -> None`. Every run is wrapped by the graph executor to write one `agent_logs` row regardless of success/failure.

1. **Story Architect Agent** — Input: project premise, genre hint. Output: world bible (setting, rules, tone), character roster with archetypes, lore primer. Writes `timelines.world_bible`. Calls Qwen.
2. **Decision Detector Agent** — Input: world bible + generated outline/script beats. Output: ordered list of decision points (`{beat_index, description, branch_candidates[]}`). Each candidate becomes a future `branches` row. Calls Qwen with structured-output prompting; validates count is within configured min/max (default 2–4 branches per decision) to bound fan-out cost.
3. **Timeline Generator Agent** — Input: a decision + its branch candidates. Output: concrete `branches` rows (name, summary, initial divergent state) plus a delta-script for each universe. Calls `timeline_service` to persist nodes/edges.
4. **Character Memory Agent** — Input: character roster + target branch. Output: per-character `state_diff` for this branch, drift warnings if a trait contradicts `canonical_traits`. Reads/writes Qdrant embeddings for similarity-based consistency checks across sibling branches; writes `character_branch_states`.
5. **Storyboard Agent** — Input: branch script + character states. Output: ordered shot list (`scene, shot_number, description, camera, duration, characters_present[]`). Persisted as a `storyboard` version under `versions`.
6. **Prompt Director Agent** — Input: storyboard shots. Output: provider-optimized generation prompts per shot (one row per shot in `prompts`, `stage='shot_prompt'`), including negative prompts and style/consistency tokens derived from Character Memory output.
7. **Video Generation Agent** — Input: shot prompts. Output: rendered shot video assets via `video_service` (Wan primary, HappyHorse fallback/alternate). Handles per-shot retry with prompt back-off on provider rejection; writes `assets` rows + `prompts.response_payload`.
8. **Voice Agent** — Input: dialogue lines + character voice profiles. Output: narration/dialogue audio assets, time-coded for editor alignment. Calls HappyHorse (or configured TTS provider) via `voice_service`.
9. **Music Agent** — Input: branch tone/genre + scene emotional beats. Output: music *generation prompts* (and/or generated stems if provider supports it), tempo/mood metadata for the Editor Agent to sync against.
10. **Editor Agent** — Input: all shot videos + voice + music assets for a branch. Output: assembled final movie asset (`movies.final_asset_id`), via server-side ffmpeg composition job; writes final `movies` status transitions.

### 5.1 Graph Wiring

- `story_creation_graph`: `Story Architect → Decision Detector → Timeline Generator (fan-out per decision)`. Conditional edge: if Decision Detector returns zero decisions, terminate with a single-branch (linear) timeline.
- `movie_production_graph` (run once per branch, in parallel across branches): `Character Memory → Storyboard → Prompt Director → Video Generation (fan-out per shot) → [Voice, Music in parallel] → Editor`.
- Both graphs persist a checkpoint after every node (LangGraph checkpointer backed by Postgres) so a failed run resumes from the last successful node, not from scratch.

---

## 6. API Planning (REST, versioned under `/v1`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/auth/register` | create account |
| POST | `/v1/auth/login` | issue JWT |
| POST | `/v1/auth/refresh` | refresh token |
| GET | `/v1/users/me` | current user |
| POST | `/v1/projects` | create project from premise → enqueues `story_creation_graph` |
| GET | `/v1/projects` | list (paginated, filter by status) |
| GET | `/v1/projects/{id}` | detail |
| PATCH | `/v1/projects/{id}` | update title/settings |
| DELETE | `/v1/projects/{id}` | soft delete |
| GET | `/v1/projects/{id}/timeline` | full timeline graph (nodes+edges, denormalized for React Flow) |
| POST | `/v1/timelines/{id}/branches` | manually force a branch (user-authored decision) |
| GET | `/v1/branches/{id}` | branch detail incl. movie status |
| POST | `/v1/branches/{id}/regenerate` | re-run `movie_production_graph` for this branch (new `version`) |
| DELETE | `/v1/branches/{id}` | prune branch (soft, cascades to its subtree as `pruned` status, not hard delete) |
| GET | `/v1/movies/{id}` | movie detail + playback URL (presigned OSS) |
| GET | `/v1/movies/{id}/shots` | shot-level breakdown (storyboard + per-shot asset) |
| GET | `/v1/characters?project_id=` | list characters |
| POST | `/v1/characters` | manually add/edit character |
| GET | `/v1/characters/{id}/states` | per-branch state diffs (consistency view) |
| GET | `/v1/jobs/{id}` | job status/progress |
| POST | `/v1/jobs/{id}/cancel` | request cancellation |
| GET | `/v1/agents/logs?branch_id=` | agent run history for debugging a branch |
| GET | `/v1/events?project_id=&cursor=` | activity feed, cursor-paginated |
| GET | `/v1/events/stream/{job_id}` | SSE stream of job/agent progress |
| WS | `/v1/ws/projects/{id}` | live graph updates (branch created, movie completed) pushed to Timeline Explorer |
| GET | `/v1/health` , `/v1/health/ready` | liveness/readiness |

All list endpoints: cursor-based pagination, `?limit=&cursor=`. All mutating endpoints return the updated resource, never bare `204`, so the frontend can update Zustand state directly from the response.

---

## 7. Event Flow (end-to-end)

1. User submits premise via Create Project Wizard → `POST /v1/projects`.
2. `project_service` creates `projects` + `timelines` rows (status `pending`), enqueues `story_creation_graph` Celery task, returns `202` with `job_id`.
3. Worker runs **Story Architect** → writes `world_bible`, emits `events(event_type='world_built')`.
4. **Decision Detector** runs against the world bible/outline → emits `events(event_type='decision_detected')` per decision, persists candidate count.
5. For each decision, **Timeline Generator** creates N `branches` rows → emits `events(event_type='branch_created')` per branch → frontend's `/v1/ws/projects/{id}` pushes a graph-update message → React Flow adds nodes live.
6. For each new branch, backend enqueues a `movie_production_graph` Celery task (parallel fan-out, bounded by a per-project concurrency limit enforced via a Redis semaphore).
7. **Character Memory** resolves per-branch character state, flags drift → if drift severity exceeds threshold, emits `events(event_type='character_drift_detected')` and either auto-corrects (default) or pauses for user review (configurable).
8. **Storyboard Agent** produces shot list → version snapshot written.
9. **Prompt Director** converts shots to provider prompts → `prompts` rows created.
10. **Video Generation Agent** fans out per-shot render jobs → each shot is its own Celery task with its own retry policy; `movies.status = 'rendering'`; per-shot completion updates `jobs.progress_pct` on the parent movie job.
11. **Voice** and **Music** agents run concurrently with/after Video Generation (voice can start as soon as dialogue lines exist; music can start as soon as tone/duration are known).
12. **Editor Agent** waits (LangGraph join) on shots + voice + music completion → assembles final cut via ffmpeg worker → writes `assets` (final video) → `movies.status='completed'` → emits `events(event_type='movie_completed')`.
13. Frontend receives the completion event over the websocket/SSE channel, updates `timelineStore`/`playerStore`, surfaces the new movie node as "ready" in the Timeline Explorer without a manual refresh.
14. Any failure at any step: task retried per policy (§9); after max retries, `jobs.status='failed'`, `events(event_type='job_failed')` emitted, surfaced as an actionable error in the UI with a "Retry" action calling `POST /v1/jobs/{id}/cancel` + branch `regenerate`.

---

## 8. Redis Usage

| Use case | Mechanism | Notes |
|---|---|---|
| Celery broker | Redis list/streams (or RabbitMQ-compatible mode if scaled later) | Default broker for dev/small scale; documented as swappable |
| Celery result backend | Redis | TTL'd results; source of truth remains Postgres `jobs` table |
| API response cache | Redis `GET/SETEX` | Cache `/v1/projects/{id}/timeline` graph payload (invalidated on any `branch_created`/`movie_completed` event) |
| Rate limiting | Redis token bucket (`INCR` + `EXPIRE`) | Per-user and per-IP, enforced in `rate_limit` middleware |
| Distributed locks | Redis `SET NX EX` (redlock-style for single-instance Redis) | Prevent duplicate Decision Detector runs on the same timeline, guard concurrent branch regeneration |
| Concurrency semaphore | Redis counter | Bounds parallel `movie_production_graph` runs per project to control GPU/provider cost |
| Pub/Sub | Redis Pub/Sub channel per `project_id` | Backend publishes agent/job progress; a dedicated WS gateway process subscribes and fans out to connected websocket clients (horizontal scale-friendly) |
| Idempotency keys | Redis `SETNX` with task signature hash | Prevents duplicate enqueue on client retry of `POST` endpoints |
| Session/JWT blacklist | Redis set with TTL = token expiry | Supports logout/revocation even though auth is modular |

---

## 9. Celery Job Architecture

### 9.1 Queues

| Queue | Tasks | Concurrency profile |
|---|---|---|
| `story` | story generation, decision detection | CPU-light, LLM-bound; moderate concurrency |
| `timeline` | branch creation/persistence | fast, DB-bound |
| `storyboard` | storyboard + prompt director | LLM-bound |
| `video` | per-shot video generation | GPU/provider-bound; lowest concurrency, highest priority for backoff |
| `voice` | TTS synthesis | provider-bound |
| `music` | music prompt/generation | provider-bound |
| `editing` | ffmpeg assembly | CPU-bound, memory-heavy, dedicated worker pool |
| `maintenance` | OSS lifecycle cleanup, stale-job reaper, embedding re-index | low priority, scheduled (Celery beat) |

### 9.2 Retry Policy

- Default: exponential backoff (`base=2s, max=300s`), `max_retries=5` for transient provider errors (timeouts, 429/503).
- Non-retryable: validation errors (e.g., agent output fails schema) → fail fast, write `agent_logs.status='validation_failed'`, surface to user instead of silently retrying.
- Each task is idempotent via a deterministic task key (`branch_id + stage + version_number`) checked against `jobs.celery_task_id` before re-enqueueing.

### 9.3 Chaining / Fan-out-Fan-in

- LangGraph itself runs **inside** a single Celery task per graph-level node where the node's work is agent-local; multi-shot fan-out (Video Generation) is implemented as a Celery `group()` of per-shot tasks followed by a `chord` callback that triggers the Editor join only once all shots (+ voice + music) report success or permanent failure.
- Celery beat schedules: nightly `maintenance` sweep (orphaned OSS objects, jobs stuck in `running` past timeout → marked `failed` and retried).

### 9.4 Worker Topology (Docker services)

`worker-story`, `worker-video`, `worker-voice-music`, `worker-editing`, `worker-maintenance`, plus `beat` — separated so a slow/expensive queue (e.g. `video`) never starves fast queues (e.g. `timeline`).

---

## 10. OSS Storage Structure (Alibaba OSS)

Bucket-per-environment (`butterfly-director-{env}`), key layout designed for predictable lifecycle rules and CDN cache-ability:

```
/projects/{project_id}/
  world/
    bible_v{n}.json
  characters/{character_id}/
    reference/{asset_id}.{ext}
    voice-samples/{asset_id}.{ext}
  branches/{branch_id}/
    storyboard/v{version_number}.json
    shots/{shot_number}/
      prompt.json
      video/{asset_id}.mp4
      thumbnail/{asset_id}.jpg
    voice/{asset_id}.wav
    music/{asset_id}.mp3
    final/{asset_id}.mp4          # Editor Agent output
  exports/
    {movie_id}_{quality}.mp4      # transcoded delivery renditions
```

- **Lifecycle rules**: intermediate per-shot raw renders moved to Infrequent Access after 30 days once a branch's `movies.status='completed'`; raw renders deletable after final assembly is confirmed stable (configurable retention, default 90 days, to allow re-edits).
- **Access pattern**: backend never proxies bytes — `storage_service` issues short-TTL (15 min) presigned GET URLs for playback/download and presigned PUT URLs for any direct client upload (e.g., custom character reference image).
- **Naming**: every OSS key is mirrored exactly in `assets.oss_key`; no key is ever guessed/reconstructed client-side.

---

## 11. Docker Architecture

### 11.1 Services (docker-compose)

```
services:
  web            # Next.js (apps/web)
  api            # FastAPI (apps/api)
  worker-story
  worker-video
  worker-voice-music
  worker-editing
  worker-maintenance
  beat           # celery beat scheduler
  ws-gateway     # dedicated websocket fan-out process subscribing to Redis Pub/Sub
  postgres
  redis
  qdrant
  nginx          # reverse proxy / TLS termination, routes /api and / to api/web
```

- `api`, all `worker-*`, and `beat` share one built image (`apps/api/Dockerfile`) with different `command:` overrides (`uvicorn ...` vs `celery -A app.workers.celery_app worker -Q video ...` vs `celery beat`) — single source of dependencies, no drift between API and workers.
- `web` is its own image (`apps/web/Dockerfile`), multi-stage (deps → build → standalone Next.js runtime).
- Local dev: `docker-compose.override.yml` mounts source for hot-reload (`uvicorn --reload`, `next dev`), prod compose uses built images only, no bind mounts.
- Secrets: `.env` files per environment, never baked into images; OSS/Qwen/Wan/HappyHorse keys injected at runtime via compose `env_file`.
- Health checks defined for `api` (`/v1/health/ready` — checks Postgres+Redis+Qdrant connectivity), `postgres`, `redis`; `nginx`/orchestrator waits on these before routing traffic.

### 11.2 Scaling Knobs

`docker-compose.yml` services declare `deploy.replicas` (compose v2/Swarm) for `worker-video` and `worker-voice-music` specifically, since those are the cost/latency bottleneck; `api` and `web` are stateless and horizontally replicate behind `nginx` trivially.

---

## 12. Coding Conventions

**Backend (Python 3.12 / FastAPI)**
- Strict typing: `mypy --strict` on `app/`; every function signature typed, Pydantic v2 models everywhere data crosses a boundary.
- Async-first: all DB/HTTP I/O uses `async def` + `asyncpg`/`SQLAlchemy 2.0 async` + `httpx.AsyncClient`.
- One responsibility per module; routers ≤ ~150 lines, delegate everything non-trivial to services.
- Dependency injection exclusively via FastAPI `Depends()` — no module-level singletons except read-only config.
- Naming: `snake_case` everywhere, `*_service.py`, `*_repository.py`, `*Agent` classes, `*Result`/`*Input` Pydantic contracts.
- Every agent's prompt template is versioned (`v1`, `v2`, …) and selected via config, never edited in place once shipped — enables rollback and A/B comparison.
- Formatting/linting: `ruff` (lint+format) + `isort` enforced in CI pre-merge.

**Frontend (TypeScript / Next.js)**
- Strict TS (`strict: true`), no `any` without an inline justification comment.
- Server Components by default; `"use client"` only for interactive leaves (timeline canvas, player controls, forms).
- Co-locate component + its hook + its test; shared cross-feature logic lives in `lib/` or `hooks/`, never duplicated.
- Zustand stores are domain-scoped (one per bounded context — see §13), never one global "app store".
- All API access goes through `lib/api-client.ts` (typed via `packages/shared-types`) — no ad-hoc `fetch` calls in components.
- Naming: `PascalCase` components, `camelCase` hooks/functions, `useXStore` for Zustand hooks.

**Cross-cutting**
- Conventional Commits (`feat:`, `fix:`, `chore:`...).
- Every PR touching an agent must include a fixture-based test against `agents/<name>/schema.py` so output-contract regressions are caught at review time, not in production.

---

## 13. State Management Plan (Frontend)

Zustand stores, one per bounded context, each with a narrow public API (no store reaches into another store's internals — cross-store reads happen in hooks/selectors):

- **`projectStore`** — current project metadata, list cache, wizard-created project hydration.
- **`timelineStore`** — React Flow nodes/edges, selected node, expand/collapse state, optimistic updates applied immediately on websocket `branch_created`/`movie_completed` events, reconciled against the next `GET /v1/projects/{id}/timeline` fetch.
- **`playerStore`** — current movie/shot playback state, scrub position, quality selection.
- **`wizardStore`** — multi-step Create Project Wizard form state, survives step navigation, cleared on submit/cancel.
- **`uiStore`** — modals, toasts, sidebar collapse, theme — pure UI, no server data.

Server data fetching/caching (lists, detail views) uses React Query (TanStack Query) layered on top of `api-client.ts`; Zustand is reserved for client-only/derived/interactive state and for the live-graph state that the websocket mutates directly (React Query cache is invalidated/merged from the same websocket events to stay consistent). This split avoids the common anti-pattern of duplicating server cache inside Zustand.

---

## 14. Error Handling Strategy

**Backend**
- Domain exception hierarchy in `core/exceptions.py` (`NotFoundError`, `ValidationError`, `ConflictError`, `AgentOutputInvalidError`, `ProviderUnavailableError`) — services raise these, never raw `HTTPException`.
- Single `error_handler` middleware maps domain exceptions → consistent JSON shape: `{ "error": { "code", "message", "details", "request_id" } }`, with correct HTTP status per exception type.
- Agent output validation failures are a distinct, non-retryable class (`AgentOutputInvalidError`) — they indicate a prompt/model issue, not a transient fault, so they surface to the user/ops immediately rather than burning retry budget.
- Provider errors (`ProviderUnavailableError`) trigger the configured fallback (e.g. Wan timeout → HappyHorse) before being treated as task failure.
- All exceptions logged with full context (job id, branch id, agent name) before being shaped into the response — nothing is swallowed silently.

**Frontend**
- `api-client.ts` normalizes the backend's error envelope into a typed `ApiError`; React Query's `onError` + a global error boundary route unexpected errors to a toast, expected/validation errors to inline form/field messages.
- Long-running operations (movie generation) surface failure state per-branch directly on the Timeline Explorer node (red state + retry action), never as a silent dead end.

**Workers**
- Every task wrapped by a decorator that, on final failure (retries exhausted), writes `jobs.status='failed'` + `agent_logs` error row + `events(event_type='job_failed')` in one transaction — so UI, audit trail, and job table are never out of sync.

---

## 15. Logging Strategy

- Structured JSON logging (`structlog`) everywhere in the backend; every log line carries `request_id` (HTTP) or `task_id`/`job_id` (worker) plus `project_id`/`branch_id` when available, propagated via context vars set in middleware/task wrapper.
- Log levels: `DEBUG` (dev only, includes raw prompt/response bodies), `INFO` (lifecycle events: job started/completed, branch created), `WARNING` (retries, fallback provider used, character drift auto-corrected), `ERROR` (task failed, validation failed), `CRITICAL` (provider outage affecting all in-flight jobs).
- `agent_logs` table is the **structured, queryable** record of every agent execution (input/output snapshots, latency) — application logs are the **operational** stream (stdout → collected by the deployment's log driver); the two are complementary, not duplicative — logs are for "what happened in the process," `agent_logs` is for "what did this agent decide."
- Frontend: client errors (websocket disconnects, failed fetches) reported to a lightweight error-reporting hook; no PII in logs anywhere.
- Correlation: `request_id` generated by `request_id` middleware is returned in every API error response so a user-reported bug can be traced directly to its log lines and `agent_logs`/`jobs` rows.

---

## 16. Scalability Strategy

- **Stateless API/Web tiers** scale horizontally behind `nginx`/a load balancer; no in-process state beyond per-request DB/Redis connections.
- **Worker tiers scale independently per queue** (§9.4) — the GPU/provider-bound `video` queue is the real bottleneck and is scaled (and rate-limited) separately from cheap queues like `timeline`.
- **Fan-out cost control**: Redis semaphore (§8) caps concurrent `movie_production_graph` runs per project and per account tier, preventing one user's premise (which might detect 10 decisions × 3 branches) from monopolizing GPU/provider capacity.
- **Database**: read replicas for the heavy read paths (timeline graph fetch, activity feed) once write load justifies it; `branches`/`events` partitioned by `project_id` range if a single project's graph grows very large (rare, but the schema's indices already assume project-scoped access patterns).
- **Qdrant** scales independently as a vector service; character embeddings are namespaced by `project_id` (collection-per-tenant or payload-filtered single collection, decided at implementation time based on tenant count) so consistency lookups stay fast regardless of total platform size.
- **OSS + CDN**: all playback URLs are presigned and CDN-fronted; the API server is never in the hot path for media bytes, so video traffic scales independently of compute.
- **Idempotency + checkpointing** (LangGraph checkpointer, Celery idempotency keys) mean horizontal worker scale-out/scale-in (including spot/preemptible GPU workers for `video`) never loses partially completed work.
- **Caching**: timeline graph payload and project list are the two highest-read, lowest-write-frequency endpoints — both Redis-cached with event-driven invalidation, keeping Postgres load flat as concurrent viewers grow.

---

## 17. Future Extensibility

- **New agents slot in without touching existing ones**: e.g. a future "Trailer Agent" or "Localization Agent" is a new folder under `agents/`, a new LangGraph node, and a new Celery queue — no changes to Story Architect, Video Generation, etc.
- **Provider swapping**: `video_service`/`voice_service` already abstract Wan/HappyHorse behind a façade; adding a third provider (or a self-hosted model) is a new `integrations/*_client.py` + a routing rule, with zero changes to agents that consume `video_service`.
- **Branch merging**: schema already supports a `branches` DAG (not strictly a tree) via nullable `parent_branch_id` design that could extend to `branch_merges` join table later, enabling "two universes converge" storytelling without a schema rewrite.
- **Multi-timeline projects**: `timelines` is already separate from `projects` (1:N), so "alternate premises within one project" is additive, not a migration.
- **Collaboration**: `users.role` + soft-delete + `events.actor_type='user'` lay the groundwork for multi-user projects (comments, shared editing) without redesigning the core graph.
- **Monetization**: `billing_service` exists as an explicit, disabled-by-default module so usage metering (per-render cost tracking via `prompts.token_usage` + per-shot render cost) can be wired to a paywall later without retrofitting tracking.
- **Auth modularity**: the entire auth layer is a toggleable middleware (`FEATURE_AUTH_ENABLED`) precisely so the system can run open (hackathon/demo mode) today and become multi-tenant with zero architectural change later — only configuration.
- **Export/interop**: because every artifact (storyboard, shots, final cut) is a versioned row with an OSS-backed asset, exporting a branch as a shareable package (script + shots + final video) or feeding it into a third-party editor is a read-only export job, not a new subsystem.

---

*End of architecture document. No application code has been generated — this document is the contract future implementation work must conform to.*
