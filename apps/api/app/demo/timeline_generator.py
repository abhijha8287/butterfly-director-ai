"""Standalone demo: runs the full pipeline built so far - Story Architect ->
Decision Detector -> Timeline Generator - against the live DashScope API and a
real Postgres database, and prints the resulting branches with the butterfly
scores the existing scoring engine computes from this agent's output.

Unlike the earlier demos, this one needs a database session directly (not just
an agent call in isolation), since Timeline Generator's whole job is creating
persisted Branch rows through the existing, already-tested BranchService.

Usage:
    python -m app.demo.timeline_generator
"""

from __future__ import annotations

import asyncio
import json

from app.agents.story_architect.schema import StoryRequest
from app.db.base import async_session_factory
from app.repositories.project_repository import ProjectRepository
from app.services.decision_detector_service import DecisionDetectorService
from app.services.story_architect_service import StoryArchitectService
from app.services.timeline_generator_service import TimelineGeneratorService


async def main() -> None:
    async with async_session_factory() as session:
        project = await ProjectRepository(session).create(
            title="Timeline Generator Demo",
            premise="Demo project created by python -m app.demo.timeline_generator",
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

        print(json.dumps([b.model_dump(mode="json") for b in timeline_response.branches], indent=2))
        print("\n--- butterfly scores (computed by the existing scoring engine) ---")
        for branch in timeline_response.branches:
            print(
                f"{branch.name}: score={branch.butterfly_score} "
                f"probability={branch.probability} confidence={branch.confidence_score}"
            )
        print("\n--- generation metadata ---")
        print(
            f"model={timeline_response.model} prompt_version={timeline_response.prompt_version} "
            f"latency_ms={timeline_response.latency_ms} attempts={timeline_response.attempts} "
            f"prompt_tokens={timeline_response.prompt_tokens} "
            f"completion_tokens={timeline_response.completion_tokens}"
        )


if __name__ == "__main__":
    asyncio.run(main())
