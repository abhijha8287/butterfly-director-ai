import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agents.story_architect.schema import StoryBible, StoryRequest

StoryGenerateRequest = StoryRequest


class StoryGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    story_bible: StoryBible
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
