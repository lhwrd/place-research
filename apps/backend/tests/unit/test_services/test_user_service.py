from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.user import User
from app.models.user_preference import UserPreference
from app.services.user_service import UserService

"""Tests for user service."""


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def user_service(mock_db):
    """User service instance with mocked database."""
    return UserService(mock_db)


@pytest.fixture
def sample_user():
    """Sample user object."""
    return User(
        id=1,
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        last_login=None,
    )


class TestGetUserByEmail:
    def test_get_user_by_email_found(self, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        result = user_service.get_user_by_email("test@example.com")

        assert result == sample_user
        mock_db.query.assert_called_once_with(User)

    def test_get_user_by_email_not_found(self, user_service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = user_service.get_user_by_email("nonexistent@example.com")

        assert result is None


class TestGetUserById:
    def test_get_user_by_id_found(self, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        result = user_service.get_user_by_id(1)

        assert result == sample_user
        mock_db.query.assert_called_once_with(User)

    def test_get_user_by_id_not_found(self, user_service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = user_service.get_user_by_id(999)

        assert result is None


class TestCreateUser:
    @patch("app.services.user_service.get_password_hash")
    def test_create_user_with_full_name(self, mock_hash, user_service, mock_db):
        mock_hash.return_value = "hashed_password"

        result = user_service.create_user("test@example.com", "password123", "Test User")

        assert result.email == "test@example.com"
        assert result.full_name == "Test User"
        assert result.is_active is True
        assert result.is_superuser is False
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    @patch("app.services.user_service.get_password_hash")
    def test_create_user_without_full_name(self, mock_hash, user_service, mock_db):
        mock_hash.return_value = "hashed_password"

        result = user_service.create_user("test@example.com", "password123")

        assert result.email == "test@example.com"
        assert result.full_name is None


class TestAuthenticateUser:
    @patch("app.services.user_service.verify_password")
    def test_authenticate_user_success(self, mock_verify, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        mock_verify.return_value = True

        result = user_service.authenticate_user("test@example.com", "password123")

        assert result == sample_user
        mock_verify.assert_called_once_with("password123", sample_user.hashed_password)

    @patch("app.services.user_service.verify_password")
    def test_authenticate_user_wrong_password(
        self, mock_verify, user_service, mock_db, sample_user
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        mock_verify.return_value = False

        result = user_service.authenticate_user("test@example.com", "wrong_password")

        assert result is None

    def test_authenticate_user_not_found(self, user_service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = user_service.authenticate_user("nonexistent@example.com", "password123")

        assert result is None


class TestUpdateUser:
    def test_update_user(self, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        updates = {"full_name": "Updated Name", "is_active": False}

        result = user_service.update_user(1, updates)

        assert result.full_name == "Updated Name"
        assert result.is_active is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()


class TestUpdatePassword:
    @patch("app.services.user_service.get_password_hash")
    def test_update_password(self, mock_hash, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user
        mock_hash.return_value = "new_hashed_password"

        user_service.update_password(1, "new_password")

        assert sample_user.hashed_password == "new_hashed_password"
        mock_db.commit.assert_called_once()


class TestUpdateLastLogin:
    def test_update_last_login(self, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        user_service.update_last_login(1)

        assert sample_user.last_login is not None
        mock_db.commit.assert_called_once()


class TestDeactivateUser:
    def test_deactivate_user(self, user_service, mock_db, sample_user):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        user_service.deactivate_user(1)

        assert sample_user.is_active is False
        mock_db.commit.assert_called_once()


class TestActivateUser:
    def test_activate_user(self, user_service, mock_db, sample_user):
        sample_user.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = sample_user

        user_service.activate_user(1)

        assert sample_user.is_active is True
        mock_db.commit.assert_called_once()
