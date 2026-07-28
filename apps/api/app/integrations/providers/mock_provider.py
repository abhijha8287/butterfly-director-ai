from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from app.integrations.providers.base import (
    EditorComposeProvider,
    EditorComposeRequest,
    EditorComposeResult,
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

_PLACEHOLDER_VIDEO_BASE = "https://www.w3schools.com/html/mov_bbb.mp4"


class MockVideoProvider(VideoGenerationProvider):
    """Returns a unique placeholder video URL per prompt — no external API call.
    Use VIDEO_PROVIDER=mock for local development when Wan quota is unavailable.
    """

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        slug = hashlib.sha256(request.prompt.encode()).hexdigest()[:12]
        video_url = f"mock://video/{slug}"
        return VideoGenerationResult(
            video_url=video_url,
            duration_seconds=5.0,
            provider="mock",
            raw_response={"prompt": request.prompt, "mock": True},
        )


class MockVoiceProvider(VoiceGenerationProvider):
    """Returns a tiny silent MP3 instantly — no external API call.
    Use VOICE_PROVIDER=mock for local development when DashScope TTS is unavailable.
    """

    # 1-second silent MP3 (ID3v2 header + minimal MPEG frame)
    _SILENT_MP3 = bytes([
        0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ] * 256)

    async def synthesize(self, request: VoiceGenerationRequest) -> VoiceGenerationResult:
        return VoiceGenerationResult(
            audio_bytes=self._SILENT_MP3,
            audio_format="mp3",
            provider="mock",
            raw_response={"text": request.text[:50], "mock": True},
        )


class MockMusicProvider(MusicGenerationProvider):
    """Returns no audio — equivalent to music_provider=none but explicit."""

    async def generate(self, request: MusicGenerationRequest) -> MusicGenerationResult:
        return MusicGenerationResult(
            audio_bytes=None,
            provider="mock",
            raw_response={"prompt": request.prompt, "mock": True},
        )


class MockEditorComposeProvider(EditorComposeProvider):
    """Skips ffmpeg entirely — writes a 1-byte placeholder file so the service
    can read_bytes/checksum it without needing real video data."""

    _PLACEHOLDER = b"\x00"

    async def compose(self, request: EditorComposeRequest) -> EditorComposeResult:
        out = Path(request.output_path)
        await asyncio.to_thread(lambda: (out.parent.mkdir(parents=True, exist_ok=True), out.write_bytes(self._PLACEHOLDER)))
        return EditorComposeResult(
            output_path=request.output_path,
            duration_seconds=5.0 * len(request.shot_video_urls),
            provider="mock",
            raw_response={"shot_count": len(request.shot_video_urls), "mock": True},
        )
