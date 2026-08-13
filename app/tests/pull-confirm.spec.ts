import { test, expect, type Locator, type Page } from '@playwright/test'

/* The first rows of docs/DESIGN.md's Fulfillment constraints table, as assertions.
 *
 * That table opens with the reason these exist: "The agent cannot see its own output, so
 * these are Playwright assertions, not prose." Step 6 builds one component, so this file
 * covers the constraints that component carries and no others. The rest — 32px position
 * labels, the 320px photo short edge, the banned-word list, the undo window, no route to
 * a destructive action — arrive with the views that carry them at step 7.
 *
 * Every number here is quoted from that table. None is computed from the tokens, and none
 * is copied from the sheet: a floor that reads its value from the thing it is checking
 * checks nothing.
 */

const HEIGHT_FLOOR = 44 // "Tap targets  >= 44 x 44 px"
const GAP_FLOOR = 12 // "...  >= 12px apart"
const BODY_FLOOR = 20 // "Body text  font-size >= 20px on every text node in the view"
const CONTRAST_FLOOR = 7 // "Contrast  >= 7:1 for body text (WCAG AAA)"

/** Every state the gallery renders, by its data-specimen name. */
const STATES = ['default', 'pressed', 'disabled', 'with-key'] as const

type Rgb = { r: number; g: number; b: number; a: number }

function parseRgb(value: string): Rgb {
  const match = /rgba?\(([^)]+)\)/.exec(value)
  if (match === null) throw new Error(`not an rgb colour: ${value}`)
  const group = match[1]
  if (group === undefined) throw new Error(`not an rgb colour: ${value}`)
  const parts = group.split(',').map((part) => Number(part.trim()))
  const [r, g, b, a] = parts
  if (r === undefined || g === undefined || b === undefined) {
    throw new Error(`not an rgb colour: ${value}`)
  }
  return { r, g, b, a: a ?? 1 }
}

/** WCAG 2.1 relative luminance. */
function luminance({ r, g, b }: Rgb): number {
  const channel = (raw: number) => {
    const c = raw / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrastRatio(one: Rgb, two: Rgb): number {
  const a = luminance(one)
  const b = luminance(two)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
}

function styleOf(target: Locator, property: string): Promise<string> {
  return target.evaluate(
    (node, prop) => window.getComputedStyle(node).getPropertyValue(prop),
    property,
  )
}

function buttonFor(page: Page, state: string): Locator {
  return page.locator(`[data-specimen="${state}"] .pull-confirm`)
}

/* The gallery's own route. At step 6 it was the whole app and answered at '/', which is why
 * this file used to navigate there; step 7a mounted the capture screen at the root and moved
 * the specimens to their own hash route. Nothing in the typecheck, the lint or the harness
 * can see that move — the first symptom would have been every test below failing in this
 * hook, on the run after the one that broke it.
 *
 * The hash form is what App.tsx routes on, so it must survive here verbatim: a path-style
 * '/gallery' would be served index.html by Vite, mount the app with an empty hash, and
 * render the capture screen — a passing navigation to the wrong view, which is the failure
 * this constant exists to make impossible to reintroduce quietly.
 */
const GALLERY = '/#/gallery'

test.beforeEach(async ({ page }) => {
  await page.goto(GALLERY)
  await expect(buttonFor(page, 'default')).toBeVisible()
})

for (const state of STATES) {
  test(`${state}: tap target is at least ${HEIGHT_FLOOR}x${HEIGHT_FLOOR}px`, async ({ page }) => {
    const box = await buttonFor(page, state).boundingBox()
    expect(box, 'the button has no layout box').not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(HEIGHT_FLOOR)
    expect(box!.width).toBeGreaterThanOrEqual(HEIGHT_FLOOR)
  })

  test(`${state}: label is at least ${BODY_FLOOR}px`, async ({ page }) => {
    const size = await styleOf(buttonFor(page, state), 'font-size')
    expect(Number.parseFloat(size)).toBeGreaterThanOrEqual(BODY_FLOOR)
  })

  test(`${state}: label on fill clears ${CONTRAST_FLOOR}:1`, async ({ page }) => {
    const button = buttonFor(page, state)
    const fill = parseRgb(await styleOf(button, 'background-color'))
    const label = parseRgb(await styleOf(button, 'color'))

    // A transparent fill would make the ratio below meaningless — and it is exactly what
    // a stylesheet that failed to load looks like. Assert the fill is really there first.
    expect(fill.a, 'the fill is not opaque, so the measured ratio is not the one on screen')
      .toBe(1)
    expect(label.a).toBe(1)

    expect(contrastRatio(fill, label)).toBeGreaterThanOrEqual(CONTRAST_FLOOR)
  })
}

test(`adjacent tap targets are at least ${GAP_FLOOR}px apart`, async ({ page }) => {
  // The gallery stacks its specimens, so this measures the vertical gaps. The horizontal
  // case has no component to measure yet — step 7 is where two targets first sit side by
  // side, and this test should grow a case for it then.
  const boxes = await Promise.all(
    STATES.map((state) => buttonFor(page, state).boundingBox()),
  )

  for (const [index, box] of boxes.entries()) {
    expect(box, `${STATES[index]} has no layout box`).not.toBeNull()
  }

  for (let index = 1; index < boxes.length; index += 1) {
    const previous = boxes[index - 1]!
    const current = boxes[index]!
    const gap = current.y - (previous.y + previous.height)
    expect(gap, `${STATES[index - 1]} -> ${STATES[index]}`).toBeGreaterThanOrEqual(GAP_FLOOR)
  }
})

test('the key hint is owner-side only, and absent by default', async ({ page }) => {
  // docs/DESIGN.md: "Every choice shows its key ... The Fulfiller's screens are touch and
  // show none." docs/design-refs/locked.html draws the chip on all three pull-confirm
  // states, which is the sheet being stale — docs/design-refs/README.md gives the doc
  // priority. This asserts the direction that disagreement was resolved in.
  await expect(buttonFor(page, 'default').locator('kbd')).toHaveCount(0)
  await expect(buttonFor(page, 'with-key').locator('kbd')).toHaveCount(1)
})
