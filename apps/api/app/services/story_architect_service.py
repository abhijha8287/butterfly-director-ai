from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryBible, StoryRequest
from app.config.logging import get_logger
from app.db.models.enums import AgentLogStatus, StoryStatus
from app.db.models.story import Story
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.story_repository import StoryRepository
from app.schemas.common import Page
from app.schemas.story_architect import StoryGenerateResponse

logger = get_logger(__name__)


class StoryArchitectService:
    """Reference service implementation every later agent's service follows:
    run the agent, persist the validated output + generation provenance, and
    write an AgentLog audit row regardless of success or failure.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.story_repo = StoryRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = StoryArchitectAgent()

    async def generate(self, request: StoryRequest) -> StoryGenerateResponse:
        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                input_snapshot=request.model_dump(mode="json"),
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        story_bible = result.output
        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        story = await self.story_repo.create(
            project_id=None,
            premise=request.prompt,
            genre=story_bible.genre,
            tone=story_bible.tone,
            status=StoryStatus.COMPLETED,
            world_bible=story_bible.model_dump(mode="json"),
            generation_metadata=generation_metadata,
        )

        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            input_snapshot=request.model_dump(mode="json"),
            output_snapshot={"story_bible": story_bible.model_dump(mode="json"), **generation_metadata},
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )

        await self.session.commit()
        await self.session.refresh(story)

        logger.info("story_architect_persisted", story_id=str(story.id))
        return self._to_response(story)

    async def get(self, story_id: UUID) -> StoryGenerateResponse:
        story = await self.story_repo.get_or_404(story_id)
        return self._to_response(story)

    async def list(self, cursor: str | None, limit: int) -> Page[StoryGenerateResponse]:
        items, next_cursor = await self.story_repo.list_paginated(cursor=cursor, limit=limit)
        return Page(items=[self._to_response(story) for story in items], next_cursor=next_cursor)

    async def delete(self, story_id: UUID) -> None:
        story = await self.story_repo.get_or_404(story_id)
        await self.story_repo.soft_delete(story)
        await self.session.commit()

    @staticmethod
    def _to_response(story: Story) -> StoryGenerateResponse:
        metadata = story.generation_metadata or {}
        return StoryGenerateResponse(
            id=story.id,
            story_bible=StoryBible.model_validate(story.world_bible),
            prompt_version=metadata.get("prompt_version", "unknown"),
            model=metadata.get("model", "unknown"),
            latency_ms=metadata.get("latency_ms", 0),
            attempts=metadata.get("attempts", 0),
            prompt_tokens=metadata.get("prompt_tokens"),
            completion_tokens=metadata.get("completion_tokens"),
            created_at=story.created_at,
        )
