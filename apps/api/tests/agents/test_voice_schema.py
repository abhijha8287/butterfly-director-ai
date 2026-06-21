from app.agents.voice.schema import DialogueScript, VoiceAgentResult, VoiceRequest
from tests.factories import (
    make_dialogue_line,
    make_shot_script,
    make_story_bible,
    make_voice_character_profile,
    make_voice_line_failure,
    make_voice_line_result,
)


def test_voice_character_profile_defaults_unchanged_state() -> None:
    profile = make_voice_character_profile(emotional_state="unchanged")
    assert profile.emotional_state == "unchanged"


def test_shot_script_defaults_empty_characters_present() -> None:
    shot = make_shot_script(characters_present=[])
    assert shot.characters_present == []


def test_voice_request_pairs_bible_shots_and_characters() -> None:
    request = VoiceRequest(
        story_bible=make_story_bible(),
        branch_name="Universe: Rescue",
        shots=[make_shot_script()],
        characters=[make_voice_character_profile()],
    )
    assert request.shots[0].shot_number == 1
    assert request.characters[0].name == "Hero"


def test_dialogue_line_accepts_full_valid_payload() -> None:
    line = make_dialogue_line(shot_number=1)
    assert line.character_name == "Hero"
    assert line.delivery_note


def test_dialogue_script_accepts_empty_lines_at_schema_level() -> None:
    # The hard "lines must reference real shots/characters" rule lives in
    # validators.py (it needs to be retryable), not as a structural Pydantic
    # constraint here. An empty list is a valid extraction result.
    script = DialogueScript(lines=[])
    assert script.lines == []


def test_voice_line_result_accepts_full_valid_payload() -> None:
    result = make_voice_line_result(shot_number=1)
    assert result.provider == "dashscope"
    assert result.attempts == 1


def test_voice_line_failure_accepts_full_valid_payload() -> None:
    failure = make_voice_line_failure(shot_number=1)
    assert failure.attempts == 3
    assert failure.error


def test_voice_agent_result_holds_mixed_outcomes() -> None:
    result = VoiceAgentResult(
        lines=[make_voice_line_result(shot_number=1)],
        failed_lines=[make_voice_line_failure(shot_number=2)],
    )
    assert len(result.lines) == 1
    assert len(result.failed_lines) == 1
