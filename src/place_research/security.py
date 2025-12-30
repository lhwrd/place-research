"""Security utilities for password hashing and JWT token management."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from .config import get_settings
from .models.auth import TokenData, UserRole

logger = logging.getLogger(__name__)

# Password hasher using Argon2
pwd_context = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: int,
    username: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: User's database ID
        username: Username
        role: User's role
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    settings = get_settings()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode = {
        "sub": str(user_id),
        "username": username,
        "role": role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(
    user_id: int,
    username: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        user_id: User's database ID
        username: Username
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token
    """
    settings = get_settings()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Verify and decode a JWT token.

    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None otherwise
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )

        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(
                "Invalid token type: expected %s, got %s",
                token_type,
                payload.get("type"),
            )
            return None

        user_id: int = int(payload.get("sub", 0))
        username: str = payload.get("username", "")
        role_str: str = payload.get("role", "")

        if not user_id or not username:
            logger.warning("Invalid token payload: missing user_id or username")
            return None

        # For refresh tokens, role might not be present
        if token_type == "access":
            try:
                role = UserRole(role_str)
            except ValueError:
                logger.warning("Invalid role in token: %s", role_str)
                return None
        else:
            role = UserRole.USER  # Default for refresh tokens

        return TokenData(user_id=user_id, username=username, role=role)

    except JWTError as e:
        logger.warning("JWT verification failed: %s", str(e))
        return None
