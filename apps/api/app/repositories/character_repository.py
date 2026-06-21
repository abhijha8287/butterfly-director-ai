from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.db.models.character import Character
from app.repositories.base_repository import BaseRepository


class CharacterRepository(BaseRepository[Character]):
    model = Character

    async def list_all_by_story(self, story_id: UUID) -> Sequence[Character]:
        stmt = select(Character).where(
            Character.story_id == story_id, Character.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
