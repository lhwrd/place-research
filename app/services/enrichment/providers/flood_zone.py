import logging
from typing import Any, Dict, Optional

import httpx

from app.integrations.fema_nfhl_api import FemaNfhlAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)


class FloodZoneProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = FemaNfhlAPIClient()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="flood_zone_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Provides the FEMA flood hazard zone from the National Flood Hazard Layer.",
            version="2.0.0",
            requires_api_key=False,
            cost_per_call=0.0,
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
        Enrich property with its FEMA flood hazard zone.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Property address
            property_data: Additional property information
            user_preferences: User-specific preferences

        Returns:
            ProviderResult with flood_zone, flood_risk, in_sfha and base_flood_elevation_ft
        """
        try:
            data = await self.api_client.get_flood_zone(latitude, longitude)
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error(
                "Error fetching FEMA flood zone for %s (%s, %s): %s",
                address,
                latitude,
                longitude,
                e,
            )
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data=data,
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        """Validate that the FEMA service is reachable."""
        return await self.api_client.validate_api_key()
