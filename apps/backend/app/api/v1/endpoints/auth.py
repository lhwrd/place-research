"""Authentication endpoints."""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.db.database import get_db
from app.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    Token,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.schemas.user import UserData
from app.services.email_service import EmailService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password",
)
async def register(user_data: UserCreate, db: Session = Depends(get_db)) -> Any:
    """
    Register a new user.

    - **email**: Valid email address (will be used for login)
    - **password**: Password (min 8 characters, will be hashed)
    - **full_name**: Optional full name
    """
    user_service = UserService(db)

    # Check if user already exists
    existing_user = user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise EmailAlreadyExistsError(email=user_data.email)

    # Create user
    user = user_service.create_user(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
    )

    logger.info(f"New user registered: {user.email}")

    # Generate tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return UserResponse(
        user=UserData.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with email and password to receive access token",
)
async def login(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login.

    Use your email as username and password to get an access token.
    The token should be used in subsequent requests in the Authorization header:
    `Authorization: Bearer {token}`
    """
    user_service = UserService(db)

    # Authenticate user (username field contains email)
    user = user_service.authenticate_user(email=form_data.username, password=form_data.password)

    if not user:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account")

    # Update last login
    user_service.update_last_login(user.id)

    logger.info(f"User logged in: {user.email}")

    # Create tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserData.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Get a new access token using a refresh token",
)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)) -> Any:
    """
    Refresh access token.

    Provide a valid refresh token to get a new access token.
    """

    try:
        payload = jwt.decode(
            refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise InvalidTokenError()

    except JWTError as e:
        raise InvalidTokenError() from e

    # Verify user still exists and is active
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user or not user.is_active:
        raise InvalidTokenError()

    # Create new access token
    new_access_token = create_access_token(subject=str(user.id))

    return Token(access_token=new_access_token, token_type="bearer")


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Logout the current user (client should discard tokens)",
)
async def logout(current_user: User = Depends(deps.get_current_user)) -> Any:
    """
    Logout current user.

    Note: Since we're using JWT tokens, actual logout happens client-side
    by discarding the tokens. This endpoint is mainly for logging purposes.

    TODO: For production, you might want to implement token blacklisting.
    """
    logger.info(f"User logged out: {current_user.email}")

    return {
        "message": "Successfully logged out",
        "detail": "Please discard your access and refresh tokens",
    }


@router.get(
    "/me",
    response_model=UserData,
    summary="Get current user",
    description="Get the currently authenticated user's information",
)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user information.

    Returns the profile information of the currently authenticated user.
    """
    return UserData.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserData,
    summary="Update current user",
    description="Update the currently authenticated user's information",
)
async def update_current_user(
    user_update: dict,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update current user information.

    Allowed fields:
    - full_name
    - email (must be unique)
    """
    user_service = UserService(db)

    # Only allow specific fields to be updated
    allowed_fields = {"full_name", "email"}
    updates = {k: v for k, v in user_update.items() if k in allowed_fields}

    # Check if email is being changed and if it's already taken
    if "email" in updates and updates["email"] != current_user.email:
        existing = user_service.get_user_by_email(updates["email"])
        if existing:
            raise EmailAlreadyExistsError(email=updates["email"])

    updated_user = user_service.update_user(current_user.id, updates)

    return UserData.model_validate(updated_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change the current user's password",
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Change current user's password.

    Requires:
    - current_password: Current password for verification
    - new_password: New password (min 8 characters)
    """
    user_service = UserService(db)

    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    # Update password
    user_service.update_password(current_user.id, password_data.new_password)

    logger.info(f"Password changed for user: {current_user.email}")

    return {"message": "Password changed successfully"}


@router.post(
    "/request-password-reset",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Request a password reset email",
)
async def request_password_reset(
    request_data: PasswordResetRequest, db: Session = Depends(get_db)
) -> Any:
    """
    Request password reset.

    Sends a password reset email to the user's email address.
    For security, always returns success even if email doesn't exist.
    """
    user_service = UserService(db)
    email_service = EmailService()

    # Find user
    user = user_service.get_user_by_email(request_data.email)

    if user:
        # Generate reset token (valid for 1 hour)
        reset_token = create_access_token(subject=str(user.id), expires_delta=timedelta(hours=1))

        logger.info(f"Password reset requested for {user.email}")

        await email_service.send_password_reset_email(email=user.email, reset_token=reset_token)

    # Always return success for security (don't reveal if email exists)
    return {"message": "If that email exists, a password reset link has been sent"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset password using a reset token",
)
async def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)) -> Any:
    """
    Reset password using token from email.

    Requires:
    - token: Password reset token from email
    - new_password:  New password (min 8 characters)
    """
    try:
        payload = jwt.decode(
            reset_data.token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")

        if user_id is None:
            raise InvalidTokenError()

    except JWTError as e:
        raise InvalidTokenError() from e

    # Update password
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user:
        raise InvalidTokenError()

    user_service.update_password(user.id, reset_data.new_password)

    logger.info(f"Password reset for user:  {user.email}")

    return {"message": "Password reset successfully"}


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account",
    description="Delete the current user's account (soft delete)",
)
async def delete_account(
    current_user: User = Depends(deps.get_current_user), db: Session = Depends(get_db)
) -> None:
    """
    Delete current user's account.

    This performs a soft delete by marking the account as inactive.
    All user data is retained but the account cannot be used.
    """
    user_service = UserService(db)
    user_service.deactivate_user(current_user.id)

    logger.info(f"User account deleted: {current_user. email}")

    return None
