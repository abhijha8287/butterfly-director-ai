"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_timeline_generator_live.py
"""

import os

import pytest

from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest
from app.agents.timeline_generator.agent import TimelineGeneratorAgent
from app.agents.timeline_generator.schema import TimelineGeneratorRequest
from tests.factories import make_decision_point

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_timeline_generation_produces_one_draft_per_candidate() -> None:
    story_agent = StoryArchitectAgent()
    story_result = await story_agent.run(
        StoryRequest(
            prompt="A lighthouse keeper finds a message in a bottle from the future.",
            target_runtime_minutes=8,
        )
    )

    decision = make_decision_point(
        description="The keeper must decide whether to follow the message's instructions.",
        source_hook=None,
    )

    timeline_agent = TimelineGeneratorAgent()
    result = await timeline_agent.run(
        TimelineGeneratorRequest(story_bible=story_result.output, decision=decision)
    )

    assert len(result.output.branches) == len(decision.branch_candidates)
    assert result.attempts >= 1
    assert result.model
