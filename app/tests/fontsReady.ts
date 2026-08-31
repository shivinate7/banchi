import type { Page } from '@playwright/test'

/* WAIT FOR THE WEB FACES BEFORE MEASURING A LAYOUT.
 *
 * `app/index.html` fetches Atkinson Hyperlegible and Martian Mono from Google Fonts with
 * `&display=swap`. That is a deliberate instruction to the browser to PAINT IN THE FALLBACK
 * FACE FIRST and re-lay-out when the real one arrives, and it is right for the product — a
 * reader sees text immediately rather than a blank column. It is wrong for a ruler. Every
 * `getBoundingClientRect` in this directory is measuring type, and a measurement taken inside
 * the swap window is measuring a DIFFERENT TYPEFACE than the one the assertion was computed
 * against: `app/tests/inventory.spec.ts` prices its own numbers at "Martian Mono's 0.70em
 * advance", which is not the advance of whatever fallback stood in for it.
 *
 * THIS IS NOT THE WHOLE OF THE DESIGN-CHECK FLAKE AND MUST NOT BE READ AS IT. `docs/DEBTS.md`
 * carries the full reading. The recorded red was a `toBeVisible()` timeout in a test's own
 * `open()` — the app had not rendered at all — and that is answered by `expect.timeout` in
 * `app/playwright.config.ts`, not by anything here. What the swap explains is the second,
 * narrower failure: a case that read two tops eleven round-trips apart and subtracted them as
 * though they came from one layout, where the thing moving the grid in between was, in that
 * investigation's own words, "row 1 growing as a face swaps in". That case was fixed by
 * reading both tops in ONE evaluate, which closes the EXPOSURE. This closes the CAUSE, so a
 * measurement written later cannot reopen it by splitting a read again.
 *
 * IT WEAKENS NOTHING. No assertion, threshold or allowance changes; a false statement is still
 * false. What changes is that the ruler and the type agree about which typeface is on screen.
 * `document.fonts.ready` resolves once every face used by the document has settled, so this
 * removes the window rather than sleeping a guessed number of milliseconds inside it.
 */
export async function settleFonts(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready.then(() => true))
}
