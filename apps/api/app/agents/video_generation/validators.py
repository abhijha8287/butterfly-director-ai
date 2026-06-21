from __future__ import annotations

from app.agents.video_generation.schema import ShotRenderRequest, VideoGenerationAgentResult
from app.core.exceptions import AgentOutputInvalidError


def validate_against_shots(
    result: VideoGenerationAgentResult, shots: list[ShotRenderRequest]
) -> list[str]:
    """Structural check: every requested shot must end up in exactly one of
    `rendered`/`failed`, matched by shot_number - this mapping is load-bearing
    for persistence (each outcome is written back onto the PromptHistory row
    it came from). Unlike the LLM agents, a per-shot failure itself is not a
    reason to retry the whole batch - other shots may have rendered fine -
    so it only produces a warning, never a hard fail.
    """
    warnings: list[str] = []

    expected_numbers = {s.shot_number for s in shots}
    rendered_numbers = [r.shot_number for r in result.rendered]
    failed_numbers = [f.shot_number for f in result.failed]
    actual_numbers = rendered_numbers + failed_numbers

    details = {"expected_numbers": sorted(expected_numbers), "actual_numbers": actual_numbers}

    if len(actual_numbers) != len(shots):
        raise AgentOutputInvalidError(
            f"Expected {len(shots)} shot outcomes (rendered + failed), got {len(actual_numbers)}",
            details=details,
        )

    if set(actual_numbers) != expected_numbers:
        raise AgentOutputInvalidError(
            "Rendered/failed shot_number values do not match the requested shots exactly",
            details=details,
        )

    if len(set(actual_numbers)) != len(actual_numbers):
        raise AgentOutputInvalidError(
            "Shot outcomes contain duplicate shot_number values",
            details={"actual_numbers": actual_numbers},
        )

    if result.failed:
        warnings.append(
            f"{len(result.failed)} of {len(shots)} shots failed to render: "
            f"{sorted(failed_numbers)}"
        )

    return warnings
