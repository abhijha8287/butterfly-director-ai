from __future__ import annotations

from decimal import Decimal

from app.db.models.branch import Branch

# Butterfly Score factors are intentionally structural-only (depth, sibling count,
# decision_summary richness) because no agent has populated semantic decision content
# yet (no Decision Detector / Character Memory agents in this build phase). Each factor
# reads real decision_summary keys when present and degrades to a documented baseline
# when absent, so the score automatically gets richer once agents populate
# decision_summary without any change to this algorithm.
BASE_SCORE = 10
MAX_DEPTH_CONTRIBUTION = 30
DEPTH_WEIGHT = 6
MAX_SIBLING_CONTRIBUTION = 20
SIBLING_WEIGHT = 5
MAX_CHARACTER_CONTRIBUTION = 20
CHARACTER_WEIGHT = 8
MAX_LOCATION_CONTRIBUTION = 10
LOCATION_WEIGHT = 4
ENDING_DIVERGENCE_CONTRIBUTION = 10

MIN_CONFIDENCE = 40
MAX_CONFIDENCE = 90
CONFIDENCE_PER_SIGNAL = 10

_SIGNAL_KEYS = (
    "affected_characters",
    "affected_locations",
    "emotional_impact",
    "ending_divergence",
    "narrative_impact",
)


def compute_butterfly_score(branch: Branch, sibling_count: int) -> int:
    """Score 0-100: higher means this decision radically changes the universe."""
    summary = branch.decision_summary or {}
    affected_characters = summary.get("affected_characters") or []
    affected_locations = summary.get("affected_locations") or []
    ending_divergence = summary.get("ending_divergence")

    score = BASE_SCORE
    score += min(MAX_DEPTH_CONTRIBUTION, branch.depth * DEPTH_WEIGHT)
    score += min(MAX_SIBLING_CONTRIBUTION, max(0, sibling_count - 1) * SIBLING_WEIGHT)
    score += min(MAX_CHARACTER_CONTRIBUTION, len(affected_characters) * CHARACTER_WEIGHT)
    score += min(MAX_LOCATION_CONTRIBUTION, len(affected_locations) * LOCATION_WEIGHT)
    if ending_divergence:
        score += ENDING_DIVERGENCE_CONTRIBUTION

    return max(0, min(100, score))


def compute_probability_confidence_explanation(
    branch: Branch, sibling_count: int
) -> tuple[Decimal, Decimal, str]:
    """Baseline probability is an even split across siblings (no agent weighting signal
    exists yet to favor one branch over another); confidence reflects how much real
    decision metadata backs that estimate."""
    summary = branch.decision_summary or {}
    signal_count = sum(1 for key in _SIGNAL_KEYS if summary.get(key))

    probability = (Decimal(100) / Decimal(max(1, sibling_count))).quantize(Decimal("0.01"))
    confidence = Decimal(min(MAX_CONFIDENCE, MIN_CONFIDENCE + signal_count * CONFIDENCE_PER_SIGNAL))

    if signal_count == 0:
        explanation = (
            f"Even split across {sibling_count} sibling branch(es) discovered at this "
            "decision point; no decision metadata yet, so this is a structural estimate."
        )
    else:
        explanation = (
            f"Even split across {sibling_count} sibling branch(es); confidence reflects "
            f"{signal_count} decision signal(s) (e.g. affected characters/locations) "
            "captured for this branch."
        )

    return probability, confidence, explanation
