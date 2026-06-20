from __future__ import annotations

from app.agents.decision_detector.schema import DecisionPoint
from app.agents.timeline_generator.schema import TimelineGenerationResult
from app.core.exceptions import AgentOutputInvalidError


def validate_against_decision(result: TimelineGenerationResult, decision: DecisionPoint) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. The hard rule is
    structural and non-negotiable: every branch_candidate on the decision must
    be expanded into exactly one BranchDraft, matched by label - persistence
    maps drafts back to candidates by candidate_label, so a mismatch here
    would silently corrupt that mapping if not caught. Returns non-fatal
    warnings for thin scoring-signal content.
    """
    warnings: list[str] = []

    expected_labels = {c.label for c in decision.branch_candidates}
    actual_labels = [b.candidate_label for b in result.branches]

    if len(actual_labels) != len(decision.branch_candidates):
        raise AgentOutputInvalidError(
            f"Expected {len(decision.branch_candidates)} branch drafts (one per "
            f"candidate), got {len(actual_labels)}",
            details={"expected_labels": sorted(expected_labels), "actual_labels": actual_labels},
        )

    if set(actual_labels) != expected_labels:
        raise AgentOutputInvalidError(
            "Branch draft candidate_label values do not match the decision's "
            "branch_candidates exactly",
            details={"expected_labels": sorted(expected_labels), "actual_labels": actual_labels},
        )

    if len(set(actual_labels)) != len(actual_labels):
        raise AgentOutputInvalidError(
            "Branch drafts contain duplicate candidate_label values",
            details={"actual_labels": actual_labels},
        )

    for draft in result.branches:
        if not draft.affected_characters:
            warnings.append(f"Branch draft '{draft.candidate_label}' has no affected_characters")
        if not draft.ending_divergence.strip():
            warnings.append(f"Branch draft '{draft.candidate_label}' has a blank ending_divergence")

    return warnings
