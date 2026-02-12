"""FastAPI application factory for Run Season Command REST API.

Launch with: uvicorn api.main:app --reload
OpenAPI docs available at /docs (Swagger UI) and /redoc.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from api.routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


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
    application.include_router(router)
    return application


app = create_app()
