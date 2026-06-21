from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.character import Character
from app.db.models.enums import BranchStatus, StoryStatus, TimelineStatus
from app.db.models.project import Project
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.services.character_memory_service import CharacterMemoryService
from tests.factories import (
    make_character_memory_agent_run_result,
    make_character_memory_result,
    make_character_state_diff,
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


async def _create_character(session: AsyncSession, story_id, name: str, **trait_overrides) -> Character:
    traits = {
        "role": "protagonist",
        "personality_traits": ["determined"],
        "motivation": "To find the truth.",
        "internal_conflict": "Fear of repeating the past.",
        "external_conflict": "Hunted by old allies.",
        "defining_strengths": ["resourceful"],
        "defining_flaws": ["stubborn"],
        "dialogue_style": "Short, clipped sentences.",
    }
    traits.update(trait_overrides)
    character = await CharacterRepository(session).create(
        story_id=story_id,
        name=name,
        canonical_traits=traits,
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


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> CharacterMemoryService:
    service = CharacterMemoryService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "character_memory"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_creates_one_state_per_character(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    await _create_character(db_session, story.id, "Sidekick")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    run_result = make_character_memory_agent_run_result(
        output=make_character_memory_result(
            character_states=[
                make_character_state_diff(character_name="Hero"),
                make_character_state_diff(character_name="Sidekick"),
            ]
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(branch.id)

    assert response.branch_id == branch.id
    assert response.story_id == story.id
    assert {s.character_name for s in response.states} == {"Hero", "Sidekick"}
    for state in response.states:
        assert state.drift_severity == "none"


@pytest.mark.asyncio
async def test_generate_reruns_update_existing_state_instead_of_duplicating(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    first_run = make_character_memory_agent_run_result(
        output=make_character_memory_result(
            character_states=[
                make_character_state_diff(character_name="Hero", emotional_state="Relieved.")
            ]
        )
    )
    service = _service_with_mocked_agent(db_session, first_run)
    first = await service.generate(branch.id)

    second_run = make_character_memory_agent_run_result(
        output=make_character_memory_result(
            character_states=[
                make_character_state_diff(character_name="Hero", emotional_state="Terrified.")
            ]
        )
    )
    service.agent.run.return_value = second_run
    second = await service.generate(branch.id)

    assert first.states[0].id == second.states[0].id
    assert second.states[0].state_diff["emotional_state"] == "Terrified."


@pytest.mark.asyncio
async def test_generate_returns_empty_when_story_has_no_characters(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_character_memory_agent_run_result())
    response = await service.generate(branch.id)

    assert response.states == []
    assert response.attempts == 0
    service.agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_branch(db_session: AsyncSession) -> None:
    service = CharacterMemoryService(db_session)
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

    service = CharacterMemoryService(db_session)
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
async def test_generate_persists_drift_warning_when_severity_is_major(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(
        db_session, timeline.id, decision_summary={"affected_characters": ["Hero"]}
    )

    run_result = make_character_memory_agent_run_result(
        output=make_character_memory_result(
            character_states=[
                make_character_state_diff(
                    character_name="Hero",
                    drift_severity="major",
                    drift_warning="Acts like a coward, contradicting defining_strengths.",
                )
            ]
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(branch.id)

    assert response.states[0].drift_severity == "major"
    assert response.states[0].drift_warning == "Acts like a coward, contradicting defining_strengths."


@pytest.mark.asyncio
async def test_get_returns_state_with_character_name(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_character_memory_agent_run_result())
    created = await service.generate(branch.id)

    state = await service.get(created.states[0].id)

    assert state.character_name == "Hero"
    assert state.id == created.states[0].id


@pytest.mark.asyncio
async def test_get_raises_not_found_for_unknown_state(db_session: AsyncSession) -> None:
    service = CharacterMemoryService(db_session)
    with pytest.raises(NotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_list_filters_by_branch_and_character_id(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    await _create_character(db_session, story.id, "Sidekick")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    run_result = make_character_memory_agent_run_result(
        output=make_character_memory_result(
            character_states=[
                make_character_state_diff(character_name="Hero"),
                make_character_state_diff(character_name="Sidekick"),
            ]
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)
    created = await service.generate(branch.id)
    hero_state = next(s for s in created.states if s.character_name == "Hero")

    by_branch = await service.list(branch.id, None, None, 10)
    assert {s.character_name for s in by_branch.items} == {"Hero", "Sidekick"}

    by_character = await service.list(None, hero_state.character_id, None, 10)
    assert len(by_character.items) == 1
    assert by_character.items[0].character_name == "Hero"


@pytest.mark.asyncio
async def test_delete_soft_deletes_state(db_session: AsyncSession) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)

    service = _service_with_mocked_agent(db_session, make_character_memory_agent_run_result())
    created = await service.generate(branch.id)
    state_id = created.states[0].id

    await service.delete(state_id)

    with pytest.raises(NotFoundError):
        await service.get(state_id)
