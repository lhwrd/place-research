"""Tests for the file-based RailroadProvider."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from app.services.enrichment.providers import railroads
from app.services.enrichment.providers.railroads import RailroadProvider

# ~111 km per degree of latitude
METERS_PER_DEGREE_LAT = 110_950


def _east_west_lines(lat, lon, *offsets):
    """East-west rail lines `offset` degrees north of (lat, lon)."""
    return gpd.GeoDataFrame(
        geometry=[LineString([(lon - 0.05, lat + o), (lon + 0.05, lat + o)]) for o in offsets],
        crs="EPSG:4326",
    )


class TestDistance:
    @pytest.mark.parametrize("lat", [0.0, 29.0, 40.0, 47.0])
    @pytest.mark.asyncio
    async def test_true_distance_at_any_latitude(self, lat):
        """Web Mercator's stretch (14% at 29°N, 30% at 40°N) is corrected."""
        provider = RailroadProvider(raillines_data=_east_west_lines(lat, -100.0, 0.01, -0.05))

        result = await provider.enrich(lat, -100.0, "x")

        assert result.success
        assert result.api_calls_made == 0
        assert result.data["railroad_distance_m"] == pytest.approx(
            0.01 * METERS_PER_DEGREE_LAT, rel=0.01
        )

    def test_providers_keep_their_own_data(self):
        near = RailroadProvider(raillines_data=_east_west_lines(29.0, -81.0, 0.001))
        far = RailroadProvider(raillines_data=_east_west_lines(29.0, -81.0, 0.02))

        assert near._calculate_nearest_distance(29.0, -81.0) < 150
        assert far._calculate_nearest_distance(29.0, -81.0) > 2000

    @pytest.mark.asyncio
    async def test_no_lines(self):
        provider = RailroadProvider(raillines_data=_east_west_lines(29.0, -81.0))

        result = await provider.enrich(29.0, -81.0, "x")

        assert result.success
        assert result.data == {}
        assert await provider.validate_config() is False

    @pytest.mark.asyncio
    async def test_ignores_abandoned_track_and_finds_main_line(self):
        lines = _east_west_lines(29.0, -81.0, 0.001, 0.002, 0.005, 0.01)
        lines["NET_CODE"] = ["A", "X", "O", "M"]  # abandoned, out of service, spur, main

        data = (await RailroadProvider(raillines_data=lines).enrich(29.0, -81.0, "x")).data

        assert data["railroad_distance_m"] == pytest.approx(0.005 * METERS_PER_DEGREE_LAT, rel=0.01)
        assert data["mainline_distance_m"] == pytest.approx(0.01 * METERS_PER_DEGREE_LAT, rel=0.01)

    @pytest.mark.asyncio
    async def test_without_net_codes_all_lines_count(self):
        data = (
            await RailroadProvider(raillines_data=_east_west_lines(29.0, -81.0, 0.01)).enrich(
                29.0, -81.0, "x"
            )
        ).data

        assert "mainline_distance_m" not in data
        assert data["railroad_distance_m"] > 0

    def test_requires_crs(self):
        lines = _east_west_lines(29.0, -81.0, 0.01).set_crs(None, allow_override=True)
        with pytest.raises(ValueError, match="CRS"):
            RailroadProvider(raillines_data=lines)


class TestLoading:
    @pytest.mark.parametrize("suffix", [".geojson", ".parquet"])
    def test_shared_load(self, tmp_path, monkeypatch, suffix):
        path = tmp_path / f"rails{suffix}"
        lines = _east_west_lines(29.0, -81.0, 0.01, 0.02)
        if suffix == ".parquet":
            lines.to_parquet(path)
        else:
            lines.to_file(path, driver="GeoJSON")
        monkeypatch.setattr(railroads.settings, "raillines_path", path)
        monkeypatch.setattr(RailroadProvider, "_shared_raillines", None)

        first, second = RailroadProvider(), RailroadProvider()

        assert first._raillines is second._raillines
        assert len(first._raillines.all) == 2
        assert first._calculate_nearest_distance(29.0, -81.0) == pytest.approx(1110, rel=0.01)

    def test_not_configured(self, monkeypatch):
        monkeypatch.setattr(railroads.settings, "raillines_path", None)
        monkeypatch.setattr(RailroadProvider, "_shared_raillines", None)

        with pytest.raises(ValueError, match="RAILLINES_PATH"):
            RailroadProvider()

    def test_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(railroads.settings, "raillines_path", tmp_path / "nope.parquet")
        monkeypatch.setattr(RailroadProvider, "_shared_raillines", None)

        with pytest.raises(FileNotFoundError):
            RailroadProvider()

    def test_metadata(self):
        metadata = RailroadProvider(raillines_data=_east_west_lines(0, 0, 0.1)).metadata
        assert metadata.name == "railroad_provider"
        assert metadata.requires_api_key is False
