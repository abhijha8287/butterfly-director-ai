from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.db.base import async_session_factory
from app.integrations.redis_client import get_redis_client


def get_settings_dep() -> Settings:
    return get_settings()


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_redis() -> Redis:
    return get_redis_client()


async def get_current_user_id(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if not settings.auth_enabled:
        return None

    if authorization is None or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(settings, token)
    if payload is None or "sub" not in payload:
        raise UnauthorizedError("Invalid or expired token")

    return str(payload["sub"])


class PaginationParams:
    def __init__(
        self,
        cursor: Annotated[str | None, Query()] = None,
        limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    ) -> None:
        self.cursor = cursor
        self.limit = limit

    def resolved_limit(self, settings: Settings) -> int:
        if self.limit is None:
            return settings.default_page_size
        return min(self.limit, settings.max_page_size)


def get_pagination(
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> PaginationParams:
    return PaginationParams(cursor=cursor, limit=limit)
