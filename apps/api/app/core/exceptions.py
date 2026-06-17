class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class RateLimitExceededError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"


class ProviderNotConfiguredError(AppError):
    status_code = 500
    code = "provider_not_configured"


class ProviderUnavailableError(AppError):
    status_code = 503
    code = "provider_unavailable"


class AgentOutputInvalidError(AppError):
    status_code = 502
    code = "agent_output_invalid"


def error_envelope(code: str, message: str, details: dict, request_id: str | None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
