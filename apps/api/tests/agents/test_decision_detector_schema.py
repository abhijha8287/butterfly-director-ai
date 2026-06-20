import pytest
from pydantic import ValidationError

from app.agents.decision_detector.schema import DecisionList
from tests.factories import make_branch_candidate, make_decision_list, make_decision_point


def test_branch_candidate_accepts_full_valid_payload() -> None:
    candidate = make_branch_candidate(label="Run")
    assert candidate.label == "Run"


def test_decision_point_accepts_empty_source_hook() -> None:
    decision = make_decision_point(source_hook=None)
    assert decision.source_hook is None


def test_decision_point_rejects_negative_beat_index() -> None:
    with pytest.raises(ValidationError):
        make_decision_point(beat_index=-1)


def test_decision_list_accepts_empty_decisions() -> None:
    decisions = DecisionList(decisions=[])
    assert decisions.decisions == []


def test_decision_list_accepts_multiple_ordered_decisions() -> None:
    decisions = make_decision_list(
        decisions=[
            make_decision_point(beat_index=0),
            make_decision_point(beat_index=1, description="Second fork."),
        ]
    )
    assert len(decisions.decisions) == 2


def test_decision_list_rejects_duplicate_beat_index() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        make_decision_list(
            decisions=[
                make_decision_point(beat_index=0),
                make_decision_point(beat_index=0, description="Conflicting fork."),
            ]
        )
