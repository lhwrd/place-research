"""FastAPI application for place-research.

This module provides a REST API for enriching places with data from multiple providers.
It serves as the API-first interface to the place enrichment service.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting place-research API")

    yield

    # Shutdown
    logger.info("Shutting down place-research API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The app uses dependency injection for Settings and PlaceEnrichmentService.
    See routes.py for the dependency definitions.

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


# Create app instance
app = create_app()
