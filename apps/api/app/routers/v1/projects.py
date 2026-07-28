from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.schema import StoryRequest
from app.config.settings import Settings
from app.core.deps import PaginationParams, get_db, get_pagination, get_settings_dep
from app.db.models.enums import VersionEntityType
from app.repositories.branch_repository import BranchRepository
from app.repositories.decision_point_repository import DecisionPointRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.character_architect import CharacterGenerateResponse
from app.schemas.character_memory import CharacterMemoryGenerateResponse
from app.schemas.common import Page
from app.schemas.decision_detector import DecisionGenerateResponse
from app.schemas.editor import EditorGenerateResponse
from app.schemas.music import MusicGenerateResponse
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.prompt_director import PromptDirectorGenerateResponse
from app.schemas.story_architect import StoryGenerateResponse
from app.schemas.storyboard import StoryboardGenerateResponse
from app.schemas.timeline_generator import TimelineGenerateBranchesResponse
from app.schemas.video_generation import VideoGenerationGenerateResponse
from app.schemas.voice import VoiceGenerateResponse
from app.services.character_architect_service import CharacterArchitectService
from app.services.character_memory_service import CharacterMemoryService
from app.services.decision_detector_service import DecisionDetectorService
from app.services.editor_service import EditorService
from app.services.music_service import MusicService
from app.services.project_service import ProjectService
from app.services.prompt_director_service import PromptDirectorService
from app.services.story_architect_service import StoryArchitectService
from app.services.storyboard_service import StoryboardService
from app.services.timeline_generator_service import TimelineGeneratorService
from app.services.video_generation_service import VideoGenerationService
from app.services.voice_service import VoiceService

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


# ── helpers ──────────────────────────────────────────────────────────────────

async def _latest_story(project_id: UUID, db: AsyncSession):
    items, _ = await StoryRepository(db).list_paginated(
        cursor=None, limit=1, project_id=project_id
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No story found for this project. Run Story Architect first.",
        )
    return items[0]


async def _latest_branch(project_id: UUID, db: AsyncSession):
    timelines, _ = await TimelineRepository(db).list_paginated(
        cursor=None, limit=1, project_id=project_id
    )
    if not timelines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No timeline found. Run Timeline Generator first.",
        )
    branch = await TimelineRepository(db).get_root_branch(timelines[0].id)
    if branch is None:
        branches = await BranchRepository(db).list_by_timeline(timelines[0].id)
        if not branches:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No branches found. Run Timeline Generator first.",
            )
        branch = branches[0]
    return branch


async def _latest_storyboard_version(project_id: UUID, db: AsyncSession):
    branch = await _latest_branch(project_id, db)
    versions, _ = await VersionRepository(db).list_paginated(
        cursor=None, limit=1,
        entity_type=VersionEntityType.STORYBOARD,
        entity_id=branch.id,
    )
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No storyboard version found. Run Storyboard first.",
        )
    return versions[0]


# ── Agent endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/agents/story-architect",
    response_model=StoryGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_story_architect(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryGenerateResponse:
    project = await ProjectService(db).get(project_id)
    story_request = StoryRequest(
        prompt=project.premise,
        target_runtime_minutes=int(project.settings.get("target_runtime_seconds", 300) / 60),
        genre=project.genre,
        style=project.tone,
    )
    return await StoryArchitectService(db).generate(story_request, project_id=project_id)


@router.post(
    "/{project_id}/agents/character-architect",
    response_model=CharacterGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_character_architect(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterGenerateResponse:
    story = await _latest_story(project_id, db)
    return await CharacterArchitectService(db).generate(story.id)


@router.post(
    "/{project_id}/agents/decision-detector",
    response_model=DecisionGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_decision_detector(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> DecisionGenerateResponse:
    story = await _latest_story(project_id, db)
    return await DecisionDetectorService(db).generate(story.id)


@router.post(
    "/{project_id}/agents/timeline-generator",
    response_model=TimelineGenerateBranchesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_timeline_generator(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> TimelineGenerateBranchesResponse:
    story = await _latest_story(project_id, db)
    decisions, _ = await DecisionPointRepository(db).list_paginated(
        cursor=None, limit=1, story_id=story.id
    )
    if not decisions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No decisions found for this story. Run Decision Detector first.",
        )
    return await TimelineGeneratorService(db).generate(
        project_id=project_id,
        story_id=story.id,
        decision_id=decisions[0].id,
        parent_branch_id=None,
    )


@router.post(
    "/{project_id}/agents/character-memory",
    response_model=CharacterMemoryGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_character_memory(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CharacterMemoryGenerateResponse:
    branch = await _latest_branch(project_id, db)
    return await CharacterMemoryService(db).generate(branch.id)


@router.post(
    "/{project_id}/agents/storyboard",
    response_model=StoryboardGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_storyboard(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoryboardGenerateResponse:
    branch = await _latest_branch(project_id, db)
    return await StoryboardService(db).generate(branch.id)


@router.post(
    "/{project_id}/agents/prompt-director",
    response_model=PromptDirectorGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_prompt_director(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> PromptDirectorGenerateResponse:
    version = await _latest_storyboard_version(project_id, db)
    return await PromptDirectorService(db).generate(version.id)


@router.post(
    "/{project_id}/agents/video-generation",
    response_model=VideoGenerationGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_video_generation(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> VideoGenerationGenerateResponse:
    version = await _latest_storyboard_version(project_id, db)
    return await VideoGenerationService(db).generate(version.id)


@router.post(
    "/{project_id}/agents/voice",
    response_model=VoiceGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_voice(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> VoiceGenerateResponse:
    version = await _latest_storyboard_version(project_id, db)
    return await VoiceService(db).generate(version.id)


@router.post(
    "/{project_id}/agents/music",
    response_model=MusicGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_music(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> MusicGenerateResponse:
    version = await _latest_storyboard_version(project_id, db)
    return await MusicService(db).generate(version.id)


@router.post(
    "/{project_id}/agents/editor",
    response_model=EditorGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_editor(
    project_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> EditorGenerateResponse:
    version = await _latest_storyboard_version(project_id, db)
    return await EditorService(db).generate(version.id)


@router.get("/{project_id}/agents/{agent_name}/status")
async def get_agent_status(
    project_id: UUID, agent_name: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    await ProjectService(db).get(project_id)
    return {"status": "ready", "project_id": str(project_id), "agent": agent_name}
