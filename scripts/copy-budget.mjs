// Pin the copy-budget ceilings from a real run of `app/tests/copy-budget.spec.ts`.
//
//     node scripts/copy-budget.mjs --pin
//
// THIS SCRIPT DOES NOT COUNT A SINGLE WORD. The counting rule — split on whitespace, drop a
// token with no letter — lives once, in `app/tests/copy-budget.spec.ts:countWords`, because a
// second copy here is a second thing to drift the exact way `D194`'s own header
// warns about for the ratchet as a whole. What this does is set `COPY_BUDGET_PIN=1` and run
// that one spec through Playwright, which is the "write the counts instead of asserting them"
// branch the spec's own header names — so the pin path and the assert path are one file
// exercising the same measurement, and the only thing that can differ is what happens to the
// number once it is taken.
//
// It runs the spec DIRECTLY through `npx playwright test`, not through `make design-check` —
// this is a generator (D18: may write, never gates a commit) rather than the suite that
// decides whether the tree is good, so it does not take `scripts/suite-lock.py`'s machine-wide
// lock. Run it when nothing else on this Mac is mid-`make design-check`, the same courtesy any
// other manual Playwright invocation already owes the lock it is not holding.
//
// What it writes: app/tests/copy-budget.json, route -> the word count measured this run,
// exactly — no slack added, because slack is how a ratchet leaks.
import { spawnSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const APP_DIR = resolve(ROOT, 'app')

function main() {
  const args = process.argv.slice(2)
  if (!args.includes('--pin')) {
    console.error('usage: node scripts/copy-budget.mjs --pin')
    process.exit(2)
  }

  console.log('copy-budget: measuring every owner route at 1440 and writing app/tests/copy-budget.json ...')
  const result = spawnSync(
    'npx',
    ['playwright', 'test', 'tests/copy-budget.spec.ts'],
    {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, COPY_BUDGET_PIN: '1' },
    },
  )

  if (result.error) {
    console.error(`copy-budget: could not run Playwright: ${result.error.message}`)
    process.exit(1)
  }
  if (result.status !== 0) {
    console.error(`copy-budget: the pin run itself failed (exit ${result.status}) — nothing was written`)
    process.exit(result.status ?? 1)
  }
  console.log('copy-budget: pinned. `git diff app/tests/copy-budget.json` shows what moved.')
}

main()
