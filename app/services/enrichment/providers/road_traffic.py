"""How busy the road at the property is (FDOT annual average daily traffic).

FDOT publishes a traffic count for every state road and for the local roads it counts:
collectors and arterials, not residential streets. So a house with no counted road beside
it is on a street too minor to count, which is the good answer. The highway provider and
the noise model deal with interstates farther off; this is about the road out front.

Segments carry the cross streets they run between, not the road's own name. Florida only;
no key.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FDOT_TDA, ArcGISClient
from app.utils.distance_calculator import geometry_distance_m

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

AADT_LAYER = "Annual_Average_Daily_Traffic_TDA/FeatureServer/0"
FIELDS = ("COSITE", "ROADWAY", "DESC_FRM", "DESC_TO", "AADT", "YEAR_")

# Counted roads this close are listed
SEARCH_RADIUS_M = 200
MAX_ROADS = 4


class RoadTrafficProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FDOT_TDA, service="FDOT traffic counts")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="road_traffic_provider",
            category=ProviderCategory.NOISE,
            description="Daily traffic on the counted roads within 200 m (FDOT AADT).",
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=365,  # counts are published once a year
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
            ProviderResult with roads, nearest first (at most 4): from_street, to_street,
            vehicles_per_day, year and distance_m
        """
        try:
            features = await self.api_client.query_near(
                AADT_LAYER, latitude, longitude, SEARCH_RADIUS_M, FIELDS, geometry=True
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching traffic counts for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"roads": summarize_roads(latitude, longitude, features)},
            success=True,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return True


def summarize_roads(
    latitude: float, longitude: float, features: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    roads = sorted(
        (
            {
                "from_street": _street(f.get("DESC_FRM")),
                "to_street": _street(f.get("DESC_TO")),
                "vehicles_per_day": int(f["AADT"]),
                "year": f.get("YEAR_"),
                "distance_m": round(geometry_distance_m(latitude, longitude, f["geometry"])),
                "_site": f.get("COSITE"),
            }
            for f in features
            if f.get("geometry") is not None and f.get("AADT")
        ),
        key=lambda r: r["distance_m"],
    )
    # One count station can cover several segments, and overlapping route numbers repeat it
    seen, unique = set(), []
    for road in roads:
        site = road.pop("_site") or (road["from_street"], road["to_street"])
        if site not in seen:
            seen.add(site)
            unique.append(road)
    return unique[:MAX_ROADS]


def _street(text: Optional[str]) -> Optional[str]:
    """ "SR-426/FAIRBANKS AVE" -> "SR-426/Fairbanks Ave"; route numbers stay upper case."""
    words = " ".join((text or "").split())
    if not words:
        return None
    return "/".join(
        part if any(c.isdigit() for c in part) else part.title() for part in words.split("/")
    )
