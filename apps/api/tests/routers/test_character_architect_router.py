from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.factories import make_agent_run_result, make_character_agent_run_result


async def _create_story_id(client: AsyncClient) -> str:
    with patch("app.services.story_architect_service.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_agent_cls.return_value.name = "story_architect"

        response = await client.post(
            "/v1/story/generate",
            json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 10},
        )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_generate_endpoint_returns_full_roster(client: AsyncClient) -> None:
    story_id = await _create_story_id(client)

    with patch("app.services.character_architect_service.CharacterArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_character_agent_run_result())
        mock_agent_cls.return_value.name = "character_architect"

        response = await client.post("/v1/character/generate", json={"story_id": story_id})

    assert response.status_code == 201
    body = response.json()
    assert body["story_id"] == story_id
    assert body["characters"][0]["name"] == "Hero"
    assert body["model"] == "qwen-plus"


@pytest.mark.asyncio
async def test_generate_endpoint_returns_404_for_unknown_story(client: AsyncClient) -> None:
    response = await client.post("/v1/character/generate", json={"story_id": str(uuid4())})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_endpoint_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(f"/v1/character/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_full_generate_get_list_delete_lifecycle(client: AsyncClient) -> None:
    story_id = await _create_story_id(client)

    with patch("app.services.character_architect_service.CharacterArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_character_agent_run_result())
        mock_agent_cls.return_value.name = "character_architect"

        create_response = await client.post("/v1/character/generate", json={"story_id": story_id})
    character_id = create_response.json()["characters"][0]["id"]

    get_response = await client.get(f"/v1/character/{character_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == character_id

    list_response = await client.get("/v1/character", params={"story_id": story_id})
    assert list_response.status_code == 200
    assert any(item["id"] == character_id for item in list_response.json()["items"])

    delete_response = await client.delete(f"/v1/character/{character_id}")
    assert delete_response.status_code == 204

    after_delete_response = await client.get(f"/v1/character/{character_id}")
    assert after_delete_response.status_code == 404
