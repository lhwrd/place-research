"""Integration tests for authentication endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


class TestAuthEndpoints:
    """Test suite for authentication endpoints."""

    def test_register_user(self, client: TestClient, db: Session):
        """Test user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"

        # Verify user exists in database
        user = db.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None
        assert user.full_name == "New User"

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registering with existing email."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": test_user.email, "password": "SecurePass123"},
        )

        assert response.status_code == 409  # Conflict

    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": test_user.email, "password": "testpassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client: TestClient, test_user: User):
        """Test login with invalid password."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": test_user.email, "password": "wrongpassword"},
        )

        assert response.status_code == 401

    def test_get_current_user(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test getting current user info."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_get_current_user_unauthorized(self, client: TestClient):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
