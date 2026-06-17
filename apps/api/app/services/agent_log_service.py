from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_log import AgentLog
from app.repositories.agent_log_repository import AgentLogRepository
from app.schemas.common import Page


class AgentLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AgentLogRepository(session)

    async def get(self, agent_log_id: UUID) -> AgentLog:
        return await self.repo.get_or_404(agent_log_id)

    async def list(
        self,
        cursor: str | None,
        limit: int,
        branch_id: UUID | None = None,
        agent_name: str | None = None,
    ) -> Page[AgentLog]:
        filters = {}
        if branch_id is not None:
            filters["branch_id"] = branch_id
        if agent_name is not None:
            filters["agent_name"] = agent_name
        items, next_cursor = await self.repo.list_paginated(cursor=cursor, limit=limit, **filters)
        return Page(items=list(items), next_cursor=next_cursor)
