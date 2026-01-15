"""Example tests for RailroadProvider showing improved testability."""

from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from app.services.enrichment.providers.railroads import RailroadProvider


@pytest.fixture
def mock_railroad_data():
    """Create mock railroad data for testing."""
    # Create a simple railroad line
    lines = [
        LineString([(0, 0), (1, 1)]),
        LineString([(2, 2), (3, 3)]),
    ]
    return gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")


class TestRailroadProviderTestability:
    """Examples demonstrating improved testability."""

    @pytest.mark.asyncio
    async def test_enrich_with_injected_data(self, mock_railroad_data):
        """Test enrichment by injecting mock data - no file I/O needed."""
        # BEFORE: Had to create actual files or mock settings and gpd.read_file
        # NOW: Just inject the data directly
        provider = RailroadProvider(raillines_data=mock_railroad_data)

        result = await provider.enrich(latitude=0.5, longitude=0.5, address="123 Test St")

        assert result.success
        assert "railroad_distance_m" in result.data
        assert result.data["railroad_distance_m"] >= 0

    def test_calculate_distance_isolated(self, mock_railroad_data):
        """Test distance calculation logic in isolation."""
        # BEFORE: Had to test through enrich() method
        # NOW: Can test the calculation directly
        provider = RailroadProvider(raillines_data=mock_railroad_data)

        distance = provider._calculate_nearest_distance(0.5, 0.5)

        assert isinstance(distance, int)
        assert distance >= 0

    def test_load_geodataframe_can_be_mocked(self):
        """Test that file loading can be easily mocked."""
        # BEFORE: Had to mock gpd.read_file globally
        # NOW: Can mock just the provider's method
        provider = RailroadProvider.__new__(RailroadProvider)
        provider._raillines_data = None
        provider.logger = Mock()

        mock_gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
        provider._load_geodataframe = Mock(return_value=mock_gdf)

        with (
            patch("app.services.enrichment.providers.railroads.settings") as mock_settings,
            patch("app.services.enrichment.providers.railroads.Path.exists", return_value=True),
        ):
            mock_settings.raillines_path = "/fake/path.geojson"
            provider._load_raillines_data()

        assert provider._raillines_data is not None
        provider._load_geodataframe.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_without_file_dependency(self):
        """Complete end-to-end test without touching filesystem."""
        # Create test data
        lines = [LineString([(0, 0), (1, 1)])]
        test_data = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")

        # Test without any file I/O
        provider = RailroadProvider(raillines_data=test_data)

        result = await provider.enrich(latitude=0.5, longitude=0.5, address="Test Location")

        assert result.success
        assert result.provider_name == "railroad_provider"
        assert result.api_calls_made == 0
