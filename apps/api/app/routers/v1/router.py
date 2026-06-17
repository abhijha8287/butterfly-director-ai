from fastapi import APIRouter

from app.routers.v1 import (
    agent_logs,
    assets,
    branches,
    characters,
    health,
    jobs,
    movies,
    projects,
    prompt_history,
    stories,
    timelines,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(stories.router)
api_v1_router.include_router(timelines.router)
api_v1_router.include_router(branches.router)
api_v1_router.include_router(movies.router)
api_v1_router.include_router(characters.router)
api_v1_router.include_router(assets.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(agent_logs.router)
api_v1_router.include_router(prompt_history.router)
