from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.timeline import TimelineCreate, TimelineRead, TimelineTree, TimelineUpdate
from app.services.timeline_service import TimelineService

router = APIRouter(prefix="/timelines", tags=["timelines"])


@router.post("", response_model=TimelineRead, status_code=status.HTTP_201_CREATED)
async def create_timeline(
    payload: TimelineCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineRead:
    timeline = await TimelineService(db).create(payload)
    return TimelineRead.model_validate(timeline)


@router.get("", response_model=Page[TimelineRead])
async def list_timelines(
    project_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[TimelineRead]:
    return await TimelineService(db).list_for_project(
        project_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{timeline_id}", response_model=TimelineRead)
async def get_timeline(
    timeline_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineRead:
    timeline = await TimelineService(db).get(timeline_id)
    return TimelineRead.model_validate(timeline)


@router.get("/{timeline_id}/tree", response_model=TimelineTree)
async def get_timeline_tree(
    timeline_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineTree:
    return await TimelineService(db).get_tree(timeline_id)


@router.patch("/{timeline_id}", response_model=TimelineRead)
async def update_timeline(
    timeline_id: UUID, payload: TimelineUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineRead:
    timeline = await TimelineService(db).update(timeline_id, payload)
    return TimelineRead.model_validate(timeline)


@router.delete("/{timeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline(timeline_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await TimelineService(db).delete(timeline_id)
