import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import BranchStatus, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.agent_log import AgentLog
    from app.db.models.job import Job
    from app.db.models.movie import Movie
    from app.db.models.prompt_history import PromptHistory
    from app.db.models.timeline import Timeline


class Branch(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        Index("ix_branches_timeline_parent", "timeline_id", "parent_branch_id"),
        CheckConstraint(
            "butterfly_score IS NULL OR (butterfly_score >= 0 AND butterfly_score <= 100)",
            name="ck_branches_butterfly_score_range",
        ),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 100)",
            name="ck_branches_probability_range",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)",
            name="ck_branches_confidence_score_range",
        ),
    )

    timeline_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("timelines.id", ondelete="CASCADE"), nullable=False
    )
    parent_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[BranchStatus] = mapped_column(
        pg_enum(BranchStatus, "branch_status"),
        default=BranchStatus.PENDING,
        nullable=False,
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    butterfly_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    stability_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    timeline: Mapped["Timeline"] = relationship(back_populates="branches")
    parent: Mapped["Branch | None"] = relationship(
        remote_side="Branch.id", back_populates="children"
    )
    children: Mapped[list["Branch"]] = relationship(back_populates="parent")
    movie: Mapped["Movie | None"] = relationship(back_populates="branch", uselist=False)
    jobs: Mapped[list["Job"]] = relationship(back_populates="branch")
    agent_logs: Mapped[list["AgentLog"]] = relationship(back_populates="branch")
    prompt_history: Mapped[list["PromptHistory"]] = relationship(back_populates="branch")
