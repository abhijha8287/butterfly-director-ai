from __future__ import annotations

from app.config.settings import Settings, get_settings
from app.integrations.providers.base import (
    MusicGenerationProvider,
    VideoGenerationProvider,
    VoiceGenerationProvider,
)
from app.integrations.providers.dashscope_tts_provider import DashScopeTTSProvider
from app.integrations.providers.happyhorse_provider import HappyHorseProvider
from app.integrations.providers.wan_video_provider import WanVideoProvider


def get_video_provider(settings: Settings | None = None) -> VideoGenerationProvider:
    settings = settings or get_settings()
    if settings.video_provider == "wan":
        return WanVideoProvider(settings)
    if settings.video_provider == "happyhorse":
        return HappyHorseProvider(settings)
    raise ValueError(f"Unknown video provider: {settings.video_provider}")


def get_voice_provider(settings: Settings | None = None) -> VoiceGenerationProvider:
    settings = settings or get_settings()
    if settings.voice_provider == "dashscope":
        return DashScopeTTSProvider(settings)
    if settings.voice_provider == "happyhorse":
        return HappyHorseProvider(settings)
    raise ValueError(f"Unknown voice provider: {settings.voice_provider}")


def get_music_provider(settings: Settings | None = None) -> MusicGenerationProvider | None:
    settings = settings or get_settings()
    if settings.music_provider == "none":
        return None
    if settings.music_provider == "happyhorse":
        return HappyHorseProvider(settings)
    raise ValueError(f"Unknown music provider: {settings.music_provider}")
