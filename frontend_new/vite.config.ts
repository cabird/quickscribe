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
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/plaud': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/az_transcription': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
