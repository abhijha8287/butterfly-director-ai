import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import JobStatus, JobType


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    celery_task_id: str | None
    job_type: JobType
    branch_id: uuid.UUID | None
    timeline_id: uuid.UUID | None
    status: JobStatus
    progress_pct: int
    attempt: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
