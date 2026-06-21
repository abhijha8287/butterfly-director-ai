from __future__ import annotations

import time

from app.agents.base.agent_result import AgentRunResult
from app.agents.base.base_agent import BaseAgent
from app.agents.editor.schema import EditorRequest, EditorResult
from app.config.logging import get_logger
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import (
    EditorAudioTrack,
    EditorComposeProvider,
    EditorComposeRequest,
)
from app.integrations.providers.factory import get_editor_provider

logger = get_logger(__name__)

PROMPT_VERSION = "n/a"
MAX_ATTEMPTS = 3


class EditorAgent(BaseAgent[EditorRequest, EditorResult]):
    """Eleventh and final agent in the pipeline. Like Video Generation, it
    never calls an LLM - it calls the configured EditorComposeProvider
    (ffmpeg, the only real implementation) directly, so there's no prompts/
    directory and prompt_version is always "n/a". Unlike every fan-out agent
    (Video Generation/Voice/Music), there's no per-item retry loop here: a
    single ffmpeg invocation either assembles the whole cut or it doesn't, so
    the whole call is retried as one unit on a transient provider failure,
    up to MAX_ATTEMPTS, rather than reporting partial per-shot/per-track
    outcomes. Trusts that the request it's given is already well-formed
    (at least one shot) - the service layer is responsible for that
    precondition, the same way Voice/Music's services refuse to call their
    agents for a storyboard version with zero shots.
    """

    name = "editor"

    def __init__(self, provider: EditorComposeProvider | None = None) -> None:
        self._provider = provider or get_editor_provider()

    async def run(self, request: EditorRequest) -> AgentRunResult[EditorResult]:
        start = time.perf_counter()
        provider_request = EditorComposeRequest(
            shot_video_urls=[shot.video_url for shot in request.shots],
            audio_tracks=[
                EditorAudioTrack(
                    source=track.source,
                    start_offset_ms=round(track.start_offset_seconds * 1000),
                )
                for track in request.audio_tracks
            ],
            output_path=request.output_path,
        )

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = await self._provider.compose(provider_request)
            except ProviderUnavailableError as exc:
                last_error = exc
                logger.warning(
                    "editor_compose_attempt_failed", attempt=attempt, error=str(exc)[:300]
                )
                continue

            output = EditorResult(
                output_path=result.output_path,
                duration_seconds=result.duration_seconds,
                provider=result.provider,
                shot_count=len(request.shots),
                audio_track_count=len(request.audio_tracks),
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "editor_succeeded",
                latency_ms=latency_ms,
                shot_count=output.shot_count,
                audio_track_count=output.audio_track_count,
            )
            return AgentRunResult(
                output=output,
                model="ffmpeg",
                prompt_version=PROMPT_VERSION,
                latency_ms=latency_ms,
                attempts=attempt,
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("editor_failed", latency_ms=latency_ms, attempts=MAX_ATTEMPTS)
        raise ProviderUnavailableError(
            f"Editor agent failed to compose the final cut after {MAX_ATTEMPTS} attempts: "
            f"{last_error}"
        ) from last_error
