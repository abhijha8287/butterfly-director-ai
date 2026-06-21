import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.storyboard.agent import MAX_ATTEMPTS, StoryboardAgent
from app.agents.storyboard.schema import StoryboardRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from tests.factories import make_character_state_summary, make_story_bible

_SHOT = {
    "scene": "INT. ALLEY - NIGHT",
    "description": "She screams. Footsteps approach.",
    "camera": "low-angle tracking shot",
    "duration_seconds": 4.5,
    "characters_present": ["Hero"],
}

VALID_RESULT_JSON = json.dumps(
    {
        "shots": [
            {**_SHOT, "shot_number": 1},
            {**_SHOT, "shot_number": 2, "scene": "EXT. ROOFTOP - NIGHT"},
        ]
    }
)

EMPTY_RESULT_JSON = json.dumps({"shots": []})


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> StoryboardRequest:
    return StoryboardRequest(
        story_bible=make_story_bible(),
        branch_name="Universe: Rescue",
        branch_summary="She shouts and is rescued.",
        delta_script="INT. ALLEY - NIGHT\nShe screams. Footsteps approach.",
        characters=[make_character_state_summary(name="Hero")],
    )


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    agent = StoryboardAgent(settings=_settings())

    with patch("app.agents.storyboard.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_RESULT_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert len(result.output.shots) == 2
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    agent = StoryboardAgent(settings=_settings())

    with patch("app.agents.storyboard.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_RESULT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2
    second_call_messages = instance.ainvoke.call_args_list[1].args[0]
    assert "previous response was invalid" in second_call_messages[1].content


@pytest.mark.asyncio
async def test_run_repairs_when_shot_list_is_empty() -> None:
    agent = StoryboardAgent(settings=_settings())

    with patch("app.agents.storyboard.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message(EMPTY_RESULT_JSON), _fake_message(VALID_RESULT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    agent = StoryboardAgent(settings=_settings())

    with patch("app.agents.storyboard.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    agent = StoryboardAgent(settings=_settings(api_key=""))

    with patch("app.agents.storyboard.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()
