import pytest

from app.agents.timeline_generator.schema import TimelineGenerationResult
from app.agents.timeline_generator.validators import validate_against_decision
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_branch_candidate, make_branch_draft, make_decision_point


def test_matching_drafts_produce_no_warnings() -> None:
    decision = make_decision_point()
    result = TimelineGenerationResult(
        branches=[
            make_branch_draft(candidate_label="Shout"),
            make_branch_draft(candidate_label="Stay silent"),
        ]
    )
    warnings = validate_against_decision(result, decision)
    assert warnings == []


def test_wrong_draft_count_raises() -> None:
    decision = make_decision_point()
    result = TimelineGenerationResult(branches=[make_branch_draft(candidate_label="Shout")])
    with pytest.raises(AgentOutputInvalidError):
        validate_against_decision(result, decision)


def test_mismatched_labels_raise() -> None:
    decision = make_decision_point()
    result = TimelineGenerationResult(
        branches=[
            make_branch_draft(candidate_label="Shout"),
            make_branch_draft(candidate_label="Run away"),
        ]
    )
    with pytest.raises(AgentOutputInvalidError):
        validate_against_decision(result, decision)


def test_duplicate_labels_in_drafts_raise_when_label_set_still_matches() -> None:
    # The source decision itself has a duplicate candidate label (not prevented by
    # Decision Detector's schema) - this is the one case where the label-set-equality
    # check above can't catch a duplicate, so the explicit duplicate check matters.
    decision = make_decision_point(
        branch_candidates=[
            make_branch_candidate(label="Shout"),
            make_branch_candidate(label="Shout"),
        ]
    )
    result = TimelineGenerationResult(
        branches=[
            make_branch_draft(candidate_label="Shout"),
            make_branch_draft(candidate_label="Shout"),
        ]
    )
    with pytest.raises(AgentOutputInvalidError, match="duplicate"):
        validate_against_decision(result, decision)


def test_missing_affected_characters_warns() -> None:
    decision = make_decision_point()
    result = TimelineGenerationResult(
        branches=[
            make_branch_draft(candidate_label="Shout", affected_characters=[]),
            make_branch_draft(candidate_label="Stay silent"),
        ]
    )
    warnings = validate_against_decision(result, decision)
    assert any("affected_characters" in w for w in warnings)


def test_blank_ending_divergence_warns() -> None:
    decision = make_decision_point()
    result = TimelineGenerationResult(
        branches=[
            make_branch_draft(candidate_label="Shout", ending_divergence="  "),
            make_branch_draft(candidate_label="Stay silent"),
        ]
    )
    warnings = validate_against_decision(result, decision)
    assert any("ending_divergence" in w for w in warnings)
