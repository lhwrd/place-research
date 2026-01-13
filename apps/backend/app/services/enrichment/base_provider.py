"""Base provider interface for enrichment services."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderCategory(Enum):
    """Categories for organizing providers."""

    WALKABILITY = "walkability"
    NEARBY_PLACES = "nearby_places"
    DISTANCES = "distances"
    ENVIRONMENTAL = "environmental"
    CLIMATE = "climate"
    NOISE = "noise"
    SAFETY = "safety"
    TRANSIT = "transit"
    DEMOGRAPHICS = "demographics"


@dataclass
class ProviderMetadata:
    """Metadata about a provider."""

    name: str
    category: ProviderCategory
    description: str
    version: str
    enabled: bool = True
    requires_api_key: bool = True
    cost_per_call: float = 0.0  # Estimated cost in USD
    cache_duration_days: int = 30
    rate_limit_per_hour: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)  # Other providers this depends on


@dataclass
class ProviderResult:
    """Standardized result from a provider."""

    provider_name: str
    data: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None
    api_calls_made: int = 0
    cached: bool = False
    enriched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseEnrichmentProvider(ABC):
    """
    Base class for all enrichment providers.

    All providers must implement this interface to be automatically
    discovered and loaded by the enrichment orchestrator.
    """

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Return provider metadata."""

    @abstractmethod
    async def enrich(
        self,
        latitude: float,
        longitude: float,
        address: str,
        property_data: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Enrich property with provider-specific data.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Additional property information
            user_preferences: User-specific preferences

        Returns:
            ProviderResult with enrichment data
        """

    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Validate provider configuration (API keys, etc.).

        Returns:
            True if configuration is valid
        """

    def should_run(self, user_preferences: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if this provider should run based on preferences.

        Override this method to implement custom logic for when
        the provider should be executed.

        Args:
            user_preferences: User-specific preferences

        Returns:
            True if provider should run
        """
        if not self.metadata.enabled:
            return False

        # Default:  always run if enabled
        return True

    def get_cache_key(self, latitude: float, longitude: float, **kwargs) -> str:
        """
        Generate a cache key for this provider's data.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            **kwargs: Additional parameters for cache key

        Returns:
            Cache key string
        """
        # Round coordinates to reduce cache fragmentation
        lat_rounded = round(latitude, 4)
        lon_rounded = round(longitude, 4)

        base_key = f"{self.metadata.name}:{lat_rounded}:{lon_rounded}"

        # Add additional parameters to cache key
        if kwargs:
            params = ": ".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            base_key = f"{base_key}:{params}"

        return base_key
