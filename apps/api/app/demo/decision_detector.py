"""Standalone demo: chains the Story Architect into the Decision Detector against
the live DashScope API and prints the validated DecisionList.

Usage:
    python -m app.demo.decision_detector
"""

from __future__ import annotations

import asyncio
import json

from app.agents.decision_detector.agent import DecisionDetectorAgent
from app.agents.decision_detector.schema import DecisionDetectorRequest
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
    print(f"StoryBible ready: {story_bible.title!r}")
    print(f"story_hooks: {story_bible.story_hooks}\n")

    decision_agent = DecisionDetectorAgent()
    decision_request = DecisionDetectorRequest(story_bible=story_bible)

    print("Requesting DecisionList for that StoryBible...\n")
    decision_result = await decision_agent.run(decision_request)

    print(json.dumps(decision_result.output.model_dump(mode="json"), indent=2))
    print("\n--- generation metadata ---")
    print(
        f"model={decision_result.model} prompt_version={decision_result.prompt_version} "
        f"latency_ms={decision_result.latency_ms} attempts={decision_result.attempts} "
        f"prompt_tokens={decision_result.prompt_tokens} "
        f"completion_tokens={decision_result.completion_tokens}"
    )


if __name__ == "__main__":
    asyncio.run(main())
