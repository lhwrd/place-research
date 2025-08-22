from unittest.mock import Mock, patch

import pytest

from place_research.models.place import Place
from place_research.providers.highways import HighwayProvider


class TestHighwayProvider:
    def test_haversine_distance_calculation(self):
        """Test the haversine distance calculation."""
        provider = HighwayProvider()

        # Test distance between known points (approximately)
        # Distance between NYC and Boston is roughly 306 km
        nyc_lat, nyc_lon = 40.7128, -74.0060
        boston_lat, boston_lon = 42.3601, -71.0589

        distance = provider._haversine_distance(
            nyc_lat, nyc_lon, boston_lat, boston_lon
        )

        # Should be roughly 306 km (306,000 meters), allow 10% tolerance
        assert 275000 < distance < 340000

    def test_estimate_road_noise_level(self):
        """Test road noise estimation."""
        provider = HighwayProvider()

        # Test motorway at reference distance (30m)
        noise_data = provider._estimate_road_noise_level(30.0, ["motorway"])
        assert noise_data["noise_level_db"] == 75.0
        assert noise_data["noise_category"] == "Very High"

        # Test far from highway
        noise_data = provider._estimate_road_noise_level(1000.0, ["motorway"])
        assert noise_data["noise_level_db"] < 60
        assert noise_data["noise_category"] in ["Low", "Very Low"]

        # Test with no distance
        noise_data = provider._estimate_road_noise_level(None, ["motorway"])
        assert noise_data["noise_level_db"] is None
        assert noise_data["noise_category"] == "Unknown"

    @patch("requests.post")
    def test_fetch_place_data_success(self, mock_post):
        """Test successful highway data fetching."""
        # Mock the Overpass API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "way",
                    "tags": {"highway": "motorway"},
                    "geometry": [
                        {"lat": 29.135, "lon": -80.982},
                        {"lat": 29.136, "lon": -80.983},
                    ],
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        provider = HighwayProvider()
        place = Place("Test Address", (29.1358887, -80.9828534))

        provider.fetch_place_data(place)

        # Verify attributes were set
        assert "highway_distance_m" in place.attributes
        assert "nearest_highway_type" in place.attributes
        assert "road_noise_level_db" in place.attributes
        assert "road_noise_category" in place.attributes
        assert place.attributes["nearest_highway_type"] == "motorway"

    @patch("requests.post")
    def test_fetch_place_data_no_highways(self, mock_post):
        """Test when no highways are found."""
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"elements": []}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        provider = HighwayProvider()
        place = Place("Test Address", (29.1358887, -80.9828534))

        provider.fetch_place_data(place)

        # Verify attributes indicate no highways
        assert place.attributes["highway_distance_m"] is None
        assert place.attributes["nearest_highway_type"] is None
        assert place.attributes["road_noise_level_db"] is None
        assert place.attributes["road_noise_category"] == "Very Low"

    @patch("requests.post")
    def test_fetch_place_data_api_error(self, mock_post):
        """Test API error handling."""
        # Mock request exception
        import requests

        mock_post.side_effect = requests.RequestException("API Error")

        provider = HighwayProvider()
        place = Place("Test Address", (29.1358887, -80.9828534))

        provider.fetch_place_data(place)

        # Verify error handling
        assert place.attributes["highway_distance_m"] is None
        assert "API Error" in place.attributes["highway_error"]
        assert place.attributes["road_noise_category"] == "Unknown"
