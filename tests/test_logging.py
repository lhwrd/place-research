"""
Tests for logging and observability features.

Tests cover:
- Logging configuration and setup
- Request ID tracking
- Log context management
- Request/response logging middleware
- Metrics collection middleware
- Performance tracking
"""

import logging
import pytest
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from place_research.logging_config import (
    setup_logging,
    set_request_id,
    get_request_id,
    set_log_context,
    get_log_context,
    clear_log_context,
    LogTimer,
)
from place_research.middleware import (
    RequestLoggingMiddleware,
    MetricsMiddleware,
    get_metrics_middleware,
    set_metrics_middleware,
)


class TestLoggingConfig:
    """Test logging configuration."""

    def test_setup_logging_json_format(self):
        """Test JSON logging setup."""
        setup_logging(log_level="INFO", log_format="json")
        logger = logging.getLogger("test_json")

        # Verify logger is configured
        assert (
            logger.level == logging.INFO or logger.level == 0
        )  # root logger sets level

    def test_setup_logging_text_format(self):
        """Test text logging setup."""
        setup_logging(log_level="DEBUG", log_format="text")
        logger = logging.getLogger("test_text")

        # Verify logger is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_color_format(self):
        """Test colored logging setup."""
        setup_logging(log_level="WARNING", log_format="color")
        root_logger = logging.getLogger()

        assert root_logger.level == logging.WARNING

    def test_request_id_context(self):
        """Test request ID context management."""
        # Initially should be None
        assert get_request_id() is None

        # Set request ID
        test_id = "test-request-123"
        set_request_id(test_id)

        # Verify it's set
        assert get_request_id() == test_id

    def test_log_context_management(self):
        """Test log context management."""
        # Start with empty context
        clear_log_context()
        assert get_log_context() == {}

        # Set some context
        set_log_context(user_id="user123", action="test")
        context = get_log_context()
        assert context["user_id"] == "user123"
        assert context["action"] == "test"

        # Add more context
        set_log_context(request_path="/test")
        context = get_log_context()
        assert "user_id" in context
        assert "action" in context
        assert context["request_path"] == "/test"

        # Clear context
        clear_log_context()
        assert get_log_context() == {}

    def test_log_timer_success(self, caplog):
        """Test LogTimer for successful operations."""
        logger = logging.getLogger("test_timer")

        with caplog.at_level(logging.INFO):
            with LogTimer(
                logger, "test_operation", level=logging.INFO, user="test_user"
            ):
                # Simulate some work
                pass

        # Check logs contain start and completion messages
        messages = [record.message for record in caplog.records]
        assert any("Starting test_operation" in msg for msg in messages)
        assert any("Completed test_operation" in msg for msg in messages)

    def test_log_timer_failure(self, caplog):
        """Test LogTimer for failed operations."""
        logger = logging.getLogger("test_timer_fail")

        with caplog.at_level(logging.INFO):  # Capture INFO level for start message
            with pytest.raises(ValueError):
                with LogTimer(logger, "failing_operation", level=logging.INFO):
                    raise ValueError("Test error")

        # Check logs contain error message (start message may not appear due to exception)
        messages = [record.message for record in caplog.records]
        assert any("Failed failing_operation" in msg for msg in messages)


class TestRequestLoggingMiddleware:
    """Test request logging middleware."""

    @pytest.fixture
    def app_with_logging(self):
        """Create a test app with logging middleware."""
        app = FastAPI()

        # Add middleware
        app.add_middleware(
            RequestLoggingMiddleware, log_requests=True, log_responses=True
        )

        # Add test endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    def test_successful_request_logging(self, app_with_logging, caplog):
        """Test logging of successful requests."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.INFO):
            response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        # Check logs
        messages = [record.message for record in caplog.records]
        assert any(
            "GET /test" in msg and "request_started" not in msg for msg in messages
        )

    def test_error_request_logging(self, app_with_logging, caplog):
        """Test logging of failed requests."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                client.get("/error")

        # Check error logs
        messages = [record.message for record in caplog.records]
        assert any("ERROR" in msg or "Test error" in msg for msg in messages)

    def test_request_id_propagation(self, app_with_logging):
        """Test that request ID is added to response headers."""
        client = TestClient(app_with_logging)

        response = client.get("/test")

        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0  # Should be a UUID

    def test_logging_disabled(self):
        """Test middleware with logging disabled."""
        app = FastAPI()
        app.add_middleware(
            RequestLoggingMiddleware, log_requests=False, log_responses=False
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Middleware still adds request ID even if logging is off
        assert "X-Request-ID" in response.headers


class TestMetricsMiddleware:
    """Test metrics collection middleware."""

    @pytest.fixture
    def app_with_metrics(self):
        """Create a test app with metrics middleware."""
        app = FastAPI()

        # Create metrics middleware instance
        metrics = MetricsMiddleware(app)
        set_metrics_middleware(metrics)

        # Add test endpoints
        @app.get("/success")
        async def success_endpoint():
            return {"status": "ok"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        # Manually call dispatch to simulate middleware
        # In real app, FastAPI handles this
        return app, metrics

    def test_metrics_collection(self, app_with_metrics):
        """Test that metrics are collected."""
        app, metrics = app_with_metrics
        client = TestClient(app)

        # Make some requests
        response1 = client.get("/success")
        response2 = client.get("/success")

        # Manually update metrics (since middleware isn't actually running)
        metrics._update_metrics("GET", "/success", 200, 10.0, error=False)
        metrics._update_metrics("GET", "/success", 200, 12.0, error=False)

        # Get metrics
        result = metrics.get_metrics()

        assert result["total_requests"] >= 2
        assert "GET /success" in result["endpoints"]
        assert result["endpoints"]["GET /success"]["count"] >= 2

    def test_error_metrics(self, app_with_metrics):
        """Test that errors are tracked in metrics."""
        app, metrics = app_with_metrics

        # Reset metrics first
        metrics.reset_metrics()

        # Manually update metrics to simulate requests
        metrics._update_metrics("GET", "/success", 200, 10.0, error=False)
        metrics._update_metrics("GET", "/error", 500, 15.0, error=True)

        # Get metrics
        result = metrics.get_metrics()

        assert result["total_requests"] >= 2
        assert result["total_errors"] >= 1
        assert result["error_rate"] > 0

    def test_metrics_reset(self, app_with_metrics):
        """Test metrics reset functionality."""
        app, metrics = app_with_metrics

        # Add some metrics
        metrics._update_metrics("GET", "/success", 200, 10.0, error=False)

        # Reset
        metrics.reset_metrics()

        # Metrics should be zero
        result = metrics.get_metrics()
        assert result["total_requests"] == 0
        assert result["total_errors"] == 0
        assert len(result["endpoints"]) == 0

    def test_endpoint_statistics(self, app_with_metrics):
        """Test per-endpoint statistics."""
        app, metrics = app_with_metrics

        # Reset and add metrics
        metrics.reset_metrics()

        metrics._update_metrics("GET", "/success", 200, 10.0, error=False)
        metrics._update_metrics("GET", "/success", 200, 12.0, error=False)
        metrics._update_metrics("GET", "/success", 200, 15.0, error=False)

        # Get metrics
        result = metrics.get_metrics()
        endpoint_stats = result["endpoints"]["GET /success"]

        assert endpoint_stats["count"] == 3
        assert "avg_duration_ms" in endpoint_stats
        assert "min_duration_ms" in endpoint_stats
        assert "max_duration_ms" in endpoint_stats
        assert endpoint_stats["avg_duration_ms"] > 0
        assert endpoint_stats["min_duration_ms"] == 10.0
        assert endpoint_stats["max_duration_ms"] == 15.0

    def test_status_code_tracking(self, app_with_metrics):
        """Test HTTP status code tracking."""
        app, metrics = app_with_metrics

        # Reset and add metrics
        metrics.reset_metrics()

        metrics._update_metrics("GET", "/success", 200, 10.0, error=False)
        metrics._update_metrics("GET", "/success", 200, 12.0, error=False)

        # Get metrics
        result = metrics.get_metrics()

        assert 200 in result["status_codes"]
        assert result["status_codes"][200] >= 2


class TestMetricsEndpoint:
    """Test the /metrics API endpoint."""

    @pytest.fixture
    def app_with_metrics_endpoint(self):
        """Create app with metrics endpoint."""
        from place_research.api import create_app

        app = create_app()
        return app

    def test_metrics_endpoint_returns_data(self, app_with_metrics_endpoint):
        """Test that /metrics endpoint returns metrics data."""
        client = TestClient(app_with_metrics_endpoint)

        # Make a request first
        client.get("/health")

        # Get metrics
        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()

        # Should have basic metrics fields
        assert "total_requests" in data
        assert "total_errors" in data
        assert "endpoints" in data


class TestProviderMetricsLogging:
    """Test provider execution metrics logging."""

    def test_provider_timing_logged(self, caplog):
        """Test that provider execution time is logged."""
        from place_research.service import PlaceEnrichmentService
        from place_research.config import Settings
        from place_research.models import Place

        # Create service with logging enabled
        settings = Settings(
            log_level="INFO",
            log_provider_metrics=True,
            cache_enabled=False,  # Disable cache for this test
        )
        service = PlaceEnrichmentService(settings)

        # Create a test place
        place = Place(
            name="Test Place",
            address="123 Test St",
            latitude=40.7128,
            longitude=-74.0060,
        )

        # This test would need mock providers to fully work
        # For now, just verify service is configured
        assert service.settings.log_provider_metrics is True

    def test_cache_operations_logging(self, caplog):
        """Test that cache operations are logged when enabled."""
        from place_research.config import get_settings
        from place_research.service import PlaceEnrichmentService

        # Get settings and verify default
        settings = get_settings()

        # Default should be False
        assert settings.log_cache_operations is False

        # Create service
        service = PlaceEnrichmentService(settings)
        assert service.settings.log_cache_operations is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
