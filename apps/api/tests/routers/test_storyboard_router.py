from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.factories import (
    make_agent_run_result,
    make_character_agent_run_result,
    make_decision_agent_run_result,
    make_storyboard_agent_run_result,
    make_timeline_agent_run_result,
)


async def _create_story_id(client: AsyncClient) -> str:
    with patch("app.services.story_architect_service.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_agent_cls.return_value.name = "story_architect"

        response = await client.post(
            "/v1/story/generate",
            json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 10},
        )
    return response.json()["id"]


async def _create_characters(client: AsyncClient, story_id: str) -> None:
    with patch("app.services.character_architect_service.CharacterArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_character_agent_run_result())
        mock_agent_cls.return_value.name = "character_architect"

        await client.post("/v1/character/generate", json={"story_id": story_id})


async def _create_decision_id(client: AsyncClient, story_id: str) -> str:
    with patch("app.services.decision_detector_service.DecisionDetectorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_decision_agent_run_result())
        mock_agent_cls.return_value.name = "decision_detector"

        response = await client.post("/v1/decision/generate", json={"story_id": story_id})
    return response.json()["decisions"][0]["id"]


async def _create_project_id(client: AsyncClient) -> str:
    response = await client.post(
        "/v1/projects", json={"title": "Test Project", "premise": "A test premise."}
    )
    return response.json()["id"]


async def _create_branch_id(client: AsyncClient, project_id: str, story_id: str, decision_id: str) -> str:
    with patch("app.services.timeline_generator_service.TimelineGeneratorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_timeline_agent_run_result())
        mock_agent_cls.return_value.name = "timeline_generator"

        response = await client.post(
            "/v1/timelines/generate-branches",
            json={"project_id": project_id, "story_id": story_id, "decision_id": decision_id},
        )
    return response.json()["branches"][0]["id"]


async def _full_branch_setup(client: AsyncClient) -> str:
    story_id = await _create_story_id(client)
    await _create_characters(client, story_id)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)
    return await _create_branch_id(client, project_id, story_id, decision_id)


@pytest.mark.asyncio
async def test_generate_storyboard_endpoint_returns_ordered_shots(client: AsyncClient) -> None:
    branch_id = await _full_branch_setup(client)

    with patch("app.services.storyboard_service.StoryboardAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_storyboard_agent_run_result())
        mock_agent_cls.return_value.name = "storyboard"

        response = await client.post("/v1/storyboard/generate", json={"branch_id": branch_id})

    assert response.status_code == 201
    body = response.json()
    assert body["branch_id"] == branch_id
    assert body["version_number"] == 1
    assert len(body["shots"]) == 2
    assert body["shots"][0]["shot_number"] == 1


@pytest.mark.asyncio
async def test_generate_storyboard_endpoint_returns_404_for_unknown_branch(
    client: AsyncClient,
) -> None:
    response = await client.post("/v1/storyboard/generate", json={"branch_id": str(uuid4())})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generated_storyboards_are_visible_via_list_and_get_endpoints(
    client: AsyncClient,
) -> None:
    branch_id = await _full_branch_setup(client)

    with patch("app.services.storyboard_service.StoryboardAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_storyboard_agent_run_result())
        mock_agent_cls.return_value.name = "storyboard"

        create_response = await client.post("/v1/storyboard/generate", json={"branch_id": branch_id})
    version_id = create_response.json()["version_id"]

    get_response = await client.get(f"/v1/storyboard/{version_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == version_id

    list_response = await client.get("/v1/storyboard", params={"branch_id": branch_id})
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1


@pytest.mark.asyncio
async def test_delete_storyboard_version_returns_204(client: AsyncClient) -> None:
    branch_id = await _full_branch_setup(client)

    with patch("app.services.storyboard_service.StoryboardAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_storyboard_agent_run_result())
        mock_agent_cls.return_value.name = "storyboard"

        create_response = await client.post("/v1/storyboard/generate", json={"branch_id": branch_id})
    version_id = create_response.json()["version_id"]

    delete_response = await client.delete(f"/v1/storyboard/{version_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/v1/storyboard/{version_id}")
    assert get_response.status_code == 404
