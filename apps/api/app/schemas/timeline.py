import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import TimelineStatus


class TimelineBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class TimelineCreate(TimelineBase):
    project_id: uuid.UUID
    story_id: uuid.UUID | None = None


class TimelineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: TimelineStatus | None = None


class TimelineRead(TimelineBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    story_id: uuid.UUID | None
    status: TimelineStatus
    created_at: datetime
    updated_at: datetime


class BranchTreeNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_branch_id: uuid.UUID | None
    name: str
    summary: str | None
    decision_summary: dict | None
    depth: int
    position: dict | None
    status: str
    is_canonical: bool
    butterfly_score: int | None = None
    probability: Decimal | None = None
    confidence_score: Decimal | None = None
    stability_explanation: str | None = None
    movie_id: uuid.UUID | None = None
    movie_status: str | None = None


class TimelineTree(BaseModel):
    timeline: TimelineRead
    branches: list[BranchTreeNode]
