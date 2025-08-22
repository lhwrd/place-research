import os
from typing import TYPE_CHECKING

import requests
from dotenv import load_dotenv

from ..models import Place

if TYPE_CHECKING:
    from ..config import Config

load_dotenv()


class FloodZoneProvider:
    def __init__(
        self, session: requests.Session | None = None, config: "Config | None" = None
    ):
        self.config = config
        self._session = session or requests.Session()
        api_key = os.getenv("NATIONAL_FLOOD_DATA_API_KEY")
        if api_key is None:
            raise ValueError("NATIONAL_FLOOD_DATA_API_KEY is not set")
        self._session.headers["x-api-key"] = api_key

        # Use timeout from config if available
        self.timeout = config.timeout_seconds if config else 30

    def fetch_place_data(self, place: Place):
        """Fetch data from the API if not already fetched."""
        params = {
            "lat": place.coordinates[0],
            "lon": place.coordinates[1],
            "address": place.address,
            "searchtype": "addresscoord",
        }
        response = self._session.get(
            "https://api.nationalflooddata.com/v3/data",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        json_data = response.json()
        result = json_data.get("result")
        if not result:
            raise ValueError("No flood zone data found")

        flood_hazard_area = result.get("flood.s_fld_haz_ar")
        if len(flood_hazard_area) == 0:
            place.attributes["flood_zone"] = "Unknown"
            place.attributes["flood_risk"] = "Unknown"
        flood_zone = flood_hazard_area[0].get("fld_zone")
        flood_risk = flood_hazard_area[0].get("zone_subty")

        place.attributes["flood_zone"] = flood_zone
        place.attributes["flood_risk"] = flood_risk

    def fetch_city_data(self, city):
        pass

    def fetch_county_data(self, county):
        pass

    def fetch_state_data(self, state):
        pass
