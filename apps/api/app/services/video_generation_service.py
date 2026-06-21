from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.video_generation.agent import VideoGenerationAgent
from app.agents.video_generation.schema import ShotRenderRequest, VideoGenerationAgentRequest
from app.config.logging import get_logger
from app.core.exceptions import ConflictError
from app.db.models.branch import Branch
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
from app.db.models.movie import Movie
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
from app.schemas.video_generation import (
    FailedShotRead,
    RenderedShotRead,
    VideoGenerationGenerateResponse,
)

logger = get_logger(__name__)


class VideoGenerationService:
    """Follows the established reference service shape: run the agent,
    persist the validated output + generation provenance, and write an
    AgentLog audit row regardless of success or failure. Takes a
    storyboard_version_id, exactly like Prompt Director, and resolves the
    branch from that Version row - the input to render is every PromptHistory
    row Prompt Director created for that exact storyboard version (scoped via
    PromptHistoryRepository.list_by_storyboard_version, since reruns are
    additive and a branch can have several batches of shot prompts over
    time). Persists one Asset row per successfully rendered shot and writes
    each shot's outcome back onto the PromptHistory row it came from
    (response_payload), per ARCHITECTURE.md's "writes assets rows +
    prompts.response_payload". Also creates one Job row (job_type=video_render)
    per run and moves the branch's Movie to RENDERING, mirroring the
    movies.status/jobs.progress_pct bookkeeping ARCHITECTURE.md describes for
    this step - this build does that bookkeeping synchronously in-request
    rather than via real Celery tasks, see README's Known Limitations.
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
        self.agent = VideoGenerationAgent()

    async def generate(self, storyboard_version_id: UUID) -> VideoGenerationGenerateResponse:
        version = await self.version_repo.get_or_404(storyboard_version_id)
        if version.entity_type != VersionEntityType.STORYBOARD:
            raise ConflictError(
                f"Version {storyboard_version_id} is not a storyboard version"
            )

        branch = await self.branch_repo.get_or_404(version.entity_id)
        timeline = await self.timeline_repo.get_or_404(branch.timeline_id)

        prompt_rows = list(
            await self.prompt_history_repo.list_by_storyboard_version(
                branch_id=branch.id,
                storyboard_version_id=storyboard_version_id,
                stage=PromptStage.SHOT_PROMPT,
            )
        )
        if not prompt_rows:
            raise ConflictError(
                f"No shot prompts found for storyboard version {storyboard_version_id}; "
                "run Prompt Director first"
            )

        rows_by_history_id = {row.id: row for row in prompt_rows}
        shots = [self._shot_request_from_row(row) for row in prompt_rows]
        request = VideoGenerationAgentRequest(shots=shots)

        movie = await self._get_or_create_movie(branch)
        movie = await self.movie_repo.update(movie, status=MovieStatus.RENDERING)

        job = await self.job_repo.create(
            job_type=JobType.VIDEO_RENDER,
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
                    "shot_count": len(shots),
                },
                output_snapshot=None,
                latency_ms=None,
                status=AgentLogStatus.ERROR,
                error_detail=str(exc)[:2000],
            )
            await self.session.commit()
            raise

        rendered_reads: list[RenderedShotRead] = []
        for shot_result in result.output.rendered:
            history_row = rows_by_history_id[shot_result.prompt_history_id]
            asset = await self.asset_repo.create(
                project_id=timeline.project_id,
                owner_type=AssetOwnerType.SHOT,
                owner_id=history_row.id,
                kind=AssetKind.VIDEO,
                oss_key=shot_result.video_url,
                oss_bucket=shot_result.provider,
                mime_type="video/mp4",
                size_bytes=0,
                duration_seconds=(
                    Decimal(str(shot_result.duration_seconds))
                    if shot_result.duration_seconds is not None
                    else None
                ),
            )
            await self.prompt_history_repo.update(
                history_row,
                response_payload={
                    "asset_id": str(asset.id),
                    "video_url": shot_result.video_url,
                    "provider": shot_result.provider,
                    "attempts": shot_result.attempts,
                },
            )
            rendered_reads.append(
                RenderedShotRead(
                    shot_number=shot_result.shot_number,
                    asset=AssetRead.model_validate(asset),
                )
            )

        failed_reads: list[FailedShotRead] = []
        for shot_failure in result.output.failed:
            history_row = rows_by_history_id[shot_failure.prompt_history_id]
            await self.prompt_history_repo.update(
                history_row,
                response_payload={
                    "error": shot_failure.error,
                    "attempts": shot_failure.attempts,
                },
            )
            failed_reads.append(
                FailedShotRead(
                    shot_number=shot_failure.shot_number,
                    attempts=shot_failure.attempts,
                    error=shot_failure.error,
                )
            )

        job_status = JobStatus.FAILED if result.output.failed else JobStatus.SUCCEEDED
        error_message = (
            None
            if not result.output.failed
            else f"{len(result.output.failed)} of {len(shots)} shots failed: "
            f"{sorted(f.shot_number for f in result.output.failed)}"
        )
        await self.job_repo.update(
            job,
            status=job_status,
            progress_pct=round(len(result.output.rendered) / len(shots) * 100),
            error_message=error_message,
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
                "shot_count": len(shots),
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
            "video_generation_persisted",
            branch_id=str(branch.id),
            movie_id=str(movie.id),
            rendered_count=len(rendered_reads),
            failed_count=len(failed_reads),
        )
        return VideoGenerationGenerateResponse(
            branch_id=branch.id,
            movie_id=movie.id,
            job_id=job.id,
            storyboard_version_id=storyboard_version_id,
            rendered=rendered_reads,
            failed_shots=failed_reads,
            prompt_version=generation_metadata["prompt_version"],
            model=generation_metadata["model"],
            latency_ms=generation_metadata["latency_ms"],
            attempts=generation_metadata["attempts"],
            created_at=generated_at,
        )

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
    def _shot_request_from_row(row: PromptHistory) -> ShotRenderRequest:
        shot = row.input_payload.get("shot", {})
        duration = shot.get("duration_seconds")
        return ShotRenderRequest(
            shot_number=shot["shot_number"],
            prompt_history_id=row.id,
            prompt=row.rendered_prompt,
            negative_prompt=row.input_payload.get("negative_prompt", ""),
            duration_seconds=round(duration) if duration is not None else None,
        )
