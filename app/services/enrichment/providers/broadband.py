"""Home internet providers and speeds at the property's census block (FCC data).

Reads BROADBAND_PATH, built by scripts/build_broadband.py from the FCC National Broadband
Map availability files: for each census block, the providers offering residential
service, their fastest advertised speeds, and how many of the block's locations they
serve. The block is found with the Census geocoder (one call); the rest is local.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd

from app.core.config import settings
from app.integrations.census_api import CensusAPIClient

from ..base_provider import (
    BaseEnrichmentProvider,
    ProviderCategory,
    ProviderMetadata,
    ProviderResult,
)

# FCC technology codes
TECHNOLOGIES = {
    10: "DSL",
    40: "Cable",
    50: "Fiber",
    60: "Satellite",
    61: "Satellite (LEO)",
    70: "Fixed wireless",
    71: "Fixed wireless",
    72: "Fixed wireless",
    0: "Other",
}
WIRED = {10, 40, 50}
FIBER = 50

logger = logging.getLogger(__name__)


class BroadbandProvider(BaseEnrichmentProvider):
    """Providers per census block, with the file loaded once per process."""

    _shared_blocks: Optional[pd.DataFrame] = None
    _data_lock = threading.Lock()

    def __init__(self, broadband_data: Optional[pd.DataFrame] = None):
        """
        Args:
            broadband_data: Pre-loaded block table (tests). If None, BROADBAND_PATH is
                loaded once and shared across instances.

        Raises:
            ValueError: If BROADBAND_PATH isn't set
            FileNotFoundError: If BROADBAND_PATH doesn't exist
        """
        self.census_client = CensusAPIClient()
        if broadband_data is not None:
            self._blocks = _index(broadband_data)
            return

        cls = self.__class__
        if cls._shared_blocks is None:
            with cls._data_lock:
                if cls._shared_blocks is None:
                    cls._shared_blocks = _index(_load(settings.broadband_path))
                    logger.info("Loaded broadband data for %d rows", len(cls._shared_blocks))
        self._blocks = cls._shared_blocks

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="broadband_provider",
            category=ProviderCategory.CONNECTIVITY,
            description="Home internet providers and advertised speeds (FCC broadband map).",
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
            ProviderResult with block_geoid, providers (fastest first: name, technology,
            max_down_mbps, max_up_mbps, coverage_pct), fiber_available, wired_providers
            and max_down_mbps
        """
        try:
            block = await self.census_client.get_block_geoid(latitude, longitude)
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Error finding the census block for %s: %s", address, e)
            return ProviderResult(
                provider_name=self.metadata.name,
                data={},
                success=False,
                error_message=str(e),
                api_calls_made=1,
            )
        return ProviderResult(
            provider_name=self.metadata.name,
            data={"block_geoid": block, **self.lookup(block)},
            success=True,
            api_calls_made=1,
        )

    def lookup(self, block: Optional[str]) -> Dict[str, Any]:
        rows = self._blocks.loc[[block]] if block and block in self._blocks.index else None
        providers = summarize_providers(rows) if rows is not None else []
        wired = [p for p in providers if p["technology_code"] in WIRED]
        return {
            "providers": providers,
            "fiber_available": any(p["technology_code"] == FIBER for p in providers),
            "wired_providers": len({p["name"] for p in wired}),
            "max_down_mbps": max((p["max_down_mbps"] for p in providers), default=None),
        }

    async def validate_config(self) -> bool:
        return not self._blocks.empty


def summarize_providers(rows: pd.DataFrame) -> List[Dict[str, Any]]:
    providers = [
        {
            "name": r.brand_name,
            "technology": TECHNOLOGIES.get(int(r.technology), "Other"),
            "technology_code": int(r.technology),
            "max_down_mbps": float(r.max_down),
            "max_up_mbps": float(r.max_up),
            "coverage_pct": round(100 * r.locations / r.block_locations)
            if r.block_locations
            else None,
        }
        for r in rows.itertuples()
    ]
    return sorted(providers, key=lambda p: (-p["max_down_mbps"], p["name"]))


def _load(path: Optional[Path]) -> pd.DataFrame:
    if not path:
        raise ValueError("BROADBAND_PATH not configured")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Broadband file not found: {path}")
    logger.info("Loading broadband data from %s", path)
    return pd.read_parquet(path)


def _index(blocks: pd.DataFrame) -> pd.DataFrame:
    blocks = blocks.copy()
    blocks["block_geoid"] = blocks["block_geoid"].astype(str)
    return blocks.set_index("block_geoid").sort_index()
