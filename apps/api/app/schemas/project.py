import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import ProjectStatus


class ProjectBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    premise: str = Field(min_length=1)
    genre: str | None = None
    tone: str | None = None


class ProjectCreate(ProjectBase):
    settings: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    premise: str | None = Field(default=None, min_length=1)
    genre: str | None = None
    tone: str | None = None
    status: ProjectStatus | None = None
    settings: dict | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ProjectStatus
    settings: dict
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
