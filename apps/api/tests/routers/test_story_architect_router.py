from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.factories import make_agent_run_result


@pytest.mark.asyncio
async def test_generate_endpoint_returns_full_story_bible(client: AsyncClient) -> None:
    with patch("app.services.story_architect_service.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_agent_cls.return_value.name = "story_architect"

        response = await client.post(
            "/v1/story/generate",
            json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 10},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["story_bible"]["title"] == "T"
    assert body["model"] == "qwen-plus"
    assert "id" in body


@pytest.mark.asyncio
async def test_generate_endpoint_rejects_invalid_runtime(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/story/generate",
        json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 999},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_endpoint_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(f"/v1/story/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_full_generate_get_list_delete_lifecycle(client: AsyncClient) -> None:
    with patch("app.services.story_architect_service.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_agent_cls.return_value.name = "story_architect"

        create_response = await client.post(
            "/v1/story/generate",
            json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 10},
        )
    story_id = create_response.json()["id"]

    get_response = await client.get(f"/v1/story/{story_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == story_id

    list_response = await client.get("/v1/story")
    assert list_response.status_code == 200
    assert any(item["id"] == story_id for item in list_response.json()["items"])

    delete_response = await client.delete(f"/v1/story/{story_id}")
    assert delete_response.status_code == 204

    after_delete_response = await client.get(f"/v1/story/{story_id}")
    assert after_delete_response.status_code == 404
