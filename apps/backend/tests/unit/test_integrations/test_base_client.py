"""Tests for base API client functionality."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import httpx
import pytest

from app.exceptions import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
)
from app.integrations.base_client import BaseAPIClient, retry_on_failure


class ConcreteAPIClient(BaseAPIClient):
    """Concrete implementation for testing."""

    def _get_service_name(self) -> str:
        return "TestService"

    async def validate_api_key(self) -> bool:
        return self.api_key is not None

    def _get_auth_headers(self):
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}


@pytest.fixture
def client():
    """Create test client instance."""
    return ConcreteAPIClient(
        base_url="https://api.example.com",
        api_key="test_key",
        timeout=10.0,
    )


@pytest.fixture
def rate_limited_client():
    """Create rate-limited test client."""
    return ConcreteAPIClient(
        base_url="https://api.example.com",
        api_key="test_key",
        rate_limit_per_second=2.0,
    )


class TestBaseAPIClient:
    """Test BaseAPIClient class."""

    def test_init(self, client):
        """Test client initialization."""
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test_key"
        assert client.timeout == 10.0
        assert client._client is None

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base_url."""
        client = ConcreteAPIClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    def test_client_property_creates_client(self, client):
        """Test that client property creates HTTP client."""
        http_client = client.client
        assert isinstance(http_client, httpx.AsyncClient)
        assert http_client.timeout.read == 10.0

    def test_client_property_reuses_client(self, client):
        """Test that client property reuses existing client."""
        http_client1 = client.client
        http_client2 = client.client
        assert http_client1 is http_client2

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing HTTP client."""
        _ = client.client  # Create client
        await client.close()
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_rate_limit_no_limit(self, client):
        """Test rate limiting when no limit is set."""
        start = datetime.now(timezone.utc)
        await client._rate_limit()
        await client._rate_limit()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        assert elapsed < 0.1  # Should be nearly instant

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, rate_limited_client):
        """Test that rate limiting is enforced."""
        start = datetime.now(timezone.utc)
        await rate_limited_client._rate_limit()
        await rate_limited_client._rate_limit()
        await rate_limited_client._rate_limit()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        # 2 requests/sec = 0.5s between requests, so 3 requests ~= 1s
        assert elapsed >= 0.9

    @pytest.mark.asyncio
    async def test_make_request_success(self, client):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.content = b'{"data": "test"}'

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            result = await client._make_request("GET", "/test", params={"q": "value"})

            assert result == {"data": "test"}
            mock_http_client.request.assert_called_once()
            call_kwargs = mock_http_client.request.call_args.kwargs
            assert call_kwargs["method"] == "GET"
            assert call_kwargs["url"] == "https://api.example.com/test"
            assert call_kwargs["params"] == {"q": "value"}
            assert "Authorization" in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_make_request_with_auth_headers(self, client):
        """Test that auth headers are added."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.content = b"{}"

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            await client._make_request("GET", "/test")

            headers = mock_http_client.request.call_args.kwargs["headers"]
            assert headers["Authorization"] == "Bearer test_key"

    @pytest.mark.asyncio
    async def test_make_request_401_error(self, client):
        """Test handling of 401 Unauthorized error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

        error = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=mock_response)

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(side_effect=error)

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            with pytest.raises(APIKeyInvalidError) as exc_info:
                await client._make_request("GET", "/test")

            assert exc_info.value.details["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_make_request_429_error(self, client):
        """Test handling of 429 Rate Limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}

        error = httpx.HTTPStatusError("Too Many Requests", request=Mock(), response=mock_response)

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(side_effect=error)

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            with pytest.raises(APIQuotaExceededError) as exc_info:
                await client._make_request("GET", "/test")

            assert exc_info.value.details["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_make_request_500_error(self, client):
        """Test handling of 500 Server Error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal server error"}}

        error = httpx.HTTPStatusError("Server Error", request=Mock(), response=mock_response)

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(side_effect=error)

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            with pytest.raises(ExternalAPIError) as exc_info:
                await client._make_request("GET", "/test")

            assert exc_info.value.details["service"] == "TestService"
            assert exc_info.value.details["api_status_code"] == 500

    @pytest.mark.asyncio
    async def test_make_request_network_error(self, client):
        """Test handling of network errors."""
        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

        with patch.object(
            type(client),
            "client",
            new_callable=PropertyMock,
            return_value=mock_http_client,
        ):
            with pytest.raises(ExternalAPIError) as exc_info:
                await client._make_request("GET", "/test")

            assert exc_info.value.status_code == 503
            assert "Request failed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_handle_http_error_with_json_response(self, client):
        """Test error handling with JSON error response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": {"message": "Not found"}}

        error = httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_response)

        with pytest.raises(ExternalAPIError) as exc_info:
            await client._handle_http_error(error)

        assert "Not found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_handle_http_error_with_text_response(self, client):
        """Test error handling with plain text error response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Page not found"

        error = httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_response)

        with pytest.raises(ExternalAPIError) as exc_info:
            await client._handle_http_error(error)

        assert "Page not found" in exc_info.value.message


class TestRetryDecorator:
    """Test retry_on_failure decorator."""

    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        mock_func = AsyncMock(return_value="success")
        decorated = retry_on_failure(max_retries=3)(mock_func)

        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful execution after retries."""
        mock_func = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "Server Error", request=Mock(), response=Mock(status_code=500)
                ),
                httpx.HTTPStatusError(
                    "Server Error", request=Mock(), response=Mock(status_code=503)
                ),
                "success",
            ]
        )
        decorated = retry_on_failure(max_retries=3, backoff_factor=0.01)(mock_func)

        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_no_retry_on_4xx(self):
        """Test that 4xx errors are not retried."""
        mock_response = Mock(status_code=404)
        error = httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_response)
        mock_func = AsyncMock(side_effect=error)
        decorated = retry_on_failure(max_retries=3)(mock_func)

        with pytest.raises(httpx.HTTPStatusError):
            await decorated()

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test that exception is raised after all retries exhausted."""
        mock_response = Mock(status_code=500)
        error = httpx.HTTPStatusError("Server Error", request=Mock(), response=mock_response)
        mock_func = AsyncMock(side_effect=error)
        decorated = retry_on_failure(max_retries=3, backoff_factor=0.01)(mock_func)

        with pytest.raises(httpx.HTTPStatusError):
            await decorated()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Test exponential backoff timing."""
        mock_response = Mock(status_code=500)
        error = httpx.HTTPStatusError("Server Error", request=Mock(), response=mock_response)
        mock_func = AsyncMock(side_effect=error)
        decorated = retry_on_failure(max_retries=3, backoff_factor=0.1)(mock_func)

        start = datetime.now()
        with pytest.raises(httpx.HTTPStatusError):
            await decorated()
        elapsed = (datetime.now() - start).total_seconds()

        # Backoff: 0.1 * 2^0 + 0.1 * 2^1 = 0.1 + 0.2 = 0.3 seconds
        assert elapsed >= 0.25

    @pytest.mark.asyncio
    async def test_retry_non_http_exception_raised_immediately(self):
        """Test that non-HTTP exceptions are raised immediately."""
        error = ValueError("Some error")
        mock_func = AsyncMock(side_effect=error)
        decorated = retry_on_failure(max_retries=3)(mock_func)

        with pytest.raises(ValueError):
            await decorated()

        assert mock_func.call_count == 1
