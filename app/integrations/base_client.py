"""Base API client with common functionality for all external integrations."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx

from app.core.redaction import redact_secrets
from app.exceptions import (
    APIKeyInvalidError,
    APIQuotaExceededError,
    ExternalAPIError,
)

logger = logging.getLogger(__name__)

# Some APIs (e.g. Overpass) reject httpx's default User-Agent
USER_AGENT = "place-research/2.0 (+https://github.com/lhwrd/place-research)"

# Statuses public APIs use for "busy, try again"
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)


async def send_with_retry(
    send: Callable[[], Awaitable[httpx.Response]],
    service: str,
    max_attempts: int = 4,
    backoff_seconds: float = 2.0,
    retry_statuses: tuple = RETRYABLE_STATUSES,
) -> httpx.Response:
    """
    Send a request, retrying transport errors and busy statuses with exponential backoff.

    Args:
        send: Zero-argument coroutine function that sends the request
        service: Name for log messages
        max_attempts: Total attempts, including the first
        backoff_seconds: Wait before the first retry; doubles each time
        retry_statuses: Response statuses worth retrying

    Returns:
        The last response (the caller decides how to handle its status)

    Raises:
        httpx.TransportError: If the final attempt fails to connect or times out
    """
    for attempt in range(1, max_attempts + 1):
        try:
            response = await send()
        except httpx.TransportError as e:
            if attempt == max_attempts:
                raise
            reason = type(e).__name__
        else:
            if response.status_code not in retry_statuses or attempt == max_attempts:
                return response
            reason = f"HTTP {response.status_code}"

        delay = backoff_seconds * 2 ** (attempt - 1)
        logger.warning(
            "%s busy (%s), retrying in %.0fs (attempt %d/%d)",
            service,
            reason,
            delay,
            attempt,
            max_attempts,
        )
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


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
                            "API call failed (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1,
                            max_retries,
                            wait_time,
                            str(e),
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "wait_time": wait_time,
                            },
                        )
                        await asyncio.sleep(wait_time)
                except Exception as e:
                    last_exception = e
                    # Don't retry on unexpected exceptions
                    logger.error(
                        "Unexpected error during API call: %s",
                        str(e),
                        extra={"error": str(e), "error_type": type(e).__name__},
                        exc_info=True,
                    )
                    raise

            # All retries exhausted
            if last_exception:
                raise last_exception
            raise RuntimeError("Max retries reached without exception")

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
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
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
                logger.debug(
                    "Rate limiting: waiting %.3fs (limit: %d req/s)",
                    wait_time,
                    self.rate_limit_per_second,
                    extra={
                        "wait_time": wait_time,
                        "rate_limit": self.rate_limit_per_second,
                    },
                )
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
        logger.info(
            "%s API request: %s %s",
            self._get_service_name(),
            method,
            endpoint,
            extra={
                "service": self._get_service_name(),
                "method": method,
                "endpoint": endpoint,
                "url": url,
                "params": params,
                "has_body": json_data is not None,
            },
        )
        # Log headers (mask sensitive values)
        masked_headers = {}
        for k, v in request_headers.items():
            if k.lower() in [
                "authorization",
                "x-goog-api-key",
                "apikey",
                "x-rapidapi-key",
            ]:
                # Show first/last 4 chars for debugging
                masked_headers[k] = f"{v[:4]}...{v[-4:]}" if len(v) > 8 else "***"
            else:
                masked_headers[k] = v

        logger.debug(
            "%s request details - params: %s",
            self._get_service_name(),
            params,
            extra={
                "headers": masked_headers,
                "has_api_key": self.api_key is not None,
                "api_key_length": len(self.api_key) if self.api_key else 0,
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

            # Log successful response
            logger.info(
                "%s API response: %d - %d bytes",
                self._get_service_name(),
                response.status_code,
                len(response.content),
                extra={
                    "service": self._get_service_name(),
                    "status_code": response.status_code,
                    "response_size": len(response.content),
                    "endpoint": endpoint,
                },
            )

            return data

        except httpx.HTTPStatusError as e:
            await self._handle_http_error(e)
        except httpx.RequestError as e:
            error = redact_secrets(str(e))
            logger.error(
                "%s API request failed: %s",
                self._get_service_name(),
                error,
                extra={
                    "service": self._get_service_name(),
                    "endpoint": endpoint,
                    "error": error,
                },
                exc_info=True,
            )
            raise ExternalAPIError(
                service=self._get_service_name(),
                message=f"Request failed: {error}",
                status_code=503,
            ) from e
        except Exception as e:
            error = redact_secrets(str(e))
            logger.error(
                "%s unexpected API error: %s",
                self._get_service_name(),
                error,
                extra={
                    "service": self._get_service_name(),
                    "endpoint": endpoint,
                    "error": error,
                },
                exc_info=True,
            )
            raise ExternalAPIError(
                service=self._get_service_name(),
                message=f"Unexpected error: {error}",
                status_code=500,
            ) from e

    async def _handle_http_error(self, error: httpx.HTTPStatusError):
        """Handle HTTP errors and convert to appropriate exceptions."""
        status_code = error.response.status_code

        # Parse error response. Bodies vary by API, so fall back to the status line and URL.
        fallback = f"HTTP {status_code} from {redact_secrets(str(error.request.url))}"
        try:
            error_data = error.response.json()
            detail = error_data.get("error") if isinstance(error_data, dict) else None
            error_message = (
                detail.get("message") if isinstance(detail, dict) else None
            ) or fallback
        except ValueError:
            error_message = error.response.text or fallback
        error_message = redact_secrets(error_message)

        logger.error(
            "%s API HTTP error: %d - %s",
            self._get_service_name(),
            status_code,
            error_message,
            extra={
                "service": self._get_service_name(),
                "status_code": status_code,
                "error_message": error_message,
            },
        )

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
