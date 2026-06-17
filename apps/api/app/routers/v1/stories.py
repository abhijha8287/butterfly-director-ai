from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.story import StoryCreate, StoryRead, StoryUpdate
from app.services.story_service import StoryService

router = APIRouter(prefix="/stories", tags=["stories"])


@router.post("", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryRead:
    story = await StoryService(db).create(payload)
    return StoryRead.model_validate(story)


@router.get("", response_model=Page[StoryRead])
async def list_stories(
    project_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[StoryRead]:
    return await StoryService(db).list_for_project(
        project_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{story_id}", response_model=StoryRead)
async def get_story(story_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> StoryRead:
    story = await StoryService(db).get(story_id)
    return StoryRead.model_validate(story)


@router.patch("/{story_id}", response_model=StoryRead)
async def update_story(
    story_id: UUID, payload: StoryUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryRead:
    story = await StoryService(db).update(story_id, payload)
    return StoryRead.model_validate(story)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(story_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await StoryService(db).delete(story_id)
