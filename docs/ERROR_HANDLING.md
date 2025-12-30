# Error Handling & Validation

This document describes the comprehensive error handling and validation system implemented in place-research.

## Overview

The error handling system provides:

- **Custom exception hierarchy** for type-safe error handling
- **Input validation** with clear error messages
- **Consistent API error responses** following REST best practices
- **Sanitization** of error messages to prevent sensitive data leakage
- **Proper HTTP status codes** for different error types

## Exception Hierarchy

All custom exceptions inherit from `PlaceResearchError` base class:

```python
from place_research.exceptions import (
    PlaceResearchError,      # Base exception
    ValidationError,         # Invalid input
    ConfigurationError,      # Missing/invalid config
    ProviderError,          # Provider failures
    RepositoryError,        # Storage failures
    EnrichmentError,        # Service layer errors
)
```

### Exception Structure

Every exception includes:

- `message`: Human-readable error description
- `error_code`: Machine-readable error identifier (e.g., "VALIDATION_ERROR")
- `details`: Dictionary with additional context
- `to_dict()`: Method for JSON serialization

### Exception Categories

#### 1. Configuration Errors

```python
# Missing required configuration
MissingConfigError(config_key="WALKSCORE_API_KEY", provider="WalkBikeScore")

# Invalid configuration value
ConfigurationError("Invalid path for railroad data")
```

#### 2. Validation Errors

```python
# Invalid coordinates
InvalidCoordinatesError(lat=100, lng=-74)  # Lat out of range

# Invalid geolocation format
InvalidGeolocationError("invalid")  # Should be "lat;lng"

# Generic validation
ValidationError("Address too short", field="address", value="AB")
```

#### 3. Provider Errors

```python
# API call failed
ProviderAPIError(
    provider_name="WalkScore",
    api_name="Walk Score API",
    status_code=429,
    original_error="Rate limit exceeded"
)

# Provider timeout
ProviderTimeoutError(provider_name="FloodZone", timeout_seconds=30.0)

# Invalid data from provider
ProviderDataError(provider_name="AirQuality", reason="Missing required field 'aqi'")
```

#### 4. Repository Errors

```python
# Place not found
PlaceNotFoundError(place_id="abc-123")

# Connection failure
RepositoryConnectionError(
    repository_type="NocoDB",
    original_error="Connection refused"
)
```

#### 5. Service Errors

```python
# Complete enrichment failure
EnrichmentError(reason="All providers failed", place_id="abc-123")

# Partial enrichment failure (warning level)
PartialEnrichmentError(
    failed_providers=["AirQuality", "FloodZone"],
    error_count=2
)
```

#### 6. Rate Limiting

```python
RateLimitError(
    limit=100,
    window_seconds=3600,
    retry_after=1800  # Optional
)
```

## Input Validation

The `validation` module provides utilities for validating common inputs:

### Geolocation Validation

```python
from place_research.validation import validate_geolocation

# Valid input
lat, lng = validate_geolocation("40.7128;-74.0060")

# Raises InvalidGeolocationError for:
# - Missing semicolon: "40.7128 -74.0060"
# - Wrong number of parts: "40.7128;-74.0060;100"
# - Non-numeric: "forty;-seventy"

# Raises InvalidCoordinatesError for:
# - Latitude out of range: "100;-74"
# - Longitude out of range: "40;200"
```

### Coordinate Validation

```python
from place_research.validation import validate_coordinates

# Valid
lat, lng = validate_coordinates(40.7128, -74.0060)

# Raises InvalidCoordinatesError
validate_coordinates(100, -74)  # lat > 90
validate_coordinates(40, 200)   # lng > 180
```

### Address Validation

```python
from place_research.validation import validate_address

# Valid
address = validate_address("1600 Amphitheatre Parkway")

# Raises ValidationError
validate_address("AB")  # Too short (< 3 chars)
validate_address("x" * 501)  # Too long (> 500 chars)
```

### Provider Name Validation

```python
from place_research.validation import validate_provider_name

# Valid (normalized to lowercase)
name = validate_provider_name("WalkBikeScore")  # Returns "walkbikescore"

# Raises ValidationError
validate_provider_name("Walk-Score")  # Invalid chars
validate_provider_name("")  # Empty
```

### Error Message Sanitization

Removes sensitive information from error messages:

```python
from place_research.validation import sanitize_error_message

# Removes API keys, tokens, passwords, secrets
message = "Failed: api_key=sk_abc123"
safe = sanitize_error_message(message)  # "Failed: api_key=***"

# Truncates long messages
long_msg = "x" * 1000
safe = sanitize_error_message(long_msg, max_length=100)  # Truncated to 100 chars
```

## API Error Responses

All API errors follow a consistent JSON format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "details": {
    "field": "optional_field_name",
    "additional": "context"
  }
}
```

### HTTP Status Code Mapping

| Error Type            | HTTP Status | Description              |
| --------------------- | ----------- | ------------------------ |
| `VALIDATION_ERROR`    | 422         | Invalid request data     |
| `PLACE_NOT_FOUND`     | 404         | Resource not found       |
| `CONFIGURATION_ERROR` | 404         | Missing config           |
| `RATE_LIMIT_EXCEEDED` | 429         | Too many requests        |
| `PROVIDER_*`          | 503         | External service failure |
| `INTERNAL_ERROR`      | 500         | Unexpected error         |

### Exception Handlers

FastAPI automatically converts exceptions to proper HTTP responses:

```python
# Custom exception
raise ValidationError("Invalid coordinates", field="geolocation")

# Returns HTTP 422:
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid coordinates",
  "details": {
    "field": "geolocation"
  }
}
```

```python
# Provider failure
raise ProviderAPIError("WalkScore", "Walk Score API", status_code=500)

# Returns HTTP 503:
{
  "error": "PROVIDER_API_ERROR",
  "message": "API error from Walk Score API (HTTP 500)",
  "details": {
    "provider": "WalkScore",
    "api": "Walk Score API",
    "status_code": 500
  }
}
```

```python
# All providers failed
raise EnrichmentError("All providers failed", place_id="123")

# Returns HTTP 500:
{
  "error": "ENRICHMENT_ERROR",
  "message": "Enrichment failed: All providers failed",
  "details": {
    "reason": "All providers failed",
    "place_id": "123"
  }
}
```

## Pydantic Validation

Request models use Pydantic validators for automatic validation:

```python
from pydantic import BaseModel, Field, field_validator

class PlaceEnrichRequest(BaseModel):
    address: Optional[str] = Field(None, min_length=3, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator('latitude', 'longitude')
    @classmethod
    def validate_coordinates_together(cls, v, info):
        # Custom validation logic
        return v
```

Pydantic validation errors are automatically converted to our standard format:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {
        "field": "latitude",
        "message": "Input should be greater than or equal to -90",
        "type": "greater_than_equal"
      }
    ]
  }
}
```

## Service Layer Error Handling

The service layer (`PlaceEnrichmentService`) handles provider failures gracefully:

### Partial Failures

```python
result = service.enrich_place(place)

# Check for errors
if result.has_errors():
    print(f"{len(result.errors)} provider(s) failed")
    for error in result.errors:
        print(f"{error.provider_name}: {error.error_message}")

# Still return successful results
print(f"Walk Score: {result.walk_bike_score}")
```

### Complete Failures

```python
try:
    result = service.enrich_place(place)
except EnrichmentError as e:
    # All providers failed
    print(f"Enrichment failed: {e.message}")
    print(f"Details: {e.details}")
```

### Timeout Handling

```python
# Providers that timeout are caught and logged
# Result includes ProviderError with type "PROVIDER_TIMEOUT"
result = service.enrich_place(place)

timeout_errors = [
    e for e in result.errors
    if e.error_type == "PROVIDER_TIMEOUT"
]
```

## Best Practices

### 1. Use Specific Exceptions

```python
# Good
raise MissingConfigError("WALKSCORE_API_KEY", provider="WalkBikeScore")

# Avoid
raise Exception("Missing API key")
```

### 2. Include Context in Details

```python
# Good
raise ValidationError(
    "Invalid coordinate range",
    field="latitude",
    value=100
)

# Less helpful
raise ValidationError("Invalid input")
```

### 3. Sanitize Error Messages

```python
# Good
from place_research.validation import sanitize_error_message

try:
    # API call with API key in URL
    response = requests.get(url)
except Exception as e:
    safe_msg = sanitize_error_message(str(e))
    raise ProviderError(provider_name, safe_msg)

# Avoid
raise ProviderError(provider_name, str(e))  # May leak API keys
```

### 4. Log Appropriately

```python
# Warning for expected errors
logger.warning(f"Provider {name} failed: {e.message}")

# Error for unexpected errors
logger.error(f"Unexpected error: {e}", exc_info=True)
```

### 5. Handle Partial Failures

```python
# Don't fail the entire request if one provider fails
result = service.enrich_place(place)

# Check result.errors for failures
# Return successful results
return result.to_dict()
```

## Testing Error Handling

```python
import pytest
from place_research.exceptions import ValidationError, InvalidCoordinatesError
from place_research.validation import validate_coordinates

def test_coordinate_validation():
    # Valid coordinates
    lat, lng = validate_coordinates(40.0, -74.0)
    assert lat == 40.0
    assert lng == -74.0

    # Invalid latitude
    with pytest.raises(InvalidCoordinatesError) as exc:
        validate_coordinates(100, -74)

    assert exc.value.error_code == "VALIDATION_ERROR"
    assert "out of range" in exc.value.message.lower()

    # Check details
    error_dict = exc.value.to_dict()
    assert error_dict["details"]["value"] == "100;-74"
```

## Monitoring and Logging

All errors are logged with appropriate levels:

- **DEBUG**: Provider execution start/completion
- **INFO**: Enrichment summary (success/failure counts)
- **WARNING**: Known errors (provider failures, partial enrichment)
- **ERROR**: Unexpected errors with stack traces

Logs include structured context:

```python
logger.warning(
    f"Provider {provider.name} failed: {e.message}",
    extra={
        "error_code": e.error_code,
        "provider": provider.name,
        "place_id": place.id
    }
)
```

This enables easy filtering and monitoring in production logging systems.
