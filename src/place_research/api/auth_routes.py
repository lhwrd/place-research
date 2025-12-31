"""Authentication routes for JWT-based authentication."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..auth import CurrentUser
from ..config import Settings, get_settings
from ..database import get_db
from ..db_models import User
from ..models.auth import Token, UserCreate, UserResponse, UserRole
from ..security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user account.

    Creates a new user with hashed password. Admin users can only be created
    via this endpoint if the first user doesn't exist yet (bootstrap).
    """
    # Check if username already exists
    existing_username = db.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Username already exists",
                "details": {"username": user_data.username},
            },
        )

    # Check if email already exists
    existing_email = db.exec(select(User).where(User.email == user_data.email)).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Email already exists",
                "details": {"email": user_data.email},
            },
        )

    # Check if this is the first user (bootstrap admin)
    user_count = len(db.exec(select(User)).all())
    if user_count == 0:
        # First user becomes admin
        role = UserRole.ADMIN
    else:
        # Otherwise use requested role (default USER)
        role = user_data.role
        # Non-admins can't create admin users via this endpoint
        if role == UserRole.ADMIN:
            role = UserRole.USER

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=role,
        is_active=True,
        is_verified=False,  # Email verification not implemented yet
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse.from_orm(new_user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Token:
    """Login with username and password to receive JWT tokens.

    This endpoint follows the OAuth2 password flow standard.
    Returns an access token and refresh token.
    """
    # Find user by username
    user = db.exec(select(User).where(User.username == form_data.username)).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "Incorrect username or password",
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "AUTHORIZATION_ERROR",
                "message": "User account is disabled",
                "details": {},
            },
        )

    # Create access and refresh tokens
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "User ID is None"},
        )

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    refresh_token = create_refresh_token(
        user_id=user.id,
        username=user.username,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    refresh_token: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Token:
    """Refresh an access token using a refresh token.

    Provide a valid refresh token to receive a new access token.
    """
    token_data = verify_token(refresh_token, token_type="refresh")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTHENTICATION_ERROR",
                "message": "Invalid or expired refresh token",
                "details": {},
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
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

    # Create new access token
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": "User ID is None"},
        )

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: CurrentUser,
) -> UserResponse:
    """Get information about the currently authenticated user.

    Requires JWT token authentication.
    """
    return UserResponse.from_orm(user)
