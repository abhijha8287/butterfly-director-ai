from app.agents.character_architect.validators import validate_against_story_bible
from tests.factories import make_character_profile, make_character_roster, make_story_bible


def test_matching_roster_produces_no_warnings() -> None:
    bible = make_story_bible(antagonist_summary=None, supporting_characters_summary=[])
    roster = make_character_roster()
    warnings = validate_against_story_bible(roster, bible)
    assert warnings == []


def test_missing_antagonist_when_expected_warns() -> None:
    bible = make_story_bible(antagonist_summary="A ruthless rival.")
    roster = make_character_roster()
    warnings = validate_against_story_bible(roster, bible)
    assert any("antagonist" in w for w in warnings)


def test_supporting_character_count_mismatch_warns() -> None:
    bible = make_story_bible(
        supporting_characters_summary=["Friend one", "Friend two", "Friend three"]
    )
    roster = make_character_roster()
    warnings = validate_against_story_bible(roster, bible)
    assert any("supporting" in w for w in warnings)


def test_character_with_no_relationships_in_multi_character_roster_warns() -> None:
    bible = make_story_bible(antagonist_summary=None, supporting_characters_summary=[])
    roster = make_character_roster(
        characters=[
            make_character_profile(name="Hero", role="protagonist", relationships=[]),
            make_character_profile(
                name="Villain", role="antagonist", relationships=["Hero is my rival."]
            ),
        ]
    )
    warnings = validate_against_story_bible(roster, bible)
    assert any("Hero" in w for w in warnings)
