import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import JobStatus, JobType, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.agent_log import AgentLog
    from app.db.models.branch import Branch
    from app.db.models.timeline import Timeline


class Job(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_job_type", "status", "job_type"),
        CheckConstraint("progress_pct >= 0 AND progress_pct <= 100", name="ck_jobs_progress_pct"),
    )

    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    job_type: Mapped[JobType] = mapped_column(pg_enum(JobType, "job_type"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    timeline_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("timelines.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), default=JobStatus.QUEUED, nullable=False
    )
    progress_pct: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    attempt: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped["Branch | None"] = relationship(back_populates="jobs")
    timeline: Mapped["Timeline | None"] = relationship(back_populates="jobs")
    agent_logs: Mapped[list["AgentLog"]] = relationship(back_populates="job")
