from __future__ import annotations

from app.agents.voice.schema import DialogueScript, ShotScript, VoiceCharacterProfile
from app.core.exceptions import AgentOutputInvalidError


def validate_dialogue_script(
    script: DialogueScript, shots: list[ShotScript], characters: list[VoiceCharacterProfile]
) -> list[str]:
    """Hard rule: every line must reference a real shot_number and a real
    character name from the input - this mapping is load-bearing, since lines
    are persisted/synthesized keyed off these references. Unlike Prompt
    Director's "exactly one per shot", there's no fixed count here - a shot
    can have zero, one, or several lines, and a branch with no spoken
    dialogue at all (an empty `lines` list) is a valid, common output, not an
    error - it only produces a warning.
    """
    warnings: list[str] = []
    valid_shot_numbers = {s.shot_number for s in shots}
    valid_character_names = {c.name for c in characters}

    for line in script.lines:
        if line.shot_number not in valid_shot_numbers:
            raise AgentOutputInvalidError(
                f"DialogueLine references unknown shot_number {line.shot_number}",
                details={"valid_shot_numbers": sorted(valid_shot_numbers)},
            )
        if line.character_name not in valid_character_names:
            raise AgentOutputInvalidError(
                f"DialogueLine references unknown character {line.character_name!r}",
                details={"valid_character_names": sorted(valid_character_names)},
            )
        if not line.line_text.strip():
            warnings.append(
                f"Shot {line.shot_number}: {line.character_name} has a blank line_text"
            )

    if not script.lines:
        warnings.append(
            "No dialogue lines were extracted for this branch - all shots may be "
            "non-verbal/action only"
        )

    return warnings
