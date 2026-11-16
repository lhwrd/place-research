"""Record every external API response in the api_calls table, for usage dashboards.

Hooked into the HTTP client that BaseAPIClient builds, so it sees every request any
integration sends, retries included. Requests that never get a response (connection
errors, timeouts) aren't recorded: nothing was served, and nothing is billed.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_STARTED = "usage_started"

# Google bills by product ("SKU"). The names follow its price list; the Places ones are
# the Pro tier because of the fields GooglePlacesAPI.FIELDS asks for.
GEOCODING = "Geocoding"
DISTANCE_MATRIX = "Distance Matrix"
DISTANCE_MATRIX_ADVANCED = "Distance Matrix Advanced"  # with traffic (a departure time)
PLACES_NEARBY = "Places Nearby Search Pro"
PLACES_TEXT = "Places Text Search Pro"
PLACE_DETAILS = "Place Details Pro"


def billing(request: httpx.Request) -> Tuple[Optional[str], int]:
    """
    What a request is charged as.

    Returns:
        (sku, units). sku is None for free APIs and free endpoints (Street View metadata).
        units is 1 except for Distance Matrix, which bills each origin-destination pair.
    """
    host, path = request.url.host, request.url.path
    if host == "maps.googleapis.com":
        if path.endswith("/geocode/json"):
            return GEOCODING, 1
        if path.endswith("/distancematrix/json"):
            params = request.url.params
            pairs = _count(params.get("origins")) * _count(params.get("destinations"))
            sku = DISTANCE_MATRIX_ADVANCED if "departure_time" in params else DISTANCE_MATRIX
            return sku, pairs
    elif host == "places.googleapis.com":
        if path.endswith(":searchNearby"):
            return PLACES_NEARBY, 1
        if path.endswith(":searchText"):
            return PLACES_TEXT, 1
        if "/places/" in path:
            return PLACE_DETAILS, 1
    return None, 1


def _count(piped: Optional[str]) -> int:
    """How many locations are in a "a|b|c" parameter."""
    return len([part for part in (piped or "").split("|") if part]) or 1


def usage_hooks(service: Callable[[], str]) -> Dict[str, List[Callable[..., Any]]]:
    """
    httpx event hooks that record each response.

    Args:
        service: Returns the client's name (called per request)
    """

    async def started(request: httpx.Request) -> None:
        request.extensions[_STARTED] = time.monotonic()

    async def finished(response: httpx.Response) -> None:
        # Usage tracking must never be the reason an API call fails
        try:
            from app.db import get_database  # imported late: the database opens on first use

            request = response.request
            started_at = request.extensions.get(_STARTED)
            sku, units = billing(request)
            get_database().record_api_call(
                service=service(),
                host=request.url.host,
                endpoint=request.url.path,
                method=request.method,
                status=response.status_code,
                duration_ms=(
                    None if started_at is None else round((time.monotonic() - started_at) * 1000)
                ),
                sku=sku,
                units=units,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not record API usage: %s", e)

    return {"request": [started], "response": [finished]}
