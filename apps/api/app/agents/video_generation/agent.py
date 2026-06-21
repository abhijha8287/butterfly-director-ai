from __future__ import annotations

import asyncio
import time

from app.agents.base.agent_result import AgentRunResult
from app.agents.base.base_agent import BaseAgent
from app.agents.video_generation.schema import (
    ShotRenderFailure,
    ShotRenderRequest,
    ShotRenderResult,
    VideoGenerationAgentRequest,
    VideoGenerationAgentResult,
)
from app.agents.video_generation.validators import validate_against_shots
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import VideoGenerationProvider
from app.integrations.providers.base import VideoGenerationRequest as ProviderVideoRequest
from app.integrations.providers.factory import get_video_provider

logger = get_logger(__name__)

PROMPT_VERSION = "n/a"
MAX_ATTEMPTS = 3


class VideoGenerationAgent(BaseAgent[VideoGenerationAgentRequest, VideoGenerationAgentResult]):
    """Eighth agent in the pipeline, but the first that doesn't call an LLM at
    all - it calls the configured VideoGenerationProvider (Wan/HappyHorse)
    directly, so there's no prompts/ directory and prompt_version is always
    "n/a". `run()` fans every requested shot out concurrently
    (ARCHITECTURE.md's "fan-out per shot", implemented here as in-process
    asyncio.gather rather than a real Celery group/chord - see README's Known
    Limitations). Each shot gets its own independent repair loop: on a
    provider rejection it backs the prompt off (drops the negative prompt,
    then shortens the prompt) before retrying, up to MAX_ATTEMPTS, rather
    than failing the whole batch - a shot that exhausts its attempts is
    reported as a failure alongside whatever other shots succeeded.
    """

    name = "video_generation"

    def __init__(
        self, provider: VideoGenerationProvider | None = None, provider_name: str | None = None
    ) -> None:
        self._provider = provider or get_video_provider()
        self._provider_name = provider_name or get_settings().video_provider

    async def run(
        self, request: VideoGenerationAgentRequest
    ) -> AgentRunResult[VideoGenerationAgentResult]:
        start = time.perf_counter()

        outcomes = await asyncio.gather(*(self._render_shot(shot) for shot in request.shots))
        rendered = [o for o in outcomes if isinstance(o, ShotRenderResult)]
        failed = [o for o in outcomes if isinstance(o, ShotRenderFailure)]
        output = VideoGenerationAgentResult(rendered=rendered, failed=failed)

        for warning in validate_against_shots(output, request.shots):
            logger.warning("video_generation_warning", message=warning)

        latency_ms = int((time.perf_counter() - start) * 1000)
        max_attempts = max((o.attempts for o in outcomes), default=1)
        logger.info(
            "video_generation_succeeded",
            latency_ms=latency_ms,
            rendered_count=len(rendered),
            failed_count=len(failed),
        )
        return AgentRunResult(
            output=output,
            model=self._provider_name,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            attempts=max_attempts,
        )

    async def _render_shot(
        self, shot: ShotRenderRequest
    ) -> ShotRenderResult | ShotRenderFailure:
        prompt = shot.prompt
        negative_prompt = shot.negative_prompt
        last_error: Exception | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = await self._provider.generate(
                    ProviderVideoRequest(
                        prompt=prompt,
                        negative_prompt=negative_prompt or None,
                        duration_seconds=shot.duration_seconds,
                    )
                )
            except ProviderUnavailableError as exc:
                last_error = exc
                logger.warning(
                    "video_generation_shot_attempt_failed",
                    shot_number=shot.shot_number,
                    attempt=attempt,
                    error=str(exc)[:300],
                )
                if attempt == 1:
                    negative_prompt = ""
                elif attempt == 2:
                    prompt = shot.prompt[: max(len(shot.prompt) // 2, 40)]
                continue

            return ShotRenderResult(
                shot_number=shot.shot_number,
                prompt_history_id=shot.prompt_history_id,
                video_url=result.video_url,
                duration_seconds=result.duration_seconds,
                provider=result.provider,
                attempts=attempt,
                raw_response=result.raw_response,
            )

        return ShotRenderFailure(
            shot_number=shot.shot_number,
            prompt_history_id=shot.prompt_history_id,
            attempts=MAX_ATTEMPTS,
            error=str(last_error),
        )
