"""Main FastAPI application."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

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
from app.services.baserow_enrichment import get_baserow_service

# Initialize logging
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    app_name=settings.app_name,
)

logger = logging.getLogger(__name__)


async def _sweep_forever(interval_seconds: int) -> None:
    """Periodically enrich rows whose webhook was missed (e.g. backend was down)."""
    service = get_baserow_service()
    while True:
        try:
            await service.sweep()
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Baserow sweep failed: %s", e, exc_info=True)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    - Startup: start the Baserow sweep loop (runs once immediately, then on an interval)
    - Shutdown: stop it
    """
    sweep_task = None
    if settings.baserow_configured and not settings.testing:
        sweep_task = asyncio.create_task(_sweep_forever(settings.baserow_sweep_interval_seconds))
        logger.info("Baserow sweep started (every %ds)", settings.baserow_sweep_interval_seconds)
    else:
        logger.warning("Baserow is not configured; enrichment sweep disabled")

    yield

    if sweep_task:
        sweep_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweep_task
    logger.info("Application shutdown")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="Enriches Zillow listings stored in Baserow",
    version="2.0.0",
    debug="DEBUG" in str(settings.log_level).upper(),
    lifespan=lifespan,
)

# Logging middleware
app.add_middleware(
    RequestLoggingMiddleware,
    log_requests=settings.log_requests,
    log_responses=settings.log_responses,
)

# Register exception handlers
app.add_exception_handler(AppError, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name, "version": "2.0.0"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "baserow": "configured" if settings.baserow_configured else "not configured",
        "api": "ready",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
