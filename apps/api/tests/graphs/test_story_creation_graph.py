from unittest.mock import AsyncMock, patch

import pytest

from app.agents.story_architect.schema import StoryRequest
from app.graphs.story_creation_graph import build_story_creation_graph
from tests.factories import (
    make_agent_run_result,
    make_character_agent_run_result,
    make_decision_agent_run_result,
)


@pytest.mark.asyncio
async def test_graph_runs_story_character_decision_end_to_end() -> None:
    graph = build_story_creation_graph()
    request = StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)

    with (
        patch("app.graphs.story_creation_graph.StoryArchitectAgent") as mock_story_cls,
        patch("app.graphs.story_creation_graph.CharacterArchitectAgent") as mock_character_cls,
        patch("app.graphs.story_creation_graph.DecisionDetectorAgent") as mock_decision_cls,
    ):
        mock_story_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_character_cls.return_value.run = AsyncMock(return_value=make_character_agent_run_result())
        mock_decision_cls.return_value.run = AsyncMock(return_value=make_decision_agent_run_result())

        final_state = await graph.ainvoke({"request": request})

    assert final_state["story_bible"].title == "T"
    assert final_state["story_model"] == "qwen-plus"
    assert final_state["story_prompt_version"] == "v1"
    assert final_state["story_attempts"] == 1

    assert final_state["character_roster"].characters[0].name == "Hero"
    assert final_state["character_model"] == "qwen-plus"
    assert final_state["character_prompt_version"] == "v1"
    assert final_state["character_attempts"] == 1

    assert final_state["decision_list"].decisions[0].beat_index == 0
    assert final_state["decision_model"] == "qwen-plus"
    assert final_state["decision_prompt_version"] == "v1"
    assert final_state["decision_attempts"] == 1

    # the character and decision nodes must receive the story node's output,
    # not the original request
    character_request = mock_character_cls.return_value.run.call_args.args[0]
    assert character_request.story_bible.title == "T"
    decision_request = mock_decision_cls.return_value.run.call_args.args[0]
    assert decision_request.story_bible.title == "T"
