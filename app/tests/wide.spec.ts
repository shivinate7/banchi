import { test, expect, type Page } from '@playwright/test'
import { routesFromNav } from './routes'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE OWNER'S SCREENS ABOVE THE DESK, WHICH NOTHING IN THIS SUITE HAD EVER LOOKED AT.
 *
 * `playwright.config.ts` runs one chromium project on `devices['Desktop Chrome']` — a 1280x720
 * baseline — and every deviation in this directory is a `page.setViewportSize` inside a test,
 * "because the viewport is the thing under test" (gallery.spec.ts). Ten cases set 1440x900 and
 * NOTHING RAN ABOVE IT. `docs/DESIGN.md` says the build was walked at 390, 820 and 1440;
 * `phone.spec.ts` reads the first, and nothing read anything above the third — so `.bn-page`'s
 * own cap, the single most consequential layout rule in the product, had never been rendered at
 * a width where it bites. D123 is the entry.
 *
 * WHAT THAT COST, MEASURED BEFORE THIS FILE EXISTED. At a 1920 viewport with the sidebar open,
 * `#/pricing`'s card-identity cell was 924px wide — nine of the row's ten tracks are fixed, so
 * every pixel the page gained landed in that one cell — while the price field it decides was
 * 68px at the far end of that gap. At 2560 the widest prose line in the product was 950px, in a
 * notice that carried no measure at all.
 *
 * THREE WIDTHS, EACH ANSWERING A DIFFERENT QUESTION.
 *   1440  the owner's Mac, and the width the whole build was verified at by eye.
 *   1920  the ordinary external monitor, and the first width where `.bn-page`'s cap can bite
 *         once the 236px sidebar is taken off it.
 *   2560  where the cap has to be doing all the work.
 *
 * AND A FOURTH DIMENSION THAT IS NOT A WIDTH. `.bn-shell[data-rail='true']` collapses the
 * sidebar 236 -> 64, so at ONE viewport a screen is drawn in two columns 172px apart — wider
 * than the gap between two ladder steps. Every case runs in both states, driven off
 * `banchi.rail` in an init script rather than off the hotkey, because a keypress is a race and
 * a stored preference is read before first paint (`App.tsx:readRail`).
 *
 * IT ASSERTS THE RULE, NEVER THE ROSTER — `cursor.spec.ts`'s sentence, and why this file takes
 * its routes from the same harvest that file does rather than typing them.
 */

/* NOTHING HERE MAY REACH THE CAPTURE SERVER. Above every hook, which `make docs-audit`'s
   `spec seal` row checks. */
sealEveryTest({ store: true, cards: 122 })

/* The widest a screen may be. `--bn-page-w` is 1600px and `.bn-page` is border-box, so no
   content box can exceed it; a screen that does has escaped the kit's cap entirely. */
const PAGE_CEILING = 1600

/* THE PROSE FLOOR IS THE KIT'S OWN CAP PLUS SLACK, NOT A ROUND NUMBER. `.bn-lede` is 72ch at
   `--bn-fs-lg`, which renders at 632px — so anything past 720 is a run with no measure rather
   than a lede doing its job. The one that was over it, `.orders-backlog p` at 950px, is the
   defect this floor was written from. */
const PROSE_CEILING = 720

const RAILS = [
  { label: 'sidebar', stored: 'wide' },
  { label: 'rail', stored: 'rail' },
] as const

/** The shell in one of its two desktop states, before first paint.
 *
 *  SEEDED RATHER THAN PRESSED, for `orders.spec.ts:remember`'s reason and one of its own.
 *  `App.tsx:readRail` reads `banchi.rail` ONCE, in a `useState` initialiser, so the state is
 *  decided before the first frame and a `⌘.` afterwards is a different thing being tested —
 *  a transition, not a layout. And a keypress is a race against the same first paint every
 *  assertion below is measuring. */
async function withRail(page: Page, stored: string, width: number): Promise<void> {
  await page.addInitScript((value) => {
    try {
      /* eslint-disable-next-line no-restricted-syntax -- WRITING THE SHELL'S OWN DEVICE KEY to
         put it in a known state before first paint, not introducing one. `banchi.rail` already
         lives in `app/src/deviceMemory.ts` where D27's argument for it is, which is what the
         rule exists to force; this only reads that state INTO a test. The alternative is
         pressing `⌘.` and racing the paint this file measures. `orders.spec.ts:remember` is
         the other call of this shape and carries the same argument. */
      window.localStorage.setItem('banchi.rail', value)
    } catch {
      /* a browser refusing storage reads as never chosen, which is the sidebar — a real state
         and the default one, so the sweep is still measuring something */
    }
  }, stored)
  await page.setViewportSize({ width, height: 1000 })
}

/** Every visible prose run on the page, and how wide its FIRST LINE actually inked. */
async function proseLines(page: Page): Promise<{ w: number; cls: string; text: string }[]> {
  return page.evaluate(() => {
    const root = document.querySelector('main')
    if (root === null) return []
    const out: { w: number; cls: string; text: string }[] = []
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    let node = walk.nextNode()
    while (node !== null) {
      const text = (node.textContent ?? '').trim()
      const parent = node.parentElement
      /* PROSE, NOT EVERY STRING. A label, a SKU and a figure are short by design and a wide
         cell is not a defect for them — this floor is about a SENTENCE, which is the thing a
         measure exists for. Sixty characters and ten words is the line between the two. */
      if (text.length >= 60 && text.split(/\s+/).length >= 10 && parent?.checkVisibility()) {
        const range = document.createRange()
        range.selectNodeContents(node)
        /* THE FIRST LINE BOX, NOT THE ELEMENT. A box tells you the column it was given; the
           line tells you how far the eye actually has to travel back to find the next one. */
        const first = range.getClientRects()[0]
        if (first !== undefined) {
          out.push({
            w: Math.round(first.width),
            cls: (parent.className || '').toString().slice(0, 40),
            text: text.slice(0, 60),
          })
        }
      }
      node = walk.nextNode()
    }
    return out
  })
}

test('every owner screen is capped above the desk, in both rail states', async ({ page }) => {
  await withRail(page, 'wide', 1920)
  const routes = await routesFromNav(page)
  let measured = 0

  for (const width of [1440, 1920, 2560]) {
    for (const rail of RAILS) {
      await withRail(page, rail.stored, width)

      for (const route of routes) {
        const where = `${route} at ${width} (${rail.label})`
        await page.goto(`/${route}`)
        await settleFonts(page)
        /* Arrival first, THEN which screen — `toHaveCount(0)` is satisfied by an element that
           has not rendered yet, which is `cursor.spec.ts`'s hard-won ordering. */
        await expect(page.locator('main').first(), `${where}: drew no <main>`).toBeVisible()
        await expect(
          page.locator('main.no-such-view'),
          `${where}: is in the nav and resolves to nothing`,
        ).toHaveCount(0)

        const shape = await page.evaluate(() => {
          /* THE CONTENT COLUMN, NOT THE SCREEN'S GROUND. `main.fulfillment` is deliberately
             full-bleed — it paints `.ff-glow` edge to edge — and its cap lives on `.ff-column`,
             a child. Measuring `main` everywhere would call that a defect; measuring only
             `.bn-page` would let a screen with no cap anywhere pass by not having one. So this
             names the two shapes a capped column takes in this product, and a screen that grows
             a third has to say so here. A `<Page width={false}>` (D275's amendment, the
             Fulfiller's screen) opts out of the kit's cap and is full-bleed on purpose, so it is
             skipped: the capped column inside it is what this measures. */
          const main = document.querySelector('.bn-page:not([data-bn-page-width="auto"]), .ff-column')
          return {
            pageW: main === null ? null : Math.round(main.getBoundingClientRect().width),
            overflow:
              document.documentElement.scrollWidth - document.documentElement.clientWidth,
          }
        })
        expect(shape.pageW, `${where}: no capped column (.bn-page / .ff-column) to measure`)
          .not.toBeNull()
        expect(
          shape.pageW as number,
          `${where}: the content box is ${shape.pageW}px — past --bn-page-w. ` +
            `Something is drawing outside the kit's cap.`,
        ).toBeLessThanOrEqual(PAGE_CEILING)
        expect(shape.overflow, `${where}: the page scrolls sideways by ${shape.overflow}px`).toBe(0)
        measured += 1
      }
    }
  }

  /* THE SWEEP IS FLOORED, because a harvest that returned nothing would make every assertion
     above vacuous and this file green forever. Eleven routes x three widths x two rail states
     is 66; 40 sits well below that and well above anything a broken harvest could produce. */
  expect(measured, 'the sweep measured almost nothing — did the roster harvest break?')
    .toBeGreaterThan(40)
})

test('no sentence outruns its measure at 2560', async ({ page }) => {
  await withRail(page, 'rail', 2560)
  const routes = await routesFromNav(page)
  const over: string[] = []
  let runs = 0

  for (const route of routes) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    for (const line of await proseLines(page)) {
      runs += 1
      if (line.w > PROSE_CEILING) {
        over.push(`${route} ${line.w}px .${line.cls || '(no class)'} — “${line.text}…”`)
      }
    }
  }

  /* ANTI-VACUITY: a store that renders no sentences measures no measures. */
  expect(runs, 'no prose was found on any screen, so nothing was measured').toBeGreaterThan(8)
  expect(
    over,
    `a sentence is wider than ${PROSE_CEILING}px, which is past the kit's own 72ch lede.\n` +
      `Give it a measure — \`.bn-lede\`, a \`ch\` cap, or a --bn-page-max on the screen:\n  ` +
      over.join('\n  '),
  ).toEqual([])
})
