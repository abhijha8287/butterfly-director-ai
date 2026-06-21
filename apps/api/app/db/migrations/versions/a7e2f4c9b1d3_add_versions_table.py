"""add versions table

Revision ID: a7e2f4c9b1d3
Revises: f3b9c1a2d7e4
Create Date: 2026-06-21 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7e2f4c9b1d3'
down_revision: str | None = 'f3b9c1a2d7e4'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None

# create_type=False: app/db/models/version.py also defines this enum (via
# pg_enum()) and that model is imported into Base.metadata by env.py -
# letting op.create_table's column also auto-create the type fires
# CREATE TYPE twice in one DDL run ("type already exists"). See the
# character_branch_states migration for the same workaround.
version_entity_type_enum = postgresql.ENUM(
    'timeline', 'branch', 'movie', 'character', 'storyboard',
    name='version_entity_type', create_type=False,
)


def upgrade() -> None:
    version_entity_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table('versions',
    sa.Column('entity_type', version_entity_type_enum, nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_type', 'entity_id', 'version_number', name='uq_versions_entity_version')
    )
    op.create_index(op.f('ix_versions_entity_id'), 'versions', ['entity_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_versions_entity_id'), table_name='versions')
    op.drop_table('versions')
    version_entity_type_enum.drop(op.get_bind(), checkfirst=True)
