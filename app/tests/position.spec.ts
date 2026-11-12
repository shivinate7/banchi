// Protects: The chip a card's position bar marks is the section its heading names, even when the box's section list was read one slot out of step with the card's own place (a sale closed the slots up behind it).
// Governs: D155 (the section ruler leads the box: the box strip's chip and its caret sit on the chip the card is in), `app/src/position.ts` `spansOf`
import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { place } from './routeFixtures'
import type { Place, SectionDetail } from '../src/types'

/* `spansOf` lives in `position.ts`, which imports `server.ts`, and `server.ts` reads
 * `import.meta.env` at load. The unit tier has no Vite, so it cannot load that module. This tier
 * does: the dev server serves `/src/position.ts` to the page, and the case calls it there. */
sealEveryTest()

const POSITION_MODULE = '/src/position.ts'

type SpanRead = { section: number; current: boolean }

async function spansOf(page: Page, at: Place, sections: SectionDetail[]): Promise<SpanRead[]> {
  /* `__BN_DEMO__` is a build-time constant that `server.ts` reads bare. The dev graph this page
     loads does not fold it, so the page defines it as the ordinary build does: not the demo. */
  await page.addInitScript(() => {
    ;(globalThis as { __BN_DEMO__?: boolean }).__BN_DEMO__ = false
  })
  await page.goto(POSITION_MODULE)
  return page.evaluate(
    async ({ at, sections, path }) => {
      const mod = await import(/* @vite-ignore */ path)
      return (mod.spansOf(at, sections) as SpanRead[]).map((span) => ({ section: span.section, current: span.current }))
    },
    { at, sections, path: POSITION_MODULE },
  )
}

const currentSections = (spans: SpanRead[]) => spans.filter((span) => span.current).map((span) => span.section)

/* A 133-card box in three sections. Every case below reads these or the agreeing set. */
const AGREEING: SectionDetail[] = [
  { section: 11, start: 100, end: 110, count: 11, name: null },
  { section: 12, start: 111, end: 125, count: 15, name: null },
  { section: 13, start: 126, end: 133, count: 8, name: null },
]

/* The same box one slot out: section 11 is read as ending at 111 and section 12 as starting at 112,
   so slot 111 falls inside section 11's bounds while the place still says section 12. */
const SHIFTED: SectionDetail[] = [
  { section: 11, start: 100, end: 111, count: 12, name: null },
  { section: 12, start: 112, end: 125, count: 14, name: null },
  { section: 13, start: 126, end: 133, count: 8, name: null },
]

test("the current chip is the heading's section when the section read is one slot behind the place", async ({ page }) => {
  const spans = await spansOf(page, place({ section: 12, section_start: 111, section_end: 125, slot: 111, card: 1 }), SHIFTED)

  /* Scope first: the three chips tile the box as the read states them. */
  expect(spans.map((span) => span.section)).toEqual([11, 12, 13])
  expect(currentSections(spans)).toEqual([12])
})

test("the current chip is the heading's section when the section read agrees with the place", async ({ page }) => {
  const spans = await spansOf(page, place({ section: 12, section_start: 111, section_end: 125, slot: 115, card: 5 }), AGREEING)

  expect(spans.map((span) => span.section)).toEqual([11, 12, 13])
  expect(currentSections(spans)).toEqual([12])
})

test('a place with no section marks the chip its slot falls in', async ({ page }) => {
  const spans = await spansOf(page, place({ section: null, section_start: 111, section_end: 125, slot: 115, card: null }), AGREEING)

  expect(spans.map((span) => span.section)).toEqual([11, 12, 13])
  expect(currentSections(spans)).toEqual([12])
})
