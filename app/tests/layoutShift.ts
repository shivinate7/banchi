import type { Page } from '@playwright/test'

/* THE ONE LAYOUT-SHIFT READER (D-nothing-moves-unless-moved). `stability.spec.ts` reads a screen's
 * first seconds with it, and the press cases in `inventory.spec.ts` and `orders.spec.ts` read the
 * half second after a press. One observer, so the two cannot disagree about what a shift is.
 *
 * THE MEASURE IS THE BROWSER'S OWN `layout-shift` ENTRY, summed with no recent-input exclusion: a
 * press is an input, and the browser's own score would drop exactly the shift a press causes.
 * `watchShifts` must run before the navigation, since it is an init script. */

export interface Shift {
  readonly value: number
  /** `performance.now()` at the shift. */
  readonly at: number
  /** What moved, as tag and first two classes. */
  readonly moved: readonly string[]
}

export async function watchShifts(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as { __shifts: unknown[] }
    w.__shifts = []
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as {
        value: number
        startTime: number
        sources: { node: Node | null }[]
      }[]) {
        const name = (n: Node | null) => {
          const el = n instanceof Element ? n : n?.parentElement
          if (!el) return '?'
          const cls = typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''
          return el.tagName.toLowerCase() + cls
        }
        w.__shifts.push({ value: e.value, at: e.startTime, moved: e.sources.map((s) => name(s.node)) })
      }
    }).observe({ type: 'layout-shift', buffered: true })
  })
}

/** Every shift so far, and the page's own clock, so a caller can cut a window out of it. */
export async function readShifts(page: Page): Promise<{ shifts: Shift[]; now: number }> {
  return page.evaluate(() => ({
    shifts: (window as unknown as { __shifts: Shift[] }).__shifts,
    now: performance.now(),
  }))
}

export const sumOf = (shifts: readonly Shift[]): number => shifts.reduce((a, s) => a + s.value, 0)

export const describeShifts = (shifts: readonly Shift[]): string =>
  shifts.map((s) => `${s.value.toFixed(4)}@${Math.round(s.at)}[${s.moved.join(',')}]`).join(' ')

/** The page's clock now: take it right before a press, then cut `[mark, mark + 500)`. */
export async function markNow(page: Page): Promise<number> {
  return page.evaluate(() => performance.now())
}
