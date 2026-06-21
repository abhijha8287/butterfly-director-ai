from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.character_memory import (
    CharacterMemoryGenerateRequest,
    CharacterMemoryGenerateResponse,
    CharacterStateRead,
)
from app.schemas.common import Page
from app.services.character_memory_service import CharacterMemoryService

router = APIRouter(prefix="/character-memory", tags=["character-memory"])


@router.post(
    "/generate", response_model=CharacterMemoryGenerateResponse, status_code=status.HTTP_201_CREATED
)
async def generate_character_memory(
    payload: CharacterMemoryGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterMemoryGenerateResponse:
    return await CharacterMemoryService(db).generate(payload.branch_id)


@router.get("", response_model=Page[CharacterStateRead])
async def list_character_states(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    branch_id: Annotated[UUID | None, Query()] = None,
    character_id: Annotated[UUID | None, Query()] = None,
) -> Page[CharacterStateRead]:
    return await CharacterMemoryService(db).list(
        branch_id, character_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{state_id}", response_model=CharacterStateRead)
async def get_character_state(
    state_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterStateRead:
    return await CharacterMemoryService(db).get(state_id)


@router.delete("/{state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_state(
    state_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await CharacterMemoryService(db).delete(state_id)
