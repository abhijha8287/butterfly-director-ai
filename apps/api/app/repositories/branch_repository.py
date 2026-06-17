from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.db.models.branch import Branch
from app.repositories.base_repository import BaseRepository


class BranchRepository(BaseRepository[Branch]):
    model = Branch

    async def list_children(self, parent_branch_id: UUID) -> Sequence[Branch]:
        stmt = select(Branch).where(
            Branch.parent_branch_id == parent_branch_id, Branch.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_timeline(self, timeline_id: UUID) -> Sequence[Branch]:
        stmt = select(Branch).where(
            Branch.timeline_id == timeline_id, Branch.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_roots(self, timeline_id: UUID) -> Sequence[Branch]:
        stmt = select(Branch).where(
            Branch.timeline_id == timeline_id,
            Branch.parent_branch_id.is_(None),
            Branch.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_timeline(self, timeline_id: UUID) -> int:
        branches = await self.list_by_timeline(timeline_id)
        return len(branches)
