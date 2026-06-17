import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import TimelineStatus, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.job import Job
    from app.db.models.project import Project
    from app.db.models.story import Story


class Timeline(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "timelines"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TimelineStatus] = mapped_column(
        pg_enum(TimelineStatus, "timeline_status"),
        default=TimelineStatus.PENDING,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="timelines")
    story: Mapped["Story | None"] = relationship(back_populates="timelines")
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="timeline", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="timeline")

    @property
    def root_branch(self) -> "Branch | None":
        return next((b for b in self.branches if b.parent_branch_id is None), None)
