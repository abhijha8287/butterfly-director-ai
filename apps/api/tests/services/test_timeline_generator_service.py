from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.decision_point import DecisionPoint
from app.db.models.enums import StoryStatus
from app.db.models.project import Project
from app.db.models.story import Story
from app.repositories.decision_point_repository import DecisionPointRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.services.timeline_generator_service import TimelineGeneratorService
from tests.factories import (
    make_branch_candidate,
    make_story_bible,
    make_timeline_agent_run_result,
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


async def _create_decision(session: AsyncSession, story_id) -> DecisionPoint:
    decision = await DecisionPointRepository(session).create(
        story_id=story_id,
        beat_index=0,
        description="She must decide whether to shout or stay silent.",
        source_hook="hook",
        branch_candidates=[
            make_branch_candidate(label="Shout").model_dump(mode="json"),
            make_branch_candidate(label="Stay silent").model_dump(mode="json"),
        ],
        generation_metadata={},
    )
    await session.commit()
    return decision


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> TimelineGeneratorService:
    service = TimelineGeneratorService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "timeline_generator"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_creates_timeline_root_and_branches_with_scores(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    decision = await _create_decision(db_session, story.id)
    service = _service_with_mocked_agent(db_session, make_timeline_agent_run_result())

    response = await service.generate(project.id, story.id, decision.id, None)

    assert response.decision_id == decision.id
    assert len(response.branches) == 2
    for branch in response.branches:
        assert branch.depth == 1
        assert branch.parent_branch_id is not None
        assert branch.butterfly_score is not None
        assert branch.probability == 50

    timeline = await service.timeline_repo.get_or_404(response.timeline_id)
    assert timeline.project_id == project.id
    assert timeline.story_id == story.id

    root = await service.timeline_repo.get_root_branch(timeline.id)
    assert root is not None
    assert root.is_canonical is True


@pytest.mark.asyncio
async def test_generate_reuses_existing_timeline_and_root_branch(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    decision = await _create_decision(db_session, story.id)
    service = _service_with_mocked_agent(db_session, make_timeline_agent_run_result())

    first = await service.generate(project.id, story.id, decision.id, None)
    second = await service.generate(project.id, story.id, decision.id, None)

    assert first.timeline_id == second.timeline_id
    # second run's branches share the same parent (the same root) as the first
    first_parents = {b.parent_branch_id for b in first.branches}
    second_parents = {b.parent_branch_id for b in second.branches}
    assert first_parents == second_parents


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_project(db_session: AsyncSession) -> None:
    story = await _create_story(db_session)
    decision = await _create_decision(db_session, story.id)
    service = TimelineGeneratorService(db_session)
    with pytest.raises(NotFoundError):
        await service.generate(uuid4(), story.id, decision.id, None)


@pytest.mark.asyncio
async def test_generate_raises_conflict_for_decision_from_other_story(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    other_story = await _create_story(db_session)
    decision = await _create_decision(db_session, other_story.id)
    service = TimelineGeneratorService(db_session)

    with pytest.raises(ConflictError):
        await service.generate(project.id, story.id, decision.id, None)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    decision = await _create_decision(db_session, story.id)
    service = _service_with_mocked_agent(db_session, ConflictError("boom"))

    with pytest.raises(ConflictError):
        await service.generate(project.id, story.id, decision.id, None)


@pytest.mark.asyncio
async def test_generate_with_explicit_parent_branch(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    decision = await _create_decision(db_session, story.id)
    service = _service_with_mocked_agent(db_session, make_timeline_agent_run_result())

    first = await service.generate(project.id, story.id, decision.id, None)
    parent_id = first.branches[0].id

    second = await service.generate(project.id, story.id, decision.id, parent_id)

    for branch in second.branches:
        assert branch.parent_branch_id == parent_id
        assert branch.depth == 2


@pytest.mark.asyncio
async def test_generate_raises_conflict_for_parent_branch_from_other_timeline(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story_one = await _create_story(db_session)
    story_two = await _create_story(db_session)
    decision_one = await _create_decision(db_session, story_one.id)
    decision_two = await _create_decision(db_session, story_two.id)
    service = _service_with_mocked_agent(db_session, make_timeline_agent_run_result())

    # Seed a branch that belongs to story_two's timeline.
    other_timeline_result = await service.generate(project.id, story_two.id, decision_two.id, None)
    foreign_parent_id = other_timeline_result.branches[0].id

    with pytest.raises(ConflictError):
        await service.generate(project.id, story_one.id, decision_one.id, foreign_parent_id)
