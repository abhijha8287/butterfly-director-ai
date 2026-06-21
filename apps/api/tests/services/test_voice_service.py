from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.branch import Branch
from app.db.models.character import Character
from app.db.models.enums import (
    BranchStatus,
    DriftSeverity,
    PromptProvider,
    StoryStatus,
    TimelineStatus,
    VersionEntityType,
)
from app.db.models.project import Project
from app.db.models.story import Story
from app.db.models.timeline import Timeline
from app.db.models.version import Version
from app.repositories.branch_repository import BranchRepository
from app.repositories.character_branch_state_repository import CharacterBranchStateRepository
from app.repositories.character_repository import CharacterRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.prompt_history_repository import PromptHistoryRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.repositories.version_repository import VersionRepository
from app.services.voice_service import VoiceService
from tests.factories import (
    make_story_bible,
    make_voice_agent_result,
    make_voice_agent_run_result,
    make_voice_line_failure,
    make_voice_line_result,
)

_SHOTS_SNAPSHOT = {
    "shots": [
        {
            "scene": "INT. ALLEY - NIGHT",
            "shot_number": 1,
            "description": "She screams. Footsteps approach.",
            "camera": "low-angle tracking shot",
            "duration_seconds": 4.5,
            "characters_present": ["Hero"],
        },
        {
            "scene": "EXT. ROOFTOP - NIGHT",
            "shot_number": 2,
            "description": "She climbs over the ledge.",
            "camera": "wide shot",
            "duration_seconds": 5.0,
            "characters_present": [],
        },
    ]
}


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


async def _create_timeline(session: AsyncSession, project_id, story_id) -> Timeline:
    timeline = await TimelineRepository(session).create(
        project_id=project_id, story_id=story_id, title="Test Timeline", status=TimelineStatus.ACTIVE
    )
    await session.commit()
    return timeline


async def _create_character(session: AsyncSession, story_id, name: str) -> Character:
    character = await CharacterRepository(session).create(
        story_id=story_id,
        name=name,
        canonical_traits={"personality_traits": ["determined"], "dialogue_style": "Clipped."},
        voice_profile={
            "descriptor": "low warm voice", "tone": "calm", "pace": "measured", "pitch": "low"
        },
        generation_metadata={},
    )
    await session.commit()
    return character


async def _create_branch(session: AsyncSession, timeline_id) -> Branch:
    branch = await BranchRepository(session).create(
        timeline_id=timeline_id,
        parent_branch_id=None,
        name="Universe: Rescue",
        summary="She shouts and is rescued.",
        depth=0,
        status=BranchStatus.PENDING,
        is_canonical=True,
    )
    await session.commit()
    return branch


async def _create_storyboard_version(
    session: AsyncSession, branch_id, snapshot: dict | None = None
) -> Version:
    version = await VersionRepository(session).create(
        entity_type=VersionEntityType.STORYBOARD,
        entity_id=branch_id,
        version_number=1,
        snapshot=snapshot if snapshot is not None else _SHOTS_SNAPSHOT,
        created_by=None,
    )
    await session.commit()
    return version


async def _full_setup(session: AsyncSession) -> tuple[Branch, Version]:
    project = await _create_project(session)
    story = await _create_story(session)
    timeline = await _create_timeline(session, project.id, story.id)
    branch = await _create_branch(session, timeline.id)
    version = await _create_storyboard_version(session, branch.id)
    return branch, version


def _service_with_mocked_agent(session: AsyncSession, run_result_or_error: object) -> VoiceService:
    service = VoiceService(session)
    mock_agent = AsyncMock()
    if isinstance(run_result_or_error, Exception):
        mock_agent.run.side_effect = run_result_or_error
    else:
        mock_agent.run.return_value = run_result_or_error
    mock_agent.name = "voice"
    service.agent = mock_agent
    return service


@pytest.fixture
def _media_root(tmp_path: Path):
    with patch(
        "app.services.voice_service.get_settings",
        return_value=Settings(media_root=str(tmp_path)),
    ):
        yield tmp_path


@pytest.mark.asyncio
async def test_generate_uses_existing_character_branch_state_when_present(
    db_session: AsyncSession, _media_root: Path
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    character = await _create_character(db_session, story.id, "Hero")
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id)

    await CharacterBranchStateRepository(db_session).create(
        character_id=character.id,
        branch_id=branch.id,
        state_diff={
            "knowledge_state": "Knows the truth.",
            "emotional_state": "Furious.",
            "relationship_changes": [],
            "goal_shift": "unchanged",
            "physical_state": "Bruised left arm.",
        },
        drift_severity=DriftSeverity.NONE,
        drift_warning=None,
        generation_metadata={},
    )
    await db_session.commit()

    service = _service_with_mocked_agent(db_session, make_voice_agent_run_result())
    await service.generate(version.id)

    sent_request = service.agent.run.call_args.args[0]
    hero_profile = next(c for c in sent_request.characters if c.name == "Hero")
    assert hero_profile.emotional_state == "Furious."


@pytest.mark.asyncio
async def test_generate_creates_one_asset_per_line(
    db_session: AsyncSession, _media_root: Path
) -> None:
    branch, version = await _full_setup(db_session)
    run_result = make_voice_agent_run_result(
        output=make_voice_agent_result(
            lines=[
                make_voice_line_result(shot_number=1, character_name="Hero"),
                make_voice_line_result(shot_number=1, character_name="Hero", line_text="Wait."),
            ],
            failed_lines=[],
        )
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert response.branch_id == branch.id
    assert response.storyboard_version_id == version.id
    assert len(response.lines) == 2
    assert response.failed_lines == []
    for item in response.lines:
        assert item.asset.kind == "audio"
        assert Path(item.asset.oss_key).exists()


@pytest.mark.asyncio
async def test_generate_writes_real_audio_bytes_to_media_root(
    db_session: AsyncSession, _media_root: Path
) -> None:
    branch, version = await _full_setup(db_session)
    line = make_voice_line_result(
        shot_number=1, character_name="Hero", audio_bytes=b"hello-world-audio"
    )
    run_result = make_voice_agent_run_result(
        output=make_voice_agent_result(lines=[line], failed_lines=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    asset = response.lines[0].asset
    written = Path(asset.oss_key).read_bytes()
    assert written == b"hello-world-audio"
    assert asset.size_bytes == len(b"hello-world-audio")
    assert asset.checksum_sha256 is not None


@pytest.mark.asyncio
async def test_generate_writes_outcome_back_to_prompt_history(
    db_session: AsyncSession, _media_root: Path
) -> None:
    branch, version = await _full_setup(db_session)
    rendered = make_voice_line_result(shot_number=1, character_name="Hero")
    failed = make_voice_line_failure(shot_number=2, character_name="Hero")
    run_result = make_voice_agent_run_result(
        output=make_voice_agent_result(lines=[rendered], failed_lines=[failed])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    response = await service.generate(version.id)

    assert len(response.lines) == 1
    assert len(response.failed_lines) == 1
    assert response.failed_lines[0].error == failed.error


@pytest.mark.asyncio
async def test_generate_persists_prompt_history_rows_with_voice_provider(
    db_session: AsyncSession, _media_root: Path
) -> None:
    branch, version = await _full_setup(db_session)
    rendered = make_voice_line_result(shot_number=1, character_name="Hero")
    run_result = make_voice_agent_run_result(
        output=make_voice_agent_result(lines=[rendered], failed_lines=[])
    )
    service = _service_with_mocked_agent(db_session, run_result)

    await service.generate(version.id)

    rows, _ = await PromptHistoryRepository(db_session).list_paginated(
        cursor=None, limit=10, branch_id=branch.id
    )
    assert len(rows) == 1
    assert rows[0].provider == PromptProvider.DASHSCOPE
    assert rows[0].response_payload["asset_id"]


@pytest.mark.asyncio
async def test_generate_raises_not_found_for_unknown_version(db_session: AsyncSession) -> None:
    service = VoiceService(db_session)
    with pytest.raises(NotFoundError):
        await service.generate(uuid4())


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_version_is_not_storyboard(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    not_a_storyboard = await VersionRepository(db_session).create(
        entity_type=VersionEntityType.BRANCH,
        entity_id=branch.id,
        version_number=1,
        snapshot={"some": "thing"},
        created_by=None,
    )
    await db_session.commit()

    service = VoiceService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(not_a_storyboard.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_timeline_has_no_story(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    timeline = await TimelineRepository(db_session).create(
        project_id=project.id, story_id=None, title="No Story Timeline", status=TimelineStatus.ACTIVE
    )
    await db_session.commit()
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id)

    service = VoiceService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_raises_conflict_when_storyboard_has_no_shots(
    db_session: AsyncSession,
) -> None:
    project = await _create_project(db_session)
    story = await _create_story(db_session)
    timeline = await _create_timeline(db_session, project.id, story.id)
    branch = await _create_branch(db_session, timeline.id)
    version = await _create_storyboard_version(db_session, branch.id, snapshot={"shots": []})

    service = VoiceService(db_session)
    with pytest.raises(ConflictError):
        await service.generate(version.id)


@pytest.mark.asyncio
async def test_generate_propagates_agent_failure_and_logs_it(
    db_session: AsyncSession, _media_root: Path
) -> None:
    branch, version = await _full_setup(db_session)
    service = _service_with_mocked_agent(db_session, ConflictError("boom"))

    with pytest.raises(ConflictError):
        await service.generate(version.id)
