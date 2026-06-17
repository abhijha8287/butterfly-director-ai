from sqlalchemy import select

from app.db.models.branch import Branch
from app.db.models.timeline import Timeline
from app.repositories.base_repository import BaseRepository


class TimelineRepository(BaseRepository[Timeline]):
    model = Timeline

    async def get_root_branch(self, timeline_id) -> Branch | None:
        stmt = select(Branch).where(
            Branch.timeline_id == timeline_id,
            Branch.parent_branch_id.is_(None),
            Branch.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
