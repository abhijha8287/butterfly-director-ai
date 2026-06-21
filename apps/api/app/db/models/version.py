import uuid

from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import VersionEntityType, pg_enum
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Version(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Polymorphic regeneration history for any creative artifact (per
    ARCHITECTURE.md §4.12). entity_id is intentionally not a foreign key -
    it points at whichever table entity_type names (branches.id for a
    storyboard, characters.id for a character revision, etc.), so a single
    FK constraint isn't possible. created_by has no FK either: no `users`
    table exists in this build (auth is unbuilt, not just disabled), so it
    stays a plain nullable UUID - mirrors Project.owner_id.
    """

    __tablename__ = "versions"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "version_number", name="uq_versions_entity_version"
        ),
    )

    entity_type: Mapped[VersionEntityType] = mapped_column(
        pg_enum(VersionEntityType, "version_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
