from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.prompt_director import (
    PromptDirectorGenerateRequest,
    PromptDirectorGenerateResponse,
)
from app.services.prompt_director_service import PromptDirectorService

router = APIRouter(prefix="/prompt-history", tags=["prompt-director"])


@router.post(
    "/generate", response_model=PromptDirectorGenerateResponse, status_code=status.HTTP_201_CREATED
)
async def generate_shot_prompts(
    payload: PromptDirectorGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> PromptDirectorGenerateResponse:
    return await PromptDirectorService(db).generate(payload.storyboard_version_id)
