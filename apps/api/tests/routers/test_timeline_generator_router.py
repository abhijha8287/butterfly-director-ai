from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.factories import make_agent_run_result, make_timeline_agent_run_result


async def _create_story_id(client: AsyncClient) -> str:
    with patch("app.services.story_architect_service.StoryArchitectAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_agent_run_result())
        mock_agent_cls.return_value.name = "story_architect"

        response = await client.post(
            "/v1/story/generate",
            json={"prompt": "A scientist discovers time travel.", "target_runtime_minutes": 10},
        )
    return response.json()["id"]


async def _create_decision_id(client: AsyncClient, story_id: str) -> str:
    from unittest.mock import AsyncMock as _AsyncMock

    from tests.factories import make_decision_agent_run_result

    with patch("app.services.decision_detector_service.DecisionDetectorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = _AsyncMock(return_value=make_decision_agent_run_result())
        mock_agent_cls.return_value.name = "decision_detector"

        response = await client.post("/v1/decision/generate", json={"story_id": story_id})
    return response.json()["decisions"][0]["id"]


async def _create_project_id(client: AsyncClient) -> str:
    response = await client.post(
        "/v1/projects", json={"title": "Test Project", "premise": "A test premise."}
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_generate_branches_endpoint_returns_full_response(client: AsyncClient) -> None:
    story_id = await _create_story_id(client)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)

    with patch("app.services.timeline_generator_service.TimelineGeneratorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_timeline_agent_run_result())
        mock_agent_cls.return_value.name = "timeline_generator"

        response = await client.post(
            "/v1/timelines/generate-branches",
            json={"project_id": project_id, "story_id": story_id, "decision_id": decision_id},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["decision_id"] == decision_id
    assert len(body["branches"]) == 2
    assert body["model"] == "qwen-plus"
    for branch in body["branches"]:
        assert branch["butterfly_score"] is not None


@pytest.mark.asyncio
async def test_generate_branches_endpoint_returns_404_for_unknown_project(client: AsyncClient) -> None:
    story_id = await _create_story_id(client)
    decision_id = await _create_decision_id(client, story_id)

    response = await client.post(
        "/v1/timelines/generate-branches",
        json={"project_id": str(uuid4()), "story_id": story_id, "decision_id": decision_id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_branches_endpoint_returns_409_for_decision_from_other_story(
    client: AsyncClient,
) -> None:
    story_id = await _create_story_id(client)
    decision_id = await _create_decision_id(client, story_id)
    other_story_id = await _create_story_id(client)
    project_id = await _create_project_id(client)

    response = await client.post(
        "/v1/timelines/generate-branches",
        json={"project_id": project_id, "story_id": other_story_id, "decision_id": decision_id},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_generated_branches_are_visible_via_existing_branches_endpoint(
    client: AsyncClient,
) -> None:
    story_id = await _create_story_id(client)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)

    with patch("app.services.timeline_generator_service.TimelineGeneratorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_timeline_agent_run_result())
        mock_agent_cls.return_value.name = "timeline_generator"

        create_response = await client.post(
            "/v1/timelines/generate-branches",
            json={"project_id": project_id, "story_id": story_id, "decision_id": decision_id},
        )
    timeline_id = create_response.json()["branches"][0]["timeline_id"]
    branch_id = create_response.json()["branches"][0]["id"]

    get_response = await client.get(f"/v1/branches/{branch_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == branch_id

    list_response = await client.get("/v1/branches", params={"timeline_id": timeline_id})
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 3  # root + 2 generated branches

    tree_response = await client.get(f"/v1/timelines/{timeline_id}/tree")
    assert tree_response.status_code == 200
    assert len(tree_response.json()["branches"]) == 3
