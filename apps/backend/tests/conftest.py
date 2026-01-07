"""Shared pytest fixtures and configuration."""

import asyncio
import os
import pathlib
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing app
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only-not-for-production-use"
os.environ["EMAIL_USERNAME"] = "test@example.com"
os.environ["EMAIL_PASSWORD"] = "test-password"
os.environ["EMAIL_FROM_ADDRESS"] = "noreply@example.com"
os.environ["USE_MOCK_PROPERTY_DATA"] = "true"

from app.core.security import get_password_hash
from app.db.database import Base, get_db
from app.main import app
from app.models.custom_location import CustomLocation
from app.models.property import Property
from app.models.saved_property import SavedProperty
from app.models.user import User
from app.models.user_preference import UserPreference

# Create test database engine
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
TEST_DB_PATH = pathlib.Path("test.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database file after all tests complete."""
    yield
    # This runs after all tests in the session are done
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database for each test.

    This ensures test isolation - each test gets a clean database.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with database session override.
    """

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create default preferences
    preferences = UserPreference(user_id=user.id)
    db.add(preferences)
    db.commit()

    return user


@pytest.fixture
def test_superuser(db: Session) -> User:
    """Create a test superuser."""
    user = User(
        email="admin@example. com",
        hashed_password=get_password_hash("adminpassword123"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    from app.core.security import create_access_token

    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_property(db: Session, test_user: User) -> Property:
    """Create a test property."""
    property_record = Property(
        user_id=test_user.id,
        address="123 Test St",
        city="Seattle",
        state="WA",
        zip_code="98101",
        county="King County",
        latitude=47.6062,
        longitude=-122.3321,
        bedrooms=3,
        bathrooms=2.5,
        square_feet=2100,
        lot_size=5000,
        year_built=2005,
        property_type="Single Family",
        estimated_value=850000,
    )
    db.add(property_record)
    db.commit()
    db.refresh(property_record)
    return property_record


@pytest.fixture
def test_custom_location(db: Session, test_user: User) -> CustomLocation:
    """Create a test custom location."""
    location = CustomLocation(
        user_id=test_user.id,
        name="Mom's House",
        description="Parents' home",
        address="456 Family Ave, Portland, OR 97201",
        city="Portland",
        state="OR",
        zip_code="97201",
        latitude=45.5231,
        longitude=-122.6765,
        location_type="family",
        priority=90,
        is_active=True,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@pytest.fixture
def test_saved_property(db: Session, test_user: User, test_property: Property) -> SavedProperty:
    """Create a test saved property."""
    saved = SavedProperty(
        user_id=test_user.id,
        property_id=test_property.id,
        notes="Great location!",
        rating=5,
        tags="favorite,close-to-work",
        is_favorite=True,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


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
def mock_property_data_api(monkeypatch):
    """Mock Property Data API responses."""
    # Already a mock, but ensure it's used
    from app.integrations import property_data_factory
    from app.integrations.mock_property_data_api import MockPropertyDataAPI

    monkeypatch.setattr(
        property_data_factory, "get_property_data_api", lambda: MockPropertyDataAPI()
    )
    return MockPropertyDataAPI()


@pytest.fixture
def disable_rate_limiting(monkeypatch):
    """Disable rate limiting for tests."""
    from app.integrations.base_client import BaseAPIClient

    async def mock_rate_limit(self):
        pass

    monkeypatch.setattr(BaseAPIClient, "_rate_limit", mock_rate_limit)
