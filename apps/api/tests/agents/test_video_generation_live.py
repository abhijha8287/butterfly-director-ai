"""Live DashScope API test. Costs real API credits and can take several
minutes (Wan's task-create + poll loop) - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_video_generation_live.py
"""

import os

import pytest

from app.agents.video_generation.agent import VideoGenerationAgent
from app.agents.video_generation.schema import VideoGenerationAgentRequest
from tests.factories import make_shot_render_request

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_video_generation_renders_one_shot() -> None:
    shot = make_shot_render_request(
        shot_number=1,
        prompt=(
            "A lone figure walks down a rain-slicked neon-lit alley at night, "
            "cinematic wide shot, slow dolly forward."
        ),
        negative_prompt="text, watermark, distorted faces",
        duration_seconds=5,
    )
    request = VideoGenerationAgentRequest(shots=[shot])

    agent = VideoGenerationAgent()
    result = await agent.run(request)

    assert len(result.output.rendered) == 1
    assert result.output.rendered[0].video_url
    assert result.model
