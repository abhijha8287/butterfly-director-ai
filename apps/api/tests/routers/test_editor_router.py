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
    make_editor_agent_run_result,
    make_editor_result,
    make_music_agent_result,
    make_music_agent_run_result,
    make_music_cue_result,
    make_prompt_director_agent_run_result,
    make_shot_render_result,
    make_storyboard_agent_run_result,
    make_timeline_agent_run_result,
    make_video_generation_agent_result,
    make_video_generation_agent_run_result,
    make_voice_agent_result,
    make_voice_agent_run_result,
    make_voice_line_result,
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


async def _create_shot_prompts(client: AsyncClient, storyboard_version_id: str) -> None:
    with patch("app.services.prompt_director_service.PromptDirectorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(
            return_value=make_prompt_director_agent_run_result()
        )
        mock_agent_cls.return_value.name = "prompt_director"

        await client.post(
            "/v1/prompt-history/generate",
            json={"storyboard_version_id": storyboard_version_id},
        )


async def _render_shots(client: AsyncClient, branch_id: str, storyboard_version_id: str) -> None:
    list_response = await client.get("/v1/prompt-history", params={"branch_id": branch_id})
    shot_prompts = list_response.json()["items"]
    rendered = [
        make_shot_render_result(
            shot_number=p["input_payload"]["shot"]["shot_number"],
            prompt_history_id=p["id"],
        )
        for p in shot_prompts
    ]
    run_result = make_video_generation_agent_run_result(
        output=make_video_generation_agent_result(rendered=rendered, failed=[])
    )
    with patch("app.services.video_generation_service.VideoGenerationAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=run_result)
        mock_agent_cls.return_value.name = "video_generation"

        await client.post(
            "/v1/assets/render-shots",
            json={"storyboard_version_id": storyboard_version_id},
        )


async def _synthesize_voice(client: AsyncClient, storyboard_version_id: str, tmp_path: Path) -> None:
    run_result = make_voice_agent_run_result(
        output=make_voice_agent_result(
            lines=[make_voice_line_result(shot_number=1, character_name="Hero")],
            failed_lines=[],
        )
    )
    with (
        patch("app.services.voice_service.VoiceAgent") as mock_agent_cls,
        patch(
            "app.services.voice_service.get_settings",
            return_value=Settings(media_root=str(tmp_path)),
        ),
    ):
        mock_agent_cls.return_value.run = AsyncMock(return_value=run_result)
        mock_agent_cls.return_value.name = "voice"

        await client.post(
            "/v1/assets/synthesize-voice",
            json={"storyboard_version_id": storyboard_version_id},
        )


async def _generate_music(client: AsyncClient, storyboard_version_id: str, tmp_path: Path) -> None:
    run_result = make_music_agent_run_result(
        output=make_music_agent_result(
            cues=[
                make_music_cue_result(
                    start_shot_number=1,
                    end_shot_number=2,
                    audio_bytes=b"fake-music-bytes",
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

        await client.post(
            "/v1/assets/generate-music",
            json={"storyboard_version_id": storyboard_version_id},
        )


async def _full_setup(client: AsyncClient, tmp_path: Path) -> tuple[str, str]:
    story_id = await _create_story_id(client)
    await _create_characters(client, story_id)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)
    branch_id = await _create_branch_id(client, project_id, story_id, decision_id)
    storyboard_version_id = await _create_storyboard_version_id(client, branch_id)
    await _create_shot_prompts(client, storyboard_version_id)
    await _render_shots(client, branch_id, storyboard_version_id)
    await _synthesize_voice(client, storyboard_version_id, tmp_path)
    await _generate_music(client, storyboard_version_id, tmp_path)
    return branch_id, storyboard_version_id


@pytest.mark.asyncio
async def test_assemble_movie_endpoint_returns_final_cut_asset(
    client: AsyncClient, tmp_path: Path
) -> None:
    branch_id, storyboard_version_id = await _full_setup(client, tmp_path)

    output_file = tmp_path / "final.mp4"
    output_file.write_bytes(b"fake-final-cut-bytes")
    run_result = make_editor_agent_run_result(
        output=make_editor_result(output_path=str(output_file), duration_seconds=10.0)
    )
    with patch("app.services.editor_service.EditorAgent") as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=run_result)
        mock_agent_cls.return_value.name = "editor"

        response = await client.post(
            "/v1/assets/assemble-movie",
            json={"storyboard_version_id": storyboard_version_id},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["branch_id"] == branch_id
    assert body["storyboard_version_id"] == storyboard_version_id
    assert body["shot_count"] == 2
    assert body["voice_track_count"] == 1
    assert body["music_track_count"] == 1
    assert body["asset"]["kind"] == "video"

    movie_response = await client.get(f"/v1/movies/by-branch/{branch_id}")
    movie = movie_response.json()
    assert movie["status"] == "completed"
    assert movie["final_asset_id"] == body["asset"]["id"]


@pytest.mark.asyncio
async def test_assemble_movie_endpoint_returns_404_for_unknown_version(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/v1/assets/assemble-movie", json={"storyboard_version_id": str(uuid4())}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_assemble_movie_endpoint_returns_409_when_video_generation_never_ran(
    client: AsyncClient,
) -> None:
    story_id = await _create_story_id(client)
    await _create_characters(client, story_id)
    decision_id = await _create_decision_id(client, story_id)
    project_id = await _create_project_id(client)
    branch_id = await _create_branch_id(client, project_id, story_id, decision_id)
    storyboard_version_id = await _create_storyboard_version_id(client, branch_id)

    response = await client.post(
        "/v1/assets/assemble-movie",
        json={"storyboard_version_id": storyboard_version_id},
    )
    assert response.status_code == 409
