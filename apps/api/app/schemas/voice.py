import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset import AssetRead


class VoiceGenerateRequest(BaseModel):
    storyboard_version_id: uuid.UUID


class RenderedLineRead(BaseModel):
    shot_number: int
    character_name: str
    line_text: str
    delivery_note: str
    asset: AssetRead


class FailedLineRead(BaseModel):
    shot_number: int
    character_name: str
    line_text: str
    attempts: int
    error: str


class VoiceGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    storyboard_version_id: uuid.UUID
    lines: list[RenderedLineRead] = Field(default_factory=list)
    failed_lines: list[FailedLineRead] = Field(default_factory=list)
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
