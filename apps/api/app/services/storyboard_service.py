from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.schema import StoryBible
from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.schema import CharacterStateSummary, StoryboardRequest
from app.config.logging import get_logger
from app.core.exceptions import ConflictError
from app.db.models.branch import Branch
from app.db.models.character import Character
from app.db.models.character_branch_state import CharacterBranchState
from app.db.models.enums import AgentLogStatus, MovieStatus, VersionEntityType
from app.db.models.movie import Movie
from app.db.models.version import Version
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.common import Page
from app.schemas.storyboard import ShotRead, StoryboardGenerateResponse, StoryboardRead

logger = get_logger(__name__)


class StoryboardService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Like Character
    Memory, this agent resolves its own input from a single branch_id. Output
    is persisted as a `storyboard` Version snapshot (per ARCHITECTURE.md
    §4.12) rather than a bespoke table - re-running for the same branch adds
    a new version_number rather than overwriting history, since re-
    storyboarding is an explicitly named regeneration case in that table's
    own docstring. A Movie row is lazily get-or-created for the branch and
    its status moved to STORYBOARDING, mirroring Timeline Generator's lazy
    get-or-create of the Timeline/root Branch.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.branch_repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.story_repo = StoryRepository(session)
        self.character_repo = CharacterRepository(session)
        self.character_state_repo = CharacterBranchStateRepository(session)
        self.movie_repo = MovieRepository(session)
        self.version_repo = VersionRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = StoryboardAgent()

    async def generate(self, branch_id: UUID) -> StoryboardGenerateResponse:
        branch = await self.branch_repo.get_or_404(branch_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)
        if timeline.story_id is None:
            raise ConflictError(
                "Branch's timeline has no associated story; Storyboard requires a "
                "story-linked timeline"
            )

        story = await self.story_repo.get_or_404(timeline.story_id)
        story_bible = StoryBible.model_validate(story.world_bible)

        characters = list(await self.character_repo.list_all_by_story(story.id))
        states_by_character_id = {
            s.character_id: s
            for s in await self.character_state_repo.list_all_by_branch(branch.id)
        }
        character_summaries = [
            self._summary_from_character(c, states_by_character_id.get(c.id)) for c in characters
        ]

        request = StoryboardRequest(
            story_bible=story_bible,
            branch_name=branch.name,
            branch_summary=branch.summary,
            delta_script=(branch.decision_summary or {}).get("delta_script"),
            characters=character_summaries,
        )
        generated_at = datetime.now(UTC)

        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                branch_id=branch.id,
                input_snapshot={"branch_id": str(branch_id), "story_id": str(story.id)},
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        movie = await self._get_or_create_movie(branch)
        version_number = await self.version_repo.next_version_number(
            VersionEntityType.STORYBOARD, branch.id
        )
        version = await self.version_repo.create(
            entity_type=VersionEntityType.STORYBOARD,
            entity_id=branch.id,
            version_number=version_number,
            snapshot=result.output.model_dump(mode="json"),
            created_by=None,
        )
        movie = await self.movie_repo.update(
            movie,
            status=MovieStatus.STORYBOARDING,
            extra_metadata={
                **movie.extra_metadata,
                "shot_count": len(result.output.shots),
                "last_storyboard_version": version_number,
            },
        )

        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": generated_at.isoformat(),
        }
        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            branch_id=branch.id,
            input_snapshot={"branch_id": str(branch_id), "story_id": str(story.id)},
            output_snapshot={
                "result": result.output.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()
        await self.session.refresh(version)

        logger.info(
            "storyboard_persisted",
            branch_id=str(branch.id),
            movie_id=str(movie.id),
            version_number=version_number,
            shot_count=len(result.output.shots),
        )
        return StoryboardGenerateResponse(
            branch_id=branch.id,
            movie_id=movie.id,
            version_id=version.id,
            version_number=version_number,
            shots=[ShotRead(**shot.model_dump(mode="json")) for shot in result.output.shots],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=generated_at,
        )

    async def get(self, version_id: UUID) -> StoryboardRead:
        version = await self.version_repo.get_or_404(version_id)
        return self._to_storyboard_read(version)

    async def list(self, branch_id: UUID, cursor: str | None, limit: int) -> Page[StoryboardRead]:
        items, next_cursor = await self.version_repo.list_paginated(
            cursor=cursor,
            limit=limit,
            entity_type=VersionEntityType.STORYBOARD,
            entity_id=branch_id,
        )
        return Page(
            items=[self._to_storyboard_read(item) for item in items],
            next_cursor=next_cursor,
        )

    async def delete(self, version_id: UUID) -> None:
        version = await self.version_repo.get_or_404(version_id)
        await self.version_repo.soft_delete(version)
        await self.session.commit()

    async def _get_or_create_movie(self, branch: Branch) -> Movie:
        existing = await self.movie_repo.get_by_branch_id(branch.id)
        if existing is not None:
            return existing
        return await self.movie_repo.create(
            branch_id=branch.id,
            title=branch.name,
            status=MovieStatus.QUEUED,
        )

    @staticmethod
    def _summary_from_character(
        character: Character, state: CharacterBranchState | None
    ) -> CharacterStateSummary:
        traits = character.canonical_traits or {}
        kwargs = {
            "name": character.name,
            "role": traits.get("role", "supporting"),
            "physical_description": character.description or "",
        }
        if state is not None:
            diff = state.state_diff or {}
            kwargs["knowledge_state"] = diff.get("knowledge_state", "unchanged")
            kwargs["emotional_state"] = diff.get("emotional_state", "unchanged")
            kwargs["physical_state"] = diff.get("physical_state", "unchanged")
        return CharacterStateSummary(**kwargs)

    @staticmethod
    def _to_storyboard_read(version: Version) -> StoryboardRead:
        snapshot = version.snapshot or {}
        return StoryboardRead(
            id=version.id,
            branch_id=version.entity_id,
            version_number=version.version_number,
            shots=[ShotRead(**shot) for shot in snapshot.get("shots", [])],
            created_at=version.created_at,
        )
