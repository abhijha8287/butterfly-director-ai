from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.asset import AssetCreate, AssetRead
from app.schemas.common import Page
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> AssetRead:
    asset = await AssetService(db).create(payload)
    return AssetRead.model_validate(asset)


@router.get("", response_model=Page[AssetRead])
async def list_assets(
    project_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[AssetRead]:
    return await AssetService(db).list_for_project(
        project_id, pagination.cursor, pagination.resolved_limit(settings)
    )


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(asset_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> AssetRead:
    asset = await AssetService(db).get(asset_id)
    return AssetRead.model_validate(asset)
