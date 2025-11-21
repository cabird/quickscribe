# Adding Microsoft Azure AD Authentication to Frontend

**Status:** ✅ COMPLETE - Both backend and frontend implementation finished.
**Date:** 2025-11-17
**Implementation Date:** 2025-11-17
**Authentication Pattern:** Frontend-Driven (SPA) with JWT tokens

> **Note:** For detailed frontend implementation documentation, see [AUTH_IMPLEMENTATION.md](./AUTH_IMPLEMENTATION.md)

## Overview

The backend Flask API now supports Microsoft Azure AD authentication with JWT token validation. The frontend needs to be updated to:
1. Handle user login/logout via Microsoft
2. Acquire and manage access tokens
3. Inject tokens into all API requests
4. Handle token expiration and refresh

## Backend Implementation Status

✅ **Complete:**
- JWT token validation in `backend/src/auth.py`
- Environment-based auth modes (development/testing/production)
- `@require_auth` decorator on all protected routes
- Auto-user provisioning on first login using Azure AD `oid` claim
- Thread-safe JWKS caching with staleness protection

## Authentication Modes

The system supports three modes controlled by backend environment variables:

### 1. Development Mode (Current Default)
**Backend Settings:**
```env
AUTH_MODE=disabled
USE_DEV_USER_BYPASS=true
DEFAULT_DEV_USER=cbird
```

**Behavior:**
- No authentication required
- Uses default 'cbird' user or test users
- No token validation
- Fast iteration for development

### 2. Local Testing Mode
**Backend Settings:**
```env
AUTH_MODE=enabled
USE_DEV_USER_BYPASS=false
```

**Frontend Settings:**
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=<your-client-id>
VITE_AZURE_TENANT_ID=<your-tenant-id>
```

**Behavior:**
- Full authentication flow enabled
- Frontend acquires tokens from Azure AD
- Backend validates JWT tokens
- Test locally before deploying

### 3. Production Mode
**Backend Settings (baked into Docker):**
```env
AUTH_MODE=enabled
USE_DEV_USER_BYPASS=false
```

**Frontend Settings (.env.production):**
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=<production-client-id>
VITE_AZURE_TENANT_ID=<production-tenant-id>
```

**Behavior:**
- Authentication always enforced
- HTTPS only
- Strict JWT validation

## Azure AD Configuration

### App Registration Details
The backend is configured to accept tokens from this Azure AD app:

**From backend/.env:**
- **Client ID:** `3c16fc14-5e18-48d3-9047-a657a89a2c64`
- **Tenant ID:** `7e46456d-b9b2-4981-8010-cd33f0d7ff89`
- **Client Secret:** (backend only, not needed for frontend)

### Required Azure AD Setup

Before implementing frontend auth, ensure the following are configured in Azure Portal:

1. **App Registration Type:** Single-page application (SPA)
2. **Redirect URIs:**
   - Development: `http://localhost:5173` (or whatever Vite uses)
   - Production: `https://your-production-domain.com`
3. **API Scope (Expose an API):**
   - Scope URI: `api://3c16fc14-5e18-48d3-9047-a657a89a2c64/user_impersonation`
   - Display name: "Access QuickScribe API"
   - Who can consent: Admins and users
4. **API Permissions:**
   - Microsoft Graph → User.Read (basic profile)
   - Microsoft Graph → email (email address)
   - Microsoft Graph → profile (name, picture)

### Token Requirements

**The frontend must request:**
- **Scope:** `api://3c16fc14-5e18-48d3-9047-a657a89a2c64/user_impersonation`
- **Authorization Flow:** Authorization Code with PKCE (handled by MSAL)

**The backend validates:**
- **Audience (`aud`):** Either `3c16fc14-5e18-48d3-9047-a657a89a2c64` or `api://3c16fc14-5e18-48d3-9047-a657a89a2c64`
- **Issuer (`iss`):** `https://login.microsoftonline.com/7e46456d-b9b2-4981-8010-cd33f0d7ff89/v2.0`
- **Claims used:**
  - `oid` (Object ID) → User ID (primary key)
  - `email` or `preferred_username` → User email
  - `name` → Display name

## Frontend Implementation Requirements

### 1. Install MSAL Libraries

```bash
npm install @azure/msal-react @azure/msal-browser
```

**Versions to use:**
- `@azure/msal-react`: Latest stable (v2.x)
- `@azure/msal-browser`: Latest stable (v3.x)

### 2. Create Authentication Configuration

**File:** `src/config/authConfig.ts`

**Required Configuration:**
```typescript
import { Configuration, LogLevel } from '@azure/msal-browser';

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage', // or 'localStorage'
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Info,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        console.log(message);
      }
    }
  }
};

export const loginRequest = {
  scopes: ['api://3c16fc14-5e18-48d3-9047-a657a89a2c64/user_impersonation'],
};

export const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true';
```

**Important Notes:**
- Use exact scope URL from backend configuration
- `sessionStorage` clears on tab close (more secure)
- `localStorage` persists across tabs (better UX)

### 3. Initialize MSAL Instance

**File:** `src/auth/msalInstance.ts`

**Pattern:**
```typescript
import { PublicClientApplication } from '@azure/msal-browser';
import { msalConfig } from '../config/authConfig';

export const msalInstance = new PublicClientApplication(msalConfig);

// Initialize the instance before using
await msalInstance.initialize();
```

### 4. Wrap App with MSAL Provider

**File:** `src/main.tsx` or `src/App.tsx`

**Pattern:**
```typescript
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from './auth/msalInstance';
import { authEnabled } from './config/authConfig';

// If auth enabled, wrap with MsalProvider
if (authEnabled) {
  return (
    <MsalProvider instance={msalInstance}>
      <App />
    </MsalProvider>
  );
} else {
  // Development mode: no auth wrapper
  return <App />;
}
```

### 5. Create API Client with Token Injection

**File:** `src/api/client.ts` or update existing API client

**Required Functionality:**
- Detect if auth is enabled
- Acquire token silently before each request
- Add `Authorization: Bearer <token>` header
- Handle 401 responses (token expired)
- Automatic token refresh via MSAL

**Token Acquisition Pattern:**
```typescript
import { msalInstance } from '../auth/msalInstance';
import { loginRequest } from '../config/authConfig';

async function getAccessToken(): Promise<string | null> {
  if (!authEnabled) return null;

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) {
    // User not logged in, redirect to login
    await msalInstance.loginRedirect(loginRequest);
    return null;
  }

  try {
    // Try silent token acquisition
    const response = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return response.accessToken;
  } catch (error) {
    // Silent acquisition failed, try interactive
    const response = await msalInstance.acquireTokenPopup(loginRequest);
    return response.accessToken;
  }
}

// In API calls
const token = await getAccessToken();
const headers = {
  'Content-Type': 'application/json',
  ...(token && { 'Authorization': `Bearer ${token}` })
};
```

### 6. Create Login/Logout Components

**Login Button:**
- Conditionally render only when auth enabled
- Trigger `msalInstance.loginRedirect(loginRequest)` or `loginPopup()`
- Show loading state during redirect

**Logout Button:**
- Trigger `msalInstance.logoutRedirect()` or `logoutPopup()`
- Clears local tokens and Azure AD session

**User Profile Display:**
- Use `useMsal()` hook to get account info
- Display user name/email from `accounts[0]`

### 7. Handle Authentication State

**MSAL React Hooks:**
- `useMsal()` - Access MSAL instance and accounts
- `useIsAuthenticated()` - Boolean auth state
- `useMsalAuthentication()` - Trigger auth flow

**Pattern:**
```typescript
import { useIsAuthenticated, useMsal } from '@azure/msal-react';

function MyComponent() {
  const isAuthenticated = useIsAuthenticated();
  const { accounts } = useMsal();

  if (!authEnabled) {
    // Development mode: always show content
    return <Content />;
  }

  if (!isAuthenticated) {
    return <LoginPrompt />;
  }

  return <Content user={accounts[0]} />;
}
```

### 8. Environment Configuration

**Development (.env.local):**
```env
VITE_AUTH_ENABLED=false
VITE_API_URL=http://localhost:8000
```

**Local Testing (.env.test):**
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=3c16fc14-5e18-48d3-9047-a657a89a2c64
VITE_AZURE_TENANT_ID=7e46456d-b9b2-4981-8010-cd33f0d7ff89
VITE_API_URL=http://localhost:8000
```

**Production (.env.production):**
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=3c16fc14-5e18-48d3-9047-a657a89a2c64
VITE_AZURE_TENANT_ID=7e46456d-b9b2-4981-8010-cd33f0d7ff89
VITE_API_URL=https://quickscribewebapp.azurewebsites.net
```

## Current Backend API Endpoints

All endpoints under `/api/*` now require authentication when `AUTH_MODE=enabled`:

**Public Endpoints (no auth required):**
- `GET /api/health` - Health check
- `GET /api/get_api_version` - API version
- `POST /api/transcoding_callback` - Transcoder service callback

**Protected Endpoints (auth required):**
- `GET /api/recordings` - List user's recordings
- `GET /api/recording/<id>` - Get recording details
- `POST /api/upload` - Upload audio file
- `GET /api/transcription/<id>` - Get transcription
- `POST /api/tags/create` - Create tag
- All other `/api/*` endpoints

**Development-Only Endpoints (gated by USE_DEV_USER_BYPASS):**
- `POST /api/local/login` - Switch test users
- `GET /api/local/users` - List test users
- `POST /api/local/create_test_user` - Create test user

## Backend Auth Flow

**When Auth Enabled:**

1. Frontend makes API request with `Authorization: Bearer <token>`
2. Backend `@require_auth` decorator intercepts request
3. `extract_token_from_header()` extracts token from header
4. `validate_token()` validates JWT:
   - Fetches Azure AD public keys (cached 24hrs)
   - Verifies signature using matching key
   - Validates issuer, audience, expiration
   - Returns claims if valid
5. `get_current_user()` extracts user info:
   - Gets `oid` (Object ID) from token
   - Fetches user from CosmosDB
   - Auto-provisions if first login
6. Request proceeds with authenticated user

**When Auth Disabled (Development):**

1. Frontend makes API request (no token needed)
2. Backend `@require_auth` decorator checks `AUTH_MODE`
3. If `disabled` + `USE_DEV_USER_BYPASS=true`:
   - Uses session user (from `/api/local/login`)
   - Falls back to `DEFAULT_DEV_USER` ('cbird')
4. Request proceeds with test user

## Testing Strategy

### Test in Development Mode
1. Set `VITE_AUTH_ENABLED=false` in frontend
2. Set `AUTH_MODE=disabled` in backend
3. No login required, uses 'cbird' user
4. Fast iteration, no Azure AD involved

### Test Local Auth Flow
1. Create frontend `.env.test` with auth enabled
2. Create backend `.env.test` with auth enabled (already exists)
3. Run backend: `cd backend && source venv/bin/activate && cp .env.test .env && python src/app.py`
4. Run frontend: `npm run dev -- --mode test`
5. Login button should appear
6. Click login → Redirect to Microsoft
7. After login → Token acquired
8. API calls should include Bearer token
9. Backend validates token

### Test Production Mode
1. Deploy backend with `.env.azure` (AUTH_MODE=enabled)
2. Build frontend with `.env.production`
3. Authentication always enforced
4. No bypass available

## Common Issues & Solutions

### Issue: "CORS error on token acquisition"
**Solution:** Redirect URI must match exactly in Azure AD configuration. Check for trailing slashes, http vs https.

### Issue: "Invalid audience" error from backend
**Solution:** Ensure frontend requests scope `api://<client-id>/user_impersonation`, not just `<client-id>`.

### Issue: "Token expired" on every request
**Solution:** MSAL should auto-refresh. Check `acquireTokenSilent()` is being used, not just initial token.

### Issue: "Multi-tab sync not working"
**Solution:** Use `localStorage` instead of `sessionStorage` in MSAL config. MSAL handles cross-tab token sharing.

### Issue: "User not found after login"
**Solution:** Backend auto-provisions users. Check that `oid` claim exists in token and CosmosDB is accessible.

### Issue: "Development mode requires login"
**Solution:** Check `VITE_AUTH_ENABLED=false` in frontend .env and `AUTH_MODE=disabled` in backend .env.

## Security Considerations

### Token Storage
- **sessionStorage:** More secure, clears on tab close
- **localStorage:** Better UX, persists across tabs
- Tokens are vulnerable to XSS attacks
- **Mitigation:** Strict Content Security Policy (CSP)

### Token Lifetime
- Access tokens: 1 hour (Azure AD default)
- Refresh tokens: 90 days idle timeout
- MSAL handles refresh automatically

### HTTPS Enforcement
- Development: HTTP allowed for localhost
- Production: HTTPS required for all token transmission
- Azure enforces HTTPS in production

### Content Security Policy
Recommended CSP headers for production:
```
Content-Security-Policy: default-src 'self';
  script-src 'self';
  connect-src 'self' https://login.microsoftonline.com https://*.azurewebsites.net;
  frame-src https://login.microsoftonline.com;
```

## Implementation Checklist

**Before Starting:**
- [ ] Verify Azure AD app registration is type "SPA"
- [ ] Confirm redirect URIs configured for dev and prod
- [ ] Verify API scope exists: `api://<client-id>/user_impersonation`
- [ ] Test backend in development mode (should work without changes)

**Core Implementation:**
- [ ] Install `@azure/msal-react` and `@azure/msal-browser`
- [ ] Create `src/config/authConfig.ts` with MSAL configuration
- [ ] Create `src/auth/msalInstance.ts` to initialize MSAL
- [ ] Wrap app with `MsalProvider` (conditionally, based on auth enabled)
- [ ] Update API client to inject Bearer tokens
- [ ] Handle 401 responses (redirect to login)
- [ ] Create login/logout buttons
- [ ] Add user profile display

**Environment Configuration:**
- [ ] Create `.env.local` with `VITE_AUTH_ENABLED=false`
- [ ] Create `.env.test` with `VITE_AUTH_ENABLED=true` + Azure config
- [ ] Create `.env.production` with production Azure config
- [ ] Add `.env*` to `.gitignore` (should already be there)

**Testing:**
- [ ] Test development mode (no auth)
- [ ] Test local auth mode (full flow)
- [ ] Test token refresh (wait for expiration or force)
- [ ] Test multi-tab behavior
- [ ] Test logout and re-login
- [ ] Test 401 handling (expired token)
- [ ] Test with multiple test users

**Production Readiness:**
- [ ] Configure CSP headers
- [ ] Ensure HTTPS in production
- [ ] Test production build locally
- [ ] Deploy and verify end-to-end flow

## Reference Documentation

**MSAL Documentation:**
- [MSAL React Quickstart](https://github.com/AzureAD/microsoft-authentication-library-for-js/tree/dev/lib/msal-react)
- [MSAL Browser Configuration](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/configuration.md)
- [Acquiring Tokens](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/acquire-token.md)

**Azure AD:**
- [Azure AD SPA Tutorial](https://learn.microsoft.com/en-us/azure/active-directory/develop/tutorial-v2-react)
- [Token Claims Reference](https://learn.microsoft.com/en-us/azure/active-directory/develop/access-tokens)

**Project Documentation:**
- `/AUTH.md` (repository root) - Comprehensive auth guide for all modes
- `backend/SYSTEM_DESCRIPTION.md` - Backend architecture and auth details
- `backend/src/auth.py` - JWT validation implementation (reference)
- `backend/src/user_util.py` - Auth mode logic (reference)

## Questions to Resolve Before Implementation

1. **Login UX:** Redirect or popup? (Recommend redirect for better UX)
2. **Token Storage:** sessionStorage or localStorage? (Recommend localStorage for multi-tab support)
3. **Protected Routes:** Wrap individual components or use route guards?
4. **Error Handling:** Where to display auth errors? Toast? Modal? Inline?
5. **Loading States:** Show spinner during token acquisition? Full-page or inline?

## Success Criteria

**Development Mode:**
- App works without any login prompts
- Uses 'cbird' or selected test user
- Fast iteration maintained

**Local Testing Mode:**
- Login button appears
- Redirects to Microsoft login
- Acquires and stores token
- All API calls include Bearer token
- Backend accepts and validates token
- User auto-provisioned in CosmosDB

**Production Mode:**
- Authentication always enforced
- Unauthenticated users see login screen
- Tokens refreshed automatically
- Logout clears all state
- 401 errors trigger re-login
