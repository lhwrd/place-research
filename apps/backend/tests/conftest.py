"""Shared pytest fixtures and configuration."""

import asyncio
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

    async def reverse_geocode(self, latitude, longitude):
        """Mock reverse geocode method."""
        return {
            "formatted_address": f"Address at {latitude}, {longitude}",
            "latitude": latitude,
            "longitude": longitude,
            "city": "Mountain View",
            "state": "CA",
            "zip_code": "94043",
            "county": "Santa Clara County",
            "country": "United States",
        }

    async def nearby_search(self, lat, lon, place_type, radius_miles, keyword=None, max_results=20):
        """Mock nearby search method."""
        return [
            {
                "name": f"Test {place_type} 1",
                "place_id": f"test_place_{place_type}_1",
                "vicinity": "123 Test St",
                "latitude": lat + 0.01,
                "longitude": lon + 0.01,
                "rating": 4.5,
                "distance_miles": 0.5,
            },
            {
                "name": f"Test {place_type} 2",
                "place_id": f"test_place_{place_type}_2",
                "vicinity": "456 Test Ave",
                "latitude": lat + 0.02,
                "longitude": lon + 0.02,
                "rating": 4.0,
                "distance_miles": 1.2,
            },
        ]

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

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """Mock distance calculation."""
        return 5.0


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


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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


@pytest.fixture
def mock_google_maps_api(monkeypatch):
    """Mock Google Maps API responses."""

    class MockGoogleMapsAPI:
        async def geocode(self, address, components=None):
            return {
                "formatted_address": "123 Test St, Seattle, WA 98101, USA",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "county": "King County",
                "country": "United States",
                "place_id": "test_place_id",
            }

        async def reverse_geocode(self, latitude, longitude):
            return {
                "formatted_address": "123 Test St, Seattle, WA 98101, USA",
                "latitude": latitude,
                "longitude": longitude,
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
            }

        async def nearby_search(
            self, lat, lon, place_type, radius_miles, keyword=None, max_results=20
        ):
            return [
                {
                    "name": f"Test {place_type}",
                    "place_id": "test_place_1",
                    "vicinity": "123 Test St",
                    "latitude": lat + 0.01,
                    "longitude": lon + 0.01,
                    "rating": 4.5,
                    "distance_miles": 0.5,
                }
            ]

        async def distance_matrix(self, origin, destinations, mode="driving", departure_time=None):
            return [
                {
                    "destination_index": i,
                    "distance_miles": 5.0 + i,
                    "duration_minutes": 10 + i * 2,
                }
                for i in range(len(destinations))
            ]

        async def validate_api_key(self):
            return True

        @staticmethod
        def _calculate_distance(lat1, lon1, lat2, lon2):
            return 5.0

    from app.integrations import google_maps_api

    monkeypatch.setattr(google_maps_api, "GoogleMapsAPI", MockGoogleMapsAPI)
    return MockGoogleMapsAPI()


@pytest.fixture
def disable_rate_limiting(monkeypatch):
    """Disable rate limiting for tests."""
    from app.integrations.base_client import BaseAPIClient

    async def mock_rate_limit(self):
        pass

    monkeypatch.setattr(BaseAPIClient, "_rate_limit", mock_rate_limit)
