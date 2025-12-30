import logging
import os

import requests
from dotenv import load_dotenv

from place_research.interfaces import ProviderNameMixin
from place_research.models.results import FloodZoneResult

from ..models import Place

load_dotenv()


class FloodZoneProvider(ProviderNameMixin):
    def __init__(self, session: requests.Session | None = None):
        self.logger = logging.getLogger(__name__)
        self._session = session or requests.Session()
        api_key = os.getenv("NATIONAL_FLOOD_DATA_API_KEY")
        if api_key is None:
            raise ValueError("NATIONAL_FLOOD_DATA_API_KEY is not set")
        self._session.headers["x-api-key"] = api_key

    def fetch_place_data(self, place: Place) -> FloodZoneResult | None:
        """Fetch data from the API if not already fetched."""
        params = {
            "lat": str(place.latitude),
            "lon": str(place.longitude),
            "address": place.address,
            "searchtype": "addresscoord",
        }
        response = self._session.get(
            "https://api.nationalflooddata.com/v3/data",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        json_data = response.json()
        result = json_data.get("result")
        if not result:
            raise ValueError("No flood zone data found")

        flood_hazard_area = result.get("flood.s_fld_haz_ar")
        if len(flood_hazard_area) == 0:
            return FloodZoneResult(flood_zone="Unknown", flood_risk="Unknown")
        flood_zone = flood_hazard_area[0].get("fld_zone")
        flood_risk = flood_hazard_area[0].get("zone_subty")
        self.logger.info(
            "Flood zone data fetched for place with lat: %s and lon: %s",
            place.latitude,
            place.longitude,
        )
        return FloodZoneResult(flood_zone=flood_zone, flood_risk=flood_risk)
