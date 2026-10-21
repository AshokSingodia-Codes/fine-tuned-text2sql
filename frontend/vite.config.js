import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// VITE_API_BASE_URL: set in Netlify env vars to your Render backend URL
// e.g. https://text2sql-api.onrender.com
// Leave empty for single-container / local dev (uses proxy)
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  define: {
    // Expose env var to client bundle (empty string = same origin)
    __API_BASE__: JSON.stringify(process.env.VITE_API_BASE_URL || ''),
  },
  server: {
    port: 3000,
    proxy: {
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': 'http://localhost:8000',
      '/ready': 'http://localhost:8000',
    }
  }
})
