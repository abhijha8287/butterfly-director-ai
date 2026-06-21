import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoryboardGenerateRequest(BaseModel):
    branch_id: uuid.UUID


class ShotRead(BaseModel):
    scene: str
    shot_number: int
    description: str
    camera: str
    duration_seconds: float
    characters_present: list[str]


class StoryboardRead(BaseModel):
    """A single persisted storyboard version, reconstructed from the Version
    row's snapshot - the API-facing shape callers actually want, not the raw
    polymorphic Version row.
    """

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    branch_id: uuid.UUID
    version_number: int
    shots: list[ShotRead]
    created_at: datetime


class StoryboardGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    movie_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    shots: list[ShotRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
