import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import AgentLogStatus


class AgentLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    agent_name: str
    input_snapshot: dict
    output_snapshot: dict | None
    latency_ms: int | None
    status: AgentLogStatus
    error_detail: str | None
    created_at: datetime
