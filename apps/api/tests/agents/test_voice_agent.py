import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.voice.agent import MAX_ATTEMPTS, MAX_SYNTHESIS_ATTEMPTS, VoiceAgent
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from app.integrations.providers.base import VoiceGenerationResult
from tests.factories import make_shot_script, make_voice_character_profile, make_voice_request

_LINE = {
    "shot_number": 1,
    "character_name": "Hero",
    "line_text": "Stay back. I know this place better than you think.",
    "delivery_note": "low, urgent whisper",
}

VALID_SCRIPT_JSON = json.dumps({"lines": [_LINE]})
EMPTY_SCRIPT_JSON = json.dumps({"lines": []})
UNKNOWN_SHOT_SCRIPT_JSON = json.dumps({"lines": [{**_LINE, "shot_number": 99}]})


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> object:
    return make_voice_request(
        shots=[make_shot_script(shot_number=1, characters_present=["Hero"])],
        characters=[make_voice_character_profile(name="Hero")],
    )


def _voice_result(provider: str = "dashscope") -> VoiceGenerationResult:
    return VoiceGenerationResult(audio_bytes=b"fake-audio", audio_format="mp3", provider=provider)


@pytest.mark.asyncio
async def test_run_extracts_and_synthesizes_on_first_attempt() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=_voice_result())
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert len(result.output.lines) == 1
    assert result.output.failed_lines == []
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1
    assert provider.synthesize.call_count == 1


@pytest.mark.asyncio
async def test_run_is_valid_with_zero_extracted_lines() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=_voice_result())
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(EMPTY_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.output.lines == []
    assert result.output.failed_lines == []
    provider.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=_voice_result())
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_SCRIPT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_run_repairs_when_line_references_unknown_shot() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(return_value=_voice_result())
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
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
    provider.synthesize = AsyncMock(return_value=_voice_result())
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS
    provider.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    provider = MagicMock()
    agent = VoiceAgent(settings=_settings(api_key=""), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()


@pytest.mark.asyncio
async def test_run_backs_off_text_on_retry_then_succeeds() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(
        side_effect=[ProviderUnavailableError("rejected"), _voice_result()]
    )
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert len(result.output.lines) == 1
    assert result.output.lines[0].attempts == 2
    first_call, second_call = provider.synthesize.call_args_list
    assert len(second_call.args[0].text) < len(first_call.args[0].text)


@pytest.mark.asyncio
async def test_run_reports_line_failure_after_max_synthesis_attempts() -> None:
    provider = MagicMock()
    provider.synthesize = AsyncMock(side_effect=ProviderUnavailableError("permanently rejected"))
    agent = VoiceAgent(settings=_settings(), provider=provider)

    with patch("app.agents.voice.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_SCRIPT_JSON))

        result = await agent.run(_request())

    assert result.output.lines == []
    assert len(result.output.failed_lines) == 1
    assert result.output.failed_lines[0].attempts == MAX_SYNTHESIS_ATTEMPTS
    assert provider.synthesize.call_count == MAX_SYNTHESIS_ATTEMPTS
