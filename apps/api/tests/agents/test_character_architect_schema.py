import pytest
from pydantic import ValidationError

from app.agents.character_architect.schema import CharacterRoster
from tests.factories import make_character_profile, make_character_roster, make_voice_profile


def test_voice_profile_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        make_voice_profile(descriptor=None)  # type: ignore[arg-type]


def test_character_profile_accepts_full_valid_payload() -> None:
    profile = make_character_profile(name="Lira", role="protagonist")
    assert profile.name == "Lira"
    assert profile.secret is None
    assert profile.relationships == []


def test_character_profile_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        make_character_profile(role="sidekick")


def test_roster_accepts_one_protagonist() -> None:
    roster = make_character_roster()
    assert len(roster.characters) == 1
    assert roster.characters[0].role == "protagonist"


def test_roster_accepts_protagonist_antagonist_and_supporting() -> None:
    roster = make_character_roster(
        characters=[
            make_character_profile(name="Hero", role="protagonist"),
            make_character_profile(name="Villain", role="antagonist"),
            make_character_profile(name="Sidekick", role="supporting"),
        ]
    )
    assert len(roster.characters) == 3


def test_roster_rejects_zero_protagonists() -> None:
    with pytest.raises(ValidationError, match="protagonist"):
        CharacterRoster(characters=[make_character_profile(name="Villain", role="antagonist")])


def test_roster_rejects_multiple_protagonists() -> None:
    with pytest.raises(ValidationError, match="protagonist"):
        make_character_roster(
            characters=[
                make_character_profile(name="Hero", role="protagonist"),
                make_character_profile(name="Hero Two", role="protagonist"),
            ]
        )


def test_roster_rejects_duplicate_names_case_insensitive() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        make_character_roster(
            characters=[
                make_character_profile(name="Hero", role="protagonist"),
                make_character_profile(name="hero", role="antagonist"),
            ]
        )
