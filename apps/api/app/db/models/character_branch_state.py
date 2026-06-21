import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import DriftSeverity, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.character import Character


class CharacterBranchState(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Per-(character, branch) consistency record produced by the Character
    Memory agent. drift_severity/drift_warning are first-class columns (not
    folded into state_diff) so ops can query "show me every major drift"
    directly; state_diff holds the descriptive fields (knowledge_state,
    emotional_state, relationship_changes, goal_shift, physical_state) that
    have no need to be individually queryable.
    """

    __tablename__ = "character_branch_states"
    __table_args__ = (
        UniqueConstraint("character_id", "branch_id", name="uq_character_branch_states"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    state_diff: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    drift_severity: Mapped[DriftSeverity] = mapped_column(
        pg_enum(DriftSeverity, "drift_severity"),
        default=DriftSeverity.NONE,
        nullable=False,
    )
    drift_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Agent generation provenance: prompt_version, model, latency_ms, attempts,
    # prompt_tokens, completion_tokens, generated_at. Mirrors every other
    # agent-produced row in this codebase.
    generation_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    character: Mapped["Character"] = relationship(back_populates="branch_states")
    branch: Mapped["Branch"] = relationship(back_populates="character_states")
