from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)

    async def create(self, data: ProjectCreate) -> Project:
        project = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return project

    async def get(self, project_id: UUID) -> Project:
        return await self.repo.get_or_404(project_id)

    async def list(self, cursor: str | None, limit: int) -> Page[Project]:
        items, next_cursor = await self.repo.list_paginated(cursor=cursor, limit=limit)
        return Page(items=list(items), next_cursor=next_cursor)

    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project:
        project = await self.repo.get_or_404(project_id)
        updates = data.model_dump(exclude_unset=True)
        project = await self.repo.update(project, **updates)
        await self.session.commit()
        return project

    async def delete(self, project_id: UUID) -> None:
        project = await self.repo.get_or_404(project_id)
        await self.repo.soft_delete(project)
        await self.session.commit()
