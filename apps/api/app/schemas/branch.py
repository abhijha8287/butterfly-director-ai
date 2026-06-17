import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import BranchStatus


class BranchBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    summary: str | None = None


class BranchCreate(BranchBase):
    timeline_id: uuid.UUID
    parent_branch_id: uuid.UUID | None = None
    decision_summary: dict | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    decision_summary: dict | None = None
    status: BranchStatus | None = None
    is_canonical: bool | None = None
    position: dict | None = None


class BranchRead(BranchBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timeline_id: uuid.UUID
    parent_branch_id: uuid.UUID | None
    decision_summary: dict | None
    depth: int
    position: dict | None
    status: BranchStatus
    is_canonical: bool
    butterfly_score: int | None
    probability: Decimal | None
    confidence_score: Decimal | None
    stability_explanation: str | None
    created_at: datetime
    updated_at: datetime
