from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.config.settings import Settings
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectRead:
    project = await ProjectService(db).create(payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=Page[ProjectRead])
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Page[ProjectRead]:
    return await ProjectService(db).list(pagination.cursor, pagination.resolved_limit(settings))


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectRead:
    project = await ProjectService(db).get(project_id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID, payload: ProjectUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectRead:
    project = await ProjectService(db).update(project_id, payload)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    await ProjectService(db).delete(project_id)
