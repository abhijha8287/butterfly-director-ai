import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import StoryStatus


class StoryBase(BaseModel):
    premise: str = Field(min_length=1)
    genre: str | None = None
    tone: str | None = None


class StoryCreate(StoryBase):
    project_id: uuid.UUID


class StoryUpdate(BaseModel):
    genre: str | None = None
    tone: str | None = None
    status: StoryStatus | None = None
    world_bible: dict | None = None
    characters_summary: dict | None = None
    lore: dict | None = None


class StoryRead(StoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    status: StoryStatus
    world_bible: dict
    characters_summary: dict
    lore: dict
    created_at: datetime
    updated_at: datetime
