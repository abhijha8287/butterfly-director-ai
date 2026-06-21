import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import AssetRead


class VideoGenerationGenerateRequest(BaseModel):
    storyboard_version_id: uuid.UUID


class RenderedShotRead(BaseModel):
    shot_number: int
    asset: AssetRead


class FailedShotRead(BaseModel):
    shot_number: int
    attempts: int
    error: str


class VideoGenerationGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    movie_id: uuid.UUID
    job_id: uuid.UUID
    storyboard_version_id: uuid.UUID
    rendered: list[RenderedShotRead] = Field(default_factory=list)
    failed_shots: list[FailedShotRead] = Field(default_factory=list)
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    created_at: datetime
