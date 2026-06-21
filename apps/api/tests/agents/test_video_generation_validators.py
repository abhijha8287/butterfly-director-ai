import pytest

from app.agents.video_generation.schema import VideoGenerationAgentResult
from app.agents.video_generation.validators import validate_against_shots
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import (
    make_shot_render_failure,
    make_shot_render_request,
    make_shot_render_result,
)


def test_all_rendered_produce_no_warnings() -> None:
    shots = [make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=2)]
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=1), make_shot_render_result(shot_number=2)],
        failed=[],
    )
    warnings = validate_against_shots(result, shots)
    assert warnings == []


def test_partial_failure_warns_but_does_not_raise() -> None:
    shots = [make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=2)]
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=1)],
        failed=[make_shot_render_failure(shot_number=2)],
    )
    warnings = validate_against_shots(result, shots)
    assert any("1 of 2 shots failed" in w for w in warnings)


def test_wrong_outcome_count_raises() -> None:
    shots = [make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=2)]
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=1)], failed=[]
    )
    with pytest.raises(AgentOutputInvalidError):
        validate_against_shots(result, shots)


def test_mismatched_shot_numbers_raise() -> None:
    shots = [make_shot_render_request(shot_number=1)]
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=2)], failed=[]
    )
    with pytest.raises(AgentOutputInvalidError):
        validate_against_shots(result, shots)


def test_duplicate_shot_numbers_across_rendered_and_failed_raise() -> None:
    shots = [make_shot_render_request(shot_number=1), make_shot_render_request(shot_number=1)]
    result = VideoGenerationAgentResult(
        rendered=[make_shot_render_result(shot_number=1)],
        failed=[make_shot_render_failure(shot_number=1)],
    )
    with pytest.raises(AgentOutputInvalidError, match="duplicate"):
        validate_against_shots(result, shots)


def test_all_failed_warns_with_full_count() -> None:
    shots = [make_shot_render_request(shot_number=1)]
    result = VideoGenerationAgentResult(
        rendered=[], failed=[make_shot_render_failure(shot_number=1)]
    )
    warnings = validate_against_shots(result, shots)
    assert any("1 of 1 shots failed" in w for w in warnings)
