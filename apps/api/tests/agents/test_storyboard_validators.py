import pytest

from app.agents.storyboard.schema import StoryboardResult
from app.agents.storyboard.validators import validate_shot_list
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_shot


def test_valid_contiguous_shots_produce_no_warnings() -> None:
    result = StoryboardResult(
        shots=[
            make_shot(shot_number=1, characters_present=["Hero"]),
            make_shot(shot_number=2, characters_present=["Hero"]),
        ]
    )
    warnings = validate_shot_list(result, {"Hero"})
    assert warnings == []


def test_empty_shot_list_raises() -> None:
    result = StoryboardResult(shots=[])
    with pytest.raises(AgentOutputInvalidError, match="at least one shot"):
        validate_shot_list(result, {"Hero"})


def test_duplicate_shot_numbers_raise() -> None:
    result = StoryboardResult(
        shots=[make_shot(shot_number=1), make_shot(shot_number=1, scene="EXT. ROOFTOP - NIGHT")]
    )
    with pytest.raises(AgentOutputInvalidError, match="unique"):
        validate_shot_list(result, {"Hero"})


def test_non_contiguous_shot_numbers_raise() -> None:
    result = StoryboardResult(
        shots=[make_shot(shot_number=1), make_shot(shot_number=3, scene="EXT. ROOFTOP - NIGHT")]
    )
    with pytest.raises(AgentOutputInvalidError, match="contiguous"):
        validate_shot_list(result, {"Hero"})


def test_shot_numbers_not_starting_at_one_raise() -> None:
    result = StoryboardResult(
        shots=[make_shot(shot_number=2), make_shot(shot_number=3, scene="EXT. ROOFTOP - NIGHT")]
    )
    with pytest.raises(AgentOutputInvalidError, match="contiguous"):
        validate_shot_list(result, {"Hero"})


def test_unknown_character_reference_warns() -> None:
    result = StoryboardResult(shots=[make_shot(shot_number=1, characters_present=["Ghost"])])
    warnings = validate_shot_list(result, {"Hero"})
    assert any("unknown characters" in w for w in warnings)


def test_unusually_long_shot_duration_warns() -> None:
    result = StoryboardResult(
        shots=[make_shot(shot_number=1, duration_seconds=120.0, characters_present=["Hero"])]
    )
    warnings = validate_shot_list(result, {"Hero"})
    assert any("unusually long duration" in w for w in warnings)
