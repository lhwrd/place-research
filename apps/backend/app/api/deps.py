"""Request authentication dependencies.

The API has two callers: the iOS Shortcut (static bearer token) and Baserow's
webhook (shared secret header).
"""

import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

ingest_bearer = HTTPBearer(auto_error=False)


async def verify_ingest_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(ingest_bearer),
) -> None:
    """
    Check the static bearer token used by the iOS Shortcut.

    Raises:
        HTTPException: 503 if ingest isn't configured, 401 if the token is missing or wrong.
    """
    if not settings.ingest_api_token or not settings.baserow_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Listing ingest is not configured",
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, settings.ingest_api_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingest token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_baserow_webhook(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
) -> None:
    """
    Check the shared secret header configured on the Baserow webhook.

    Raises:
        HTTPException: 503 if webhooks aren't configured, 401 if the secret is wrong.
    """
    if not settings.baserow_webhook_secret or not settings.baserow_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Baserow webhooks are not configured",
        )
    if x_webhook_secret is None or not secrets.compare_digest(
        x_webhook_secret, settings.baserow_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret"
        )
