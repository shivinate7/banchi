import { defineConfig } from '@playwright/test'

// THE UNIT TIER: the same Playwright runner as `playwright.config.ts`, with no browser, no dev
// server and no checkout-identity setup. A case here takes no `page`, so nothing launches.
// Files are `tests/unit/*.unit.ts`; the browser config's default `*.spec.ts` match never sees them.
export default defineConfig({
  testDir: './tests/unit',
  testMatch: '**/*.unit.ts',
  fullyParallel: true,
  reporter: [['list']],
})
