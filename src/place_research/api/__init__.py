"""FastAPI application for place-research.

This module provides a REST API for enriching places with data from multiple providers.
It serves as the API-first interface to the place enrichment service.
"""

from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from ..service import PlaceEnrichmentService


# Global service instance
_service: Optional[PlaceEnrichmentService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app.

    Initializes the enrichment service on startup.
    """
    global _service

    # Startup
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting place-research API")

    settings = get_settings()
    _service = PlaceEnrichmentService(settings)

    logger.info(
        "Enrichment service initialized with %d providers", len(_service.providers)
    )

    yield

    # Shutdown
    logger.info("Shutting down place-research API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Place Research API",
        description="API for enriching places with data from multiple providers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routers
    from .routes import router

    app.include_router(router)

    return app


def get_service() -> PlaceEnrichmentService:
    """Get the global enrichment service instance.

    Returns:
        PlaceEnrichmentService instance

    Raises:
        RuntimeError: If service not initialized (app not started)
    """
    if _service is None:
        raise RuntimeError("Service not initialized. Is the app started?")
    return _service


# Create app instance
app = create_app()
