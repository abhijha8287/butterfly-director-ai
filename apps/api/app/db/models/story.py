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
    from app.db.models.character import Character
    from app.db.models.project import Project
    from app.db.models.timeline import Timeline


class Story(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "stories"

    # Nullable: a story can be generated standalone by an agent (e.g. the Story
    # Architect reference harness) before any Project exists to attach it to.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
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
    # Agent generation provenance: prompt_version, model, latency_ms, attempts,
    # prompt_tokens, completion_tokens, generated_at. Kept on the row itself
    # (rather than joined from AgentLog) since AgentLog has no story_id FK.
    generation_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    project: Mapped["Project | None"] = relationship(back_populates="stories")
    timelines: Mapped[list["Timeline"]] = relationship(back_populates="story")
    characters: Mapped[list["Character"]] = relationship(back_populates="story")
