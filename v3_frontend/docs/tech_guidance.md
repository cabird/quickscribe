## Recommended Dev Setup for React + Fluent UI + TypeScript

### **Yes, TypeScript works great with Fluent UI!** 
Fluent UI has excellent TypeScript support - in fact, it's written in TypeScript, so you get perfect type definitions out of the box.

## **Recommended Stack**

### **1. Use Vite** (Strongly Recommended)
```bash
npm create vite@latest meeting-recordings-frontend -- --template react-ts
cd meeting-recordings-frontend
npm install
```

**Why Vite over Create React App:**
- ? **MUCH faster** hot module reload (instant vs 3-5 seconds)
- ?? Faster build times
- ?? Smaller bundle sizes
- ?? Better TypeScript support
- ?? Modern and actively maintained (CRA is basically deprecated)

### **2. Install Fluent UI & Dependencies**
```bash
# Fluent UI components and icons
npm install @fluentui/react-components @fluentui/react-icons

# For API calls to your Flask backend
npm install axios

# For routing if you need multiple pages
npm install react-router-dom
npm install -D @types/react-router-dom
```

### **3. Dev Tools**
```bash
# ESLint & Prettier for code quality
npm install -D eslint prettier eslint-plugin-prettier eslint-config-prettier

# For environment variables
npm install -D dotenv
```

## **Project Structure**
```
meeting-recordings-frontend/
��� src/
�   ��� components/
�   �   ��� NavigationRail.tsx
�   �   ��� RecordingsList.tsx
�   �   ��� TranscriptViewer.tsx
�   �   ��� LogsViewer.tsx
�   �   ��� SearchView.tsx
�   ��� services/
�   �   ��� api.ts          # Axios config for Flask backend
�   ��� types/
�   �   ��� index.ts        # TypeScript interfaces
�   ��� hooks/
�   �   ��� useRecordings.ts
�   ��� App.tsx
�   ��� main.tsx
��� .env.development        # Local dev config
��� .env.production        # Production config
��� vite.config.ts
```

## **TypeScript Types Example**
```typescript
// src/types/index.ts
export interface Recording {
  id: string;
  title: string;
  date: string;
  time: string;
  duration: string;
  speakers: string[];
  description: string;
  transcript: TranscriptEntry[];
}

export interface TranscriptEntry {
  time: string;
  speaker: string;
  text: string;
}
```

## **API Service Setup**
```typescript
// src/services/api.ts
import axios from 'axios';
import type { Recording } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const recordingsApi = {
  getAll: () => api.get<Recording[]>('/recordings'),
  getById: (id: string) => api.get<Recording>(`/recordings/${id}`),
  search: (query: string) => api.post('/search/rag', { query }),
};
```

## **Environment Variables**
```bash
# .env.development
VITE_API_URL=http://localhost:5000

# .env.production
VITE_API_URL=https://your-api-domain.com
```

## **Vite Config for Flask Backend**
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Proxy API calls to Flask during development
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});
```

## **Package.json Scripts**
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .ts,.tsx",
    "format": "prettier --write 'src/**/*.{ts,tsx,css}'"
  }
}
```

## **CORS Setup for Flask**
Don't forget to enable CORS in your Flask backend:
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=['http://localhost:3000'])  # Add your frontend URL
```

## **VS Code Extensions**
Install these for the best dev experience:
- **Prettier** - Code formatter
- **ESLint** - Linting
- **TypeScript React code snippets**
- **Fluent UI React Snippets** (if available)
- **Thunder Client** or **REST Client** - Test your Flask API

## **Quick Start Commands**
```bash
# Full setup in one go:
npm create vite@latest my-app -- --template react-ts
cd my-app
npm install
npm install @fluentui/react-components @fluentui/react-icons axios
npm install -D @types/node
npm run dev
```

Your app will be at `http://localhost:3000` and can talk to Flask at `http://localhost:5000`.

**Pro tip:** Keep your Flask backend running on port 5000, and Vite dev server on port 3000. The proxy config will handle the API calls seamlessly!
