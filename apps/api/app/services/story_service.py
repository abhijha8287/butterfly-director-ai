from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.story import Story
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.schemas.common import Page
from app.schemas.story import StoryCreate, StoryUpdate


class StoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = StoryRepository(session)
        self.project_repo = ProjectRepository(session)

    async def create(self, data: StoryCreate) -> Story:
        await self.project_repo.get_or_404(data.project_id)
        story = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return story

    async def get(self, story_id: UUID) -> Story:
        return await self.repo.get_or_404(story_id)

    async def list_for_project(self, project_id: UUID, cursor: str | None, limit: int) -> Page[Story]:
        items, next_cursor = await self.repo.list_paginated(
            cursor=cursor, limit=limit, project_id=project_id
        )
        return Page(items=list(items), next_cursor=next_cursor)

    async def update(self, story_id: UUID, data: StoryUpdate) -> Story:
        story = await self.repo.get_or_404(story_id)
        updates = data.model_dump(exclude_unset=True)
        story = await self.repo.update(story, **updates)
        await self.session.commit()
        return story

    async def delete(self, story_id: UUID) -> None:
        story = await self.repo.get_or_404(story_id)
        await self.repo.soft_delete(story)
        await self.session.commit()
