from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.music import MusicGenerateRequest, MusicGenerateResponse
from app.services.music_service import MusicService

router = APIRouter(prefix="/assets", tags=["music"])


@router.post(
    "/generate-music",
    response_model=MusicGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_music(
    payload: MusicGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> MusicGenerateResponse:
    return await MusicService(db).generate(payload.storyboard_version_id)
