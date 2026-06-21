from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.editor import EditorGenerateRequest, EditorGenerateResponse
from app.services.editor_service import EditorService

router = APIRouter(prefix="/assets", tags=["editor"])


@router.post(
    "/assemble-movie",
    response_model=EditorGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assemble_movie(
    payload: EditorGenerateRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> EditorGenerateResponse:
    return await EditorService(db).generate(payload.storyboard_version_id)
