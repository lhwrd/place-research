"""Tests for Google Places API integration."""

from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import GoogleMapsAPIError
from app.integrations.google_places_api import GooglePlacesAPI


@pytest.fixture
def google_places_api():
    """Create GooglePlacesAPI instance."""
    with patch("app.integrations.google_places_api.settings") as mock_settings:
        mock_settings.google_maps_api_key = "test_api_key"
        return GooglePlacesAPI()


@pytest.fixture
def sample_place_response():
    """Sample place data from API."""
    return {
        "displayName": {"text": "Walmart Supercenter"},
        "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
        "location": {"latitude": 34.052235, "longitude": -118.243683},
        "formattedAddress": "123 Main St, Los Angeles, CA 90012",
        "primaryTypeDisplayName": {"text": "Grocery Store"},
    }


@pytest.fixture
def sample_nearby_response(sample_place_response):
    """Sample nearby search response."""
    return {"places": [sample_place_response]}


class TestGooglePlacesAPI:
    """Test GooglePlacesAPI class."""

    def test_init(self, google_places_api):
        """Test initialization."""
        assert google_places_api.api_key == "test_api_key"
        assert google_places_api.base_url == "https://places.googleapis.com/v1"
        assert google_places_api.timeout == 30.0

    def test_get_service_name(self, google_places_api):
        """Test service name."""
        assert google_places_api._get_service_name() == "google_places"

    def test_get_auth_headers(self, google_places_api):
        """Test auth headers."""
        headers = google_places_api._get_auth_headers()
        assert headers == {"X-Goog-Api-Key": "test_api_key"}

    def test_get_auth_headers_no_key(self):
        """Test auth headers without API key."""
        with patch("app.integrations.google_places_api.settings") as mock_settings:
            mock_settings.google_maps_api_key = None
            api = GooglePlacesAPI()
            assert api._get_auth_headers() == {}

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, google_places_api, sample_place_response):
        """Test API key validation success."""
        google_places_api._make_request = AsyncMock(return_value=sample_place_response)
        result = await google_places_api.validate_api_key()
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_failure(self, google_places_api):
        """Test API key validation failure."""
        google_places_api._make_request = AsyncMock(
            side_effect=GoogleMapsAPIError("Invalid key", 401)
        )
        result = await google_places_api.validate_api_key()
        assert result is False

    @pytest.mark.asyncio
    async def test_nearby_search_success(self, google_places_api, sample_nearby_response):
        """Test nearby search success."""
        google_places_api._make_request = AsyncMock(return_value=sample_nearby_response)

        results = await google_places_api.nearby_search(
            lat=34.052235,
            lon=-118.243683,
            place_types=["grocery_store"],
            radius_miles=5.0,
            max_results=3,
        )

        assert len(results) == 1
        assert results[0]["name"] == "Walmart Supercenter"
        assert results[0]["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"
        assert results[0]["latitude"] == 34.052235
        assert results[0]["longitude"] == -118.243683

    @pytest.mark.asyncio
    async def test_nearby_search_empty_results(self, google_places_api):
        """Test nearby search with empty results."""
        google_places_api._make_request = AsyncMock(return_value={"places": []})

        results = await google_places_api.nearby_search(
            lat=34.052235, lon=-118.243683, place_types=["grocery_store"]
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_nearby_search_radius_conversion(self, google_places_api, sample_nearby_response):
        """Test radius conversion from miles to meters."""
        google_places_api._make_request = AsyncMock(return_value=sample_nearby_response)

        await google_places_api.nearby_search(
            lat=34.052235,
            lon=-118.243683,
            place_types=["grocery_store"],
            radius_miles=5.0,
        )

        call_args = google_places_api._make_request.call_args
        assert call_args[1]["json_data"]["locationRestriction"]["circle"]["radius"] == 8046

    @pytest.mark.asyncio
    async def test_text_search_success(self, google_places_api, sample_nearby_response):
        """Test text search success."""
        google_places_api._make_request = AsyncMock(return_value=sample_nearby_response)

        results = await google_places_api.text_search(
            lat=34.052235,
            lon=-118.243683,
            text_query="walmart",
            radius_miles=5.0,
            max_results=3,
        )

        assert len(results) == 1
        assert results[0]["name"] == "Walmart Supercenter"

    @pytest.mark.asyncio
    async def test_text_search_restricts_to_rectangle(self, google_places_api):
        """Text Search rejects a circle in locationRestriction; it only takes a rectangle."""
        google_places_api._make_request = AsyncMock(return_value={"places": []})

        await google_places_api.text_search(
            lat=40.0, lon=-105.0, text_query="Costco", radius_miles=10.0, max_results=2
        )

        body = google_places_api._make_request.call_args[1]["json_data"]
        assert body["textQuery"] == "Costco"
        assert body["pageSize"] == 6
        assert body["rankPreference"] == "DISTANCE"
        assert "circle" not in body["locationRestriction"]
        rect = body["locationRestriction"]["rectangle"]
        assert rect["low"]["latitude"] < 40.0 < rect["high"]["latitude"]
        assert rect["low"]["longitude"] < -105.0 < rect["high"]["longitude"]

    @pytest.mark.asyncio
    async def test_text_search_drops_results_outside_radius(self, google_places_api):
        def place(name, lat, lon):
            return {"displayName": {"text": name}, "location": {"latitude": lat, "longitude": lon}}

        google_places_api._make_request = AsyncMock(
            return_value={
                "places": [
                    place("Near", 40.05, -105.0),  # ~3.5 mi
                    place("Corner", 40.14, -105.18),  # inside the box, ~13 mi away
                ]
            }
        )

        results = await google_places_api.text_search(
            lat=40.0, lon=-105.0, text_query="Costco", radius_miles=10.0
        )

        assert [r["name"] for r in results] == ["Near"]

    @pytest.mark.asyncio
    async def test_text_search_empty_results(self, google_places_api):
        """Test text search with empty results."""
        google_places_api._make_request = AsyncMock(return_value={"places": []})

        results = await google_places_api.text_search(
            lat=34.052235, lon=-118.243683, text_query="nonexistent"
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_place_details_success(self, google_places_api, sample_place_response):
        """Test place details success."""
        google_places_api._make_request = AsyncMock(return_value=sample_place_response)

        result = await google_places_api.place_details(place_id="ChIJN1t_tDeuEmsRUsoyG83frY4")

        assert result["name"] == "Walmart Supercenter"
        assert result["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"

    @pytest.mark.asyncio
    async def test_place_details_custom_fields(self, google_places_api, sample_place_response):
        """Test place details with custom fields."""
        google_places_api._make_request = AsyncMock(return_value=sample_place_response)

        await google_places_api.place_details(
            place_id="ChIJN1t_tDeuEmsRUsoyG83frY4", fields=["id", "displayName"]
        )

        call_args = google_places_api._make_request.call_args
        assert "X-Goog-FieldMask" in call_args[1]["headers"]

    @pytest.mark.asyncio
    async def test_place_details_empty_response(self, google_places_api):
        """Test place details with empty response."""
        google_places_api._make_request = AsyncMock(return_value={})

        with pytest.raises(GoogleMapsAPIError):
            await google_places_api.place_details(place_id="invalid_id")

    def test_parse_place_result(self, google_places_api, sample_place_response):
        """Test place result parsing."""
        parsed = google_places_api._parse_place_result(sample_place_response)

        assert parsed["name"] == "Walmart Supercenter"
        assert parsed["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"
        assert parsed["latitude"] == 34.052235
        assert parsed["longitude"] == -118.243683
        assert parsed["address"] == "123 Main St, Los Angeles, CA 90012"
        assert parsed["type"] == "Grocery Store"

    def test_parse_place_result_missing_fields(self, google_places_api):
        """Test place result parsing with missing fields."""
        minimal_place = {"id": "test_id"}
        parsed = google_places_api._parse_place_result(minimal_place)

        assert parsed["place_id"] == "test_id"
        assert parsed["name"] is None
        assert parsed["latitude"] is None


@pytest.mark.asyncio
async def test_text_search_one_result_per_store(google_places_api):
    def place(name, lat):
        return {"displayName": {"text": name}, "formattedAddress": name,
                "location": {"latitude": lat, "longitude": -105.0}}  # fmt: skip

    google_places_api._make_request = AsyncMock(
        return_value={
            "places": [
                place("Costco Gas Station", 40.0100),
                place("Costco Food Court", 40.0101),  # ~11 m away: same store
                place("Costco Wholesale", 40.0500),
                place("Costco Pharmacy", 40.0505),  # ~55 m away: same store
                place("Costco Wholesale #3", 40.0800),
            ]
        }
    )

    results = await google_places_api.text_search(
        lat=40.0, lon=-105.0, text_query="Costco", max_results=2
    )

    assert [r["name"] for r in results] == ["Costco Gas Station", "Costco Wholesale"]


@pytest.mark.parametrize("lat", [0.0, 40.0, 64.0])
def test_bounding_box_contains_circle(lat):
    from app.integrations.google_places_api import bounding_box
    from app.utils.distance_calculator import haversine_distance

    box = bounding_box(lat, -105.0, 16093)

    # Each edge's midpoint is the radius away from the center
    assert haversine_distance(lat, -105.0, box["high"]["latitude"], -105.0) == pytest.approx(
        16093, rel=0.01
    )
    assert haversine_distance(lat, -105.0, lat, box["high"]["longitude"]) == pytest.approx(
        16093, rel=0.01
    )
