"""Tests for security utilities."""

from datetime import timedelta, timezone, datetime
from unittest.mock import patch
import pytest
from jose import jwt
from app.core.config import settings

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    _pre_hash_password,
)


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_password_hash_and_verify(self):
        """Test that a password can be hashed and verified."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails_verification(self):
        """Test that wrong password fails verification."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_long_password_support(self):
        """Test that very long passwords are supported."""
        # Passwords longer than 72 bytes (bcrypt limit)
        long_password = "a" * 200
        hashed = get_password_hash(long_password)

        assert verify_password(long_password, hashed) is True

    def test_pre_hash_password(self):
        """Test pre-hashing produces consistent SHA-256 hash."""
        password = "test_password"
        hash1 = _pre_hash_password(password)
        hash2 = _pre_hash_password(password)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex is 64 characters

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)

        assert hash1 != hash2


class TestAccessToken:
    """Test JWT access token creation."""

    def test_create_access_token_default_expiry(self):
        """Test creating access token with default expiration."""
        subject = "user123"
        token = create_access_token(subject)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert decoded["sub"] == subject
        assert decoded["type"] == "access"
        assert "exp" in decoded

    def test_create_access_token_custom_expiry(self):
        """Test creating access token with custom expiration."""
        subject = "user456"
        expires_delta = timedelta(minutes=30)
        token = create_access_token(subject, expires_delta)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert decoded["sub"] == subject
        assert decoded["type"] == "access"

    def test_access_token_expiration_time(self):
        """Test that access token has correct expiration time."""
        subject = "user789"
        expires_delta = timedelta(minutes=15)

        before_creation = datetime.now(timezone.utc)
        token = create_access_token(subject, expires_delta)
        after_creation = datetime.now(timezone.utc)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        expected_exp = before_creation + expires_delta

        # Allow small time difference for test execution
        assert abs((exp_time - expected_exp).total_seconds()) < 2

    def test_access_token_with_int_subject(self):
        """Test creating access token with integer subject."""
        subject = 12345
        token = create_access_token(subject)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert decoded["sub"] == str(subject)


class TestRefreshToken:
    """Test JWT refresh token creation."""

    def test_create_refresh_token_default_expiry(self):
        """Test creating refresh token with default expiration (7 days)."""
        subject = "user123"
        token = create_refresh_token(subject)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert decoded["sub"] == subject
        assert decoded["type"] == "refresh"
        assert "exp" in decoded

    def test_create_refresh_token_custom_expiry(self):
        """Test creating refresh token with custom expiration."""
        subject = "user456"
        expires_delta = timedelta(days=14)
        token = create_refresh_token(subject, expires_delta)

        decoded = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert decoded["sub"] == subject
        assert decoded["type"] == "refresh"

    def test_refresh_token_type_differs_from_access(self):
        """Test that refresh token type is different from access token."""
        subject = "user789"
        access_token = create_access_token(subject)
        refresh_token = create_refresh_token(subject)

        decoded_access = jwt.decode(
            access_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        decoded_refresh = jwt.decode(
            refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )

        assert decoded_access["type"] == "access"
        assert decoded_refresh["type"] == "refresh"
