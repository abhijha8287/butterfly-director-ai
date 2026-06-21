"""Standalone demo: runs the full pipeline built so far - Story Architect ->
Character Architect -> Decision Detector -> Timeline Generator -> Character
Memory -> Storyboard - against the live DashScope API and a real Postgres
database, and prints the ordered shot list for the first generated branch.

Usage:
    python -m app.demo.storyboard
"""

from __future__ import annotations

import asyncio
import json

from app.agents.story_architect.schema import StoryRequest
from app.db.base import async_session_factory
from app.repositories.project_repository import ProjectRepository
from app.services.character_architect_service import CharacterArchitectService
from app.services.character_memory_service import CharacterMemoryService
from app.services.decision_detector_service import DecisionDetectorService
from app.services.story_architect_service import StoryArchitectService
from app.services.storyboard_service import StoryboardService
from app.services.timeline_generator_service import TimelineGeneratorService


async def main() -> None:
    async with async_session_factory() as session:
        project = await ProjectRepository(session).create(
            title="Storyboard Demo",
            premise="Demo project created by python -m app.demo.storyboard",
        )
        await session.commit()
        print(f"Created project: {project.id}\n")

        story_request = StoryRequest(
            prompt=(
                "A retired thief is recruited for one last job: steal back a memory "
                "that was stolen from her own mind."
            ),
            target_runtime_minutes=8,
            genre="neo-noir sci-fi",
        )
        print(f"Requesting StoryBible for: {story_request.prompt!r}\n")
        story_response = await StoryArchitectService(session).generate(story_request)
        print(f"StoryBible ready: {story_response.story_bible.title!r}\n")

        print("Requesting CharacterRoster for that StoryBible...\n")
        character_response = await CharacterArchitectService(session).generate(story_response.id)
        print(f"Generated {len(character_response.characters)} characters.\n")

        print("Requesting DecisionList for that StoryBible...\n")
        decision_response = await DecisionDetectorService(session).generate(story_response.id)

        if not decision_response.decisions:
            print("No decision points were detected - this story is linear. Nothing to branch.")
            return

        decision = decision_response.decisions[0]
        print(
            f"Detected decision at beat_index={decision.beat_index} with "
            f"{len(decision.branch_candidates)} branch candidates.\n"
        )

        print("Requesting Timeline branches for that decision...\n")
        timeline_response = await TimelineGeneratorService(session).generate(
            project_id=project.id,
            story_id=story_response.id,
            decision_id=decision.id,
            parent_branch_id=None,
        )

        branch = timeline_response.branches[0]
        print(f"Resolving Character Memory for branch {branch.name!r} ({branch.id})...\n")
        await CharacterMemoryService(session).generate(branch.id)

        print(f"Requesting Storyboard for branch {branch.name!r}...\n")
        storyboard_response = await StoryboardService(session).generate(branch.id)

        print(
            json.dumps(
                [shot.model_dump(mode="json") for shot in storyboard_response.shots], indent=2
            )
        )
        print("\n--- shot summary ---")
        for shot in storyboard_response.shots:
            chars = ", ".join(shot.characters_present) or "none"
            print(
                f"#{shot.shot_number} {shot.scene} ({shot.duration_seconds}s, camera="
                f"{shot.camera!r}) - characters: {chars}"
            )
        print("\n--- generation metadata ---")
        print(
            f"model={storyboard_response.model} "
            f"prompt_version={storyboard_response.prompt_version} "
            f"latency_ms={storyboard_response.latency_ms} attempts={storyboard_response.attempts} "
            f"prompt_tokens={storyboard_response.prompt_tokens} "
            f"completion_tokens={storyboard_response.completion_tokens}"
        )


if __name__ == "__main__":
    asyncio.run(main())
