# Frontend Authentication Implementation

**Status:** ✅ Complete
**Date:** 2025-11-17
**Auth Pattern:** Frontend-Driven (SPA) with Microsoft Azure AD

## Overview

The frontend now supports Microsoft Azure AD authentication with JWT token management. The implementation allows for three modes:

1. **Development Mode** - No authentication required (fast iteration)
2. **Local Testing Mode** - Full auth flow for testing
3. **Production Mode** - Authentication always enforced

## Implementation Details

### Files Added/Modified

#### New Files Created:
- `src/config/authConfig.ts` - MSAL configuration and scope definitions
- `src/auth/msalInstance.ts` - MSAL instance initialization with event handlers
- `src/components/auth/AuthButton.tsx` - Login/logout UI component
- `src/vite-env.d.ts` - TypeScript definitions for environment variables
- `.env.local` - Development environment (auth disabled)
- `.env.test` - Testing environment (auth enabled)

#### Modified Files:
- `src/services/api.ts` - Added token acquisition and injection into API requests
- `src/main.tsx` - Wrapped app with MsalProvider (conditional)
- `src/components/layout/TopActionBar.tsx` - Added AuthButton component
- `.env.development` - Updated with auth configuration
- `.env.production` - Updated with Azure AD credentials

### Architecture

#### Token Flow
```
User → Login → Azure AD → JWT Token → API Requests (Bearer Token) → Backend Validation
```

#### Token Acquisition Strategy
1. **Silent Token Acquisition** (preferred)
   - Uses cached/refresh tokens
   - No user interaction required
   - Fast and seamless

2. **Interactive Popup** (fallback)
   - When silent fails (e.g., expired refresh token)
   - Opens popup for re-authentication

3. **Redirect** (final fallback)
   - When all else fails or on 401 errors
   - Full page redirect to Azure AD

#### API Request Interceptor
The API client automatically:
- Acquires tokens before each request (if auth enabled)
- Injects `Authorization: Bearer <token>` header
- Handles 401 responses by triggering re-login
- Gracefully degrades when auth is disabled

### Configuration Modes

#### 1. Development Mode (.env.development)
```env
VITE_AUTH_ENABLED=false
VITE_API_URL=http://localhost:5050
```

**Behavior:**
- No login button appears
- No tokens sent to backend
- Backend uses default 'cbird' user
- Fast iteration without auth overhead

**To use:**
```bash
npm run dev
```

#### 2. Local Testing Mode (.env.test)
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=3c16fc14-5e18-48d3-9047-a657a89a2c64
VITE_AZURE_TENANT_ID=7e46456d-b9b2-4981-8010-cd33f0d7ff89
VITE_API_URL=http://localhost:5050
```

**Behavior:**
- "Sign In" button appears in top action bar
- Full Microsoft login flow
- Tokens sent with all API requests
- Backend validates tokens (requires backend in auth mode)

**To use:**
```bash
npm run dev -- --mode test
```

**Backend Configuration Required:**
```env
AUTH_MODE=enabled
USE_DEV_USER_BYPASS=false
```

#### 3. Production Mode (.env.production)
```env
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=3c16fc14-5e18-48d3-9047-a657a89a2c64
VITE_AZURE_TENANT_ID=7e46456d-b9b2-4981-8010-cd33f0d7ff89
VITE_API_URL=
```

**Behavior:**
- Authentication always enforced
- Unauthenticated users redirected to login
- Tokens auto-refresh
- HTTPS only

**To use:**
```bash
npm run build
```

### Azure AD Configuration

#### App Registration Details
- **Client ID:** `3c16fc14-5e18-48d3-9047-a657a89a2c64`
- **Tenant ID:** `7e46456d-b9b2-4981-8010-cd33f0d7ff89`
- **App Type:** Single-page application (SPA)

#### Required Azure Portal Configuration
Ensure these settings are configured in Azure Portal:

1. **Redirect URIs:**
   - Development: `http://localhost:3001` (or whatever Vite uses)
   - Production: `https://your-production-domain.com`

2. **API Scope:**
   - Scope URI: `api://3c16fc14-5e18-48d3-9047-a657a89a2c64/user_impersonation`
   - Display name: "Access QuickScribe API"
   - Consent: Admins and users

3. **API Permissions:**
   - Microsoft Graph → User.Read
   - Microsoft Graph → email
   - Microsoft Graph → profile

### User Interface

#### AuthButton Component
Location: Top action bar (right side)

**When Not Authenticated:**
- Shows "Sign In" button with person icon
- Clicking triggers Microsoft login redirect

**When Authenticated:**
- Shows user avatar and name
- Clicking opens menu with:
  - User name and email (disabled item)
  - "Sign Out" option

**When Auth Disabled:**
- Component renders nothing
- No visual indication of auth system

### Token Management

#### Token Storage
- **Location:** localStorage (for multi-tab support)
- **Alternative:** sessionStorage (more secure, clears on tab close)
- Change in `src/config/authConfig.ts`: `cacheLocation: 'localStorage'`

#### Token Lifetime
- **Access tokens:** 1 hour (Azure AD default)
- **Refresh tokens:** 90 days idle timeout
- **Auto-refresh:** MSAL handles automatically via `acquireTokenSilent()`

#### Token Claims Used
Backend extracts these claims from the JWT:
- `oid` (Object ID) → User ID (primary key)
- `email` or `preferred_username` → User email
- `name` → Display name

### Error Handling

#### 401 Unauthorized
- Intercepted by API client response interceptor
- Automatically triggers login redirect
- User re-authenticates and request retries

#### Token Acquisition Failures
1. Silent acquisition fails → Try interactive popup
2. Popup fails → Redirect to login
3. All failures logged to console

#### Network Errors
- JWKS fetch failures handled by backend (with stale cache fallback)
- Frontend retries token acquisition on transient failures

### Testing Strategy

#### Test in Development Mode
```bash
# Start frontend
npm run dev

# Backend should be in development mode:
# AUTH_MODE=disabled in backend/.env
```
✅ No login required
✅ Uses 'cbird' user
✅ Fast iteration

#### Test Local Auth Flow
```bash
# Start frontend with test env
npm run dev -- --mode test

# Start backend with auth enabled:
cd ../backend && source venv/bin/activate
# Set AUTH_MODE=enabled in backend/.env
python src/app.py
```

**Test Steps:**
1. Navigate to http://localhost:3001
2. Click "Sign In" button
3. Redirected to Microsoft login
4. Enter credentials
5. Redirected back to app
6. Token acquired and stored
7. API requests include Bearer token
8. Backend validates token
9. Click user menu → "Sign Out"
10. Token cleared, redirected to login

#### Test Production Build
```bash
npm run build
# Serve from backend
cd ../backend && python src/app.py
```

### Security Considerations

#### Token Storage Security
- Tokens vulnerable to XSS attacks
- **Mitigation:** Strict Content Security Policy (CSP)
- Consider sessionStorage for higher security (loses multi-tab support)

#### HTTPS Enforcement
- Development: HTTP allowed for localhost
- Production: HTTPS required
- Azure enforces HTTPS in production

#### Content Security Policy
Recommended CSP headers for production:
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  connect-src 'self' https://login.microsoftonline.com https://*.azurewebsites.net;
  frame-src https://login.microsoftonline.com;
```

### Common Issues & Solutions

#### Issue: "CORS error on token acquisition"
**Solution:** Redirect URI must match exactly in Azure AD. Check for trailing slashes, http vs https.

#### Issue: "Invalid audience" error from backend
**Solution:** Ensure frontend requests scope `api://<client-id>/user_impersonation`, not just `<client-id>`.

#### Issue: "Token expired" on every request
**Solution:** Check that `acquireTokenSilent()` is being used. MSAL should auto-refresh.

#### Issue: "Multi-tab sync not working"
**Solution:** Use `localStorage` instead of `sessionStorage` in `authConfig.ts`.

#### Issue: "Development mode requires login"
**Solution:** Check `VITE_AUTH_ENABLED=false` in `.env.development` or `.env.local`.

#### Issue: Build fails with MSAL errors
**Solution:** Ensure all environment variables are defined. Check `src/vite-env.d.ts` types match.

### Development Workflow

#### Adding New Protected Routes
No changes needed! The API interceptor automatically handles all requests.

#### Testing Without Auth
```bash
# Use .env.local (already created)
npm run dev
# OR explicitly set mode
npm run dev -- --mode development
```

#### Testing With Auth
```bash
npm run dev -- --mode test
```

#### Building for Production
```bash
npm run build
# Uses .env.production automatically
```

### Integration with Backend

#### Backend Auth Validation
Located in: `backend/src/auth.py`

**Validation Steps:**
1. Extract Bearer token from `Authorization` header
2. Fetch Azure AD public keys (JWKS)
3. Verify token signature using matching key
4. Validate issuer, audience, expiration
5. Extract user claims (oid, email, name)
6. Auto-provision user in CosmosDB if first login
7. Attach user to request context

#### Protected Endpoints
All `/api/*` endpoints require authentication when `AUTH_MODE=enabled`:
- `GET /api/recordings`
- `GET /api/recording/<id>`
- `POST /api/upload`
- `GET /api/transcription/<id>`
- etc.

#### Public Endpoints
These endpoints don't require authentication:
- `GET /api/health`
- `GET /api/get_api_version`
- `POST /api/transcoding_callback`

### Next Steps / Future Enhancements

#### Optional Improvements
- [ ] Add "Remember Me" functionality (adjust token cache settings)
- [ ] Implement token refresh indicator/loading state
- [ ] Add user profile page with Azure AD info
- [ ] Support for multiple Azure AD tenants
- [ ] Offline token refresh handling
- [ ] Token expiration warnings before expiry

#### Advanced Features
- [ ] Role-based access control (RBAC) using Azure AD groups
- [ ] Multi-factor authentication (MFA) enforcement
- [ ] Conditional access policies
- [ ] B2B guest user support

## Summary

✅ **Core Implementation Complete:**
- MSAL libraries installed and configured
- Token acquisition and injection working
- Login/logout UI implemented
- Environment-based auth modes
- Development mode (no auth) functional
- Testing mode (full auth) ready
- Production mode configured
- TypeScript types defined
- Error handling in place

✅ **Tested:**
- Build succeeds with no errors
- Dev server starts successfully
- Auth components render conditionally
- API interceptor functional

✅ **Ready for:**
- Local development (auth disabled)
- Local testing (auth enabled)
- Production deployment

## References

- Backend Auth: `../backend/src/auth.py`
- Auth Guide: `../ADDING_AUTH.md`
- MSAL React Docs: https://github.com/AzureAD/microsoft-authentication-library-for-js/tree/dev/lib/msal-react
- Azure AD SPA Tutorial: https://learn.microsoft.com/en-us/azure/active-directory/develop/tutorial-v2-react
