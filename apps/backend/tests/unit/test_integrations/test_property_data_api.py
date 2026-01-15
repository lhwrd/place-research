"""Tests for Property Data API integration."""

from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import PropertyDataAPIError
from app.integrations.property_data_api import PropertyDataAPI


@pytest.fixture
def mock_settings():
    """Mock settings for property data API."""
    with patch("app.integrations.property_data_api.settings") as mock:
        mock.property_data_api_base_url = "https://api.example.com"
        mock.property_data_api_key = "test_api_key"
        mock.property_data_provider = "attom"
        yield mock


@pytest.fixture
def property_api(mock_settings):
    """Create PropertyDataAPI instance with mocked settings."""
    return PropertyDataAPI()


@pytest.fixture
def sample_attom_response():
    """Sample Attom API response."""
    return {
        "property": [
            {
                "address": {
                    "line1": "123 Main St",
                    "locality": "Seattle",
                    "countrySubd": "WA",
                    "postal1": "98101",
                    "county": "King County",
                },
                "building": {
                    "size": {"livingSize": 2100},
                    "rooms": {"beds": 3, "bathsTotal": 2.5},
                    "summary": {
                        "yearbuilt": 2005,
                        "proptype": "Single Family",
                        "propsubtype": "Residential",
                    },
                },
                "lot": {"lotSize1": 5000, "apn": "1234567890"},
                "assessment": {
                    "assessed": {"assdTtlValue": 800000},
                    "tax": {"taxamt": 8500},
                    "market": {"mktTtlValue": 850000},
                },
                "sale": {"amount": {"saleamt": 650000, "salerecdate": "2018-05-15"}},
            }
        ]
    }


@pytest.mark.asyncio
class TestPropertyDataAPI:
    """Test PropertyDataAPI class."""

    async def test_init(self, property_api, mock_settings):
        """Test API initialization."""
        assert property_api.base_url == "https://api.example.com"
        assert property_api.api_key == "test_api_key"
        assert property_api.provider == "attom"
        assert property_api.timeout == 30.0

    async def test_get_service_name(self, property_api):
        """Test service name generation."""
        assert property_api._get_service_name() == "property_data_attom"

    async def test_get_auth_headers_attom(self, property_api):
        """Test auth headers for Attom provider."""
        headers = property_api._get_auth_headers()
        assert headers == {"apikey": "test_api_key", "Accept": "application/json"}

    async def test_get_auth_headers_zillow(self, property_api):
        """Test auth headers for Zillow provider."""
        property_api.provider = "zillow"
        headers = property_api._get_auth_headers()
        assert headers["X-RapidAPI-Key"] == "test_api_key"
        assert "X-RapidAPI-Host" in headers

    async def test_get_auth_headers_realty_mole(self, property_api):
        """Test auth headers for Realty Mole provider."""
        property_api.provider = "realty_mole"
        headers = property_api._get_auth_headers()
        assert headers["X-RapidAPI-Key"] == "test_api_key"
        assert "X-RapidAPI-Host" in headers

    async def test_validate_api_key_success(self, property_api):
        """Test API key validation success."""
        property_api.get_property_by_address = AsyncMock(return_value={"address": "123 Main St"})
        result = await property_api.validate_api_key()
        assert result is True

    async def test_validate_api_key_failure(self, property_api):
        """Test API key validation failure."""
        property_api.get_property_by_address = AsyncMock(
            side_effect=PropertyDataAPIError("Invalid key")
        )
        result = await property_api.validate_api_key()
        assert result is False

    async def test_get_property_details_attom(self, property_api, sample_attom_response):
        """Test getting property details from Attom."""
        property_api._make_request = AsyncMock(return_value=sample_attom_response)

        result = await property_api.get_property_details(
            47.6062, -122.3321, "123 Main St, Seattle, WA"
        )

        assert result["address"] == "123 Main St"
        assert result["city"] == "Seattle"
        assert result["state"] == "WA"
        assert result["zip_code"] == "98101"
        assert result["bedrooms"] == 3
        assert result["bathrooms"] == 2.5
        assert result["square_feet"] == 2100

    async def test_get_property_details_no_data(self, property_api):
        """Test getting property details with no data returned."""
        property_api._make_request = AsyncMock(return_value={})

        result = await property_api.get_property_details(
            47.6062, -122.3321, "123 Main St, Seattle, WA"
        )

        assert result["address"] is None
        assert result["city"] is None

    async def test_get_property_details_error(self, property_api):
        """Test getting property details with error."""
        property_api._make_request = AsyncMock(side_effect=Exception("API Error"))

        result = await property_api.get_property_details(
            47.6062, -122.3321, "123 Main St, Seattle, WA"
        )

        assert result["address"] is None

    async def test_get_property_by_address(self, property_api, sample_attom_response):
        """Test getting property by address."""
        property_api._make_request = AsyncMock(return_value=sample_attom_response)

        result = await property_api.get_property_by_address("123 Main St, Seattle, WA")

        assert result is not None
        assert result["address"] == "123 Main St"

    async def test_get_property_by_address_not_found(self, property_api):
        """Test getting property by address when not found."""
        property_api._make_request = AsyncMock(side_effect=Exception("Not found"))

        result = await property_api.get_property_by_address("Invalid Address")

        assert result is None

    async def test_get_property_valuation(self, property_api):
        """Test getting property valuation."""
        avm_response = {
            "property": [
                {
                    "avm": {
                        "amount": {
                            "value": 850000,
                            "valueLow": 800000,
                            "valueHigh": 900000,
                        },
                        "confidence": {"score": 0.85},
                        "eventDate": "2023-01-15",
                    }
                }
            ]
        }
        property_api._make_request = AsyncMock(return_value=avm_response)

        result = await property_api.get_property_valuation("123 Main St")

        assert result["estimated_value"] == 850000
        assert result["value_low"] == 800000
        assert result["value_high"] == 900000
        assert result["confidence_score"] == 0.85

    async def test_get_sales_history(self, property_api):
        """Test getting sales history."""
        sales_response = {
            "property": [
                {
                    "sale": {
                        "history": [
                            {
                                "amount": {
                                    "salerecdate": "2018-05-15",
                                    "saleamt": 650000,
                                },
                                "transaction": {"salestype": "Resale"},
                                "buyer": {"name1full": "John Doe"},
                                "seller": {"name1full": "Jane Smith"},
                            }
                        ]
                    }
                }
            ]
        }
        property_api._make_request = AsyncMock(return_value=sales_response)

        result = await property_api.get_sales_history("123 Main St")

        assert len(result) == 1
        assert result[0]["sale_price"] == 650000
        assert result[0]["sale_date"] == "2018-05-15"

    async def test_search_properties(self, property_api, sample_attom_response):
        """Test searching properties."""
        search_response = {"property": [sample_attom_response["property"][0]]}
        property_api._make_request = AsyncMock(return_value=search_response)

        result = await property_api.search_properties(
            city="Seattle", state="WA", min_bedrooms=3, limit=10
        )

        assert len(result) == 1
        assert result[0]["city"] == "Seattle"

    async def test_empty_property_data(self, property_api):
        """Test empty property data structure."""
        result = property_api._empty_property_data()

        assert result["address"] is None
        assert result["bedrooms"] is None
        assert "city" in result
        assert "parcel_id" in result

    async def test_parse_zillow_response(self, property_api):
        """Test parsing Zillow API response."""
        zillow_data = {
            "address": {
                "streetAddress": "456 Oak Ave",
                "city": "Portland",
                "state": "OR",
                "zipcode": "97201",
            },
            "bedrooms": 4,
            "bathrooms": 3,
            "livingArea": 2500,
            "yearBuilt": 2010,
            "homeType": "Single Family",
            "zestimate": 950000,
        }

        result = property_api._parse_zillow_response(zillow_data)

        assert result["address"] == "456 Oak Ave"
        assert result["city"] == "Portland"
        assert result["bedrooms"] == 4
        assert result["estimated_value"] == 950000

    async def test_parse_realty_mole_response(self, property_api):
        """Test parsing Realty Mole API response."""
        realty_data = {
            "formattedAddress": "789 Pine St",
            "city": "San Francisco",
            "state": "CA",
            "zipCode": "94102",
            "bedrooms": 2,
            "bathrooms": 2,
            "squareFootage": 1800,
            "yearBuilt": 2015,
            "assessedValue": 1200000,
        }

        result = property_api._parse_realty_mole_response(realty_data)

        assert result["address"] == "789 Pine St"
        assert result["city"] == "San Francisco"
        assert result["bedrooms"] == 2
