"""Tests for the Census client, using httpx.MockTransport."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations import census_api
from app.integrations.census_api import TRACT_VARIABLES, CensusAPIClient

STATE = {"NAME": "Colorado", "STATE": "08", "GEOID": "08"}
COUNTY = {"NAME": "Boulder County", "STATE": "08", "COUNTY": "013", "GEOID": "08013"}
TRACT = {"NAME": "Census Tract 122.06", "TRACT": "012206", "GEOID": "08013012206"}
CITY = {"NAME": "Boulder city", "BASENAME": "Boulder", "PLACE": "07850", "GEOID": "0807850"}
CDP = {"NAME": "Highlands Ranch CDP", "BASENAME": "Highlands Ranch", "PLACE": "36410",
       "GEOID": "0836410"}  # fmt: skip


def _geocoder(**layers):
    return {"result": {"geographies": {k: [v] for k, v in layers.items()}}}


GEO_CITY = _geocoder(
    States=STATE, Counties=COUNTY, **{"Census Tracts": TRACT, "Incorporated Places": CITY}
)


def _tract_values():
    """A tract of 1,000 people: 200 per age band group of B01001, etc."""
    values = {v: 0 for v in TRACT_VARIABLES}
    values.update({"B01003_001E": 1000, "B01002_001E": 36.4, "B01001_001E": 1000})
    values["B01001_003E"] = 100  # male under 5   -> Under 18
    values["B01001_030E"] = 100  # female 15-17   -> Under 18
    values["B01001_011E"] = 300  # male 25-29     -> 18-54
    values["B01001_049E"] = 500  # female 85+     -> 55+
    values.update({"B03002_001E": 1000, "B03002_003E": 700, "B03002_012E": 250,
                   "B03002_006E": 50})  # fmt: skip
    # 25+: 800 adults
    values.update({"B15003_001E": 800, "B15003_017E": 200, "B15003_021E": 100,
                   "B15003_022E": 300, "B15003_023E": 150, "B15003_025E": 50})  # fmt: skip
    return values


def _acs_rows(values, geo_columns):
    names = list(values)
    return [names + list(geo_columns), [str(values[n]) for n in names] + list(geo_columns.values())]


def make_client(api_key="test-key"):
    """Client that answers geocoder and ACS requests from the routes in `responses`."""
    requests = []
    responses = {"geocoder": GEO_CITY, "acs": {}}

    def handler(request):
        requests.append(request)
        if request.url.host == "geocoding.geo.census.gov":
            item = responses["geocoder"]
        else:
            params = request.url.params
            item = responses["acs"].get(params["for"].split(":")[0])
            if callable(item):
                item = item(params)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(200, json=item)

    with patch.object(census_api.settings, "census_api_key", api_key):
        api = CensusAPIClient()
    api._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return api, requests, responses


def _acs_for(values_by_level):
    """ACS route that returns only the variables requested, like the real API."""

    def route(params):
        values = values_by_level
        names = params["get"].split(",")
        return _acs_rows({n: values.get(n, -666666666) for n in names}, {"x": "1"})

    return route


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("app.integrations.base_client.asyncio.sleep", new_callable=AsyncMock) as sleep:
        yield sleep


@pytest.fixture
def api():
    api, requests, responses = make_client()
    responses["acs"] = {
        "county": _acs_for({"B01003_001E": 330000}),
        "place": _acs_for({"B01003_001E": 105000}),
        "tract": _acs_for(_tract_values()),
    }
    return api, requests, responses


@pytest.mark.asyncio
async def test_demographics(api):
    api, requests, _ = api

    result = await api.get_demographics(40.015, -105.2705)

    assert result == {
        "acs_year": 2024,
        "state": "Colorado",
        "city": {
            "name": "Boulder",
            "type": "incorporated",
            "geoid": "0807850",
            "population": 105000,
        },  # fmt: skip
        "county": {"name": "Boulder County", "geoid": "08013", "population": 330000},
        "tract": {
            "name": "Census Tract 122.06",
            "geoid": "08013012206",
            "population": 1000,
            "median_age": 36.4,
            "age_groups": {
                "Under 18": 20.0,
                "18-54": 30.0,
                "55+": 50.0,
            },  # fmt: skip
            "race_ethnicity": {
                "White": 70.0,
                "Black": 0.0,
                "American Indian / Alaska Native": 0.0,
                "Asian": 5.0,
                "Native Hawaiian / Pacific Islander": 0.0,
                "Other race": 0.0,
                "Two or more races": 0.0,
                "Hispanic or Latino": 25.0,
            },
            "education": {
                "Less than high school": 0.0,
                "High school / GED": 25.0,
                "Some college / associate's": 12.5,
                "Bachelor's": 37.5,
                "Graduate / professional": 25.0,
            },
            "bachelors_or_higher_pct": 62.5,
        },
    }
    # Geocoder, county, city, and the tract split into two requests of <= 50 variables
    assert len(requests) == 5


@pytest.mark.asyncio
async def test_request_parameters(api):
    api, requests, _ = api

    await api.get_demographics(40.015, -105.2705)

    geocoder = requests[0].url.params
    assert geocoder["x"] == "-105.2705"
    assert geocoder["y"] == "40.015"
    assert geocoder["vintage"] == "ACS2024_Current"

    acs = [r for r in requests if r.url.host == "api.census.gov"]
    assert all(r.url.path == "/data/2024/acs/acs5" for r in acs)
    assert all(r.url.params["key"] == "test-key" for r in acs)
    by_level = {}
    for r in acs:
        by_level.setdefault(r.url.params["for"], []).append(r.url.params)
    assert by_level["county:013"][0]["in"] == "state:08"
    assert by_level["place:07850"][0]["in"] == "state:08"
    tract = by_level["tract:012206"]
    assert all(p["in"] == "state:08 county:013" for p in tract)
    assert all(len(p["get"].split(",")) <= 50 for p in tract)
    assert sorted(v for p in tract for v in p["get"].split(",")) == sorted(TRACT_VARIABLES)


@pytest.mark.asyncio
async def test_unincorporated_uses_census_designated_place(api):
    api, requests, responses = api
    responses["geocoder"] = _geocoder(
        States=STATE, Counties=COUNTY, **{"Census Tracts": TRACT, "Census Designated Places": CDP}
    )

    result = await api.get_demographics(39.54, -104.97)

    assert result["city"]["name"] == "Highlands Ranch"
    assert result["city"]["type"] == "CDP"


@pytest.mark.asyncio
async def test_outside_any_place(api):
    api, requests, responses = api
    responses["geocoder"] = _geocoder(States=STATE, Counties=COUNTY, **{"Census Tracts": TRACT})

    result = await api.get_demographics(40.1, -105.5)

    assert result["city"] is None
    assert result["county"]["population"] == 330000
    assert not any(r.url.params.get("for", "").startswith("place") for r in requests)


@pytest.mark.asyncio
async def test_suppressed_values_are_none(api):
    api, _, responses = api
    responses["acs"]["tract"] = _acs_for({"B01003_001E": 0})  # everything else -666666666

    tract = (await api.get_demographics(40.0, -105.0))["tract"]

    assert tract["population"] == 0
    assert tract["median_age"] is None
    assert tract["age_groups"] == {}
    assert tract["race_ethnicity"] == {}
    assert tract["education"] == {}
    assert tract["bachelors_or_higher_pct"] is None


@pytest.mark.asyncio
async def test_outside_us(api):
    api, _, responses = api
    responses["geocoder"] = {"result": {"geographies": {}}}

    with pytest.raises(ValueError, match="No US census tract"):
        await api.get_demographics(30.0, -30.0)


@pytest.mark.asyncio
async def test_missing_key():
    api, requests, _ = make_client(api_key=None)

    with pytest.raises(ValueError, match="CENSUS_API_KEY is not set"):
        await api.get_demographics(40.0, -105.0)
    assert requests == []


@pytest.mark.asyncio
async def test_bad_key_html_response(api):
    api, _, responses = api
    responses["acs"]["county"] = httpx.Response(200, text="<html>Invalid Key</html>")

    with pytest.raises(ValueError, match="check CENSUS_API_KEY"):
        await api.get_demographics(40.0, -105.0)


@pytest.mark.asyncio
async def test_retries_busy_api(api, no_backoff_sleep):
    api, _, responses = api
    county = responses["acs"]["county"]
    attempts = []

    def flaky(params):
        attempts.append(params)
        return httpx.Response(503) if len(attempts) == 1 else county(params)

    responses["acs"]["county"] = flaky

    result = await api.get_demographics(40.0, -105.0)

    assert result["county"]["population"] == 330000
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_validate_api_key(api):
    api, _, responses = api
    responses["acs"]["state"] = _acs_for({"B01003_001E": 5900000})
    assert await api.validate_api_key() is True

    responses["acs"]["state"] = httpx.Response(200, text="<html>Invalid Key</html>")
    assert await api.validate_api_key() is False

    no_key, _, _ = make_client(api_key=None)
    assert await no_key.validate_api_key() is False
