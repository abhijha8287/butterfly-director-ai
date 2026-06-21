import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import AssetRead


class EditorGenerateRequest(BaseModel):
    storyboard_version_id: uuid.UUID


class EditorGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    movie_id: uuid.UUID
    job_id: uuid.UUID
    storyboard_version_id: uuid.UUID
    asset: AssetRead
    shot_count: int
    voice_track_count: int
    music_track_count: int
    skipped_shot_numbers: list[int] = Field(default_factory=list)
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    created_at: datetime
