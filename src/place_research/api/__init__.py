"""FastAPI application for place-research.

This module provides a REST API for enriching places with data from multiple providers.
It serves as the API-first interface to the place enrichment service.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from ..exceptions import PlaceResearchError
from ..validation import sanitize_error_message


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

    # Exception handlers
    @app.exception_handler(PlaceResearchError)
    async def place_research_error_handler(request: Request, exc: PlaceResearchError):
        """Handle custom PlaceResearchError exceptions."""
        logger = logging.getLogger(__name__)
        logger.warning(
            f"PlaceResearchError: {exc.message}", extra={"error_code": exc.error_code}
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

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        logger = logging.getLogger(__name__)
        logger.warning(f"Validation error: {exc.errors()}")

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

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all uncaught exceptions."""
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

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
    from .routes import router

    app.include_router(router)

    return app


# Create app instance
app = create_app()
