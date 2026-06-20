import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agents.decision_detector.schema import BranchCandidate


class DecisionGenerateRequest(BaseModel):
    story_id: uuid.UUID


class DecisionPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    story_id: uuid.UUID
    beat_index: int
    description: str
    source_hook: str | None
    branch_candidates: list[BranchCandidate]
    created_at: datetime


class DecisionGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    story_id: uuid.UUID
    decisions: list[DecisionPointRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
