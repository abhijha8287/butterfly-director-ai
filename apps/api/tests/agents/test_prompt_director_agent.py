import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.prompt_director.agent import MAX_ATTEMPTS, PromptDirectorAgent
from app.agents.prompt_director.schema import PromptDirectorRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from tests.factories import make_character_visual_profile, make_shot_context, make_story_bible

_PROMPT = {
    "positive_prompt": "Tall, sharp-eyed woman in a worn leather jacket screams in a dark alley.",
    "negative_prompt": "extra limbs, wrong character count, text artifacts",
    "consistency_tokens": ["tall sharp-eyed woman", "worn leather jacket"],
    "style_tokens": ["high-contrast neon noir"],
}

VALID_RESULT_JSON = json.dumps(
    {"shot_prompts": [{**_PROMPT, "shot_number": 1}, {**_PROMPT, "shot_number": 2}]}
)

SINGLE_PROMPT_JSON = json.dumps({"shot_prompts": [{**_PROMPT, "shot_number": 1}]})


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> PromptDirectorRequest:
    return PromptDirectorRequest(
        story_bible=make_story_bible(),
        shots=[
            make_shot_context(shot_number=1, characters=[make_character_visual_profile()]),
            make_shot_context(shot_number=2, scene="EXT. ROOFTOP - NIGHT", characters=[]),
        ],
    )


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    agent = PromptDirectorAgent(settings=_settings())

    with patch("app.agents.prompt_director.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_RESULT_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert len(result.output.shot_prompts) == 2
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    agent = PromptDirectorAgent(settings=_settings())

    with patch("app.agents.prompt_director.agent.ChatOpenAI") as mock_llm_cls:
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
async def test_run_repairs_when_prompt_count_mismatches_shots() -> None:
    agent = PromptDirectorAgent(settings=_settings())

    with patch("app.agents.prompt_director.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message(SINGLE_PROMPT_JSON), _fake_message(VALID_RESULT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    agent = PromptDirectorAgent(settings=_settings())

    with patch("app.agents.prompt_director.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    agent = PromptDirectorAgent(settings=_settings(api_key=""))

    with patch("app.agents.prompt_director.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()
