"""Standalone demo: chains the Story Architect into the Character Architect against
the live DashScope API and prints the validated CharacterRoster.

Usage:
    python -m app.demo.character_architect
"""

from __future__ import annotations

import asyncio
import json

from app.agents.character_architect.agent import CharacterArchitectAgent
from app.agents.character_architect.schema import CharacterRequest
from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest


async def main() -> None:
    story_agent = StoryArchitectAgent()
    story_request = StoryRequest(
        prompt=(
            "A retired thief is recruited for one last job: steal back a memory "
            "that was stolen from her own mind."
        ),
        target_runtime_minutes=8,
        genre="neo-noir sci-fi",
    )

    print(f"Requesting StoryBible for: {story_request.prompt!r}\n")
    story_result = await story_agent.run(story_request)
    story_bible = story_result.output
    print(f"StoryBible ready: {story_bible.title!r}\n")

    character_agent = CharacterArchitectAgent()
    character_request = CharacterRequest(story_bible=story_bible)

    print("Requesting CharacterRoster for that StoryBible...\n")
    character_result = await character_agent.run(character_request)

    print(json.dumps(character_result.output.model_dump(mode="json"), indent=2))
    print("\n--- generation metadata ---")
    print(
        f"model={character_result.model} prompt_version={character_result.prompt_version} "
        f"latency_ms={character_result.latency_ms} attempts={character_result.attempts} "
        f"prompt_tokens={character_result.prompt_tokens} "
        f"completion_tokens={character_result.completion_tokens}"
    )


if __name__ == "__main__":
    asyncio.run(main())
