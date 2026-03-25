import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/companies": "http://localhost:8000",
      "/legal-forms": "http://localhost:8000",
      "/cantons": "http://localhost:8000",
      "/sectors": "http://localhost:8000",
    },
  },
})
