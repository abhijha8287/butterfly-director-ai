from app.agents.editor.schema import EditorRequest
from tests.factories import make_editor_audio_input, make_editor_request, make_editor_shot_input


def test_editor_shot_input_accepts_full_valid_payload() -> None:
    shot = make_editor_shot_input()
    assert shot.shot_number == 1
    assert shot.duration_seconds and shot.duration_seconds > 0


def test_editor_audio_input_accepts_voice_and_music_kinds() -> None:
    voice_track = make_editor_audio_input(kind="voice")
    music_track = make_editor_audio_input(kind="music")
    assert voice_track.kind == "voice"
    assert music_track.kind == "music"


def test_editor_request_defaults_to_empty_audio_tracks() -> None:
    request = EditorRequest(shots=[make_editor_shot_input()], output_path="/tmp/out.mp4")
    assert request.audio_tracks == []


def test_editor_request_orders_shots_as_given() -> None:
    request = make_editor_request(
        shots=[
            make_editor_shot_input(shot_number=1),
            make_editor_shot_input(shot_number=2),
        ]
    )
    assert [s.shot_number for s in request.shots] == [1, 2]
