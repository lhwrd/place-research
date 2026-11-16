"""Walk, bike and transit scores, fetched from Walk Score each time a property page is shown.

Walk Score's terms don't allow storing or caching its scores, so unlike the enrichment
providers nothing here is saved: no database column, no in-process cache. They also require
each displayed score to link to Walk Score's page for the address (the "link" returned here).
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from app.core.redaction import redact_secrets
from app.integrations.walk_score_api import WalkScoreAPI

logger = logging.getLogger(__name__)

# The page waits for this, so give up quickly and show it without scores instead
TIMEOUT_SECONDS = 4.0

# The API answers HTTP 200 with a status: 1 is a score; others are "still being
# calculated", bad key, quota exceeded, ...
STATUS_OK = 1

_client: Optional[WalkScoreAPI] = None


def _api() -> WalkScoreAPI:
    global _client  # pylint: disable=global-statement
    if _client is None:
        _client = WalkScoreAPI()
    return _client


async def live_walk_scores(
    latitude: float, longitude: float, address: str, timeout: float = TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    Current scores for an address.

    Returns:
        {"walk_score", "bike_score", "transit_score", "description", "bike_description",
        "transit_description", "link"}, or {} if there's no WALKSCORE_API_KEY, no score, or
        Walk Score didn't answer in time. Never raises: the page renders either way.
    """
    api = _api()
    if not api.api_key:
        return {}
    try:
        result = await asyncio.wait_for(
            api.get_score(lat=latitude, lon=longitude, address=address), timeout
        )
    except asyncio.TimeoutError:
        logger.warning("Walk Score did not answer within %.0fs", timeout)
        return {}
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("Walk Score lookup failed: %s", redact_secrets(str(e)))
        return {}

    if not isinstance(result, dict) or result.get("status") != STATUS_OK:
        logger.info("No Walk Score (status %s)", (result or {}).get("status"))
        return {}

    # Bike and transit can come back as null where they aren't scored
    bike = result.get("bike") or {}
    transit = result.get("transit") or {}
    return {
        "walk_score": result.get("walkscore"),
        "bike_score": bike.get("score"),
        "transit_score": transit.get("score"),
        "description": result.get("description"),  # the walk description
        "bike_description": bike.get("description"),
        "transit_description": transit.get("description"),
        "link": result.get("ws_link"),
    }
