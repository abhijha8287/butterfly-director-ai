"""Live DashScope API test. Costs real API credits - opt in explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_music_live.py

No real DashScope music provider exists in this build (MUSIC_PROVIDER defaults
to "none"), so this only exercises the LLM extraction phase against the real
Qwen API - there is no synthesis phase to verify live.
"""

import os

import pytest

from app.agents.music.agent import MusicAgent
from app.config.settings import Settings
from tests.factories import make_music_request, make_music_shot_script

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_music_extracts_score_for_branch() -> None:
    request = make_music_request(
        branch_summary="Mara escapes the mirror hall and is finally safe.",
        shots=[
            make_music_shot_script(
                scene="INT. MIRROR HALL - NIGHT",
                shot_number=1,
                description="Mara raises the hammer and shouts a warning at the shadow.",
                duration_seconds=4.5,
            ),
            make_music_shot_script(
                scene="EXT. ROOFTOP - DAWN",
                shot_number=2,
                description="She climbs over the ledge into the morning light, breathing easy.",
                duration_seconds=5.0,
            ),
        ],
    )

    agent = MusicAgent(settings=Settings(music_provider="none"))
    result = await agent.run(request)

    assert result.attempts >= 1
    assert result.model
    for cue in result.output.cues:
        assert cue.generation_prompt
        assert cue.provider is None
        assert cue.attempts == 0
    for failure in result.output.failed_cues:
        assert failure.error
