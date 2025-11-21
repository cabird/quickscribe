# Authentication Guide

**Last Updated:** 2025-11-17
**Authentication Type:** Microsoft Azure AD (OAuth 2.0 / OpenID Connect)
**Pattern:** Frontend-Driven Token-Based Authentication (SPA)

## Overview

QuickScribe uses Microsoft Azure AD for authentication with a modern SPA (Single Page Application) pattern:
- **Frontend** (React): Handles user login flow, acquires access tokens via MSAL
- **Backend** (Flask): Validates JWT tokens on each API request (stateless)
- **Flexible Modes**: Supports development bypass, local testing, and production enforcement

## Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  React Frontend │         │  Azure AD    │         │  Flask Backend  │
│   (MSAL.js)     │         │              │         │   (JWT Valid)   │
└────────┬────────┘         └──────┬───────┘         └────────┬────────┘
         │                         │                          │
         │  1. Redirect to login   │                          │
         ├────────────────────────>│                          │
         │                         │                          │
         │  2. User authenticates  │                          │
         │     (username/password) │                          │
         │                         │                          │
         │  3. Auth code redirect  │                          │
         │<────────────────────────┤                          │
         │                         │                          │
         │  4. Exchange code       │                          │
         ├────────────────────────>│                          │
         │                         │                          │
         │  5. Access token (JWT)  │                          │
         │<────────────────────────┤                          │
         │                         │                          │
         │  6. API call with Authorization: Bearer <token>    │
         ├───────────────────────────────────────────────────>│
         │                         │                          │
         │                         │  7. Validate JWT         │
         │                         │  (signature, exp, aud)   │
         │                         │                          │
         │  8. Protected resource  │                          │
         │<───────────────────────────────────────────────────┤
```

## Authentication Modes

QuickScribe supports three authentication modes controlled by environment variables:

| Mode | Backend AUTH_MODE | Frontend VITE_AUTH_ENABLED | Use Case |
|------|-------------------|----------------------------|----------|
| **Development** | `disabled` | `false` | Fast local dev, test users, no Azure AD |
| **Local Testing** | `enabled` | `true` | Test full auth flow locally |
| **Production** | `enabled` | `true` | Deployed app, auth always enforced |

---

## Mode 1: Development (No Authentication)

**When to use:** Daily development work, creating test data, rapid iteration

### Backend Setup

**File:** `backend/.env`
```env
AUTH_MODE=disabled
LOCAL_AUTH_ENABLED=true
BACKEND_BASE_URL=http://localhost:8000
```

### Frontend Setup

**File:** `v3_frontend/.env.local`
```env
VITE_AUTH_ENABLED=false
VITE_API_URL=http://localhost:8000
```

### How It Works

1. **No Login Required:** Backend uses test users from database
2. **Test User Management:** Switch between test users via local API endpoints
3. **No Azure AD:** No MSAL libraries loaded, no token validation

### Managing Test Users

**Create a test user:**
```bash
curl -X POST http://localhost:8000/api/local/users \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-user-1",
    "name": "Test User One",
    "email": "test1@example.com",
    "is_test_user": true
  }'
```

**Login as test user:**
```bash
curl -X POST http://localhost:8000/api/local/login/test-user-1
```

**Check current user:**
```bash
curl http://localhost:8000/api/local/whoami
```

### Starting Development Mode

```bash
# Backend
cd backend
source venv/bin/activate
python src/app.py

# Frontend (new terminal)
cd v3_frontend
npm run dev

# Access: http://localhost:5173
# No login required, using test-user-1 by default
```

---

## Mode 2: Local Testing (Authentication Enabled)

**When to use:** Testing login flow, debugging token issues, verifying auth logic before deploying

### Prerequisites

1. **Azure AD App Registration** (see Azure AD Setup section below)
2. **Redirect URI** configured: `http://localhost:5173`
3. **API Scope** defined: `api://<your-client-id>/user_impersonation`

### Backend Setup

**File:** `backend/.env.test`
```env
AUTH_MODE=enabled
LOCAL_AUTH_ENABLED=false
BACKEND_BASE_URL=http://localhost:8000

# Azure AD credentials
AZ_AUTH_CLIENT_ID=<your-client-id>
AZ_AUTH_CLIENT_SECRET=<your-client-secret>
AZ_AUTH_TENANT_ID=<your-tenant-id>

# Other Azure services (same as .env)
AZURE_COSMOS_ENDPOINT=...
AZURE_STORAGE_CONNECTION_STRING=...
```

### Frontend Setup

**File:** `v3_frontend/.env.test`
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=<your-client-id>
VITE_AZURE_TENANT_ID=<your-tenant-id>
VITE_API_URL=http://localhost:8000
```

### How It Works

1. **Full Auth Flow:** Frontend redirects to Microsoft login
2. **Token Acquisition:** MSAL acquires access token from Azure AD
3. **Token Validation:** Backend validates JWT signature, claims, expiration
4. **User Provisioning:** Backend auto-creates user in CosmosDB on first login

### Starting Test Mode

```bash
# Backend
cd backend
source venv/bin/activate
cp .env.test .env  # Switch to test mode
python src/app.py

# Frontend (new terminal)
cd v3_frontend
npm run dev -- --mode test  # Uses .env.test

# Access: http://localhost:5173
# Click "Login" button → Redirects to Microsoft
# After login → Redirected back with token
```

### Debugging

**Check token validation:**
```bash
# Get token from browser console
const token = await msalInstance.acquireTokenSilent({...}).accessToken;
console.log(token);

# Manually test backend validation
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer <paste-token-here>"
```

**Decode JWT (for debugging):**
```bash
# Use jwt.io or:
echo "<token>" | cut -d. -f2 | base64 -d | jq .
```

---

## Mode 3: Production (Authentication Required)

**When to use:** Deployed application on Azure

### Backend Setup

**File:** `backend/.env.azure` (baked into Docker image)
```env
AUTH_MODE=enabled
LOCAL_AUTH_ENABLED=false
BACKEND_BASE_URL=https://quickscribewebapp.azurewebsites.net

# Azure AD credentials (from Key Vault or env vars)
AZ_AUTH_CLIENT_ID=<production-client-id>
AZ_AUTH_CLIENT_SECRET=<production-client-secret>
AZ_AUTH_TENANT_ID=<production-tenant-id>

# Production Azure services
AZURE_COSMOS_ENDPOINT=https://quickscribecosmosdb.documents.azure.com:443/
AZURE_STORAGE_CONNECTION_STRING=...
```

### Frontend Setup

**File:** `v3_frontend/.env.production`
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=<production-client-id>
VITE_AZURE_TENANT_ID=<production-tenant-id>
VITE_API_URL=https://quickscribewebapp.azurewebsites.net
```

### How It Works

1. **Auth Always Enforced:** `AUTH_MODE=enabled` cannot be disabled
2. **HTTPS Only:** Tokens only transmitted over secure connections
3. **No Test Users:** Only real Azure AD accounts allowed
4. **Token Validation:** Strict JWT validation on every request

### Deployment

```bash
# Backend
cd backend
make deploy_azure  # Uses .env.azure

# Frontend
cd v3_frontend
npm run build  # Uses .env.production
# Deploy to Azure Static Web Apps or App Service
```

---

## Azure AD Setup

### 1. Register Application (SPA)

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click **New registration**
3. Configure:
   - **Name:** `QuickScribe` (or your app name)
   - **Supported account types:** Single tenant (or multi-tenant if needed)
   - **Redirect URI:**
     - Type: **Single-page application (SPA)**
     - URI: `http://localhost:5173` (add production URI later)
4. Click **Register**
5. Note the **Application (client) ID** and **Directory (tenant) ID**

### 2. Create Client Secret (Backend)

1. In your app registration → **Certificates & secrets**
2. Click **New client secret**
3. Description: `Backend API validation`
4. Expiration: Choose duration (6 months, 1 year, etc.)
5. Click **Add**
6. **Copy the secret VALUE immediately** (won't be shown again)

### 3. Expose API Scope

1. In your app registration → **Expose an API**
2. Click **Add a scope**
3. Application ID URI: `api://<your-client-id>` (suggested)
4. Scope name: `user_impersonation`
5. Who can consent: **Admins and users**
6. Admin consent display name: `Access QuickScribe API`
7. Admin consent description: `Allows the app to access QuickScribe API on behalf of the signed-in user`
8. State: **Enabled**
9. Click **Add scope**

### 4. Configure API Permissions

1. In your app registration → **API permissions**
2. Click **Add a permission** → **Microsoft Graph**
3. Select **Delegated permissions**
4. Add:
   - `User.Read` (basic profile)
   - `email` (email address)
   - `profile` (name, picture)
5. Click **Grant admin consent** (if you're an admin)

### 5. Add Production Redirect URIs

1. In your app registration → **Authentication**
2. Under **Single-page application** platform:
   - Add: `https://your-production-domain.com`
   - Add: `https://your-production-domain.azurewebsites.net`
3. **Implicit grant and hybrid flows:** Leave unchecked (using modern PKCE flow)
4. Click **Save**

### 6. Update Environment Files

```bash
# Copy values from Azure Portal
VITE_AZURE_CLIENT_ID=<Application (client) ID>
VITE_AZURE_TENANT_ID=<Directory (tenant) ID>
AZ_AUTH_CLIENT_ID=<Application (client) ID>
AZ_AUTH_CLIENT_SECRET=<Client secret VALUE>
AZ_AUTH_TENANT_ID=<Directory (tenant) ID>
```

---

## Backend Implementation Details

### Token Validation Process

**File:** `backend/src/auth.py`

1. **Extract token** from `Authorization: Bearer <token>` header
2. **Fetch Azure AD signing keys** from `https://login.microsoftonline.com/<tenant>/discovery/keys`
3. **Decode JWT header** to get `kid` (key ID)
4. **Validate signature** using matching public key
5. **Validate claims:**
   - `iss` (issuer): `https://login.microsoftonline.com/<tenant>/v2.0`
   - `aud` (audience): `<your-client-id>` or `api://<your-client-id>`
   - `exp` (expiration): Token not expired
   - `nbf` (not before): Token is valid now
6. **Return claims** if valid, `None` if invalid

### User Provisioning

**File:** `backend/src/user_util.py`

On first successful login:
```python
# Extract claims from validated token
user_id = claims['oid']  # Azure AD Object ID (stable, unique)
email = claims.get('email') or claims.get('preferred_username')
name = claims.get('name')

# Create user in CosmosDB
user = User(
    id=user_id,  # Use Azure AD oid as primary key
    email=email,
    name=name,
    is_test_user=False,
    created_at=datetime.now(UTC)
)
user_handler.save_user(user)
```

### Protected Routes

**File:** `backend/src/routes/api.py`

```python
from user_util import require_auth, get_current_user

@api_bp.route('/recordings', methods=['GET'])
@require_auth  # Enforces authentication
def get_recordings():
    user = get_current_user()
    # user is guaranteed to exist here
    recordings = recording_handler.get_recordings_by_user(user.id)
    return jsonify([r.model_dump() for r in recordings])
```

---

## Frontend Implementation Details

### MSAL Configuration

**File:** `v3_frontend/src/config/auth.ts`

```typescript
import { Configuration } from '@azure/msal-browser';

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage', // 'localStorage' or 'sessionStorage'
    storeAuthStateInCookie: false,   // Set to true for IE11 or Edge
  },
};

export const loginRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID}/user_impersonation`],
};
```

### API Client with Token Injection

**File:** `v3_frontend/src/api/client.ts`

```typescript
import { msalInstance } from '../auth/msalInstance';
import { loginRequest } from '../config/auth';

async function getAccessToken(): Promise<string> {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) {
    throw new Error('No accounts found. Please login.');
  }

  try {
    // Try silent token acquisition first
    const response = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return response.accessToken;
  } catch (error) {
    // Silent acquisition failed, trigger interactive login
    const response = await msalInstance.acquireTokenPopup(loginRequest);
    return response.accessToken;
  }
}

export async function apiCall(endpoint: string, options: RequestInit = {}) {
  const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true';

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add auth token if enabled
  if (authEnabled) {
    const token = await getAccessToken();
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(
    `${import.meta.env.VITE_API_URL}${endpoint}`,
    { ...options, headers }
  );

  if (!response.ok) {
    if (response.status === 401) {
      // Token expired or invalid, redirect to login
      await msalInstance.loginRedirect(loginRequest);
    }
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}
```

---

## Security Considerations

### Token Lifetimes

- **Access Token:** 1 hour (Azure AD default)
- **Refresh Token:** 90 days (idle timeout)
- **ID Token:** 1 hour

### Storage

- **Frontend:** Tokens in `sessionStorage` (cleared on tab close) or `localStorage` (persistent)
- **Backend:** No token storage (stateless validation)

### HTTPS

- **Development:** HTTP allowed (`http://localhost`)
- **Production:** HTTPS required for all token transmission

### Content Security Policy (CSP)

Frontend should implement CSP headers to prevent XSS:
```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self';
               script-src 'self';
               connect-src 'self' https://login.microsoftonline.com https://*.azurewebsites.net">
```

### CORS

Backend CORS configuration:
```python
# Development
CORS(app, origins=['http://localhost:5173'], supports_credentials=True)

# Production
CORS(app, origins=['https://your-production-domain.com'], supports_credentials=True)
```

---

## Troubleshooting

### "Invalid token" errors

**Check:**
1. Token not expired: `exp` claim > current time
2. Audience matches: `aud` claim = your client ID
3. Issuer correct: `iss` claim = `https://login.microsoftonline.com/<tenant>/v2.0`
4. Signature valid: Backend fetched correct public keys

**Debug:**
```bash
# Decode token to inspect claims
echo "<token>" | cut -d. -f2 | base64 -d | jq .
```

### "CORS errors" in browser

**Check:**
1. Backend CORS enabled for frontend origin
2. `supports_credentials=True` if using cookies
3. Preflight OPTIONS requests handled

### "User not found" after login

**Check:**
1. User provisioning code runs on first login
2. `oid` claim extracted correctly from token
3. CosmosDB connection working

### "Redirect loop" on login

**Check:**
1. Redirect URI matches Azure AD configuration exactly
2. No trailing slashes mismatch
3. MSAL cache not corrupted (clear browser storage)

---

## Testing Checklist

### Development Mode
- [ ] Backend starts without Azure AD credentials
- [ ] Frontend loads without MSAL errors
- [ ] Can switch between test users via `/api/local/login`
- [ ] API calls work without Authorization header

### Local Testing Mode
- [ ] Login button appears
- [ ] Clicking login redirects to Microsoft
- [ ] After auth, redirects back to app
- [ ] Token acquired and stored
- [ ] API calls include Bearer token
- [ ] Backend validates token successfully
- [ ] User created in CosmosDB on first login

### Production Mode
- [ ] Cannot disable auth via environment variables
- [ ] Unauthenticated requests return 401
- [ ] Token validation strict (signature, expiration, audience)
- [ ] HTTPS enforced
- [ ] No test users accessible

---

## References

- [Microsoft Identity Platform Docs](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [MSAL.js Documentation](https://github.com/AzureAD/microsoft-authentication-library-for-js)
- [Azure AD OAuth 2.0 Flow](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)
- [JWT.io Token Debugger](https://jwt.io)
- [Azure AD Token Reference](https://docs.microsoft.com/en-us/azure/active-directory/develop/access-tokens)
