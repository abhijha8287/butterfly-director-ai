from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.editor.agent import MAX_ATTEMPTS, EditorAgent
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import EditorComposeRequest, EditorComposeResult
from app.integrations.providers.ffmpeg_editor_provider import FfmpegEditorComposeProvider
from tests.factories import make_editor_audio_input, make_editor_request, make_editor_shot_input


def _compose_result(path: str = "/app/media/editor/out.mp4") -> EditorComposeResult:
    return EditorComposeResult(output_path=path, duration_seconds=12.5, provider="ffmpeg")


@pytest.mark.asyncio
async def test_run_composes_on_first_attempt() -> None:
    provider = MagicMock()
    provider.compose = AsyncMock(return_value=_compose_result())
    agent = EditorAgent(provider=provider)

    request = make_editor_request(
        shots=[make_editor_shot_input(shot_number=1), make_editor_shot_input(shot_number=2)],
        audio_tracks=[make_editor_audio_input()],
    )
    result = await agent.run(request)

    assert result.attempts == 1
    assert result.model == "ffmpeg"
    assert result.prompt_version == "n/a"
    assert result.output.output_path == "/app/media/editor/out.mp4"
    assert result.output.duration_seconds == 12.5
    assert result.output.shot_count == 2
    assert result.output.audio_track_count == 1
    provider.compose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_passes_through_shot_urls_in_order() -> None:
    provider = MagicMock()
    provider.compose = AsyncMock(return_value=_compose_result())
    agent = EditorAgent(provider=provider)

    request = make_editor_request(
        shots=[
            make_editor_shot_input(shot_number=1, video_url="https://example.com/s1.mp4"),
            make_editor_shot_input(shot_number=2, video_url="https://example.com/s2.mp4"),
        ]
    )
    await agent.run(request)

    sent_request = provider.compose.call_args.args[0]
    assert sent_request.shot_video_urls == [
        "https://example.com/s1.mp4",
        "https://example.com/s2.mp4",
    ]


@pytest.mark.asyncio
async def test_run_converts_start_offset_seconds_to_milliseconds() -> None:
    provider = MagicMock()
    provider.compose = AsyncMock(return_value=_compose_result())
    agent = EditorAgent(provider=provider)

    request = make_editor_request(
        audio_tracks=[make_editor_audio_input(start_offset_seconds=2.5, kind="music")]
    )
    await agent.run(request)

    sent_request = provider.compose.call_args.args[0]
    assert sent_request.audio_tracks[0].start_offset_ms == 2500


@pytest.mark.asyncio
async def test_run_retries_then_succeeds() -> None:
    provider = MagicMock()
    provider.compose = AsyncMock(
        side_effect=[ProviderUnavailableError("ffmpeg transient failure"), _compose_result()]
    )
    agent = EditorAgent(provider=provider)

    result = await agent.run(make_editor_request())

    assert result.attempts == 2
    assert provider.compose.call_count == 2


@pytest.mark.asyncio
async def test_run_raises_after_max_attempts() -> None:
    provider = MagicMock()
    provider.compose = AsyncMock(side_effect=ProviderUnavailableError("ffmpeg permanently down"))
    agent = EditorAgent(provider=provider)

    with pytest.raises(ProviderUnavailableError):
        await agent.run(make_editor_request())

    assert provider.compose.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_ffmpeg_provider_rejects_empty_shot_list_without_invoking_ffmpeg() -> None:
    provider = FfmpegEditorComposeProvider()
    with pytest.raises(ProviderUnavailableError):
        await provider.compose(
            EditorComposeRequest(shot_video_urls=[], audio_tracks=[], output_path="/tmp/out.mp4")
        )
