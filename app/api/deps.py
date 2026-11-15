"""Request authentication for the iOS Shortcut's static bearer token."""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
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
    if not settings.ingest_api_token:
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
