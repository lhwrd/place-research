"""Authentication and authorization specific exceptions."""

from app.exceptions.base import ConflictError, ForbiddenError, UnauthorizedError


class InvalidCredentialsError(UnauthorizedError):
    """Raised when login credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid email or password")


class TokenExpiredError(UnauthorizedError):
    """Raised when JWT token has expired."""

    def __init__(self):
        super().__init__("Token has expired")


class InvalidTokenError(UnauthorizedError):
    """Raised when JWT token is malformed or invalid."""

    def __init__(self):
        super().__init__("Invalid authentication token")


class InactiveUserError(ForbiddenError):
    """Raised when user account is inactive/disabled."""

    def __init__(self):
        super().__init__("User account is inactive")


class EmailAlreadyExistsError(ConflictError):
    """Raised when attempting to register with existing email."""

    def __init__(self, email: str):
        super().__init__(f"Email {email} is already registered", details={"email": email})
