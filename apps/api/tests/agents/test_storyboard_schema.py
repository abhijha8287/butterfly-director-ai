from app.agents.storyboard.schema import StoryboardRequest, StoryboardResult
from tests.factories import make_character_state_summary, make_shot, make_storyboard_request


def test_character_state_summary_defaults_unresolved_state() -> None:
    summary = make_character_state_summary(
        name="Sidekick", knowledge_state="Not yet resolved for this branch."
    )
    assert summary.knowledge_state == "Not yet resolved for this branch."


def test_shot_accepts_full_valid_payload() -> None:
    shot = make_shot(shot_number=1)
    assert shot.shot_number == 1
    assert shot.characters_present == ["Hero"]


def test_shot_defaults_empty_characters_present() -> None:
    shot = make_shot(characters_present=[])
    assert shot.characters_present == []


def test_storyboard_result_accepts_multiple_shots() -> None:
    result = StoryboardResult(
        shots=[make_shot(shot_number=1), make_shot(shot_number=2, scene="EXT. ROOFTOP - NIGHT")]
    )
    assert len(result.shots) == 2


def test_storyboard_result_accepts_empty_shots_at_schema_level() -> None:
    # The schema itself allows an empty list - the hard "at least one shot"
    # rule lives in validators.py (it needs to be retryable, not a permanent
    # construction failure), not as a structural Pydantic constraint here.
    result = StoryboardResult(shots=[])
    assert result.shots == []


def test_storyboard_request_pairs_bible_branch_and_characters() -> None:
    request = StoryboardRequest(
        story_bible=make_storyboard_request().story_bible,
        branch_name="Universe: Rescue",
        characters=[make_character_state_summary()],
    )
    assert request.branch_name == "Universe: Rescue"
    assert request.characters[0].name == "Hero"
