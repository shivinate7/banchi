import { defineConfig, devices } from '@playwright/test'
import { DEV_URL } from './devPort'

// docs/DESIGN.md: "The agent cannot see its own output, so these are Playwright
// assertions, not prose." This config exists to run that table. Today it covers one
// component; step 7 extends it to the Fulfillment view.
//
// `webServer` starts Vite itself, so `make design-check` works from a cold repo without
// anyone remembering to background `make dev` first. reuseExistingServer means it
// attaches to a dev server that is already up rather than failing on the busy port that
// vite.config.ts's strictPort deliberately refuses.
//
// REUSE IS SAFE ONLY BECAUSE THE PORT IS PER-CHECKOUT, and until 2026-08-29 it was not.
// Both this file and vite.config.ts hardcoded 5173, so design-check run from a git
// worktree attached to the MAIN TREE'S server and asserted docs/DESIGN.md's floors against
// code this branch had never seen — and passed. `./devPort` is now the single source both
// configs read, so the only server that can be on this tree's port is this tree's own.
//
// Turning reuse OFF was the obvious fix and is the wrong one: it would leave both trees on
// one port, turning a silent wrong answer into a hard failure, and it would break the case
// where you already have `make dev` up in the tree you are testing. The port was the
// fault; the flag was doing its job.
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: DEV_URL,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: DEV_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
