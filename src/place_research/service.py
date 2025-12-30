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

import logging
from typing import Optional, Any

from .config import Settings
from .models import Place
from .models.results import (
    EnrichmentResult,
    ProviderError,
    WalkBikeScoreResult,
    AirQualityResult,
    FloodZoneResult,
    HighwayResult,
    RailroadResult,
    WalmartResult,
    DistancesResult,
    AnnualAverageClimateResult,
)
from .interfaces import PlaceProvider, PlaceRepository
from .providers import (
    WalkBikeScoreProvider,
    AirQualityProvider,
    FloodZoneProvider,
    HighwayProvider,
    RailroadProvider,
    WalmartProvider,
    DistanceProvider,
    AnnualAverageClimateProvider,
)


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

    def enrich_place(self, place: Place) -> EnrichmentResult:
        """Enrich a single place with data from all enabled providers.

        Args:
            place: The place to enrich

        Returns:
            EnrichmentResult with data from all providers and any errors
        """
        self.logger.info("Enriching place %s: %s", place.id or "unknown", place.address)

        result = EnrichmentResult(place_id=place.id)

        # Run each provider and collect results
        for provider in self.providers:
            try:
                self.logger.debug("Running provider: %s", provider.name)
                provider_result = self._run_provider(provider, place)

                # Store result in appropriate field
                # (This is a temporary bridge - will be cleaner when all providers return Results)
                if provider_result:
                    self._store_provider_result(provider_result, result)

            except (
                ConnectionError,
                TimeoutError,
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
                        error_message=str(e),
                        error_type="PROVIDER_ERROR",
                    )
                )

        self.logger.info(
            "Enrichment complete for place %s. Errors: %d", place.id, len(result.errors)
        )
        return result

    def _run_provider(self, provider: PlaceProvider, place: Place) -> Optional[Any]:
        """Run a single provider and return its result.

        Handles both legacy providers (that mutate place) and new providers (that return Results).
        """
        provider_result = provider.fetch_place_data(place)

        # If provider returned a result object, use it
        if provider_result is not None:
            return provider_result
        else:
            # Legacy provider - no result returned
            self.logger.debug(
                "Provider %s did not return a result object.", provider.name
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

    def enrich_and_save(self, place: Place) -> EnrichmentResult:
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

        result = self.enrich_place(place)

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
