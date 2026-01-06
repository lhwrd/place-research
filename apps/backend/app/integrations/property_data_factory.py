"""Factory for creating property data API instances."""

from typing import Union

from app.core.config import settings
from app.integrations.mock_property_data_api import MockPropertyDataAPI
from app.integrations.property_data_api import PropertyDataAPI


def get_property_data_api() -> Union[PropertyDataAPI, MockPropertyDataAPI]:
    """
    Get appropriate property data API instance based on configuration.

    Returns:
        PropertyDataAPI or MockPropertyDataAPI instance
    """
    if settings.use_mock_property_data or settings.property_data_provider == "mock":
        return MockPropertyDataAPI()
    else:
        return PropertyDataAPI()
