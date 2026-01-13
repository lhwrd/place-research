"""Mock property data API for development and testing."""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockPropertyDataAPI:
    """
    Mock property data API for development.

    Generates realistic fake data so you can develop without API keys.
    """

    PROPERTY_TYPES = [
        "Single Family",
        "Condo",
        "Townhouse",
        "Multi-Family",
        "Apartment",
    ]

    def __init__(self):
        """Initialize mock API."""
        self.call_count = 0

    async def validate_api_key(self) -> bool:
        """Always returns True for mock."""
        return True

    async def get_property_details(
        self, latitude: float, longitude: float, address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate mock property details."""
        self.call_count += 1

        # Generate realistic data based on coordinates
        random.seed(f"{latitude}{longitude}")

        bedrooms = random.randint(1, 5)
        bathrooms = random.choice([1, 1.5, 2, 2.5, 3, 3.5, 4])
        square_feet = random.randint(800, 4000)
        year_built = random.randint(1950, 2023)

        # Price based on square feet and age
        base_price_per_sqft = random.randint(200, 600)
        age_factor = 1 - ((2024 - year_built) * 0.005)  # Older = slightly cheaper
        estimated_value = int(square_feet * base_price_per_sqft * age_factor)

        # Last sold (some time in the past)
        years_ago = random.randint(1, 10)
        last_sold_date = datetime.now() - timedelta(days=years_ago * 365)
        last_sold_price = int(estimated_value * random.uniform(0.6, 0.9))

        return {
            "address": address or f"{random.randint(100, 9999)} Main St",
            "city": self._get_city_from_coords(latitude, longitude),
            "state": self._get_state_from_coords(latitude, longitude),
            "zip_code": f"{random.randint(10000, 99999)}",
            "county": f"{random.choice(['King', 'Pierce', 'Snohomish', 'Clark'])} County",
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "square_feet": square_feet,
            "lot_size": random.randint(3000, 10000),
            "year_built": year_built,
            "property_type": random.choice(self.PROPERTY_TYPES),
            "estimated_value": estimated_value,
            "last_sold_price": last_sold_price,
            "last_sold_date": last_sold_date,  # Return datetime object instead of string
            "tax_assessed_value": int(estimated_value * 0.9),
            "annual_tax": int(estimated_value * 0.01),
            "parcel_id": f"{random.randint(1000000000, 9999999999)}",
            "description": f"{bedrooms} bed, {bathrooms} bath {random.choice(self.PROPERTY_TYPES).lower()}",
        }

    async def get_property_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """Get property by address (mock)."""
        # Generate coordinates from address hash
        address_hash = hash(address)
        latitude = 47.6 + (address_hash % 100) / 1000
        longitude = -122.3 + (address_hash % 100) / 1000

        return await self.get_property_details(latitude, longitude, address)

    async def get_property_valuation(
        self,
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get mock valuation."""
        base_value = random.randint(300000, 1000000)

        return {
            "estimated_value": base_value,
            "value_low": int(base_value * 0.9),
            "value_high": int(base_value * 1.1),
            "confidence_score": random.uniform(0.7, 0.95),
            "valuation_date": datetime.now().strftime("%Y-%m-%d"),
        }

    async def get_sales_history(
        self,
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get mock sales history."""
        num_sales = random.randint(1, 4)
        sales = []

        current_price = random.randint(300000, 1000000)

        for i in range(num_sales):
            years_ago = (i + 1) * random.randint(3, 7)
            sale_date = datetime.now() - timedelta(days=years_ago * 365)

            # Price appreciation over time
            appreciation = 0.95**years_ago
            sale_price = int(current_price * appreciation)

            sales.append(
                {
                    "sale_date": sale_date.strftime("%Y-%m-%d"),
                    "sale_price": sale_price,
                    "sale_type": random.choice(["Resale", "New Construction", "Foreclosure"]),
                    "buyer_name": "Buyer Name (Redacted)",
                    "seller_name": "Seller Name (Redacted)",
                }
            )

        return sorted(sales, key=lambda x: x["sale_date"], reverse=True)

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
        """Mock property search."""
        results = []

        for i in range(min(limit, 10)):
            # Generate random coordinates
            lat = 47.6 + random.uniform(-0.2, 0.2)
            lon = -122.3 + random.uniform(-0.2, 0.2)

            property_data = await self.get_property_details(lat, lon)

            # Apply filters
            if min_price and property_data["estimated_value"] < min_price:
                continue
            if max_price and property_data["estimated_value"] > max_price:
                continue
            if min_bedrooms and property_data["bedrooms"] < min_bedrooms:
                continue
            if property_type and property_data["property_type"] != property_type:
                continue

            results.append(property_data)

        return results

    def _get_city_from_coords(self, latitude: float, longitude: float) -> str:
        """Get mock city name from coordinates."""
        cities = ["Seattle", "Bellevue", "Redmond", "Kirkland", "Tacoma"]
        return cities[int(abs(latitude * longitude)) % len(cities)]

    def _get_state_from_coords(self, latitude: float, longitude: float) -> str:
        """Get mock state from coordinates."""
        return "WA"
