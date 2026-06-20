import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.character_architect.agent import MAX_ATTEMPTS, CharacterArchitectAgent
from app.agents.character_architect.schema import CharacterRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from tests.factories import make_story_bible

VALID_ROSTER_JSON = json.dumps(
    {
        "characters": [
            {
                "name": "Hero",
                "role": "protagonist",
                "age_range": "30s",
                "physical_description": "Tall, sharp-eyed.",
                "wardrobe_style": "Worn leather jacket.",
                "personality_traits": ["determined"],
                "backstory": "Grew up on the docks.",
                "motivation": "To find the truth.",
                "internal_conflict": "Fear of repeating the past.",
                "external_conflict": "Hunted by old allies.",
                "character_arc": "Learns to trust again.",
                "relationships": [],
                "defining_strengths": ["resourceful"],
                "defining_flaws": ["stubborn"],
                "dialogue_style": "Short, clipped sentences.",
                "voice_profile": {
                    "descriptor": "low warm voice",
                    "tone": "calm",
                    "pace": "measured",
                    "pitch": "low",
                },
                "secret": None,
            }
        ]
    }
)


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> CharacterRequest:
    return CharacterRequest(story_bible=make_story_bible())


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    agent = CharacterArchitectAgent(settings=_settings())

    with patch("app.agents.character_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_ROSTER_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert result.output.characters[0].name == "Hero"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    agent = CharacterArchitectAgent(settings=_settings())

    with patch("app.agents.character_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_ROSTER_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2
    second_call_messages = instance.ainvoke.call_args_list[1].args[0]
    assert "previous response was invalid" in second_call_messages[1].content


@pytest.mark.asyncio
async def test_run_repairs_when_protagonist_count_is_wrong() -> None:
    agent = CharacterArchitectAgent(settings=_settings())

    zero_protagonist_json = VALID_ROSTER_JSON.replace('"role": "protagonist"', '"role": "supporting"')

    with patch("app.agents.character_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message(zero_protagonist_json), _fake_message(VALID_ROSTER_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    agent = CharacterArchitectAgent(settings=_settings())

    with patch("app.agents.character_architect.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    agent = CharacterArchitectAgent(settings=_settings(api_key=""))

    with patch("app.agents.character_architect.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()
