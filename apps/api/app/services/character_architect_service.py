from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.character_architect.agent import CharacterArchitectAgent
from app.agents.character_architect.schema import CharacterProfile, CharacterRequest, VoiceProfile
from app.agents.story_architect.schema import StoryBible
from app.config.logging import get_logger
from app.db.models.character import Character
from app.db.models.enums import AgentLogStatus
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.story_repository import StoryRepository
from app.schemas.character_architect import CharacterGenerateResponse, CharacterProfileRead
from app.schemas.common import Page

logger = get_logger(__name__)


class CharacterArchitectService:
    """Follows the Story Architect's reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. The one structural
    difference is that one agent run produces a whole roster, so this service
    persists N Character rows per generate() call, all sharing one
    generation_metadata blob and one AgentLog entry.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.story_repo = StoryRepository(session)
        self.character_repo = CharacterRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = CharacterArchitectAgent()

    async def generate(self, story_id: UUID) -> CharacterGenerateResponse:
        story = await self.story_repo.get_or_404(story_id)
        story_bible = StoryBible.model_validate(story.world_bible)
        request = CharacterRequest(story_bible=story_bible)

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

        roster = result.output
        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        characters: list[Character] = []
        for profile in roster.characters:
            character = await self.character_repo.create(
                project_id=story.project_id,
                story_id=story.id,
                name=profile.name,
                description=profile.physical_description,
                voice_profile=profile.voice_profile.model_dump(mode="json"),
                canonical_traits=self._traits_from_profile(profile),
                generation_metadata=generation_metadata,
            )
            characters.append(character)

        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            input_snapshot={"story_id": str(story_id)},
            output_snapshot={
                "roster": roster.model_dump(mode="json"),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )

        await self.session.commit()
        for character in characters:
            await self.session.refresh(character)

        logger.info(
            "character_architect_persisted",
            story_id=str(story.id),
            character_count=len(characters),
        )
        return CharacterGenerateResponse(
            story_id=story.id,
            characters=[self._to_profile_read(c) for c in characters],
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=characters[0].created_at if characters else story.created_at,
        )

    async def get(self, character_id: UUID) -> CharacterProfileRead:
        character = await self.character_repo.get_or_404(character_id)
        return self._to_profile_read(character)

    async def list(
        self, story_id: UUID | None, cursor: str | None, limit: int
    ) -> Page[CharacterProfileRead]:
        filters = {"story_id": story_id} if story_id is not None else {}
        items, next_cursor = await self.character_repo.list_paginated(
            cursor=cursor, limit=limit, **filters
        )
        return Page(
            items=[self._to_profile_read(c) for c in items],
            next_cursor=next_cursor,
        )

    async def delete(self, character_id: UUID) -> None:
        character = await self.character_repo.get_or_404(character_id)
        await self.character_repo.soft_delete(character)
        await self.session.commit()

    @staticmethod
    def _traits_from_profile(profile: CharacterProfile) -> dict:
        return {
            "role": profile.role,
            "age_range": profile.age_range,
            "wardrobe_style": profile.wardrobe_style,
            "personality_traits": profile.personality_traits,
            "backstory": profile.backstory,
            "motivation": profile.motivation,
            "internal_conflict": profile.internal_conflict,
            "external_conflict": profile.external_conflict,
            "character_arc": profile.character_arc,
            "relationships": profile.relationships,
            "defining_strengths": profile.defining_strengths,
            "defining_flaws": profile.defining_flaws,
            "dialogue_style": profile.dialogue_style,
            "secret": profile.secret,
        }

    @staticmethod
    def _to_profile_read(character: Character) -> CharacterProfileRead:
        traits = character.canonical_traits or {}
        voice = character.voice_profile or {}
        return CharacterProfileRead(
            id=character.id,
            story_id=character.story_id,
            name=character.name,
            role=traits.get("role", "supporting"),
            age_range=traits.get("age_range", "unknown"),
            physical_description=character.description or "",
            wardrobe_style=traits.get("wardrobe_style", ""),
            personality_traits=traits.get("personality_traits", []),
            backstory=traits.get("backstory", ""),
            motivation=traits.get("motivation", ""),
            internal_conflict=traits.get("internal_conflict", ""),
            external_conflict=traits.get("external_conflict", ""),
            character_arc=traits.get("character_arc", ""),
            relationships=traits.get("relationships", []),
            defining_strengths=traits.get("defining_strengths", []),
            defining_flaws=traits.get("defining_flaws", []),
            dialogue_style=traits.get("dialogue_style", ""),
            voice_profile=VoiceProfile(
                descriptor=voice.get("descriptor", ""),
                tone=voice.get("tone", ""),
                pace=voice.get("pace", ""),
                pitch=voice.get("pitch", ""),
            ),
            secret=traits.get("secret"),
            created_at=character.created_at,
        )
