"""add dashscope to prompt provider enum

Revision ID: c2fccaabd7a7
Revises: a7e2f4c9b1d3
Create Date: 2026-06-21 08:56:34.030451

"""
from collections.abc import Sequence

from alembic import op

revision: str = 'c2fccaabd7a7'
down_revision: str | None = 'a7e2f4c9b1d3'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # The Voice Agent's TTS provider self-reports as "dashscope" (DashScopeTTSProvider
    # returns provider="dashscope" in VoiceGenerationResult), distinct from "wan" - the
    # prompt_provider enum predates this agent and only had qwen/wan/happyhorse.
    op.execute("ALTER TYPE prompt_provider ADD VALUE IF NOT EXISTS 'dashscope'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums - removing 'dashscope' would require
    # rebuilding the prompt_provider type and rewriting every row using it. No-op,
    # consistent with this being a purely additive change.
    pass
