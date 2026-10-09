/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const REPO_ROOT = fileURLToPath(new URL('..', import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Where Vite forwards /api in development. Override with VITE_API_PROXY_TARGET in the
  // environment or in frontend/.env.local when the backend runs on another port.
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // The repository's own .env (the one .env.example describes) is read as well, for VITE_
  // keys the frontend's env files do not set, so VITE_MAP_TILE_KEY can live next to the
  // backend's settings. Vite exposes process.env VITE_* values on import.meta.env.
  for (const [key, value] of Object.entries(loadEnv(mode, REPO_ROOT, 'VITE_'))) {
    if (!(key in env)) {
      env[key] = value
      process.env[key] = value
    }
  }
  const apiProxyTarget = env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      // Same origin in development too: the browser talks to Vite, which forwards /api.
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: false,
        },
      },
    },
    build: {
      sourcemap: false,
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})
