from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AgentOutputInvalidError, NotFoundError
from app.db.models.enums import StoryStatus
from app.db.models.story import Story
from app.repositories.story_repository import StoryRepository
from app.services.character_architect_service import CharacterArchitectService
from tests.factories import make_character_agent_run_result, make_story_bible


async def _create_story(session: AsyncSession, **overrides: object) -> Story:
    bible = make_story_bible()
    repo = StoryRepository(session)
    defaults: dict[str, object] = {
        "project_id": None,
        "premise": "A scientist discovers time travel.",
        "genre": bible.genre,
        "tone": bible.tone,
        "status": StoryStatus.COMPLETED,
        "world_bible": bible.model_dump(mode="json"),
        "generation_metadata": {},
    }
    defaults.update(overrides)
    story = await repo.create(**defaults)
    await session.commit()
    return story


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object):
    service = CharacterArchitectService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "character_architect"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_persists_characters_with_full_profile_and_metadata(
    db_session: AsyncSession,
) -> None:
    story = await _create_story(db_session)
    service = _service_with_mocked_agent(db_session, make_character_agent_run_result())

    response = await service.generate(story.id)

    assert response.story_id == story.id
    assert len(response.characters) == 1
    assert response.characters[0].name == "Hero"
    assert response.characters[0].role == "protagonist"
    assert response.model == "qwen-plus"
    assert response.prompt_version == "v1"

    fetched = await service.get(response.characters[0].id)
    assert fetched.name == "Hero"
    assert fetched.story_id == story.id


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_story(db_session: AsyncSession) -> None:
    service = CharacterArchitectService(db_session)
    with pytest.raises(NotFoundError):
        await service.generate(uuid4())


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(db_session: AsyncSession) -> None:
    story = await _create_story(db_session)
    service = _service_with_mocked_agent(db_session, AgentOutputInvalidError("boom"))

    with pytest.raises(AgentOutputInvalidError):
        await service.generate(story.id)


@pytest.mark.asyncio
async def test_get_missing_character_raises_not_found(db_session: AsyncSession) -> None:
    service = CharacterArchitectService(db_session)
    with pytest.raises(NotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_delete_soft_deletes_character(db_session: AsyncSession) -> None:
    story = await _create_story(db_session)
    service = _service_with_mocked_agent(db_session, make_character_agent_run_result())
    response = await service.generate(story.id)
    character_id = response.characters[0].id

    await service.delete(character_id)

    with pytest.raises(NotFoundError):
        await service.get(character_id)


@pytest.mark.asyncio
async def test_list_filters_by_story_id(db_session: AsyncSession) -> None:
    story_one = await _create_story(db_session)
    story_two = await _create_story(db_session)
    service = _service_with_mocked_agent(db_session, make_character_agent_run_result())

    await service.generate(story_one.id)
    await service.generate(story_two.id)

    page = await service.list(story_id=story_one.id, cursor=None, limit=10)

    assert len(page.items) == 1
    assert page.items[0].story_id == story_one.id
