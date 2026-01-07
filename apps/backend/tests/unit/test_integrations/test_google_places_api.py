import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.integrations.google_places_api import GooglePlacesAPI
from app.exceptions import GoogleMapsAPIError

"""Tests for Google Places API integration."""


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
        "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
        "displayName": {"text": "Walmart Supercenter"},
        "formattedAddress": {"text": "123 Main St, Los Angeles, CA 90012"},
        "location": {"latitude": 34.052235, "longitude": -118.243683},
        "primaryTypeDisplayName": "Grocery Store",
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
