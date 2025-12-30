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

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from place_research.logging_config import (
    clear_log_context,
    set_log_context,
    set_request_id,
)

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
                f"{request.method} {request.url.path}",
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
                    f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms",
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
                f"{request.method} {request.url.path} - ERROR - {duration_ms:.2f}ms",
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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting performance metrics."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
        self.total_duration = 0.0
        self.status_codes: dict[int, int] = {}
        self.endpoint_metrics: dict[str, dict] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            # Update metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._update_metrics(
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                error=False,
            )

            return response

        except Exception as e:
            # Update error metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._update_metrics(
                request.method,
                request.url.path,
                500,
                duration_ms,
                error=True,
            )
            raise

    def _update_metrics(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        error: bool,
    ) -> None:
        """Update internal metrics."""
        self.request_count += 1
        self.total_duration += duration_ms

        if error:
            self.error_count += 1

        # Update status code counts
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

        # Update endpoint-specific metrics
        endpoint_key = f"{method} {path}"
        if endpoint_key not in self.endpoint_metrics:
            self.endpoint_metrics[endpoint_key] = {
                "count": 0,
                "total_duration": 0.0,
                "min_duration": float("inf"),
                "max_duration": 0.0,
                "errors": 0,
            }

        metrics = self.endpoint_metrics[endpoint_key]
        metrics["count"] += 1
        metrics["total_duration"] += duration_ms
        metrics["min_duration"] = min(metrics["min_duration"], duration_ms)
        metrics["max_duration"] = max(metrics["max_duration"], duration_ms)
        if error:
            metrics["errors"] += 1

    def get_metrics(self) -> dict:
        """Get current metrics summary."""
        avg_duration = (
            self.total_duration / self.request_count if self.request_count > 0 else 0
        )
        error_rate = (
            self.error_count / self.request_count if self.request_count > 0 else 0
        )

        # Calculate endpoint averages
        endpoint_stats = {}
        for endpoint, metrics in self.endpoint_metrics.items():
            count = metrics["count"]
            endpoint_stats[endpoint] = {
                "count": count,
                "avg_duration_ms": (
                    metrics["total_duration"] / count if count > 0 else 0
                ),
                "min_duration_ms": metrics["min_duration"] if count > 0 else 0,
                "max_duration_ms": metrics["max_duration"],
                "errors": metrics["errors"],
                "error_rate": metrics["errors"] / count if count > 0 else 0,
            }

        return {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": error_rate,
            "avg_duration_ms": avg_duration,
            "status_codes": self.status_codes,
            "endpoints": endpoint_stats,
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.request_count = 0
        self.error_count = 0
        self.total_duration = 0.0
        self.status_codes = {}
        self.endpoint_metrics = {}


# Global metrics instance (singleton)
_metrics_middleware_instance: MetricsMiddleware | None = None


def get_metrics_middleware() -> MetricsMiddleware:
    """Get the global metrics middleware instance."""
    global _metrics_middleware_instance
    if _metrics_middleware_instance is None:
        raise RuntimeError("Metrics middleware not initialized")
    return _metrics_middleware_instance


def set_metrics_middleware(middleware: MetricsMiddleware) -> None:
    """Set the global metrics middleware instance."""
    global _metrics_middleware_instance
    _metrics_middleware_instance = middleware
