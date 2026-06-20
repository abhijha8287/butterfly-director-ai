from __future__ import annotations

from app.agents.character_architect.schema import CharacterRoster
from app.agents.story_architect.schema import StoryBible

_SUPPORTING_COUNT_TOLERANCE = 1


def validate_against_story_bible(roster: CharacterRoster, bible: StoryBible) -> list[str]:
    """Semantic checks beyond plain Pydantic field types (those guarantee shape;
    this guarantees the roster actually answers the StoryBible it was built from).
    Returns non-fatal warnings; the schema's own model_validator already raises
    on the two hard contract violations (duplicate names, not-exactly-one
    protagonist), so nothing here needs to raise.
    """
    warnings: list[str] = []

    has_antagonist = any(c.role == "antagonist" for c in roster.characters)
    if bible.antagonist_summary and not has_antagonist:
        warnings.append(
            "StoryBible.antagonist_summary is set but the roster has no antagonist role"
        )

    expected_supporting = len(bible.supporting_characters_summary)
    actual_supporting = len([c for c in roster.characters if c.role == "supporting"])
    if abs(expected_supporting - actual_supporting) > _SUPPORTING_COUNT_TOLERANCE:
        warnings.append(
            f"StoryBible lists {expected_supporting} supporting character summaries but "
            f"the roster has {actual_supporting} supporting characters"
        )

    for character in roster.characters:
        if not character.relationships and len(roster.characters) > 1:
            warnings.append(f"Character '{character.name}' has no relationships listed")

    return warnings
