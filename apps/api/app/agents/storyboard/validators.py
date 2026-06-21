from __future__ import annotations

from app.agents.storyboard.schema import StoryboardResult
from app.core.exceptions import AgentOutputInvalidError

_MAX_REASONABLE_SHOT_SECONDS = 60.0


def validate_shot_list(result: StoryboardResult, known_character_names: set[str]) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. The hard rules are
    structural and non-negotiable: a storyboard with zero shots is never a
    valid output (unlike Decision Detector, where zero decisions is a valid
    linear story), and shot_number must form a contiguous 1..N sequence -
    Prompt Director and Video Generation fan out per shot_number in order, so
    a gap or duplicate would silently corrupt that ordering. Returns non-fatal
    warnings for unknown character references and unusually long shots.
    """
    warnings: list[str] = []

    if not result.shots:
        raise AgentOutputInvalidError("Storyboard must contain at least one shot")

    shot_numbers = [s.shot_number for s in result.shots]
    if len(set(shot_numbers)) != len(shot_numbers):
        raise AgentOutputInvalidError(
            "Storyboard shot_number values must be unique", details={"shot_numbers": shot_numbers}
        )

    if sorted(shot_numbers) != list(range(1, len(shot_numbers) + 1)):
        raise AgentOutputInvalidError(
            "Storyboard shot_number values must form a contiguous sequence from 1 to N",
            details={"shot_numbers": shot_numbers},
        )

    for shot in result.shots:
        unknown = [name for name in shot.characters_present if name not in known_character_names]
        if unknown:
            warnings.append(f"Shot {shot.shot_number} references unknown characters: {unknown}")
        if shot.duration_seconds > _MAX_REASONABLE_SHOT_SECONDS:
            warnings.append(
                f"Shot {shot.shot_number} has an unusually long duration "
                f"({shot.duration_seconds}s) for a single shot"
            )

    return warnings
