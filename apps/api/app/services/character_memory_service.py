from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.character_memory.agent import CharacterMemoryAgent
from app.agents.character_memory.schema import (
    BranchContext,
    CharacterMemoryProfile,
    CharacterMemoryRequest,
    CharacterStateDiff,
)
from app.config.logging import get_logger
from app.core.exceptions import ConflictError
from app.db.models.branch import Branch
from app.db.models.character import Character
from app.db.models.character_branch_state import CharacterBranchState
from app.db.models.enums import AgentLogStatus, DriftSeverity
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.character_memory import CharacterMemoryGenerateResponse, CharacterStateRead
from app.schemas.common import Page

logger = get_logger(__name__)


class CharacterMemoryService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Unlike the other
    four agents, this one resolves its own input from a single branch_id -
    the character roster and branch context are both derived from already-
    persisted rows, never supplied by the caller. A story with zero
    characters yet (Character Architect hasn't run) is a valid precondition
    state, not an error: it short-circuits to an empty result without
    spending an LLM call, mirroring the "empty list is valid" philosophy
    Decision Detector established.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.branch_repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.character_repo = CharacterRepository(session)
        self.state_repo = CharacterBranchStateRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = CharacterMemoryAgent()

    async def generate(self, branch_id: UUID) -> CharacterMemoryGenerateResponse:
        branch = await self.branch_repo.get_or_404(branch_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)
        if timeline.story_id is None:
            raise ConflictError(
                "Branch's timeline has no associated story; Character Memory requires a "
                "story-linked timeline"
            )

        characters = list(await self.character_repo.list_all_by_story(timeline.story_id))
        generated_at = datetime.now(UTC)

        if not characters:
            logger.info(
                "character_memory_skipped_no_characters",
                branch_id=str(branch_id),
                story_id=str(timeline.story_id),
            )
            return CharacterMemoryGenerateResponse(
                branch_id=branch.id,
                story_id=timeline.story_id,
                states=[],
                prompt_version="n/a",
                model="n/a",
                latency_ms=0,
                attempts=0,
                prompt_tokens=None,
                completion_tokens=None,
                created_at=generated_at,
            )

        characters_by_name = {c.name: c for c in characters}
        request = CharacterMemoryRequest(
            branch=self._branch_context_from_branch(branch),
            characters=[self._profile_from_character(c) for c in characters],
        )

        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                branch_id=branch.id,
                input_snapshot={"branch_id": str(branch_id), "story_id": str(timeline.story_id)},
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": generated_at.isoformat(),
        }

        persisted: list[tuple[CharacterBranchState, str]] = []
        for state in result.output.character_states:
            character = characters_by_name[state.character_name]
            row = await self._upsert_state(character, branch, state, generation_metadata)
            persisted.append((row, character.name))

        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            branch_id=branch.id,
            input_snapshot={"branch_id": str(branch_id), "story_id": str(timeline.story_id)},
            output_snapshot={
                "result": result.output.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()
        for row, _ in persisted:
            await self.session.refresh(row)

        logger.info(
            "character_memory_persisted",
            branch_id=str(branch.id),
            story_id=str(timeline.story_id),
            state_count=len(persisted),
        )
        return CharacterMemoryGenerateResponse(
            branch_id=branch.id,
            story_id=timeline.story_id,
            states=[self._to_state_read(row, name) for row, name in persisted],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=generated_at,
        )

    async def get(self, state_id: UUID) -> CharacterStateRead:
        state = await self.state_repo.get_or_404(state_id)
        character = await self.character_repo.get_or_404(state.character_id)
        return self._to_state_read(state, character.name)

    async def list(
        self, branch_id: UUID | None, character_id: UUID | None, cursor: str | None, limit: int
    ) -> Page[CharacterStateRead]:
        filters: dict[str, UUID] = {}
        if branch_id is not None:
            filters["branch_id"] = branch_id
        if character_id is not None:
            filters["character_id"] = character_id
        items, next_cursor = await self.state_repo.list_paginated(
            cursor=cursor, limit=limit, **filters
        )
        names_by_id: dict[UUID, str] = {}
        for item in items:
            if item.character_id not in names_by_id:
                character = await self.character_repo.get_or_404(item.character_id)
                names_by_id[item.character_id] = character.name
        return Page(
            items=[self._to_state_read(item, names_by_id[item.character_id]) for item in items],
            next_cursor=next_cursor,
        )

    async def delete(self, state_id: UUID) -> None:
        state = await self.state_repo.get_or_404(state_id)
        await self.state_repo.soft_delete(state)
        await self.session.commit()

    async def _upsert_state(
        self,
        character: Character,
        branch: Branch,
        state: CharacterStateDiff,
        generation_metadata: dict,
    ) -> CharacterBranchState:
        state_diff = {
            "knowledge_state": state.knowledge_state,
            "emotional_state": state.emotional_state,
            "relationship_changes": state.relationship_changes,
            "goal_shift": state.goal_shift,
            "physical_state": state.physical_state,
        }
        existing = await self.state_repo.get_by_character_and_branch(character.id, branch.id)
        if existing is not None:
            return await self.state_repo.update(
                existing,
                state_diff=state_diff,
                drift_severity=DriftSeverity(state.drift_severity),
                drift_warning=state.drift_warning,
                generation_metadata=generation_metadata,
            )
        return await self.state_repo.create(
            character_id=character.id,
            branch_id=branch.id,
            state_diff=state_diff,
            drift_severity=DriftSeverity(state.drift_severity),
            drift_warning=state.drift_warning,
            generation_metadata=generation_metadata,
        )

    @staticmethod
    def _profile_from_character(character: Character) -> CharacterMemoryProfile:
        traits = character.canonical_traits or {}
        return CharacterMemoryProfile(
            name=character.name,
            role=traits.get("role", "supporting"),
            personality_traits=traits.get("personality_traits", []),
            motivation=traits.get("motivation") or "Unknown.",
            internal_conflict=traits.get("internal_conflict") or "Unknown.",
            external_conflict=traits.get("external_conflict") or "Unknown.",
            defining_strengths=traits.get("defining_strengths", []),
            defining_flaws=traits.get("defining_flaws", []),
            dialogue_style=traits.get("dialogue_style") or "Unspecified.",
        )

    @staticmethod
    def _branch_context_from_branch(branch: Branch) -> BranchContext:
        ds = branch.decision_summary or {}
        return BranchContext(
            name=branch.name,
            summary=branch.summary,
            initial_divergent_state=ds.get("initial_divergent_state"),
            delta_script=ds.get("delta_script"),
            affected_characters=ds.get("affected_characters", []),
            emotional_impact=ds.get("emotional_impact"),
            ending_divergence=ds.get("ending_divergence"),
            narrative_impact=ds.get("narrative_impact"),
        )

    @staticmethod
    def _to_state_read(state: CharacterBranchState, character_name: str) -> CharacterStateRead:
        return CharacterStateRead(
            id=state.id,
            character_id=state.character_id,
            character_name=character_name,
            branch_id=state.branch_id,
            state_diff=state.state_diff or {},
            drift_severity=state.drift_severity,
            drift_warning=state.drift_warning,
            created_at=state.created_at,
        )
