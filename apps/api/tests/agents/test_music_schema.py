from app.agents.music.schema import MusicAgentResult, MusicScript
from tests.factories import (
    make_music_cue,
    make_music_cue_failure,
    make_music_cue_result,
    make_music_request,
    make_music_shot_script,
    make_story_bible,
)


def test_music_shot_script_accepts_full_valid_payload() -> None:
    shot = make_music_shot_script()
    assert shot.shot_number == 1
    assert shot.duration_seconds > 0


def test_music_request_pairs_bible_summary_and_shots() -> None:
    request = make_music_request(story_bible=make_story_bible())
    assert request.branch_summary == "She shouts and is rescued."
    assert request.shots[0].shot_number == 1


def test_music_cue_accepts_full_valid_payload() -> None:
    cue = make_music_cue()
    assert cue.start_shot_number == 1
    assert cue.end_shot_number == 1
    assert cue.tempo_bpm > 0


def test_music_script_accepts_empty_cues_at_schema_level() -> None:
    # The hard "cues must reference real shots" rule lives in validators.py (it
    # needs to be retryable), not as a structural Pydantic constraint here. An
    # empty list is a structurally valid extraction result.
    script = MusicScript(cues=[])
    assert script.cues == []


def test_music_cue_result_defaults_to_no_provider() -> None:
    result = make_music_cue_result(provider=None, attempts=0)
    assert result.provider is None
    assert result.attempts == 0
    assert result.audio_url is None
    assert result.audio_bytes is None


def test_music_cue_failure_accepts_full_valid_payload() -> None:
    failure = make_music_cue_failure()
    assert failure.attempts == 3
    assert failure.error


def test_music_agent_result_holds_mixed_outcomes() -> None:
    result = MusicAgentResult(
        cues=[make_music_cue_result(start_shot_number=1, end_shot_number=1)],
        failed_cues=[make_music_cue_failure(start_shot_number=2, end_shot_number=3)],
    )
    assert len(result.cues) == 1
    assert len(result.failed_cues) == 1
