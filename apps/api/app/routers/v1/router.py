from fastapi import APIRouter

from app.routers.v1 import (
    agent_logs,
    assets,
    branches,
    character_architect,
    character_memory,
    characters,
    decision_detector,
    health,
    jobs,
    movies,
    projects,
    prompt_history,
    stories,
    story_architect,
    storyboard,
    timeline_generator,
    timelines,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(stories.router)
api_v1_router.include_router(story_architect.router)
api_v1_router.include_router(timelines.router)
api_v1_router.include_router(timeline_generator.router)
api_v1_router.include_router(branches.router)
api_v1_router.include_router(movies.router)
api_v1_router.include_router(characters.router)
api_v1_router.include_router(character_architect.router)
api_v1_router.include_router(character_memory.router)
api_v1_router.include_router(decision_detector.router)
api_v1_router.include_router(storyboard.router)
api_v1_router.include_router(assets.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(agent_logs.router)
api_v1_router.include_router(prompt_history.router)
