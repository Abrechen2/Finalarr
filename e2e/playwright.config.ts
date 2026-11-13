import { defineConfig } from '@playwright/test'

// The app, the demo Sonarr and the hook receiver are started by run.sh.
export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.FINALARR_URL ?? 'http://127.0.0.1:15791',
    locale: 'de-DE',
    trace: 'off',
  },
})
