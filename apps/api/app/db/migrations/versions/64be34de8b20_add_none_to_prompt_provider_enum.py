"""add none to prompt provider enum

Revision ID: 64be34de8b20
Revises: c2fccaabd7a7
Create Date: 2026-06-21 13:32:54.169503

"""
from collections.abc import Sequence

from alembic import op

revision: str = '64be34de8b20'
down_revision: str | None = 'c2fccaabd7a7'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # MUSIC_PROVIDER defaults to "none" (no real DashScope music provider exists in
    # this build) - the Music Agent still persists a PromptHistory row per cue even
    # when synthesis is skipped, and needs a provider value to write for that case.
    # The prompt_provider enum predates this agent and only had qwen/wan/happyhorse/
    # dashscope.
    op.execute("ALTER TYPE prompt_provider ADD VALUE IF NOT EXISTS 'none'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums - removing 'none' would require rebuilding
    # the prompt_provider type and rewriting every row using it. No-op, consistent
    # with this being a purely additive change.
    pass
