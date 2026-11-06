"""
Error classes for the Property Research application.

Import exceptions from this module for consistency.
"""

from app.exceptions.address import InvalidAddressError
from app.exceptions.base import (
    AppError,
    ValidationError,
)
from app.exceptions.enrichment import (
    EnrichmentError,
    GeocodingFailedError,
)
from app.exceptions.external_api import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
    GoogleMapsAPIError,
    WalkScoreAPIError,
)

__all__ = [
    # Base
    "AppError",
    "ValidationError",
    # Address
    "InvalidAddressError",
    # Enrichment
    "EnrichmentError",
    "GeocodingFailedError",
    # External API
    "ExternalAPIError",
    "GoogleMapsAPIError",
    "WalkScoreAPIError",
    "APIQuotaExceededError",
    "APIKeyInvalidError",
]
