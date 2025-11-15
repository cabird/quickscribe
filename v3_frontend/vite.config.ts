import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy all API routes to backend during development
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
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
});
