from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.decision_detector import (
    DecisionGenerateRequest,
    DecisionGenerateResponse,
    DecisionPointRead,
)
from app.services.decision_detector_service import DecisionDetectorService

router = APIRouter(prefix="/decision", tags=["decision-detector"])


@router.post("/generate", response_model=DecisionGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_decisions(
    payload: DecisionGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> DecisionGenerateResponse:
    return await DecisionDetectorService(db).generate(payload.story_id)


@router.get("", response_model=Page[DecisionPointRead])
async def list_decisions(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    story_id: Annotated[UUID | None, Query()] = None,
) -> Page[DecisionPointRead]:
    return await DecisionDetectorService(db).list(
        story_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{decision_id}", response_model=DecisionPointRead)
async def get_decision(
    decision_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> DecisionPointRead:
    return await DecisionDetectorService(db).get(decision_id)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision(decision_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await DecisionDetectorService(db).delete(decision_id)
