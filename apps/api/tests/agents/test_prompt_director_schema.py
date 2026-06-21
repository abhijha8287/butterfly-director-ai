from app.agents.prompt_director.schema import PromptDirectorRequest, PromptDirectorResult
from tests.factories import (
    make_character_visual_profile,
    make_shot_context,
    make_shot_prompt,
    make_story_bible,
)


def test_character_visual_profile_accepts_full_valid_payload() -> None:
    profile = make_character_visual_profile(name="Hero")
    assert profile.name == "Hero"
    assert profile.emotional_state == "Relieved but shaken."


def test_character_visual_profile_defaults_unchanged_state() -> None:
    profile = make_character_visual_profile(emotional_state="unchanged", physical_state="unchanged")
    assert profile.emotional_state == "unchanged"
    assert profile.physical_state == "unchanged"


def test_shot_context_defaults_empty_characters() -> None:
    context = make_shot_context(characters=[])
    assert context.characters == []


def test_shot_prompt_accepts_full_valid_payload() -> None:
    prompt = make_shot_prompt(shot_number=1)
    assert prompt.shot_number == 1
    assert prompt.consistency_tokens


def test_prompt_director_result_accepts_multiple_prompts() -> None:
    result = PromptDirectorResult(
        shot_prompts=[make_shot_prompt(shot_number=1), make_shot_prompt(shot_number=2)]
    )
    assert len(result.shot_prompts) == 2


def test_prompt_director_result_accepts_empty_prompts_at_schema_level() -> None:
    # The hard "exactly one per shot" rule lives in validators.py (it needs to
    # be retryable), not as a structural Pydantic constraint here.
    result = PromptDirectorResult(shot_prompts=[])
    assert result.shot_prompts == []


def test_prompt_director_request_pairs_bible_and_shots() -> None:
    request = PromptDirectorRequest(story_bible=make_story_bible(), shots=[make_shot_context()])
    assert request.shots[0].shot_number == 1
