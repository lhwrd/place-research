import smtplib
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.integrations.email import EmailClient


@pytest.fixture
def email_client():
    """Fixture to create an EmailClient instance."""
    return EmailClient()


@pytest.mark.asyncio
async def test_send_email_success(email_client):
    """Test successful email sending."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = await email_client.send_email(
            to_address="test@example.com", subject="Test Subject", body="Test Body"
        )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_smtp_exception(email_client):
    """Test email sending with SMTP exception."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException("SMTP error")

        result = await email_client.send_email(
            to_address="test@example.com", subject="Test Subject", body="Test Body"
        )

        assert result is False


@pytest.mark.asyncio
async def test_send_email_os_error(email_client):
    """Test email sending with OS error."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.side_effect = OSError("Connection error")

        result = await email_client.send_email(
            to_address="test@example.com", subject="Test Subject", body="Test Body"
        )

        assert result is False


@pytest.mark.asyncio
async def test_send_email_logs_error(email_client):
    """Test that errors are logged properly."""
    with patch("smtplib.SMTP") as mock_smtp, patch.object(
        email_client.logger, "error"
    ) as mock_logger:
        mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException("SMTP error")

        await email_client.send_email(
            to_address="test@example.com", subject="Test Subject", body="Test Body"
        )

        mock_logger.assert_called_once()
