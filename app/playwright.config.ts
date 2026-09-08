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
  // THE FIRST OF THIS SUITE'S TWO RECORDED FLAKES WAS THIS NUMBER, AND IT IS A WAIT RATHER
  // THAN AN ASSERTION. Playwright's default is 5s, and under `fullyParallel` every worker's
  // first act is `await expect(page.locator(VIEW)).toBeVisible()` — a cold Vite dev server
  // compiling the module graph for N contexts at once. Measured on this rig at 40 workers
  // against 12 spinning CPU hogs: 9 of 80 repeats of one case failed, every one of them on
  // that first visibility wait and none of them on an assertion; with the wait lengthened the
  // same 80 passed, the slowest whole case taking 5.276s. 15s is ~3x that.
  //
  // RAISING THIS WEAKENS NOTHING, which is the distinction D16 turns on. It does not change
  // what is asserted or the value asserted against — it changes how long a true statement is
  // given to become true, and a statement that is false is still false at 15s. What it costs
  // is slower reporting of a genuine failure, and `fulfillment.spec.ts` already pays that
  // knowingly with a 60s `toHaveCount` of its own.
  //
  // WHAT IT IS NOT IS A CURE FOR A STARVED RIG. At 40 workers against 12 hogs a context can
  // fail to render at all rather than slowly: with the allowance raised to 120s, 10 of 80
  // still failed and one took 122s. A wait cannot answer that, and that load is 4x
  // oversubscription — `make design-check` runs 7 workers. See docs/DEBTS.md.
  expect: { timeout: 15_000 },
  use: {
    baseURL: DEV_URL,

    /* THE SUITE RENDERS WHAT THE OWNER SEES, ON ANY MACHINE. The product formats every date
       with `toLocaleDateString(undefined, ...)` — 63 call sites — which resolves to the
       RUNTIME's zone and locale, and that is correct: a person should see their own. It makes
       a test that asserts a formatted date true only where it was written, and two do.
       FOUND BY RUNNING IT SOMEWHERE ELSE, which is the whole argument for the CI job that
       found it: `pricing.spec.ts` asserts `Box 2 · Aug 23` and a UTC runner drew `Aug 24`,
       because the stamp behind it falls late on the 23rd in America/Chicago. Nothing in this
       config, the Makefile or package.json had ever pinned either, so every date assertion in
       this suite was a fact about one Mac. Reproduced locally with `TZ=UTC` before the pin and
       green after it. The zone is the rig's, so what the suite asserts is still what the owner
       reads over the boxes. */
    timezoneId: 'America/Chicago',
    locale: 'en-US',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: DEV_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
