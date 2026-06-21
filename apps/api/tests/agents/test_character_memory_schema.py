from app.agents.character_memory.schema import CharacterMemoryRequest, CharacterMemoryResult
from tests.factories import (
    make_branch_context,
    make_character_memory_profile,
    make_character_state_diff,
)


def test_character_memory_profile_accepts_full_valid_payload() -> None:
    profile = make_character_memory_profile(name="Hero")
    assert profile.name == "Hero"
    assert profile.personality_traits == ["determined"]


def test_branch_context_allows_all_optional_fields_unset() -> None:
    context = make_branch_context(
        summary=None,
        initial_divergent_state=None,
        delta_script=None,
        emotional_impact=None,
        ending_divergence=None,
        narrative_impact=None,
        affected_characters=[],
    )
    assert context.summary is None
    assert context.affected_characters == []


def test_character_state_diff_defaults_drift_warning_to_none() -> None:
    state = make_character_state_diff(drift_severity="none", drift_warning=None)
    assert state.drift_warning is None


def test_character_state_diff_accepts_drift_warning() -> None:
    state = make_character_state_diff(
        drift_severity="major", drift_warning="Contradicts established cowardice."
    )
    assert state.drift_severity == "major"
    assert state.drift_warning == "Contradicts established cowardice."


def test_character_memory_result_accepts_multiple_states() -> None:
    result = CharacterMemoryResult(
        character_states=[
            make_character_state_diff(character_name="Hero"),
            make_character_state_diff(character_name="Villain"),
        ]
    )
    assert len(result.character_states) == 2


def test_character_memory_result_accepts_empty_states() -> None:
    result = CharacterMemoryResult(character_states=[])
    assert result.character_states == []


def test_character_memory_request_pairs_branch_and_characters() -> None:
    request = CharacterMemoryRequest(
        branch=make_branch_context(), characters=[make_character_memory_profile()]
    )
    assert request.branch.name == "Universe: Rescue"
    assert request.characters[0].name == "Hero"
