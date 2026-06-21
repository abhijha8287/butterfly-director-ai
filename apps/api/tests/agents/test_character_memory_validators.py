import pytest

from app.agents.character_memory.schema import CharacterMemoryResult
from app.agents.character_memory.validators import validate_against_roster
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_character_memory_profile, make_character_state_diff


def test_matching_states_produce_no_warnings() -> None:
    characters = [make_character_memory_profile(name="Hero")]
    result = CharacterMemoryResult(character_states=[make_character_state_diff(character_name="Hero")])
    warnings = validate_against_roster(result, characters)
    assert warnings == []


def test_wrong_state_count_raises() -> None:
    characters = [
        make_character_memory_profile(name="Hero"),
        make_character_memory_profile(name="Villain"),
    ]
    result = CharacterMemoryResult(character_states=[make_character_state_diff(character_name="Hero")])
    with pytest.raises(AgentOutputInvalidError):
        validate_against_roster(result, characters)


def test_mismatched_names_raise() -> None:
    characters = [make_character_memory_profile(name="Hero")]
    result = CharacterMemoryResult(
        character_states=[make_character_state_diff(character_name="Someone Else")]
    )
    with pytest.raises(AgentOutputInvalidError):
        validate_against_roster(result, characters)


def test_duplicate_names_in_states_raise_when_name_set_still_matches() -> None:
    # The input roster itself has a duplicate character name (not prevented by
    # the service, which builds it from raw Character rows) - this is the one
    # case where the name-set-equality check above can't catch a duplicate, so
    # the explicit duplicate check matters.
    characters = [
        make_character_memory_profile(name="Hero"),
        make_character_memory_profile(name="Hero"),
    ]
    result = CharacterMemoryResult(
        character_states=[
            make_character_state_diff(character_name="Hero"),
            make_character_state_diff(character_name="Hero"),
        ]
    )
    with pytest.raises(AgentOutputInvalidError, match="duplicate"):
        validate_against_roster(result, characters)


def test_drift_severity_without_warning_raises() -> None:
    characters = [make_character_memory_profile(name="Hero")]
    result = CharacterMemoryResult(
        character_states=[
            make_character_state_diff(character_name="Hero", drift_severity="major", drift_warning=None)
        ]
    )
    with pytest.raises(AgentOutputInvalidError, match="drift_severity"):
        validate_against_roster(result, characters)


def test_drift_severity_none_with_warning_set_warns() -> None:
    characters = [make_character_memory_profile(name="Hero")]
    result = CharacterMemoryResult(
        character_states=[
            make_character_state_diff(
                character_name="Hero", drift_severity="none", drift_warning="Stray warning."
            )
        ]
    )
    warnings = validate_against_roster(result, characters)
    assert any("drift_warning" in w for w in warnings)


def test_thin_state_diff_warns() -> None:
    characters = [make_character_memory_profile(name="Hero")]
    result = CharacterMemoryResult(
        character_states=[
            make_character_state_diff(character_name="Hero", knowledge_state="  ", emotional_state="  ")
        ]
    )
    warnings = validate_against_roster(result, characters)
    assert any("thin state_diff" in w for w in warnings)
