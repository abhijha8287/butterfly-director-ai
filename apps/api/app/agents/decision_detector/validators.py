from __future__ import annotations

from app.agents.decision_detector.schema import DecisionList
from app.agents.story_architect.schema import StoryBible
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError


def validate_against_story_bible(
    decisions: DecisionList, bible: StoryBible, settings: Settings
) -> list[str]:
    """Semantic checks beyond plain Pydantic field types. The schema's own
    model_validator already raises on the one hard structural rule (duplicate
    beat_index); this enforces the configured branch-candidate fan-out bound
    (a hard contract violation - retry) and returns non-fatal warnings for
    everything else. An empty decision list is never flagged: per the
    architecture, zero decisions is a valid outcome (linear, single-branch
    timeline), not a failure.
    """
    warnings: list[str] = []

    for decision in decisions.decisions:
        count = len(decision.branch_candidates)
        if not (settings.decision_branch_candidates_min <= count <= settings.decision_branch_candidates_max):
            raise AgentOutputInvalidError(
                f"Decision at beat_index={decision.beat_index} has {count} branch "
                f"candidates, outside the configured "
                f"[{settings.decision_branch_candidates_min}, "
                f"{settings.decision_branch_candidates_max}] range",
                details={
                    "beat_index": decision.beat_index,
                    "candidate_count": count,
                    "min": settings.decision_branch_candidates_min,
                    "max": settings.decision_branch_candidates_max,
                },
            )

    if bible.story_hooks and not decisions.decisions:
        warnings.append(
            "StoryBible.story_hooks is non-empty but the agent produced zero decisions"
        )

    mapped_hooks = {d.source_hook for d in decisions.decisions if d.source_hook}
    unmatched_hooks = [h for h in bible.story_hooks if h not in mapped_hooks]
    if unmatched_hooks:
        warnings.append(f"{len(unmatched_hooks)} StoryBible.story_hooks were not mapped to a decision")

    indices = [d.beat_index for d in decisions.decisions]
    if indices != sorted(indices):
        warnings.append("Decision beat_index values are not in ascending order")

    return warnings
