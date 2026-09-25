import type { Page } from '@playwright/test'

/* WAIT FOR THE ENTRY MOTION BEFORE MEASURING A POSITION.
 *
 * THE SAME ARGUMENT `fontsReady.ts` MAKES ABOUT THE SWAP WINDOW, one layer out. `kit.css`'s
 * `bn-page-in` runs `translateY(6px)` to `none` over `--bn-t` on every list row the product
 * draws, each row delayed by `.bn-stagger`. A `boundingBox()` taken inside that window is
 * reading a position the browser is still moving, and the number it returns is whatever frame
 * the compositor last painted. It is not noise and it is not a rounding difference: it is a
 * real, correct reading of a real, transient position.
 *
 * WHAT IT COST BEFORE IT HAD A NAME. `orders.spec.ts`'s D118 guard — "the sentence changing on
 * a write moves no box row beneath it" — subtracted two such readings and failed about a third
 * of the time, once on CI in `design-check` shard 2 on 2026-09-17. It was read as a flaky
 * guard, then as a real one-pixel reflow in the product, and it was neither. Measured on the
 * rig over twelve runs: `getBoundingClientRect` inside the page reports the gap as exactly
 * 26px every single time, before and after, while `boundingBox()` taken at the same moment
 * reported 24.88, 25.36, 25.41 and 26.00. Awaiting this helper first, the same twelve runs
 * report 26.000 against 26.000 with a drift of 0.000. The tree never moved.
 *
 * IT WEAKENS NOTHING, AND THE ASSERTIONS AROUND IT GOT TIGHTER, NOT LOOSER. No threshold moves.
 * A layout that really does reflow still reflows once it has stopped animating; what changes is
 * that the ruler and the page agree about which frame is being measured. This removes the
 * window rather than sleeping a guessed number of milliseconds inside it.
 *
 * A LOOPING ANIMATION IS EXCLUDED BY CONSTRUCTION. `docs/DESIGN.md`: only loops carrying
 * meaning keep turning, and a spinner's `iterations` is `Infinity` — it never reaches
 * `finished`, so waiting on it would hang rather than settle. Finite animations only.
 *
 * SO IS A SCROLL-DRIVEN ONE, AND THAT EXCLUSION WAS MISSING UNTIL 2026-09-19. A progress
 * animation attached to `scroll()` rather than to the document's clock has `iterations: 1` and
 * is therefore FINITE, but it advances with a scroller's position and not with time: it reads
 * `running` for as long as the element exists and reaches `finished` only if the scroller is
 * pushed to its end. `.orders-chips` and `.review-filters` each carry one below 768px
 * (`animation-timeline: scroll(self inline)`, the phone chip strip's edge fade), so this helper
 * hung for its full 30s timeout on every phone-width render of `#/orders` and `#/review` —
 * measured, not inferred: `bn-edgefade` on `DIV.orders-chips`, `playState: running`,
 * `iterations: 1`, forever.
 *
 * THE TEST IS THE TIMELINE AND NOT THE NAME. `animation.timeline !== document.timeline` is true
 * of exactly the animations whose progress is not a clock, so a scroll or view timeline added
 * to any other screen is covered the day it lands rather than the day somebody remembers to add
 * its class here.
 */
export async function settleMotion(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .filter((one) => (one.effect?.getTiming().iterations ?? 1) !== Infinity)
      .filter((one) => one.timeline === document.timeline)
      .every((one) => one.playState === 'finished'),
  )
}

/* D118'S OWN SWEEP, ONE COPY. `inventory.spec.ts` ("the press that sells a copy moves nothing
 * outside the panel it lands in") and `confirm-identity.spec.ts` ("the confirm press moves
 * nothing outside the panel it lands in") each carried a byte-identical `outsideThePanel` /
 * `whatMoved`, and `confirm-identity.spec.ts` alone carried `settled` on top — moved here
 * rather than kept as two copies.
 *
 * THE RACE THIS `settled` CLOSES: the box rail opens the walk's first section as a consequence
 * of landing on it (`BoxBrowse.tsx`, the effect keyed on `selected`), including on the very
 * first render, so the walk never arrives with its own selection hidden. That fold's chevron
 * (`.browse-sectmark`) rotates in over `.2s`, entirely on MOUNT and independent of either press.
 * BOTH specs' `open()` wait for `.browse-sectfold` to be VISIBLE before returning, and visible
 * is not settled — the fold can already report a size and still be mid-rotation, so a "before"
 * sample taken right after can catch it moving. MEASURED (CI run 36089115485's trace,
 * reproduced locally by throttling the CPU 6x): the chevron's own svg and path, unsettled —
 * `svg @ 303,477 h16 -> svg @ 304,478 h14` — settled into the SAME shape by the next sample,
 * and neither press ever touched it.
 *
 * `settleMotion` above does not close this one: it waits for every animation already RUNNING
 * at the moment it is called, but the chevron's rotation can start (on mount) and finish before
 * either spec ever calls it, or can still be mid-flight when `outsideThePanel`'s own
 * `getBoundingClientRect` sample runs a tick later — the gap is between two READS of the DOM,
 * not between a press and an animation `settleMotion` can watch start-to-finish. Sampling twice
 * and requiring agreement reads the chevron once it has stopped moving, on its own schedule,
 * never on the press's — so a press that genuinely moves something still fails this every time,
 * because two samples of a REAL move never agree either. */

/** Every element outside the card panel, by a stable id, with its box. Fixed-position furniture
 *  is skipped: the toast stack a receipt posts to is `position: fixed`, so it is over the page
 *  rather than in it, and a receipt arriving is the whole point of a press this sweep covers. */
export async function outsideThePanel(page: Page): Promise<Record<string, string>> {
  return await page.evaluate(() => {
    const out: Record<string, string> = {}
    /* A COUNTER RESTARTING AT ZERO EACH SWEEP HANDS AN ID TWICE. The second sweep numbers the
       elements it has to stamp from 0 again, so a node created by the press collides with one
       the first sweep had already stamped, and the report pairs two unrelated elements. */
    const stamp = () => `n${Math.random().toString(36).slice(2)}`
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      if (el.closest('.browse-card') !== null) continue
      let fixed = false
      for (let a: HTMLElement | null = el; a !== null && a !== document.body; a = a.parentElement) {
        if (getComputedStyle(a).position === 'fixed') {
          fixed = true
          break
        }
      }
      if (fixed) continue
      const r = el.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) continue
      if (el.dataset.stableId === undefined) el.dataset.stableId = stamp()
      const cls =
        typeof el.className === 'string' && el.className !== '' ? `.${el.className.trim().split(/\s+/)[0]}` : ''
      out[el.dataset.stableId] = `${el.tagName.toLowerCase()}${cls} @ ${Math.round(r.x)},${Math.round(r.y)} h${Math.round(r.height)}`
    }
    return out
  })
}

export function whatMoved(before: Record<string, string>, after: Record<string, string>): string[] {
  const moved: string[] = []
  for (const [id, was] of Object.entries(before)) {
    const now = after[id]
    if (now === undefined || now === was) continue
    moved.push(`${was}   ->   ${now}`)
  }
  return moved
}

/** `outsideThePanel`, held until two reads 75ms apart agree, or `tries` runs out. See the
 *  block comment above for the race this closes and why a real move still fails every time. */
export async function settled(page: Page, tries = 40): Promise<Record<string, string>> {
  let last = await outsideThePanel(page)
  for (let i = 0; i < tries; i += 1) {
    await page.waitForTimeout(75)
    const next = await outsideThePanel(page)
    if (JSON.stringify(next) === JSON.stringify(last)) return next
    last = next
  }
  return last
}
