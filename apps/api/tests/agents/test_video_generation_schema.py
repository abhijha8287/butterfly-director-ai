from app.agents.video_generation.schema import (
    VideoGenerationAgentRequest,
    VideoGenerationAgentResult,
)
from tests.factories import (
    make_shot_render_failure,
    make_shot_render_request,
    make_shot_render_result,
)


def test_shot_render_request_defaults_no_negative_prompt() -> None:
    shot = make_shot_render_request(negative_prompt="")
    assert shot.negative_prompt == ""


def test_video_generation_agent_request_holds_multiple_shots() -> None:
    request = VideoGenerationAgentRequest(
        shots=[make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=2)]
    )
    assert len(request.shots) == 2


def test_shot_render_result_accepts_full_valid_payload() -> None:
    result = make_shot_render_result(shot_number=1)
    assert result.provider == "wan"
    assert result.attempts == 1


def test_shot_render_failure_accepts_full_valid_payload() -> None:
    failure = make_shot_render_failure(shot_number=1)
    assert failure.attempts == 3
    assert failure.error


def test_video_generation_agent_result_accepts_empty_lists_at_schema_level() -> None:
    # The hard "every requested shot appears exactly once" rule lives in
    # validators.py (it needs to be retryable), not as a structural Pydantic
    # constraint here.
    result = VideoGenerationAgentResult(rendered=[], failed=[])
    assert result.rendered == []
    assert result.failed == []


def test_video_generation_agent_result_holds_mixed_outcomes() -> None:
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=1)],
        failed=[make_shot_render_failure(shot_number=2)],
    )
    assert len(result.rendered) == 1
    assert len(result.failed) == 1
