"""FastAPI application factory for Run Season Command REST API.

Launch with: uvicorn api.main:app --reload
OpenAPI docs available at /docs (Swagger UI) and /redoc.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

        @application.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str):
            file_path = FRONTEND_DIST / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIST / "index.html")

    return application


app = create_app()
