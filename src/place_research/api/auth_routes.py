"""Authentication and API key management routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import APIKeyManager, AuthUser, get_api_key_manager, require_role
from ..config import Settings, get_settings
from ..models.auth import APIKeyResponse, CreateAPIKeyRequest, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_api_key(
    request: CreateAPIKeyRequest,
    _user: AuthUser,
    manager: APIKeyManager = Depends(get_api_key_manager),
    settings: Settings = Depends(get_settings),
) -> APIKeyResponse:
    """Create a new API key (Admin only).

    Requires ADMIN role to create new API keys.
    """
    if not settings.allow_api_key_creation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "AUTHORIZATION_ERROR",
                "message": "API key creation is disabled",
                "details": {},
            },
        )

    api_key = manager.create_key(request)

    return APIKeyResponse(
        key=api_key.key,
        name=api_key.name,
        role=api_key.role,
        tier=api_key.tier,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        enabled=api_key.enabled,
        request_count=api_key.request_count,
        rate_limit_per_hour=api_key.get_rate_limit(),
    )


@router.get(
    "/keys",
    response_model=list[APIKeyResponse],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def list_api_keys(
    _user: AuthUser,
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> list[APIKeyResponse]:
    """List all API keys (Admin only).

    Requires ADMIN role to view all API keys.
    """
    keys = manager.list_keys()

    return [
        APIKeyResponse(
            key=k.key,
            name=k.name,
            role=k.role,
            tier=k.tier,
            created_at=k.created_at,
            expires_at=k.expires_at,
            enabled=k.enabled,
            request_count=k.request_count,
            rate_limit_per_hour=k.get_rate_limit(),
        )
        for k in keys
    ]


@router.get("/me", response_model=APIKeyResponse)
async def get_current_key(
    user: AuthUser,
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> APIKeyResponse:
    """Get information about the current API key.

    Returns details about the API key used to authenticate this request.
    """
    api_key = manager.get_key(user.api_key)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": "API key not found",
                "details": {},
            },
        )

    return APIKeyResponse(
        key=api_key.key,
        name=api_key.name,
        role=api_key.role,
        tier=api_key.tier,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        enabled=api_key.enabled,
        request_count=api_key.request_count,
        rate_limit_per_hour=api_key.get_rate_limit(),
    )


@router.delete(
    "/keys/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def revoke_api_key(
    key: str,
    _user: AuthUser,
    manager: APIKeyManager = Depends(get_api_key_manager),
):
    """Revoke (disable) an API key (Admin only).

    Requires ADMIN role to revoke API keys.
    """
    if not manager.revoke_key(key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": "API key not found",
                "details": {"key": key},
            },
        )

    return None
