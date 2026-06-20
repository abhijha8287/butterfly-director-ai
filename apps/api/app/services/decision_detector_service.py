from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.decision_detector.agent import DecisionDetectorAgent
from app.agents.decision_detector.schema import DecisionDetectorRequest
from app.agents.story_architect.schema import StoryBible
from app.config.logging import get_logger
from app.db.models.decision_point import DecisionPoint
from app.db.models.enums import AgentLogStatus
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.decision_point_repository import DecisionPointRepository
from app.repositories.story_repository import StoryRepository
from app.schemas.common import Page
from app.schemas.decision_detector import DecisionGenerateResponse, DecisionPointRead

logger = get_logger(__name__)


class DecisionDetectorService:
    """Follows the established reference service shape: run the agent, persist
    the validated output + generation provenance, and write an AgentLog audit
    row regardless of success or failure. An empty decision list is a valid,
    expected outcome (a linear story) - it persists zero DecisionPoint rows
    and still returns a 201 with that empty list, not an error.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.story_repo = StoryRepository(session)
        self.decision_repo = DecisionPointRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = DecisionDetectorAgent()

    async def generate(self, story_id: UUID) -> DecisionGenerateResponse:
        story = await self.story_repo.get_or_404(story_id)
        story_bible = StoryBible.model_validate(story.world_bible)
        request = DecisionDetectorRequest(story_bible=story_bible)

        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                input_snapshot={"story_id": str(story_id)},
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        decision_list = result.output
        generated_at = datetime.now(UTC)
        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": generated_at.isoformat(),
        }

        decisions: list[DecisionPoint] = []
        for decision in decision_list.decisions:
            row = await self.decision_repo.create(
                story_id=story.id,
                beat_index=decision.beat_index,
                description=decision.description,
                source_hook=decision.source_hook,
                branch_candidates=[c.model_dump(mode="json") for c in decision.branch_candidates],
                generation_metadata=generation_metadata,
            )
            decisions.append(row)

        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            input_snapshot={"story_id": str(story_id)},
            output_snapshot={
                "decisions": decision_list.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )

        await self.session.commit()
        for row in decisions:
            await self.session.refresh(row)

        logger.info(
            "decision_detector_persisted",
            story_id=str(story.id),
            decision_count=len(decisions),
        )
        return DecisionGenerateResponse(
            story_id=story.id,
            decisions=[self._to_decision_read(d) for d in decisions],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=generated_at,
        )

    async def get(self, decision_id: UUID) -> DecisionPointRead:
        decision = await self.decision_repo.get_or_404(decision_id)
        return self._to_decision_read(decision)

    async def list(
        self, story_id: UUID | None, cursor: str | None, limit: int
    ) -> Page[DecisionPointRead]:
        filters = {"story_id": story_id} if story_id is not None else {}
        items, next_cursor = await self.decision_repo.list_paginated(
            cursor=cursor, limit=limit, **filters
        )
        return Page(
            items=[self._to_decision_read(d) for d in items],
            next_cursor=next_cursor,
        )

    async def delete(self, decision_id: UUID) -> None:
        decision = await self.decision_repo.get_or_404(decision_id)
        await self.decision_repo.soft_delete(decision)
        await self.session.commit()

    @staticmethod
    def _to_decision_read(decision: DecisionPoint) -> DecisionPointRead:
        return DecisionPointRead(
            id=decision.id,
            story_id=decision.story_id,
            beat_index=decision.beat_index,
            description=decision.description,
            source_hook=decision.source_hook,
            branch_candidates=decision.branch_candidates or [],
            created_at=decision.created_at,
        )
