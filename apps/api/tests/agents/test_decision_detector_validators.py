import pytest

from app.agents.decision_detector.validators import validate_against_story_bible
from app.config.settings import Settings
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_branch_candidate, make_decision_list, make_decision_point, make_story_bible


def _settings() -> Settings:
    return Settings(decision_branch_candidates_min=2, decision_branch_candidates_max=4)


def test_matching_decisions_within_bounds_produce_no_warnings() -> None:
    bible = make_story_bible(story_hooks=["hook"])
    decisions = make_decision_list(decisions=[make_decision_point(source_hook="hook")])
    warnings = validate_against_story_bible(decisions, bible, _settings())
    assert warnings == []


def test_too_few_branch_candidates_raises() -> None:
    bible = make_story_bible(story_hooks=[])
    decisions = make_decision_list(
        decisions=[make_decision_point(branch_candidates=[make_branch_candidate()])]
    )
    with pytest.raises(AgentOutputInvalidError):
        validate_against_story_bible(decisions, bible, _settings())


def test_too_many_branch_candidates_raises() -> None:
    bible = make_story_bible(story_hooks=[])
    candidates = [make_branch_candidate(label=f"Option {i}") for i in range(5)]
    decisions = make_decision_list(decisions=[make_decision_point(branch_candidates=candidates)])
    with pytest.raises(AgentOutputInvalidError):
        validate_against_story_bible(decisions, bible, _settings())


def test_empty_decisions_despite_hooks_warns() -> None:
    bible = make_story_bible(story_hooks=["hook"])
    decisions = make_decision_list(decisions=[])
    warnings = validate_against_story_bible(decisions, bible, _settings())
    assert any("zero decisions" in w for w in warnings)


def test_empty_decisions_with_no_hooks_produces_no_warning() -> None:
    bible = make_story_bible(story_hooks=[])
    decisions = make_decision_list(decisions=[])
    warnings = validate_against_story_bible(decisions, bible, _settings())
    assert warnings == []


def test_unmatched_hooks_warn() -> None:
    bible = make_story_bible(story_hooks=["hook one", "hook two"])
    decisions = make_decision_list(decisions=[make_decision_point(source_hook="hook one")])
    warnings = validate_against_story_bible(decisions, bible, _settings())
    assert any("not mapped" in w for w in warnings)


def test_out_of_order_beat_indices_warn() -> None:
    bible = make_story_bible(story_hooks=[])
    decisions = make_decision_list(
        decisions=[
            make_decision_point(beat_index=1, source_hook=None),
            make_decision_point(beat_index=0, description="Earlier fork.", source_hook=None),
        ]
    )
    warnings = validate_against_story_bible(decisions, bible, _settings())
    assert any("ascending" in w for w in warnings)
