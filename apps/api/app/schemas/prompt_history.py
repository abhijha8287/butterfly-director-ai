import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import PromptProvider, PromptStage


class PromptHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID | None
    agent_name: str
    stage: PromptStage
    provider: PromptProvider
    input_payload: dict
    rendered_prompt: str
    response_payload: dict | None
    token_usage: dict | None
    created_at: datetime
