import pytest
from app.middleware.metrics import MetricsMiddleware, MetricsRegistry


@pytest.fixture
def middleware():
    """Create a MetricsMiddleware instance for testing."""
    registry = MetricsRegistry()
    return MetricsMiddleware(app=None, registry=registry)


def test_reset_metrics_clears_request_count(middleware):
    """Test that reset_metrics clears request count."""
    middleware.request_count = 100
    middleware.reset_metrics()
    assert middleware.request_count == 0


def test_reset_metrics_clears_error_count(middleware):
    """Test that reset_metrics clears error count."""
    middleware.error_count = 50
    middleware.reset_metrics()
    assert middleware.error_count == 0


def test_reset_metrics_clears_total_duration(middleware):
    """Test that reset_metrics clears total duration."""
    middleware.total_duration = 1234.56
    middleware.reset_metrics()
    assert middleware.total_duration == 0.0


def test_reset_metrics_clears_status_codes(middleware):
    """Test that reset_metrics clears status codes dictionary."""
    middleware.status_codes = {200: 50, 404: 10, 500: 5}
    middleware.reset_metrics()
    assert middleware.status_codes == {}


def test_reset_metrics_clears_endpoint_metrics(middleware):
    """Test that reset_metrics clears endpoint metrics dictionary."""
    middleware.endpoint_metrics = {
        "GET /api/test": {
            "count": 10,
            "total_duration": 100.0,
            "min_duration": 5.0,
            "max_duration": 20.0,
            "errors": 0,
        }
    }
    middleware.reset_metrics()
    assert middleware.endpoint_metrics == {}


def test_reset_metrics_clears_all_fields(middleware):
    """Test that reset_metrics clears all metrics fields at once."""
    middleware.request_count = 100
    middleware.error_count = 25
    middleware.total_duration = 5000.0
    middleware.status_codes = {200: 75, 500: 25}
    middleware.endpoint_metrics = {"GET /test": {"count": 100}}

    middleware.reset_metrics()

    assert middleware.request_count == 0
    assert middleware.error_count == 0
    assert middleware.total_duration == 0.0
    assert middleware.status_codes == {}
    assert middleware.endpoint_metrics == {}


def test_reset_metrics_on_empty_middleware(middleware):
    """Test that reset_metrics works on already empty middleware."""
    middleware.reset_metrics()

    assert middleware.request_count == 0
    assert middleware.error_count == 0
    assert middleware.total_duration == 0.0
    assert middleware.status_codes == {}
    assert middleware.endpoint_metrics == {}
