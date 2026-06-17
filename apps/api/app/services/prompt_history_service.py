from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.prompt_history import PromptHistory
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.schemas.common import Page


class PromptHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PromptHistoryRepository(session)

    async def get(self, prompt_history_id: UUID) -> PromptHistory:
        return await self.repo.get_or_404(prompt_history_id)

    async def list(
        self, cursor: str | None, limit: int, branch_id: UUID | None = None
    ) -> Page[PromptHistory]:
        filters = {}
        if branch_id is not None:
            filters["branch_id"] = branch_id
        items, next_cursor = await self.repo.list_paginated(cursor=cursor, limit=limit, **filters)
        return Page(items=list(items), next_cursor=next_cursor)
