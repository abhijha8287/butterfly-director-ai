from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config.constants import REQUEST_ID_HEADER
from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.core.middleware.auth import AuthContextMiddleware
from app.core.middleware.error_handler import register_exception_handlers
from app.core.middleware.logging_middleware import LoggingMiddleware
from app.core.middleware.rate_limit import RateLimitMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.db.base import async_engine
from app.integrations.redis_client import close_redis_pool, get_redis_client
from app.routers.v1.router import api_v1_router

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("application_starting", env=settings.env)

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connection_verified")
    except Exception:
        logger.exception("database_connection_failed_at_startup")

    redis_client = get_redis_client()
    try:
        await redis_client.ping()
        logger.info("redis_connection_verified")
    except Exception:
        logger.exception("redis_connection_failed_at_startup")

    yield

    logger.info("application_shutting_down")
    await async_engine.dispose()
    await close_redis_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings, redis=get_redis_client())
    app.add_middleware(AuthContextMiddleware, settings=settings)

    register_exception_handlers(app)

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
