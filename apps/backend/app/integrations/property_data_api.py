"""Property data API integration for fetching property details."""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.exceptions import PropertyDataAPIError
from app.integrations.base_client import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class PropertyDataAPI(BaseAPIClient):
    """
    Property data API client.

    Integrates with property data providers like:
    - Attom Data Solutions
    - CoreLogic
    - Zillow (via RapidAPI)
    - Realty Mole
    - DataTree

    This implementation uses a generic interface that can be adapted
    to any provider.  Currently configured for Attom Data Solutions.
    """

    # API endpoints
    PROPERTY_BASIC_PROFILE_ENDPOINT = "property/basicprofile"
    PROPERTY_DETAIL_ENDPOINT = "property/detail"
    PROPERTY_SEARCH_ENDPOINT = "property/search"
    PROPERTY_SNAPSHOT_ENDPOINT = "property/snapshot"
    AVM_ENDPOINT = "property/avm"  # Automated Valuation Model
    SALES_HISTORY_ENDPOINT = "property/saleshistory"

    def __init__(self):
        """Initialize property data API client."""
        super().__init__(
            base_url=settings.property_data_api_base_url,
            api_key=settings.property_data_api_key,
            timeout=30.0,
            rate_limit_per_second=10,  # Conservative rate limit
        )

        self.provider = settings.property_data_provider  # "attom", "zillow", "realty_mole"

    def _get_service_name(self) -> str:
        """Return service name."""
        return f"property_data_{self.provider}"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on provider."""
        if self.provider == "attom":
            return {"apikey": self.api_key, "Accept": "application/json"}
        elif self.provider == "zillow":
            # Zillow via RapidAPI
            return {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
            }
        elif self.provider == "realty_mole":
            return {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "realty-mole-property-api.p.rapidapi.com",
            }
        else:
            return {"Authorization": f"Bearer {self.api_key}"}

    async def validate_api_key(self) -> bool:
        """Validate API key is configured and working."""
        if not self.api_key:
            logger.error("Property Data API key is not configured")
            return False
        try:
            # Try a simple property lookup
            result = await self.get_property_by_address("123 Main St, New York, NY")
            # Ensure 200 OK and some data returned
            return result is not None
        except PropertyDataAPIError:
            return False

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def get_property_details(
        self, latitude: float, longitude: float, address: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive property details by coordinates.

        Args:
            latitude: Property latitude
            longitude: Property longitude
            address: Optional address for fallback lookup

        Returns:
            Dictionary with property details

        Example response:
            {
                "address": "123 Main St",
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "county": "King County",
                "bedrooms": 3,
                "bathrooms": 2.5,
                "square_feet": 2100,
                "lot_size":  5000,
                "year_built": 2005,
                "property_type": "Single Family",
                "estimated_value": 850000,
                "last_sold_price": 650000,
                "last_sold_date": "2018-05-15",
                "tax_assessed_value": 800000,
                "annual_tax":  8500,
                "parcel_id": "1234567890"
            }
        """
        if self.provider == "attom":
            return await self._get_property_details_attom(latitude, longitude, address)
        elif self.provider == "zillow":
            return await self._get_property_details_zillow(address)
        elif self.provider == "realty_mole":
            return await self._get_property_details_realty_mole(address)
        else:
            return await self._get_property_details_generic(latitude, longitude, address)

    async def _get_property_details_attom(
        self, latitude: float, longitude: float, address: str
    ) -> Dict[str, Any]:
        """Get property details from Attom Data Solutions."""
        address1 = address.split(",")[0].strip()
        address2 = address.split(",", 1)[1].strip()
        params = {"address1": address1, "address2": address2}

        try:
            data = await self._make_request(
                "GET", self.PROPERTY_BASIC_PROFILE_ENDPOINT, params=params
            )

            if not data or "property" not in data:
                logger.warning(
                    f"No property data found for coordinates:  ({latitude}, {longitude})"
                )
                return self._empty_property_data()

            return self._parse_attom_response(data)

        except Exception as e:
            logger.error(f"Attom API error: {str(e)}")
            # Return minimal data structure
            return self._empty_property_data()

    async def _get_property_details_zillow(self, address: str) -> Dict[str, Any]:
        """Get property details from Zillow API."""
        if not address:
            return self._empty_property_data()

        params = {"address": address}

        try:
            data = await self._make_request("GET", "propertyExtendedSearch", params=params)

            return self._parse_zillow_response(data)

        except Exception as e:
            logger.error(f"Zillow API error: {str(e)}")
            return self._empty_property_data()

    async def _get_property_details_realty_mole(self, address: str) -> Dict[str, Any]:
        """Get property details from Realty Mole API."""
        if not address:
            return self._empty_property_data()

        params = {"address": address}

        try:
            data = await self._make_request("GET", "properties", params=params)

            return self._parse_realty_mole_response(data)

        except Exception as e:
            logger.error(f"Realty Mole API error: {str(e)}")
            return self._empty_property_data()

    async def _get_property_details_generic(
        self, latitude: float, longitude: float, address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generic property data lookup (fallback)."""
        return self._empty_property_data()

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def get_property_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get property details by address.

        Args:
            address: Full property address

        Returns:
            Property details or None if not found
        """
        if self.provider == "attom":
            # Attom uses address parsing
            params = {"address1": address}

            try:
                data = await self._make_request("GET", self.PROPERTY_DETAIL_ENDPOINT, params=params)

                return self._parse_attom_response(data) if data else None

            except Exception as e:
                logger.error(f"Property lookup by address failed: {str(e)}")
                return None
        else:
            # Other providers
            return await self.get_property_details(0, 0, address)

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def get_property_valuation(
        self,
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get automated valuation (AVM) for a property.

        Args:
            address: Property address
            latitude: Optional latitude
            longitude: Optional longitude

        Returns:
            Valuation data:
            {
                "estimated_value": int,
                "value_low": int,
                "value_high": int,
                "confidence_score": float,
                "valuation_date": str
            }
        """
        if self.provider == "attom":
            params = {"address1": address}

            try:
                data = await self._make_request("GET", self.AVM_ENDPOINT, params=params)

                return self._parse_attom_avm(data)

            except Exception as e:
                logger.error(f"AVM lookup failed: {str(e)}")
                return None

        return None

    @retry_on_failure(max_retries=3, backoff_factor=1.0)
    async def get_sales_history(
        self,
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get sales history for a property.

        Args:
            address: Property address
            latitude: Optional latitude
            longitude: Optional longitude

        Returns:
            List of sales transactions
            [
                {
                    "sale_date": "2018-05-15",
                    "sale_price": 650000,
                    "sale_type": "Resale",
                    "buyer_name": ".. .",
                    "seller_name": "..."
                },
                ...
            ]
        """
        if self.provider == "attom":
            params = {"address1": address}

            try:
                data = await self._make_request("GET", self.SALES_HISTORY_ENDPOINT, params=params)

                return self._parse_attom_sales_history(data)

            except Exception as e:
                logger.error(f"Sales history lookup failed: {str(e)}")
                return []

        return []

    async def search_properties(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for properties matching criteria.

        Args:
            city: City name
            state: State code
            zip_code: ZIP code
            min_price:  Minimum price
            max_price:  Maximum price
            min_bedrooms: Minimum bedrooms
            property_type: Property type filter
            limit: Maximum results

        Returns:
            List of matching properties
        """
        params = {}

        if city:
            params["city"] = city
        if state:
            params["state"] = state
        if zip_code:
            params["postalcode"] = zip_code
        if min_price:
            params["minprice"] = min_price
        if max_price:
            params["maxprice"] = max_price
        if min_bedrooms:
            params["minbeds"] = min_bedrooms
        if property_type:
            params["propertytype"] = property_type

        params["pagesize"] = min(limit, 100)

        try:
            data = await self._make_request("GET", self.PROPERTY_SEARCH_ENDPOINT, params=params)

            return self._parse_property_search_results(data)

        except Exception as e:
            logger.error(f"Property search failed:  {str(e)}")
            return []

    # Parsing methods for different providers

    def _parse_attom_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Attom API response into standard format."""
        try:
            property_data = data.get("property", [{}])[0]
            area_data = property_data.get("area", {})
            address_data = property_data.get("address", {})
            building_data = property_data.get("building", {})
            size_data = building_data.get("size", {})
            rooms_data = building_data.get("rooms", {})
            # Summary is at property level, not building level
            summary_data = property_data.get("summary", {})
            assessment_data = property_data.get("assessment", {})
            market_data = property_data.get("assessment", {}).get("market", {})
            sale_data = property_data.get("sale", {})

            # Helper to safely convert to int
            def safe_int(value):
                if value is None:
                    return None
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    return None

            # Helper to safely convert to float
            def safe_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            return {
                "address": address_data.get("line1"),
                "city": address_data.get("locality"),
                "state": address_data.get("countrySubd"),
                "zip_code": address_data.get("postal1"),
                "county": area_data.get("countrySecSubd"),
                "bedrooms": safe_int(rooms_data.get("beds")),
                "bathrooms": safe_float(rooms_data.get("bathsTotal")),
                "square_feet": safe_int(
                    size_data.get("livingSize") or size_data.get("universalSize")
                ),
                "lot_size": safe_float(property_data.get("lot", {}).get("lotSize1")),
                "year_built": safe_int(summary_data.get("yearBuilt")),
                "property_type": summary_data.get("propertyType"),
                "estimated_value": safe_int(market_data.get("mktTtlValue")),
                "last_sold_price": safe_int(sale_data.get("saleAmountData", {}).get("saleAmt")),
                "last_sold_date": sale_data.get("saleAmountData", {}).get("saleRecDate"),
                "tax_assessed_value": safe_int(
                    assessment_data.get("assessed", {}).get("assdTtlValue")
                ),
                "annual_tax": safe_int(assessment_data.get("tax", {}).get("taxAmt")),
                "parcel_id": property_data.get("identifier", {}).get("apn"),
                "description": summary_data.get("propSubType"),
            }
        except Exception as e:
            logger.error(f"Failed to parse Attom response: {str(e)}")
            return self._empty_property_data()

    def _parse_zillow_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Zillow API response into standard format."""
        try:
            return {
                "address": data.get("address", {}).get("streetAddress"),
                "city": data.get("address", {}).get("city"),
                "state": data.get("address", {}).get("state"),
                "zip_code": data.get("address", {}).get("zipcode"),
                "county": None,
                "bedrooms": data.get("bedrooms"),
                "bathrooms": data.get("bathrooms"),
                "square_feet": data.get("livingArea"),
                "lot_size": data.get("lotSize"),
                "year_built": data.get("yearBuilt"),
                "property_type": data.get("homeType"),
                "estimated_value": data.get("zestimate"),
                "last_sold_price": data.get("price"),
                "last_sold_date": None,
                "tax_assessed_value": data.get("taxAssessedValue"),
                "annual_tax": data.get("taxAnnualAmount"),
                "parcel_id": None,
                "description": data.get("description"),
            }
        except Exception as e:
            logger.error(f"Failed to parse Zillow response: {str(e)}")
            return self._empty_property_data()

    def _parse_realty_mole_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Realty Mole API response into standard format."""
        try:
            return {
                "address": data.get("formattedAddress"),
                "city": data.get("city"),
                "state": data.get("state"),
                "zip_code": data.get("zipCode"),
                "county": data.get("county"),
                "bedrooms": data.get("bedrooms"),
                "bathrooms": data.get("bathrooms"),
                "square_feet": data.get("squareFootage"),
                "lot_size": data.get("lotSize"),
                "year_built": data.get("yearBuilt"),
                "property_type": data.get("propertyType"),
                "estimated_value": data.get("assessedValue"),
                "last_sold_price": data.get("lastSalePrice"),
                "last_sold_date": data.get("lastSaleDate"),
                "tax_assessed_value": data.get("assessedValue"),
                "annual_tax": None,
                "parcel_id": data.get("addressParcelNumber"),
                "description": None,
            }
        except Exception as e:
            logger.error(f"Failed to parse Realty Mole response: {str(e)}")
            return self._empty_property_data()

    def _parse_attom_avm(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Attom AVM response."""
        try:
            avm_data = data.get("property", [{}])[0].get("avm", {})

            return {
                "estimated_value": avm_data.get("amount", {}).get("value"),
                "value_low": avm_data.get("amount", {}).get("valueLow"),
                "value_high": avm_data.get("amount", {}).get("valueHigh"),
                "confidence_score": avm_data.get("confidence", {}).get("score"),
                "valuation_date": avm_data.get("eventDate"),
            }
        except Exception as e:
            logger.error(f"Failed to parse Attom AVM:  {str(e)}")
            return None

    def _parse_attom_sales_history(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Attom sales history response."""
        try:
            sales = data.get("property", [{}])[0].get("sale", {}).get("history", [])

            return [
                {
                    "sale_date": sale.get("amount", {}).get("salerecdate"),
                    "sale_price": sale.get("amount", {}).get("saleamt"),
                    "sale_type": sale.get("transaction", {}).get("salestype"),
                    "buyer_name": sale.get("buyer", {}).get("name1full"),
                    "seller_name": sale.get("seller", {}).get("name1full"),
                }
                for sale in sales
            ]
        except Exception as e:
            logger.error(f"Failed to parse sales history: {str(e)}")
            return []

    def _parse_property_search_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse property search results."""
        try:
            properties = data.get("property", [])
            return [self._parse_attom_response({"property": [prop]}) for prop in properties]
        except Exception as e:
            logger.error(f"Failed to parse search results: {str(e)}")
            return []

    def _empty_property_data(self) -> Dict[str, Any]:
        """Return empty property data structure."""
        return {
            "address": None,
            "city": None,
            "state": None,
            "zip_code": None,
            "county": None,
            "bedrooms": None,
            "bathrooms": None,
            "square_feet": None,
            "lot_size": None,
            "year_built": None,
            "property_type": None,
            "estimated_value": None,
            "last_sold_price": None,
            "last_sold_date": None,
            "tax_assessed_value": None,
            "annual_tax": None,
            "parcel_id": None,
            "description": None,
        }
