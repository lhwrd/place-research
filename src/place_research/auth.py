"""Authentication and authorization for place-research API.

This module provides OAuth2 password flow with JWT token authentication
and role-based authorization.
"""

import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from .database import get_db
from .db_models import User
from .exceptions import PlaceResearchError
from .models.auth import AuthenticatedUser, UserRole
from .security import verify_token

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


# Security scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User object if token is valid

    Raises:
        HTTPException: If authentication fails (401)
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "Authentication required",
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(token, token_type="access")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "Invalid or expired token",
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.exec(select(User).where(User.id == token_data.user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "User not found or inactive",
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login time
    user.last_login_at = datetime.utcnow()
    db.commit()

    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get the current user, or None if not authenticated.

    This allows endpoints to work with or without authentication.
    """
    if not token:
        return None

    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


async def authenticate(user: User = Depends(get_current_user)) -> AuthenticatedUser:
    """Authenticate the request using JWT token.

    This dependency can be used on endpoints to require authentication.

    Returns:
        AuthenticatedUser with role and permissions
    """
    return AuthenticatedUser(
        api_key="",  # Not using API keys
        role=user.role,
        tier="unlimited",  # All authenticated users get full access
        name=user.username,
    )


async def authenticate_optional(
    user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[AuthenticatedUser]:
    """Optional authentication - returns None if no token provided.

    This allows endpoints to work with or without authentication,
    potentially with different behavior based on auth status.
    """
    if not user:
        return None

    return AuthenticatedUser(
        api_key="",
        role=user.role,
        tier="unlimited",
        name=user.username,
    )


def require_role(required_role: UserRole):
    """Dependency factory for role-based authorization.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """

    async def check_role(user: User = Depends(get_current_user)):
        # Role hierarchy: ADMIN > USER > READONLY
        role_hierarchy = {
            UserRole.READONLY: 0,
            UserRole.USER: 1,
            UserRole.ADMIN: 2,
        }

        if role_hierarchy[user.role] < role_hierarchy[required_role]:
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

    async def check_write(user: User = Depends(get_current_user)):
        if user.role == UserRole.READONLY:
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
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]
