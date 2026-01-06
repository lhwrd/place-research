import logging
from typing import Any, Dict, Optional

from app.integrations.flood_zone_api import FloodZoneAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class FloodZoneProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = FloodZoneAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="flood_zone_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides flood zone and risk information using National Flood Data API.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.002,  # Estimated cost per API call
        )

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

        try:
            data = await self.api_client.fetch_flood_zone_data(latitude, longitude, address)
            return ProviderResult(
                provider_name=self.metadata.name,
                data=data,
                success=True,
                api_calls_made=1,
            )
        except (ValueError, ConnectionError, TimeoutError) as e:
            self.logger.error(
                f"Error fetching flood zone data for {address} ({latitude}, {longitude}): {e}"
            )
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

    async def validate_config(self) -> bool:
        """Validate that the API key is set and valid."""
        is_valid = await self.api_client.validate_api_key()
        return is_valid
