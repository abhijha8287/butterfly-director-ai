import pytest
from pydantic import ValidationError

from app.agents.story_architect.schema import StoryBible, StoryRequest

_VALID_BIBLE_KWARGS = {
    "title": "The Erasure Equation",
    "logline": "A scientist loses a memory every time she time travels.",
    "synopsis": "A long synopsis describing the plot in detail across paragraphs.",
    "genre": "sci-fi",
    "tone": "moody",
    "setting": "A basement lab",
    "world_description": "Near future, quiet technological exhaustion.",
    "timeline_period": "2031",
    "visual_style": "Desaturated, grainy",
    "cinematic_style": "Handheld, intimate",
    "target_runtime": 12,
    "target_audience": "adults",
    "ending_type": "ambiguous",
    "conflict": "Memory versus truth",
    "protagonist_summary": "Dr. Lena Voss, a grieving chronophysicist.",
}


def test_story_request_accepts_minimal_valid_input() -> None:
    request = StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)
    assert request.genre is None
    assert request.style is None


@pytest.mark.parametrize("runtime", [0, -5, 181, 1000])
def test_story_request_rejects_out_of_range_runtime(runtime: int) -> None:
    with pytest.raises(ValidationError):
        StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=runtime)


def test_story_request_rejects_empty_prompt() -> None:
    with pytest.raises(ValidationError):
        StoryRequest(prompt="", target_runtime_minutes=10)


def test_story_bible_accepts_full_valid_payload() -> None:
    bible = StoryBible(**_VALID_BIBLE_KWARGS, themes=["grief"], story_hooks=["she could shout or stay silent"])
    assert bible.title == "The Erasure Equation"
    assert bible.themes == ["grief"]
    # Optional list fields default to empty rather than requiring the caller to set them.
    assert bible.world_constraints == []
    assert bible.antagonist_summary is None


def test_story_bible_rejects_missing_required_field() -> None:
    kwargs = dict(_VALID_BIBLE_KWARGS)
    del kwargs["title"]
    with pytest.raises(ValidationError):
        StoryBible(**kwargs)


def test_story_bible_rejects_blank_core_field() -> None:
    kwargs = dict(_VALID_BIBLE_KWARGS)
    kwargs["title"] = "   "
    with pytest.raises(ValidationError, match="title"):
        StoryBible(**kwargs)
