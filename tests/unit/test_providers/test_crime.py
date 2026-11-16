"""Tests for the FBI crime provider and its CDE client."""

from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.fbi_cde_api import FbiCdeAPIClient
from app.services.enrichment.providers.crime import (
    CrimeProvider,
    choose_agency,
    month_window,
    summarize,
)

AGENCIES = [
    {"ori": "FL0480000", "agency_name": "Orange County Sheriff's Office",
     "agency_type_name": "County", "counties": "ORANGE"},
    {"ori": "FL0480600", "agency_name": "Winter Park Police Department",
     "agency_type_name": "City", "counties": "ORANGE"},
    {"ori": "FL0550100", "agency_name": "St. Cloud Police Department",
     "agency_type_name": "City", "counties": "OSCEOLA"},
    {"ori": "FL0550000", "agency_name": "Osceola County Sheriff's Office",
     "agency_type_name": "County", "counties": "OSCEOLA"},
    {"ori": "FL0640000", "agency_name": "Volusia County Sheriff's Office",
     "agency_type_name": "County", "counties": "FLAGLER, VOLUSIA"},
    {"ori": "FL0481400", "agency_name": "University of Central Florida",
     "agency_type_name": "University or College", "counties": "ORANGE"},
]  # fmt: skip

SHERIFF = "Orange County Sheriff's Office"


def _cde(name, actuals, rates, state_rates, population=955_709):
    """A CDE summarized response, in the shape the API returns."""
    return {
        "offenses": {
            "actuals": {f"{name} Offenses": actuals, f"{name} Clearances": {}},
            "rates": {f"{name} Offenses": rates, "Florida Offenses": state_rates},
        },
        "populations": {"population": {name: {m: population for m in actuals}}},
    }


class TestChooseAgency:
    def test_city_with_police_department(self):
        place = {"BASENAME": "Winter Park", "type": "incorporated"}
        assert choose_agency(AGENCIES, "Orange", place)["ori"] == "FL0480600"

    def test_abbreviated_city_name(self):
        place = {"BASENAME": "St. Cloud", "type": "incorporated"}
        assert choose_agency(AGENCIES, "Osceola", place)["ori"] == "FL0550100"

    def test_city_without_its_own_department_falls_back_to_sheriff(self):
        place = {"BASENAME": "Belle Isle", "type": "incorporated"}
        assert choose_agency(AGENCIES, "Orange", place)["ori"] == "FL0480000"

    def test_cdp_is_unincorporated(self):
        place = {"BASENAME": "Winter Park", "type": "CDP"}
        assert choose_agency(AGENCIES, "Orange", place)["ori"] == "FL0480000"

    def test_multi_county_listing(self):
        assert choose_agency(AGENCIES, "Volusia", None)["ori"] == "FL0640000"

    def test_unknown_county(self):
        assert choose_agency(AGENCIES, "Nowhere", None) is None


def test_month_window():
    assert month_window(date(2026, 11, 15)) == ("05-2025", "11-2026")
    assert month_window(date(2026, 6, 1)) == ("12-2024", "06-2026")


class TestSummarize:
    def test_skips_unreported_months_and_annualizes(self):
        # Oct/Nov 2024 not reported (0), Jan-Mar 2025 reported, Apr 2025 not yet published
        violent = _cde(
            SHERIFF,
            {"10-2024": 0, "11-2024": 0, "01-2025": 293, "02-2025": 287, "03-2025": 343,
             "04-2025": None},
            {"10-2024": 0, "11-2024": 0, "01-2025": 30.66, "02-2025": 30.03, "03-2025": 35.89},
            {"10-2024": 30.0, "11-2024": 30.0, "01-2025": 16.66, "02-2025": 15.09,
             "03-2025": 16.87},
        )  # fmt: skip
        prop = _cde(
            SHERIFF,
            {"10-2024": 0, "11-2024": 0, "01-2025": 1500, "02-2025": 1400, "03-2025": 1600},
            {"01-2025": 157.0, "02-2025": 146.5, "03-2025": 167.4},
            {"01-2025": 120.0, "02-2025": 110.0, "03-2025": 125.0},
        )

        summary = summarize(SHERIFF, "Florida", violent, prop)

        assert summary["reporting"] is True
        assert summary["months"] == 3
        assert (summary["period_start"], summary["period_end"]) == ("01-2025", "03-2025")
        assert summary["violent_per_100k"] == pytest.approx((30.66 + 30.03 + 35.89) * 4, abs=0.1)
        assert summary["state_violent_per_100k"] == pytest.approx(
            (16.66 + 15.09 + 16.87) * 4, abs=0.1
        )
        assert summary["property_per_100k"] == pytest.approx((157.0 + 146.5 + 167.4) * 4, abs=0.1)
        assert summary["population"] == 955_709

    def test_keeps_latest_twelve_months(self):
        months = [f"{m:02d}-2025" for m in range(1, 13)] + ["01-2026", "02-2026"]
        body = _cde(SHERIFF, {m: 10 for m in months}, {m: 1.0 for m in months}, {})

        summary = summarize(SHERIFF, "Florida", body, body)

        assert summary["months"] == 12
        assert (summary["period_start"], summary["period_end"]) == ("03-2025", "02-2026")
        assert summary["state_violent_per_100k"] is None

    def test_agency_not_reporting(self):
        name = "Orlando Police Department"
        body = _cde(name, {"01-2025": 0, "02-2025": 0}, {"01-2025": 0}, {"01-2025": 16.0})
        assert summarize(name, "Florida", body, body) == {"reporting": False}


class TestProvider:
    def _provider(self, place=None):
        provider = CrimeProvider()
        provider.api_client = FbiCdeAPIClient(api_key="k")
        provider.census_client.get_geographies = AsyncMock(
            return_value={
                "state": {"STUSAB": "FL", "NAME": "Florida"},
                "county": {"BASENAME": "Orange", "NAME": "Orange County"},
                "place": place,
            }
        )
        provider.api_client.get_agencies = AsyncMock(return_value=AGENCIES)
        body = _cde(SHERIFF, {"01-2025": 293}, {"01-2025": 30.66}, {"01-2025": 16.66})
        provider.api_client.get_monthly_offenses = AsyncMock(return_value=body)
        return provider

    @pytest.mark.asyncio
    async def test_enrich_unincorporated(self):
        provider = self._provider()

        result = await provider.enrich(28.4, -81.3, "x")

        assert result.success
        assert result.api_calls_made == 4
        assert result.data["agency"] == SHERIFF
        assert result.data["jurisdiction"] == "county"
        assert result.data["violent_per_100k"] == pytest.approx(367.9, abs=0.1)
        offenses = {c.args[1] for c in provider.api_client.get_monthly_offenses.call_args_list}
        assert offenses == {"violent-crime", "property-crime"}

    @pytest.mark.asyncio
    async def test_no_agency(self):
        provider = self._provider()
        provider.api_client.get_agencies = AsyncMock(return_value=[])

        result = await provider.enrich(28.4, -81.3, "x")

        assert not result.success
        assert "No police agency" in result.error_message

    @pytest.mark.asyncio
    async def test_api_error_redacts_key(self):
        provider = self._provider()
        request = httpx.Request("GET", "https://api.usa.gov/crime?API_KEY=secret123")
        provider.api_client.get_agencies = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429 for url 'https://api.usa.gov/crime?API_KEY=secret123'",
                request=request,
                response=httpx.Response(429, request=request),
            )
        )

        result = await provider.enrich(28.4, -81.3, "x")

        assert not result.success
        assert "secret123" not in result.error_message

    def test_skipped_without_key(self):
        provider = CrimeProvider()
        provider.api_client = FbiCdeAPIClient(api_key=None)
        with patch.object(provider.api_client, "api_key", None):
            assert provider.should_run() is False


class TestClient:
    @pytest.mark.asyncio
    async def test_agencies_flattened_deduplicated_and_cached(self):
        calls = []

        def handler(request):
            calls.append(request)
            agency = {"ori": "FL0640000", "agency_name": "Volusia County Sheriff's Office"}
            return httpx.Response(200, json={"VOLUSIA": [agency], "FLAGLER, VOLUSIA": [agency]})

        FbiCdeAPIClient._agencies.pop("ZZ", None)
        api = FbiCdeAPIClient(api_key="k")
        api._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        first = await api.get_agencies("zz")
        second = await api.get_agencies("ZZ")

        assert len(first) == 1 and second is first
        assert len(calls) == 1
        assert calls[0].url.path == "/crime/fbi/cde/agency/byStateAbbr/ZZ"
        assert calls[0].url.params["API_KEY"] == "k"
        FbiCdeAPIClient._agencies.pop("ZZ", None)

    @pytest.mark.asyncio
    async def test_offenses_request(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={})

        api = FbiCdeAPIClient(api_key="k")
        api._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        await api.get_monthly_offenses("FL0480000", "violent-crime", "05-2025", "11-2026")

        url = seen[0].url
        assert url.path == "/crime/fbi/cde/summarized/agency/FL0480000/violent-crime"
        assert (url.params["from"], url.params["to"]) == ("05-2025", "11-2026")

    @pytest.mark.asyncio
    async def test_missing_key(self):
        api = FbiCdeAPIClient(api_key=None)
        api.api_key = None
        with pytest.raises(ValueError, match="CRIME_DATA_API_KEY"):
            await api.get_agencies("FL")
