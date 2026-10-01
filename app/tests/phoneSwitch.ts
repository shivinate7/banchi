import { test, type Page } from '@playwright/test'
import { settleMotion } from './motionSettled'

/* THE ONE SWITCH FOR EVERY PHONE-WIDTH CASE. The owner turned phone off (docs/debts, the
 * phone-off entry). Flip `PHONE_SPECS_ON` to `true` and every phone case runs again; nothing
 * else changes. No test is deleted.
 *
 * A PHONE WIDTH IS BELOW 768, the shell's own phone breakpoint. Every spec sizes its page
 * through `setViewport` instead of `page.setViewportSize`: a phone width skips the case
 * (`test.skip`) while the switch is off, any other width resizes as before. `phone.spec.ts`
 * and gallery's touch-screen block read `PHONE_SPECS_ON` directly. */
export const PHONE_SPECS_ON = false
export const PHONE_BELOW = 768
export const PHONE_OFF_REASON = 'phone-width specs are off by the owner (PHONE_SPECS_ON in phoneSwitch.ts)'

export const isPhoneWidth = (width: number): boolean => width < PHONE_BELOW

/* for a loop over widths inside one case: `if (phoneOff(width)) continue`. */
export const phoneOff = (width: number): boolean => !PHONE_SPECS_ON && isPhoneWidth(width)

export async function setViewport(page: Page, size: { width: number; height: number }): Promise<void> {
  test.skip(phoneOff(size.width), PHONE_OFF_REASON)
  await page.setViewportSize(size)
  /* A resize across the rail breakpoint flips `data-rail` a task later, then the shell
     animates its columns. Two frames let the flip land; `settleMotion` then waits the slide out,
     so the next layout read sees one layout. */
  await page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))))
  await settleMotion(page)
}
