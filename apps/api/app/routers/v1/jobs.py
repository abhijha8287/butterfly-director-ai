from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.schemas.common import Page
from app.schemas.job import JobRead
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=Page[JobRead])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    branch_id: Annotated[UUID | None, Query()] = None,
    timeline_id: Annotated[UUID | None, Query()] = None,
) -> Page[JobRead]:
    return await JobService(db).list(
        pagination.cursor,
        pagination.resolved_limit(settings),
        branch_id=branch_id,
        timeline_id=timeline_id,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> JobRead:
    job = await JobService(db).get(job_id)
    return JobRead.model_validate(job)
