"""FastAPI application for place-research.

This module provides a REST API for enriching places with data from multiple providers.
It serves as the API-first interface to the place enrichment service.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..exceptions import PlaceResearchError
from ..logging_config import setup_logging
from ..middleware import (
    MetricsMiddleware,
    RequestLoggingMiddleware,
    create_metrics_registry,
)
from ..validation import sanitize_error_message


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    settings = get_settings()

    # Configure logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        app_name="place-research",
    )

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
    application = FastAPI(
        title="Place Research API",
        description="API for enriching places with data from multiple providers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Get settings for middleware configuration
    settings = get_settings()

    # Add middleware (order matters - last added = first executed)

    # Metrics middleware (innermost - closest to route handlers)
    # Create registry and metrics middleware
    metrics_registry = create_metrics_registry()
    metrics_middleware = MetricsMiddleware(application)

    # Register the middleware
    metrics_registry.register(metrics_middleware)

    # Add middleware to app
    application.add_middleware(MetricsMiddleware)

    # Store registry in app state for dependency injection
    application.state.metrics_registry = metrics_registry

    # Request logging middleware
    application.add_middleware(
        RequestLoggingMiddleware,
        log_requests=settings.log_requests,
        log_responses=settings.log_responses,
    )

    # CORS middleware for frontend access (outermost)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @application.exception_handler(PlaceResearchError)
    async def place_research_error_handler(_request: Request, exc: PlaceResearchError):
        """Handle custom PlaceResearchError exceptions."""
        logger = logging.getLogger(__name__)
        logger.warning(
            "PlaceResearchError: %s", exc.message, extra={"error_code": exc.error_code}
        )

        # Determine HTTP status code based on error type
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if exc.error_code.startswith("VALIDATION"):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif exc.error_code in ["PLACE_NOT_FOUND", "CONFIGURATION_ERROR"]:
            status_code = status.HTTP_404_NOT_FOUND
        elif exc.error_code == "RATE_LIMIT_EXCEEDED":
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif exc.error_code.startswith("PROVIDER"):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(status_code=status_code, content=exc.to_dict())

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        logger = logging.getLogger(__name__)
        logger.warning("Validation error: %s", exc.errors())

        # Format Pydantic errors into our standard format
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append(
                {"field": field, "message": error["msg"], "type": error["type"]}
            )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
            },
        )

    @application.exception_handler(Exception)
    async def general_exception_handler(_request: Request, exc: Exception):
        """Handle all uncaught exceptions."""
        logger = logging.getLogger(__name__)
        logger.error("Unhandled exception: %s", exc, exc_info=True)

        # Sanitize error message to avoid leaking sensitive info
        safe_message = sanitize_error_message(str(exc))

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"type": type(exc).__name__, "message": safe_message},
            },
        )

    # Import and include routers
    # pylint: disable=import-outside-toplevel
    from .auth_routes import (
        router as auth_router,
    )
    from .routes import router  # pylint: disable=import-outside-toplevel

    application.include_router(router)
    application.include_router(auth_router)

    return application


# Create app instance
app = create_app()
