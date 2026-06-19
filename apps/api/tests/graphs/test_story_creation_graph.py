from unittest.mock import AsyncMock, patch

import pytest

from app.agents.story_architect.schema import StoryRequest
from app.graphs.story_creation_graph import build_story_creation_graph
from tests.factories import make_agent_run_result


@pytest.mark.asyncio
async def test_graph_runs_story_architect_node_end_to_end() -> None:
    graph = build_story_creation_graph()
    request = StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)

    with patch("app.graphs.story_creation_graph.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())

        final_state = await graph.ainvoke({"request": request})

    assert final_state["story_bible"].title == "T"
    assert final_state["model"] == "qwen-plus"
    assert final_state["prompt_version"] == "v1"
    assert final_state["attempts"] == 1
