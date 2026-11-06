"""FEMA National Flood Hazard Layer (NFHL) client.

Queries FEMA's public ArcGIS service for the flood hazard zone at a point. No API key.
https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer
"""

import logging
from typing import Any, Dict, Optional

from .base_client import BaseAPIClient, send_with_retry

logger = logging.getLogger(__name__)

# Layer 28 is "Flood Hazard Zones" (the S_FLD_HAZ_AR polygons)
FLOOD_HAZARD_ZONES_LAYER = 28

# FEMA uses -9999 for "no value" in numeric fields
NO_VALUE = -9999

NOT_MAPPED = "Not mapped"


class FemaNfhlAPIClient(BaseAPIClient):
    """Flood zone lookups against FEMA's NFHL map service."""

    def __init__(self):
        super().__init__(
            base_url="https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer",
            api_key=None,
            timeout=30.0,
            rate_limit_per_second=5.0,
        )

    def _get_service_name(self) -> str:
        return "fema_nfhl"

    async def validate_api_key(self) -> bool:
        """No key is needed; check the service answers for a known mapped point."""
        try:
            zone = await self.get_flood_zone(latitude=39.74, longitude=-104.99)
        except Exception:  # pylint: disable=broad-except
            return False
        return zone.get("flood_zone") not in (None, NOT_MAPPED)

    async def get_flood_zone(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Look up the flood hazard zone containing a point.

        Returns:
            {"flood_zone", "flood_risk", "in_sfha", "base_flood_elevation_ft"}. flood_zone is
            "Not mapped" where FEMA has no flood map, and the other fields are then None.

        Raises:
            httpx.HTTPError: If the service can't be reached or returns an HTTP error
            ValueError: If the service returns an ArcGIS error body
        """
        params = {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
            "returnGeometry": "false",
            "f": "json",
        }
        url = f"{self.base_url}/{FLOOD_HAZARD_ZONES_LAYER}/query"

        # The service intermittently resets connections; retries usually succeed
        response = await send_with_retry(
            lambda: self.client.get(url, params=params), service="FEMA NFHL"
        )
        response.raise_for_status()
        data = response.json()

        # ArcGIS reports query errors with HTTP 200 and an "error" body
        if "error" in data:
            raise ValueError(f"FEMA NFHL query failed: {data['error'].get('message')}")

        zones = [feature["attributes"] for feature in data.get("features", [])]
        if not zones:
            logger.info("No FEMA flood map at (%.6f, %.6f)", latitude, longitude)
            return {
                "flood_zone": NOT_MAPPED,
                "flood_risk": None,
                "in_sfha": None,
                "base_flood_elevation_ft": None,
            }

        # Overlapping polygons (e.g. along a zone boundary): report the riskiest
        zone = max(zones, key=_risk_rank)
        return {
            "flood_zone": zone.get("FLD_ZONE"),
            "flood_risk": zone.get("ZONE_SUBTY") or None,
            "in_sfha": zone.get("SFHA_TF") == "T",
            "base_flood_elevation_ft": _value(zone.get("STATIC_BFE")),
        }


def _risk_rank(zone: Dict[str, Any]) -> tuple:
    """Higher is riskier: SFHA first, then coastal V zones, then the 0.2% (moderate) X zone."""
    fld_zone = str(zone.get("FLD_ZONE") or "")
    subtype = str(zone.get("ZONE_SUBTY") or "")
    return (zone.get("SFHA_TF") == "T", fld_zone.startswith("V"), "0.2 PCT" in subtype)


def _value(number: Optional[float]) -> Optional[float]:
    return None if number is None or number <= NO_VALUE else number
