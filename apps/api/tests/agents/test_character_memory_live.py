"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_character_memory_live.py
"""

import os

import pytest

from app.agents.character_memory.agent import CharacterMemoryAgent
from app.agents.character_memory.schema import CharacterMemoryRequest
from tests.factories import make_branch_context, make_character_memory_profile

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_character_memory_produces_one_state_per_character() -> None:
    characters = [
        make_character_memory_profile(name="Mara", role="protagonist"),
        make_character_memory_profile(
            name="倒影 (The Reflection)",
            role="antagonist",
            motivation="To replace Mara entirely.",
            internal_conflict="Resents being only a copy.",
            external_conflict="Cannot exist outside the mirrored world.",
        ),
    ]
    branch = make_branch_context(
        name="Universe: The Mirror Cracks",
        summary="Mara shatters the mirror instead of stepping through it.",
        initial_divergent_state="The reflection is trapped, fading.",
        affected_characters=["Mara", "倒影 (The Reflection)"],
    )

    agent = CharacterMemoryAgent()
    result = await agent.run(CharacterMemoryRequest(branch=branch, characters=characters))

    assert len(result.output.character_states) == len(characters)
    assert result.attempts >= 1
    assert result.model
