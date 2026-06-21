from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.video_generation import (
    VideoGenerationGenerateRequest,
    VideoGenerationGenerateResponse,
)
from app.services.video_generation_service import VideoGenerationService

router = APIRouter(prefix="/assets", tags=["video-generation"])


@router.post(
    "/render-shots",
    response_model=VideoGenerationGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def render_shots(
    payload: VideoGenerationGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> VideoGenerationGenerateResponse:
    return await VideoGenerationService(db).generate(payload.storyboard_version_id)
