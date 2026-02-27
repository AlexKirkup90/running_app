from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as redis_async

from api.observability import (
    configure_logging,
    monotonic_ms,
    new_request_id,
    request_log_fields,
    reset_request_id,
    set_request_id,
)
from api.ratelimit import limiter, rate_limit_exceeded_handler
from api.routes import router
from core.config import get_settings
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        redis_client = None
        try:
            redis_client = redis_async.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await redis_client.ping()
            FastAPICache.init(RedisBackend(redis_client), prefix=settings.cache_prefix)
            app.state.redis = redis_client
            app.state.cache_backend = "redis"
            logger.info("cache_backend_initialized", extra={"cache_backend": "redis", "redis_url": settings.redis_url})
        except Exception as exc:  # pragma: no cover - depends on runtime infra
            logger.warning("Redis unavailable, using in-memory cache backend: %s", exc)
            FastAPICache.init(InMemoryBackend(), prefix=settings.cache_prefix)
            app.state.redis = None
            app.state.cache_backend = "memory"
            logger.info("cache_backend_initialized", extra={"cache_backend": "memory"})

        try:
            yield
        finally:
            redis_client = getattr(app.state, "redis", None)
            if redis_client is not None:
                await redis_client.aclose()

    app = FastAPI(title="Run Season Command API", version="1.0.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.include_router(router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_and_logging(request: Request, call_next: Callable) -> Response:
        header_name = settings.request_id_header_name or "X-Request-ID"
        request_id = (request.headers.get(header_name) or "").strip() or new_request_id()
        token = set_request_id(request_id)
        started_ms = monotonic_ms()
        client_ip = getattr(request.client, "host", None)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = monotonic_ms() - started_ms
            logger.exception(
                "http_request_error",
                extra=request_log_fields(
                    method=request.method,
                    path=request.url.path,
                    status_code=500,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                ),
            )
            raise
        else:
            response.headers[header_name] = request_id
            duration_ms = monotonic_ms() - started_ms
            logger.info(
                "http_request",
                extra=request_log_fields(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                ),
            )
            return response
        finally:
            reset_request_id(token)

    return app


app = create_app()
