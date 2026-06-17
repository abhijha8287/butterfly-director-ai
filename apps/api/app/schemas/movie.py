import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import MovieStatus


class MovieBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MovieCreate(MovieBase):
    branch_id: uuid.UUID


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    duration_seconds: int | None = None
    status: MovieStatus | None = None
    final_asset_id: uuid.UUID | None = None
    extra_metadata: dict | None = None


class MovieRead(MovieBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    duration_seconds: int | None
    status: MovieStatus
    final_asset_id: uuid.UUID | None
    extra_metadata: dict
    created_at: datetime
    updated_at: datetime
