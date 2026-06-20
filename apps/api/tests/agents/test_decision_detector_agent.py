import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.decision_detector.agent import MAX_ATTEMPTS, DecisionDetectorAgent
from app.agents.decision_detector.schema import DecisionDetectorRequest
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError, ProviderUnavailableError
from tests.factories import make_story_bible

VALID_DECISION_JSON = json.dumps(
    {
        "decisions": [
            {
                "beat_index": 0,
                "description": "She must decide whether to shout or stay silent.",
                "source_hook": "hook",
                "branch_candidates": [
                    {
                        "label": "Shout",
                        "description": "She shouts for help.",
                        "tone_shift": "Tension spikes.",
                        "divergence_summary": "This universe ends with rescue.",
                    },
                    {
                        "label": "Stay silent",
                        "description": "She stays silent.",
                        "tone_shift": "Dread deepens.",
                        "divergence_summary": "This universe ends in isolation.",
                    },
                ],
            }
        ]
    }
)

SINGLE_CANDIDATE_JSON = json.dumps(
    {
        "decisions": [
            {
                "beat_index": 0,
                "description": "Only one option exists, which is invalid.",
                "source_hook": None,
                "branch_candidates": [
                    {
                        "label": "Only option",
                        "description": "The only thing that happens.",
                        "tone_shift": "None.",
                        "divergence_summary": "No real fork.",
                    }
                ],
            }
        ]
    }
)


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(
        dashscope_api_key=api_key,
        qwen_model="qwen-plus",
        decision_branch_candidates_min=2,
        decision_branch_candidates_max=4,
    )


def _fake_message(content: str, prompt_tokens: int = 100, completion_tokens: int = 200) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.usage_metadata = {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
    return message


def _request() -> DecisionDetectorRequest:
    return DecisionDetectorRequest(story_bible=make_story_bible(story_hooks=["hook"]))


@pytest.mark.asyncio
async def test_run_succeeds_on_first_attempt() -> None:
    agent = DecisionDetectorAgent(settings=_settings())

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(VALID_DECISION_JSON))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert result.output.decisions[0].beat_index == 0
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 200
    assert instance.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_repairs_malformed_json_then_succeeds() -> None:
    agent = DecisionDetectorAgent(settings=_settings())

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message("not json at all"), _fake_message(VALID_DECISION_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2
    assert instance.ainvoke.call_count == 2
    second_call_messages = instance.ainvoke.call_args_list[1].args[0]
    assert "previous response was invalid" in second_call_messages[1].content


@pytest.mark.asyncio
async def test_run_repairs_when_branch_candidate_count_out_of_bounds() -> None:
    agent = DecisionDetectorAgent(settings=_settings())

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(
            side_effect=[_fake_message(SINGLE_CANDIDATE_JSON), _fake_message(VALID_DECISION_JSON)]
        )

        result = await agent.run(_request())

    assert result.attempts == 2


@pytest.mark.asyncio
async def test_run_fails_after_max_attempts() -> None:
    agent = DecisionDetectorAgent(settings=_settings())

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message("still not json"))

        with pytest.raises(AgentOutputInvalidError):
            await agent.run(_request())

    assert instance.ainvoke.call_count == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_run_raises_when_api_key_missing() -> None:
    agent = DecisionDetectorAgent(settings=_settings(api_key=""))

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        with pytest.raises(ProviderUnavailableError):
            await agent.run(_request())

    mock_llm_cls.assert_not_called()


@pytest.mark.asyncio
async def test_run_accepts_empty_decision_list() -> None:
    agent = DecisionDetectorAgent(settings=_settings())
    empty_json = json.dumps({"decisions": []})

    with patch("app.agents.decision_detector.agent.ChatOpenAI") as mock_llm_cls:
        instance = mock_llm_cls.return_value
        instance.ainvoke = AsyncMock(return_value=_fake_message(empty_json))

        result = await agent.run(_request())

    assert result.attempts == 1
    assert result.output.decisions == []
