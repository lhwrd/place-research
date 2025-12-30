import time
from typing import Callable, Protocol

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class MetricsProvider(Protocol):
    """Protocol for metrics collection."""

    def get_metrics(self) -> dict:
        """Get current metrics summary."""
        ...

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        ...


class MetricsRegistry:
    """Registry for managing metrics middleware instances."""

    def __init__(self) -> None:
        self._metrics_provider: MetricsProvider | None = None

    def register(self, provider: MetricsProvider) -> None:
        """Register a metrics provider."""
        self._metrics_provider = provider

    def get_provider(self) -> MetricsProvider:
        """Get the registered metrics provider."""
        if self._metrics_provider is None:
            raise RuntimeError("No metrics provider registered")
        return self._metrics_provider

    def is_registered(self) -> bool:
        """Check if a provider is registered."""
        return self._metrics_provider is not None


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
            raise e

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


def create_metrics_registry() -> MetricsRegistry:
    """Factory function to create a metrics registry."""
    return MetricsRegistry()


def get_metrics_middleware(registry: MetricsRegistry) -> MetricsProvider:
    """Get metrics provider from registry."""
    return registry.get_provider()
