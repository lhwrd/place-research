"""Base API client with common functionality for all external integrations."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional

import httpx

from app.exceptions import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
)

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 1.0):
    """
    Decorator to retry API calls on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    last_exception = e

                    # Don't retry on client errors (4xx)
                    if 400 <= e.response.status_code < 500:
                        raise

                    # Exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2**attempt)
                        logger.warning(
                            f"API call failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s:  {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                except Exception as e:
                    last_exception = e
                    raise

            # All retries exhausted
            raise last_exception

        return wrapper

    return decorator


class BaseAPIClient(ABC):
    """
    Base class for external API integrations.

    Provides common functionality:
    - HTTP client management
    - Rate limiting
    - Error handling
    - Request/response logging
    - API key management
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        rate_limit_per_second: Optional[float] = None,
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL for the API
            api_key:  API key for authentication
            timeout:  Request timeout in seconds
            rate_limit_per_second: Maximum requests per second
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit_per_second = rate_limit_per_second

        # Rate limiting state
        self._last_request_time = None
        self._request_count = 0

        # HTTP client (async)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting."""
        if not self.rate_limit_per_second:
            return

        if self._last_request_time:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            min_interval = 1.0 / self.rate_limit_per_second

            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                await asyncio.sleep(wait_time)

        self._last_request_time = datetime.now(timezone.utc)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to base_url)
            params: Query parameters
            json_data: JSON body data
            headers: Additional headers

        Returns:
            Response data as dictionary

        Raises:
            ExternalAPIError: On API errors
        """
        # Rate limiting
        await self._rate_limit()

        # Build URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Prepare headers
        request_headers = headers or {}
        if self.api_key:
            request_headers.update(self._get_auth_headers())

        # Log request
        logger.debug(
            f"API Request: {method} {url}",
            extra={
                "params": params,
                "headers": {
                    k: v for k, v in request_headers.items() if k.lower() != "authorization"
                },
            },
        )

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=request_headers,
            )

            # Raise on HTTP errors
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Log response
            logger.debug(
                f"API Response: {response.status_code}",
                extra={"response_size": len(response.content)},
            )

            return data

        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.RequestError as e:
            logger.error(f"API request failed: {str(e)}")
            raise ExternalAPIError(
                service=self._get_service_name(),
                message=f"Request failed: {str(e)}",
                status_code=503,
            ) from e
        except Exception as e:
            logger.error(f"Unexpected API error: {str(e)}")
            raise ExternalAPIError(
                service=self._get_service_name(),
                message=f"Unexpected error: {str(e)}",
                status_code=500,
            ) from e

    async def _handle_http_error(self, error: httpx.HTTPStatusError):
        """Handle HTTP errors and convert to appropriate exceptions."""
        status_code = error.response.status_code

        # Parse error response
        try:
            error_data = error.response.json()
            error_message = error_data.get("error", {}).get("message", str(error))
        except ValueError:
            error_message = error.response.text or str(error)

        logger.error(f"API HTTP error: {status_code}", extra={"error_message": error_message})

        # Handle specific status codes
        if status_code == 401:
            raise APIKeyInvalidError(service=self._get_service_name())
        elif status_code == 429:
            raise APIQuotaExceededError(service=self._get_service_name())
        else:
            raise ExternalAPIError(
                service=self._get_service_name(),
                message=error_message,
                api_status_code=status_code,
            )

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers.
        Override this method for custom auth.
        """
        return {}

    @abstractmethod
    def _get_service_name(self) -> str:
        """Return service name for error reporting."""

    @abstractmethod
    async def validate_api_key(self) -> bool:
        """
        Validate that API key is configured and working.

        Returns:
            True if valid, False otherwise
        """
