from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.character import Character
from app.db.models.enums import (
    BranchStatus,
    DriftSeverity,
    MovieStatus,
    StoryStatus,
    TimelineStatus,
)
from app.db.models.project import Project
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.services.storyboard_service import StoryboardService
from tests.factories import (
    make_shot,
    make_storyboard_agent_run_result,
    make_storyboard_result,
    make_story_bible,
)


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


async def _create_character(session: AsyncSession, story_id, name: str) -> Character:
    character = await CharacterRepository(session).create(
        story_id=story_id,
        name=name,
        canonical_traits={"role": "protagonist"},
        generation_metadata={},
    )
    await session.commit()
    return character


async def _create_timeline(session: AsyncSession, project_id, story_id) -> Timeline:
    timeline = await TimelineRepository(session).create(
        project_id=project_id, story_id=story_id, title="Test Timeline", status=TimelineStatus.ACTIVE
    )
    await session.commit()
    return timeline


async def _create_branch(
    session: AsyncSession, timeline_id, decision_summary: dict | None = None
) -> Branch:
    branch = await BranchRepository(session).create(
        timeline_id=timeline_id,
        parent_branch_id=None,
        name="Universe: Rescue",
        summary="She shouts and is rescued.",
        depth=0,
        status=BranchStatus.PENDING,
        is_canonical=True,
        decision_summary=decision_summary,
    )
    await session.commit()
    return branch


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> StoryboardService:
    service = StoryboardService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "storyboard"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_creates_storyboard_version_and_movie(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(
        db_session, timeline.id, decision_summary={"delta_script": "INT. ALLEY - NIGHT\n..."}
    )

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    response = await service.generate(branch.id)

    assert response.branch_id == branch.id
    assert response.version_number == 1
    assert len(response.shots) == 2

    movie = await MovieRepository(db_session).get_by_branch_id(branch.id)
    assert movie is not None
    assert movie.status == MovieStatus.STORYBOARDING
    assert movie.extra_metadata["shot_count"] == 2
    assert movie.extra_metadata["last_storyboard_version"] == 1


@pytest.mark.asyncio
async def test_generate_increments_version_number_on_rerun(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    first = await service.generate(branch.id)
    second = await service.generate(branch.id)

    assert first.version_number == 1
    assert second.version_number == 2
    assert first.version_id != second.version_id

    movie = await MovieRepository(db_session).get_by_branch_id(branch.id)
    assert movie.extra_metadata["last_storyboard_version"] == 2


@pytest.mark.asyncio
async def test_generate_uses_existing_character_branch_state_when_present(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    character = await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    await CharacterBranchStateRepository(db_session).create(
        character_id=character.id,
        branch_id=branch.id,
        state_diff={
            "knowledge_state": "Knows the truth.",
            "emotional_state": "Furious.",
            "relationship_changes": [],
            "goal_shift": "unchanged",
            "physical_state": "unchanged",
        },
        drift_severity=DriftSeverity.NONE,
        drift_warning=None,
        generation_metadata={},
    )
    await db_session.commit()

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    await service.generate(branch.id)

    sent_request = service.agent.run.call_args.args[0]
    assert sent_request.characters[0].emotional_state == "Furious."
    assert sent_request.characters[0].knowledge_state == "Knows the truth."


@pytest.mark.asyncio
async def test_generate_falls_back_to_unresolved_state_when_character_memory_has_not_run(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    await service.generate(branch.id)

    sent_request = service.agent.run.call_args.args[0]
    assert sent_request.characters[0].emotional_state == "Not yet resolved for this branch."


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_branch(db_session: AsyncSession) -> None:
    service = StoryboardService(db_session)
    with pytest.raises(NotFoundError):
        await service.generate(uuid4())


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_timeline_has_no_story(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    timeline = await TimelineRepository(db_session).create(
        project_id=project.id, story_id=None, title="No Story Timeline", status=TimelineStatus.ACTIVE
    )
    await db_session.commit()
    branch = await _create_branch(db_session, timeline.id)

    service = StoryboardService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(branch.id)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, ConflictError("boom"))

    with pytest.raises(ConflictError):
        await service.generate(branch.id)


@pytest.mark.asyncio
async def test_get_returns_storyboard_with_shots(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    created = await service.generate(branch.id)

    storyboard = await service.get(created.version_id)

    assert storyboard.branch_id == branch.id
    assert len(storyboard.shots) == 2
    assert storyboard.shots[0].shot_number == 1


@pytest.mark.asyncio
async def test_get_raises_not_found_for_unknown_version(db_session: AsyncSession) -> None:
    service = StoryboardService(db_session)
    with pytest.raises(NotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_list_filters_by_branch_id(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch_one = await _create_branch(db_session, timeline.id)
    branch_two = await BranchRepository(db_session).create(
        timeline_id=timeline.id,
        parent_branch_id=None,
        name="Universe: Stay Silent",
        summary="She says nothing.",
        depth=0,
        status=BranchStatus.PENDING,
        is_canonical=False,
    )
    await db_session.commit()

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    await service.generate(branch_one.id)
    service.agent.run.return_value = make_storyboard_agent_run_result(
        output=make_storyboard_result(shots=[make_shot(shot_number=1)])
    )
    await service.generate(branch_two.id)

    page = await service.list(branch_one.id, None, 10)
    assert len(page.items) == 1
    assert page.items[0].branch_id == branch_one.id


@pytest.mark.asyncio
async def test_delete_soft_deletes_version(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_storyboard_agent_run_result())
    created = await service.generate(branch.id)

    await service.delete(created.version_id)

    with pytest.raises(NotFoundError):
        await service.get(created.version_id)
