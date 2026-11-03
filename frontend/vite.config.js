import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // During local dev, /analyze calls go to FastAPI without CORS issues
      '/analyze': 'http://localhost:8000',
      '/health':  'http://localhost:8000',
    },
  },
})
