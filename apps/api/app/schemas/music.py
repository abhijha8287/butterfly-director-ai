import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import AssetRead


class MusicGenerateRequest(BaseModel):
    storyboard_version_id: uuid.UUID


class RenderedCueRead(BaseModel):
    start_shot_number: int
    end_shot_number: int
    mood: str
    tempo_bpm: int
    generation_prompt: str
    asset: AssetRead | None = Field(
        default=None, description="None when no MusicGenerationProvider is configured."
    )


class FailedCueRead(BaseModel):
    start_shot_number: int
    end_shot_number: int
    mood: str
    tempo_bpm: int
    generation_prompt: str
    attempts: int
    error: str


class MusicGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    storyboard_version_id: uuid.UUID
    cues: list[RenderedCueRead] = Field(default_factory=list)
    failed_cues: list[FailedCueRead] = Field(default_factory=list)
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
