from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompt_director.agent import PromptDirectorAgent
from app.agents.prompt_director.schema import (
    CharacterVisualProfile,
    PromptDirectorRequest,
    ShotContext,
)
from app.agents.story_architect.schema import StoryBible
from app.agents.storyboard.schema import Shot
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.core.exceptions import ConflictError
from app.db.models.character import Character
from app.db.models.character_branch_state import CharacterBranchState
from app.db.models.enums import AgentLogStatus, PromptProvider, PromptStage, VersionEntityType
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.prompt_director import PromptDirectorGenerateResponse
from app.schemas.prompt_history import PromptHistoryRead

logger = get_logger(__name__)

_VIDEO_PROVIDER_TO_PROMPT_PROVIDER = {
    "wan": PromptProvider.WAN,
    "happyhorse": PromptProvider.HAPPYHORSE,
}


class PromptDirectorService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Unlike Character
    Memory/Storyboard, this agent persists through the pre-existing,
    already-tested `prompt_history` table (ARCHITECTURE.md's `prompts` table)
    rather than a bespoke one - it predates this agent (built read-only) and
    already has exactly the columns needed: rendered_prompt for the positive
    prompt, input_payload for everything else (shot reference, negative
    prompt, consistency/style tokens). Input is a storyboard_version_id
    (not a branch_id) since a branch can have multiple storyboard versions
    and the caller should be explicit about which one to direct prompts for.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.version_repo = VersionRepository(session)
        self.branch_repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.story_repo = StoryRepository(session)
        self.character_repo = CharacterRepository(session)
        self.character_state_repo = CharacterBranchStateRepository(session)
        self.prompt_history_repo = PromptHistoryRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = PromptDirectorAgent()

    async def generate(self, storyboard_version_id: UUID) -> PromptDirectorGenerateResponse:
        version = await self.version_repo.get_or_404(storyboard_version_id)
        if version.entity_type != VersionEntityType.STORYBOARD:
            raise ConflictError(
                f"Version {storyboard_version_id} is not a storyboard version"
            )

        branch = await self.branch_repo.get_or_404(version.entity_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)
        if timeline.story_id is None:
            raise ConflictError(
                "Branch's timeline has no associated story; Prompt Director requires a "
                "story-linked timeline"
            )

        story = await self.story_repo.get_or_404(timeline.story_id)
        story_bible = StoryBible.model_validate(story.world_bible)

        shots_raw = (version.snapshot or {}).get("shots", [])
        if not shots_raw:
            raise ConflictError(f"Storyboard version {storyboard_version_id} has no shots")

        characters = list(await self.character_repo.list_all_by_story(story.id))
        characters_by_name = {c.name: c for c in characters}
        states_by_character_id = {
            s.character_id: s
            for s in await self.character_state_repo.list_all_by_branch(branch.id)
        }

        shots_by_number = {raw["shot_number"]: raw for raw in shots_raw}
        shot_contexts = [
            self._shot_context_from_shot(
                Shot(**raw), characters_by_name, states_by_character_id
            )
            for raw in shots_raw
        ]
        request = PromptDirectorRequest(story_bible=story_bible, shots=shot_contexts)
        generated_at = datetime.now(UTC)

        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                branch_id=branch.id,
                input_snapshot={
                    "storyboard_version_id": str(storyboard_version_id),
                    "story_id": str(story.id),
                },
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        provider = _VIDEO_PROVIDER_TO_PROMPT_PROVIDER[get_settings().video_provider]
        created: list[tuple[int, PromptHistoryRead]] = []
        for shot_prompt in result.output.shot_prompts:
            row = await self.prompt_history_repo.create(
                branch_id=branch.id,
                agent_name=self.agent.name,
                stage=PromptStage.SHOT_PROMPT,
                provider=provider,
                input_payload={
                    "storyboard_version_id": str(storyboard_version_id),
                    "shot": shots_by_number[shot_prompt.shot_number],
                    "negative_prompt": shot_prompt.negative_prompt,
                    "consistency_tokens": shot_prompt.consistency_tokens,
                    "style_tokens": shot_prompt.style_tokens,
                },
                rendered_prompt=shot_prompt.positive_prompt,
                response_payload=None,
                token_usage=None,
            )
            created.append((shot_prompt.shot_number, PromptHistoryRead.model_validate(row)))

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
            input_snapshot={
                "storyboard_version_id": str(storyboard_version_id),
                "story_id": str(story.id),
            },
            output_snapshot={
                "result": result.output.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()

        logger.info(
            "prompt_director_persisted",
            branch_id=str(branch.id),
            storyboard_version_id=str(storyboard_version_id),
            shot_prompt_count=len(created),
        )
        created.sort(key=lambda pair: pair[0])
        return PromptDirectorGenerateResponse(
            branch_id=branch.id,
            storyboard_version_id=storyboard_version_id,
            shot_prompts=[row for _, row in created],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=generated_at,
        )

    @staticmethod
    def _shot_context_from_shot(
        shot: Shot,
        characters_by_name: dict[str, Character],
        states_by_character_id: dict[UUID, CharacterBranchState],
    ) -> ShotContext:
        profiles: list[CharacterVisualProfile] = []
        for name in shot.characters_present:
            character = characters_by_name.get(name)
            if character is None:
                continue
            traits = character.canonical_traits or {}
            kwargs = {
                "name": character.name,
                "physical_description": character.description or "",
                "wardrobe_style": traits.get("wardrobe_style", ""),
            }
            state = states_by_character_id.get(character.id)
            if state is not None:
                diff = state.state_diff or {}
                kwargs["emotional_state"] = diff.get("emotional_state", "unchanged")
                kwargs["physical_state"] = diff.get("physical_state", "unchanged")
            profiles.append(CharacterVisualProfile(**kwargs))
        return ShotContext(
            scene=shot.scene,
            shot_number=shot.shot_number,
            description=shot.description,
            camera=shot.camera,
            duration_seconds=shot.duration_seconds,
            characters=profiles,
        )
