from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.editor.agent import EditorAgent
from app.agents.editor.schema import EditorAudioInput, EditorRequest, EditorShotInput
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.core.exceptions import ConflictError
from app.db.models.enums import (
    AgentLogStatus,
    AssetKind,
    AssetOwnerType,
    JobStatus,
    JobType,
    MovieStatus,
    PromptStage,
    VersionEntityType,
)
from app.db.models.prompt_history import PromptHistory
from app.repositories.agent_log_repository import AgentLogRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.asset import AssetRead
from app.schemas.editor import EditorGenerateResponse

logger = get_logger(__name__)


class EditorService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Takes a
    storyboard_version_id, exactly like Prompt Director/Video Generation/
    Voice/Music, and resolves the branch from that Version row. Unlike every
    other agent, Editor produces no PromptHistory rows of its own (there's no
    `editing` PromptStage - ARCHITECTURE.md frames this step as literal
    assembly, not prompt-driven generation) - it only *reads* the
    SHOT_PROMPT/VOICE/MUSIC rows the upstream agents already wrote for this
    exact storyboard version, to build the ordered EditorRequest the
    EditorAgent assembles into one final cut. Requires a Movie row to already
    exist for the branch (created by VideoGenerationService) and at least one
    successfully rendered shot; gracefully skips any shot/line/cue that never
    rendered, the same "assemble from whatever's available" choice Storyboard/
    Prompt Director make for unresolved upstream state.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.version_repo = VersionRepository(session)
        self.branch_repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)
        self.movie_repo = MovieRepository(session)
        self.prompt_history_repo = PromptHistoryRepository(session)
        self.asset_repo = AssetRepository(session)
        self.job_repo = JobRepository(session)
        self.agent_log_repo = AgentLogRepository(session)
        self.agent = EditorAgent()

    async def generate(self, storyboard_version_id: UUID) -> EditorGenerateResponse:
        version = await self.version_repo.get_or_404(storyboard_version_id)
        if version.entity_type != VersionEntityType.STORYBOARD:
            raise ConflictError(f"Version {storyboard_version_id} is not a storyboard version")

        branch = await self.branch_repo.get_or_404(version.entity_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)

        movie = await self.movie_repo.get_by_branch_id(branch.id)
        if movie is None:
            raise ConflictError(
                f"Branch {branch.id} has no Movie yet; run Video Generation first"
            )

        shot_rows = list(
            await self.prompt_history_repo.list_by_storyboard_version(
                branch_id=branch.id,
                storyboard_version_id=storyboard_version_id,
                stage=PromptStage.SHOT_PROMPT,
            )
        )
        if not shot_rows:
            raise ConflictError(
                f"No shot prompts found for storyboard version {storyboard_version_id}; "
                "run Prompt Director and Video Generation first"
            )

        included_shots, skipped_shot_numbers = await self._resolve_shots(shot_rows)
        if not included_shots:
            raise ConflictError(
                f"No successfully rendered shots found for storyboard version "
                f"{storyboard_version_id}; cannot assemble a final cut"
            )
        included_shots.sort(key=lambda s: s.shot_number)

        shot_start_time = self._compute_shot_start_times(included_shots)

        voice_rows = list(
            await self.prompt_history_repo.list_by_storyboard_version(
                branch_id=branch.id,
                storyboard_version_id=storyboard_version_id,
                stage=PromptStage.VOICE,
            )
        )
        voice_tracks = await self._resolve_audio_tracks(
            voice_rows, shot_start_time, shot_number_key="shot_number", kind="voice"
        )

        music_rows = list(
            await self.prompt_history_repo.list_by_storyboard_version(
                branch_id=branch.id,
                storyboard_version_id=storyboard_version_id,
                stage=PromptStage.MUSIC,
            )
        )
        music_tracks = await self._resolve_audio_tracks(
            music_rows, shot_start_time, shot_number_key="start_shot_number", kind="music"
        )

        media_root = Path(get_settings().media_root) / "editor"
        output_path = str(media_root / f"{uuid4().hex}.mp4")
        request = EditorRequest(
            shots=included_shots,
            audio_tracks=voice_tracks + music_tracks,
            output_path=output_path,
        )

        movie = await self.movie_repo.update(movie, status=MovieStatus.ASSEMBLING)
        job = await self.job_repo.create(
            job_type=JobType.EDITING,
            branch_id=branch.id,
            timeline_id=timeline.id,
            status=JobStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        generated_at = datetime.now(UTC)
        try:
            result = await self.agent.run(request)
        except Exception as exc:
            await self.job_repo.update(
                job,
                status=JobStatus.FAILED,
                error_message=str(exc)[:2000],
                finished_at=datetime.now(UTC),
            )
            await self.agent_log_repo.create(
                agent_name=self.agent.name,
                branch_id=branch.id,
                job_id=job.id,
                input_snapshot={
                    "storyboard_version_id": str(storyboard_version_id),
                    "shot_count": len(included_shots),
                },
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        file_bytes = await asyncio.to_thread(Path(result.output.output_path).read_bytes)
        checksum = hashlib.sha256(file_bytes).hexdigest()
        duration = result.output.duration_seconds
        asset = await self.asset_repo.create(
            project_id=timeline.project_id,
            owner_type=AssetOwnerType.MOVIE,
            owner_id=movie.id,
            kind=AssetKind.VIDEO,
            oss_key=result.output.output_path,
            oss_bucket="local",
            mime_type="video/mp4",
            size_bytes=len(file_bytes),
            duration_seconds=Decimal(str(duration)) if duration is not None else None,
            checksum_sha256=checksum,
        )
        movie = await self.movie_repo.update(
            movie,
            status=MovieStatus.COMPLETED,
            final_asset_id=asset.id,
            duration_seconds=round(duration) if duration is not None else None,
        )
        await self.job_repo.update(
            job,
            status=JobStatus.SUCCEEDED,
            progress_pct=100,
            finished_at=datetime.now(UTC),
        )

        generation_metadata = {
            "prompt_version": result.prompt_version,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "generated_at": generated_at.isoformat(),
        }
        await self.agent_log_repo.create(
            agent_name=self.agent.name,
            branch_id=branch.id,
            job_id=job.id,
            input_snapshot={
                "storyboard_version_id": str(storyboard_version_id),
                "shot_count": len(included_shots),
                "skipped_shot_numbers": skipped_shot_numbers,
            },
            output_snapshot={
                "result": result.output.model_dump(mode="json"),
                "asset_id": str(asset.id),
                **generation_metadata,
            },
            latency_ms=result.latency_ms,
            status=AgentLogStatus.SUCCESS,
        )
        await self.session.commit()

        logger.info(
            "editor_persisted",
            branch_id=str(branch.id),
            movie_id=str(movie.id),
            shot_count=len(included_shots),
            skipped_shot_numbers=skipped_shot_numbers,
            voice_track_count=len(voice_tracks),
            music_track_count=len(music_tracks),
        )
        return EditorGenerateResponse(
            branch_id=branch.id,
            movie_id=movie.id,
            job_id=job.id,
            storyboard_version_id=storyboard_version_id,
            asset=AssetRead.model_validate(asset),
            shot_count=len(included_shots),
            voice_track_count=len(voice_tracks),
            music_track_count=len(music_tracks),
            skipped_shot_numbers=skipped_shot_numbers,
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            created_at=generated_at,
        )

    async def _resolve_shots(
        self, shot_rows: list[PromptHistory]
    ) -> tuple[list[EditorShotInput], list[int]]:
        included: list[EditorShotInput] = []
        skipped: list[int] = []
        fallback_duration = float(get_settings().wan_video_duration_seconds)

        for row in shot_rows:
            shot_number = row.input_payload.get("shot", {}).get("shot_number")
            payload = row.response_payload or {}
            asset_id = payload.get("asset_id")
            if shot_number is None or asset_id is None:
                if shot_number is not None:
                    skipped.append(shot_number)
                continue

            asset = await self.asset_repo.get_or_404(UUID(asset_id))
            duration = (
                float(asset.duration_seconds)
                if asset.duration_seconds is not None
                else row.input_payload.get("shot", {}).get("duration_seconds", fallback_duration)
            )
            included.append(
                EditorShotInput(
                    shot_number=shot_number,
                    video_url=asset.oss_key,
                    duration_seconds=duration,
                )
            )

        return included, sorted(skipped)

    @staticmethod
    def _compute_shot_start_times(shots: list[EditorShotInput]) -> dict[int, float]:
        start_times: dict[int, float] = {}
        elapsed = 0.0
        for shot in shots:
            start_times[shot.shot_number] = elapsed
            elapsed += shot.duration_seconds or 0.0
        return start_times

    async def _resolve_audio_tracks(
        self,
        rows: list[PromptHistory],
        shot_start_time: dict[int, float],
        *,
        shot_number_key: str,
        kind: Literal["voice", "music"],
    ) -> list[EditorAudioInput]:
        tracks: list[EditorAudioInput] = []
        for row in rows:
            payload = row.response_payload or {}
            asset_id = payload.get("asset_id")
            if asset_id is None:
                continue

            shot_number = row.input_payload.get(shot_number_key)
            start_time = shot_start_time.get(shot_number) if isinstance(shot_number, int) else None
            if start_time is None:
                logger.warning(
                    "editor_audio_track_skipped",
                    kind=kind,
                    shot_number=shot_number,
                    reason="referenced shot was not included in the final cut",
                )
                continue

            asset = await self.asset_repo.get_or_404(UUID(asset_id))
            tracks.append(
                EditorAudioInput(
                    source=asset.oss_key,
                    start_offset_seconds=start_time,
                    kind=kind,
                )
            )
        return tracks
