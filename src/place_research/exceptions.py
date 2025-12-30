"""Custom exceptions for place-research.

This module defines the exception hierarchy for the application.
All exceptions include proper error codes and messages for API responses.
"""

from typing import Any, Optional


class PlaceResearchError(Exception):
    """Base exception for all place-research errors.

    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# Configuration Errors
class ConfigurationError(PlaceResearchError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str, provider: Optional[str] = None):
        message = f"Missing required configuration: {config_key}"
        if provider:
            message += f" (required by {provider})"
        super().__init__(
            message, details={"missing_key": config_key, "provider": provider}
        )


# Provider Errors
class ProviderError(PlaceResearchError):
    """Base exception for provider-related errors."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        error_code: str = "PROVIDER_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        details["provider"] = provider_name
        super().__init__(message, error_code, details)
        self.provider_name = provider_name


class ProviderAPIError(ProviderError):
    """Raised when a provider's external API call fails."""

    def __init__(
        self,
        provider_name: str,
        api_name: str,
        status_code: Optional[int] = None,
        original_error: Optional[str] = None,
    ):
        message = f"API error from {api_name}"
        if status_code:
            message += f" (HTTP {status_code})"

        details = {
            "api": api_name,
            "status_code": status_code,
            "original_error": original_error,
        }
        super().__init__(message, provider_name, "PROVIDER_API_ERROR", details)


class ProviderTimeoutError(ProviderError):
    """Raised when a provider times out."""

    def __init__(self, provider_name: str, timeout_seconds: float):
        message = f"Provider timed out after {timeout_seconds}s"
        super().__init__(
            message,
            provider_name,
            "PROVIDER_TIMEOUT",
            {"timeout_seconds": timeout_seconds},
        )


class ProviderDataError(ProviderError):
    """Raised when provider returns invalid or unexpected data."""

    def __init__(self, provider_name: str, reason: str):
        super().__init__(
            f"Invalid data from provider: {reason}",
            provider_name,
            "PROVIDER_DATA_ERROR",
            {"reason": reason},
        )


# Validation Errors
class ValidationError(PlaceResearchError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, "VALIDATION_ERROR", details)


class InvalidGeolocationError(ValidationError):
    """Raised when geolocation format is invalid."""

    def __init__(self, geolocation: str):
        super().__init__(
            "Invalid geolocation format. Expected 'lat;lng' (e.g., '40.7128;-74.0060')",
            field="geolocation",
            value=geolocation,
        )


class InvalidCoordinatesError(ValidationError):
    """Raised when coordinates are out of valid range."""

    def __init__(self, lat: float, lng: float):
        super().__init__(
            "Coordinates out of range. Latitude must be -90 to 90, longitude -180 to 180",
            field="coordinates",
            value=f"{lat};{lng}",
        )


# Repository Errors
class RepositoryError(PlaceResearchError):
    """Base exception for repository/storage errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, "REPOSITORY_ERROR", details)


class PlaceNotFoundError(RepositoryError):
    """Raised when a place is not found in the repository."""

    def __init__(self, place_id: str):
        super().__init__(f"Place not found: {place_id}", details={"place_id": place_id})
        self.error_code = "PLACE_NOT_FOUND"


class RepositoryConnectionError(RepositoryError):
    """Raised when connection to repository fails."""

    def __init__(self, repository_type: str, original_error: Optional[str] = None):
        message = f"Failed to connect to {repository_type}"
        details = {"repository_type": repository_type}
        if original_error:
            details["original_error"] = original_error
        super().__init__(message, details)
        self.error_code = "REPOSITORY_CONNECTION_ERROR"


# Service Errors
class ServiceError(PlaceResearchError):
    """Base exception for service layer errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, "SERVICE_ERROR", details)


class EnrichmentError(ServiceError):
    """Raised when place enrichment fails completely."""

    def __init__(self, reason: str, place_id: Optional[str] = None):
        details = {"reason": reason}
        if place_id:
            details["place_id"] = place_id
        super().__init__(f"Enrichment failed: {reason}", details)
        self.error_code = "ENRICHMENT_ERROR"


class PartialEnrichmentError(ServiceError):
    """Raised when some providers fail during enrichment.

    This is a warning-level exception that may not need to fail the request.
    """

    def __init__(self, failed_providers: list[str], error_count: int):
        message = f"{error_count} provider(s) failed during enrichment"
        super().__init__(
            message,
            details={"failed_providers": failed_providers, "error_count": error_count},
        )
        self.error_code = "PARTIAL_ENRICHMENT_ERROR"


# Rate Limiting Errors
class RateLimitError(PlaceResearchError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, limit: int, window_seconds: int, retry_after: Optional[int] = None
    ):
        message = f"Rate limit exceeded: {limit} requests per {window_seconds}s"
        details = {
            "limit": limit,
            "window_seconds": window_seconds,
        }
        if retry_after:
            details["retry_after_seconds"] = retry_after
            message += f". Retry after {retry_after}s"

        super().__init__(message, "RATE_LIMIT_EXCEEDED", details)
