from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.schema import StoryBible
from app.agents.voice.agent import VoiceAgent
from app.agents.voice.schema import ShotScript, VoiceCharacterProfile, VoiceRequest
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.core.exceptions import ConflictError
from app.db.models.character import Character
from app.db.models.character_branch_state import CharacterBranchState
from app.db.models.enums import (
    AgentLogStatus,
    AssetKind,
    AssetOwnerType,
    PromptProvider,
    PromptStage,
    VersionEntityType,
)
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.asset import AssetRead
from app.schemas.voice import FailedLineRead, RenderedLineRead, VoiceGenerateResponse

logger = get_logger(__name__)

_VOICE_PROVIDER_TO_PROMPT_PROVIDER = {
    "dashscope": PromptProvider.DASHSCOPE,
    "happyhorse": PromptProvider.HAPPYHORSE,
}


class VoiceService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Takes a
    storyboard_version_id, exactly like Prompt Director and Video Generation,
    and resolves the branch from that Version row. Unlike either of those,
    VoiceAgent.run() does both the LLM dialogue-extraction call AND the
    per-line provider synthesis internally - so this service persists fresh
    PromptHistory rows (stage=voice) directly from the agent's combined
    output, rather than consuming rows a prior agent already wrote. Persists
    one Asset row per successfully synthesized line, writing the raw audio
    bytes to local disk under settings.media_root (no real OSS upload
    pipeline exists in this build - see README's Known Limitations).
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
        self.asset_repo = AssetRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = VoiceAgent()

    async def generate(self, storyboard_version_id: UUID) -> VoiceGenerateResponse:
        version = await self.version_repo.get_or_404(storyboard_version_id)
        if version.entity_type != VersionEntityType.STORYBOARD:
            raise ConflictError(f"Version {storyboard_version_id} is not a storyboard version")

        branch = await self.branch_repo.get_or_404(version.entity_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)
        if timeline.story_id is None:
            raise ConflictError(
                "Branch's timeline has no associated story; Voice requires a "
                "story-linked timeline"
            )

        story = await self.story_repo.get_or_404(timeline.story_id)
        story_bible = StoryBible.model_validate(story.world_bible)

        shots_raw = (version.snapshot or {}).get("shots", [])
        if not shots_raw:
            raise ConflictError(f"Storyboard version {storyboard_version_id} has no shots")
        shots = [
            ShotScript(
                scene=raw["scene"],
                shot_number=raw["shot_number"],
                description=raw["description"],
                characters_present=raw.get("characters_present", []),
            )
            for raw in shots_raw
        ]

        characters = list(await self.character_repo.list_all_by_story(story.id))
        states_by_character_id = {
            s.character_id: s
            for s in await self.character_state_repo.list_all_by_branch(branch.id)
        }
        character_profiles = [
            self._voice_profile_from_character(c, states_by_character_id.get(c.id))
            for c in characters
        ]

        request = VoiceRequest(
            story_bible=story_bible,
            branch_name=branch.name,
            delta_script=(branch.decision_summary or {}).get("delta_script"),
            shots=shots,
            characters=character_profiles,
        )
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

        provider = _VOICE_PROVIDER_TO_PROMPT_PROVIDER[get_settings().voice_provider]
        media_root = Path(get_settings().media_root) / "voice"

        rendered_reads: list[RenderedLineRead] = []
        for line_result in result.output.lines:
            row = await self.prompt_history_repo.create(
                branch_id=branch.id,
                agent_name=self.agent.name,
                stage=PromptStage.VOICE,
                provider=provider,
                input_payload={
                    "storyboard_version_id": str(storyboard_version_id),
                    "shot_number": line_result.shot_number,
                    "character_name": line_result.character_name,
                    "delivery_note": line_result.delivery_note,
                },
                rendered_prompt=line_result.line_text,
                response_payload=None,
                token_usage=None,
            )
            file_name = f"{row.id}.{line_result.audio_format}"
            file_path = await asyncio.to_thread(
                self._write_audio_file, media_root, file_name, line_result.audio_bytes
            )
            checksum = hashlib.sha256(line_result.audio_bytes).hexdigest()
            asset = await self.asset_repo.create(
                project_id=timeline.project_id,
                owner_type=AssetOwnerType.VOICE,
                owner_id=row.id,
                kind=AssetKind.AUDIO,
                oss_key=str(file_path),
                oss_bucket="local",
                mime_type=f"audio/{line_result.audio_format}",
                size_bytes=len(line_result.audio_bytes),
                duration_seconds=None,
                checksum_sha256=checksum,
            )
            await self.prompt_history_repo.update(
                row,
                response_payload={
                    "asset_id": str(asset.id),
                    "provider": line_result.provider,
                    "attempts": line_result.attempts,
                },
            )
            rendered_reads.append(
                RenderedLineRead(
                    shot_number=line_result.shot_number,
                    character_name=line_result.character_name,
                    line_text=line_result.line_text,
                    delivery_note=line_result.delivery_note,
                    asset=AssetRead.model_validate(asset),
                )
            )

        failed_reads: list[FailedLineRead] = []
        for failure in result.output.failed_lines:
            await self.prompt_history_repo.create(
                branch_id=branch.id,
                agent_name=self.agent.name,
                stage=PromptStage.VOICE,
                provider=provider,
                input_payload={
                    "storyboard_version_id": str(storyboard_version_id),
                    "shot_number": failure.shot_number,
                    "character_name": failure.character_name,
                    "delivery_note": failure.delivery_note,
                },
                rendered_prompt=failure.line_text,
                response_payload={"error": failure.error, "attempts": failure.attempts},
                token_usage=None,
            )
            failed_reads.append(
                FailedLineRead(
                    shot_number=failure.shot_number,
                    character_name=failure.character_name,
                    line_text=failure.line_text,
                    attempts=failure.attempts,
                    error=failure.error,
                )
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
            input_snapshot={
                "storyboard_version_id": str(storyboard_version_id),
                "story_id": str(story.id),
            },
            output_snapshot={
                # exclude audio_bytes: raw audio isn't JSON-serializable (it's
                # arbitrary binary, not necessarily valid UTF-8 text) and doesn't
                # belong in an audit log regardless - the Asset rows are the
                # actual record of what was synthesized.
                "result": result.output.model_dump(
                    mode="json", exclude={"lines": {"__all__": {"audio_bytes"}}}
                ),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()

        logger.info(
            "voice_persisted",
            branch_id=str(branch.id),
            storyboard_version_id=str(storyboard_version_id),
            line_count=len(rendered_reads),
            failed_count=len(failed_reads),
        )
        return VoiceGenerateResponse(
            branch_id=branch.id,
            storyboard_version_id=storyboard_version_id,
            lines=rendered_reads,
            failed_lines=failed_reads,
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            prompt_tokens=generation_metadata["prompt_tokens"],
            completion_tokens=generation_metadata["completion_tokens"],
            created_at=generated_at,
        )

    @staticmethod
    def _write_audio_file(media_root: Path, file_name: str, audio_bytes: bytes) -> Path:
        media_root.mkdir(parents=True, exist_ok=True)
        file_path = media_root / file_name
        file_path.write_bytes(audio_bytes)
        return file_path

    @staticmethod
    def _voice_profile_from_character(
        character: Character, state: CharacterBranchState | None
    ) -> VoiceCharacterProfile:
        traits = character.canonical_traits or {}
        voice = character.voice_profile or {}
        emotional_state = "unchanged"
        if state is not None:
            emotional_state = (state.state_diff or {}).get("emotional_state", "unchanged")
        return VoiceCharacterProfile(
            name=character.name,
            personality_traits=traits.get("personality_traits", []),
            dialogue_style=traits.get("dialogue_style", ""),
            voice_descriptor=voice.get("descriptor", ""),
            emotional_state=emotional_state,
        )
