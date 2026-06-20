from app.agents.timeline_generator.schema import TimelineGeneratorRequest, TimelineGenerationResult
from tests.factories import make_branch_draft, make_decision_point, make_story_bible


def test_branch_draft_accepts_full_valid_payload() -> None:
    draft = make_branch_draft(candidate_label="Shout")
    assert draft.candidate_label == "Shout"
    assert draft.affected_characters == ["Hero"]


def test_branch_draft_defaults_empty_lists() -> None:
    draft = make_branch_draft(affected_characters=[], affected_locations=[])
    assert draft.affected_characters == []
    assert draft.affected_locations == []


def test_timeline_generation_result_accepts_multiple_drafts() -> None:
    result = TimelineGenerationResult(
        branches=[make_branch_draft(candidate_label="Shout"), make_branch_draft(candidate_label="Run")]
    )
    assert len(result.branches) == 2


def test_timeline_generation_result_accepts_empty_branches() -> None:
    result = TimelineGenerationResult(branches=[])
    assert result.branches == []


def test_timeline_generator_request_pairs_bible_and_decision() -> None:
    request = TimelineGeneratorRequest(story_bible=make_story_bible(), decision=make_decision_point())
    assert request.story_bible.title == "T"
    assert request.decision.beat_index == 0
