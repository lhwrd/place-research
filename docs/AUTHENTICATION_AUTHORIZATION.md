# Authentication & Authorization Implementation

## Overview

This document describes the complete authentication and authorization implementation for the Place Research application. The system ensures that only authenticated users can access the application, with proper redirect handling and token management.

## Security Features

### 1. Protected Routes (Frontend)

All application routes except authentication pages are protected using the `ProtectedRoute` component:

- **Login Page** (`/login`) - Public
- **Register Page** (`/register`) - Public
- **Forgot Password** (`/forgot-password`) - Public
- **Reset Password** (`/reset-password`) - Public
- **All Other Routes** - Protected (requires authentication)

### 2. Authentication Flow

#### Login Flow

1. User navigates to a protected route (e.g., `/search`)
2. `ProtectedRoute` checks authentication status
3. If not authenticated, user is redirected to `/login` with the original location saved
4. User enters credentials and submits login form
5. On successful login:
   - JWT access token and refresh token are stored
   - User data is saved to Zustand store and persisted to localStorage
   - User is redirected back to the originally requested page (or home if direct login)

#### Logout Flow

1. User clicks logout
2. Logout API call is made to backend
3. Tokens are cleared from localStorage
4. Zustand store is cleared
5. React Query cache is invalidated
6. User is redirected to `/login`

#### Session Persistence

- Authentication state is persisted using Zustand's `persist` middleware
- Tokens are stored in localStorage
- On app reload, auth state is automatically rehydrated
- If tokens exist in localStorage but not in Zustand state, they are synchronized
- If state claims authenticated but no tokens exist, state is cleared

### 3. Token Management

#### Access Tokens

- Short-lived JWT tokens (typically 15-30 minutes)
- Included in `Authorization: Bearer <token>` header for all API requests
- Handled automatically by axios interceptor

#### Refresh Tokens

- Long-lived tokens (typically 7-30 days)
- Used to obtain new access tokens when they expire
- Automatically exchanged for new access token on 401 responses

#### Token Refresh Flow

1. API request returns 401 Unauthorized
2. Axios response interceptor catches the error
3. Refresh token is sent to `/auth/refresh` endpoint
4. New access token is received and stored
5. Original request is retried with new access token
6. If refresh fails, user is logged out and redirected to login

### 4. Backend Authorization

All protected endpoints use FastAPI's dependency injection for authentication:

```python
@router.post("/endpoint")
async def protected_endpoint(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db)
):
    # Only authenticated users can access this
    ...
```

The `get_current_user` dependency:

- Validates the JWT token from the Authorization header
- Decodes the token and extracts user ID
- Fetches the user from the database
- Raises 401 Unauthorized if token is invalid or user not found

## Implementation Details

### Frontend Components

#### ProtectedRoute Component

Location: [`/apps/frontend/src/components/auth/ProtectedRoute.tsx`](../apps/frontend/src/components/auth/ProtectedRoute.tsx)

Features:

- Shows loading spinner during auth state hydration (prevents flash of unauthenticated content)
- Redirects to login if not authenticated
- Preserves intended destination in location state for post-login redirect
- Wraps all protected routes in the app

#### Auth Store

Location: [`/apps/frontend/src/components/store/auth.ts`](../apps/frontend/src/store/auth.ts)

Features:

- Zustand store with persist middleware
- Stores user data, tokens, and authentication status
- Automatically syncs with localStorage
- Handles hydration on app startup
- Provides `setAuth`, `clearAuth`, and `updateUser` actions

#### Auth Hook

Location: [`/apps/frontend/src/hooks/useAuth.ts`](../apps/frontend/src/hooks/useAuth.ts)

Features:

- React Query mutations for login, register, logout
- Returns authentication state and loading status
- Handles success/error toast notifications
- Manages navigation after auth actions

#### Axios Configuration

Location: [`/apps/frontend/src/lib/axios.ts`](../apps/frontend/src/lib/axios.ts)

Features:

- Request interceptor adds Bearer token to all requests
- Response interceptor handles 401 errors
- Automatic token refresh on expiration
- Logout on refresh failure

### Backend Components

#### Authentication Dependency

Location: [`/apps/backend/app/api/deps.py`](../apps/backend/app/api/deps.py)

Functions:

- `get_current_user`: Validates JWT and returns user
- `get_current_active_user`: Ensures user is active
- OAuth2 password bearer scheme configuration

#### Auth Endpoints

Location: [`/apps/backend/app/api/v1/endpoints/auth.py`](../apps/backend/app/api/v1/endpoints/auth.py)

Endpoints:

- `POST /auth/register` - Create new user account
- `POST /auth/login` - Authenticate and receive tokens
- `POST /auth/logout` - Invalidate session (requires auth)
- `POST /auth/refresh` - Exchange refresh token for new access token
- `GET /auth/me` - Get current user info (requires auth)

## Security Best Practices

### ✅ Implemented

- JWT tokens with expiration
- Refresh token rotation
- HTTP-only cookies support (configurable)
- CORS configuration
- Password hashing with bcrypt
- Token validation on every request
- Automatic logout on token expiration
- Protected route enforcement
- State synchronization between localStorage and memory

### 🔒 Additional Recommendations

- Enable HTTPS in production
- Set secure flags on cookies in production
- Implement rate limiting on auth endpoints
- Add CSRF protection for cookie-based auth
- Monitor failed login attempts
- Implement account lockout after failed attempts
- Add two-factor authentication (future enhancement)
- Rotate refresh tokens on use
- Add token blacklisting for logout

## Testing Authentication

### Manual Testing

1. **Test Protected Routes**

   ```
   1. Clear localStorage
   2. Navigate to http://localhost:5173/search
   3. Should redirect to /login
   4. Note the URL should preserve the intended destination
   ```

2. **Test Login Flow**

   ```
   1. Enter credentials on login page
   2. Click login
   3. Should redirect to originally requested page
   4. Verify auth token in localStorage
   ```

3. **Test Token Persistence**

   ```
   1. Login to the application
   2. Refresh the page
   3. Should remain logged in
   4. Should not flash login page
   ```

4. **Test Logout**

   ```
   1. Click logout from user menu
   2. Should redirect to login
   3. Navigate to /search
   4. Should redirect to login (not accessible)
   ```

5. **Test Token Refresh**
   ```
   1. Login to the application
   2. Wait for access token to expire (check token expiration)
   3. Make an API request
   4. Should automatically refresh and succeed
   5. Check network tab for refresh call
   ```

### Backend Testing

Test authentication on backend endpoints:

```bash
# Without auth - should fail with 401
curl http://localhost:8000/api/v1/properties/search

# With auth - should succeed
curl -H "Authorization: Bearer <access_token>" \
     http://localhost:8000/api/v1/properties/search
```

## Troubleshooting

### User is Stuck on Login Page

- Clear localStorage: `localStorage.clear()`
- Check browser console for errors
- Verify backend is running and accessible
- Check CORS configuration

### Token Refresh Fails

- Check refresh token is not expired
- Verify `/auth/refresh` endpoint is working
- Check backend logs for JWT errors
- Ensure JWT_SECRET is consistent

### Flash of Unauthenticated Content

- Verify ProtectedRoute has loading state
- Check Zustand persist is configured correctly
- Ensure auth state hydrates before rendering

### 401 Errors on All Requests

- Verify token is in localStorage
- Check Authorization header in network tab
- Ensure token hasn't expired
- Verify backend JWT_SECRET matches

## Environment Variables

### Frontend

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Backend

```env
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Future Enhancements

- [ ] Implement role-based access control (RBAC)
- [ ] Add two-factor authentication (2FA)
- [ ] Implement social login (Google, GitHub)
- [ ] Add session management (view active sessions)
- [ ] Implement device tracking
- [ ] Add email verification for registration
- [ ] Implement password strength meter
- [ ] Add remember me functionality
- [ ] Implement magic link authentication
- [ ] Add biometric authentication support
