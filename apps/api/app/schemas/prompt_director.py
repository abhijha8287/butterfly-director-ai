import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.prompt_history import PromptHistoryRead


class PromptDirectorGenerateRequest(BaseModel):
    storyboard_version_id: uuid.UUID


class PromptDirectorGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    storyboard_version_id: uuid.UUID
    shot_prompts: list[PromptHistoryRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
