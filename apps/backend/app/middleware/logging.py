"""
Middleware for logging, request tracking, and performance monitoring.

Provides FastAPI middleware components for:
- Request ID generation and propagation
- Request/response logging
- Performance metrics collection
- Error tracking
"""

import logging
import time
import uuid
from typing import Callable

from apps.backend.app.core.logging_config import clear_log_context, set_log_context, set_request_id
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    def __init__(
        self,
        app: ASGIApp,
        log_requests: bool = True,
        log_responses: bool = True,
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        set_request_id(request_id)

        # Add request ID to response headers
        request.state.request_id = request_id

        # Set initial log context
        set_log_context(
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        # Start timer
        start_time = time.perf_counter()

        # Log incoming request
        if self.log_requests:
            logger.info(
                "%s %s",
                request.method,
                request.url.path,
                extra={
                    "event": "request_started",
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
            )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Update log context with response info
            set_log_context(
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Log response
            if self.log_responses:
                log_level = logging.INFO
                if response.status_code >= 500:
                    log_level = logging.ERROR
                elif response.status_code >= 400:
                    log_level = logging.WARNING

                logger.log(
                    log_level,
                    "%s %s - %s - %.2fms",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                    extra={
                        "event": "request_completed",
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            logger.error(
                "%s %s - ERROR - %.2fms",
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

        finally:
            # Clear context for next request
            clear_log_context()
