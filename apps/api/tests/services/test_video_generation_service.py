from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.enums import (
    BranchStatus,
    JobStatus,
    JobType,
    MovieStatus,
    PromptProvider,
    PromptStage,
    StoryStatus,
    TimelineStatus,
    VersionEntityType,
)
from app.db.models.project import Project
from app.db.models.prompt_history import PromptHistory
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.db.models.version import Version
from app.repositories.branch_repository import BranchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.services.video_generation_service import VideoGenerationService
from tests.factories import (
    make_shot_render_failure,
    make_shot_render_result,
    make_story_bible,
    make_video_generation_agent_result,
    make_video_generation_agent_run_result,
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


async def _create_shot_prompt(
    session: AsyncSession, branch_id, storyboard_version_id, shot: dict
) -> PromptHistory:
    row = await PromptHistoryRepository(session).create(
        branch_id=branch_id,
        agent_name="prompt_director",
        stage=PromptStage.SHOT_PROMPT,
        provider=PromptProvider.WAN,
        input_payload={
            "storyboard_version_id": str(storyboard_version_id),
            "shot": shot,
            "negative_prompt": "extra limbs, text artifacts",
            "consistency_tokens": [],
            "style_tokens": [],
        },
        rendered_prompt=f"Provider-ready prompt for shot {shot['shot_number']}.",
        response_payload=None,
        token_usage=None,
    )
    await session.commit()
    return row


async def _full_setup(session: AsyncSession) -> tuple[Branch, Version, list[PromptHistory]]:
    project = await _create_project(session)
    story = await _create_story(session)
    timeline = await _create_timeline(session, project.id, story.id)
    branch = await _create_branch(session, timeline.id)
    version = await _create_storyboard_version(session, branch.id)
    rows = [
        await _create_shot_prompt(session, branch.id, version.id, shot)
        for shot in _SHOTS_SNAPSHOT["shots"]
    ]
    return branch, version, rows


def _render_result_for(row: PromptHistory, **overrides: object) -> object:
    return make_shot_render_result(
        shot_number=row.input_payload["shot"]["shot_number"],
        prompt_history_id=row.id,
        **overrides,
    )


def _service_with_mocked_agent(
    session: AsyncSession, run_result_or_error: object
) -> VideoGenerationService:
    service = VideoGenerationService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "video_generation"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_creates_one_asset_per_rendered_shot(db_session: AsyncSession) -> None:
    branch, version, rows = await _full_setup(db_session)
    rendered = [
        _render_result_for(row)
        for row in rows
    ]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.branch_id == branch.id
    assert response.storyboard_version_id == version.id
    assert len(response.rendered) == 2
    assert response.failed_shots == []
    for item in response.rendered:
        assert item.asset.kind == "video"


@pytest.mark.asyncio
async def test_generate_writes_outcome_back_to_prompt_history_response_payload(
    db_session: AsyncSession,
) -> None:
    branch, version, rows = await _full_setup(db_session)
    rendered = [make_shot_render_result(shot_number=1, prompt_history_id=rows[0].id)]
    failed = [make_shot_render_failure(shot_number=2, prompt_history_id=rows[1].id)]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=failed)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    await service.generate(version.id)

    await db_session.refresh(rows[0])
    await db_session.refresh(rows[1])
    assert rows[0].response_payload["video_url"] == rendered[0].video_url
    assert rows[1].response_payload["error"] == failed[0].error


@pytest.mark.asyncio
async def test_generate_marks_job_succeeded_when_all_shots_render(db_session: AsyncSession) -> None:
    branch, version, rows = await _full_setup(db_session)
    rendered = [
        _render_result_for(row)
        for row in rows
    ]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    job = await JobRepository(db_session).get_or_404(response.job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert job.job_type == JobType.VIDEO_RENDER
    assert job.progress_pct == 100


@pytest.mark.asyncio
async def test_generate_marks_job_failed_with_partial_progress_on_partial_failure(
    db_session: AsyncSession,
) -> None:
    branch, version, rows = await _full_setup(db_session)
    rendered = [make_shot_render_result(shot_number=1, prompt_history_id=rows[0].id)]
    failed = [make_shot_render_failure(shot_number=2, prompt_history_id=rows[1].id)]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=failed)
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    job = await JobRepository(db_session).get_or_404(response.job_id)
    assert job.status == JobStatus.FAILED
    assert job.progress_pct == 50
    assert len(response.failed_shots) == 1


@pytest.mark.asyncio
async def test_generate_moves_movie_to_rendering_status(db_session: AsyncSession) -> None:
    branch, version, rows = await _full_setup(db_session)
    rendered = [
        _render_result_for(row)
        for row in rows
    ]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    movie = await MovieRepository(db_session).get_or_404(response.movie_id)
    assert movie.status == MovieStatus.RENDERING
    assert movie.branch_id == branch.id


@pytest.mark.asyncio
async def test_generate_reuses_existing_movie_for_branch(db_session: AsyncSession) -> None:
    branch, version, rows = await _full_setup(db_session)
    existing_movie = await MovieRepository(db_session).create(
        branch_id=branch.id, title="Universe: Rescue", status=MovieStatus.STORYBOARDING
    )
    await db_session.commit()

    rendered = [_render_result_for(row) for row in rows]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.movie_id == existing_movie.id
    movie = await MovieRepository(db_session).get_or_404(existing_movie.id)
    assert movie.status == MovieStatus.RENDERING


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_version(db_session: AsyncSession) -> None:
    service = VideoGenerationService(db_session)
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

    service = VideoGenerationService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(not_a_storyboard.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_no_shot_prompts_found(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id)

    service = VideoGenerationService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_marks_job_failed(
    db_session: AsyncSession,
) -> None:
    branch, version, rows = await _full_setup(db_session)
    service = _service_with_mocked_agent(db_session, ConflictError("boom"))

    with pytest.raises(ConflictError):
        await service.generate(version.id)

    jobs, _ = await JobRepository(db_session).list_paginated(
        cursor=None, limit=10, branch_id=branch.id
    )
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.FAILED
    assert jobs[0].error_message == "boom"
