from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.services.movie_service import MovieService

router = APIRouter(prefix="/movies", tags=["movies"])


@router.post("", response_model=MovieRead, status_code=status.HTTP_201_CREATED)
async def create_movie(
    payload: MovieCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> MovieRead:
    movie = await MovieService(db).create(payload)
    return MovieRead.model_validate(movie)


@router.get("/{movie_id}", response_model=MovieRead)
async def get_movie(movie_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> MovieRead:
    movie = await MovieService(db).get(movie_id)
    return MovieRead.model_validate(movie)


@router.get("/by-branch/{branch_id}", response_model=MovieRead)
async def get_movie_by_branch(
    branch_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> MovieRead:
    movie = await MovieService(db).get_by_branch(branch_id)
    return MovieRead.model_validate(movie)


@router.patch("/{movie_id}", response_model=MovieRead)
async def update_movie(
    movie_id: UUID, payload: MovieUpdate, db: Annotated[AsyncSession, Depends(get_db)]
) -> MovieRead:
    movie = await MovieService(db).update(movie_id, payload)
    return MovieRead.model_validate(movie)
