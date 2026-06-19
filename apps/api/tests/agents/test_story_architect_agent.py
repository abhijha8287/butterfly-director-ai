import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.story_architect.agent import MAX_ATTEMPTS, StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError

VALID_JSON = json.dumps(
    {
        "title": "T",
        "logline": "L",
        "synopsis": "S",
        "genre": "sci-fi",
        "tone": "moody",
        "setting": "Lab",
        "world_description": "W",
        "timeline_period": "2031",
        "visual_style": "V",
        "cinematic_style": "C",
        "target_runtime": 10,
        "target_audience": "adults",
        "ending_type": "ambiguous",
        "conflict": "X",
        "protagonist_summary": "P",
        "themes": ["a"],
        "story_hooks": ["hook"],
    }
)


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    agent = StoryArchitectAgent(settings=_settings())

    with patch("app.agents.story_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_JSON))

        result = await agent.run(request)

    assert result.attempts == 1
    assert result.output.title == "T"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    agent = StoryArchitectAgent(settings=_settings())

    with patch("app.agents.story_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_JSON)]
        )

        result = await agent.run(request)

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2
    # the repair turn must include the previous error so the model can fix it
    second_call_messages = instance.ainvoke.call_args_list[1].args[0]
    assert "previous response was invalid" in second_call_messages[1].content


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    agent = StoryArchitectAgent(settings=_settings())

    with patch("app.agents.story_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(request)

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_runtime_violates_request() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    agent = StoryArchitectAgent(settings=_settings())

    bad_runtime_json = VALID_JSON.replace('"target_runtime": 10', '"target_runtime": 90')

    with patch("app.agents.story_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(bad_runtime_json))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(request)

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    agent = StoryArchitectAgent(settings=_settings(api_key=""))

    with patch("app.agents.story_architect.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(request)

    mock_llm_cls.assert_not_called()
