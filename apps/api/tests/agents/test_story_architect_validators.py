import pytest

from app.agents.story_architect.schema import StoryBible, StoryRequest
from app.agents.story_architect.validators import validate_against_request
from app.core.exceptions import AgentOutputInvalidError

_BASE_KWARGS = {
    "title": "T",
    "logline": "L",
    "synopsis": "S",
    "genre": "sci-fi",
    "tone": "moody",
    "setting": "Lab",
    "world_description": "W",
    "timeline_period": "2031",
    "visual_style": "V",
    "cinematic_style": "C",
    "target_audience": "adults",
    "ending_type": "ambiguous",
    "conflict": "X",
    "protagonist_summary": "P",
}


def _bible(**overrides: object) -> StoryBible:
    kwargs = dict(_BASE_KWARGS)
    kwargs.update(overrides)
    kwargs.setdefault("target_runtime", 10)
    return StoryBible(**kwargs)


def test_runtime_within_tolerance_passes() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    bible = _bible(target_runtime=12, themes=["a"], story_hooks=["hook"])
    warnings = validate_against_request(bible, request)
    assert warnings == []


def test_runtime_wildly_off_raises() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    bible = _bible(target_runtime=90)
    with pytest.raises(AgentOutputInvalidError):
        validate_against_request(bible, request)


def test_missing_themes_and_hooks_produce_warnings() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10)
    bible = _bible(target_runtime=10, themes=[], story_hooks=[])
    warnings = validate_against_request(bible, request)
    assert any("themes" in w for w in warnings)
    assert any("story_hooks" in w for w in warnings)


def test_genre_mismatch_produces_warning() -> None:
    request = StoryRequest(prompt="x", target_runtime_minutes=10, genre="comedy")
    bible = _bible(target_runtime=10, genre="horror", themes=["a"], story_hooks=["hook"])
    warnings = validate_against_request(bible, request)
    assert any("genre" in w.lower() for w in warnings)
