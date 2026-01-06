"""Global exception handlers for FastAPI application."""

import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.base import AppError

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    Handle all custom application exceptions.
    Converts them to standardized JSON responses.
    """
    logger.error(
        "AppError: %s",
        exc.message,
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "message": exc.message,
                "type": exc.__class__.__name__,
                "details": exc.details,
            },
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    """
    logger.warning("Validation error on %s", request.url.path, extra={"errors": exc.errors()})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "message": "Validation error",
                "type": "ValidationError",
                "details": exc.errors(),
            },
        },
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handle database errors.
    """
    logger.error("Database error:  %s", str(exc), extra={"path": request.url.path}, exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "message": "A database error occurred",
                "type": "DatabaseError",
                "details": {},
            },
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.
    """
    logger.error(
        "Unexpected error:  %s",
        str(exc),
        extra={"path": request.url.path},
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "message": "An unexpected error occurred",
                "type": "InternalServerError",
                "details": {},
            },
        },
    )
