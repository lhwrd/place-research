"""Sinkhole risk from the Florida Geological Survey (via FDEP's open data server).

Two FGS datasets, both public and keyless:
- Sinkhole favorability: a statewide model of how favorable the geology is to sinkhole
  formation, in four classes (least favorable to most favorable).
- Subsidence incident reports: holes and depressions people have reported. Most are not
  verified by a geologist as true sinkholes, so the count is a signal, not a diagnosis.

Florida only; elsewhere both come back empty.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.integrations.arcgis_api import FDEP_OPEN_DATA, ArcGISClient
from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

FAVORABILITY_SERVICE = "OpenData/FGS_FAV_SINK_FORMATION/ImageServer"
INCIDENTS_LAYER = "OpenData/FGS_SUBSIDENCE/MapServer/0"

METERS_PER_MILE = 1609.344
SEARCH_RADIUS_M = 1 * METERS_PER_MILE

# The favorability raster's values 1-14 group into four classes (its attribute table)
FAVORABILITY_CLASSES = [
    (7, "Least favorable"),
    (10, "Favorable"),
    (12, "More favorable"),
    (14, "Most favorable"),
]

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

INCIDENT_FIELDS = ("REF_NUM", "EVENT_DATE", "TRUE_SINK", "LATDD", "LONGDD", "SINDEPTH")


class SinkholeProvider(BaseEnrichmentProvider):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_client = ArcGISClient(FDEP_OPEN_DATA, service="FDEP sinkholes")

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="sinkhole_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            description=(
                "Florida Geological Survey sinkhole favorability at the property and "
                "reported subsidence incidents within a mile."
            ),
            version="1.0.0",
            requires_api_key=False,
            cache_duration_days=90,
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
            ProviderResult with favorability (class name or None outside Florida),
            favorability_value (1-14), incidents_within_1mi, incidents_within_half_mi,
            verified_within_1mi, nearest_incident_m and nearest_incident_year
        """
        try:
            value, incidents = await asyncio.gather(
                self.api_client.sample(FAVORABILITY_SERVICE, latitude, longitude),
                self.api_client.query_near(
                    INCIDENTS_LAYER, latitude, longitude, SEARCH_RADIUS_M, INCIDENT_FIELDS
                ),
            )
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Error fetching sinkhole data for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=2,
            )

        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "favorability": favorability_class(value),
                "favorability_value": int(value) if value is not None else None,
                **summarize_incidents(latitude, longitude, incidents),
            },
            success=True,
            api_calls_made=2,
        )

    async def validate_config(self) -> bool:
        return True


def favorability_class(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    for upper, name in FAVORABILITY_CLASSES:
        if value <= upper:
            return name
    return None


def summarize_incidents(
    latitude: float, longitude: float, incidents: List[Dict[str, Any]]
) -> Dict[str, Any]:
    located = [
        (haversine_distance(latitude, longitude, i["LATDD"], i["LONGDD"]), i)
        for i in incidents
        if i.get("LATDD") is not None and i.get("LONGDD") is not None
    ]
    located.sort(key=lambda pair: pair[0])
    nearest = located[0] if located else None
    return {
        "incidents_within_1mi": len(located),
        "incidents_within_half_mi": sum(1 for d, _ in located if d <= METERS_PER_MILE / 2),
        "verified_within_1mi": sum(1 for _, i in located if i.get("TRUE_SINK") == "Y"),
        "nearest_incident_m": round(nearest[0]) if nearest else None,
        "nearest_incident_year": _year(nearest[1].get("EVENT_DATE")) if nearest else None,
    }


def _year(epoch_ms: Any) -> Optional[int]:
    """ArcGIS dates are milliseconds since 1970 (negative before)."""
    if epoch_ms is None:
        return None
    return (EPOCH + timedelta(milliseconds=epoch_ms)).year
