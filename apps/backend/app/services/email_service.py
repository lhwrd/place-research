from app.integrations.email import EmailClient


class EmailService:
    """
    Email service
    """

    def __init__(self) -> None:
        self.email_client = EmailClient()

    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """Send a password reset email."""
        reset_link = f"http://localhost:8000/reset-password?token={reset_token}"
        subject = "Password Reset Request"
        body = f"Click the following link to reset your password: {reset_link}"
        return await self.email_client.send_email(email, subject, body)
