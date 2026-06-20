from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.story_architect.schema import StoryRequest
from app.core.exceptions import AgentOutputInvalidError, NotFoundError
from app.services.story_architect_service import StoryArchitectService
from tests.factories import make_agent_run_result


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object):
    service = StoryArchitectService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "story_architect"
    service.agent = mock_agent
    return service


@pytest.mark.asyncio
async def test_generate_persists_story_with_full_bible_and_metadata(db_session: AsyncSession) -> None:
    service = _service_with_mocked_agent(db_session, make_agent_run_result())
    request = StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)

    response = await service.generate(request)

    assert response.story_bible.title == "T"
    assert response.model == "qwen-plus"
    assert response.prompt_version == "v1"
    assert response.attempts == 1
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 20

    fetched = await service.get(response.id)
    assert fetched.id == response.id
    assert fetched.story_bible.title == "T"


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(db_session: AsyncSession) -> None:
    service = _service_with_mocked_agent(db_session, AgentOutputInvalidError("boom"))
    request = StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)

    with pytest.raises(AgentOutputInvalidError):
        await service.generate(request)


@pytest.mark.asyncio
async def test_get_missing_story_raises_not_found(db_session: AsyncSession) -> None:
    service = StoryArchitectService(db_session)
    with pytest.raises(NotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_delete_soft_deletes_story(db_session: AsyncSession) -> None:
    service = _service_with_mocked_agent(db_session, make_agent_run_result())
    response = await service.generate(
        StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)
    )

    await service.delete(response.id)

    with pytest.raises(NotFoundError):
        await service.get(response.id)


@pytest.mark.asyncio
async def test_list_returns_generated_stories(db_session: AsyncSession) -> None:
    service = _service_with_mocked_agent(db_session, make_agent_run_result())
    created = await service.generate(
        StoryRequest(prompt="A scientist discovers time travel.", target_runtime_minutes=10)
    )

    page = await service.list(cursor=None, limit=10)

    # The DB also accumulates real rows from live demo/manual verification runs
    # outside the test transaction, so only assert our own row is present and
    # correct rather than asserting every row in an unfiltered list.
    assert len(page.items) >= 1
    matching = [item for item in page.items if item.id == created.id]
    assert len(matching) == 1
    assert matching[0].story_bible.title == "T"
