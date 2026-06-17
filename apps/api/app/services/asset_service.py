from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset import Asset
from app.repositories.asset_repository import AssetRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.asset import AssetCreate
from app.schemas.common import Page


class AssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AssetRepository(session)
        self.project_repo = ProjectRepository(session)

    async def create(self, data: AssetCreate) -> Asset:
        await self.project_repo.get_or_404(data.project_id)
        asset = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return asset

    async def get(self, asset_id: UUID) -> Asset:
        return await self.repo.get_or_404(asset_id)

    async def list_for_project(
        self, project_id: UUID, cursor: str | None, limit: int
    ) -> Page[Asset]:
        items, next_cursor = await self.repo.list_paginated(
            cursor=cursor, limit=limit, project_id=project_id
        )
        return Page(items=list(items), next_cursor=next_cursor)
