"""Active contamination cleanup sites near the property (FDEP Contamination Locator).

FDEP's "DEP Cleanup Sites" layer lists open and active waste cleanups statewide: leaking
petroleum tanks, dry cleaners, brownfields, Superfund and federal sites, PFAS. Closed
cleanups are not in it. Florida only; no key.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FDEP_OPEN_DATA, ArcGISClient
from app.utils.distance_calculator import geometry_distance_m

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

CLEANUP_SITES_LAYER = "OpenData/CLEANUP_SP/MapServer/0"

METERS_PER_MILE = 1609.344
SEARCH_RADIUS_M = 0.5 * METERS_PER_MILE
MAX_SITES = 5

CATEGORIES = {
    "PETRO": "Petroleum",
    "OTHCU": "Hazardous waste / dry cleaner",
    "BROWN": "Brownfield",
    "SUPER": "Superfund",
    "FED": "Federal facility",
    "PFAS": "PFAS",
}

FIELDS = (
    "BUSINESS_NAME",
    "ADDRESS1",
    "CLCC_CLEANUP_CATEGORY_KEY",
    "RSC2_REMEDIATION_STATUS_KEY",
    "DOCUMENTS",
)


class ContaminationProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FDEP_OPEN_DATA, service="FDEP cleanup sites")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="contamination_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description="Open FDEP contamination cleanup sites within half a mile.",
            version="1.0.0",
            requires_api_key=False,
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
            ProviderResult with sites_within_half_mi, sites_within_quarter_mi,
            superfund_within_half_mi and sites (nearest first, at most 5: name, address,
            category, status, distance_m, documents_url)
        """
        try:
            features = await self.api_client.query_near(
                CLEANUP_SITES_LAYER, latitude, longitude, SEARCH_RADIUS_M, FIELDS, geometry=True
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching cleanup sites for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data=summarize_sites(latitude, longitude, features),
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def summarize_sites(
    latitude: float, longitude: float, features: List[Dict[str, Any]]
) -> Dict[str, Any]:
    sites = sorted(
        (
            {
                "name": (f.get("BUSINESS_NAME") or "").strip() or None,
                "address": (f.get("ADDRESS1") or "").strip() or None,
                "category": CATEGORIES.get(
                    f.get("CLCC_CLEANUP_CATEGORY_KEY"), f.get("CLCC_CLEANUP_CATEGORY_KEY")
                ),
                "status": (f.get("RSC2_REMEDIATION_STATUS_KEY") or "").title() or None,
                "distance_m": round(geometry_distance_m(latitude, longitude, f["geometry"])),
                "documents_url": f.get("DOCUMENTS"),
            }
            for f in features
            if f.get("geometry") is not None
        ),
        key=lambda s: s["distance_m"],
    )
    return {
        "sites_within_half_mi": len(sites),
        "sites_within_quarter_mi": sum(1 for s in sites if s["distance_m"] <= METERS_PER_MILE / 4),
        "superfund_within_half_mi": sum(1 for s in sites if s["category"] == "Superfund"),
        "sites": sites[:MAX_SITES],
    }
