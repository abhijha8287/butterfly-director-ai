import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import PromptProvider, PromptStage, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.db.models.branch import Branch


class PromptHistory(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "prompt_history"

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[PromptStage] = mapped_column(pg_enum(PromptStage, "prompt_stage"), nullable=False)
    provider: Mapped[PromptProvider] = mapped_column(
        pg_enum(PromptProvider, "prompt_provider"), nullable=False
    )
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    branch: Mapped["Branch | None"] = relationship(back_populates="prompt_history")
