from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config.settings import Settings
from app.core.security import decode_access_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Optimistically attaches a decoded user id to request.state when auth is enabled.

    Enforcement (rejecting unauthenticated requests) happens per-route via the
    get_current_user_id dependency, not here. When settings.auth_enabled is False
    (the default for this build) this middleware is a no-op pass-through.
    """

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.user_id = None

        if self._settings.auth_enabled:
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                token = authorization.split(" ", 1)[1]
                payload = decode_access_token(self._settings, token)
                if payload is not None and "sub" in payload:
                    request.state.user_id = str(payload["sub"])

        return await call_next(request)
