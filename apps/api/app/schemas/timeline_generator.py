import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.branch import BranchRead


class TimelineGenerateBranchesRequest(BaseModel):
    project_id: uuid.UUID
    story_id: uuid.UUID
    decision_id: uuid.UUID
    parent_branch_id: uuid.UUID | None = None


class TimelineGenerateBranchesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    timeline_id: uuid.UUID
    decision_id: uuid.UUID
    branches: list[BranchRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
