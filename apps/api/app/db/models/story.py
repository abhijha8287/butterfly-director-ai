import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import StoryStatus, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.timeline import Timeline


class Story(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "stories"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    premise: Mapped[str] = mapped_column(String, nullable=False)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[StoryStatus] = mapped_column(
        pg_enum(StoryStatus, "story_status"),
        default=StoryStatus.PENDING,
        nullable=False,
    )
    world_bible: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    characters_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    lore: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="stories")
    timelines: Mapped[list["Timeline"]] = relationship(back_populates="story")
