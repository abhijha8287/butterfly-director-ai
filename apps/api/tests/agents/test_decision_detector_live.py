"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_decision_detector_live.py
"""

import os

import pytest

from app.agents.decision_detector.agent import DecisionDetectorAgent
from app.agents.decision_detector.schema import DecisionDetectorRequest
from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_decision_detection_produces_valid_list() -> None:
    story_agent = StoryArchitectAgent()
    story_result = await story_agent.run(
        StoryRequest(
            prompt="A lighthouse keeper finds a message in a bottle from the future.",
            target_runtime_minutes=8,
        )
    )

    decision_agent = DecisionDetectorAgent()
    result = await decision_agent.run(DecisionDetectorRequest(story_bible=story_result.output))

    for decision in result.output.decisions:
        assert 2 <= len(decision.branch_candidates) <= 4
    assert result.attempts >= 1
    assert result.model
