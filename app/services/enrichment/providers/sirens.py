"""Fire stations and helipads close by: sirens and rotor noise at any hour.

- Fire stations (Google Places): engines and ambulances leave with sirens on, day and
  night, and a station within a few blocks is heard on most calls.
- Heliports (app/data/heliports.csv, from OurAirports by scripts/build_heliports.py):
  hospital pads take medical helicopters at short notice, police and fire pads fly
  patrols, and tour operators fly all day.

The nearest emergency room, the other big source of sirens, comes from the emergency
room provider; the property page puts the three together.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.integrations.google_places_api import GooglePlacesAPI
from app.utils.distance_calculator import haversine_distance

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)
from .airports import _haversine

HELIPORTS_CSV = Path(__file__).resolve().parents[3] / "data" / "heliports.csv"

METERS_PER_MILE = 1609.344
RADIUS_MILES = 1.0
# Asked for: Places files records offices, union halls and even law firms as fire
# stations, so ask for a few more than are kept
FIRE_STATION_RESULTS = 6
# What a firehouse is named: "Station 5", "Fire Rescue 51", "FS 12", "Engine 3"
FIREHOUSE_NAME = re.compile(
    r"station|\bFS\s*#?\d|fire[- ](rescue|department|dept)|\bengine\b|\bladder\b|volunteer",
    re.IGNORECASE,
)
NOT_A_FIREHOUSE = re.compile(
    r"records|reports|lawsuit|attorney|law\b|headquarters|admin|training|academy|museum|"
    r"prevention|marshal|union|association|foundation|supply|equipment",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


class SirensProvider(BaseEnrichmentProvider):
    _shared_heliports: Optional[pd.DataFrame] = None

    def __init__(self, heliports: Optional[pd.DataFrame] = None):
        """
        Args:
            heliports: Heliport table (tests); defaults to the bundled list.
        """
        if heliports is None:
            if SirensProvider._shared_heliports is None:
                SirensProvider._shared_heliports = pd.read_csv(HELIPORTS_CSV, keep_default_na=False)
            heliports = SirensProvider._shared_heliports
        self._heliports = heliports.reset_index(drop=True)
        self._lat = np.radians(self._heliports["latitude"].astype(float))
        self._lon = np.radians(self._heliports["longitude"].astype(float))
        self.places_api = GooglePlacesAPI()

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="sirens_provider",
            category=ProviderCategory.NOISE,
            description="Fire stations and helipads within a mile.",
            version="1.0.0",
            requires_api_key=True,
            cost_per_call=0.032,
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
            ProviderResult with fire_stations (name, distance_m) and heliports (name,
            category, distance_m) within RADIUS_MILES, nearest first, and radius_m
        """
        try:
            found = await self.places_api.nearby_search(
                lat=latitude,
                lon=longitude,
                place_types=["fire_station"],
                radius_miles=RADIUS_MILES,
                max_results=FIRE_STATION_RESULTS,
                nearest_first=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error searching fire stations for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        fire_stations = sorted(
            (
                {
                    "name": p.get("name"),
                    "distance_m": round(
                        haversine_distance(latitude, longitude, p["latitude"], p["longitude"])
                    ),
                }
                for p in found
                if p.get("latitude") is not None
                and p.get("longitude") is not None
                and is_firehouse(p.get("name") or "")
            ),
            key=lambda s: s["distance_m"],
        )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={
                "fire_stations": fire_stations,
                "heliports": self.heliports_near(latitude, longitude),
                "radius_m": round(RADIUS_MILES * METERS_PER_MILE),
            },
            success=True,
            api_calls_made=1,
        )

    def heliports_near(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        if self._heliports.empty:
            return []
        distances = _haversine(np.radians(latitude), np.radians(longitude), self._lat, self._lon)
        radius_m = RADIUS_MILES * METERS_PER_MILE
        return [
            {
                "name": self._heliports.at[i, "name"],
                "category": self._heliports.at[i, "category"],
                "distance_m": int(round(distances[i])),
            }
            for i in np.argsort(distances)
            if distances[i] <= radius_m
        ]

    async def validate_config(self) -> bool:
        return await self.places_api.validate_api_key()


def is_firehouse(name: str) -> bool:
    return bool(FIREHOUSE_NAME.search(name)) and not NOT_A_FIREHOUSE.search(name)
