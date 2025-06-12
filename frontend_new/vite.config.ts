import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@mantine/core/styles.css";`,
      },
    },
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
