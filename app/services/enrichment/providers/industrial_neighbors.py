"""Industrial parcels within a quarter mile, from Florida's statewide parcels.

Every parcel on the tax roll carries the Department of Revenue's land use code, and codes
40-49 are industrial: warehouses and trucking terminals, factories, junkyards, cement and
asphalt plants. Next door they mean trucks backing up and idling at all hours, forklifts,
loading docks lit all night, and sometimes dust or fumes.

Same public, keyless ArcGIS layer as the parcel provider. Florida only.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FL_GIO, ArcGISClient
from app.utils.distance_calculator import geometry_distance_m

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from .parcel import PARCELS_LAYER

METERS_PER_MILE = 1609.344
RADIUS_M = 0.25 * METERS_PER_MILE

# DOR land use code: (description, kind)
INDUSTRIAL_USES = {
    "040": ("Vacant industrial land", "vacant"),
    "041": ("Light manufacturing", "light"),
    "042": ("Heavy industry", "heavy"),
    "043": ("Lumber yard or sawmill", "heavy"),
    "044": ("Packing plant", "light"),
    "045": ("Cannery, brewery or winery", "light"),
    "046": ("Food processing", "light"),
    "047": ("Mineral processing (cement, asphalt, rock)", "heavy"),
    "048": ("Warehouse, distribution or trucking terminal", "warehouse"),
    "049": ("Open storage (junkyard, fuel, equipment yard)", "heavy"),
}

FIELDS = ("DOR_UC", "PHY_ADDR1", "OWN_NAME", "TOT_LVG_AR")

logger = logging.getLogger(__name__)


class IndustrialNeighborsProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.api_client = ArcGISClient(FL_GIO, service="Florida parcels")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="industrial_neighbors_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description="Warehouses, factories and yards within a quarter mile (Florida).",
            version="1.0.0",
            requires_api_key=False,
            # The roll is republished every August
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
            ProviderResult with parcels within RADIUS_M, nearest first (use_code, use,
            kind: heavy, warehouse, light or vacant; address, owner, building_sqft,
            distance_m), and radius_m
        """
        codes = ", ".join(f"'{code}'" for code in INDUSTRIAL_USES)
        try:
            # The layer can't answer distance queries, so take the square around the
            # circle and measure each parcel
            found = await self.api_client.query_box(
                PARCELS_LAYER,
                latitude,
                longitude,
                RADIUS_M,
                FIELDS,
                where=f"DOR_UC IN ({codes})",
            )
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Error fetching industrial parcels for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "parcels": industrial_parcels(latitude, longitude, found),
                "radius_m": round(RADIUS_M),
            },
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def industrial_parcels(
    latitude: float, longitude: float, found: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    parcels = []
    for parcel in found:
        use = INDUSTRIAL_USES.get(parcel.get("DOR_UC"))
        geometry = parcel.get("geometry")
        if use is None or geometry is None:
            continue
        distance = geometry_distance_m(latitude, longitude, geometry)
        # 0 is the parcel the property itself is on
        if distance == 0 or distance > RADIUS_M:
            continue
        parcels.append(
            {
                "use_code": parcel["DOR_UC"],
                "use": use[0],
                "kind": use[1],
                "address": (parcel.get("PHY_ADDR1") or "").strip() or None,
                "owner": (parcel.get("OWN_NAME") or "").strip() or None,
                "building_sqft": parcel.get("TOT_LVG_AR") or None,
                "distance_m": round(distance),
            }
        )
    return sorted(parcels, key=lambda p: p["distance_m"])
