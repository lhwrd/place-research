import logging
import smtplib

from app.core.config import settings


class EmailClient:
    """
    A simple email client to send emails using SMTP.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    async def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Send an email to the specified address."""
        try:
            with smtplib.SMTP(settings.email_smtp_server, settings.email_smtp_port) as server:
                server.starttls()
                server.login(settings.email_username, settings.email_password)
                message = f"Subject: {subject}\n\n{body}"
                server.sendmail(settings.email_from_address, to_address, message)
            return True
        except (smtplib.SMTPException, OSError) as e:
            self.logger.error(f"Failed to send email to {to_address}: {e}")
            return False
