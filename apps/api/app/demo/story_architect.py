"""Standalone demo: calls the live DashScope API and prints a validated StoryBible.

Usage:
    python -m app.demo.story_architect
"""

from __future__ import annotations

import asyncio
import json

from app.agents.story_architect.agent import StoryArchitectAgent
from app.agents.story_architect.schema import StoryRequest


async def main() -> None:
    agent = StoryArchitectAgent()
    request = StoryRequest(
        prompt=(
            "A scientist discovers a way to travel back in time, but every trip "
            "erases one of her own memories."
        ),
        target_runtime_minutes=12,
        genre="sci-fi",
        style="moody, intimate, handheld camera",
    )

    print(f"Requesting StoryBible for: {request.prompt!r}\n")
    result = await agent.run(request)

    print(json.dumps(result.output.model_dump(mode="json"), indent=2))
    print("\n--- generation metadata ---")
    print(
        f"model={result.model} prompt_version={result.prompt_version} "
        f"latency_ms={result.latency_ms} attempts={result.attempts} "
        f"prompt_tokens={result.prompt_tokens} completion_tokens={result.completion_tokens}"
    )


if __name__ == "__main__":
    asyncio.run(main())
