from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.enums import (
    AssetKind,
    AssetOwnerType,
    BranchStatus,
    JobStatus,
    MovieStatus,
    PromptProvider,
    PromptStage,
    StoryStatus,
    TimelineStatus,
    VersionEntityType,
)
from app.db.models.movie import Movie
from app.db.models.project import Project
from app.db.models.prompt_history import PromptHistory
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.db.models.version import Version
from app.repositories.asset_repository import AssetRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.services.editor_service import EditorService
from tests.factories import make_editor_agent_run_result, make_editor_result, make_story_bible

_SHOTS_SNAPSHOT = {
    "shots": [
        {
            "scene": "INT. ALLEY - NIGHT",
            "shot_number": 1,
            "description": "She screams. Footsteps approach.",
            "camera": "low-angle tracking shot",
            "duration_seconds": 4.0,
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


async def _create_movie(session: AsyncSession, branch_id) -> Movie:
    movie = await MovieRepository(session).create(
        branch_id=branch_id, title="Test Movie", status=MovieStatus.RENDERING
    )
    await session.commit()
    return movie


async def _create_storyboard_version(session: AsyncSession, branch_id, snapshot=None) -> Version:
    version = await VersionRepository(session).create(
        entity_type=VersionEntityType.STORYBOARD,
        entity_id=branch_id,
        version_number=1,
        snapshot=snapshot if snapshot is not None else _SHOTS_SNAPSHOT,
        created_by=None,
    )
    await session.commit()
    return version


async def _create_rendered_shot(
    session: AsyncSession,
    *,
    branch_id,
    project_id,
    storyboard_version_id,
    shot_number: int,
    duration_seconds: float,
    video_url: str = "https://example.com/shot.mp4",
) -> PromptHistory:
    row = await PromptHistoryRepository(session).create(
        branch_id=branch_id,
        agent_name="prompt_director",
        stage=PromptStage.SHOT_PROMPT,
        provider=PromptProvider.WAN,
        input_payload={
            "storyboard_version_id": str(storyboard_version_id),
            "shot": {"shot_number": shot_number, "duration_seconds": duration_seconds},
            "negative_prompt": "",
            "consistency_tokens": [],
            "style_tokens": [],
        },
        rendered_prompt="a cinematic shot",
        response_payload=None,
        token_usage=None,
    )
    asset = await AssetRepository(session).create(
        project_id=project_id,
        owner_type=AssetOwnerType.SHOT,
        owner_id=row.id,
        kind=AssetKind.VIDEO,
        oss_key=f"{video_url}?shot={shot_number}",
        oss_bucket="wan",
        mime_type="video/mp4",
        size_bytes=0,
        duration_seconds=Decimal(str(duration_seconds)),
    )
    row = await PromptHistoryRepository(session).update(
        row,
        response_payload={
            "asset_id": str(asset.id),
            "video_url": asset.oss_key,
            "provider": "wan",
            "attempts": 1,
        },
    )
    await session.commit()
    return row


async def _create_failed_shot(
    session: AsyncSession, *, branch_id, storyboard_version_id, shot_number: int
) -> PromptHistory:
    row = await PromptHistoryRepository(session).create(
        branch_id=branch_id,
        agent_name="prompt_director",
        stage=PromptStage.SHOT_PROMPT,
        provider=PromptProvider.WAN,
        input_payload={
            "storyboard_version_id": str(storyboard_version_id),
            "shot": {"shot_number": shot_number, "duration_seconds": 4.0},
            "negative_prompt": "",
            "consistency_tokens": [],
            "style_tokens": [],
        },
        rendered_prompt="a cinematic shot",
        response_payload={"error": "Wan task timed out", "attempts": 3},
        token_usage=None,
    )
    await session.commit()
    return row


async def _create_rendered_voice_line(
    session: AsyncSession, *, branch_id, project_id, storyboard_version_id, shot_number: int
) -> PromptHistory:
    row = await PromptHistoryRepository(session).create(
        branch_id=branch_id,
        agent_name="voice",
        stage=PromptStage.VOICE,
        provider=PromptProvider.DASHSCOPE,
        input_payload={
            "storyboard_version_id": str(storyboard_version_id),
            "shot_number": shot_number,
            "character_name": "Hero",
            "delivery_note": "urgent whisper",
        },
        rendered_prompt="Stay back.",
        response_payload=None,
        token_usage=None,
    )
    asset = await AssetRepository(session).create(
        project_id=project_id,
        owner_type=AssetOwnerType.VOICE,
        owner_id=row.id,
        kind=AssetKind.AUDIO,
        oss_key=f"/app/media/voice/{row.id}.mp3",
        oss_bucket="local",
        mime_type="audio/mp3",
        size_bytes=100,
        checksum_sha256="a" * 64,
    )
    row = await PromptHistoryRepository(session).update(
        row, response_payload={"asset_id": str(asset.id), "provider": "dashscope", "attempts": 1}
    )
    await session.commit()
    return row


async def _create_music_cue(
    session: AsyncSession,
    *,
    branch_id,
    project_id,
    storyboard_version_id,
    start_shot_number: int,
    end_shot_number: int,
    with_asset: bool,
) -> PromptHistory:
    row = await PromptHistoryRepository(session).create(
        branch_id=branch_id,
        agent_name="music",
        stage=PromptStage.MUSIC,
        provider=PromptProvider.HAPPYHORSE if with_asset else PromptProvider.NONE,
        input_payload={
            "storyboard_version_id": str(storyboard_version_id),
            "start_shot_number": start_shot_number,
            "end_shot_number": end_shot_number,
            "mood": "tense",
            "tempo_bpm": 100,
        },
        rendered_prompt="Dark ambient score.",
        response_payload=None,
        token_usage=None,
    )
    asset_id = None
    if with_asset:
        asset = await AssetRepository(session).create(
            project_id=project_id,
            owner_type=AssetOwnerType.MUSIC,
            owner_id=row.id,
            kind=AssetKind.AUDIO,
            oss_key=f"/app/media/music/{row.id}.mp3",
            oss_bucket="local",
            mime_type="audio/mp3",
            size_bytes=100,
            checksum_sha256="b" * 64,
        )
        asset_id = str(asset.id)
    row = await PromptHistoryRepository(session).update(
        row,
        response_payload={
            "asset_id": asset_id,
            "provider": "happyhorse" if with_asset else None,
            "attempts": 1 if with_asset else 0,
        },
    )
    await session.commit()
    return row


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> EditorService:
    service = EditorService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "editor"
    service.agent = mock_agent
    return service


async def _full_setup(session: AsyncSession) -> tuple[Project, Branch, Version]:
    project = await _create_project(session)
    story = await _create_story(session)
    timeline = await _create_timeline(session, project.id, story.id)
    branch = await _create_branch(session, timeline.id)
    await _create_movie(session, branch.id)
    version = await _create_storyboard_version(session, branch.id)
    return project, branch, version


@pytest.mark.asyncio
async def test_generate_assembles_final_cut_and_completes_movie(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    await _create_rendered_voice_line(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
    )
    await _create_music_cue(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        start_shot_number=1,
        end_shot_number=1,
        with_asset=True,
    )

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=4.0)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.branch_id == branch.id
    assert response.storyboard_version_id == version.id
    assert response.shot_count == 1
    assert response.voice_track_count == 1
    assert response.music_track_count == 1
    assert response.skipped_shot_numbers == []
    assert response.asset.kind == "video"

    movie = await MovieRepository(db_session).get_by_branch_id(branch.id)
    assert movie is not None
    assert movie.status == MovieStatus.COMPLETED
    assert movie.final_asset_id == response.asset.id

    sent_request = service.agent.run.call_args.args[0]
    assert len(sent_request.shots) == 1
    assert len(sent_request.audio_tracks) == 2


@pytest.mark.asyncio
async def test_generate_skips_shots_that_never_rendered(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    await _create_failed_shot(
        db_session, branch_id=branch.id, storyboard_version_id=version.id, shot_number=2
    )

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=4.0)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.shot_count == 1
    assert response.skipped_shot_numbers == [2]
    sent_request = service.agent.run.call_args.args[0]
    assert [s.shot_number for s in sent_request.shots] == [1]


@pytest.mark.asyncio
async def test_generate_skips_audio_track_referencing_a_skipped_shot(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    await _create_failed_shot(
        db_session, branch_id=branch.id, storyboard_version_id=version.id, shot_number=2
    )
    await _create_rendered_voice_line(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=2,
    )

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=4.0)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.voice_track_count == 0
    sent_request = service.agent.run.call_args.args[0]
    assert sent_request.audio_tracks == []


@pytest.mark.asyncio
async def test_generate_excludes_music_cues_with_no_provider_configured(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    await _create_music_cue(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        start_shot_number=1,
        end_shot_number=1,
        with_asset=False,
    )

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=4.0)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.music_track_count == 0


@pytest.mark.asyncio
async def test_generate_computes_cumulative_shot_start_times(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=2,
        duration_seconds=5.0,
    )
    await _create_rendered_voice_line(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=2,
    )

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=9.0)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    await service.generate(version.id)

    sent_request = service.agent.run.call_args.args[0]
    assert sent_request.audio_tracks[0].start_offset_seconds == 4.0


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_version(db_session: AsyncSession) -> None:
    service = EditorService(db_session)
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

    service = EditorService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(not_a_storyboard.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_no_movie_exists(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id)

    service = EditorService(db_session)
    with pytest.raises(ConflictError, match="Movie"):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_no_shot_prompts_found(
    db_session: AsyncSession,
) -> None:
    _, branch, version = await _full_setup(db_session)

    service = EditorService(db_session)
    with pytest.raises(ConflictError, match="shot prompts"):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_no_shots_rendered_successfully(
    db_session: AsyncSession,
) -> None:
    _, branch, version = await _full_setup(db_session)
    await _create_failed_shot(
        db_session, branch_id=branch.id, storyboard_version_id=version.id, shot_number=1
    )

    service = EditorService(db_session)
    with pytest.raises(ConflictError, match="rendered shots"):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_marks_job_failed(
    db_session: AsyncSession,
) -> None:
    project, branch, version = await _full_setup(db_session)
    await _create_rendered_shot(
        db_session,
        branch_id=branch.id,
        project_id=project.id,
        storyboard_version_id=version.id,
        shot_number=1,
        duration_seconds=4.0,
    )
    service = _service_with_mocked_agent(db_session, ConflictError("ffmpeg boom"))

    with pytest.raises(ConflictError):
        await service.generate(version.id)

    jobs, _ = await JobRepository(db_session).list_paginated(
        cursor=None, limit=10, branch_id=branch.id
    )
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.FAILED
