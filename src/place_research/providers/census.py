import os
from typing import TYPE_CHECKING, Dict, Any
import requests
from dotenv import load_dotenv

from ..models import Place, City, County

if TYPE_CHECKING:
    from ..config import Config

load_dotenv()


class CensusProvider:
    """Provider for fetching US Census Bureau data."""

    def __init__(
        self, session: requests.Session | None = None, config: "Config | None" = None
    ):
        self.config = config
        self._session = session or requests.Session()

        # US Census API does not require an API key for basic access
        # but having one increases rate limits
        self.api_key = os.getenv("CENSUS_API_KEY")

        # Base URLs for different Census APIs
        self.geocoding_base_url = (
            "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
        )
        self.acs_base_url = "https://api.census.gov/data/2022/acs/acs5"  # American Community Survey 5-year estimates

        # Use timeout from config if available
        self.timeout = config.timeout_seconds if config else 30

    def _get_geographic_identifiers(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get geographic identifiers (FIPS codes) for given coordinates."""
        params = {
            "x": lon,
            "y": lat,
            "format": "json",
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
        }

        response = self._session.get(
            self.geocoding_base_url, params=params, timeout=self.timeout
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("result", {}).get("geographies"):
            return {}

        geo = data["result"]["geographies"]

        # Extract relevant geographic identifiers
        result = {}

        # County information
        if "Counties" in geo and geo["Counties"]:
            county = geo["Counties"][0]
            result["county_fips"] = county.get("COUNTY")
            result["state_fips"] = county.get("STATE")
            result["county_name"] = county.get("NAME")

        # Place information (incorporated places)
        if "Incorporated Places" in geo and geo["Incorporated Places"]:
            place = geo["Incorporated Places"][0]
            result["place_fips"] = place.get("PLACE")
            result["place_name"] = place.get("NAME")

        # Census tract for more detailed data
        if "Census Tracts" in geo and geo["Census Tracts"]:
            tract = geo["Census Tracts"][0]
            result["tract_fips"] = tract.get("TRACT")

        return result

    def _fetch_acs_data(
        self, geography: str, variables: list, **geo_params
    ) -> Dict[str, Any]:
        """Fetch American Community Survey data."""
        params = {"get": ",".join(["NAME"] + variables), "for": geography, **geo_params}

        if self.api_key:
            params["key"] = self.api_key

        response = self._session.get(
            self.acs_base_url, params=params, timeout=self.timeout
        )
        response.raise_for_status()

        data = response.json()
        if not data or len(data) < 2:
            return {}

        # First row is headers, second row is data
        headers = data[0]
        values = data[1]

        return dict(zip(headers, values))

    def fetch_place_data(self, place: Place):
        """Fetch census data for a specific place by coordinates."""
        try:
            # Get geographic identifiers
            geo_info = self._get_geographic_identifiers(
                place.coordinates[0], place.coordinates[1]
            )

            if not geo_info:
                place.attributes["census_error"] = "No geographic data found"
                return

            # Define variables we want to fetch
            # These are common demographic and economic indicators
            variables = [
                "B01003_001E",  # Total population
                "B25001_001E",  # Total housing units
                "B25003_002E",  # Owner-occupied housing units
                "B25003_003E",  # Renter-occupied housing units
                "B19013_001E",  # Median household income
                "B25077_001E",  # Median home value
                "B08301_010E",  # Public transportation commuters
                "B08301_021E",  # Work from home
                "B15003_022E",  # Bachelor's degree
                "B15003_023E",  # Master's degree
                "B15003_024E",  # Professional degree
                "B15003_025E",  # Doctorate degree
            ]

            census_data = {}

            # Try to get tract-level data first (most detailed)
            if (
                "tract_fips" in geo_info
                and "county_fips" in geo_info
                and "state_fips" in geo_info
            ):
                try:
                    tract_data = self._fetch_acs_data(
                        "tract",
                        variables,
                        **{
                            "in": f"state:{geo_info['state_fips']} county:{geo_info['county_fips']}"
                        },
                    )
                    census_data.update(tract_data)
                except (requests.RequestException, KeyError, ValueError):
                    pass  # Fall back to county data

            # If we have place FIPS, get place-specific data
            if "place_fips" in geo_info and "state_fips" in geo_info:
                try:
                    place_data = self._fetch_acs_data(
                        "place", variables, **{"in": f"state:{geo_info['state_fips']}"}
                    )
                    if place_data:
                        census_data.update(place_data)
                except (requests.RequestException, KeyError, ValueError):
                    pass

            # Parse and store the census data with meaningful names
            if census_data:
                place.attributes.update(
                    {
                        "census_population": self._safe_int(
                            census_data.get("B01003_001E")
                        ),
                        "census_housing_units": self._safe_int(
                            census_data.get("B25001_001E")
                        ),
                        "census_owner_occupied": self._safe_int(
                            census_data.get("B25003_002E")
                        ),
                        "census_renter_occupied": self._safe_int(
                            census_data.get("B25003_003E")
                        ),
                        "census_median_income": self._safe_int(
                            census_data.get("B19013_001E")
                        ),
                        "census_median_home_value": self._safe_int(
                            census_data.get("B25077_001E")
                        ),
                        "census_public_transit_commuters": self._safe_int(
                            census_data.get("B08301_010E")
                        ),
                        "census_work_from_home": self._safe_int(
                            census_data.get("B08301_021E")
                        ),
                        "census_bachelors_degree": self._safe_int(
                            census_data.get("B15003_022E")
                        ),
                        "census_masters_degree": self._safe_int(
                            census_data.get("B15003_023E")
                        ),
                        "census_professional_degree": self._safe_int(
                            census_data.get("B15003_024E")
                        ),
                        "census_doctorate_degree": self._safe_int(
                            census_data.get("B15003_025E")
                        ),
                    }
                )

                # Calculate derived metrics
                total_housing = place.attributes.get("census_housing_units", 0)
                if total_housing and total_housing > 0:
                    owner_occupied = (
                        place.attributes.get("census_owner_occupied", 0) or 0
                    )
                    place.attributes["census_homeownership_rate"] = round(
                        (owner_occupied / total_housing) * 100, 1
                    )

                # Calculate higher education rate
                population = place.attributes.get("census_population", 0)
                if population and population > 0:
                    higher_ed = sum(
                        [
                            place.attributes.get("census_bachelors_degree", 0) or 0,
                            place.attributes.get("census_masters_degree", 0) or 0,
                            place.attributes.get("census_professional_degree", 0) or 0,
                            place.attributes.get("census_doctorate_degree", 0) or 0,
                        ]
                    )
                    place.attributes["census_higher_education_rate"] = round(
                        (higher_ed / population) * 100, 1
                    )

                # Store geographic info
                place.attributes["census_county_fips"] = geo_info.get("county_fips")
                place.attributes["census_state_fips"] = geo_info.get("state_fips")
                place.attributes["census_place_fips"] = geo_info.get("place_fips")

        except (requests.RequestException, KeyError, ValueError) as e:
            place.attributes["census_error"] = str(e)

    def fetch_city_data(self, city: City):
        """Fetch census data for a city."""
        if not city or not city.name or not city.state:
            return

        try:
            # Get state FIPS code first
            state_fips = self._get_state_fips(city.state)
            if not state_fips:
                city.attributes["census_error"] = (
                    f"State FIPS not found for {city.state}"
                )
                return

            # Variables for city-level data
            variables = [
                "B01003_001E",  # Total population
                "B19013_001E",  # Median household income
                "B25077_001E",  # Median home value
                "B25001_001E",  # Total housing units
                "B08301_010E",  # Public transportation commuters
            ]

            # Fetch place data for the city
            city_data = self._fetch_acs_data(
                "place", variables, **{"in": f"state:{state_fips}"}
            )

            if city_data and city_data.get("NAME", "").lower().startswith(
                city.name.lower()
            ):
                city.attributes.update(
                    {
                        "census_population": self._safe_int(
                            city_data.get("B01003_001E")
                        ),
                        "census_median_income": self._safe_int(
                            city_data.get("B19013_001E")
                        ),
                        "census_median_home_value": self._safe_int(
                            city_data.get("B25077_001E")
                        ),
                        "census_housing_units": self._safe_int(
                            city_data.get("B25001_001E")
                        ),
                        "census_public_transit_commuters": self._safe_int(
                            city_data.get("B08301_010E")
                        ),
                    }
                )

        except (requests.RequestException, KeyError, ValueError) as e:
            city.attributes["census_error"] = str(e)

    def fetch_county_data(self, county: County):
        """Fetch census data for a county."""
        if not county or not county.name or not county.state:
            return

        try:
            # Get state FIPS code first
            state_fips = self._get_state_fips(county.state)
            if not state_fips:
                county.attributes["census_error"] = (
                    f"State FIPS not found for {county.state}"
                )
                return

            # Variables for county-level data
            variables = [
                "B01003_001E",  # Total population
                "B19013_001E",  # Median household income
                "B25077_001E",  # Median home value
                "B25001_001E",  # Total housing units
                "B08135_001E",  # Aggregate travel time to work
            ]

            # Fetch county data
            county_data = self._fetch_acs_data(
                "county", variables, **{"in": f"state:{state_fips}"}
            )

            if county_data and county_data.get("NAME", "").lower().startswith(
                county.name.lower()
            ):
                county.attributes.update(
                    {
                        "census_population": self._safe_int(
                            county_data.get("B01003_001E")
                        ),
                        "census_median_income": self._safe_int(
                            county_data.get("B19013_001E")
                        ),
                        "census_median_home_value": self._safe_int(
                            county_data.get("B25077_001E")
                        ),
                        "census_housing_units": self._safe_int(
                            county_data.get("B25001_001E")
                        ),
                        "census_aggregate_travel_time": self._safe_int(
                            county_data.get("B08135_001E")
                        ),
                    }
                )

        except (requests.RequestException, KeyError, ValueError) as e:
            county.attributes["census_error"] = str(e)

    def fetch_state_data(self, state):  # pylint: disable=unused-argument
        """Fetch census data for a state."""
        # Not implementing state-level data for now
        return

    def _safe_int(self, value) -> int | None:
        """Safely convert a value to integer, handling None and negative values."""
        if value is None:
            return None
        try:
            int_val = int(value)
            return int_val if int_val >= 0 else None
        except (ValueError, TypeError):
            return None

    def _get_state_fips(self, state_name: str) -> str | None:
        """Get FIPS code for a state name."""
        # Mapping of state names to FIPS codes
        state_fips_map = {
            "alabama": "01",
            "alaska": "02",
            "arizona": "04",
            "arkansas": "05",
            "california": "06",
            "colorado": "08",
            "connecticut": "09",
            "delaware": "10",
            "florida": "12",
            "georgia": "13",
            "hawaii": "15",
            "idaho": "16",
            "illinois": "17",
            "indiana": "18",
            "iowa": "19",
            "kansas": "20",
            "kentucky": "21",
            "louisiana": "22",
            "maine": "23",
            "maryland": "24",
            "massachusetts": "25",
            "michigan": "26",
            "minnesota": "27",
            "mississippi": "28",
            "missouri": "29",
            "montana": "30",
            "nebraska": "31",
            "nevada": "32",
            "new hampshire": "33",
            "new jersey": "34",
            "new mexico": "35",
            "new york": "36",
            "north carolina": "37",
            "north dakota": "38",
            "ohio": "39",
            "oklahoma": "40",
            "oregon": "41",
            "pennsylvania": "42",
            "rhode island": "44",
            "south carolina": "45",
            "south dakota": "46",
            "tennessee": "47",
            "texas": "48",
            "utah": "49",
            "vermont": "50",
            "virginia": "51",
            "washington": "53",
            "west virginia": "54",
            "wisconsin": "55",
            "wyoming": "56",
        }

        return state_fips_map.get(state_name.lower())
