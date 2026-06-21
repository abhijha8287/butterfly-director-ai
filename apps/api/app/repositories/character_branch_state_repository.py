from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.db.models.character_branch_state import CharacterBranchState
from app.repositories.base_repository import BaseRepository


class CharacterBranchStateRepository(BaseRepository[CharacterBranchState]):
    model = CharacterBranchState

    async def get_by_character_and_branch(
        self, character_id: UUID, branch_id: UUID
    ) -> CharacterBranchState | None:
        stmt = select(CharacterBranchState).where(
            CharacterBranchState.character_id == character_id,
            CharacterBranchState.branch_id == branch_id,
            CharacterBranchState.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_by_branch(self, branch_id: UUID) -> Sequence[CharacterBranchState]:
        stmt = select(CharacterBranchState).where(
            CharacterBranchState.branch_id == branch_id,
            CharacterBranchState.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
