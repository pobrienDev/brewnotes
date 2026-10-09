import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end smoke tests (plan Section 12) against a running BrewNotes with the fake GitHub
 * sign-in from backend/tests/e2e/harness.py. Locally that is the Vite dev server on 5180
 * proxying to the harness on 8001; in CI the harness serves the built frontend itself.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5180',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
