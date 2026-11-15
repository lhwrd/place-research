"""Global exception handlers for FastAPI application."""

import logging

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
    # Custom validators put the raised exception in ctx; encode it so the response
    # doesn't fail to serialize
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    logger.warning("Validation error on %s", request.url.path, extra={"errors": errors})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "success": False,
            "error": {
                "message": "Validation error",
                "type": "ValidationError",
                "details": errors,
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
