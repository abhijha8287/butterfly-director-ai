from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.schema import StoryRequest
from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.story_architect import StoryGenerateResponse
from app.services.story_architect_service import StoryArchitectService

router = APIRouter(prefix="/story", tags=["story-architect"])


@router.post("/generate", response_model=StoryGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_story(
    payload: StoryRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryGenerateResponse:
    return await StoryArchitectService(db).generate(payload)


@router.get("", response_model=Page[StoryGenerateResponse])
async def list_stories(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[StoryGenerateResponse]:
    return await StoryArchitectService(db).list(pagination.cursor, pagination.resolved_limit(settings))


@router.get("/{story_id}", response_model=StoryGenerateResponse)
async def get_story(
    story_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryGenerateResponse:
    return await StoryArchitectService(db).get(story_id)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(story_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await StoryArchitectService(db).delete(story_id)
