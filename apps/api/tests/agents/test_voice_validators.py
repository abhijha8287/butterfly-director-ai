import pytest

from app.agents.voice.schema import DialogueScript
from app.agents.voice.validators import validate_dialogue_script
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_dialogue_line, make_shot_script, make_voice_character_profile


def test_matching_lines_produce_no_warnings() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [make_voice_character_profile(name="Hero")]
    script = DialogueScript(lines=[make_dialogue_line(shot_number=1, character_name="Hero")])
    warnings = validate_dialogue_script(script, shots, characters)
    assert warnings == []


def test_empty_lines_is_valid_but_warns() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [make_voice_character_profile(name="Hero")]
    script = DialogueScript(lines=[])
    warnings = validate_dialogue_script(script, shots, characters)
    assert any("No dialogue lines" in w for w in warnings)


def test_unknown_shot_number_raises() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [make_voice_character_profile(name="Hero")]
    script = DialogueScript(lines=[make_dialogue_line(shot_number=2, character_name="Hero")])
    with pytest.raises(AgentOutputInvalidError, match="unknown shot_number"):
        validate_dialogue_script(script, shots, characters)


def test_unknown_character_name_raises() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [make_voice_character_profile(name="Hero")]
    script = DialogueScript(
        lines=[make_dialogue_line(shot_number=1, character_name="Unknown Extra")]
    )
    with pytest.raises(AgentOutputInvalidError, match="unknown character"):
        validate_dialogue_script(script, shots, characters)


def test_blank_line_text_warns() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [make_voice_character_profile(name="Hero")]
    script = DialogueScript(
        lines=[make_dialogue_line(shot_number=1, character_name="Hero", line_text="   ")]
    )
    warnings = validate_dialogue_script(script, shots, characters)
    assert any("blank line_text" in w for w in warnings)


def test_multiple_lines_in_one_shot_is_valid() -> None:
    shots = [make_shot_script(shot_number=1)]
    characters = [
        make_voice_character_profile(name="Hero"),
        make_voice_character_profile(name="Villain"),
    ]
    script = DialogueScript(
        lines=[
            make_dialogue_line(shot_number=1, character_name="Hero"),
            make_dialogue_line(shot_number=1, character_name="Villain"),
        ]
    )
    warnings = validate_dialogue_script(script, shots, characters)
    assert warnings == []
