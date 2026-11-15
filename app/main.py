"""Main FastAPI application."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.exceptions.base import AppError
from app.exceptions.handlers import (
    app_exception_handler,
    general_exception_handler,
    validation_exception_handler,
)
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security import SecurityMiddleware
from app.services.property_service import get_property_service
from app.web.routes import router as web_router

# Initialize logging
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    app_name=settings.app_name,
)

logger = logging.getLogger(__name__)


async def _resume_pending() -> None:
    """Finish enrichments interrupted by a restart."""
    try:
        await get_property_service().enrich_pending()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Resuming pending enrichments failed: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the database, then enrich anything left pending in the background."""
    get_property_service()  # creates the database and schema
    resume_task = None
    if not settings.testing:
        resume_task = asyncio.create_task(_resume_pending())

    yield

    if resume_task and not resume_task.done():
        resume_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await resume_task
    logger.info("Application shutdown")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="Collects and enriches homes you are considering",
    version="2.0.0",
    debug="DEBUG" in str(settings.log_level).upper(),
    lifespan=lifespan,
)

# Block cross-site form posts to the login-free UI; add security headers
app.add_middleware(SecurityMiddleware)

# Logging middleware (added last, so it runs first and logs blocked requests too)
app.add_middleware(
    RequestLoggingMiddleware,
    log_requests=settings.log_requests,
    log_responses=settings.log_responses,
)

# Register exception handlers
app.add_exception_handler(AppError, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# iOS Shortcut API
app.include_router(api_router, prefix="/api/v1")

# Web UI
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "web" / "static"), name="static")
app.include_router(web_router)


@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check."""
    return {"status": "healthy", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
