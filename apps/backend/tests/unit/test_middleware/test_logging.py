"""Tests for logging middleware."""

import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.middleware.logging import RequestLoggingMiddleware


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    return app


@pytest.fixture
def client(app):
    """Create a test client with middleware."""
    app.add_middleware(RequestLoggingMiddleware)
    return TestClient(app)


@pytest.mark.asyncio
async def test_request_id_generation(app):
    """Test that request ID is generated and added to response headers."""
    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    response = client.get("/test")

    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_successful_request_logging(app, caplog):
    """Test logging for successful requests."""
    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/test")

    assert response.status_code == 200
    assert any(
        "request_started" in record.message or "GET /test" in record.message
        for record in caplog.records
    )
    assert any(
        "request_completed" in record.message or "200" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_error_request_logging(app, caplog):
    """Test logging for failed requests."""
    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError):
            client.get("/error")

    assert any(
        "request_failed" in str(record) or "ERROR" in record.message for record in caplog.records
    )


@pytest.mark.asyncio
async def test_log_requests_disabled(app, caplog):
    """Test that request logging can be disabled."""
    app.add_middleware(RequestLoggingMiddleware, log_requests=False)
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        client.get("/test")

    request_started_logs = [r for r in caplog.records if "request_started" in str(r)]
    assert len(request_started_logs) == 0


@pytest.mark.asyncio
async def test_log_responses_disabled(app, caplog):
    """Test that response logging can be disabled."""
    app.add_middleware(RequestLoggingMiddleware, log_responses=False)
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        client.get("/test")

    request_completed_logs = [r for r in caplog.records if "request_completed" in str(r)]
    assert len(request_completed_logs) == 0


@pytest.mark.asyncio
async def test_performance_timing(app, caplog):
    """Test that request duration is measured and logged."""
    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/test")

    assert response.status_code == 200
    # Check that duration is logged (should contain 'ms')
    assert any("ms" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_log_context_management():
    """Test that log context is set and cleared properly."""
    with (
        patch("app.middleware.logging.set_request_id") as mock_set_id,
        patch("app.middleware.logging.set_log_context") as mock_set_context,
        patch("app.middleware.logging.clear_log_context") as mock_clear,
    ):

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)

        client.get("/test")

        assert mock_set_id.called
        assert mock_set_context.called
        assert mock_clear.called


@pytest.mark.asyncio
async def test_different_status_codes_logging(app, caplog):
    """Test that different status codes use appropriate log levels."""

    @app.get("/warning")
    async def warning_endpoint():
        return Response(status_code=404)

    @app.get("/server_error")
    async def server_error_endpoint():
        return Response(status_code=500)

    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        # Success (INFO)
        client.get("/test")
        # Warning (WARNING)
        client.get("/warning")
        # Error (ERROR)
        client.get("/server_error")

    # Check that we have different log levels
    levels = [record.levelname for record in caplog.records]
    assert "INFO" in levels
    assert "WARNING" in levels
    assert "ERROR" in levels
