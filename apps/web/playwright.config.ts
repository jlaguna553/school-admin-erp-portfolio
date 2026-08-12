import { defineConfig, devices } from '@playwright/test';

/**
 * E2E configuration.
 *
 * These tests run against a **running stack** (`docker compose up`) rather than
 * spawning their own server, because the app is only meaningful with a real
 * multi-tenant API behind it: the school is selected by the session's token, so
 * a mocked backend would not exercise the mechanism that matters.
 *
 * Override the target with E2E_BASE_URL / E2E_API_URL when your ports differ.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:3000';

// One hostname serves the platform, so nothing needs subdomain resolution any
// more. Kept because it costs nothing and keeps a stack published under a
// custom *.localhost name working.
const LAUNCH_OPTIONS = {
  args: ['--host-resolver-rules=MAP *.localhost 127.0.0.1'],
};

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  // Serial by default: the suite mutates shared school data (creating and
  // deactivating records), so parallel workers would race each other.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], launchOptions: LAUNCH_OPTIONS },
    },
  ],
});
