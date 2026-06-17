from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.logging import get_logger
from app.config.settings import Settings
from app.core.exceptions import ProviderNotConfiguredError, ProviderUnavailableError
from app.integrations.providers.base import (
    MusicGenerationProvider,
    MusicGenerationRequest,
    MusicGenerationResult,
    VideoGenerationProvider,
    VideoGenerationRequest,
    VideoGenerationResult,
    VoiceGenerationProvider,
    VoiceGenerationRequest,
    VoiceGenerationResult,
)

logger = get_logger(__name__)

_RETRYABLE_EXCEPTIONS = (httpx.TransportError, httpx.HTTPStatusError)


class HappyHorseProvider(VideoGenerationProvider, VoiceGenerationProvider, MusicGenerationProvider):
    """Generic, vendor-agnostic adapter. No real backend exists for "HappyHorse" by
    name - this class exists so any future provider (Runway, Kling, Veo, ElevenLabs,
    PlayHT, ...) can be plugged in purely via configuration (HAPPYHORSE_BASE_URL,
    HAPPYHORSE_API_KEY) as long as it implements this documented generic REST contract:

      POST {base_url}/video/generate   {prompt, negative_prompt?, duration_seconds?,
                                         size?, seed?}            -> {video_url, duration_seconds?}
      POST {base_url}/voice/synthesize {text, voice?, audio_format, speed?}
                                         -> raw audio bytes (Content-Type: audio/*)
                                            OR JSON {audio_url}
      POST {base_url}/music/generate   {prompt, mood?, duration_seconds?} -> {audio_url}

    All requests carry `Authorization: Bearer {HAPPYHORSE_API_KEY}`.

    A provider whose real API does not match this shape should NOT be force-fit here -
    write a dedicated `<Vendor>Provider` class implementing the same base interfaces
    instead, then point VIDEO_PROVIDER/VOICE_PROVIDER/MUSIC_PROVIDER at it.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.happyhorse_base_url
        self._api_key = settings.happyhorse_api_key

    def _require_configured(self) -> None:
        if not self._base_url:
            raise ProviderNotConfiguredError(
                "HappyHorseProvider was selected but HAPPYHORSE_BASE_URL is not set. "
                "Configure HAPPYHORSE_BASE_URL/HAPPYHORSE_API_KEY to point at a real "
                "service implementing the generic contract documented on this class, "
                "or write a dedicated <Vendor>Provider and select that instead."
            )

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    async def generate(self, request) -> VideoGenerationResult | MusicGenerationResult:  # type: ignore[override]
        self._require_configured()
        is_video = isinstance(request, VideoGenerationRequest)
        path = "/video/generate" if is_video else "/music/generate"

        async with httpx.AsyncClient(base_url=self._base_url, timeout=120.0) as client:
            try:
                response = await client.post(
                    path,
                    json=request.model_dump(exclude_none=True),
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise ProviderUnavailableError(f"HappyHorse request timed out: {exc}") from exc

            data = response.json()

        if is_video:
            return VideoGenerationResult(
                video_url=data["video_url"],
                duration_seconds=data.get("duration_seconds"),
                provider="happyhorse",
                raw_response=data,
            )
        return MusicGenerationResult(
            audio_url=data.get("audio_url"),
            provider="happyhorse",
            raw_response=data,
        )

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    async def synthesize(self, request: VoiceGenerationRequest) -> VoiceGenerationResult:
        self._require_configured()

        async with httpx.AsyncClient(base_url=self._base_url, timeout=120.0) as client:
            try:
                response = await client.post(
                    "/voice/synthesize",
                    json=request.model_dump(exclude_none=True),
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise ProviderUnavailableError(f"HappyHorse request timed out: {exc}") from exc

            content_type = response.headers.get("content-type", "")
            if content_type.startswith("audio/"):
                return VoiceGenerationResult(
                    audio_bytes=response.content,
                    audio_format=request.audio_format,
                    provider="happyhorse",
                    raw_response={"content_type": content_type},
                )

            data = response.json()
            audio_response = await client.get(data["audio_url"])
            audio_response.raise_for_status()
            return VoiceGenerationResult(
                audio_bytes=audio_response.content,
                audio_format=request.audio_format,
                provider="happyhorse",
                raw_response=data,
            )
