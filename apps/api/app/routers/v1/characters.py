from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.character import CharacterCreate, CharacterRead, CharacterUpdate
from app.schemas.common import Page
from app.services.character_service import CharacterService

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: CharacterCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterRead:
    character = await CharacterService(db).create(payload)
    return CharacterRead.model_validate(character)


@router.get("", response_model=Page[CharacterRead])
async def list_characters(
    project_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[CharacterRead]:
    return await CharacterService(db).list_for_project(
        project_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{character_id}", response_model=CharacterRead)
async def get_character(
    character_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterRead:
    character = await CharacterService(db).get(character_id)
    return CharacterRead.model_validate(character)


@router.patch("/{character_id}", response_model=CharacterRead)
async def update_character(
    character_id: UUID, payload: CharacterUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterRead:
    character = await CharacterService(db).update(character_id, payload)
    return CharacterRead.model_validate(character)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await CharacterService(db).delete(character_id)
