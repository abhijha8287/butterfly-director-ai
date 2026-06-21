"""Real-ffmpeg integration test for FfmpegEditorComposeProvider - the only
EditorComposeProvider implementation. Unlike the *_live.py tests, this costs
no API credits (ffmpeg runs entirely locally), so it isn't gated behind
RUN_LIVE_API_TESTS - it's gated on ffmpeg/ffprobe actually being on PATH,
since that's not guaranteed outside the Docker image (see Dockerfile).
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.config.settings import Settings
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import EditorAudioTrack, EditorComposeRequest
from app.integrations.providers.ffmpeg_editor_provider import FfmpegEditorComposeProvider

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not found on PATH",
)


def _make_test_video(path: Path, color: str, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x240:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _make_test_audio(path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_compose_concatenates_shots_with_no_audio(tmp_path: Path) -> None:
    shot1 = tmp_path / "shot1.mp4"
    shot2 = tmp_path / "shot2.mp4"
    _make_test_video(shot1, "blue", 1.0)
    _make_test_video(shot2, "red", 1.0)

    output_path = tmp_path / "output" / "final.mp4"
    provider = FfmpegEditorComposeProvider(Settings())
    result = await provider.compose(
        EditorComposeRequest(
            shot_video_urls=[str(shot1), str(shot2)],
            audio_tracks=[],
            output_path=str(output_path),
        )
    )

    assert output_path.exists()
    assert result.provider == "ffmpeg"
    assert result.duration_seconds is not None
    assert 1.5 < result.duration_seconds < 2.5


@pytest.mark.asyncio
async def test_compose_mixes_in_a_delayed_audio_track(tmp_path: Path) -> None:
    shot1 = tmp_path / "shot1.mp4"
    _make_test_video(shot1, "green", 2.0)
    audio1 = tmp_path / "line1.aac"
    _make_test_audio(audio1, 1.0)

    output_path = tmp_path / "output" / "final.mp4"
    provider = FfmpegEditorComposeProvider(Settings())
    result = await provider.compose(
        EditorComposeRequest(
            shot_video_urls=[str(shot1)],
            audio_tracks=[EditorAudioTrack(source=str(audio1), start_offset_ms=500)],
            output_path=str(output_path),
        )
    )

    assert output_path.exists()
    assert result.duration_seconds is not None
    assert 1.5 < result.duration_seconds < 2.5


@pytest.mark.asyncio
async def test_compose_raises_provider_unavailable_when_ffmpeg_fails(tmp_path: Path) -> None:
    missing_shot = tmp_path / "does-not-exist.mp4"
    output_path = tmp_path / "output" / "final.mp4"
    provider = FfmpegEditorComposeProvider(Settings())

    with pytest.raises(ProviderUnavailableError, match="ffmpeg exited"):
        await provider.compose(
            EditorComposeRequest(
                shot_video_urls=[str(missing_shot)],
                audio_tracks=[],
                output_path=str(output_path),
            )
        )


@pytest.mark.asyncio
async def test_probe_duration_returns_none_when_ffprobe_fails(tmp_path: Path) -> None:
    provider = FfmpegEditorComposeProvider(Settings())
    duration = await provider._probe_duration(str(tmp_path / "does-not-exist.mp4"))
    assert duration is None


@pytest.mark.asyncio
async def test_probe_duration_returns_none_when_ffprobe_output_is_unparseable() -> None:
    provider = FfmpegEditorComposeProvider(Settings())
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"not-a-number\n", b""))
    process.returncode = 0

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        duration = await provider._probe_duration("/tmp/whatever.mp4")

    assert duration is None
