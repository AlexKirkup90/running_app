from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import get_settings


def _limiter_enabled() -> bool:
    settings = get_settings()
    if str(settings.app_env).lower() == "test":
        return False
    return bool(settings.rate_limit_enabled)


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_settings().rate_limit_storage_uri,
    enabled=_limiter_enabled(),
    headers_enabled=True,
)


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    retry_after: Optional[str] = None
    if isinstance(exc, RateLimitExceeded):
        retry_after = getattr(exc, "retry_after", None)
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "code": "RATE_LIMITED",
                "message": "Rate limit exceeded",
            }
        },
        headers=headers,
    )
