import { expect, type Page } from '@playwright/test'

/* ONE STAGGER FOR EVERY LIST (docs/specs/motion.md, P2). Row i of a list waits
 * min(i, --bn-stagger-cap) * --bn-stagger. The expected numbers are READ from the tokens, never
 * copied here, so changing the cadence in tokens.css moves the assertion with it. A list that
 * keeps its own step, or no cap, reads a different delay on some row and fails. */
export async function expectOneStagger(page: Page, rowSelector: string, minRows: number): Promise<void> {
  const { step, cap } = await page.evaluate(() => {
    const css = getComputedStyle(document.documentElement)
    return { step: parseFloat(css.getPropertyValue('--bn-stagger')), cap: parseFloat(css.getPropertyValue('--bn-stagger-cap')) }
  })
  expect(step, '--bn-stagger is a time in ms').toBeGreaterThan(0)
  expect(cap, '--bn-stagger-cap is a count').toBeGreaterThan(0)
  const rows = page.locator(rowSelector)
  expect(await rows.count(), 'the list must be longer than the cap, or the cap is not exercised').toBeGreaterThanOrEqual(minRows)
  expect(minRows).toBeGreaterThan(cap)
  const delays = await rows.evaluateAll((els) =>
    els.map((el) => {
      const d = getComputedStyle(el).animationDelay.split(',')[0]!.trim()
      return d.endsWith('ms') ? parseFloat(d) : parseFloat(d) * 1000
    }),
  )
  delays.forEach((ms, i) => expect(ms, `row ${i} of ${rowSelector}`).toBeCloseTo(Math.min(i, cap) * step, 0))
}
