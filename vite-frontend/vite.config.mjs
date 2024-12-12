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
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/az_transcription': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/audiostream': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
});
