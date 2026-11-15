"""Tests for the file-based HighwayProvider."""

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from app.services import noise
from app.services.enrichment.providers import highways
from app.services.enrichment.providers.highways import HighwayProvider

LAT, LON = 29.0, -81.0
# ~111 m per 0.001 degree of latitude
METERS_PER_DEGREE_LAT = 110_950


def _roads(*rows):
    """rows: (MTFCC, FULLNAME, latitude offset of an east-west line through LON)."""
    return gpd.GeoDataFrame(
        {
            "LINEARID": [str(i) for i in range(len(rows))],
            "MTFCC": [r[0] for r in rows],
            "FULLNAME": [r[1] for r in rows],
        },
        geometry=[
            LineString([(LON - 0.05, LAT + offset), (LON + 0.05, LAT + offset)])
            for _, _, offset in rows
        ],
        crs="EPSG:4269",
    )


@pytest.fixture
def provider():
    return HighwayProvider(
        roads=_roads(
            ("S1200", "US Hwy 1", 0.001),  # ~111 m north
            ("S1100", "I- 95", -0.002),  # ~222 m south
            ("S1400", "Local Rd", 0.0001),  # local road: ignored
        )
    )


class TestEnrich:
    @pytest.mark.asyncio
    async def test_nearest_road_and_noise(self, provider):
        result = await provider.enrich(LAT, LON, "1 Main St")

        assert result.success
        data = result.data
        assert data["nearest_highway_type"] == "primary"
        assert data["nearest_highway_name"] == "US Hwy 1"
        # Mercator scale is corrected: within 2% of the true distance
        assert data["highway_distance_m"] == pytest.approx(0.001 * METERS_PER_DEGREE_LAT, rel=0.02)
        # The interstate 222 m away is louder than the nearer US highway 111 m away
        assert data["highway_distances_m"]["primary"] == data["highway_distance_m"]
        assert data["highway_distances_m"]["motorway"] == pytest.approx(222, rel=0.02)
        assert data["road_noise_level_db"] == pytest.approx(
            noise.loudest(noise.ROAD_LEVELS, {"primary": 111, "motorway": 222}), abs=0.3
        )
        assert data["road_noise_level_db"] > noise.loudest(noise.ROAD_LEVELS, {"primary": 111})
        assert data["road_noise_category"] == noise.category(data["road_noise_level_db"])

    @pytest.mark.asyncio
    async def test_outside_coverage_returns_no_data(self, provider):
        result = await provider.enrich(39.7, -105.0, "Denver")  # file only covers Florida

        assert result.success
        assert result.data == {}

    @pytest.mark.asyncio
    async def test_one_road_class_only(self):
        provider = HighwayProvider(roads=_roads(("S1100", None, 0.002)))

        data = (await provider.enrich(LAT, LON, "x")).data

        assert data["nearest_highway_type"] == "motorway"
        assert data["nearest_highway_name"] is None


class TestLoading:
    def test_shared_load_from_parquet(self, tmp_path, monkeypatch):
        path = tmp_path / "highways.parquet"
        _roads(("S1100", "I- 95", 0.001)).to_parquet(path)
        monkeypatch.setattr(highways.settings, "highways_path", path)
        monkeypatch.setattr(HighwayProvider, "_shared_roads", None)

        first, second = HighwayProvider(), HighwayProvider()

        assert first._roads is second._roads
        assert len(first._roads["motorway"]) == 1

    def test_geojson(self, tmp_path, monkeypatch):
        path = tmp_path / "highways.geojson"
        _roads(("S1200", "SR 5", 0.001)).to_file(path, driver="GeoJSON")
        monkeypatch.setattr(highways.settings, "highways_path", path)
        monkeypatch.setattr(HighwayProvider, "_shared_roads", None)

        assert len(HighwayProvider()._roads["primary"]) == 1

    def test_not_configured(self, monkeypatch):
        monkeypatch.setattr(highways.settings, "highways_path", None)
        monkeypatch.setattr(HighwayProvider, "_shared_roads", None)

        with pytest.raises(ValueError, match="HIGHWAYS_PATH"):
            HighwayProvider()

    def test_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(highways.settings, "highways_path", tmp_path / "nope.parquet")
        monkeypatch.setattr(HighwayProvider, "_shared_roads", None)

        with pytest.raises(FileNotFoundError):
            HighwayProvider()

    def test_requires_tiger_columns(self):
        roads = _roads(("S1100", "I- 95", 0.0)).drop(columns="MTFCC")
        with pytest.raises(ValueError, match="MTFCC"):
            HighwayProvider(roads=roads)

    def test_requires_crs(self):
        roads = _roads(("S1100", "I- 95", 0.0)).set_crs(None, allow_override=True)
        with pytest.raises(ValueError, match="CRS"):
            HighwayProvider(roads=roads)

    @pytest.mark.asyncio
    async def test_validate_config(self, provider):
        assert await provider.validate_config() is True
