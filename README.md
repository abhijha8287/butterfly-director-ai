# Butterfly Director AI

Turns one story premise into a branching set of fully generated short films, using a pipeline of 11 specialised AI agents.

## Why this exists
An experiment in long, multi-step generation: can a chain of focused agents take a one-line idea all the way to video, voice and music while keeping characters and plot consistent across branches?

## What it does
- Takes a premise, target runtime and optional genre or style
- Runs 11 agents orchestrated with LangGraph: Story Architect, Character Architect, Decision Detector, Timeline Generator, Character Memory, Storyboard, Prompt Director, Video Generation, Voice, Music, Editor
- Builds a story bible, a branching timeline of "butterfly" decision points and a storyboard for each branch
- Generates video (Wan), voice-over (CosyVoice) and text (Qwen) through Alibaba Cloud DashScope
- Assembles each branch into a film with ffmpeg
- Runs long jobs on Celery workers; FastAPI serves the API and Swagger docs

## Project structure
```
butterfly-director-ai/
├── apps/
│   ├── api/
│   │   ├── app/agents/        The 11 agents
│   │   ├── app/graphs/        LangGraph workflows
│   │   ├── app/routers/       FastAPI endpoints
│   │   ├── app/schemas/       Pydantic request and output models
│   │   ├── app/services/      Business logic per agent
│   │   ├── app/integrations/  LLM providers, Qwen and Redis clients
│   │   ├── app/db/            Database models and sessions
│   │   ├── app/repositories/  Database queries
│   │   ├── app/workers/       Celery tasks
│   │   ├── app/config/        Settings and logging
│   │   ├── app/core/          Dependencies, errors, pagination
│   │   ├── app/demo/          Stand-alone agent demo scripts
│   │   └── tests/             Unit and integration tests
│   └── web/                   Next.js frontend
├── infra/terraform/           AWS ECR, ECS, networking, storage
├── .github/workflows/         Build and deploy to AWS
├── docs/design/               Design decision documents
├── ARCHITECTURE.md            Full system design
└── docker-compose.yml         Postgres, Redis, API, worker, beat
```

## Getting started
Requirements: Docker Desktop and a DashScope API key (Alibaba Cloud Model Studio, international workspace) to generate content.
```bash
git clone https://github.com/abhijha8287/butterfly-director-ai.git
cd butterfly-director-ai
cp .env.example .env                    # set DASHSCOPE_API_KEY
docker compose up -d --build
curl http://localhost:8000/v1/health    # {"status":"ok"}
```
Open http://localhost:8000/docs to call any endpoint from the browser. To try the first agent:
```bash
curl -X POST http://localhost:8000/v1/story/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A retired thief steals back a memory taken from her own mind.", "target_runtime_minutes": 8}'
```

## Tech stack
Python, FastAPI, LangGraph, Pydantic, PostgreSQL, SQLAlchemy, Alembic, Redis, Celery, Alibaba Cloud DashScope (Qwen, Wan, CosyVoice), ffmpeg, Next.js, Docker, Terraform, AWS ECS, GitHub Actions

## Configuration (`.env`)

See `.env.example` for the full, documented list. The essentials:

- `DASHSCOPE_API_KEY` — required for any agent to actually generate content. One key
  covers Qwen (text), Wan (video), and CosyVoice (voice) — get it from the Alibaba
  Cloud Model Studio console (international workspace).
- `QWEN_MODEL`, `WAN_MODEL`, `COSYVOICE_MODEL` — model selection per capability.
- `VIDEO_PROVIDER`, `VOICE_PROVIDER`, `MUSIC_PROVIDER` — Strategy-pattern vendor
  selection (`wan`/`happyhorse`, `dashscope`/`happyhorse`, `happyhorse`/`none`).
- `MEDIA_ROOT` (default `/app/media`) — local-disk directory the Voice and Music
  Agents write synthesized audio files to, since CosyVoice/HappyHorse return raw
  bytes with no hosted URL of their own (unlike Wan's video_url); the Editor Agent
  writes its assembled final cut here too.
- `FFMPEG_BINARY` / `FFPROBE_BINARY` (default `ffmpeg`/`ffprobe`) — the Editor Agent
  shells out to these (installed in the api image's Dockerfile) to assemble the
  final cut; no Strategy pattern/vendor swap here, unlike video/voice/music.
- `DECISION_BRANCH_CANDIDATES_MIN` / `_MAX` (default 2/4) — bounds how many branch
  candidates the Decision Detector Agent may produce per decision point, to cap
  multiverse fan-out cost downstream.
- `PROVIDER_POLL_INTERVAL_SECONDS` / `PROVIDER_POLL_TIMEOUT_SECONDS` (default 15s/600s)
  — how often and how long the Video Generation Agent polls Wan's async
  task-create-then-poll API per shot before giving up.
- `WAN_VIDEO_SIZE` / `WAN_VIDEO_DURATION_SECONDS` (default `1280*720`/5s) — fallback
  video dimensions/duration the Video Generation Agent passes to Wan when a shot's own
  `duration_seconds` isn't set.
- `AUTH_ENABLED` — auth middleware exists but is off by default for this build.
- Database/Redis/Celery URLs — only matter if running the API outside docker-compose;
  compose overrides them to point at the in-network `postgres`/`redis` services.

## Known limitations

- All eleven agents `ARCHITECTURE.md` specifies — **Story Architect**, **Character
  Architect**, **Decision Detector**, **Timeline Generator**, **Character Memory**,
  **Storyboard**, **Prompt Director**, **Video Generation**, **Voice**, **Music**,
  and **Editor** — are implemented end-to-end, each with its own live-verified test
  run against the real DashScope API (or, for Editor, real local ffmpeg). The one
  thing not currently demonstrated is all eleven chained together in a single live
  run - see the next bullet.
- As of this writing, `python -m app.demo.editor` (the full 11-agent chain) fails at
  the Video Generation step with a persistent `403 Forbidden` from Wan's
  `video-synthesis` endpoint - an external DashScope account/quota issue, not a code
  defect (Video Generation itself was live-verified independently, earlier in this
  build, before this started occurring). Editor's own logic is verified two other
  ways instead: `tests/integrations/test_ffmpeg_editor_provider.py` runs the real
  `FfmpegEditorComposeProvider` against real synthetic local media (no DashScope
  involved), and `tests/routers/test_editor_router.py` exercises the full HTTP/DB
  chain with upstream agents mocked. Re-run `python -m app.demo.editor` once the Wan
  account issue clears to get a true end-to-end live cut.
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
- `PromptDirectorAgent` is the first agent requiring **zero** new DB models or
  migrations - it persists through the pre-existing, previously read-only
  `prompt_history` table (`ARCHITECTURE.md` §4.9), adding only the `POST /generate`
  write path onto its existing `/prompt-history` router prefix.
- `PromptDirectorAgent` runs once per `storyboard_version_id` you explicitly pass in,
  same as the other branch/version-scoped agents - no automatic orchestration yet.
  Re-running it for the same storyboard version always inserts a fresh batch of
  `PromptHistory` rows (there's no upsert) rather than updating or replacing the
  previous batch.
- `PromptDirectorAgent` silently skips any name in a shot's `characters_present` that
  doesn't match a character in the story's roster (rather than erroring), the same
  graceful-degradation choice `StoryboardAgent` makes for unresolved Character Memory
  state.
- `VideoGenerationAgent` implements ARCHITECTURE.md §9.3's "fan-out per shot" as
  in-process `asyncio.gather` within a single request/demo-script call, not as a real
  Celery `group()`/`chord` of per-shot tasks - live-verified this still renders shots
  genuinely concurrently (5 shots, ~50s total latency for the batch, not 5x a single
  shot's latency), but there's no real per-shot Celery task, retry-via-queue, or
  cross-process progress tracking yet. The `Job` row this agent creates
  (`job_type=video_render`) is written/updated synchronously in the same request for
  the same reason.
- `VideoGenerationAgent` doesn't call an LLM, so it has no `prompts/` directory and its
  `AgentRunResult.prompt_version` is always the literal `"n/a"`; its response schema
  omits `prompt_tokens`/`completion_tokens` entirely rather than leaving them `None`.
- `VideoGenerationAgent` doesn't upload anything to Alibaba OSS itself - no OSS
  upload/re-hosting pipeline exists in this build, despite `ARCHITECTURE.md` §10's OSS
  key structure. `Asset.oss_key` stores Wan's own (time-limited, presigned) `video_url`
  directly, `oss_bucket` stores the provider name (`wan`/`happyhorse`) as a placeholder,
  and `size_bytes`/`checksum_sha256` are left as `0`/`None` since the file is never
  downloaded - a real implementation would fetch the video and re-host it.
- `VideoGenerationAgent` runs once per `storyboard_version_id` you explicitly pass in,
  same as Prompt Director - no automatic orchestration yet. Re-running it for the same
  storyboard version inserts a fresh batch of `Asset` rows (there's no upsert keyed on
  shot) and a fresh `Job` row each time.
- The Celery `worker` binds to every queue in a single process for this build
  (per the approved design doc); splitting into dedicated per-queue worker pools is a
  `docker-compose.yml` change, not a code change.
- `ARCHITECTURE.md` specifies the Voice Agent's input as "dialogue lines + character
  voice profiles" without saying which agent produces the lines. This build has
  `VoiceAgent.run()` extract its own dialogue lines via an LLM call as the first phase
  of its own run, before synthesizing each line - a new design decision, not something
  explicit in the architecture doc, following the established pattern of agents
  resolving their own input from already-persisted data.
- `VoiceAgent` is the first agent combining an LLM phase and a provider-synthesis phase
  in one `run()`. A shot with no plausible spoken dialogue yields zero lines - same as
  Decision Detector's zero-decisions case, this is a valid result, not an error.
- Required adding `PromptProvider.DASHSCOPE` to the `prompt_provider` enum (migration
  `c2fccaabd7a7`, an additive `ALTER TYPE ... ADD VALUE`) since every prior text agent
  used `qwen`/`wan`/`happyhorse` and none needed the TTS provider name.
- Like Video Generation, `VoiceAgent` doesn't upload anywhere real - but unlike Wan,
  CosyVoice returns raw audio bytes with no hosted URL at all, so this build writes
  them to local disk under `MEDIA_ROOT` and stores that path as `Asset.oss_key`
  (`oss_bucket="local"`). Unlike Video Generation's placeholder, `size_bytes` and
  `checksum_sha256` here are real values computed from the actual bytes - an
  asymmetry between the two agents' Asset-persistence fidelity worth knowing about
  if/when a real OSS pipeline is added for both.
- Characters only carry descriptive `voice_profile` fields (`descriptor`, `tone`,
  `pace`, `pitch`) - there's no per-character voice ID, so every line for every
  character is synthesized through CosyVoice's same default voice. A real
  implementation would map characters to distinct CosyVoice voice IDs.
- `VoiceAgent` runs once per `storyboard_version_id` you explicitly pass in, same as
  Prompt Director/Video Generation - no automatic orchestration yet. Re-running it
  inserts a fresh batch of `PromptHistory`/`Asset` rows (there's no upsert) rather
  than replacing the previous batch.
- `MUSIC_PROVIDER` defaults to `none` - no real DashScope music-generation API exists
  in this build (unlike Qwen/Wan/CosyVoice), so `MusicAgent`'s provider call is
  genuinely optional rather than always-on like Voice's. With no provider configured,
  `MusicAgent` still extracts and persists every cue (mood/tempo/generation_prompt),
  just with `attempts=0` and no `Asset` row - this is the literal architecture intent
  ("generation prompts (and/or generated stems if provider supports it)"), not a
  fallback or degraded mode.
- Required adding `PromptProvider.NONE` to the `prompt_provider` enum (migration
  `64be34de8b20`, an additive `ALTER TYPE ... ADD VALUE`, following the same pattern
  as Voice's `DASHSCOPE` addition) since `MusicService` needs a provider value to
  write on `PromptHistory` rows even when synthesis was skipped entirely.
- `MusicAgent`'s cues span a contiguous range of shots (`start_shot_number` to
  `end_shot_number`), not a single shot - a deliberate departure from every other
  shot-scoped agent (Prompt Director, Video Generation, Voice), since a film score
  is structurally a small number of cues per emotional beat, not one per shot.
  `ARCHITECTURE.md` doesn't specify this shape explicitly; it's a new design decision
  following the same "agent resolves its own input/output shape" precedent Voice set.
- `MusicService` branches per cue on which of `audio_bytes`/`audio_url` the provider
  result populated: bytes get written to local disk under `MEDIA_ROOT` like Voice
  (real `size_bytes`/`checksum_sha256`), a URL gets stored directly as `Asset.oss_key`
  like Wan's `video_url` (placeholder `size_bytes=0`/`checksum_sha256=None`), and
  neither populated (no provider configured) means no `Asset` row is created at all -
  the response's `asset` field is `null` for that cue.
- `MusicAgent` runs once per `storyboard_version_id` you explicitly pass in, same as
  Voice/Prompt Director/Video Generation - no automatic orchestration yet. Re-running
  it inserts a fresh batch of `PromptHistory`/`Asset` rows (there's no upsert) rather
  than replacing the previous batch.
- `EditorAgent` is the second agent (after Video Generation) that never calls an LLM,
  and the only one that doesn't call a remote provider either - it shells out to a
  local ffmpeg binary (installed via the api image's Dockerfile), so there's no
  Strategy pattern/vendor swap for this capability, unlike video/voice/music.
- `EditorAgent` writes no `prompt_history` rows of its own - there's no `editing`
  `PromptStage`, since `ARCHITECTURE.md` frames this step as literal assembly
  ("assembled final movie asset... via server-side ffmpeg composition job"), not
  prompt-driven generation. It only *reads* the `SHOT_PROMPT`/`VOICE`/`MUSIC` rows
  the upstream agents already wrote for the exact storyboard version it's given.
- `EditorService` gracefully skips any shot that never rendered (Wan failure, or a
  shot prompt that never got rendered at all) rather than failing the whole assembly
  - the same choice Video Generation/Voice/Music make per item. A voice line or music
  cue that references a skipped shot is skipped too (there's no sensible position for
  it in a final cut that's missing that shot), logged as a warning. If literally
  every shot was skipped, the whole request fails with a `ConflictError` - there's
  nothing to assemble.
- Each included shot's absolute position in the final timeline is computed as the
  cumulative duration of every included shot before it - not stored anywhere by
  Voice/Music themselves (which only know "this line belongs to shot N", not "shot N
  starts at second X"). This is a new design decision Editor makes, consistent with
  ARCHITECTURE.md's Voice Agent description ("time-coded for editor alignment")
  without that time-coding being explicit elsewhere in the schema.
- ffmpeg reads shot videos directly from Wan's presigned `video_url` (an http(s)
  input, no local download step) - if that URL has already expired by the time
  Editor runs, composition fails. A production build would re-host shots to
  permanent storage immediately after Video Generation completes (the OSS pipeline
  this build doesn't have - see Video Generation's limitations above) specifically
  to avoid this.
- The audio mix is a single global `amix` of every voice/music track, each delayed
  into position with `adelay` - there's no per-track volume balancing (a music cue
  and a dialogue line are mixed at equal gain) or ducking (music doesn't automatically
  lower under dialogue). A production build would tune relative levels per track kind.
- `EditorAgent` retries the *entire* composition as one unit (up to 3 attempts) on a
  transient ffmpeg/provider failure, unlike every fan-out agent (Video Generation/
  Voice/Music) which retries per-item - there's no meaningful "partial" outcome for a
  single ffmpeg invocation the way there is for N independent shot/line/cue calls.
- `EditorAgent` runs once per `storyboard_version_id` you explicitly pass in, same as
  the other version-scoped agents - no automatic orchestration yet (no real LangGraph
  join on shots+voice+music completion, per `ARCHITECTURE.md` §11-12). Re-running it
  inserts a fresh `Asset` row and overwrites `movies.final_asset_id` to point at the
  newest cut, rather than keeping version history the way Storyboard's `Version` rows
  do.

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
| POST | `/v1/prompt-history/generate` | Run the Prompt Director Agent on a `storyboard_version_id`; persists and returns one `PromptHistoryRead` per shot |
| POST | `/v1/assets/render-shots` | Run the Video Generation Agent on a `storyboard_version_id`; persists and returns one `Asset` per rendered shot, plus any failed shots |
| POST | `/v1/assets/synthesize-voice` | Run the Voice Agent on a `storyboard_version_id`; extracts dialogue lines, synthesizes each one, and persists and returns one `Asset` per rendered line, plus any failed lines |
| POST | `/v1/assets/generate-music` | Run the Music Agent on a `storyboard_version_id`; scores the branch with one or more cues and, if `MUSIC_PROVIDER` is configured, synthesizes each one - persists and returns one `Asset` per synthesized cue (`null` if no provider is configured), plus any failed cues |
| POST | `/v1/assets/assemble-movie` | Run the Editor Agent on a `storyboard_version_id`; assembles every successfully rendered shot plus any voice/music tracks into one final cut via ffmpeg, persists it as an `Asset`, and sets `movies.final_asset_id`/`movies.status='completed'` |
| `/v1/projects`, `/v1/stories`, `/v1/timelines`, `/v1/branches`, `/v1/movies`, `/v1/characters`, `/v1/assets`, `/v1/jobs`, `/v1/agent-logs`, `/v1/prompt-history` | Generic CRUD endpoints for the underlying domain model (project-scoped resources used by the broader pipeline as more agents come online) - `GET /v1/branches?timeline_id=` and `GET /v1/timelines/{id}/tree` are how you read back what Timeline Generator created; `GET /v1/prompt-history?branch_id=` and `GET /v1/prompt-history/{id}` are how you read back what Prompt Director, Voice, and Music created; `GET /v1/assets?project_id=` and `GET /v1/assets/{asset_id}` are how you read back what Video Generation, Voice, Music, and Editor created; `GET /v1/movies/by-branch/{branch_id}` is how you read back the final movie's status/final_asset_id - no new read endpoints needed for any of them |

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
# -> {"branch_id": "<branch_id>", "version_id": "<version_id>", "version_number": 1, "shots": [{"shot_number": 1, "scene": "...", ...}, ...], ...}

curl -X POST http://localhost:8000/v1/prompt-history/generate \
  -H "Content-Type: application/json" \
  -d '{"storyboard_version_id": "<version_id>"}'
# -> {"branch_id": "<branch_id>", "storyboard_version_id": "<version_id>", "shot_prompts": [{"rendered_prompt": "...", ...}, ...], ...}

curl -X POST http://localhost:8000/v1/assets/render-shots \
  -H "Content-Type: application/json" \
  -d '{"storyboard_version_id": "<version_id>"}'
# -> {"branch_id": "<branch_id>", "movie_id": "<movie_id>", "job_id": "<job_id>", "rendered": [{"shot_number": 1, "asset": {"oss_key": "https://...mp4", ...}}, ...], "failed_shots": [], ...}

curl -X POST http://localhost:8000/v1/assets/synthesize-voice \
  -H "Content-Type: application/json" \
  -d '{"storyboard_version_id": "<version_id>"}'
# -> {"branch_id": "<branch_id>", "storyboard_version_id": "<version_id>", "lines": [{"shot_number": 1, "character_name": "...", "line_text": "...", "asset": {"oss_key": "/app/media/...mp3", ...}}, ...], "failed_lines": [], ...}

curl -X POST http://localhost:8000/v1/assets/generate-music \
  -H "Content-Type: application/json" \
  -d '{"storyboard_version_id": "<version_id>"}'
# -> {"branch_id": "<branch_id>", "storyboard_version_id": "<version_id>", "cues": [{"start_shot_number": 1, "end_shot_number": 2, "mood": "...", "tempo_bpm": 110, "generation_prompt": "...", "asset": null}, ...], "failed_cues": [], ...}

curl -X POST http://localhost:8000/v1/assets/assemble-movie \
  -H "Content-Type: application/json" \
  -d '{"storyboard_version_id": "<version_id>"}'
# -> {"branch_id": "<branch_id>", "movie_id": "<movie_id>", "job_id": "<job_id>", "storyboard_version_id": "<version_id>", "asset": {"oss_key": "/app/media/editor/...mp4", ...}, "shot_count": 5, "voice_track_count": 2, "music_track_count": 1, "skipped_shot_numbers": [], ...}
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
`characters_present`). Prompt Director generate returns a
`PromptDirectorGenerateResponse`: the resolved `branch_id` and `storyboard_version_id`
plus one `PromptHistoryRead` per shot (sorted by shot number), each carrying the
provider-ready `rendered_prompt` and an `input_payload` with the shot reference,
negative prompt, and consistency/style tokens. Video Generation generate returns a
`VideoGenerationGenerateResponse`: the resolved `branch_id`, `movie_id`, `job_id`, and
`storyboard_version_id`, plus `rendered` (one `AssetRead` per successfully rendered
shot) and `failed_shots` (shot_number/attempts/error for any shot that exhausted its
retries). Voice synthesize returns a `VoiceGenerateResponse`: the resolved `branch_id`
and `storyboard_version_id`, plus `lines` (one rendered line per successfully
synthesized line, each carrying its `shot_number`, `character_name`, `line_text`,
`delivery_note`, and `asset`) and `failed_lines` (shot_number/character_name/
attempts/error for any line that exhausted its synthesis retries). Music generate
returns a `MusicGenerateResponse`: the resolved `branch_id` and `storyboard_version_id`,
plus `cues` (one rendered cue per extracted `MusicCue`, each carrying its
`start_shot_number`/`end_shot_number`, `mood`, `tempo_bpm`, `generation_prompt`, and
`asset` - `null` when no `MusicGenerationProvider` is configured) and `failed_cues`
(only populated when a provider is configured and a cue's synthesis exhausted its
retries). Editor assemble returns an `EditorGenerateResponse`: the resolved
`branch_id`, `movie_id`, `job_id`, and `storyboard_version_id`, plus the final cut's
`asset`, `shot_count`/`voice_track_count`/`music_track_count`, and
`skipped_shot_numbers` (any shot that never rendered and so was left out of the cut).
All eleven share the same generation-provenance shape (`model`, `prompt_version`,
`latency_ms`, `attempts`, token counts) - Character Memory's is all zero/`"n/a"` in
the one case where it skips the LLM call entirely (a story with no characters yet),
and Video Generation/Editor's `prompt_tokens`/`completion_tokens` are simply absent
from their response schemas (not just `None`) since neither ever calls an LLM at all;
their `prompt_version` is always the literal `"n/a"`.
