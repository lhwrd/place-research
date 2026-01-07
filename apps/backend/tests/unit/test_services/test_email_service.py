import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.email_service import EmailService


@pytest.fixture
def email_service():
    """Fixture to create an EmailService instance."""
    return EmailService()


@pytest.mark.asyncio
async def test_send_password_reset_email_success(email_service):
    """Test successful password reset email sending."""
    email_service.email_client.send_email = AsyncMock(return_value=True)

    result = await email_service.send_password_reset_email("test@example.com", "test-token-123")

    assert result is True
    email_service.email_client.send_email.assert_called_once_with(
        "test@example.com",
        "Password Reset Request",
        "Click the following link to reset your password: http://localhost:8000/reset-password?token=test-token-123",
    )


@pytest.mark.asyncio
async def test_send_password_reset_email_failure(email_service):
    """Test password reset email sending failure."""
    email_service.email_client.send_email = AsyncMock(return_value=False)

    result = await email_service.send_password_reset_email("test@example.com", "test-token-123")

    assert result is False
    email_service.email_client.send_email.assert_called_once()


@pytest.mark.asyncio
async def test_send_password_reset_email_correct_link_format(email_service):
    """Test that the reset link is correctly formatted."""
    email_service.email_client.send_email = AsyncMock(return_value=True)

    await email_service.send_password_reset_email("user@example.com", "abc123")

    call_args = email_service.email_client.send_email.call_args[0]
    assert "http://localhost:8000/reset-password?token=abc123" in call_args[2]
