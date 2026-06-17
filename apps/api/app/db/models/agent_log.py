import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import AgentLogStatus, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.job import Job


class AgentLog(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "agent_logs"
    __table_args__ = (Index("ix_agent_logs_agent_name_created_at", "agent_name", "created_at"),)

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AgentLogStatus] = mapped_column(
        pg_enum(AgentLogStatus, "agent_log_status"), nullable=False
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job | None"] = relationship(back_populates="agent_logs")
    branch: Mapped["Branch | None"] = relationship(back_populates="agent_logs")
