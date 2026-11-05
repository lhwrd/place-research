"""
Error classes for the Property Research application.

Import exceptions from this module for consistency.
"""

from app.exceptions.address import InvalidAddressError
from app.exceptions.base import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from app.exceptions.enrichment import (
    EnrichmentError,
    GeocodingFailedError,
    WalkScoreUnavailableError,
)
from app.exceptions.external_api import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
    GoogleMapsAPIError,
    OSRMAPIError,
    WalkScoreAPIError,
)

__all__ = [
    # Base
    "AppError",
    "ValidationError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "RateLimitError",
    # Address
    "InvalidAddressError",
    # Enrichment
    "EnrichmentError",
    "WalkScoreUnavailableError",
    "GeocodingFailedError",
    # External API
    "ExternalAPIError",
    "GoogleMapsAPIError",
    "WalkScoreAPIError",
    "OSRMAPIError",
    "APIQuotaExceededError",
    "APIKeyInvalidError",
]
