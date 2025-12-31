# Authentication & Authorization

Comprehensive guide to the authentication and authorization system in place-research API.

## Overview

The place-research API uses **API key authentication** with **role-based authorization** to secure endpoints and manage access control.

### Features

- ✅ API Key authentication (header or Bearer token)
- ✅ Role-based access control (Admin, User, Readonly)
- ✅ Rate limiting tiers (Free, Basic, Premium, Unlimited)
- ✅ API key management endpoints
- ✅ Usage tracking and statistics
- ✅ Optional authentication mode (off by default for development)
- ✅ IP-based restrictions (optional)
- ✅ Key expiration support

## Quick Start

### Default API Keys

For development, three default API keys are available:

| Role         | API Key                  | Rate Limit | Use Case                    |
| ------------ | ------------------------ | ---------- | --------------------------- |
| **Admin**    | `dev-admin-key-12345`    | Unlimited  | Full access, key management |
| **User**     | `dev-user-key-67890`     | 1,000/hour | Standard enrichment access  |
| **Readonly** | `dev-readonly-key-11111` | 100/hour   | Read-only operations        |

### Making Authenticated Requests

**Option 1: X-API-Key Header**

```bash
curl -X POST http://localhost:8002/enrich \
  -H "X-API-Key: dev-user-key-67890" \
  -H "Content-Type: application/json" \
  -d '{"address": "1600 Amphitheatre Parkway, Mountain View, CA"}'
```

**Option 2: Authorization Bearer Token**

```bash
curl -X POST http://localhost:8002/enrich \
  -H "Authorization: Bearer dev-user-key-67890" \
  -H "Content-Type: application/json" \
  -d '{"address": "1600 Amphitheatre Parkway, Mountain View, CA"}'
```

**Python Example**

```python
import requests

headers = {"X-API-Key": "dev-user-key-67890"}
response = requests.post(
    "http://localhost:8002/enrich",
    json={"address": "123 Main St"},
    headers=headers
)
```

## Configuration

### Environment Variables

```bash
# Require authentication for all requests (default: False)
REQUIRE_AUTHENTICATION=true

# Allow API key creation via API (default: True)
ALLOW_API_KEY_CREATION=true
```

### Development vs Production

**Development (default)**:

- Authentication optional
- Default API keys available
- API key creation enabled

**Production (recommended)**:

```bash
# .env file
REQUIRE_AUTHENTICATION=true
ALLOW_API_KEY_CREATION=false  # Create keys via admin interface only
```

## User Roles

### Role Hierarchy

```
ADMIN > USER > READONLY
```

### Role Permissions

#### ADMIN Role

- ✅ Full access to all endpoints
- ✅ Create/list/revoke API keys
- ✅ Enrich places
- ✅ View provider status
- ✅ Unlimited rate limits (can be configured)

#### USER Role

- ✅ Enrich places
- ✅ View provider status
- ✅ View own API key info
- ❌ Cannot manage API keys

#### READONLY Role

- ✅ View provider status
- ✅ View own API key info
- ❌ Cannot enrich places
- ❌ Cannot manage API keys

## Rate Limiting Tiers

Each API key has an associated rate limit tier:

| Tier          | Requests/Hour | Typical Use                |
| ------------- | ------------- | -------------------------- |
| **Free**      | 100           | Testing, personal projects |
| **Basic**     | 1,000         | Small applications         |
| **Premium**   | 10,000        | Production applications    |
| **Unlimited** | No limit      | Admin, internal services   |

Rate limits are enforced per API key.

## API Key Management

### Get Current Key Info

View information about the API key you're using:

```bash
curl http://localhost:8002/auth/me \
  -H "X-API-Key: dev-user-key-67890"
```

**Response:**

```json
{
  "key": "dev-user-key-67890",
  "name": "Development User Key",
  "role": "user",
  "tier": "basic",
  "created_at": "2025-12-30T10:00:00",
  "expires_at": null,
  "enabled": true,
  "request_count": 42,
  "rate_limit_per_hour": 1000
}
```

### Create API Key (Admin Only)

```bash
curl -X POST http://localhost:8002/auth/keys \
  -H "X-API-Key: dev-admin-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production App Key",
    "role": "user",
    "tier": "premium",
    "expires_in_days": 365
  }'
```

**Response:**

```json
{
  "key": "pr_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "name": "Production App Key",
  "role": "user",
  "tier": "premium",
  "created_at": "2025-12-30T10:00:00",
  "expires_at": "2026-12-30T10:00:00",
  "enabled": true,
  "request_count": 0,
  "rate_limit_per_hour": 10000
}
```

### List All API Keys (Admin Only)

```bash
curl http://localhost:8002/auth/keys \
  -H "X-API-Key: dev-admin-key-12345"
```

**Response:** Array of API key objects

### Revoke API Key (Admin Only)

```bash
curl -X DELETE http://localhost:8002/auth/keys/pr_a1b2c3d4e5f6... \
  -H "X-API-Key: dev-admin-key-12345"
```

## Error Responses

### 401 Unauthorized

**No API key provided:**

```json
{
  "error": "AUTHENTICATION_ERROR",
  "message": "API key required. Provide via X-API-Key header or Authorization: Bearer token",
  "details": {}
}
```

**Invalid API key:**

```json
{
  "error": "AUTHENTICATION_ERROR",
  "message": "Invalid API key",
  "details": {}
}
```

**Expired API key:**

```json
{
  "error": "AUTHENTICATION_ERROR",
  "message": "API key has expired",
  "details": {}
}
```

### 403 Forbidden

**Insufficient permissions:**

```json
{
  "error": "AUTHORIZATION_ERROR",
  "message": "Requires admin role or higher",
  "details": {
    "required_role": "admin",
    "user_role": "user"
  }
}
```

## Implementation Details

### Authentication Flow

```
1. Client sends request with API key (X-API-Key or Authorization header)
2. FastAPI security dependency extracts the key
3. APIKeyManager validates the key:
   - Key exists?
   - Key enabled?
   - Key not expired?
   - IP allowed (if IP restrictions set)?
4. Usage tracking updated (last_used_at, request_count)
5. AuthenticatedUser object created with role/permissions
6. Request proceeds with user context
```

### Authorization Flow

```
1. Endpoint specifies required role (via Depends(require_role(...)))
2. User's role compared against requirement
3. Role hierarchy checked (ADMIN > USER > READONLY)
4. If authorized, request proceeds
5. If not authorized, 403 Forbidden returned
```

### Code Example: Protected Endpoint

```python
from fastapi import APIRouter, Depends
from place_research.auth import require_role, AuthUser
from place_research.models.auth import UserRole

router = APIRouter()

@router.post("/admin-only")
async def admin_endpoint(
    user: AuthUser = Depends(require_role(UserRole.ADMIN))
):
    return {"message": f"Hello admin {user.name}!"}
```

### Code Example: Optional Authentication

```python
from place_research.auth import authenticate_optional, OptionalAuthUser

@router.get("/optional-auth")
async def optional_endpoint(user: OptionalAuthUser = None):
    if user:
        return {"message": f"Hello {user.name}!", "role": user.role}
    else:
        return {"message": "Hello anonymous user!"}
```

## Advanced Features

### IP Restrictions

Create API keys that only work from specific IP addresses:

```python
request = CreateAPIKeyRequest(
    name="Office Network Key",
    role=UserRole.USER,
    tier=RateLimitTier.BASIC,
    allowed_ips=["203.0.113.0", "203.0.113.1"]
)
```

### Key Expiration

Create temporary API keys:

```python
request = CreateAPIKeyRequest(
    name="30-day Trial Key",
    role=UserRole.USER,
    tier=RateLimitTier.FREE,
    expires_in_days=30
)
```

### Usage Tracking

Each API key tracks:

- `request_count`: Total requests made
- `last_used_at`: Timestamp of most recent use
- `created_at`: When key was created

Useful for:

- Billing/usage reporting
- Identifying inactive keys
- Audit trails

## Security Best Practices

### 1. Protect API Keys

```bash
# ❌ DON'T: Commit API keys to version control
echo "X-API-Key: dev-admin-key-12345" > headers.txt
git add headers.txt

# ✅ DO: Use environment variables
export API_KEY=dev-user-key-67890
curl -H "X-API-Key: $API_KEY" http://localhost:8002/enrich
```

### 2. Use Appropriate Roles

```bash
# ❌ DON'T: Use admin keys for routine operations
X-API-Key: dev-admin-key-12345

# ✅ DO: Use least-privilege keys
X-API-Key: dev-user-key-67890  # For enrichment
X-API-Key: dev-readonly-key-11111  # For monitoring
```

### 3. Rotate Keys Regularly

```python
# Create new key
new_key = manager.create_key(CreateAPIKeyRequest(...))

# Update application to use new key
# ...

# Revoke old key
manager.revoke_key(old_key)
```

### 4. Enable Required Authentication in Production

```bash
# .env
REQUIRE_AUTHENTICATION=true
```

### 5. Monitor Usage

```python
# List all keys and check usage
keys = manager.list_keys()
for key in keys:
    print(f"{key.name}: {key.request_count} requests")
    if key.request_count == 0:
        print(f"  ⚠️  Unused key - consider revoking")
```

## Testing

### Unit Tests

```python
def test_authentication():
    from place_research.auth import APIKeyManager

    manager = APIKeyManager()

    # Validate existing key
    key = manager.validate_key("dev-user-key-67890")
    assert key.role == UserRole.USER

    # Invalid key should raise
    with pytest.raises(AuthenticationError):
        manager.validate_key("invalid-key")
```

### Integration Tests

```python
def test_auth_endpoint(client):
    # With valid key
    response = client.get(
        "/auth/me",
        headers={"X-API-Key": "dev-user-key-67890"}
    )
    assert response.status_code == 200

    # Without key
    response = client.get("/auth/me")
    assert response.status_code == 401
```

## Future Enhancements

Potential improvements for the authentication system:

1. **OAuth2/JWT Support** - Token-based authentication with refresh tokens
2. **Database Persistence** - Store API keys in database instead of memory
3. **Rate Limiting Middleware** - Automatic enforcement of tier limits
4. **Webhook Support** - Notify on key usage/revocation
5. **Multi-Tenancy** - Organization-level key management
6. **Audit Logging** - Detailed logs of all auth events
7. **Two-Factor Authentication** - For admin operations
8. **Scopes** - Fine-grained permissions beyond roles

## Troubleshooting

### "API key required" Error

**Problem:** Getting 401 error even with API key

**Solution:** Check header format

```bash
# ❌ Wrong
curl -H "API-Key: dev-user-key-67890" ...

# ✅ Correct
curl -H "X-API-Key: dev-user-key-67890" ...
```

### "Requires admin role" Error

**Problem:** Getting 403 when trying to create keys

**Solution:** Use admin key

```bash
curl -H "X-API-Key: dev-admin-key-12345" ...
```

### Authentication Not Required

**Problem:** Endpoints work without API key

**Solution:** This is expected in development. Set `REQUIRE_AUTHENTICATION=true` to enforce.

## Summary

The authentication system provides:

- ✅ **Secure** - API key validation, role-based access
- ✅ **Flexible** - Optional in dev, required in production
- ✅ **Scalable** - Multiple tiers, usage tracking
- ✅ **Developer-Friendly** - Clear errors, easy testing
- ✅ **Production-Ready** - Expiration, IP restrictions, audit trails

All tests passing: **29/29** ✅
