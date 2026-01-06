"""Security utilities for password hashing and JWT tokens."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.

    Args:
        subject:  Token subject (usually user ID)
        expires_delta:  Optional expiration time delta

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token.

    Args:
        subject: Token subject (usually user ID)
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT refresh token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)  # Refresh tokens last 7 days

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


def _pre_hash_password(password: str) -> str:
    """
    Pre-hash password with SHA-256 to bypass bcrypt's 72-byte limit.

    This allows passwords of any length while maintaining security.
    The SHA-256 hash is always 64 hex characters (32 bytes), well within
    bcrypt's limit.

    Args:
        password: Plain text password of any length

    Returns:
        Hex-encoded SHA-256 hash of the password
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password:  Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    # Pre-hash the password before verification
    pre_hashed = _pre_hash_password(plain_password)
    return pwd_context.verify(pre_hashed, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password.

    Passwords are pre-hashed with SHA-256 before bcrypt to allow
    unlimited password length while maintaining security.

    Args:
        password: Plain text password of any length

    Returns:
        Hashed password
    """
    # Pre-hash the password before bcrypt to support unlimited length
    pre_hashed = _pre_hash_password(password)
    return pwd_context.hash(pre_hashed)
