"""Tests for JWT-based authentication and authorization.

This module tests user registration, login, token refresh,
and role-based authorization.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from place_research.api import create_app
from place_research.database import get_db, get_engine, init_db
from place_research.db_models import User
from place_research.models.auth import UserRole
from place_research.security import hash_password


@pytest.fixture(scope="function")
def test_db():
    """Create a test database and clean it up after each test."""
    init_db()
    engine = get_engine()

    # Clear all users before the test
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            session.delete(user)
        session.commit()

    yield

    # Clean up after the test
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            session.delete(user)
        session.commit()


@pytest.fixture
def client(test_db):
    """Create a test client."""
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user(test_db):
    """Create a test user in the database."""
    engine = get_engine()
    with Session(engine) as session:
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=hash_password("testpass123"),
            role=UserRole.USER,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture
def admin_user(test_db):
    """Create an admin user in the database."""
    engine = get_engine()
    with Session(engine) as session:
        user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


class TestUserRegistration:
    """Test user registration endpoint."""

    def test_register_user_success(self, client):
        """Test successful user registration."""
        # Clear all users first to ensure this is the first user
        engine = get_engine()
        with Session(engine) as session:
            users = session.exec(select(User)).all()
            for user in users:
                session.delete(user)
            session.commit()

        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
                "role": "user",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        # First user becomes admin
        assert data["role"] == "admin"
        assert data["is_active"] is True
        assert "id" in data

    def test_register_first_user_becomes_admin(self, client):
        """Test that the first user becomes an admin."""
        # Clear all users first
        engine = get_engine()
        with Session(engine) as session:
            users = session.exec(select(User)).all()
            for user in users:
                session.delete(user)
            session.commit()

        response = client.post(
            "/auth/register",
            json={
                "username": "firstuser",
                "email": "first@example.com",
                "password": "firstpass123",
                "role": "user",  # Requested role
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "admin"  # First user becomes admin

    def test_register_duplicate_username(self, client, test_user):
        """Test registration with duplicate username."""
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",  # Already exists
                "email": "different@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "username already exists" in response.json()["detail"]["message"].lower()

    def test_register_duplicate_email(self, client, test_user):
        """Test registration with duplicate email."""
        response = client.post(
            "/auth/register",
            json={
                "username": "differentuser",
                "email": "test@example.com",  # Already exists
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert "email already exists" in response.json()["detail"]["message"].lower()


class TestLogin:
    """Test user login endpoint."""

    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_username(self, client):
        """Test login with invalid username."""
        response = client.post(
            "/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert (
            "incorrect username or password"
            in response.json()["detail"]["message"].lower()
        )

    def test_login_invalid_password(self, client, test_user):
        """Test login with invalid password."""
        response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert (
            "incorrect username or password"
            in response.json()["detail"]["message"].lower()
        )

    def test_login_inactive_user(self, client):
        """Test login with inactive user account."""
        # Create inactive user
        engine = get_engine()
        with Session(engine) as session:
            user = User(
                username="inactive",
                email="inactive@example.com",
                hashed_password=hash_password("password123"),
                role=UserRole.USER,
                is_active=False,
            )
            session.add(user)
            session.commit()

        response = client.post(
            "/auth/login",
            data={
                "username": "inactive",
                "password": "password123",
            },
        )

        assert response.status_code == 403
        assert "disabled" in response.json()["detail"]["message"].lower()


class TestTokenRefresh:
    """Test token refresh endpoint."""

    def test_refresh_token_success(self, client, test_user):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = client.post(
            f"/auth/refresh?refresh_token={refresh_token}",
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token."""
        response = client.post(
            "/auth/refresh?refresh_token=invalid-token",
        )

        assert response.status_code == 401
        assert "invalid or expired" in response.json()["detail"]["message"].lower()


class TestGetCurrentUser:
    """Test get current user endpoint."""

    def test_get_current_user_success(self, client, test_user):
        """Test getting current user info."""
        # Login first
        login_response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Get user info
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"

    def test_get_current_user_no_auth(self, client):
        """Test getting current user without authentication."""
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestRoleBasedAuthorization:
    """Test role-based authorization."""

    def test_admin_user_has_admin_role(self, client, admin_user):
        """Test that admin user has admin role."""
        # Login as admin
        login_response = client.post(
            "/auth/login",
            data={
                "username": "admin",
                "password": "adminpass123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Check role
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_regular_user_has_user_role(self, client, test_user):
        """Test that regular user has user role."""
        # Login as regular user
        login_response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Check role
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert response.json()["role"] == "user"


class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication."""

    def test_health_endpoint_no_auth_required(self, client):
        """Test that health endpoint doesn't require auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_providers_endpoint_no_auth_required(self, client):
        """Test that providers endpoint doesn't require auth."""
        response = client.get("/providers")
        # Should succeed or return appropriate response, not 401
        assert response.status_code != 401

    def test_authenticated_endpoint_with_token(self, client, test_user):
        """Test accessing authenticated endpoint with valid token."""
        # Login first
        login_response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )
        access_token = login_response.json()["access_token"]

        # Access authenticated endpoint (using /auth/me as example)
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200

    def test_authenticated_endpoint_without_token(self, client):
        """Test accessing authenticated endpoint without token."""
        response = client.get("/auth/me")
        assert response.status_code == 401
