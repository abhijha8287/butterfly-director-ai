"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_story_architect_live.py
"""

import os

import pytest

from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_story_generation_produces_valid_bible() -> None:
    agent = StoryArchitectAgent()
    request = StoryRequest(
        prompt="A lighthouse keeper finds a message in a bottle from the future.",
        target_runtime_minutes=8,
    )

    result = await agent.run(request)

    assert result.output.title
    assert result.output.story_hooks
    assert result.attempts >= 1
    assert result.model
