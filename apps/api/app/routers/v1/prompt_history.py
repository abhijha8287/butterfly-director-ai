from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.prompt_history import PromptHistoryRead
from app.services.prompt_history_service import PromptHistoryService

router = APIRouter(prefix="/prompt-history", tags=["prompt-history"])


@router.get("", response_model=Page[PromptHistoryRead])
async def list_prompt_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    branch_id: Annotated[UUID | None, Query()] = None,
) -> Page[PromptHistoryRead]:
    return await PromptHistoryService(db).list(
        pagination.cursor, pagination.resolved_limit(settings), branch_id=branch_id
    )


@router.get("/{prompt_history_id}", response_model=PromptHistoryRead)
async def get_prompt_history(
    prompt_history_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> PromptHistoryRead:
    entry = await PromptHistoryService(db).get(prompt_history_id)
    return PromptHistoryRead.model_validate(entry)
