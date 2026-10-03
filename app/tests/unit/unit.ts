import { test as base } from '@playwright/test'

/* THE UNIT TIER OPENS NO BROWSER. A case that asks for `page`, `context` or `browser` would launch
 * Chromium and cost what the tier exists to avoid, so those fixtures throw. Every unit spec imports
 * `test` from here, and `eslint.config.js` refuses `test` from `@playwright/test` under `tests/unit/`. */
const refuse = (name: string) => async (): Promise<never> => {
  throw new Error(`the unit tier opens no browser: a case asked for \`${name}\`. Move it to a browser spec in app/tests/.`)
}

export const test = base.extend<Record<never, never>>({
  page: refuse('page') as never,
  context: refuse('context') as never,
  browser: refuse('browser') as never,
})

export { expect } from '@playwright/test'
