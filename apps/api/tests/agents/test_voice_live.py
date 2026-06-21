"""Live DashScope API test. Costs real API credits and uses a WebSocket
streaming session (CosyVoice has no synchronous REST API) - opt in
explicitly:

    RUN_LIVE_API_TESTS=1 pytest tests/agents/test_voice_live.py
"""

import os

import pytest

from app.agents.voice.agent import VoiceAgent
from tests.factories import make_shot_script, make_voice_character_profile, make_voice_request

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to run live DashScope API tests",
)


@pytest.mark.asyncio
async def test_live_voice_extracts_and_synthesizes_dialogue() -> None:
    request = make_voice_request(
        shots=[
            make_shot_script(
                scene="INT. MIRROR HALL - NIGHT",
                shot_number=1,
                description="Mara raises the hammer and shouts a warning at the shadow.",
                characters_present=["Mara"],
            )
        ],
        characters=[
            make_voice_character_profile(
                name="Mara",
                personality_traits=["defiant", "exhausted"],
                dialogue_style="Short, clipped sentences.",
                voice_descriptor="low warm voice with a rasp",
                emotional_state="furious but controlled",
            )
        ],
    )

    agent = VoiceAgent()
    result = await agent.run(request)

    assert result.attempts >= 1
    assert result.model
    for line in result.output.lines:
        assert line.audio_bytes
        assert line.provider
    for failure in result.output.failed_lines:
        assert failure.error
