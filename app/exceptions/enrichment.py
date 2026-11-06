"""Property enrichment specific exceptions."""

from typing import Optional

from app.exceptions.base import AppError


class EnrichmentError(AppError):
    """Base exception for enrichment-related errors."""

    def __init__(self, message: str, service: Optional[str] = None):
        details = {"service": service} if service else {}
        super().__init__(message, status_code=500, details=details)


class GeocodingFailedError(EnrichmentError):
    """Raised when address geocoding fails."""

    def __init__(self, address: str):
        super().__init__(f"Failed to geocode address:  {address}", service="geocoding")
