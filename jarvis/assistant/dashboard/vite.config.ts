import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy WebSocket to the assistant's WS server during development
    proxy: {
      '/ws': {
        target: 'ws://localhost:8765',
        ws: true,
        rewriteWsPath: true,
      },
    },
  },
  build: {
    // Build to a directory the Python server can serve
    outDir: 'dist',
    emptyOutDir: true,
  },
})
