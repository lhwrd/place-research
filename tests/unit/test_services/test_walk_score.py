"""Tests for the per-page-view Walk Score lookup."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import walk_score
from app.services.walk_score import live_walk_scores

RESPONSE = {
    "status": 1,
    "walkscore": 85,
    "description": "Very Walkable",
    "ws_link": "https://www.walkscore.com/score/123-main-st",
    "bike": {"score": 75, "description": "Very Bikeable"},
    "transit": {"score": 60, "description": "Good Transit"},
}


@pytest.fixture
def api(monkeypatch):
    api = Mock(api_key="ws-key")
    api.get_score = AsyncMock(return_value=dict(RESPONSE))
    monkeypatch.setattr(walk_score, "_client", api)
    return api


@pytest.mark.asyncio
async def test_scores_and_link(api):
    scores = await live_walk_scores(40.7, -74.0, "123 Main St")

    assert scores == {
        "walk_score": 85,
        "description": "Very Walkable",
        "bike_score": 75,
        "bike_description": "Very Bikeable",
        "transit_score": 60,
        "transit_description": "Good Transit",
        "link": "https://www.walkscore.com/score/123-main-st",
    }
    api.get_score.assert_awaited_once_with(lat=40.7, lon=-74.0, address="123 Main St")


@pytest.mark.asyncio
async def test_every_call_asks_walk_score(api):
    """Nothing is cached: the terms don't allow it."""
    await live_walk_scores(40.7, -74.0, "123 Main St")
    await live_walk_scores(40.7, -74.0, "123 Main St")

    assert api.get_score.await_count == 2


@pytest.mark.asyncio
async def test_null_bike_and_transit(api):
    api.get_score.return_value = {**RESPONSE, "bike": None, "transit": None}

    scores = await live_walk_scores(40.7, -74.0, "x")

    assert scores["walk_score"] == 85
    assert scores["bike_score"] is None and scores["transit_score"] is None


@pytest.mark.asyncio
async def test_no_key_makes_no_request(api):
    api.api_key = None

    assert await live_walk_scores(40.7, -74.0, "x") == {}
    api.get_score.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [2, 40, 41])  # being calculated, bad key, quota exceeded
async def test_no_score(api, status):
    api.get_score.return_value = {"status": status}

    assert await live_walk_scores(40.7, -74.0, "x") == {}


@pytest.mark.asyncio
async def test_failure_is_not_raised(api):
    api.get_score.side_effect = RuntimeError("boom ?wsapikey=SECRET")

    assert await live_walk_scores(40.7, -74.0, "x") == {}


@pytest.mark.asyncio
async def test_slow_answer_is_abandoned(api):
    async def slow(**_):
        await asyncio.sleep(5)

    api.get_score.side_effect = slow

    assert await live_walk_scores(40.7, -74.0, "x", timeout=0.01) == {}
