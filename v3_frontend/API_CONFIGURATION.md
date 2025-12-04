# V3 Frontend API Configuration

## Summary

The v3_frontend has been configured to correctly communicate with the backend in both development and production environments.

## How It Works

### Production (Served by Flask Backend)
When the frontend is built and deployed with the Flask backend:

1. **Build**: `npm run build` creates static files in `dist/`
2. **Deploy**: Files copied to `backend/frontend-dist/`
3. **Serve**: Flask serves frontend from `frontend-dist/` folder
4. **API Calls**: Use **relative URLs** (empty `baseURL`)
5. **Same Origin**: Frontend and backend share the same domain
6. **No CORS**: No cross-origin issues

**Example API Call in Production:**
```javascript
// With empty baseURL, axios makes requests to same origin
axios.get('/api/recordings')
// → https://quickscribewebapp.azurewebsites.net/api/recordings
```

### Development (Vite Dev Server)
When running locally with `npm run dev`:

1. **Dev Server**: Vite runs on port 3000
2. **Backend**: Runs on port 5050 (docker-compose) or 5000 (local)
3. **Proxy**: Vite proxies `/api`, `/plaud`, `/az_transcription` to backend
4. **API Calls**: Can use full URL or rely on proxy

**Example API Call in Development:**
```javascript
// VITE_API_URL=http://localhost:5050
axios.get('/api/recordings')
// → Proxied to http://localhost:5050/api/recordings
```

## Configuration Files

### `.env.development`
```env
VITE_API_URL=http://localhost:5050
VITE_AZURE_CLIENT_ID=<placeholder-for-future-auth>
```

### `.env.production`
```env
# Empty - uses relative URLs when served by Flask
VITE_API_URL=
VITE_AZURE_CLIENT_ID=
```

### `vite.config.ts`
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
      '/plaud': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
      '/az_transcription': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
    },
  },
});
```

### `src/services/api.ts`
```typescript
// Empty string in production = relative URLs
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const client = axios.create({
  baseURL: API_BASE_URL,  // '' in production, 'http://localhost:5050' in dev
  headers: {
    'Content-Type': 'application/json',
  },
});
```

## Port Reference

| Environment | Frontend | Backend | Communication |
|-------------|----------|---------|---------------|
| **Production (Azure)** | Served by Flask | 443 (HTTPS) | Relative URLs (same origin) |
| **Development (Vite)** | 3000 | 5050 | Vite proxy + VITE_API_URL |
| **Local Flask** | Served by Flask | 5000 | Relative URLs (same origin) |
| **Docker Compose** | 3000 | 5050 | Vite proxy |

## Testing API Configuration

### Test Production Build Locally

```bash
# Build v3 frontend
cd v3_frontend
npm run build

# Copy to backend
npm run deploy:copy

# Run Flask backend
cd ../backend
source venv/bin/activate
python app.py

# Access at http://localhost:5000
# Open browser DevTools → Network tab
# Verify API calls go to http://localhost:5000/api/*
```

### Test Development Mode

```bash
# Terminal 1: Run backend
cd backend
source venv/bin/activate
python app.py  # Runs on port 5000

# OR use docker-compose (port 5050)
docker-compose up backend

# Terminal 2: Run frontend dev server
cd v3_frontend
npm run dev  # Runs on port 3000

# Access at http://localhost:3000
# Open browser DevTools → Network tab
# Verify API calls are proxied to backend
```

## Common Issues

### Issue: API calls fail in production
**Cause**: `VITE_API_URL` set to absolute URL in `.env.production`
**Solution**: Ensure `VITE_API_URL=` (empty) in `.env.production`

### Issue: CORS errors in development
**Cause**: Vite proxy not configured or backend port mismatch
**Solution**:
1. Check `vite.config.ts` proxy configuration
2. Verify backend port (5050 for docker-compose, 5000 for local)
3. Update `.env.development` if needed

### Issue: 404 errors on API routes
**Cause**: Backend not serving API routes or route mismatch
**Solution**:
1. Verify backend routes in `backend/routes/`
2. Check Flask blueprint registration in `backend/app.py`
3. Ensure route paths match frontend calls

## Key Takeaways

1. **Production uses relative URLs** - `VITE_API_URL` must be empty
2. **Development uses proxy or direct URL** - Configured in vite.config.ts
3. **Same origin = no CORS** - When served by Flask, no CORS issues
4. **Port 5050 in docker-compose** - Not the default 5000
5. **All API routes proxied in dev** - `/api`, `/plaud`, `/az_transcription`
