from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.config.settings import Settings
from tests.factories import (
    make_agent_run_result,
    make_character_agent_run_result,
    make_decision_agent_run_result,
    make_music_agent_result,
    make_music_agent_run_result,
    make_music_cue_result,
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


async def _create_storyboard_version_id(client: AsyncClient, branch_id: str) -> str:
    with patch("app.services.storyboard_service.StoryboardAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=make_storyboard_agent_run_result())
        mock_agent_cls.return_value.name = "storyboard"

        response = await client.post("/v1/storyboard/generate", json={"branch_id": branch_id})
    return response.json()["version_id"]


async def _full_setup(client: AsyncClient) -> tuple[str, str]:
    story_id = await _create_story_id(client)
    await _create_characters(client, story_id)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)
    branch_id = await _create_branch_id(client, project_id, story_id, decision_id)
    storyboard_version_id = await _create_storyboard_version_id(client, branch_id)
    return branch_id, storyboard_version_id


@pytest.mark.asyncio
async def test_generate_music_endpoint_returns_one_cue_with_asset(
    client: AsyncClient, tmp_path: Path
) -> None:
    branch_id, storyboard_version_id = await _full_setup(client)

    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=1,
                    audio_bytes=b"fake-audio",
                    audio_url=None,
                    provider="happyhorse",
                )
            ],
            failed_cues=[],
        )
    )
    with (
        patch("app.services.music_service.MusicAgent") as mock_agent_cls,
        patch(
            "app.services.music_service.get_settings",
            return_value=Settings(media_root=str(tmp_path), music_provider="happyhorse"),
        ),
    ):
        mock_agent_cls.return_value.run = AsyncMock(return_value=run_result)
        mock_agent_cls.return_value.name = "music"

        response = await client.post(
            "/v1/assets/generate-music",
            json={"storyboard_version_id": storyboard_version_id},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["branch_id"] == branch_id
    assert body["storyboard_version_id"] == storyboard_version_id
    assert len(body["cues"]) == 1
    assert body["cues"][0]["asset"]["kind"] == "audio"
    assert body["failed_cues"] == []


@pytest.mark.asyncio
async def test_generate_music_endpoint_returns_cue_with_no_asset_when_no_provider(
    client: AsyncClient, tmp_path: Path
) -> None:
    branch_id, storyboard_version_id = await _full_setup(client)

    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=1,
                    audio_bytes=None,
                    audio_url=None,
                    provider=None,
                    attempts=0,
                )
            ],
            failed_cues=[],
        )
    )
    with (
        patch("app.services.music_service.MusicAgent") as mock_agent_cls,
        patch(
            "app.services.music_service.get_settings",
            return_value=Settings(media_root=str(tmp_path), music_provider="none"),
        ),
    ):
        mock_agent_cls.return_value.run = AsyncMock(return_value=run_result)
        mock_agent_cls.return_value.name = "music"

        response = await client.post(
            "/v1/assets/generate-music",
            json={"storyboard_version_id": storyboard_version_id},
        )

    assert response.status_code == 201
    body = response.json()
    assert len(body["cues"]) == 1
    assert body["cues"][0]["asset"] is None
    assert body["cues"][0]["generation_prompt"]


@pytest.mark.asyncio
async def test_generate_music_endpoint_returns_404_for_unknown_version(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/v1/assets/generate-music", json={"storyboard_version_id": str(uuid4())}
    )
    assert response.status_code == 404
