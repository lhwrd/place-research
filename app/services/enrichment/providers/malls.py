"""Drive time to the nearest healthy mall, and any dying malls close by.

Uses the hand-kept list bundled with the app (app/data/malls.csv; coordinates filled in by
scripts/locate_malls.py): Florida's regional malls and big shopping centers, each marked
thriving, healthy, struggling, dead or redeveloping. The two ends matter at different
scales. A healthy mall is somewhere to drive to, so the few nearest are sent to Google's
Distance Matrix. A dying one mostly hurts the blocks around it (empty lots, vacant boxes,
crime), so only how far it is in a straight line counts. Malls being rebuilt are left out
of both: what they turn into isn't known yet.
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

MALLS_CSV = Path(__file__).resolve().parents[3] / "data" / "malls.csv"

HEALTHY = ("thriving", "healthy")
DECLINING = ("struggling", "dead")

METERS_PER_MILE = 1609.344
# Healthy malls farther than this in a straight line aren't looked up
HEALTHY_RADIUS_M = 60 * METERS_PER_MILE
# Healthy malls to compare drive times for; each is one billed Distance Matrix element
MAX_HEALTHY = 5
# Dying malls farther than this don't touch the neighborhood
DECLINING_RADIUS_M = 3 * METERS_PER_MILE

logger = logging.getLogger(__name__)


class MallsProvider(BaseEnrichmentProvider):
    _shared_malls: Optional[pd.DataFrame] = None

    def __init__(self, malls: Optional[pd.DataFrame] = None):
        """
        Args:
            malls: Mall table (tests); defaults to the bundled list.
        """
        if malls is None:
            if MallsProvider._shared_malls is None:
                MallsProvider._shared_malls = pd.read_csv(MALLS_CSV, keep_default_na=False)
            malls = MallsProvider._shared_malls
        self._malls = malls.reset_index(drop=True)
        self._lat = np.radians(self._malls["latitude"].astype(float))
        self._lon = np.radians(self._malls["longitude"].astype(float))
        self.api_client = GoogleMapsAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="malls_provider",
            category=ProviderCategory.DISTANCES,
            description="Drive to the nearest healthy mall and dying malls nearby (Florida).",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.005 * MAX_HEALTHY,
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
            ProviderResult with
            - healthy: the nearest thriving or healthy malls, shortest drive first
            - declining: struggling or dead malls within DECLINING_RADIUS_M, nearest first
            Each mall has name, city, kind, status, note, latitude, longitude and
            straight_line_m; healthy ones also drive_minutes and drive_miles.
        """
        nearby = self.nearby(latitude, longitude)
        declining = [m for m in nearby if m["status"] in DECLINING]
        declining = [m for m in declining if m["straight_line_m"] <= DECLINING_RADIUS_M]
        healthy = [m for m in nearby if m["status"] in HEALTHY]
        healthy = [m for m in healthy if m["straight_line_m"] <= HEALTHY_RADIUS_M][:MAX_HEALTHY]
        if not healthy:
            return ProviderResult(
                provider_name=self.metadata.name,
                data={"healthy": [], "declining": declining},
                success=True,
            )

        try:
            results = await self.api_client.distance_matrix(
                origin=(latitude, longitude),
                destinations=[(m["latitude"], m["longitude"]) for m in healthy],
                mode="driving",
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error fetching mall drive times for %s: %s", address, e)
            return self._failed(str(e))

        for result in results:
            index = result.get("destination_index")
            if result.get("status") != "OK" or index is None or index >= len(healthy):
                continue
            healthy[index]["drive_minutes"] = result.get("duration_minutes")
            healthy[index]["drive_miles"] = result.get("distance_miles")
        reached = sorted(
            (m for m in healthy if m.get("drive_minutes") is not None),
            key=lambda m: m["drive_minutes"],
        )
        if not reached:
            return self._failed("No drive time to any nearby mall")
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"healthy": reached, "declining": declining},
            success=True,
            api_calls_made=1,
        )

    def nearby(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """Every listed mall, nearest (straight line) first."""
        if self._malls.empty:
            return []
        distances = _haversine(np.radians(latitude), np.radians(longitude), self._lat, self._lon)
        return [
            {
                "name": row["name"],
                "city": row["city"],
                "kind": row["kind"],
                "status": row["status"],
                "note": row["note"] or None,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "straight_line_m": int(round(distances[i])),
            }
            for i in np.argsort(distances)
            for row in (self._malls.iloc[i],)
        ]

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
