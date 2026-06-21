"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_storyboard_live.py
"""

import os

import pytest

from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.schema import StoryboardRequest
from tests.factories import make_character_state_summary, make_story_bible

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_storyboard_produces_a_contiguous_shot_list() -> None:
    characters = [
        make_character_state_summary(
            name="Mara",
            role="protagonist",
            physical_description="Lean, scarred hands, watchful eyes.",
            emotional_state="Resolved but afraid.",
        ),
    ]
    request = StoryboardRequest(
        story_bible=make_story_bible(
            visual_style="High-contrast neon noir.",
            cinematic_style="Handheld, claustrophobic framing.",
        ),
        branch_name="Universe: The Mirror Cracks",
        branch_summary="Mara shatters the mirror instead of stepping through it.",
        delta_script="INT. MIRROR HALL - NIGHT\nMara raises the hammer. The glass screams back.",
        characters=characters,
    )

    agent = StoryboardAgent()
    result = await agent.run(request)

    assert len(result.output.shots) >= 1
    shot_numbers = [s.shot_number for s in result.output.shots]
    assert shot_numbers == list(range(1, len(shot_numbers) + 1))
    assert result.attempts >= 1
    assert result.model
