"""API routes for place-research.

This module defines all the REST API endpoints for place enrichment.
Uses FastAPI dependency injection for explicit configuration and service management.
"""

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from ..config import Settings, get_settings
from ..models import Place, UserRole
from ..service import PlaceEnrichmentService

# Auth imports
try:
    from ..auth import require_role

    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)


router = APIRouter()


# Dependency for getting the enrichment service
def get_enrichment_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlaceEnrichmentService:
    """Create PlaceEnrichmentService instance.

    This is a FastAPI dependency that provides the enrichment service.
    A new service instance is created for each request, ensuring thread safety.

    Args:
        settings: Application settings (injected dependency)

    Returns:
        PlaceEnrichmentService instance
    """
    return PlaceEnrichmentService(settings)


# Request/Response Models
class PlaceEnrichRequest(BaseModel):
    """Request body for enriching a place."""

    address: Optional[str] = Field(None, min_length=3, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_coordinates_together(cls, v, _info):
        """Validate that if one coordinate is provided, both must be provided."""
        # This validator runs for each field, so we just return the value
        # The actual validation happens in the endpoint
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "address": "1600 Amphitheatre Parkway, Mountain View, CA",
                "latitude": 37.4221,
                "longitude": -122.0841,
            }
        }


class ProviderStatusResponse(BaseModel):
    """Response for provider status endpoint."""

    enabled_providers: list[str]
    provider_details: dict


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: str
    version: str
    providers_count: int


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "VALIDATION_ERROR",
                "message": "Invalid geolocation format",
                "details": {"field": "geolocation", "value": "invalid"},
            }
        }


@router.get("/", tags=["General"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Place Research API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "providers": "/providers",
            "enrich": "/enrich (POST)",
            "cache_stats": "/cache/stats",
            "metrics": "/metrics",
        },
    }


@router.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check(
    service: Annotated[PlaceEnrichmentService, Depends(get_enrichment_service)],
):
    """Health check endpoint.

    Returns service status and configuration.
    """
    return HealthResponse(
        status="healthy", version="0.1.0", providers_count=len(service.providers)
    )


@router.get("/providers", response_model=ProviderStatusResponse, tags=["Providers"])
async def get_providers(
    service: Annotated[PlaceEnrichmentService, Depends(get_enrichment_service)],
):
    """Get status of all providers.

    Returns information about which providers are enabled and their configuration status.
    """
    return ProviderStatusResponse(
        enabled_providers=service.get_enabled_providers(),
        provider_details=service.get_provider_status(),
    )


@router.post(
    "/enrich",
    tags=["Enrichment"],
    responses={
        200: {"description": "Successfully enriched place"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def enrich_place(
    request: PlaceEnrichRequest,
    service: Annotated[PlaceEnrichmentService, Depends(get_enrichment_service)],
    settings: Settings = Depends(get_settings),
    user: Optional[Any] = (
        None if not AUTH_AVAILABLE else Depends(require_role(UserRole.READONLY))
    ),
) -> dict:
    """Enrich a place with data from all enabled providers.

    Args:
        request: Place information (address and/or latitude/longitude)
        service: Enrichment service (injected dependency)
        settings: Application settings
        user: Authenticated user (optional)

    Returns:
        Enrichment results from all providers

    Raises:
        HTTPException: If place information is invalid or enrichment fails
    """
    # Check if authentication is required
    if settings.require_authentication and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "Authentication required. Provide API key via X-API-Key header or Authorization: Bearer token",  # pylint: disable=line-too-long
                "details": {},
            },
        )

    # Log authenticated requests
    if user:
        logger.info("Enrichment request from %s (%s)", user.username, user.role)

    if not request.address and not request.latitude and not request.longitude:
        raise HTTPException(
            status_code=400,
            detail="Either address or latitude and longitude must be provided",
        )

    # Create Place object
    try:
        place_data = {}
        if request.address:
            place_data["address"] = request.address
        if request.latitude is not None:
            place_data["latitude"] = request.latitude
        if request.longitude is not None:
            place_data["longitude"] = request.longitude

        place = Place(**place_data)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid place data: {str(e)}"
        ) from e

    # Enrich the place
    try:
        result = await service.enrich_place(place)
        return result.to_dict()

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Enrichment failed: {str(e)}"
        ) from e


@router.get("/enrich", tags=["Enrichment"])
async def enrich_place_get(
    service: Annotated[PlaceEnrichmentService, Depends(get_enrichment_service)],
    address: Optional[str] = Query(None, description="Place address"),
    latitude: Optional[float] = Query(None, description="Place latitude"),
    longitude: Optional[float] = Query(None, description="Place longitude"),
) -> dict:
    """Enrich a place with data from all enabled providers (GET version).

    This is a convenience endpoint that accepts query parameters instead of POST body.
    Useful for simple requests and testing.

    Args:
        address: Place address
        latitude: Place latitude
        longitude: Place longitude
        service: Enrichment service (injected dependency)

    Returns:
        Enrichment results from all providers
    """
    request = PlaceEnrichRequest(
        address=address, latitude=latitude, longitude=longitude
    )
    return await enrich_place(request, service)


@router.get("/cache/stats", tags=["Cache"])
async def get_cache_stats(
    service: Annotated[PlaceEnrichmentService, Depends(get_enrichment_service)],
) -> dict:
    """Get cache statistics.

    Returns cache hit rate, size, and other metrics.
    Returns empty stats if caching is disabled.

    Returns:
        Cache statistics dictionary
    """
    if not service.cache_manager:
        return {
            "enabled": False,
            "message": "Caching is disabled",
        }

    stats = await service.cache_manager.get_stats()
    stats["enabled"] = True
    return stats


def get_metrics_provider(request: Request):
    """Dependency to get metrics provider from app state.

    This follows DIP by depending on the abstraction stored in app state.

    Args:
        request: FastAPI request object containing app state

    Returns:
        MetricsProvider instance

    Raises:
        HTTPException: If metrics provider is not available
    """
    try:
        registry = request.app.state.metrics_registry
        return registry.get_provider()
    except (AttributeError, RuntimeError) as e:
        logger.warning("Metrics provider not available: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "METRICS_UNAVAILABLE",
                "message": "Metrics middleware not initialized",
                "details": {"reason": str(e)},
            },
        ) from e


@router.get("/metrics", tags=["Observability"])
async def get_metrics(
    metrics_provider: Annotated[Any, Depends(get_metrics_provider)],
) -> dict:
    """Get application performance metrics.

    Returns request counts, error rates, average response times,
    and per-endpoint statistics.

    Args:
        metrics_provider: Metrics provider (injected dependency)

    Returns:
        Metrics dictionary with request statistics
    """
    return metrics_provider.get_metrics()
