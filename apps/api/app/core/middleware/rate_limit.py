from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.constants import RATE_LIMIT_WINDOW_SECONDS
from app.config.logging import get_logger
from app.config.settings import Settings
from app.core.exceptions import error_envelope

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings, redis: Redis) -> None:
        super().__init__(app)
        self._settings = settings
        self._redis = redis

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in ("/v1/health", "/v1/health/ready", "/v1/health/live"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_host}:{request.url.path}"

        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)

        if count > self._settings.rate_limit_per_minute:
            logger.warning("rate_limit_exceeded", client=client_host, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content=error_envelope(
                    "rate_limit_exceeded",
                    "Too many requests, slow down.",
                    {"limit_per_minute": self._settings.rate_limit_per_minute},
                    getattr(request.state, "request_id", None),
                ),
            )

        return await call_next(request)
