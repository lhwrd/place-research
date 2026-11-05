"""Errors for external API integrations."""

from typing import Optional

from app.exceptions.base import AppError


class ExternalAPIError(AppError):
    """Base exception for external API errors."""

    def __init__(
        self,
        service: str,
        message: str,
        status_code: int = 503,
        api_status_code: Optional[int] = None,
    ):
        details = {"service": service, "api_status_code": api_status_code}
        super().__init__(message, status_code=status_code, details=details)


class GoogleMapsAPIError(ExternalAPIError):
    """Raised when Google Maps API call fails."""

    def __init__(self, message: str, api_status_code: Optional[int] = None):
        super().__init__(
            service="google_maps",
            message=f"Google Maps API error: {message}",
            api_status_code=api_status_code,
        )


class WalkScoreAPIError(ExternalAPIError):
    """Raised when Walk Score API call fails."""

    def __init__(self, message: str, api_status_code: Optional[int] = None):
        super().__init__(
            service="walk_score",
            message=f"Walk Score API error: {message}",
            api_status_code=api_status_code,
        )


class APIQuotaExceededError(ExternalAPIError):
    """Raised when external API quota is exceeded."""

    def __init__(self, service: str):
        super().__init__(service=service, message=f"{service} API quota exceeded", status_code=429)


class APIKeyInvalidError(ExternalAPIError):
    """Raised when external API key is invalid or expired."""

    def __init__(self, service: str):
        super().__init__(
            service=service,
            message=f"Invalid or expired API key for {service}",
            status_code=500,
        )
