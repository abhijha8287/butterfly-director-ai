from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EditorShotInput(BaseModel):
    shot_number: int = Field(ge=1)
    video_url: str
    duration_seconds: float | None = None


class EditorAudioInput(BaseModel):
    """One audio layer to mix into the final cut - a Voice dialogue line or a
    Music cue, already rendered to a file (local path or URL) by their
    respective agents. start_offset_seconds is the cue/line's absolute
    position in the assembled timeline, computed by the service from the
    cumulative duration of every shot that precedes it in the final cut.
    """

    source: str
    start_offset_seconds: float = Field(ge=0)
    kind: Literal["voice", "music"]


class EditorRequest(BaseModel):
    shots: list[EditorShotInput] = Field(
        default_factory=list, description="Ordered by shot_number - the backbone of the cut."
    )
    audio_tracks: list[EditorAudioInput] = Field(default_factory=list)
    output_path: str


class EditorResult(BaseModel):
    output_path: str
    duration_seconds: float | None
    provider: str
    shot_count: int
    audio_track_count: int
