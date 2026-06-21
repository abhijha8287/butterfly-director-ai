from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.voice import VoiceGenerateRequest, VoiceGenerateResponse
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/assets", tags=["voice"])


@router.post(
    "/synthesize-voice",
    response_model=VoiceGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def synthesize_voice(
    payload: VoiceGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> VoiceGenerateResponse:
    return await VoiceService(db).generate(payload.storyboard_version_id)
