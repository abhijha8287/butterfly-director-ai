"""Standalone demo: runs the full pipeline built so far - Story Architect ->
Character Architect -> Decision Detector -> Timeline Generator -> Character
Memory -> Storyboard -> Prompt Director -> Video Generation -> Voice ->
Music - against the live DashScope API and a real Postgres database, and
prints the extracted music cues and their synthesis outcome.

Usage:
    python -m app.demo.music
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
from app.services.music_service import MusicService
from app.services.prompt_director_service import PromptDirectorService
from app.services.story_architect_service import StoryArchitectService
from app.services.storyboard_service import StoryboardService
from app.services.timeline_generator_service import TimelineGeneratorService
from app.services.video_generation_service import VideoGenerationService
from app.services.voice_service import VoiceService


async def main() -> None:
    async with async_session_factory() as session:
        project = await ProjectRepository(session).create(
            title="Music Demo",
            premise="Demo project created by python -m app.demo.music",
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
        print(f"Storyboard ready with {len(storyboard_response.shots)} shots.\n")

        print("Requesting Prompt Director for that storyboard...\n")
        prompt_response = await PromptDirectorService(session).generate(
            storyboard_response.version_id
        )
        print(f"Generated {len(prompt_response.shot_prompts)} shot prompts.\n")

        print("Requesting Video Generation for those shot prompts...\n")
        video_response = await VideoGenerationService(session).generate(
            storyboard_response.version_id
        )
        print(f"Rendered {len(video_response.rendered)} shot videos.\n")

        print("Requesting Voice for that storyboard...\n")
        voice_response = await VoiceService(session).generate(storyboard_response.version_id)
        print(f"Synthesized {len(voice_response.lines)} dialogue lines.\n")

        print("Requesting Music for that storyboard...\n")
        music_response = await MusicService(session).generate(storyboard_response.version_id)

        print(
            json.dumps(
                {
                    "cues": [
                        {
                            "shots": f"{cue.start_shot_number}-{cue.end_shot_number}",
                            "mood": cue.mood,
                            "tempo_bpm": cue.tempo_bpm,
                            "generation_prompt": cue.generation_prompt,
                            "audio_path": cue.asset.oss_key if cue.asset else None,
                        }
                        for cue in music_response.cues
                    ],
                    "failed": [
                        {
                            "shots": f"{f.start_shot_number}-{f.end_shot_number}",
                            "attempts": f.attempts,
                            "error": f.error,
                        }
                        for f in music_response.failed_cues
                    ],
                },
                indent=2,
            )
        )
        print("\n--- generation metadata ---")
        print(
            f"model={music_response.model} prompt_version={music_response.prompt_version} "
            f"latency_ms={music_response.latency_ms} attempts={music_response.attempts} "
            f"prompt_tokens={music_response.prompt_tokens} "
            f"completion_tokens={music_response.completion_tokens}"
        )


if __name__ == "__main__":
    asyncio.run(main())
