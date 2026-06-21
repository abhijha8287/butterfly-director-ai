from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.storyboard import (
    StoryboardGenerateRequest,
    StoryboardGenerateResponse,
    StoryboardRead,
)
from app.services.storyboard_service import StoryboardService

router = APIRouter(prefix="/storyboard", tags=["storyboard"])


@router.post(
    "/generate", response_model=StoryboardGenerateResponse, status_code=status.HTTP_201_CREATED
)
async def generate_storyboard(
    payload: StoryboardGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryboardGenerateResponse:
    return await StoryboardService(db).generate(payload.branch_id)


@router.get("", response_model=Page[StoryboardRead])
async def list_storyboard_versions(
    branch_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[StoryboardRead]:
    return await StoryboardService(db).list(
        branch_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{version_id}", response_model=StoryboardRead)
async def get_storyboard_version(
    version_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryboardRead:
    return await StoryboardService(db).get(version_id)


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storyboard_version(
    version_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await StoryboardService(db).delete(version_id)
