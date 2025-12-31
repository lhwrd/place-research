# Authentication Migration Guide

This document describes the new secure authentication system for place-research.

## Overview

The authentication system has been completely redesigned with security best practices:

### What Changed

#### ✅ New Features

- **OAuth2 Password Flow**: Username/password authentication with JWT tokens
- **JWT Tokens**: Secure access and refresh tokens using industry-standard JWT
- **Password Hashing**: Argon2 algorithm for secure password storage
- **Database Storage**: All users and API keys stored in database (SQLite/PostgreSQL)
- **User Management**: Full user registration and management
- **Role-Based Access**: ADMIN, USER, and READONLY roles
- **Dual Authentication**: Support both JWT tokens and API keys

#### ❌ Removed

- **Default API Keys**: No hardcoded keys in source code
- **In-Memory Storage**: No more volatile key storage
- **Insecure Keys**: No plain text keys in code

## Quick Start

### 1. Set Environment Variables

Create a `.env` file:

```bash
# Generate JWT secret key
openssl rand -hex 32

# Add to .env
JWT_SECRET_KEY=your-generated-secret-key-here
DATABASE_URL=sqlite:///./place_research.db  # or postgresql://...
```

### 2. Initialize Database

```bash
# Install dependencies
uv sync

# Initialize database and create admin user
python scripts/init_db.py

# Follow prompts to set admin password
```

### 3. Start the Server

```bash
uv run uvicorn place_research.api.server:app --reload
```

### 4. Authenticate

#### Option A: JWT Token (Recommended)

```bash
# Register a new user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "email": "user@example.com",
    "password": "securepassword123"
  }'

# Login to get tokens
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=myuser&password=securepassword123"

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

# Use the access token
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

#### Option B: API Key

```bash
# First, login with JWT to create an API key
curl -X POST http://localhost:8000/auth/keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "tier": "basic"
  }'

# Response includes the key
{
  "key": "pr_abc123...",
  "name": "My API Key",
  ...
}

# Use the API key
curl http://localhost:8000/auth/me \
  -H "X-API-Key: pr_abc123..."

# Or with Bearer scheme
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer pr_abc123..."
```

## API Reference

### Authentication Endpoints

#### `POST /auth/register`

Register a new user account.

**Request:**

```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string (min 8 chars)"
}
```

**Response:** User object
**Note:** First user becomes ADMIN automatically

---

#### `POST /auth/login`

Login with username and password (OAuth2 password flow).

**Request (form data):**

- `username`: string
- `password`: string

**Response:**

```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "string"
}
```

---

#### `POST /auth/refresh`

Refresh an access token.

**Request:**

```json
{
  "refresh_token": "string"
}
```

**Response:** New access token

---

#### `GET /auth/me`

Get current user information (works with JWT or API key).

---

### API Key Management

#### `POST /auth/keys`

Create a new API key (requires authentication).

**Request:**

```json
{
  "name": "string",
  "tier": "free|basic|premium|unlimited",
  "expires_in_days": 365 // optional
}
```

---

#### `GET /auth/keys`

List API keys.

- Regular users see only their own keys
- Admins see all keys

---

#### `GET /auth/keys/current`

Get information about the current API key (API key auth only).

---

#### `DELETE /auth/keys/{key}`

Revoke an API key.

- Users can revoke their own keys
- Admins can revoke any key

## Configuration

### Environment Variables

```bash
# Required
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>

# Optional - Database
DATABASE_URL=sqlite:///./place_research.db  # or postgresql://user:pass@host/db

# Optional - JWT Settings
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Optional - API Settings
REQUIRE_AUTHENTICATION=true
ALLOW_API_KEY_CREATION=true
```

## Security Best Practices

### Password Requirements

- Minimum 8 characters
- Hashed with Argon2 (industry standard)
- Never stored in plain text

### JWT Tokens

- Short-lived access tokens (30 minutes default)
- Long-lived refresh tokens (7 days default)
- Signed with HS256 algorithm
- Include user ID, username, and role

### API Keys

- Generated with cryptographically secure random bytes
- Prefixed with `pr_` for identification
- Stored in database with usage tracking
- Can be revoked at any time
- Support expiration dates

### Role-Based Access Control

- **ADMIN**: Full access, can manage all users and keys
- **USER**: Standard access, can create own API keys
- **READONLY**: Read-only access, limited write operations

## Migration from Old System

If you were using the old default keys:

1. **Remove hardcoded keys** from your scripts
2. **Initialize the database** with `python scripts/init_db.py`
3. **Create an admin user** during initialization
4. **Login to get JWT token** or **create API keys** for your applications
5. **Update your applications** to use new authentication

### Old Code

```python
# DON'T DO THIS - Old insecure way
headers = {"X-API-Key": "dev-admin-key-12345"}
```

### New Code

```python
# Option 1: JWT Token
headers = {"Authorization": f"Bearer {access_token}"}

# Option 2: API Key
headers = {"X-API-Key": api_key}
# or
headers = {"Authorization": f"Bearer {api_key}"}
```

## Troubleshooting

### "JWT_SECRET_KEY is required"

Generate a secret key:

```bash
openssl rand -hex 32
```

Add to `.env` file.

### "Database connection error"

Check `DATABASE_URL` in your environment. Default is SQLite.

### "User already exists"

Use a different username or login with existing credentials.

### "Invalid token"

Token may be expired. Use refresh token to get a new access token.

## Database Schema

### Users Table

- `id`: Primary key
- `username`: Unique username
- `email`: Unique email
- `hashed_password`: Argon2 hashed password
- `role`: ADMIN, USER, or READONLY
- `is_active`: Account status
- `is_verified`: Email verification status
- `created_at`, `updated_at`, `last_login_at`: Timestamps

### API Keys Table

- `id`: Primary key
- `key`: Unique API key
- `name`: Descriptive name
- `user_id`: Foreign key to users
- `tier`: Rate limit tier
- `enabled`: Key status
- `expires_at`: Optional expiration
- `created_at`, `last_used_at`: Timestamps
- `request_count`: Usage tracking

## Support

For issues or questions:

1. Check this documentation
2. Review error messages carefully
3. Check server logs for detailed errors
4. Ensure environment variables are set correctly
