import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.story import Story


class DecisionPoint(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A single narrative fork detected by the Decision Detector agent for one
    Story. branch_candidates is the set of mutually exclusive directions the
    story could take here - the Timeline Generator agent later turns a chosen
    candidate into a concrete `branches` row.
    """

    __tablename__ = "decision_points"

    story_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    beat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_hook: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    branch_candidates: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Agent generation provenance: prompt_version, model, latency_ms, attempts,
    # prompt_tokens, completion_tokens, generated_at. Same blob duplicated across
    # every decision point produced by one agent run, mirroring stories/characters.
    generation_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    story: Mapped["Story"] = relationship(back_populates="decision_points")
