from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.enums import (
    BranchStatus,
    PromptProvider,
    StoryStatus,
    TimelineStatus,
    VersionEntityType,
)
from app.db.models.project import Project
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.db.models.version import Version
from app.repositories.branch_repository import BranchRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.services.music_service import MusicService
from tests.factories import (
    make_music_agent_result,
    make_music_agent_run_result,
    make_music_cue_failure,
    make_music_cue_result,
    make_story_bible,
)

_SHOTS_SNAPSHOT = {
    "shots": [
        {
            "scene": "INT. ALLEY - NIGHT",
            "shot_number": 1,
            "description": "She screams. Footsteps approach.",
            "camera": "low-angle tracking shot",
            "duration_seconds": 4.5,
            "characters_present": ["Hero"],
        },
        {
            "scene": "EXT. ROOFTOP - NIGHT",
            "shot_number": 2,
            "description": "She climbs over the ledge.",
            "camera": "wide shot",
            "duration_seconds": 5.0,
            "characters_present": [],
        },
    ]
}


async def _create_project(session: AsyncSession) -> Project:
    project = await ProjectRepository(session).create(title="Test Project", premise="A test premise.")
    await session.commit()
    return project


async def _create_story(session: AsyncSession) -> Story:
    bible = make_story_bible()
    story = await StoryRepository(session).create(
        project_id=None,
        premise="A scientist discovers time travel.",
        genre=bible.genre,
        tone=bible.tone,
        status=StoryStatus.COMPLETED,
        world_bible=bible.model_dump(mode="json"),
        generation_metadata={},
    )
    await session.commit()
    return story


async def _create_timeline(session: AsyncSession, project_id, story_id) -> Timeline:
    timeline = await TimelineRepository(session).create(
        project_id=project_id, story_id=story_id, title="Test Timeline", status=TimelineStatus.ACTIVE
    )
    await session.commit()
    return timeline


async def _create_branch(session: AsyncSession, timeline_id) -> Branch:
    branch = await BranchRepository(session).create(
        timeline_id=timeline_id,
        parent_branch_id=None,
        name="Universe: Rescue",
        summary="She shouts and is rescued.",
        depth=0,
        status=BranchStatus.PENDING,
        is_canonical=True,
    )
    await session.commit()
    return branch


async def _create_storyboard_version(
    session: AsyncSession, branch_id, snapshot: dict | None = None
) -> Version:
    version = await VersionRepository(session).create(
        entity_type=VersionEntityType.STORYBOARD,
        entity_id=branch_id,
        version_number=1,
        snapshot=snapshot if snapshot is not None else _SHOTS_SNAPSHOT,
        created_by=None,
    )
    await session.commit()
    return version


async def _full_setup(session: AsyncSession) -> tuple[Branch, Version]:
    project = await _create_project(session)
    story = await _create_story(session)
    timeline = await _create_timeline(session, project.id, story.id)
    branch = await _create_branch(session, timeline.id)
    version = await _create_storyboard_version(session, branch.id)
    return branch, version


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> MusicService:
    service = MusicService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "music"
    service.agent = mock_agent
    return service


def _media_root_with_provider(tmp_path: Path, music_provider: str):
    return patch(
        "app.services.music_service.get_settings",
        return_value=Settings(media_root=str(tmp_path), music_provider=music_provider),
    )


@pytest.mark.asyncio
async def test_generate_creates_asset_from_audio_bytes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    branch, version = await _full_setup(db_session)
    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=2,
                    audio_bytes=b"hello-world-audio",
                    audio_url=None,
                    provider="happyhorse",
                )
            ],
            failed_cues=[],
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    with _media_root_with_provider(tmp_path, "happyhorse"):
        response = await service.generate(version.id)

    assert response.branch_id == branch.id
    assert response.storyboard_version_id == version.id
    assert len(response.cues) == 1
    asset = response.cues[0].asset
    assert asset is not None
    assert asset.kind == "audio"
    written = Path(asset.oss_key).read_bytes()
    assert written == b"hello-world-audio"
    assert asset.size_bytes == len(b"hello-world-audio")
    assert asset.checksum_sha256 is not None


@pytest.mark.asyncio
async def test_generate_creates_asset_from_audio_url(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    branch, version = await _full_setup(db_session)
    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=2,
                    audio_bytes=None,
                    audio_url="https://example.com/cue.mp3",
                    provider="happyhorse",
                )
            ],
            failed_cues=[],
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    with _media_root_with_provider(tmp_path, "happyhorse"):
        response = await service.generate(version.id)

    asset = response.cues[0].asset
    assert asset is not None
    assert asset.oss_key == "https://example.com/cue.mp3"
    assert asset.oss_bucket == "happyhorse"
    assert asset.size_bytes == 0
    assert asset.checksum_sha256 is None


@pytest.mark.asyncio
async def test_generate_leaves_asset_none_when_no_provider_configured(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    branch, version = await _full_setup(db_session)
    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=2,
                    audio_bytes=None,
                    audio_url=None,
                    provider=None,
                    attempts=0,
                )
            ],
            failed_cues=[],
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    with _media_root_with_provider(tmp_path, "none"):
        response = await service.generate(version.id)

    assert len(response.cues) == 1
    assert response.cues[0].asset is None
    assert response.cues[0].generation_prompt

    rows, _ = await PromptHistoryRepository(db_session).list_paginated(
        cursor=None, limit=10, branch_id=branch.id
    )
    assert len(rows) == 1
    assert rows[0].provider == PromptProvider.NONE
    assert rows[0].response_payload["asset_id"] is None


@pytest.mark.asyncio
async def test_generate_writes_outcome_back_to_prompt_history(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    branch, version = await _full_setup(db_session)
    rendered = make_music_cue_result(start_shot_number=1, end_shot_number=1)
    failed = make_music_cue_failure(start_shot_number=2, end_shot_number=2)
    run_result = make_music_agent_run_result(
        output=make_music_agent_result(cues=[rendered], failed_cues=[failed])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    with _media_root_with_provider(tmp_path, "happyhorse"):
        response = await service.generate(version.id)

    assert len(response.cues) == 1
    assert len(response.failed_cues) == 1
    assert response.failed_cues[0].error == failed.error


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_version(db_session: AsyncSession) -> None:
    service = MusicService(db_session)
    with pytest.raises(NotFoundError):
        await service.generate(uuid4())


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_version_is_not_storyboard(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    not_a_storyboard = await VersionRepository(db_session).create(
        entity_type=VersionEntityType.BRANCH,
        entity_id=branch.id,
        version_number=1,
        snapshot={"some": "thing"},
        created_by=None,
    )
    await db_session.commit()

    service = MusicService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(not_a_storyboard.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_timeline_has_no_story(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    timeline = await TimelineRepository(db_session).create(
        project_id=project.id, story_id=None, title="No Story Timeline", status=TimelineStatus.ACTIVE
    )
    await db_session.commit()
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id)

    service = MusicService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_storyboard_has_no_shots(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id, snapshot={"shots": []})

    service = MusicService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(
    db_session: AsyncSession,
) -> None:
    branch, version = await _full_setup(db_session)
    service = _service_with_mocked_agent(db_session, ConflictError("boom"))

    with pytest.raises(ConflictError):
        await service.generate(version.id)
