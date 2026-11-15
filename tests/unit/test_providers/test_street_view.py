"""Tests for the StreetViewProvider."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.enrichment.providers.street_view import StreetViewProvider, bearing


@pytest.fixture
def provider():
    with patch("app.services.enrichment.providers.street_view.GoogleMapsAPI"):
        return StreetViewProvider()


@pytest.mark.asyncio
async def test_faces_the_house(provider):
    # Panorama on the street just south of the house: look north
    provider.api_client.street_view_metadata = AsyncMock(
        return_value={"pano_id": "abc", "latitude": 28.9997, "longitude": -81.0, "date": "2024-03"}
    )

    result = await provider.enrich(29.0, -81.0, "x")

    assert result.success
    assert result.data == {
        "available": True,
        "pano_id": "abc",
        "latitude": 28.9997,
        "longitude": -81.0,
        "date": "2024-03",
        "heading": 0,
    }


@pytest.mark.asyncio
async def test_uses_the_embed_key(provider, monkeypatch):
    from app.services.enrichment.providers import street_view

    monkeypatch.setattr(street_view.settings, "google_maps_embed_key", "embed-key")
    provider.api_client.street_view_metadata = AsyncMock(return_value=None)

    await provider.enrich(29.0, -81.0, "x")

    assert provider.api_client.street_view_metadata.call_args.kwargs["api_key"] == "embed-key"


@pytest.mark.asyncio
async def test_no_coverage_is_recorded(provider):
    provider.api_client.street_view_metadata = AsyncMock(return_value=None)

    result = await provider.enrich(29.0, -81.0, "x")

    assert result.data == {"available": False}


@pytest.mark.parametrize(
    "to,expected",
    [((29.001, -81.0), 0), ((29.0, -80.999), 90), ((28.999, -81.0), 180), ((29.0, -81.001), 270)],
)
def test_bearing(to, expected):
    assert bearing(29.0, -81.0, *to) == pytest.approx(expected, abs=0.1)
