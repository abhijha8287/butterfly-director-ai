from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.character_architect import (
    CharacterGenerateRequest,
    CharacterGenerateResponse,
    CharacterProfileRead,
)
from app.schemas.common import Page
from app.services.character_architect_service import CharacterArchitectService

router = APIRouter(prefix="/character", tags=["character-architect"])


@router.post("/generate", response_model=CharacterGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_characters(
    payload: CharacterGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterGenerateResponse:
    return await CharacterArchitectService(db).generate(payload.story_id)


@router.get("", response_model=Page[CharacterProfileRead])
async def list_characters(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    story_id: Annotated[UUID | None, Query()] = None,
) -> Page[CharacterProfileRead]:
    return await CharacterArchitectService(db).list(
        story_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{character_id}", response_model=CharacterProfileRead)
async def get_character(
    character_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterProfileRead:
    return await CharacterArchitectService(db).get(character_id)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await CharacterArchitectService(db).delete(character_id)
