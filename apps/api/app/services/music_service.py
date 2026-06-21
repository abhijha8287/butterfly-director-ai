from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.music.agent import MusicAgent
from app.agents.music.schema import MusicRequest, MusicShotScript
from app.agents.story_architect.schema import StoryBible
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.core.exceptions import ConflictError
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
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.asset import AssetRead
from app.schemas.music import FailedCueRead, MusicGenerateResponse, RenderedCueRead

logger = get_logger(__name__)

_MUSIC_PROVIDER_TO_PROMPT_PROVIDER = {
    "happyhorse": PromptProvider.HAPPYHORSE,
    "none": PromptProvider.NONE,
}


class MusicService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Takes a
    storyboard_version_id, exactly like Prompt Director/Video Generation/
    Voice, and resolves the branch from that Version row. Like Voice,
    MusicAgent.run() does both the LLM cue-extraction call AND the
    per-cue provider synthesis internally - so this service persists fresh
    PromptHistory rows (stage=music) directly from the agent's combined
    output. Unlike Voice, synthesis is optional (MUSIC_PROVIDER defaults to
    "none"): a cue with no audio_url/audio_bytes is still persisted as a
    PromptHistory row, just without a corresponding Asset row.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.version_repo = VersionRepository(session)
        self.branch_repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.story_repo = StoryRepository(session)
        self.prompt_history_repo = PromptHistoryRepository(session)
        self.asset_repo = AssetRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = MusicAgent()

    async def generate(self, storyboard_version_id: UUID) -> MusicGenerateResponse:
        version = await self.version_repo.get_or_404(storyboard_version_id)
        if version.entity_type != VersionEntityType.STORYBOARD:
            raise ConflictError(f"Version {storyboard_version_id} is not a storyboard version")

        branch = await self.branch_repo.get_or_404(version.entity_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)
        if timeline.story_id is None:
            raise ConflictError(
                "Branch's timeline has no associated story; Music requires a "
                "story-linked timeline"
            )

        story = await self.story_repo.get_or_404(timeline.story_id)
        story_bible = StoryBible.model_validate(story.world_bible)

        shots_raw = (version.snapshot or {}).get("shots", [])
        if not shots_raw:
            raise ConflictError(f"Storyboard version {storyboard_version_id} has no shots")
        shots = [
            MusicShotScript(
                scene=raw["scene"],
                shot_number=raw["shot_number"],
                description=raw["description"],
                duration_seconds=raw["duration_seconds"],
            )
            for raw in shots_raw
        ]

        request = MusicRequest(
            story_bible=story_bible,
            branch_name=branch.name,
            branch_summary=branch.summary or "",
            shots=shots,
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

        provider = _MUSIC_PROVIDER_TO_PROMPT_PROVIDER[get_settings().music_provider]
        media_root = Path(get_settings().media_root) / "music"

        rendered_reads: list[RenderedCueRead] = []
        for cue_result in result.output.cues:
            row = await self.prompt_history_repo.create(
                branch_id=branch.id,
                agent_name=self.agent.name,
                stage=PromptStage.MUSIC,
                provider=provider,
                input_payload={
                    "storyboard_version_id": str(storyboard_version_id),
                    "start_shot_number": cue_result.start_shot_number,
                    "end_shot_number": cue_result.end_shot_number,
                    "mood": cue_result.mood,
                    "tempo_bpm": cue_result.tempo_bpm,
                },
                rendered_prompt=cue_result.generation_prompt,
                response_payload=None,
                token_usage=None,
            )

            asset = None
            if cue_result.audio_bytes is not None:
                file_name = f"{row.id}.mp3"
                file_path = await asyncio.to_thread(
                    self._write_audio_file, media_root, file_name, cue_result.audio_bytes
                )
                checksum = hashlib.sha256(cue_result.audio_bytes).hexdigest()
                asset = await self.asset_repo.create(
                    project_id=timeline.project_id,
                    owner_type=AssetOwnerType.MUSIC,
                    owner_id=row.id,
                    kind=AssetKind.AUDIO,
                    oss_key=str(file_path),
                    oss_bucket="local",
                    mime_type="audio/mp3",
                    size_bytes=len(cue_result.audio_bytes),
                    duration_seconds=None,
                    checksum_sha256=checksum,
                )
            elif cue_result.audio_url is not None:
                asset = await self.asset_repo.create(
                    project_id=timeline.project_id,
                    owner_type=AssetOwnerType.MUSIC,
                    owner_id=row.id,
                    kind=AssetKind.AUDIO,
                    oss_key=cue_result.audio_url,
                    oss_bucket=cue_result.provider or "unknown",
                    mime_type="audio/mp3",
                    size_bytes=0,
                    duration_seconds=None,
                    checksum_sha256=None,
                )

            await self.prompt_history_repo.update(
                row,
                response_payload={
                    "asset_id": str(asset.id) if asset is not None else None,
                    "provider": cue_result.provider,
                    "attempts": cue_result.attempts,
                },
            )
            rendered_reads.append(
                RenderedCueRead(
                    start_shot_number=cue_result.start_shot_number,
                    end_shot_number=cue_result.end_shot_number,
                    mood=cue_result.mood,
                    tempo_bpm=cue_result.tempo_bpm,
                    generation_prompt=cue_result.generation_prompt,
                    asset=AssetRead.model_validate(asset) if asset is not None else None,
                )
            )

        failed_reads: list[FailedCueRead] = []
        for failure in result.output.failed_cues:
            await self.prompt_history_repo.create(
                branch_id=branch.id,
                agent_name=self.agent.name,
                stage=PromptStage.MUSIC,
                provider=provider,
                input_payload={
                    "storyboard_version_id": str(storyboard_version_id),
                    "start_shot_number": failure.start_shot_number,
                    "end_shot_number": failure.end_shot_number,
                    "mood": failure.mood,
                    "tempo_bpm": failure.tempo_bpm,
                },
                rendered_prompt=failure.generation_prompt,
                response_payload={"error": failure.error, "attempts": failure.attempts},
                token_usage=None,
            )
            failed_reads.append(
                FailedCueRead(
                    start_shot_number=failure.start_shot_number,
                    end_shot_number=failure.end_shot_number,
                    mood=failure.mood,
                    tempo_bpm=failure.tempo_bpm,
                    generation_prompt=failure.generation_prompt,
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
                    mode="json", exclude={"cues": {"__all__": {"audio_bytes"}}}
                ),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()

        logger.info(
            "music_persisted",
            branch_id=str(branch.id),
            storyboard_version_id=str(storyboard_version_id),
            cue_count=len(rendered_reads),
            failed_count=len(failed_reads),
        )
        return MusicGenerateResponse(
            branch_id=branch.id,
            storyboard_version_id=storyboard_version_id,
            cues=rendered_reads,
            failed_cues=failed_reads,
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
