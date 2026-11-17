"""US Census Bureau client: geography lookup and American Community Survey (ACS) estimates.

Two services:
- Census Geocoder (no key) finds the state, county, tract and city containing a point.
  https://geocoding.geo.census.gov/geocoder/
- Census Data API serves ACS 5-year estimates for those geographies. Needs a free key
  (https://api.census.gov/data/key_signup.html); keyless requests are redirected to an
  HTML "missing key" page.

The geocoder vintage is pinned to the ACS year so tract and place boundaries match the data.
"""

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.config import settings

from .base_client import BaseAPIClient, send_with_retry

logger = logging.getLogger(__name__)

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
GEOCODER_LAYERS = "States,Counties,Census Tracts,Incorporated Places,Census Designated Places"

# The Data API accepts at most 50 variables per request
MAX_VARIABLES_PER_REQUEST = 50

TOTAL_POPULATION = "B01003_001E"
MEDIAN_AGE = "B01002_001E"

# B01001 (sex by age): male columns 003-025, female 027-049, same age bands in the same order
_MALE_AGE_START, _FEMALE_AGE_START = 3, 27
AGE_GROUPS: List[Tuple[str, range]] = [
    # (label, offsets into the 23 age bands)
    ("Under 18", range(0, 4)),  # under 5 .. 15-17
    ("18-54", range(4, 14)),  # 18-19 .. 50-54
    ("55+", range(14, 23)),  # 55-59 .. 85+
]
AGE_TOTAL = "B01001_001E"

# B03002 (Hispanic or Latino origin by race): mutually exclusive groups that sum to the total
RACE_ETHNICITY: List[Tuple[str, str]] = [
    ("White", "B03002_003E"),
    ("Black", "B03002_004E"),
    ("American Indian / Alaska Native", "B03002_005E"),
    ("Asian", "B03002_006E"),
    ("Native Hawaiian / Pacific Islander", "B03002_007E"),
    ("Other race", "B03002_008E"),
    ("Two or more races", "B03002_009E"),
    ("Hispanic or Latino", "B03002_012E"),
]
RACE_TOTAL = "B03002_001E"

# B15003 (educational attainment, population 25 and over)
EDUCATION: List[Tuple[str, List[int]]] = [
    ("Less than high school", list(range(2, 17))),
    ("High school / GED", [17, 18]),
    ("Some college / associate's", [19, 20, 21]),
    ("Bachelor's", [22]),
    ("Graduate / professional", [23, 24, 25]),
]
EDUCATION_TOTAL = "B15003_001E"
BACHELORS_OR_HIGHER = ("Bachelor's", "Graduate / professional")


# Housing and households, for "what does the rent buy here"
OCCUPIED_HOMES = "B25003_001E"
RENTER_OCCUPIED = "B25003_003E"
HOUSEHOLDS = "B11005_001E"
HOUSEHOLDS_WITH_CHILDREN = "B11005_002E"  # one or more people under 18
MEDIAN_HOUSEHOLD_INCOME = "B19013_001E"
MEDIAN_GROSS_RENT = "B25064_001E"  # rent plus utilities
# B25031 (median gross rent by bedrooms): studio, 1, 2, 3, 4, 5 or more
MEDIAN_GROSS_RENT_BY_BEDROOMS = {beds: f"B25031_{beds + 2:03d}E" for beds in range(6)}
HOUSING_VARIABLES = [
    OCCUPIED_HOMES,
    RENTER_OCCUPIED,
    HOUSEHOLDS,
    HOUSEHOLDS_WITH_CHILDREN,
    MEDIAN_HOUSEHOLD_INCOME,
    MEDIAN_GROSS_RENT,
    *MEDIAN_GROSS_RENT_BY_BEDROOMS.values(),
]


def _age_variables(offsets: Iterable[int]) -> List[str]:
    return [
        f"B01001_{start + i:03d}E"
        for i in offsets
        for start in (_MALE_AGE_START, _FEMALE_AGE_START)
    ]


def _education_variables(columns: Iterable[int]) -> List[str]:
    return [f"B15003_{c:03d}E" for c in columns]


TRACT_VARIABLES: List[str] = [
    TOTAL_POPULATION,
    MEDIAN_AGE,
    AGE_TOTAL,
    *(v for _, offsets in AGE_GROUPS for v in _age_variables(offsets)),
    RACE_TOTAL,
    *(v for _, v in RACE_ETHNICITY),
    EDUCATION_TOTAL,
    *(v for _, cols in EDUCATION for v in _education_variables(cols)),
    *HOUSING_VARIABLES,
]


class CensusAPIClient(BaseAPIClient):
    """Census geography lookups and ACS 5-year estimates."""

    def __init__(self):
        self.acs_year = settings.census_acs_year
        super().__init__(
            base_url=f"https://api.census.gov/data/{self.acs_year}/acs/acs5",
            api_key=settings.census_api_key,
            timeout=30.0,
            rate_limit_per_second=None,
        )

    def _get_service_name(self) -> str:
        return "census"

    async def validate_api_key(self) -> bool:
        """Check the key works with a one-variable state query."""
        if not self.api_key:
            return False
        try:
            await self._get_acs([TOTAL_POPULATION], for_geo="state:08")
        except Exception:  # pylint: disable=broad-except
            return False
        return True

    async def get_demographics(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Population of the city and county, and tract demographics, for a point.

        Returns:
            {"acs_year", "state", "city", "county", "tract"}. city is None outside any
            incorporated or census-designated place. city and county are
            {"name", "geoid", "population"} (city also has "type"). tract is
            {"name", "geoid", "population", "median_age", "age_groups", "race_ethnicity",
            "education", "bachelors_or_higher_pct", "renter_pct",
            "households_without_children_pct", "median_household_income",
            "median_gross_rent", "median_gross_rent_by_bedrooms"}, where the breakdowns map
            label to percent (one decimal place) and rent by bedrooms maps "0"-"5" (5 is
            five or more) to dollars, leaving out sizes with too few rentals to estimate.

        Raises:
            ValueError: If no key is set, the point isn't in a US county, or the API
                returns something other than data
            httpx.HTTPError: If a service can't be reached or returns an HTTP error
        """
        if not self.api_key:
            raise ValueError("CENSUS_API_KEY is not set")

        geo = await self.get_geographies(latitude, longitude)
        state, county, tract, place = geo["state"], geo["county"], geo["tract"], geo["place"]
        state_fips, county_fips = state["STATE"], county["COUNTY"]
        in_county = f"state:{state_fips} county:{county_fips}"

        lookups = [
            self._get_acs([TOTAL_POPULATION], f"county:{county_fips}", f"state:{state_fips}"),
            self._get_acs(TRACT_VARIABLES, f"tract:{tract['TRACT']}", in_county),
        ]
        if place:
            lookups.append(
                self._get_acs([TOTAL_POPULATION], f"place:{place['PLACE']}", f"state:{state_fips}")
            )
        county_values, tract_values, *place_values = await asyncio.gather(*lookups)

        city = None
        if place:
            city = {
                "name": place["BASENAME"],
                "type": place["type"],
                "geoid": place["GEOID"],
                "population": place_values[0].get(TOTAL_POPULATION),
            }

        return {
            "acs_year": self.acs_year,
            "state": state["NAME"],
            "city": city,
            "county": {
                "name": county["NAME"],
                "geoid": county["GEOID"],
                "population": county_values.get(TOTAL_POPULATION),
            },
            "tract": {
                "name": tract["NAME"],
                "geoid": tract["GEOID"],
                **_tract_profile(tract_values),
            },
        }

    async def get_geographies(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Find the state, county, tract and place containing a point.

        Returns:
            {"state", "county", "tract", "place"}: the geocoder's attribute dicts. place is
            the incorporated place, else the census-designated place, else None, and has a
            "type" of "incorporated" or "CDP".

        Raises:
            ValueError: If the point isn't in a US county and tract
            httpx.HTTPError: If the geocoder can't be reached or returns an HTTP error
        """
        params = {
            "x": longitude,
            "y": latitude,
            "benchmark": "Public_AR_Current",
            "vintage": f"ACS{self.acs_year}_Current",
            "layers": GEOCODER_LAYERS,
            "format": "json",
        }
        response = await send_with_retry(
            lambda: self.client.get(GEOCODER_URL, params=params), service="Census geocoder"
        )
        response.raise_for_status()
        body = response.json()
        if "errors" in body:
            raise ValueError(f"Census geocoder failed: {'; '.join(body['errors'])}")
        layers = body.get("result", {}).get("geographies", {})

        def first(layer: str) -> Optional[Dict[str, Any]]:
            features = layers.get(layer) or []
            return features[0] if features else None

        state, county, tract = first("States"), first("Counties"), first("Census Tracts")
        if not (state and county and tract):
            raise ValueError(f"No US census tract at ({latitude:.6f}, {longitude:.6f})")

        place = None
        if incorporated := first("Incorporated Places"):
            place = {**incorporated, "type": "incorporated"}
        elif cdp := first("Census Designated Places"):
            place = {**cdp, "type": "CDP"}

        return {"state": state, "county": county, "tract": tract, "place": place}

    async def get_block_geoid(self, latitude: float, longitude: float) -> Optional[str]:
        """
        The 15-digit 2020 census block GEOID containing a point, or None outside the US.

        Raises:
            ValueError: If the geocoder reports an error
            httpx.HTTPError: If the geocoder can't be reached or returns an HTTP error
        """
        params = {
            "x": longitude,
            "y": latitude,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "layers": "2020 Census Blocks",
            "format": "json",
        }
        response = await send_with_retry(
            lambda: self.client.get(GEOCODER_URL, params=params), service="Census geocoder"
        )
        response.raise_for_status()
        body = response.json()
        if "errors" in body:
            raise ValueError(f"Census geocoder failed: {'; '.join(body['errors'])}")
        blocks = body.get("result", {}).get("geographies", {}).get("2020 Census Blocks") or []
        return blocks[0].get("GEOID") if blocks else None

    async def _get_acs(
        self, variables: List[str], for_geo: str, in_geo: Optional[str] = None
    ) -> Dict[str, Optional[float]]:
        """
        Fetch ACS estimates for one geography, splitting into requests of 50 variables.

        Returns:
            Variable name to value. Values the Census suppresses or can't compute (negative
            sentinels such as -666666666) are None.
        """
        chunks = [
            variables[i : i + MAX_VARIABLES_PER_REQUEST]
            for i in range(0, len(variables), MAX_VARIABLES_PER_REQUEST)
        ]
        values: Dict[str, Optional[float]] = {}
        for result in await asyncio.gather(
            *(self._get_acs_chunk(chunk, for_geo, in_geo) for chunk in chunks)
        ):
            values.update(result)
        return values

    async def _get_acs_chunk(
        self, variables: List[str], for_geo: str, in_geo: Optional[str]
    ) -> Dict[str, Optional[float]]:
        params = {"get": ",".join(variables), "for": for_geo, "key": self.api_key}
        if in_geo:
            params["in"] = in_geo

        response = await send_with_retry(
            lambda: self.client.get(self.base_url, params=params), service="Census API"
        )
        response.raise_for_status()
        # Bad keys and unknown geographies come back as HTML or an empty 204, not JSON errors
        try:
            rows = response.json()
        except ValueError:
            raise ValueError(
                f"Census API returned no data for {for_geo} (HTTP {response.status_code}); "
                "check CENSUS_API_KEY"
            ) from None
        if len(rows) < 2:
            raise ValueError(f"Census API returned no data for {for_geo}")

        header, row = rows[0], rows[1]
        return {name: _number(value) for name, value in zip(header, row) if name in variables}


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # ACS uses large negative numbers for "not available"; no estimate we use is negative
    if number < 0:
        return None
    return int(number) if number.is_integer() else number


def _tract_profile(values: Dict[str, Optional[float]]) -> Dict[str, Any]:
    def total(names: Iterable[str]) -> Optional[float]:
        parts = [values.get(n) for n in names]
        return None if any(p is None for p in parts) else sum(parts)

    def breakdown(groups: List[Tuple[str, List[str]]], universe: str) -> Dict[str, float]:
        denominator = values.get(universe)
        if not denominator:
            return {}
        result = {}
        for label, names in groups:
            count = total(names)
            if count is not None:
                result[label] = round(100 * count / denominator, 1)
        return result

    education_groups = [(label, _education_variables(cols)) for label, cols in EDUCATION]
    bachelors_or_higher = [
        name for label, names in education_groups if label in BACHELORS_OR_HIGHER for name in names
    ]

    return {
        "population": values.get(TOTAL_POPULATION),
        "median_age": values.get(MEDIAN_AGE),
        "age_groups": breakdown(
            [(label, _age_variables(offsets)) for label, offsets in AGE_GROUPS], AGE_TOTAL
        ),
        "race_ethnicity": breakdown([(label, [v]) for label, v in RACE_ETHNICITY], RACE_TOTAL),
        "education": breakdown(education_groups, EDUCATION_TOTAL),
        "bachelors_or_higher_pct": breakdown([("all", bachelors_or_higher)], EDUCATION_TOTAL).get(
            "all"
        ),
        "renter_pct": breakdown([("all", [RENTER_OCCUPIED])], OCCUPIED_HOMES).get("all"),
        "households_without_children_pct": _complement(
            breakdown([("all", [HOUSEHOLDS_WITH_CHILDREN])], HOUSEHOLDS).get("all")
        ),
        "median_household_income": values.get(MEDIAN_HOUSEHOLD_INCOME),
        "median_gross_rent": values.get(MEDIAN_GROSS_RENT),
        "median_gross_rent_by_bedrooms": {
            str(beds): values[name]
            for beds, name in MEDIAN_GROSS_RENT_BY_BEDROOMS.items()
            if values.get(name) is not None
        },
    }


def _complement(percent: Optional[float]) -> Optional[float]:
    return None if percent is None else round(100 - percent, 1)
