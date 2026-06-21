"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_prompt_director_live.py
"""

import os

import pytest

from app.agents.prompt_director.agent import PromptDirectorAgent
from app.agents.prompt_director.schema import PromptDirectorRequest
from tests.factories import make_character_visual_profile, make_shot_context, make_story_bible

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_prompt_director_produces_one_prompt_per_shot() -> None:
    shots = [
        make_shot_context(
            scene="INT. MIRROR HALL - NIGHT",
            shot_number=1,
            description="Mara raises the hammer. The glass screams back.",
            camera="low-angle tracking shot",
            duration_seconds=4.0,
            characters=[
                make_character_visual_profile(
                    name="Mara",
                    physical_description="Lean, scarred hands, watchful eyes.",
                    wardrobe_style="Worn field jacket.",
                    emotional_state="Resolved but afraid.",
                )
            ],
        ),
        make_shot_context(
            scene="INT. MIRROR HALL - NIGHT",
            shot_number=2,
            description="The mirror shatters into a thousand falling shards.",
            camera="high-angle wide shot",
            duration_seconds=3.0,
            characters=[],
        ),
    ]
    request = PromptDirectorRequest(
        story_bible=make_story_bible(
            visual_style="High-contrast neon noir.",
            cinematic_style="Handheld, claustrophobic framing.",
        ),
        shots=shots,
    )

    agent = PromptDirectorAgent()
    result = await agent.run(request)

    assert len(result.output.shot_prompts) == len(shots)
    shot_numbers = {p.shot_number for p in result.output.shot_prompts}
    assert shot_numbers == {1, 2}
    assert result.attempts >= 1
    assert result.model
