import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // One .env at the repo root feeds both the backend containers and the
  // frontend, so there is a single place to look when something is misconfigured.
  envDir: path.resolve(import.meta.dirname, '../..'),
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // 5173 is occupied by another dev server on this machine.
    port: 5273,
    strictPort: true,
    // Bind to localhost, not 127.0.0.1. Supabase's Sign-In-With-Solana rejects a
    // bare IP as the SIWS message domain ("domain in first line of message is
    // not valid"), and supabase-js derives that domain from window.location.
    // Opening the app on 127.0.0.1:5273 makes wallet sign-in fail.
    host: 'localhost',
    // The API lives on a different origin. Proxying in dev means the browser
    // sees same-origin requests, so CORS and cookie behaviour match production
    // even though the two run separately.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8010',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
