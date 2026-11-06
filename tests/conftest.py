"""Shared pytest fixtures and configuration."""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Set test environment variables BEFORE importing app. Explicit values win over any
# developer .env, so tests never talk to a real Baserow.
os.environ["TESTING"] = "1"
os.environ["BASEROW_URL"] = "https://baserow.test"
os.environ["BASEROW_API_TOKEN"] = "test-baserow-token"
os.environ["BASEROW_PROPERTIES_TABLE_ID"] = "837"
os.environ["BASEROW_LOCATIONS_TABLE_ID"] = "838"
os.environ["BASEROW_SETTINGS_TABLE_ID"] = "839"
os.environ["BASEROW_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["INGEST_API_TOKEN"] = "test-ingest-token"


# Define mock classes at module level before any imports
class MockGoogleMapsAPI:
    """Mock Google Maps API for testing."""

    async def geocode(self, address, components=None):
        """Mock geocode method."""
        return {
            "formatted_address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
            "latitude": 37.4224764,
            "longitude": -122.0842499,
            "city": "Mountain View",
            "state": "CA",
            "zip_code": "94043",
            "county": "Santa Clara County",
            "country": "United States",
            "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
        }

    async def distance_matrix(self, origin, destinations, mode="driving", departure_time=None):
        """Mock distance matrix method."""
        return [
            {
                "destination_index": i,
                "distance_miles": 5.0 + i,
                "duration_minutes": 10 + i * 2,
            }
            for i in range(len(destinations))
        ]

    async def validate_api_key(self):
        """Mock API key validation."""
        return True


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.

    Applies mocks for external APIs to prevent real API calls during testing.
    This runs very early in the pytest lifecycle, before app modules are imported.
    """
    # Import and patch at the module level immediately
    import app.integrations.google_maps_api as google_maps_module

    # Replace GoogleMapsAPI with our mock
    google_maps_module.GoogleMapsAPI = MockGoogleMapsAPI


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the app."""
    # Lazy import after mocks are set up
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_cache():
    """Each test starts with an empty in-memory cache."""
    from app.services import cache_service

    cache_service._store.clear()
    yield


# Mock external API fixtures
