"""Authentication and authorization for place-research API.

This module provides API key authentication, role-based authorization,
and rate limiting functionality.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .exceptions import PlaceResearchError
from .models.auth import (
    APIKey,
    AuthenticatedUser,
    CreateAPIKeyRequest,
    RateLimitTier,
    UserRole,
)

logger = logging.getLogger(__name__)


class AuthenticationError(PlaceResearchError):
    """Raised when authentication fails."""

    def __init__(self, message: str):
        super().__init__(message, "AUTHENTICATION_ERROR", {})


class AuthorizationError(PlaceResearchError):
    """Raised when authorization fails."""

    def __init__(self, message: str, required_role: Optional[str] = None):
        details = {}
        if required_role:
            details["required_role"] = required_role
        super().__init__(message, "AUTHORIZATION_ERROR", details)


# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class APIKeyManager:
    """Manages API keys for authentication.

    In production, this should be backed by a database.
    For now, we use in-memory storage with some default keys.
    """

    def __init__(self):
        self.keys: dict[str, APIKey] = {}
        self._initialize_default_keys()

    def _initialize_default_keys(self):
        """Initialize some default API keys for testing."""
        # Admin key
        self.keys["dev-admin-key-12345"] = APIKey(
            key="dev-admin-key-12345",
            name="Development Admin Key",
            role=UserRole.ADMIN,
            tier=RateLimitTier.UNLIMITED,
            enabled=True,
        )

        # Regular user key
        self.keys["dev-user-key-67890"] = APIKey(
            key="dev-user-key-67890",
            name="Development User Key",
            role=UserRole.USER,
            tier=RateLimitTier.BASIC,
            enabled=True,
        )

        # Read-only key
        self.keys["dev-readonly-key-11111"] = APIKey(
            key="dev-readonly-key-11111",
            name="Development Readonly Key",
            role=UserRole.READONLY,
            tier=RateLimitTier.FREE,
            enabled=True,
        )

        logger.info("Initialized %s default API keys", len(self.keys))

    def generate_key(self) -> str:
        """Generate a new API key."""
        # Generate a secure random key
        random_bytes = secrets.token_bytes(32)
        key = hashlib.sha256(random_bytes).hexdigest()
        return f"pr_{key[:32]}"  # pr_ prefix for "place-research"

    def create_key(self, request: CreateAPIKeyRequest) -> APIKey:
        """Create a new API key."""
        key_string = self.generate_key()

        # Calculate expiration
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now() + timedelta(days=request.expires_in_days)

        api_key = APIKey(
            key=key_string,
            name=request.name,
            role=request.role,
            tier=request.tier,
            expires_at=expires_at,
            allowed_ips=request.allowed_ips,
            enabled=True,
        )

        self.keys[key_string] = api_key
        logger.info("Created new API key: %s (%s)", request.name, request.role)
        return api_key

    def get_key(self, key: str) -> Optional[APIKey]:
        """Retrieve an API key."""
        return self.keys.get(key)

    def validate_key(self, key: str, client_ip: Optional[str] = None) -> APIKey:
        """Validate an API key and return it if valid.

        Args:
            key: The API key to validate
            client_ip: The client's IP address for IP restriction checking

        Returns:
            The validated APIKey object

        Raises:
            AuthenticationError: If the key is invalid, expired, or from wrong IP
        """
        api_key = self.get_key(key)

        if not api_key:
            raise AuthenticationError("Invalid API key")

        if not api_key.enabled:
            raise AuthenticationError("API key is disabled")

        if api_key.is_expired():
            raise AuthenticationError("API key has expired")

        # Check IP restrictions
        if api_key.allowed_ips and client_ip:
            if client_ip not in api_key.allowed_ips:
                raise AuthenticationError(f"API key not allowed from IP: {client_ip}")

        # Update usage tracking
        api_key.last_used_at = datetime.now()
        api_key.request_count += 1

        return api_key

    def list_keys(self) -> list[APIKey]:
        """List all API keys."""
        return list(self.keys.values())

    def revoke_key(self, key: str) -> bool:
        """Revoke (disable) an API key."""
        api_key = self.get_key(key)
        if api_key:
            api_key.enabled = False
            logger.info("Revoked API key: %s", api_key.name)
            return True
        return False

    def delete_key(self, key: str) -> bool:
        """Delete an API key completely."""
        if key in self.keys:
            api_key = self.keys[key]
            del self.keys[key]
            logger.info("Deleted API key: %s", api_key.name)
            return True
        return False


# Global instance (in production, this would be injected from app state)
_api_key_manager = APIKeyManager()


def get_api_key_manager() -> APIKeyManager:
    """Get the API key manager instance.

    This is a dependency that can be injected into endpoints.
    """
    return _api_key_manager


async def get_api_key(
    api_key_value: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[str]:
    """Extract API key from request headers.

    Supports two formats:
    1. X-API-Key header
    2. Authorization: Bearer <key> header
    """
    if api_key_value:
        return api_key_value

    if bearer:
        return bearer.credentials

    return None


async def authenticate(
    api_key: Optional[str] = Depends(get_api_key),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> AuthenticatedUser:
    """Authenticate the request using API key.

    This dependency can be used on endpoints to require authentication.

    Returns:
        AuthenticatedUser with role and permissions

    Raises:
        HTTPException: If authentication fails (401)
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "API key required. Provide via X-API-Key header or Authorization: Bearer token",  # pylint: disable=line-too-long
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        validated_key = manager.validate_key(api_key)

        return AuthenticatedUser(
            api_key=api_key,
            role=validated_key.role,
            tier=validated_key.tier,
            name=validated_key.name,
        )
    except AuthenticationError as e:
        logger.warning("Authentication failed: %s", e.message)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def authenticate_optional(
    api_key: Optional[str] = Depends(get_api_key),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> Optional[AuthenticatedUser]:
    """Optional authentication - returns None if no API key provided.

    This allows endpoints to work with or without authentication,
    potentially with different behavior based on auth status.
    """
    if not api_key:
        return None

    try:
        validated_key = manager.validate_key(api_key)
        return AuthenticatedUser(
            api_key=api_key,
            role=validated_key.role,
            tier=validated_key.tier,
            name=validated_key.name,
        )
    except AuthenticationError:
        return None


def require_role(required_role: UserRole):
    """Dependency factory for role-based authorization.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """

    async def check_role(user: AuthenticatedUser = Depends(authenticate)):
        if not user.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AUTHORIZATION_ERROR",
                    "message": f"Requires {required_role.value} role or higher",
                    "details": {
                        "required_role": required_role.value,
                        "user_role": user.role.value,
                    },
                },
            )
        return user

    return check_role


def require_write_access():
    """Dependency for endpoints that require write access.

    Usage:
        @router.post("/create", dependencies=[Depends(require_write_access())])
        async def create_something(): ...
    """

    async def check_write(user: AuthenticatedUser = Depends(authenticate)):
        if not user.can_write():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AUTHORIZATION_ERROR",
                    "message": "Write access required (USER or ADMIN role)",
                    "details": {"user_role": user.role.value},
                },
            )
        return user

    return check_write


# Type alias for authenticated user dependency
AuthUser = Annotated[AuthenticatedUser, Depends(authenticate)]
OptionalAuthUser = Annotated[
    Optional[AuthenticatedUser], Depends(authenticate_optional)
]
