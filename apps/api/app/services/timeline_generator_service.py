from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.decision_detector.schema import BranchCandidate, DecisionPoint
from app.agents.story_architect.schema import StoryBible
from app.agents.timeline_generator.agent import TimelineGeneratorAgent
from app.agents.timeline_generator.schema import BranchDraft, TimelineGeneratorRequest
from app.config.logging import get_logger
from app.core.exceptions import ConflictError
from app.db.models.branch import Branch
from app.db.models.enums import AgentLogStatus, BranchStatus, TimelineStatus
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.decision_point_repository import DecisionPointRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.branch import BranchCreate, BranchRead
from app.schemas.timeline_generator import TimelineGenerateBranchesResponse
from app.services.branch_service import BranchService

logger = get_logger(__name__)


class TimelineGeneratorService:
    """Follows the established reference service shape (run the agent, persist,
    audit-log regardless of outcome), but persists through the existing,
    already-tested BranchService.create() rather than writing branches
    directly - that single call already handles depth calculation, the
    MAX_BRANCHES_PER_DECISION sibling cap, and recomputing butterfly_score/
    probability/confidence_score for the whole sibling group. This agent's
    only new responsibility is producing the rich decision_summary content
    (affected_characters, affected_locations, emotional_impact,
    ending_divergence, narrative_impact) that scoring engine already knows how
    to read but no prior agent populated.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.story_repo = StoryRepository(session)
        self.decision_repo = DecisionPointRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.branch_repo = BranchRepository(session)
        self.branch_service = BranchService(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = TimelineGeneratorAgent()

    async def generate(
        self,
        project_id: UUID,
        story_id: UUID,
        decision_id: UUID,
        parent_branch_id: UUID | None,
    ) -> TimelineGenerateBranchesResponse:
        project = await self.project_repo.get_or_404(project_id)
        story = await self.story_repo.get_or_404(story_id)
        decision_row = await self.decision_repo.get_or_404(decision_id)
        if decision_row.story_id != story.id:
            raise ConflictError("Decision does not belong to the given story")

        story_bible = StoryBible.model_validate(story.world_bible)
        decision = DecisionPoint(
            beat_index=decision_row.beat_index,
            description=decision_row.description,
            source_hook=decision_row.source_hook,
            branch_candidates=[BranchCandidate(**c) for c in decision_row.branch_candidates],
        )
        request = TimelineGeneratorRequest(story_bible=story_bible, decision=decision)

        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                input_snapshot={
                    "project_id": str(project_id),
                    "story_id": str(story_id),
                    "decision_id": str(decision_id),
                },
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        timeline = await self._get_or_create_timeline(project.id, story.id, story_bible)
        parent_branch = await self._get_or_create_parent_branch(timeline, parent_branch_id, story)

        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        created_branches: list[Branch] = []
        for draft in result.output.branches:
            branch = await self.branch_service.create(
                BranchCreate(
                    timeline_id=timeline.id,
                    parent_branch_id=parent_branch.id,
                    name=draft.name,
                    summary=draft.summary,
                    decision_summary=self._decision_summary_from_draft(draft, decision_id),
                )
            )
            created_branches.append(branch)

        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            input_snapshot={
                "project_id": str(project_id),
                "story_id": str(story_id),
                "decision_id": str(decision_id),
            },
            output_snapshot={
                "result": result.output.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()
        for branch in created_branches:
            await self.session.refresh(branch)

        logger.info(
            "timeline_generator_persisted",
            timeline_id=str(timeline.id),
            decision_id=str(decision_id),
            branch_count=len(created_branches),
        )
        return TimelineGenerateBranchesResponse(
            timeline_id=timeline.id,
            decision_id=decision_id,
            branches=[BranchRead.model_validate(b) for b in created_branches],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=datetime.now(UTC),
        )

    async def _get_or_create_timeline(self, project_id: UUID, story_id: UUID, story_bible: StoryBible) -> Timeline:
        items, _ = await self.timeline_repo.list_paginated(
            cursor=None, limit=1, project_id=project_id, story_id=story_id
        )
        if items:
            return items[0]
        return await self.timeline_repo.create(
            project_id=project_id,
            story_id=story_id,
            title=story_bible.title,
            status=TimelineStatus.ACTIVE,
        )

    async def _get_or_create_parent_branch(
        self, timeline: Timeline, parent_branch_id: UUID | None, story: Story
    ) -> Branch:
        if parent_branch_id is not None:
            parent = await self.branch_repo.get_or_404(parent_branch_id)
            if parent.timeline_id != timeline.id:
                raise ConflictError("parent_branch_id does not belong to the resolved timeline")
            return parent

        root = await self.timeline_repo.get_root_branch(timeline.id)
        if root is not None:
            return root

        return await self.branch_repo.create(
            timeline_id=timeline.id,
            parent_branch_id=None,
            name="Canonical Timeline",
            summary=story.premise,
            depth=0,
            status=BranchStatus.PENDING,
            is_canonical=True,
        )

    @staticmethod
    def _decision_summary_from_draft(draft: BranchDraft, decision_id: UUID) -> dict:
        return {
            "decision_id": str(decision_id),
            "candidate_label": draft.candidate_label,
            "initial_divergent_state": draft.initial_divergent_state,
            "delta_script": draft.delta_script,
            "affected_characters": draft.affected_characters,
            "affected_locations": draft.affected_locations,
            "emotional_impact": draft.emotional_impact,
            "ending_divergence": draft.ending_divergence,
            "narrative_impact": draft.narrative_impact,
        }
