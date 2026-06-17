from __future__ import annotations

import asyncio
import time

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.logging import get_logger
from app.config.settings import Settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import (
    VideoGenerationProvider,
    VideoGenerationRequest,
    VideoGenerationResult,
)

logger = get_logger(__name__)

_RETRYABLE_EXCEPTIONS = (httpx.TransportError, httpx.HTTPStatusError)
_TASK_CREATE_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"


class WanVideoProvider(VideoGenerationProvider):
    """Real DashScope Wan text-to-video provider: async task create + poll.

    Verified against https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.dashscope_base_url
        self._api_key = settings.dashscope_api_key

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    async def _create_task(self, client: httpx.AsyncClient, request: VideoGenerationRequest) -> str:
        video_input: dict = {"prompt": request.prompt}
        if request.negative_prompt:
            video_input["negative_prompt"] = request.negative_prompt

        parameters: dict = {
            "size": request.size or self._settings.wan_video_size,
            "duration": request.duration_seconds or self._settings.wan_video_duration_seconds,
            "prompt_extend": True,
            "watermark": False,
        }
        if request.seed is not None:
            parameters["seed"] = request.seed

        response = await client.post(
            _TASK_CREATE_PATH,
            json={"model": self._settings.wan_model, "input": video_input, "parameters": parameters},
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "X-DashScope-Async": "enable",
            },
        )
        response.raise_for_status()
        return response.json()["output"]["task_id"]

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    async def _poll_task(self, client: httpx.AsyncClient, task_id: str) -> dict:
        response = await client.get(
            f"/api/v1/tasks/{task_id}", headers={"Authorization": f"Bearer {self._api_key}"}
        )
        response.raise_for_status()
        return response.json()

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        if not self._api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY is not configured")

        async with httpx.AsyncClient(base_url=self._base_url, timeout=60.0) as client:
            task_id = await self._create_task(client, request)
            logger.info("wan_video_task_created", task_id=task_id)

            deadline = time.monotonic() + self._settings.provider_poll_timeout_seconds
            while True:
                payload = await self._poll_task(client, task_id)
                status = payload["output"]["task_status"]

                if status == "SUCCEEDED":
                    logger.info("wan_video_task_succeeded", task_id=task_id)
                    return VideoGenerationResult(
                        video_url=payload["output"]["video_url"],
                        duration_seconds=request.duration_seconds
                        or self._settings.wan_video_duration_seconds,
                        provider="wan",
                        raw_response=payload,
                    )

                if status in ("FAILED", "CANCELED", "UNKNOWN"):
                    raise ProviderUnavailableError(
                        f"Wan video task {task_id} ended with status {status}",
                        details={"raw_response": payload},
                    )

                if time.monotonic() > deadline:
                    raise ProviderUnavailableError(
                        f"Wan video task {task_id} timed out after "
                        f"{self._settings.provider_poll_timeout_seconds}s"
                    )

                await asyncio.sleep(self._settings.provider_poll_interval_seconds)
