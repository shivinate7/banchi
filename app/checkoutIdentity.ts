import type { Plugin } from 'vite'
import { DEV_URL, checkoutRoot } from './devPort'

// A SERVER THIS SUITE REUSES MUST SAY WHICH CHECKOUT IT SERVES
// (D261).
//
// THE INCIDENT, 2026-09-24. Two live worktrees hashed into one slot and both derived dev port
// 5218. A lane in one of them ran `make design-check`. Playwright's `webServer` found 5218
// already answering, reused it (`reuseExistingServer: true`), and ran the suite against the
// OTHER tree's Vite. It passed. `playwright.config.ts` said reuse was "safe only because the
// port is per-checkout". A hash into 300 slots is not per-checkout, so the premise was false.
//
// SO THE PORT IS NO LONGER THE PROOF. Two halves:
//   - `checkoutIdentityPlugin` makes every Vite this repo starts answer `GET /__checkout` with
//     the resolved path of the checkout it serves.
//   - The default export is Playwright's `globalSetup`. Playwright starts or reuses the
//     `webServer` BEFORE `globalSetup` runs (plugin setup comes first in its task list), so
//     this asks the server that is actually there, and refuses the whole run unless it names
//     THIS checkout. A server that does not answer, or answers with something that is not
//     JSON (an older Vite's 404, or another program), is refused too: no answer is not a yes.
//
// Reuse stays ON. A server this checkout started with `make dev` is still attached to, and it
// names this checkout, so it passes. The slot registry (`scripts/port-slots.py`) is what keeps
// two trees off one port in the first place. This file is what makes a shared port harmless
// when that fails.
//
// `PKMNSCAN_CHECKOUT_IDENTITY=off` skips the check, and the refusal prints it.

export const IDENTITY_PATH = '/__checkout'
export const IDENTITY_ESCAPE_ENV = 'PKMNSCAN_CHECKOUT_IDENTITY'

export function checkoutIdentityPlugin(): Plugin {
  const checkout = checkoutRoot()
  return {
    name: 'banchi-checkout-identity',
    configureServer(server) {
      // Registered directly, so it runs before Vite's own middlewares, and the SPA fallback
      // never answers this path with index.html.
      server.middlewares.use(IDENTITY_PATH, (_req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.setHeader('Cache-Control', 'no-store')
        res.end(JSON.stringify({ checkout }))
      })
    },
  }
}

// What the server at `base` says it serves: the path, or null when it does not say.
export async function servedCheckout(base: string): Promise<string | null> {
  try {
    const response = await fetch(`${base}${IDENTITY_PATH}`, {
      headers: { accept: 'application/json' },
    })
    if (!response.ok) return null
    const body: unknown = await response.json()
    const served = (body as { checkout?: unknown } | null)?.checkout
    return typeof served === 'string' ? served : null
  } catch {
    return null
  }
}

export async function verifyCheckout(base: string, checkout: string): Promise<void> {
  if ((process.env[IDENTITY_ESCAPE_ENV] ?? '').trim() === 'off') return
  const served = await servedCheckout(base)
  if (served === checkout) return
  throw new Error(
    [
      `REFUSED: the dev server on ${base} is not this checkout's, so this run would test another tree's code.`,
      `  this checkout: ${checkout}`,
      `  that server:   ${served ?? 'does not say which checkout it serves (an older build, or another program)'}`,
      '  No test ran. Two checkouts share this port.',
      '  Remedy: `python3 scripts/port-slots.py claim` gives this checkout a slot of its own, and',
      '  `make design-check` runs it first. If this checkout already holds the slot, the other',
      '  tree claims its own the next time it serves. Never stop a server you did not start.',
      `  ${IDENTITY_ESCAPE_ENV}=off skips this check.`,
    ].join('\n'),
  )
}

export default async function globalSetup(): Promise<void> {
  await verifyCheckout(DEV_URL, checkoutRoot())
}
