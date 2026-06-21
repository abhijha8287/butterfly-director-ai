from uuid import UUID

from sqlalchemy import func, select

from app.db.models.enums import VersionEntityType
from app.db.models.version import Version
from app.repositories.base_repository import BaseRepository


class VersionRepository(BaseRepository[Version]):
    model = Version

    async def next_version_number(self, entity_type: VersionEntityType, entity_id: UUID) -> int:
        stmt = select(func.max(Version.version_number)).where(
            Version.entity_type == entity_type,
            Version.entity_id == entity_id,
            Version.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
