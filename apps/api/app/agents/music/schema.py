from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.story_architect.schema import StoryBible


class MusicShotScript(BaseModel):
    scene: str
    shot_number: int = Field(ge=1)
    description: str
    duration_seconds: float


class MusicRequest(BaseModel):
    story_bible: StoryBible
    branch_name: str
    branch_summary: str = ""
    shots: list[MusicShotScript] = Field(default_factory=list)


class MusicCue(BaseModel):
    start_shot_number: int = Field(ge=1)
    end_shot_number: int = Field(
        ge=1, description="Must be >= start_shot_number - a cue spans a contiguous range."
    )
    mood: str = Field(description="Short, concrete emotional descriptor for this cue.")
    tempo_bpm: int = Field(ge=1, le=300)
    generation_prompt: str = Field(
        description="Self-contained, provider-ready text-to-music prompt for this cue."
    )


class MusicScript(BaseModel):
    """LLM output contract. An empty `cues` list is structurally valid (mirrors
    Decision Detector's zero-decisions and Voice's zero-lines cases), though the
    system prompt steers the model to default to scoring the whole branch.
    """

    cues: list[MusicCue] = Field(default_factory=list)


class MusicCueResult(BaseModel):
    start_shot_number: int = Field(ge=1)
    end_shot_number: int = Field(ge=1)
    mood: str
    tempo_bpm: int
    generation_prompt: str
    audio_url: str | None = None
    audio_bytes: bytes | None = None
    provider: str | None = Field(
        default=None, description="None when no MusicGenerationProvider is configured."
    )
    attempts: int = Field(ge=0, description="0 when synthesis was skipped (no provider).")


class MusicCueFailure(BaseModel):
    start_shot_number: int = Field(ge=1)
    end_shot_number: int = Field(ge=1)
    mood: str
    tempo_bpm: int
    generation_prompt: str
    attempts: int = Field(ge=1)
    error: str


class MusicAgentResult(BaseModel):
    cues: list[MusicCueResult] = Field(default_factory=list)
    failed_cues: list[MusicCueFailure] = Field(default_factory=list)
