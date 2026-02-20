"""FastAPI application factory for Run Season Command REST API.

Launch with: uvicorn api.main:app --reload
OpenAPI docs available at /docs (Swagger UI) and /redoc.
"""

from __future__ import annotations

import logging
from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    """Build and return the FastAPI application with all routes mounted."""
    application = FastAPI(
        title="Run Season Command API",
        version="2.0.0",
        description=(
            "REST API for Run Season Command — a coaching platform for endurance athletes. "
            "Provides endpoints for athletes, check-ins, training logs, plans, events, "
            "interventions, recommendations, and webhook integrations."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)

    # Serve React build with SPA catch-all for client-side routing
    if FRONTEND_DIST.is_dir():
        application.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

        @application.exception_handler(StarletteHTTPException)
        async def spa_fallback(request: Request, exc: StarletteHTTPException):
            if exc.status_code == 404 and not request.url.path.startswith("/api/"):
                return FileResponse(FRONTEND_DIST / "index.html")
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

    return application


app = create_app()
