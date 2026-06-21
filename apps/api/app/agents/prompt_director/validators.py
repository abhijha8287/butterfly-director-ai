from __future__ import annotations

from app.agents.prompt_director.schema import PromptDirectorResult, ShotContext
from app.core.exceptions import AgentOutputInvalidError


def validate_against_shots(result: PromptDirectorResult, shots: list[ShotContext]) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. The hard rule is
    structural and non-negotiable: every shot must get exactly one
    ShotPrompt, matched by shot_number - persistence maps prompts back to
    shots by shot_number, so a mismatch here would silently corrupt that
    mapping if not caught. Returns non-fatal warnings for thin content.
    """
    warnings: list[str] = []

    expected_numbers = {s.shot_number for s in shots}
    actual_numbers = [p.shot_number for p in result.shot_prompts]

    details = {"expected_numbers": sorted(expected_numbers), "actual_numbers": actual_numbers}

    if len(actual_numbers) != len(shots):
        raise AgentOutputInvalidError(
            f"Expected {len(shots)} shot prompts (one per shot), got {len(actual_numbers)}",
            details=details,
        )

    if set(actual_numbers) != expected_numbers:
        raise AgentOutputInvalidError(
            "ShotPrompt shot_number values do not match the storyboard's shots exactly",
            details=details,
        )

    if len(set(actual_numbers)) != len(actual_numbers):
        raise AgentOutputInvalidError(
            "Shot prompts contain duplicate shot_number values",
            details={"actual_numbers": actual_numbers},
        )

    shots_by_number = {s.shot_number: s for s in shots}
    for prompt in result.shot_prompts:
        shot = shots_by_number[prompt.shot_number]
        if not prompt.negative_prompt.strip():
            warnings.append(f"Shot {prompt.shot_number} has a blank negative_prompt")
        if shot.characters and not prompt.consistency_tokens:
            warnings.append(
                f"Shot {prompt.shot_number} has characters present but no consistency_tokens"
            )

    return warnings
