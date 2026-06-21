from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.video_generation.agent import MAX_ATTEMPTS, VideoGenerationAgent
from app.agents.video_generation.schema import VideoGenerationAgentRequest
from app.core.exceptions import ProviderUnavailableError
from app.integrations.providers.base import VideoGenerationResult
from tests.factories import make_shot_render_request


def _result(provider: str = "wan") -> VideoGenerationResult:
    return VideoGenerationResult(
        video_url="https://example.com/shot.mp4",
        duration_seconds=5.0,
        provider=provider,
        raw_response={"output": {"task_status": "SUCCEEDED"}},
    )


@pytest.mark.asyncio
async def test_run_renders_all_shots_successfully() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_result())
    agent = VideoGenerationAgent(provider=provider, provider_name="wan")

    request = VideoGenerationAgentRequest(
        shots=[make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=2)]
    )
    result = await agent.run(request)

    assert len(result.output.rendered) == 2
    assert result.output.failed == []
    assert result.model == "wan"
    assert result.prompt_version == "n/a"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_run_backs_off_prompt_on_retry_then_succeeds() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(
        side_effect=[
            ProviderUnavailableError("rejected"),
            ProviderUnavailableError("rejected again"),
            _result(),
        ]
    )
    agent = VideoGenerationAgent(provider=provider, provider_name="wan")

    shot = make_shot_render_request(shot_number=1, prompt="A" * 100, negative_prompt="blurry")
    result = await agent.run(VideoGenerationAgentRequest(shots=[shot]))

    assert len(result.output.rendered) == 1
    assert result.output.rendered[0].attempts == 3
    assert provider.generate.call_count == 3

    first_call, second_call, third_call = provider.generate.call_args_list
    assert first_call.args[0].negative_prompt == "blurry"
    assert second_call.args[0].negative_prompt is None
    assert len(third_call.args[0].prompt) < len(shot.prompt)


@pytest.mark.asyncio
async def test_run_reports_failure_after_max_attempts() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=ProviderUnavailableError("permanently rejected"))
    agent = VideoGenerationAgent(provider=provider, provider_name="wan")

    shot = make_shot_render_request(shot_number=1)
    result = await agent.run(VideoGenerationAgentRequest(shots=[shot]))

    assert result.output.rendered == []
    assert len(result.output.failed) == 1
    assert result.output.failed[0].attempts == MAX_ATTEMPTS
    assert provider.generate.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_handles_mixed_outcomes_across_shots() -> None:
    async def fake_generate(request: object) -> VideoGenerationResult:
        prompt = request.prompt  # type: ignore[attr-defined]
        if "fail" in prompt:
            raise ProviderUnavailableError("rejected")
        return _result()

    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=fake_generate)
    agent = VideoGenerationAgent(provider=provider, provider_name="wan")

    shots = [
        make_shot_render_request(shot_number=1, prompt="a good shot"),
        make_shot_render_request(shot_number=2, prompt="a shot doomed to fail"),
    ]
    result = await agent.run(VideoGenerationAgentRequest(shots=shots))

    assert [r.shot_number for r in result.output.rendered] == [1]
    assert [f.shot_number for f in result.output.failed] == [2]


@pytest.mark.asyncio
async def test_run_defaults_model_name_from_settings_video_provider() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_result())
    agent = VideoGenerationAgent(provider=provider)

    result = await agent.run(
        VideoGenerationAgentRequest(shots=[make_shot_render_request(shot_number=1)])
    )

    assert result.model == "wan"
