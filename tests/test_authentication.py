"""Tests for authentication and authorization.

This module tests API key authentication, role-based authorization,
and the auth management endpoints.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from place_research.api import create_app
from place_research.auth import APIKeyManager, AuthenticationError
from place_research.models.auth import (
    UserRole,
    RateLimitTier,
    CreateAPIKeyRequest,
    APIKey,
)


class TestAPIKeyModel:
    """Test API Key model."""

    def test_api_key_creation(self):
        """Test creating an API key."""
        key = APIKey(
            key="test-key-123",
            name="Test Key",
            role=UserRole.USER,
            tier=RateLimitTier.BASIC,
        )

        assert key.key == "test-key-123"
        assert key.name == "Test Key"
        assert key.role == UserRole.USER
        assert key.tier == RateLimitTier.BASIC
        assert key.enabled is True
        assert key.request_count == 0

    def test_api_key_expiration(self):
        """Test API key expiration."""
        # Not expired
        key = APIKey(
            key="test-key", name="Test", expires_at=datetime.now() + timedelta(days=1)
        )
        assert not key.is_expired()
        assert key.is_valid()

        # Expired
        key.expires_at = datetime.now() - timedelta(days=1)
        assert key.is_expired()
        assert not key.is_valid()

    def test_api_key_disabled(self):
        """Test disabled API key."""
        key = APIKey(key="test-key", name="Test", enabled=False)
        assert not key.is_valid()

    def test_rate_limits(self):
        """Test rate limit tiers."""
        tiers = {
            RateLimitTier.FREE: 100,
            RateLimitTier.BASIC: 1000,
            RateLimitTier.PREMIUM: 10000,
            RateLimitTier.UNLIMITED: 999999999,
        }

        for tier, expected_limit in tiers.items():
            key = APIKey(key="test", name="Test", tier=tier)
            assert key.get_rate_limit() == expected_limit


class TestAPIKeyManager:
    """Test API Key Manager."""

    def test_default_keys(self):
        """Test that default keys are initialized."""
        manager = APIKeyManager()
        keys = manager.list_keys()

        assert len(keys) >= 3  # At least admin, user, readonly

        # Check admin key exists
        admin_key = manager.get_key("dev-admin-key-12345")
        assert admin_key is not None
        assert admin_key.role == UserRole.ADMIN

    def test_generate_key(self):
        """Test key generation."""
        manager = APIKeyManager()
        key1 = manager.generate_key()
        key2 = manager.generate_key()

        # Keys should be unique
        assert key1 != key2

        # Keys should have proper format
        assert key1.startswith("pr_")
        assert len(key1) == 35  # pr_ + 32 chars

    def test_create_key(self):
        """Test creating a new API key."""
        manager = APIKeyManager()

        request = CreateAPIKeyRequest(
            name="Test API Key",
            role=UserRole.USER,
            tier=RateLimitTier.BASIC,
            expires_in_days=30,
        )

        key = manager.create_key(request)

        assert key.name == "Test API Key"
        assert key.role == UserRole.USER
        assert key.tier == RateLimitTier.BASIC
        assert key.enabled is True

        # Key should be retrievable
        retrieved = manager.get_key(key.key)
        assert retrieved == key

    def test_validate_key_success(self):
        """Test successful key validation."""
        manager = APIKeyManager()

        # Use default admin key
        key = manager.validate_key("dev-admin-key-12345")

        assert key.role == UserRole.ADMIN
        assert key.request_count == 1  # Should increment
        assert key.last_used_at is not None

    def test_validate_key_invalid(self):
        """Test validation with invalid key."""
        manager = APIKeyManager()

        with pytest.raises(AuthenticationError) as exc:
            manager.validate_key("invalid-key")

        assert "Invalid API key" in exc.value.message

    def test_validate_key_disabled(self):
        """Test validation with disabled key."""
        manager = APIKeyManager()

        # Create and disable a key
        request = CreateAPIKeyRequest(
            name="Test", role=UserRole.USER, expires_in_days=30
        )
        key = manager.create_key(request)
        key.enabled = False

        with pytest.raises(AuthenticationError) as exc:
            manager.validate_key(key.key)

        assert "disabled" in exc.value.message.lower()

    def test_validate_key_expired(self):
        """Test validation with expired key."""
        manager = APIKeyManager()

        # Create expired key
        request = CreateAPIKeyRequest(
            name="Test", role=UserRole.USER, expires_in_days=1
        )
        key = manager.create_key(request)
        key.expires_at = datetime.now() - timedelta(days=1)

        with pytest.raises(AuthenticationError) as exc:
            manager.validate_key(key.key)

        assert "expired" in exc.value.message.lower()

    def test_revoke_key(self):
        """Test revoking a key."""
        manager = APIKeyManager()

        request = CreateAPIKeyRequest(
            name="Test", role=UserRole.USER, expires_in_days=30
        )
        key = manager.create_key(request)

        assert key.enabled is True

        success = manager.revoke_key(key.key)
        assert success is True
        assert key.enabled is False

        # Should fail validation now
        with pytest.raises(AuthenticationError):
            manager.validate_key(key.key)

    def test_delete_key(self):
        """Test deleting a key."""
        manager = APIKeyManager()

        request = CreateAPIKeyRequest(
            name="Test", role=UserRole.USER, expires_in_days=30
        )
        key = manager.create_key(request)

        success = manager.delete_key(key.key)
        assert success is True

        # Key should not exist
        assert manager.get_key(key.key) is None


class TestAuthentication:
    """Test authentication in API."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_health_no_auth_required(self, client):
        """Test that health endpoint doesn't require auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_providers_no_auth_required(self, client):
        """Test that providers endpoint doesn't require auth."""
        response = client.get("/providers")
        assert response.status_code == 200

    def test_enrich_without_auth_when_not_required(self, client):
        """Test enrichment without auth when auth not required."""
        # By default, authentication is not required
        response = client.post("/enrich", json={"address": "123 Main St"})

        # May fail for other reasons (missing API keys), but not auth
        assert response.status_code != 401

    def test_enrich_with_valid_api_key(self, client):
        """Test enrichment with valid API key."""
        response = client.post(
            "/enrich",
            json={"address": "123 Main St"},
            headers={"X-API-Key": "dev-user-key-67890"},
        )

        # Should not fail due to authentication
        assert response.status_code != 401

    def test_enrich_with_bearer_token(self, client):
        """Test enrichment with Bearer token."""
        response = client.post(
            "/enrich",
            json={"address": "123 Main St"},
            headers={"Authorization": "Bearer dev-user-key-67890"},
        )

        # Should not fail due to authentication
        assert response.status_code != 401


class TestAuthEndpoints:
    """Test authentication management endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_get_current_key_info(self, client):
        """Test getting current key information."""
        response = client.get("/auth/me", headers={"X-API-Key": "dev-user-key-67890"})

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Development User Key"
        assert data["role"] == "user"
        assert data["tier"] == "basic"
        assert "request_count" in data

    def test_get_current_key_no_auth(self, client):
        """Test getting current key without authentication."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        data = response.json()
        # Response has 'detail' field with error info
        assert "detail" in data
        if isinstance(data["detail"], dict):
            assert data["detail"]["error"] == "AUTHENTICATION_ERROR"
        else:
            assert (
                "authentication" in str(data["detail"]).lower()
                or "api key" in str(data["detail"]).lower()
            )

    def test_list_keys_as_admin(self, client):
        """Test listing keys as admin."""
        response = client.get(
            "/auth/keys", headers={"X-API-Key": "dev-admin-key-12345"}
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 3  # Default keys

    def test_list_keys_as_user(self, client):
        """Test listing keys as regular user (should fail)."""
        response = client.get("/auth/keys", headers={"X-API-Key": "dev-user-key-67890"})

        assert response.status_code == 403
        data = response.json()
        # Check detail field
        if isinstance(data.get("detail"), dict):
            assert data["detail"]["error"] == "AUTHORIZATION_ERROR"
        else:
            assert "authorization" in str(data).lower() or "admin" in str(data).lower()

    def test_create_key_as_admin(self, client):
        """Test creating API key as admin."""
        response = client.post(
            "/auth/keys",
            json={"name": "New Test Key", "role": "user", "tier": "basic"},
            headers={"X-API-Key": "dev-admin-key-12345"},
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "New Test Key"
        assert data["role"] == "user"
        assert data["tier"] == "basic"
        assert "key" in data

    def test_create_key_as_user(self, client):
        """Test creating API key as regular user (should fail)."""
        response = client.post(
            "/auth/keys",
            json={"name": "New Test Key", "role": "user", "tier": "basic"},
            headers={"X-API-Key": "dev-user-key-67890"},
        )

        assert response.status_code == 403

    def test_revoke_key_as_admin(self, client):
        """Test revoking API key as admin."""
        # First create a key
        create_response = client.post(
            "/auth/keys",
            json={"name": "Key to Revoke", "role": "user", "tier": "free"},
            headers={"X-API-Key": "dev-admin-key-12345"},
        )

        assert create_response.status_code == 201
        key_to_revoke = create_response.json()["key"]

        # Now revoke it
        response = client.delete(
            f"/auth/keys/{key_to_revoke}", headers={"X-API-Key": "dev-admin-key-12345"}
        )

        assert response.status_code == 204

    def test_revoke_nonexistent_key(self, client):
        """Test revoking non-existent key."""
        response = client.delete(
            "/auth/keys/nonexistent-key", headers={"X-API-Key": "dev-admin-key-12345"}
        )

        assert response.status_code == 404


class TestAuthorization:
    """Test role-based authorization."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_admin_can_create_keys(self, client):
        """Test that admin can create keys."""
        response = client.post(
            "/auth/keys",
            json={"name": "Test", "role": "user", "tier": "free"},
            headers={"X-API-Key": "dev-admin-key-12345"},
        )

        assert response.status_code == 201

    def test_user_cannot_create_keys(self, client):
        """Test that regular user cannot create keys."""
        response = client.post(
            "/auth/keys",
            json={"name": "Test", "role": "user", "tier": "free"},
            headers={"X-API-Key": "dev-user-key-67890"},
        )

        assert response.status_code == 403
        data = response.json()
        # Check for authorization error
        response_str = str(data).lower()
        assert (
            "admin" in response_str
            or "authorization" in response_str
            or "forbidden" in response_str
        )

    def test_readonly_cannot_create_keys(self, client):
        """Test that readonly user cannot create keys."""
        response = client.post(
            "/auth/keys",
            json={"name": "Test", "role": "user", "tier": "free"},
            headers={"X-API-Key": "dev-readonly-key-11111"},
        )

        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
