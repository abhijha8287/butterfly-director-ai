import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agents.character_memory.schema import DriftSeverity


class CharacterMemoryGenerateRequest(BaseModel):
    branch_id: uuid.UUID


class CharacterStateRead(BaseModel):
    """A single persisted character/branch consistency record, with the
    character's name attached for readability - resolved by the service from
    the joined Character row, since CharacterBranchState itself only stores
    character_id.
    """

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    character_id: uuid.UUID
    character_name: str
    branch_id: uuid.UUID
    state_diff: dict
    drift_severity: DriftSeverity
    drift_warning: str | None
    created_at: datetime


class CharacterMemoryGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    branch_id: uuid.UUID
    story_id: uuid.UUID
    states: list[CharacterStateRead]
    prompt_version: str
    model: str
    latency_ms: int
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime
