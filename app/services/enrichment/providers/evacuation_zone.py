"""Hurricane evacuation zone (Florida Statewide Regional Evacuation Study).

Zones A-E (A evacuates first) from the statewide study, published by the regional
planning councils and FDEM. Most counties' zones date from the 2013 study; a few were
revised later (each zone carries its edit date). Inland Central Florida mostly has no
zone, which is reported as zone None. Florida only; no key.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.integrations.arcgis_api import FL_EVACUATION_ZONES, ArcGISClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

EVACUATION_ZONES_LAYER = "Evacuation_Zones/FeatureServer/0"
FIELDS = ("EZone", "County_Nam", "Edit_Date")


class EvacuationZoneProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FL_EVACUATION_ZONES, service="FL evacuation zones")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="evacuation_zone_provider",
            category=ProviderCategory.CLIMATE,
            description="Florida hurricane evacuation zone (A-E) at the property.",
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=180,
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
        Returns:
            ProviderResult with evacuation_zone ("A"-"E", or None outside every zone),
            county and zone_edit_date
        """
        try:
            zones = await self.api_client.query_near(
                EVACUATION_ZONES_LAYER, latitude, longitude, out_fields=FIELDS
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching evacuation zone for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        # Overlapping polygons along a boundary: the earlier-evacuating zone wins
        zone = min(zones, key=lambda z: z.get("EZone") or "Z") if zones else {}
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "evacuation_zone": (zone.get("EZone") or "").strip() or None,
                "county": (zone.get("County_Nam") or "").title() or None,
                "zone_edit_date": zone.get("Edit_Date"),
            },
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True
