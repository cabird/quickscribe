import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  build: {
	  target: 'esnext',
  },
  logLevel: 'info',
  plugins: [react(), tsconfigPaths()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.mjs',
  },
  server: {
    host: '0.0.0.0', // Important for Docker
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true
      },
      '/az_transcription': {
        target: 'http://backend:8000',
        changeOrigin: true
      },
      '/plaud': {
        target: 'http://backend:8000',
        changeOrigin: true
      }
    }
  }
});
