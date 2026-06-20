import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.timeline_generator.agent import MAX_ATTEMPTS, TimelineGeneratorAgent
from app.agents.timeline_generator.schema import TimelineGeneratorRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from tests.factories import make_decision_point, make_story_bible

_DRAFT = {
    "name": "Universe: Rescue",
    "summary": "She shouts and is rescued.",
    "initial_divergent_state": "Help has been alerted.",
    "delta_script": "INT. ALLEY - NIGHT\nShe screams. Footsteps approach.",
    "affected_characters": ["Hero"],
    "affected_locations": ["Alley"],
    "emotional_impact": "Relief.",
    "ending_divergence": "A hopeful ending becomes likely.",
    "narrative_impact": "Introduces a rescuer subplot.",
}

VALID_RESULT_JSON = json.dumps(
    {
        "branches": [
            {**_DRAFT, "candidate_label": "Shout"},
            {**_DRAFT, "candidate_label": "Stay silent", "name": "Universe: Isolation"},
        ]
    }
)

SINGLE_DRAFT_JSON = json.dumps({"branches": [{**_DRAFT, "candidate_label": "Shout"}]})


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(dashscope_api_key=api_key, qwen_model="qwen-plus")


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> TimelineGeneratorRequest:
    return TimelineGeneratorRequest(story_bible=make_story_bible(), decision=make_decision_point())


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    agent = TimelineGeneratorAgent(settings=_settings())

    with patch("app.agents.timeline_generator.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_RESULT_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert len(result.output.branches) == 2
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    agent = TimelineGeneratorAgent(settings=_settings())

    with patch("app.agents.timeline_generator.agent.ChatOpenAI") as mock_llm_cls:
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
async def test_run_repairs_when_draft_count_mismatches_candidates() -> None:
    agent = TimelineGeneratorAgent(settings=_settings())

    with patch("app.agents.timeline_generator.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message(SINGLE_DRAFT_JSON), _fake_message(VALID_RESULT_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    agent = TimelineGeneratorAgent(settings=_settings())

    with patch("app.agents.timeline_generator.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    agent = TimelineGeneratorAgent(settings=_settings(api_key=""))

    with patch("app.agents.timeline_generator.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()
