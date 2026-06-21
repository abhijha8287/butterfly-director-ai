import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.music.agent import MAX_ATTEMPTS, MAX_SYNTHESIS_ATTEMPTS, MusicAgent
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from app.integrations.providers.base import MusicGenerationResult
from tests.factories import make_music_request, make_music_shot_script

_CUE = {
    "start_shot_number": 1,
    "end_shot_number": 1,
    "mood": "tense, rising dread",
    "tempo_bpm": 110,
    "generation_prompt": "Dark ambient drone, low strings, slow building tension, 110bpm.",
}

VALID_SCRIPT_JSON = json.dumps({"cues": [_CUE]})
EMPTY_SCRIPT_JSON = json.dumps({"cues": []})
UNKNOWN_SHOT_SCRIPT_JSON = json.dumps({"cues": [{**_CUE, "start_shot_number": 99}]})


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> object:
    return make_music_request(shots=[make_music_shot_script(shot_number=1)])


def _music_result(provider: str = "happyhorse") -> MusicGenerationResult:
    return MusicGenerationResult(audio_url="https://example.com/cue.mp3", provider=provider)


@pytest.mark.asyncio
async def test_run_extracts_and_synthesizes_on_first_attempt() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_music_result())
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert len(result.output.cues) == 1
    assert result.output.cues[0].provider == "happyhorse"
    assert result.output.cues[0].attempts == 1
    assert result.output.failed_cues == []
    assert provider.generate.call_count == 1


@pytest.mark.asyncio
async def test_run_is_valid_with_zero_extracted_cues() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_music_result())
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(EMPTY_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.output.cues == []
    assert result.output.failed_cues == []
    provider.generate.assert_not_called()


@pytest.mark.asyncio
async def test_run_skips_synthesis_when_no_provider_configured() -> None:
    agent = MusicAgent(settings=_settings(), provider=None)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert len(result.output.cues) == 1
    cue = result.output.cues[0]
    assert cue.provider is None
    assert cue.attempts == 0
    assert cue.audio_url is None
    assert cue.audio_bytes is None
    assert result.output.failed_cues == []


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_music_result())
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_SCRIPT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_run_repairs_when_cue_references_unknown_shot() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_music_result())
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[
                _fake_message(UNKNOWN_SHOT_SCRIPT_JSON),
                _fake_message(VALID_SCRIPT_JSON),
            ]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_extraction_after_max_attempts() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=_music_result())
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS
    provider.generate.assert_not_called()


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    provider = MagicMock()
    agent = MusicAgent(settings=_settings(api_key=""), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()


@pytest.mark.asyncio
async def test_run_backs_off_prompt_on_retry_then_succeeds() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(
        side_effect=[ProviderUnavailableError("rejected"), _music_result()]
    )
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert len(result.output.cues) == 1
    assert result.output.cues[0].attempts == 2
    first_call, second_call = provider.generate.call_args_list
    assert len(second_call.args[0].prompt) < len(first_call.args[0].prompt)


@pytest.mark.asyncio
async def test_run_reports_cue_failure_after_max_synthesis_attempts() -> None:
    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=ProviderUnavailableError("permanently rejected"))
    agent = MusicAgent(settings=_settings(), provider=provider)

    with patch("app.agents.music.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.output.cues == []
    assert len(result.output.failed_cues) == 1
    assert result.output.failed_cues[0].attempts == MAX_SYNTHESIS_ATTEMPTS
    assert provider.generate.call_count == MAX_SYNTHESIS_ATTEMPTS
