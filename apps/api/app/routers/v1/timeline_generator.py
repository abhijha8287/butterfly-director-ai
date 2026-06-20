from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.timeline_generator import (
    TimelineGenerateBranchesRequest,
    TimelineGenerateBranchesResponse,
)
from app.services.timeline_generator_service import TimelineGeneratorService

router = APIRouter(prefix="/timelines", tags=["timeline-generator"])


@router.post(
    "/generate-branches",
    response_model=TimelineGenerateBranchesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_branches(
    payload: TimelineGenerateBranchesRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineGenerateBranchesResponse:
    service = TimelineGeneratorService(db)
    return await service.generate(
        payload.project_id, payload.story_id, payload.decision_id, payload.parent_branch_id
    )
