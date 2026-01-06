"""Property enrichment specific exceptions."""

from typing import Optional

from app.exceptions.base import AppError, RateLimitError


class EnrichmentError(AppError):
    """Base exception for enrichment-related errors."""

    def __init__(self, message: str, service: Optional[str] = None):
        details = {"service": service} if service else {}
        super().__init__(message, status_code=500, details=details)


class EnrichmentRateLimitError(RateLimitError):
    """Raised when user exceeds enrichment rate limits."""

    def __init__(self, retry_after: int = 3600):
        super().__init__(
            "You have exceeded your hourly enrichment limit.  Please try again later.",
            retry_after=retry_after,
            details={"limit_type": "enrichment"},
        )


class WalkScoreUnavailableError(EnrichmentError):
    """Raised when Walk Score data is unavailable for a location."""

    def __init__(self, address: str):
        super().__init__(f"Walk score data unavailable for {address}", service="walk_score")


class GeocodingFailedError(EnrichmentError):
    """Raised when address geocoding fails."""

    def __init__(self, address: str):
        super().__init__(f"Failed to geocode address:  {address}", service="geocoding")
