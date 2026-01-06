"""
Error classes for the Property Research application.

Import exceptions from this module for consistency.
"""

from app.exceptions.auth import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
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
    EnrichmentRateLimitError,
    GeocodingFailedError,
    WalkScoreUnavailableError,
)
from app.exceptions.external_api import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
    GoogleMapsAPIError,
    OSRMAPIError,
    PropertyDataAPIError,
    WalkScoreAPIError,
    ZillowAPIError,
)
from app.exceptions.property import (
    DuplicatePropertyError,
    InvalidAddressError,
    PropertyAccessDeniedError,
    PropertyNotFoundError,
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
    # Auth
    "InvalidCredentialsError",
    "TokenExpiredError",
    "InvalidTokenError",
    "InactiveUserError",
    "EmailAlreadyExistsError",
    # Property
    "PropertyNotFoundError",
    "InvalidAddressError",
    "PropertyAccessDeniedError",
    "DuplicatePropertyError",
    # Enrichment
    "EnrichmentError",
    "EnrichmentRateLimitError",
    "WalkScoreUnavailableError",
    "GeocodingFailedError",
    # External API
    "ExternalAPIError",
    "GoogleMapsAPIError",
    "WalkScoreAPIError",
    "ZillowAPIError",
    "OSRMAPIError",
    "APIQuotaExceededError",
    "APIKeyInvalidError",
    "PropertyDataAPIError",
]
