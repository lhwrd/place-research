from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from app.services.enrichment.base_provider import ProviderCategory
from app.services.enrichment.providers.annual_average_climate import (
    AnnualAverageClimateProvider,
)


@pytest.fixture
def mock_climate_data():
    """Create mock climate data DataFrame."""
    return pd.DataFrame(
        {
            "STATION_ID": ["STATION1", "STATION2", "STATION3"],
            "STATION_NAME": ["Station One", "Station Two", "Station Three"],
            "LATITUDE": [40.0, 40.5, 41.0],
            "LONGITUDE": [-74.0, -74.5, -75.0],
            "ANN-TAVG-NORMAL": [55.0, 54.0, 53.0],
            "ANN-PRCP-NORMAL": [45.0, 46.0, 47.0],
        }
    )


@pytest.fixture
def provider(mock_climate_data):
    """Create provider instance with mocked data."""
    with patch(
        "app.services.enrichment.providers.annual_average_climate.settings"
    ) as mock_settings:
        mock_settings.annual_climate_path = "/fake/path/climate.csv"
        with patch.object(
            AnnualAverageClimateProvider, "_load_data", return_value=mock_climate_data
        ):
            return AnnualAverageClimateProvider()


def test_metadata(provider):
    """Test provider metadata."""
    metadata = provider.metadata
    assert metadata.name == "AnnualAverageClimateProvider"
    assert metadata.category == ProviderCategory.ENVIRONMENTAL
    assert metadata.enabled is True
    assert metadata.requires_api_key is False
    assert metadata.cost_per_call == 0.0
    assert metadata.version == "1.0.0"


@pytest.mark.asyncio
async def test_enrich_finds_nearest_station(provider):
    """Test that enrich finds the nearest station."""
    result = await provider.enrich(latitude=40.1, longitude=-74.1, address="123 Main St")

    assert result.success is True
    assert result.provider_name == "AnnualAverageClimateProvider"
    assert result.data["annual_average_temperature"] == 55.0
    assert result.data["annual_average_precipitation"] == 45.0
    assert result.api_calls_made == 0
    assert result.cached is False


@pytest.mark.asyncio
async def test_enrich_with_different_location(provider):
    """Test enrich with location closer to different station."""
    result = await provider.enrich(latitude=41.0, longitude=-75.0, address="456 Oak Ave")

    assert result.success is True
    assert result.data["annual_average_temperature"] == 53.0
    assert result.data["annual_average_precipitation"] == 47.0


@pytest.mark.asyncio
async def test_enrich_with_optional_params(provider):
    """Test enrich with optional property_data and user_preferences."""
    result = await provider.enrich(
        latitude=40.5,
        longitude=-74.5,
        address="789 Pine Rd",
        property_data={"type": "residential"},
        user_preferences={"climate": "mild"},
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_validate_config_success(provider):
    """Test validate_config returns True when properly configured."""
    with patch(
        "app.services.enrichment.providers.annual_average_climate.settings"
    ) as mock_settings:
        mock_settings.annual_climate_path = "/fake/path/climate.csv"
        result = await provider.validate_config()
        assert result is True


@pytest.mark.asyncio
async def test_validate_config_no_path():
    """Test validate_config returns False when path is missing."""
    with patch(
        "app.services.enrichment.providers.annual_average_climate.settings"
    ) as mock_settings:
        mock_settings.annual_climate_path = None
        with patch.object(AnnualAverageClimateProvider, "_load_data", return_value=pd.DataFrame()):
            provider = AnnualAverageClimateProvider()
            result = await provider.validate_config()
            assert result is False


@pytest.mark.asyncio
async def test_validate_config_no_data():
    """Test validate_config returns False when data is None."""
    with patch(
        "app.services.enrichment.providers.annual_average_climate.settings"
    ) as mock_settings:
        mock_settings.annual_climate_path = "/fake/path/climate.csv"
        with patch.object(AnnualAverageClimateProvider, "_load_data", return_value=None):
            provider = AnnualAverageClimateProvider()
            result = await provider.validate_config()
            assert result is False


def test_load_data():
    """Test _load_data reads CSV file."""
    mock_df = pd.DataFrame({"col": [1, 2, 3]})
    with patch("pandas.read_csv", return_value=mock_df) as mock_read_csv:
        with patch(
            "app.services.enrichment.providers.annual_average_climate.settings"
        ) as mock_settings:
            mock_settings.annual_climate_path = "/fake/path/climate.csv"
            provider = AnnualAverageClimateProvider()
            mock_read_csv.assert_called_once_with("/fake/path/climate.csv")
