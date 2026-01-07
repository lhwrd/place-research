import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.integrations.walk_score_api import WalkScoreAPI
from app.exceptions import WalkScoreAPIError


@pytest.fixture
def walk_score_api():
    """Fixture to create WalkScoreAPI instance."""
    with patch("app.integrations.walk_score_api.settings") as mock_settings:
        mock_settings.walkscore_api_key = "test_api_key"
        return WalkScoreAPI()


@pytest.mark.asyncio
async def test_init(walk_score_api):
    """Test WalkScoreAPI initialization."""
    assert walk_score_api.base_url == "https://api.walkscore.com"
    assert walk_score_api.api_key == "test_api_key"
    assert walk_score_api.timeout == 30
    assert walk_score_api.rate_limit_per_second is None


@pytest.mark.asyncio
async def test_get_score_success(walk_score_api):
    """Test successful get_score call."""
    mock_response = {"status": 1, "walkscore": 85, "description": "Very Walkable"}

    walk_score_api._make_request = AsyncMock(return_value=mock_response)

    result = await walk_score_api.get_score(lat=47.608013, lon=-122.335167, address="Seattle, WA")

    assert result == mock_response
    walk_score_api._make_request.assert_called_once_with(
        method="GET",
        endpoint="score",
        params={
            "format": "json",
            "lat": 47.608013,
            "lon": -122.335167,
            "address": "Seattle, WA",
            "wsapikey": "test_api_key",
        },
    )


@pytest.mark.asyncio
async def test_get_score_error(walk_score_api):
    """Test get_score raises WalkScoreAPIError."""
    walk_score_api._make_request = AsyncMock(side_effect=WalkScoreAPIError("API error"))

    with pytest.raises(WalkScoreAPIError):
        await walk_score_api.get_score(lat=47.608013, lon=-122.335167, address="Seattle, WA")


@pytest.mark.asyncio
async def test_validate_api_key_success(walk_score_api):
    """Test successful API key validation."""
    mock_response = {"status": 1, "walkscore": 85}
    walk_score_api.get_score = AsyncMock(return_value=mock_response)

    result = await walk_score_api.validate_api_key()

    assert result is True
    walk_score_api.get_score.assert_called_once_with(
        lat=47.608013, lon=-122.335167, address="Seattle, WA"
    )


@pytest.mark.asyncio
async def test_validate_api_key_invalid_status(walk_score_api):
    """Test API key validation with invalid status."""
    mock_response = {"status": 0}
    walk_score_api.get_score = AsyncMock(return_value=mock_response)

    result = await walk_score_api.validate_api_key()

    assert result is False


@pytest.mark.asyncio
async def test_validate_api_key_exception(walk_score_api):
    """Test API key validation when exception is raised."""
    walk_score_api.get_score = AsyncMock(side_effect=WalkScoreAPIError("Invalid API key"))

    result = await walk_score_api.validate_api_key()

    assert result is False


@pytest.mark.asyncio
async def test_validate_api_key_missing_status(walk_score_api):
    """Test API key validation with missing status in response."""
    mock_response = {"walkscore": 85}
    walk_score_api.get_score = AsyncMock(return_value=mock_response)

    result = await walk_score_api.validate_api_key()

    assert result is False
