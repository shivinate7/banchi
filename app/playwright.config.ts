import { defineConfig, devices } from '@playwright/test'

// docs/DESIGN.md: "The agent cannot see its own output, so these are Playwright
// assertions, not prose." This config exists to run that table. Today it covers one
// component; step 7 extends it to the Fulfillment view.
//
// `webServer` starts Vite itself, so `make design-check` works from a cold repo without
// anyone remembering to background `make dev` first. reuseExistingServer means it
// attaches to a dev server that is already up rather than failing on the busy port that
// vite.config.ts's strictPort deliberately refuses.
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
