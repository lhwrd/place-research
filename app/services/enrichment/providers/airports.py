"""Nearby airports, for aircraft noise.

Uses the airport list bundled with the app (app/data/airports.csv, built from
OurAirports by scripts/build_airports.py): large and medium airports, each labelled
large, military, regional or general for the noise model in app/services/noise.py.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.enrichment.base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

AIRPORTS_CSV = Path(__file__).resolve().parents[3] / "data" / "airports.csv"
EARTH_RADIUS_M = 6_371_000

# Aircraft noise from even the largest airport is at ambient well inside this
SEARCH_RADIUS_M = 50_000
MAX_AIRPORTS = 5

logger = logging.getLogger(__name__)


class AirportProvider(BaseEnrichmentProvider):
    """The closest large and medium airports, with straight-line distances."""

    _shared_airports: Optional[pd.DataFrame] = None

    def __init__(self, airports: Optional[pd.DataFrame] = None):
        """
        Args:
            airports: Airport table (tests); defaults to the bundled list.
        """
        if airports is None:
            if AirportProvider._shared_airports is None:
                AirportProvider._shared_airports = _prepare(
                    pd.read_csv(AIRPORTS_CSV, keep_default_na=False)
                )
            airports = AirportProvider._shared_airports
        else:
            airports = _prepare(airports)
        self._airports = airports

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="airport_provider",
            category=ProviderCategory.ENVIRONMENTAL,
            enabled=True,
            description="Nearest large and medium airports (bundled OurAirports list).",
            version="1.0.0",
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
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"airports": self.nearby(latitude, longitude)},
            success=True,
            api_calls_made=0,
        )

    def nearby(self, latitude: float, longitude: float) -> List[Dict[str, Any]]:
        """Airports within SEARCH_RADIUS_M, closest first."""
        if self._airports.empty:
            return []
        distances = _haversine(
            np.radians(latitude),
            np.radians(longitude),
            self._airports["_lat"],
            self._airports["_lon"],
        )
        order = np.argsort(distances)[:MAX_AIRPORTS]
        nearby = []
        for i in order:
            if distances[i] > SEARCH_RADIUS_M:
                break
            row = self._airports.iloc[i]
            nearby.append(
                {
                    "code": row["iata"] or row["ident"],
                    "name": row["name"],
                    "category": row["category"],
                    "distance_m": int(round(distances[i])),
                }
            )
        return nearby

    async def validate_config(self) -> bool:
        return not self._airports.empty


def _prepare(airports: pd.DataFrame) -> pd.DataFrame:
    airports = airports.reset_index(drop=True).copy()
    airports["_lat"] = np.radians(airports["latitude"].astype(float))
    airports["_lon"] = np.radians(airports["longitude"].astype(float))
    for column in ("iata", "ident", "name", "category"):
        if column not in airports:
            airports[column] = ""
    return airports


def _haversine(lat1: float, lon1: float, lat2: pd.Series, lon2: pd.Series) -> np.ndarray:
    """Great-circle distance in meters from one point to many (all in radians)."""
    a = (
        np.sin((lat2.to_numpy() - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2.to_numpy()) * np.sin((lon2.to_numpy() - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))
