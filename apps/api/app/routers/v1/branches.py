from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate
from app.schemas.common import Page
from app.services.branch_service import BranchService

router = APIRouter(prefix="/branches", tags=["branches"])


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> BranchRead:
    branch = await BranchService(db).create(payload)
    return BranchRead.model_validate(branch)


@router.get("", response_model=Page[BranchRead])
async def list_branches(
    timeline_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[BranchRead]:
    return await BranchService(db).list_for_timeline(
        timeline_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{branch_id}", response_model=BranchRead)
async def get_branch(branch_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> BranchRead:
    branch = await BranchService(db).get(branch_id)
    return BranchRead.model_validate(branch)


@router.patch("/{branch_id}", response_model=BranchRead)
async def update_branch(
    branch_id: UUID, payload: BranchUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> BranchRead:
    branch = await BranchService(db).update(branch_id, payload)
    return BranchRead.model_validate(branch)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(branch_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await BranchService(db).delete(branch_id)
