"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_character_architect_live.py
"""

import os

import pytest

from app.agents.character_architect.agent import CharacterArchitectAgent
from app.agents.character_architect.schema import CharacterRequest
from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_character_generation_produces_valid_roster() -> None:
    story_agent = StoryArchitectAgent()
    story_result = await story_agent.run(
        StoryRequest(
            prompt="A lighthouse keeper finds a message in a bottle from the future.",
            target_runtime_minutes=8,
        )
    )

    character_agent = CharacterArchitectAgent()
    result = await character_agent.run(CharacterRequest(story_bible=story_result.output))

    assert result.output.characters
    assert any(c.role == "protagonist" for c in result.output.characters)
    assert result.attempts >= 1
    assert result.model
