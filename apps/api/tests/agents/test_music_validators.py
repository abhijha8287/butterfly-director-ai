import pytest

from app.agents.music.schema import MusicScript
from app.agents.music.validators import validate_music_script
from app.core.exceptions import AgentOutputInvalidError
from tests.factories import make_music_cue, make_music_shot_script


def test_matching_cue_produces_no_warnings() -> None:
    shots = [make_music_shot_script(shot_number=1), make_music_shot_script(shot_number=2)]
    script = MusicScript(cues=[make_music_cue(start_shot_number=1, end_shot_number=2)])
    warnings = validate_music_script(script, shots)
    assert warnings == []


def test_empty_cues_is_valid_but_warns() -> None:
    shots = [make_music_shot_script(shot_number=1)]
    script = MusicScript(cues=[])
    warnings = validate_music_script(script, shots)
    assert any("No music cues" in w for w in warnings)


def test_unknown_start_shot_number_raises() -> None:
    shots = [make_music_shot_script(shot_number=1)]
    script = MusicScript(cues=[make_music_cue(start_shot_number=2, end_shot_number=2)])
    with pytest.raises(AgentOutputInvalidError, match="unknown start_shot_number"):
        validate_music_script(script, shots)


def test_unknown_end_shot_number_raises() -> None:
    shots = [make_music_shot_script(shot_number=1)]
    script = MusicScript(cues=[make_music_cue(start_shot_number=1, end_shot_number=2)])
    with pytest.raises(AgentOutputInvalidError, match="unknown end_shot_number"):
        validate_music_script(script, shots)


def test_end_before_start_raises() -> None:
    shots = [make_music_shot_script(shot_number=1), make_music_shot_script(shot_number=2)]
    script = MusicScript(cues=[make_music_cue(start_shot_number=2, end_shot_number=1)])
    with pytest.raises(AgentOutputInvalidError, match="precedes"):
        validate_music_script(script, shots)


def test_blank_generation_prompt_warns() -> None:
    shots = [make_music_shot_script(shot_number=1)]
    script = MusicScript(
        cues=[make_music_cue(start_shot_number=1, end_shot_number=1, generation_prompt="   ")]
    )
    warnings = validate_music_script(script, shots)
    assert any("blank generation_prompt" in w for w in warnings)


def test_multiple_cues_covering_disjoint_ranges_is_valid() -> None:
    shots = [make_music_shot_script(shot_number=n) for n in (1, 2, 3)]
    script = MusicScript(
        cues=[
            make_music_cue(start_shot_number=1, end_shot_number=2),
            make_music_cue(start_shot_number=3, end_shot_number=3),
        ]
    )
    warnings = validate_music_script(script, shots)
    assert warnings == []
