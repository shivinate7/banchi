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
