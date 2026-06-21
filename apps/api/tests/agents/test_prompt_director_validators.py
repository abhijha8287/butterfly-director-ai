import pytest

from app.agents.prompt_director.schema import PromptDirectorResult
from app.agents.prompt_director.validators import validate_against_shots
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_character_visual_profile, make_shot_context, make_shot_prompt


def test_matching_prompts_produce_no_warnings() -> None:
    shots = [make_shot_context(shot_number=1), make_shot_context(shot_number=2)]
    result = PromptDirectorResult(
        shot_prompts=[make_shot_prompt(shot_number=1), make_shot_prompt(shot_number=2)]
    )
    warnings = validate_against_shots(result, shots)
    assert warnings == []


def test_wrong_prompt_count_raises() -> None:
    shots = [make_shot_context(shot_number=1), make_shot_context(shot_number=2)]
    result = PromptDirectorResult(shot_prompts=[make_shot_prompt(shot_number=1)])
    with pytest.raises(AgentOutputInvalidError):
        validate_against_shots(result, shots)


def test_mismatched_shot_numbers_raise() -> None:
    shots = [make_shot_context(shot_number=1)]
    result = PromptDirectorResult(shot_prompts=[make_shot_prompt(shot_number=2)])
    with pytest.raises(AgentOutputInvalidError):
        validate_against_shots(result, shots)


def test_duplicate_shot_numbers_in_prompts_raise_when_set_still_matches() -> None:
    # The input shots themselves have a duplicate shot_number (not prevented by
    # Storyboard's own validator if it's bypassed/historical data) - this is the
    # one case where the number-set-equality check above can't catch a
    # duplicate, so the explicit duplicate check matters.
    shots = [make_shot_context(shot_number=1), make_shot_context(shot_number=1)]
    result = PromptDirectorResult(
        shot_prompts=[make_shot_prompt(shot_number=1), make_shot_prompt(shot_number=1)]
    )
    with pytest.raises(AgentOutputInvalidError, match="duplicate"):
        validate_against_shots(result, shots)


def test_blank_negative_prompt_warns() -> None:
    shots = [make_shot_context(shot_number=1)]
    result = PromptDirectorResult(
        shot_prompts=[make_shot_prompt(shot_number=1, negative_prompt="  ")]
    )
    warnings = validate_against_shots(result, shots)
    assert any("negative_prompt" in w for w in warnings)


def test_missing_consistency_tokens_with_characters_present_warns() -> None:
    shots = [make_shot_context(shot_number=1, characters=[make_character_visual_profile()])]
    result = PromptDirectorResult(
        shot_prompts=[make_shot_prompt(shot_number=1, consistency_tokens=[])]
    )
    warnings = validate_against_shots(result, shots)
    assert any("consistency_tokens" in w for w in warnings)
