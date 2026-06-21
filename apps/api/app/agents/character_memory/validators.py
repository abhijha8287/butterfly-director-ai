from __future__ import annotations

from app.agents.character_memory.schema import CharacterMemoryProfile, CharacterMemoryResult
from app.core.exceptions import AgentOutputInvalidError


def validate_against_roster(
    result: CharacterMemoryResult, characters: list[CharacterMemoryProfile]
) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. The hard rule is
    structural and non-negotiable: every character in the input roster must
    get exactly one CharacterStateDiff, matched by name - persistence maps
    diffs back to Character rows by character_name, so a mismatch here would
    silently corrupt that mapping if not caught. The drift_severity/
    drift_warning consistency rule is the one domain-specific hard rule:
    a severity without an explanation is useless to a human reviewer.
    Returns non-fatal warnings for thin content.
    """
    warnings: list[str] = []

    expected_names = {c.name for c in characters}
    actual_names = [s.character_name for s in result.character_states]

    if len(actual_names) != len(characters):
        raise AgentOutputInvalidError(
            f"Expected {len(characters)} character state diffs (one per character), "
            f"got {len(actual_names)}",
            details={"expected_names": sorted(expected_names), "actual_names": actual_names},
        )

    if set(actual_names) != expected_names:
        raise AgentOutputInvalidError(
            "CharacterStateDiff character_name values do not match the input roster exactly",
            details={"expected_names": sorted(expected_names), "actual_names": actual_names},
        )

    if len(set(actual_names)) != len(actual_names):
        raise AgentOutputInvalidError(
            "Character state diffs contain duplicate character_name values",
            details={"actual_names": actual_names},
        )

    for state in result.character_states:
        if state.drift_severity != "none" and not (state.drift_warning or "").strip():
            raise AgentOutputInvalidError(
                f"Character state for '{state.character_name}' has drift_severity="
                f"'{state.drift_severity}' but no drift_warning explaining it",
                details={"character_name": state.character_name},
            )
        if state.drift_severity == "none" and state.drift_warning:
            warnings.append(
                f"Character '{state.character_name}' has drift_warning set despite "
                "drift_severity='none'"
            )
        if not state.knowledge_state.strip() and not state.emotional_state.strip():
            warnings.append(
                f"Character '{state.character_name}' has a thin state_diff "
                "(no knowledge_state or emotional_state)"
            )

    return warnings
