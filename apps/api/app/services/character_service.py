from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.character import Character
from app.repositories.character_repository import CharacterRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.character import CharacterCreate, CharacterUpdate
from app.schemas.common import Page


class CharacterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CharacterRepository(session)
        self.project_repo = ProjectRepository(session)

    async def create(self, data: CharacterCreate) -> Character:
        await self.project_repo.get_or_404(data.project_id)
        character = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return character

    async def get(self, character_id: UUID) -> Character:
        return await self.repo.get_or_404(character_id)

    async def list_for_project(
        self, project_id: UUID, cursor: str | None, limit: int
    ) -> Page[Character]:
        items, next_cursor = await self.repo.list_paginated(
            cursor=cursor, limit=limit, project_id=project_id
        )
        return Page(items=list(items), next_cursor=next_cursor)

    async def update(self, character_id: UUID, data: CharacterUpdate) -> Character:
        character = await self.repo.get_or_404(character_id)
        updates = data.model_dump(exclude_unset=True)
        character = await self.repo.update(character, **updates)
        await self.session.commit()
        return character

    async def delete(self, character_id: UUID) -> None:
        character = await self.repo.get_or_404(character_id)
        await self.repo.soft_delete(character)
        await self.session.commit()
