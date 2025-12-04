# V3 Frontend Deployment Guide

## Deployment Architecture

The QuickScribe V3 frontend uses **Static File Serving via Flask Backend**. The built frontend is bundled with and served by the Flask backend application deployed to Azure App Service.

## How It Works

### 1. Build Output Location
- **Frontend builds to**: `v3_frontend/dist/` (Vite default)
- **Must be copied to**: `backend/frontend-dist/`
- **Backend serves from**: Flask static folder `frontend-dist`

### 2. Flask Static File Serving

The Flask backend (`backend/app.py:57`) serves static files:

```python
app = Flask(__name__, static_folder='frontend-dist', static_url_path=None)
```

The catch-all route serves `index.html` for client-side routing.

### 3. Deployment Flow

```
v3_frontend/
  └─ npm run build
      └─ Outputs to: v3_frontend/dist/
          ├─ index.html
          └─ assets/

  └─ Copy to backend:
      cp -r dist/* ../backend/frontend-dist/

backend/
  └─ make deploy_azure
      ├─ Step 1: build_packages (backend dependencies)
      ├─ Step 2: generate_filelist.py
      │   └─ Reads fileinclude patterns
      │   └─ Includes frontend-dist/* files
      ├─ Step 3: Create app.zip with all files
      └─ Step 4: Deploy to Azure App Service
```

## Deployment Steps

```bash
# 1. Build v3 frontend
cd v3_frontend
npm run build

# 2. Copy to backend (replaces old frontend)
rm -rf ../backend/frontend-dist/*
cp -r dist/* ../backend/frontend-dist/

# 3. Deploy backend (which includes frontend)
cd ../backend
source venv/bin/activate
make deploy_azure
```

## Automated Deployment Script

Use the provided `v3_frontend/deploy.sh`:

```bash
cd v3_frontend
./deploy.sh
```

This will:
1. Build the frontend
2. Copy to `backend/frontend-dist/`
3. Show next steps for backend deployment

## Package.json Scripts

Add deployment helpers to `v3_frontend/package.json`:

```json
{
  "scripts": {
    "dev": "node scripts/sync-models.js && vite",
    "build": "node scripts/sync-models.js && tsc && vite build",
    "deploy:copy": "rm -rf ../backend/frontend-dist/* && cp -r dist/* ../backend/frontend-dist/",
    "deploy:build-and-copy": "npm run build && npm run deploy:copy"
  }
}
```

Usage:
```bash
npm run deploy:build-and-copy  # Build and copy in one step
npm run deploy:copy            # Copy existing dist/ to backend
```

## Vite Configuration for Production

Update `v3_frontend/vite.config.ts` for production builds:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  // Production build configuration
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,  // Disable sourcemaps for production
    minify: 'terser',  // Better minification
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          fluentui: ['@fluentui/react-components', '@fluentui/react-icons']
        }
      }
    }
  },

  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/plaud': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/az_transcription': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
```

## API Configuration

### Development vs Production

The frontend handles API URLs differently based on environment:

**Development** (`npm run dev`):
- Uses Vite dev server on port 3000
- Configured in `.env.development`: `VITE_API_URL=http://localhost:5050`
- Vite proxy forwards `/api`, `/plaud`, `/az_transcription` to backend
- Backend runs on port 5050 (docker-compose) or 5000 (local)

**Production** (deployed with Flask):
- Frontend served by Flask from `frontend-dist/`
- Configured in `.env.production`: `VITE_API_URL=` (empty)
- Empty baseURL means axios uses **relative URLs**
- All API requests go to same origin (Flask server)
- No CORS issues since frontend and backend share same domain

### Port Configuration Summary

| Environment | Frontend Port | Backend Port | API Requests |
|-------------|---------------|--------------|--------------|
| Development (Vite) | 3000 | 5050 | Proxied to http://localhost:5050 |
| Production (Azure) | N/A | 443 (HTTPS) | Relative URLs (same origin) |
| Local Flask | N/A | 5000 | Relative URLs (same origin) |

## Environment Variables

Frontend environment variables (`.env.production`):
- `VITE_API_URL=` (empty for production - uses relative URLs)
- `VITE_AZURE_CLIENT_ID=` (for future auth)

Backend Azure App Service variables:
- `FLASK_ENV=production`
- All backend Azure service credentials
- `CALLBACK_URL` for transcoder callbacks

## Testing Before Deployment

### Local Testing with Backend

```bash
# Terminal 1: Run backend
cd backend
source venv/bin/activate
python app.py

# Terminal 2: Build and copy v3 frontend
cd v3_frontend
npm run build
npm run deploy:copy

# Access at: http://localhost:5000
```

### Docker Compose Testing

Update `docker-compose.yml` to use v3 frontend:

```yaml
services:
  frontend:
    build:
      context: ./v3_frontend
      dockerfile: Dockerfile
    # ... rest of config
```

## Deployment Checklist

- [ ] Update `backend/fileinclude` to include v3 frontend files
- [ ] Configure Flask routes for v3 frontend
- [ ] Build v3 frontend: `npm run build`
- [ ] Copy to backend: `npm run deploy:copy` or `npm run deploy:v3`
- [ ] Test locally with backend
- [ ] Deploy backend: `cd backend && make deploy_azure`
- [ ] Verify deployment at production URL
- [ ] Check browser console for errors
- [ ] Test all major features (recording, transcription, AI workspace)

## Rollback Plan

If v3 deployment has issues:

```bash
# Restore old frontend
cd backend
git checkout frontend-dist/

# Redeploy
make deploy_azure
```

Or keep old frontend in a backup directory:

```bash
# Before replacing
cp -r backend/frontend-dist backend/frontend-dist.backup

# To rollback
rm -rf backend/frontend-dist
mv backend/frontend-dist.backup backend/frontend-dist
make deploy_azure
```

## Azure App Service Configuration

The backend deployment uses:
- **Resource Group**: `QuickScribeResourceGroup`
- **App Service**: `QuickScribeWebApp`
- **Location**: `westus`
- **Plan**: `quickscribe-container-appservice-plan`
- **SKU**: `B2`

Deploy command:
```bash
az webapp deploy --name QuickScribeWebApp \
  --resource-group QuickScribeResourceGroup \
  --type zip --src-path app.zip
```

## Production URLs

- **Production**: `https://quickscribewebapp.azurewebsites.net/`
- **Test Slot**: `https://quickscribewebapp-test.azurewebsites.net/`

## Monitoring After Deployment

1. **Azure Portal**: Check App Service logs
2. **Application Insights**: Monitor frontend errors
3. **Browser DevTools**: Check network requests and console errors
4. **Health Check**: Verify API endpoints responding

## Notes

- The frontend is served as static files by Flask
- All `/api/*`, `/plaud/*`, `/az_transcription/*` routes handled by backend
- React Router handles client-side navigation
- Flask's catch-all route serves `index.html` for unknown paths
- Build output must be included in `backend/fileinclude` patterns
