from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.agent_log import AgentLogRead
from app.schemas.common import Page
from app.services.agent_log_service import AgentLogService

router = APIRouter(prefix="/agent-logs", tags=["agent-logs"])


@router.get("", response_model=Page[AgentLogRead])
async def list_agent_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    branch_id: Annotated[UUID | None, Query()] = None,
    agent_name: Annotated[str | None, Query()] = None,
) -> Page[AgentLogRead]:
    return await AgentLogService(db).list(
        pagination.cursor,
        pagination.resolved_limit(settings),
        branch_id=branch_id,
        agent_name=agent_name,
    )


@router.get("/{agent_log_id}", response_model=AgentLogRead)
async def get_agent_log(
    agent_log_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> AgentLogRead:
    agent_log = await AgentLogService(db).get(agent_log_id)
    return AgentLogRead.model_validate(agent_log)
