from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.common import Page


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = JobRepository(session)

    async def get(self, job_id: UUID) -> Job:
        return await self.repo.get_or_404(job_id)

    async def list(
        self,
        cursor: str | None,
        limit: int,
        branch_id: UUID | None = None,
        timeline_id: UUID | None = None,
    ) -> Page[Job]:
        filters = {}
        if branch_id is not None:
            filters["branch_id"] = branch_id
        if timeline_id is not None:
            filters["timeline_id"] = timeline_id
        items, next_cursor = await self.repo.list_paginated(cursor=cursor, limit=limit, **filters)
        return Page(items=list(items), next_cursor=next_cursor)
