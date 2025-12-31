"""Enrichment service layer for place-research.

This module provides the core business logic for enriching places with data from multiple providers.
It serves as the interface between frontends (API, CLI) and the provider infrastructure.

The service layer:
- Orchestrates multiple providers
- Handles errors gracefully
- Returns structured results
- Manages configuration and dependencies
- Can be used by CLI, API, or other frontends
"""

import asyncio
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from .cache import CacheManager, get_cache_manager, initialize_cache
from .config import Settings
from .exceptions import EnrichmentError
from .exceptions import ProviderError as ProviderException
from .exceptions import ValidationError as PlaceValidationError
from .interfaces import PlaceProvider, PlaceRepository
from .models import Place
from .models.results import (
    AirQualityResult,
    AnnualAverageClimateResult,
    DistancesResult,
    EnrichmentResult,
    FloodZoneResult,
    HighwayResult,
    ProviderError,
    RailroadResult,
    WalkBikeScoreResult,
    WalmartResult,
)
from .providers import (
    AirQualityProvider,
    AnnualAverageClimateProvider,
    DistanceProvider,
    FloodZoneProvider,
    HighwayProvider,
    RailroadProvider,
    WalkBikeScoreProvider,
    WalmartProvider,
)
from .validation import sanitize_error_message


class PlaceEnrichmentService:
    """Service for enriching places with data from multiple providers.

    This is the main entry point for place enrichment. It:
    1. Initializes providers with configuration
    2. Runs providers in sequence (or parallel in future)
    3. Collects results and errors
    4. Returns structured EnrichmentResult

    Usage:
        from place_research.config import get_settings
        from place_research.service import PlaceEnrichmentService

        settings = get_settings()
        service = PlaceEnrichmentService(settings)
        result = service.enrich_place(place)
    """

    def __init__(
        self,
        settings: Settings,
        providers: Optional[list[PlaceProvider]] = None,
        repository: Optional[PlaceRepository] = None,
    ):
        """Initialize the enrichment service.

        Args:
            settings: Application settings (API keys, paths, etc.)
            providers: List of providers to use (default: all available)
            repository: Place repository for persistence (optional)
        """
        self.settings = settings
        self.repository = repository
        self.logger = logging.getLogger(__name__)

        # Initialize providers if not provided
        if providers is None:
            self.providers = self._initialize_default_providers()
        else:
            self.providers = providers

        # Initialize cache if enabled
        self.cache_manager: Optional[CacheManager] = None
        if settings.cache_enabled:
            self.cache_manager = self._initialize_cache()
            self.logger.info("Cache enabled with %s backend", settings.cache_backend)
        else:
            self.logger.info("Cache disabled")

        self.logger.info(
            "Initialized enrichment service with %d providers", len(self.providers)
        )

    def _initialize_default_providers(self) -> list[PlaceProvider]:
        """Initialize all available providers with configuration.

        Validates configuration and skips providers with missing config.
        """
        providers = []

        # WalkBikeScore
        if self.settings.walkscore_api_key:
            providers.append(
                WalkBikeScoreProvider(api_key=self.settings.walkscore_api_key)
            )
            self.logger.info("Enabled WalkBikeScoreProvider")
        else:
            self.logger.warning(
                "WalkBikeScoreProvider disabled: missing WALKSCORE_API_KEY"
            )

        # AirQuality
        if self.settings.airnow_api_key:
            providers.append(AirQualityProvider())  # Will update to accept config
            self.logger.info("Enabled AirQualityProvider")
        else:
            self.logger.warning("AirQualityProvider disabled: missing AIRNOW_API_KEY")

        # FloodZone
        if self.settings.national_flood_data_api_key:
            providers.append(FloodZoneProvider())  # Will update to accept config
            self.logger.info("Enabled FloodZoneProvider")
        else:
            self.logger.warning(
                "FloodZoneProvider disabled: missing NATIONAL_FLOOD_DATA_API_KEY"
            )

        # Highway (no config needed)
        providers.append(HighwayProvider())
        self.logger.info("Enabled HighwayProvider")

        # Railroad
        if self.settings.raillines_path:
            providers.append(RailroadProvider())  # Will update to accept config
            self.logger.info("Enabled RailroadProvider")
        else:
            self.logger.warning("RailroadProvider disabled: missing RAILLINES_PATH")

        # Walmart
        if self.settings.google_maps_api_key:
            providers.append(WalmartProvider())  # Will update to accept config
            self.logger.info("Enabled WalmartProvider")
        else:
            self.logger.warning("WalmartProvider disabled: missing GOOGLE_MAPS_API_KEY")

        # Distances
        if self.settings.google_maps_api_key and self.settings.distance_config_path:
            providers.append(DistanceProvider())  # Will update to accept config
            self.logger.info("Enabled DistanceProvider")
        else:
            self.logger.warning("DistanceProvider disabled: missing config")
        # AnnualAverageClimate
        if self.settings.annual_climate_path:
            providers.append(
                AnnualAverageClimateProvider()
            )  # Will update to accept config
            self.logger.info("Enabled AnnualAverageClimateProvider")
        else:
            self.logger.warning(
                "AnnualAverageClimateProvider disabled: missing ANNUAL_CLIMATE_PATH"
            )

        return providers

    def _initialize_cache(self) -> Optional[CacheManager]:
        """Initialize cache manager based on settings.

        Returns:
            CacheManager instance or None if cache is disabled
        """
        try:
            # Check if global cache manager exists
            cache_manager = get_cache_manager()
            if cache_manager:
                self.logger.debug("Using existing cache manager")
                return cache_manager

            # Initialize new cache manager
            provider_ttls = self.settings.get_provider_ttls()
            cache_manager = initialize_cache(
                backend_type=self.settings.cache_backend,
                redis_url=self.settings.redis_url,
                default_ttl=self.settings.cache_default_ttl,
                provider_ttls=provider_ttls,
            )
            self.logger.info(
                "Initialized cache: backend=%s, default_ttl=%ds, custom_ttls=%d",
                self.settings.cache_backend,
                self.settings.cache_default_ttl,
                len(provider_ttls),
            )
            return cache_manager
        except (ConnectionError, OSError, ImportError, ValueError, TypeError) as e:
            self.logger.error("Failed to initialize cache: %s", e, exc_info=True)
            return None

    async def enrich_place(self, place: Place) -> EnrichmentResult:
        """Enrich a single place with data from all enabled providers.

        Args:
            place: The place to enrich

        Returns:
            EnrichmentResult with data from all providers and any errors

        Raises:
            EnrichmentError: If enrichment fails completely (all providers fail)
        """
        # Validate place has required data (address is required by Place model)
        if not hasattr(place, "address") or not place.address:
            raise PlaceValidationError("Place must have an address", field="place")

        self.logger.info("Enriching place %s: %s", place.id or "unknown", place.address)

        result = EnrichmentResult(place_id=place.id)

        # Run all providers in parallel using asyncio.gather
        # Each provider execution is wrapped to catch and handle exceptions individually
        provider_tasks = [
            self._run_provider_with_error_handling(provider, place, result)
            for provider in self.providers
        ]

        # Execute all providers concurrently
        provider_results = await asyncio.gather(
            *provider_tasks, return_exceptions=False
        )

        # Count successful providers
        successful_providers = sum(1 for r in provider_results if r is not None)

        # Check if all providers failed
        if successful_providers == 0 and len(self.providers) > 0:
            raise EnrichmentError(
                "All providers failed to enrich place", place_id=place.id
            )

        self.logger.info(
            "Enrichment complete for place %s. Success: %d/%d, Errors: %d",
            place.id,
            successful_providers,
            len(self.providers),
            len(result.errors),
        )
        return result

    async def _run_provider_with_error_handling(
        self, provider: PlaceProvider, place: Place, result: EnrichmentResult
    ) -> Optional[Any]:
        """Run a provider and handle all errors, updating the result object.

        This method wraps _run_provider to catch exceptions and store them
        in the result.errors list instead of propagating them.

        Args:
            provider: The provider to run
            place: The place to enrich
            result: The EnrichmentResult to update with data or errors

        Returns:
            The provider result if successful, None otherwise
        """
        try:
            self.logger.debug("Running provider: %s", provider.name)
            provider_result = await self._run_provider(provider, place)

            # Store result in appropriate field
            if provider_result:
                self._store_provider_result(provider_result, result)
                self.logger.debug("Provider %s completed successfully", provider.name)
                return provider_result

        except ProviderException as e:
            # Known provider exception
            self.logger.warning("Provider %s failed: %s", provider.name, e.message)
            result.errors.append(
                ProviderError(
                    provider_name=provider.name,
                    error_message=sanitize_error_message(e.message),
                    error_type=e.error_code,
                )
            )
        except TimeoutError as e:
            # Timeout exception
            self.logger.warning("Provider %s timed out: %s", provider.name, e)
            result.errors.append(
                ProviderError(
                    provider_name=provider.name,
                    error_message="Provider request timed out",
                    error_type="PROVIDER_TIMEOUT",
                )
            )
        except (
            ConnectionError,
            ValueError,
            KeyError,
            TypeError,
        ) as e:
            self.logger.error(
                "Error in provider %s: %s", provider.name, e, exc_info=True
            )
            result.errors.append(
                ProviderError(
                    provider_name=provider.name,
                    error_message=sanitize_error_message(str(e)),
                    error_type="PROVIDER_ERROR",
                )
            )
        except (OSError, RuntimeError, ImportError) as e:
            # Handle other specific common exceptions that might occur
            self.logger.error(
                "Unexpected error in provider %s: %s",
                provider.name,
                e,
                exc_info=True,
            )
            result.errors.append(
                ProviderError(
                    provider_name=provider.name,
                    error_message=sanitize_error_message(str(e)),
                    error_type="PROVIDER_ERROR",
                )
            )

        return None

    async def _run_provider(
        self, provider: PlaceProvider, place: Place
    ) -> Optional[Any]:
        """Run a single provider and return its result.

        Handles both legacy providers (that mutate place) and new providers (that return Results).
        Checks cache before running provider and caches results after.
        """
        start_time = time.perf_counter()

        # Check cache if enabled and place has coordinates
        if (
            self.cache_manager
            and hasattr(place, "latitude")
            and hasattr(place, "longitude")
        ):
            try:
                cached_result = await self.cache_manager.get_provider_result(
                    provider.name,
                    place.latitude,
                    place.longitude,
                )
                if cached_result:
                    if self.settings.log_cache_operations:
                        self.logger.info(
                            "Cache hit for %s",
                            provider.name,
                            extra={
                                "provider": provider.name,
                                "event": "cache_hit",
                            },
                        )
                    # Reconstruct result object from cached dict
                    result = self._deserialize_provider_result(
                        provider.name, cached_result
                    )

                    # Log metrics if enabled
                    if self.settings.log_provider_metrics:
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        self.logger.info(
                            "Provider %s completed (cached) in %.2fms",
                            provider.name,
                            duration_ms,
                            extra={
                                "provider": provider.name,
                                "event": "provider_completed",
                                "duration_ms": duration_ms,
                                "cache_hit": True,
                            },
                        )

                    return result
            except (
                ConnectionError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                OSError,
                RuntimeError,
            ) as e:
                self.logger.warning(
                    "Cache lookup failed for %s: %s",
                    provider.name,
                    e,
                    extra={
                        "provider": provider.name,
                        "event": "cache_error",
                        "error": str(e),
                    },
                )

        # Run provider
        if self.settings.log_provider_metrics:
            self.logger.info(
                "Fetching data from %s",
                provider.name,
                extra={
                    "provider": provider.name,
                    "event": "provider_started",
                },
            )

        try:
            provider_result = await provider.fetch_place_data(place)
        except (
            ProviderException,
            TimeoutError,
            ConnectionError,
            ValueError,
            KeyError,
            TypeError,
            OSError,
            RuntimeError,
            ImportError,
        ) as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Provider %s failed after %.2fms: %s",
                provider.name,
                duration_ms,
                e,
                extra={
                    "provider": provider.name,
                    "event": "provider_failed",
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

        # Cache result if enabled and place has coordinates
        if (
            provider_result is not None
            and self.cache_manager
            and hasattr(place, "latitude")
            and hasattr(place, "longitude")
        ):
            try:
                # Serialize result for caching
                serializable_result = self._serialize_provider_result(provider_result)
                await self.cache_manager.set_provider_result(
                    provider.name,
                    place.latitude,
                    place.longitude,
                    serializable_result,
                )
                if self.settings.log_cache_operations:
                    self.logger.info(
                        "Cached result for %s",
                        provider.name,
                        extra={
                            "provider": provider.name,
                            "event": "cache_set",
                        },
                    )
            except (
                ConnectionError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                OSError,
                RuntimeError,
            ) as e:
                self.logger.warning(
                    "Failed to cache result for %s: %s",
                    provider.name,
                    e,
                    extra={
                        "provider": provider.name,
                        "event": "cache_error",
                        "error": str(e),
                    },
                )

        # Log metrics if enabled
        if self.settings.log_provider_metrics:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                "Provider %s completed in %.2fms",
                provider.name,
                duration_ms,
                extra={
                    "provider": provider.name,
                    "event": "provider_completed",
                    "duration_ms": duration_ms,
                    "cache_hit": False,
                },
            )

        # If provider returned a result object, use it
        if provider_result is not None:
            return provider_result
        else:
            # Legacy provider - no result returned
            self.logger.debug(
                "Provider %s did not return a result object.", provider.name
            )
            return None

    def _serialize_provider_result(self, result: Any) -> dict:
        """Serialize a provider result for caching."""
        if hasattr(result, "to_dict"):
            return result.to_dict()
        elif hasattr(result, "model_dump"):
            return result.model_dump()
        elif is_dataclass(result):
            # Handle dataclass results
            return asdict(result)  # type: ignore
        else:
            # Fallback for simple types
            return {"data": result}

    def _deserialize_provider_result(
        self, provider_name: str, cached_data: dict
    ) -> Any:
        """Deserialize a cached provider result back to result object."""
        # Map provider names to result classes
        # Provider names are lowercase without underscores (e.g., "walkbikescore", "airquality")
        result_classes = {
            "walkbikescore": WalkBikeScoreResult,
            "airquality": AirQualityResult,
            "floodzone": FloodZoneResult,
            "highway": HighwayResult,
            "railroad": RailroadResult,
            "walmart": WalmartResult,
            "distance": DistancesResult,
            "annualaverageclimate": AnnualAverageClimateResult,
        }

        result_class = result_classes.get(provider_name)
        if result_class:
            try:
                # Check if the result class has a from_dict() class method
                if hasattr(result_class, "from_dict"):
                    return result_class.from_dict(cached_data)
                else:
                    # Standard dataclass construction
                    return result_class(**cached_data)
            except (TypeError, ValueError, AttributeError) as e:
                self.logger.warning(
                    "Failed to deserialize cached result for %s: %s", provider_name, e
                )
                return None
        else:
            self.logger.warning(
                "Unknown provider for deserialization: %s", provider_name
            )
            return None

    def _store_provider_result(self, provider_result: Any, result: EnrichmentResult):
        """Store a provider's result in the appropriate field of EnrichmentResult."""
        if isinstance(provider_result, WalkBikeScoreResult):
            result.walk_bike_score = provider_result
        elif isinstance(provider_result, AirQualityResult):
            result.air_quality = provider_result
        elif isinstance(provider_result, FloodZoneResult):
            result.flood_zone = provider_result
        elif isinstance(provider_result, HighwayResult):
            result.highway = provider_result
        elif isinstance(provider_result, RailroadResult):
            result.railroad = provider_result
        elif isinstance(provider_result, WalmartResult):
            result.walmart = provider_result
        elif isinstance(provider_result, DistancesResult):
            result.distances = provider_result
        elif isinstance(provider_result, AnnualAverageClimateResult):
            result.climate = provider_result

    async def enrich_and_save(self, place: Place) -> EnrichmentResult:
        """Enrich a place and save it to the repository.

        Args:
            place: The place to enrich and save

        Returns:
            EnrichmentResult

        Raises:
            ValueError: If no repository is configured
        """
        if not self.repository:
            raise ValueError("No repository configured for saving")

        result = await self.enrich_place(place)

        # Save to repository
        self.repository.save(place)
        self.logger.info("Saved enriched place %s", place.id)

        return result

    def get_enabled_providers(self) -> list[str]:
        """Get list of enabled provider names."""
        return [p.name for p in self.providers]

    def get_provider_status(self) -> dict[str, dict]:
        """Get status of all providers (enabled/disabled and why).

        Returns:
            Dictionary mapping provider names to status info
        """
        status = {}

        all_providers = [
            ("WalkBikeScoreProvider", ["WALKSCORE_API_KEY"]),
            ("AirQualityProvider", ["AIRNOW_API_KEY"]),
            ("FloodZoneProvider", ["NATIONAL_FLOOD_DATA_API_KEY"]),
            ("HighwayProvider", []),
            ("RailroadProvider", ["RAILLINES_PATH"]),
            ("WalmartProvider", ["GOOGLE_MAPS_API_KEY"]),
            (
                "DistanceProvider",
                ["GOOGLE_MAPS_API_KEY", "DISTANCE_CONFIG_PATH"],
            ),
            ("AnnualAverageClimateProvider", ["ANNUAL_CLIMATE_PATH"]),
        ]

        enabled_names = self.get_enabled_providers()

        for provider_name, required_config in all_providers:
            simple_name = provider_name.lower().replace("provider", "")
            is_enabled = simple_name in enabled_names

            missing = []
            for config_key in required_config:
                if not getattr(self.settings, config_key.lower(), None):
                    missing.append(config_key)

            status[simple_name] = {
                "enabled": is_enabled,
                "required_config": required_config,
                "missing_config": missing,
            }

        return status
