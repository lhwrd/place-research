"""Drive time to the nearest beach parking.

Uses the list bundled with the app (app/data/beach_parking.csv, built from FDEP's Coastal
Access Sites by scripts/build_beach_parking.py): public Gulf and Atlantic beach accesses
in Florida that have parking. The closest access at each of the few nearest beaches is
sent to Google's Distance Matrix, since the nearest beach in a straight line can be the
longer drive (a causeway, a lagoon or a national seashore gate in between).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.integrations.google_maps_api import GoogleMapsAPI

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from .airports import _haversine

BEACH_PARKING_CSV = Path(__file__).resolve().parents[3] / "data" / "beach_parking.csv"

METERS_PER_MILE = 1609.344
# Farther than this in a straight line (out of state, in practice) and it isn't looked up
SEARCH_RADIUS_M = 150 * METERS_PER_MILE
# Beaches to compare drive times for; each is one billed Distance Matrix element
MAX_BEACHES = 10

logger = logging.getLogger(__name__)


class BeachParkingProvider(BaseEnrichmentProvider):
    _shared_sites: Optional[pd.DataFrame] = None

    def __init__(self, sites: Optional[pd.DataFrame] = None):
        """
        Args:
            sites: Beach parking table (tests); defaults to the bundled list.
        """
        if sites is None:
            if BeachParkingProvider._shared_sites is None:
                BeachParkingProvider._shared_sites = pd.read_csv(
                    BEACH_PARKING_CSV, keep_default_na=False
                )
            sites = BeachParkingProvider._shared_sites
        self._sites = sites.reset_index(drop=True)
        self._lat = np.radians(self._sites["latitude"].astype(float))
        self._lon = np.radians(self._sites["longitude"].astype(float))
        self.api_client = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="beach_parking_provider",
            category=ProviderCategory.DISTANCES,
            description="Drive time to the nearest Florida beach access with parking.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.005 * MAX_BEACHES,
            cache_duration_days=365,
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
            ProviderResult with sites: one access per nearby beach, shortest drive first
            (name, beach, county, coast, address, spaces, fee, latitude, longitude,
            straight_line_m, drive_minutes, drive_miles). Empty if no beach is in range.
        """
        candidates = self.candidates(latitude, longitude)
        if not candidates:
            return ProviderResult(
                provider_name=self.metadata.name, data={"sites": []}, success=True
            )

        try:
            results = await self.api_client.distance_matrix(
                origin=(latitude, longitude),
                destinations=[(c["latitude"], c["longitude"]) for c in candidates],
                mode="driving",
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error fetching beach drive times for %s: %s", address, e)
            return self._failed(str(e))

        for result in results:
            index = result.get("destination_index")
            if result.get("status") != "OK" or index is None or index >= len(candidates):
                continue
            candidates[index]["drive_minutes"] = result.get("duration_minutes")
            candidates[index]["drive_miles"] = result.get("distance_miles")
        sites = sorted(
            (c for c in candidates if c.get("drive_minutes") is not None),
            key=lambda c: c["drive_minutes"],
        )
        if not sites:
            return self._failed("No drive time to any nearby beach")
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"sites": sites},
            success=True,
            api_calls_made=1,
        )

    def candidates(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """The closest access (straight line) at each of the MAX_BEACHES nearest beaches."""
        if self._sites.empty:
            return []
        distances = _haversine(np.radians(latitude), np.radians(longitude), self._lat, self._lon)
        found: List[Dict[str, Any]] = []
        beaches = set()
        for i in np.argsort(distances):
            if distances[i] > SEARCH_RADIUS_M or len(found) == MAX_BEACHES:
                break
            row = self._sites.iloc[i]
            beach = (row["county"], row["beach"] or row["name"])
            if beach in beaches:
                continue
            beaches.add(beach)
            found.append(
                {
                    "name": row["name"],
                    "beach": row["beach"] or None,
                    "county": row["county"],
                    "coast": row["coast"],
                    "address": row["address"] or None,
                    "spaces": int(row["spaces"]) if str(row["spaces"]).strip() else None,
                    "fee": row["fee"] or None,
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "straight_line_m": int(round(distances[i])),
                }
            )
        return found

    def _failed(self, message: str) -> ProviderResult:
        return ProviderResult(
            provider_name=self.metadata.name,
            data={},
            success=False,
            error_message=message,
            api_calls_made=1,
        )

    async def validate_config(self) -> bool:
        return await self.api_client.validate_api_key()
