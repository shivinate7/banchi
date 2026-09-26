import { test, expect, type Page, type Route } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* WHERE A CARD IS, SAID ONE WAY ON EVERY SCREEN (the locating lane, 2026-09-23).
 *
 * The owner's rulings this spec reads back off the rendered page:
 *   - A box is shown by its NAME only; its number never reaches a screen
 *     (D259).
 *   - The card number counts within its section, card 1 is at the FAR BACK, and the ruler marks
 *     the exact card, in section numbers, with the sections before and after
 *     (D260).
 *   - A departed card keeps the place it left, drawn with a mark, never a word; it speaks in the
 *     past tense.
 *   - Review's place pill opens the card, and a screen reader hears it as a sentence. It shows
 *     which end is the back and the card's neighbours (UX-228).
 *   - The neighbour sentence says back and front ("It sits in front of X and behind Y."), and an
 *     unread neighbour counts, said in words (UX-186, LOC-28).
 *   - A place link pressed while Inventory is open walks to that card (a hash change, no mount).
 *
 * THE FIXTURE IS THE SERVER'S OWN ARITHMETIC, written out. One box of twelve slots, dividers at
 * indices 1, 5 and 9 (three sections), and index 6 sold. So index 7 is the second card of section
 * 2, and index 6, which left, names the place it left: section 2, card 2. The two strings are the
 * same on purpose; only the mark tells them apart. */

sealEveryTest({ store: true })

const SIZES = [
  { width: 1440, height: 900 },
  { width: 820, height: 1180 },
  { width: 720, height: 900 },
  { width: 390, height: 844 },
] as const
const THEMES = ['light', 'dark'] as const

const BOX = 1
const DIVIDERS = [1, 5, 9]
const SOLD = new Set([6])
const INDICES = Array.from({ length: 12 }, (_, i) => i + 1)
const OCCUPIED = INDICES.filter((i) => !SOLD.has(i))
const SECTION_NAMES: Record<number, string | null> = {
  1: null,
  2: 'Uncommons',
  3: 'Rares from the long box on the top shelf',
}

/** `pipeline/join.py:Position`, in the fixture: section by index, the slot counted over the cards
 *  on hand, and a departed card's number the one it would take going back. */
function placeOf(index: number, boxName: string) {
  const section = DIVIDERS.filter((start) => start <= index).length
  const divider = (start: number) => OCCUPIED.filter((i) => i < start).length + 1
  const sectionStart = divider(DIVIDERS[section - 1] as number)
  const nextDivider = DIVIDERS[section]
  const sectionEnd = nextDivider === undefined ? OCCUPIED.length : divider(nextDivider) - 1
  const gone = SOLD.has(index)
  const slot = gone ? null : OCCUPIED.indexOf(index) + 1
  const at = gone ? OCCUPIED.filter((i) => i < index).length + 1 : (slot as number)
  const card = at - sectionStart + 1
  const neighbor = (i: number | undefined) =>
    i === undefined ? null : { index: i, slot: OCCUPIED.indexOf(i) + 1, name: NAMES[i] ?? null, unread: 0 }
  const before = OCCUPIED.filter((i) => i < index)
  const after = OCCUPIED.filter((i) => i > index)
  return {
    located: true,
    label: `${boxName}, Section ${section}, Card ${card}`,
    box: BOX,
    index,
    slot,
    section,
    card: gone ? null : card,
    box_name: boxName,
    section_name: SECTION_NAMES[section] ?? null,
    section_start: sectionStart,
    section_end: sectionEnd,
    box_total: OCCUPIED.length,
    fraction: slot === null ? null : (slot - 1) / OCCUPIED.length,
    neighbors: { prev: neighbor(before[before.length - 1]), next: neighbor(after[0]) },
    section_gaps: 0,
  }
}

const NAMES: Record<number, string> = {
  1: 'Piercing Light', 2: 'Gentle Gemdragon', 3: 'Bellows Breath', 4: 'Sacred Shears',
  5: 'Towering Combatant', 6: 'Double Trouble', 7: 'Double Trouble', 8: 'Relentless Pursuit',
  9: 'Punch First', 10: 'Draven, Audacious', 11: 'Hextech Anomaly', 12: 'Spectral Centaur',
}
/* Index 6 (sold) and index 7 are two copies of one card, so the copies list draws both. */
const SKU: Record<number, string> = Object.fromEntries(INDICES.map((i) => [i, i === 6 ? 'sku-7' : `sku-${i}`]))

function row(index: number, boxName: string) {
  const place = placeOf(index, boxName)
  return {
    box: BOX,
    index,
    label: place.label,
    section: place.section,
    card: place.card ?? undefined,
    place,
    photo: `photos/${BOX}/${index}.jpg`,
    set_hint: 'OGN',
    metadata_finish: 'normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-09-01T12:00:00+00:00',
    capture_id: `cap-${index}`,
    cid: `cid-${index}`,
    name: NAMES[index] ?? null,
    number: '090',
    printed_total: '221',
    number_display: '090/221',
    confidence: null,
    sku: SKU[index] ?? null,
    condition: 'Near Mint',
    state: SOLD.has(index) ? 'sold' : 'identified',
    state_at: '2026-09-01T12:00:00+00:00',
    retire_reason: null,
  }
}

const json = (route: Route, body: unknown) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

/** Stub the one box, its cards and the search the card pane asks. Newer routes win over the seal's.
 *  `edit` changes the rows before any route answers, so the walk and the copies list agree. */
async function stubBox(
  page: Page,
  boxName: string,
  edit?: (cards: Record<string, ReturnType<typeof row>>) => void,
): Promise<void> {
  const cards = Object.fromEntries(INDICES.map((i) => [`${BOX}/${i}`, row(i, boxName)]))
  edit?.(cards)
  await page.route(/\/boxes(\?.*)?$/, (route) =>
    json(route, {
      boxes: [
        {
          box: BOX,
          bid: 11,
          name: boxName,
          sections: DIVIDERS,
          state: 'open',
          capacity: null,
          fill: 12,
          next_index: 13,
          cards: 12,
          on_hand: OCCUPIED.length,
          sold: SOLD.size,
          retired: 0,
          moved: 0,
          listed: 0,
          sections_detail: [1, 2, 3].map((section) => {
            const first = placeOf(DIVIDERS[section - 1] as number, boxName)
            return {
              section,
              start: first.section_start,
              end: first.section_end,
              count: first.section_end - first.section_start + 1,
              name: SECTION_NAMES[section] ?? null,
            }
          }),
        },
      ],
    }),
  )
  await page.route(/\/inventory\/1$/, (route) => json(route, { version: 2, cards, listings: {} }))
  await page.route(/\/search\?/, (route) => {
    const q = new URL(route.request().url()).searchParams.get('q') ?? ''
    const skus = [...new Set(Object.values(cards).filter((c) => c.sku === q || c.name === q).map((c) => c.sku))]
    return json(route, {
      query: q,
      groups: skus.map((sku) => {
        const held = Object.entries(cards).filter(([, c]) => c.sku === sku)
        return {
          sku,
          names: [...new Set(held.map(([, c]) => c.name))],
          number: '090',
          printed_total: '221',
          set_hint: 'OGN',
          condition: 'Near Mint',
          listed: { pushed: 0, staged: 0, live: 0 },
          sold_here: 0,
          live_as_of: null,
          on_hand: held.filter(([, c]) => c.state !== 'sold').length,
          listable: 1,
          copies: held.map(([key, c]) => ({
            key,
            state: c.state,
            state_at: c.state_at,
            has_photo: true,
            place: c.place,
            cid: c.cid,
          })),
        }
      }),
    })
  })
}

async function frame(page: Page, size: (typeof SIZES)[number], theme: (typeof THEMES)[number]) {
  await page.setViewportSize({ width: size.width, height: size.height })
  await page.emulateMedia({ colorScheme: theme })
  /* SOLD SHOWN, so the departed copy is on the list to be read. Seeded before first paint, the
     same call `inventory.spec.ts` makes for the same device key. */
  await page.addInitScript(() => {
    try {
      /* eslint-disable-next-line no-restricted-syntax -- seeding the walk's own device key into
         a known state before first paint, as `inventory.spec.ts` does. */
      window.localStorage.setItem('banchi.inventory.hide-sold', 'show')
    } catch {
      /* unreadable storage folds sold away, which the departed assertions below would name */
    }
  })
}

const NO_BOX_NUMBER = /\bBox\s+\d+\b|\bBOX\s+\d+\b/

for (const size of SIZES) {
  for (const theme of THEMES) {
    test(`Inventory at ${size.width} ${theme}: the place by name, card 1 at the back, the ruler on the exact card`, async ({ page }) => {
      await frame(page, size, theme)
      await stubBox(page, 'RB Origins')
      await page.goto(`/#/inventory?box=${BOX}&card=cid-7`)
      await settleFonts(page)

      /* THE DEEP LINK OPENS THE CARD, NOT THE BOX'S FIRST (LOC-12). */
      const current = page.locator('.card-locations-row.is-current')
      await expect(current).toBeVisible()
      const label = current.locator('.card-locations-identity')
      await expect(label).toHaveAttribute('aria-label', 'RB Origins, Section 2, Card 2')

      /* THE BOX IS NAMED, NEVER NUMBERED (D259). */
      const drawn = (await label.innerText()).replace(/\s+/g, ' ')
      expect(drawn).toContain('RB Origins')
      expect(drawn).not.toMatch(NO_BOX_NUMBER)
      expect(drawn).not.toMatch(/[·•]/)

      /* ONE COUNT PER INSTRUMENT, the section's: the ruler's ends are 1 and the section's size. */
      const bar = current.locator('.position-bar')
      await expect(bar.locator('.position-bar-edge-start')).toHaveText('1')
      await expect(bar.locator('.position-bar-edge-end')).toHaveText('3')
      /* THE CARD RULER'S OWN CAPTION IS OMITTED HERE, NOT DRAWN EMPTY (the owner's Direction-B
         build, 2026-09-25): `CardLocations.tsx`'s `RowIdentity` now states `Card 2 of 3` once,
         on the header, and this section carries no name, so there is nothing left for this
         line to say that is not said elsewhere — a dead line would be exactly the "no dead
         gaps" the owner asked against. The pin above still marks the exact card. */
      await expect(bar.locator('.position-bar-text-section')).toHaveCount(0)

      /* CARD 1 IS AT THE BACK, ON EACH RULER (the owner's ruling, 2026-09-25: "Keep it on each
         ruler" — D260 stands). The section ruler's own pair lives in `.position-bar-ends-row`;
         the card ruler's own lives in `.position-bar-zoom-ends`, added this round so both
         instruments orient on their own rather than sharing one row between them. */
      const sectionEnds = bar.locator('.position-bar-ends-row')
      const back = await sectionEnds.locator('.position-bar-end-back').boundingBox()
      const front = await sectionEnds.locator('.position-bar-end-front').boundingBox()
      expect(back && front && back.x < front.x, 'back is drawn before front').toBe(true)

      const cardEnds = bar.locator('.position-bar-zoom-ends')
      const cardBack = await cardEnds.locator('.position-bar-end-back').boundingBox()
      const cardFront = await cardEnds.locator('.position-bar-end-front').boundingBox()
      expect(cardBack && cardFront && cardBack.x < cardFront.x, 'the card ruler keeps its own back before front').toBe(true)

      /* THE MARK IS ON THE EXACT CARD (LOC-05): the pin's centre is inside card 2's own cell. */
      const cell = await bar.locator('.position-bar-cell').boundingBox()
      const pin = await bar.locator('.position-bar-sectiontrack .position-bar-marker').boundingBox()
      expect(cell && pin, 'the cell and the pin are drawn').toBeTruthy()
      if (cell && pin) {
        const center = pin.x + pin.width / 2
        expect(center).toBeGreaterThan(cell.x)
        expect(center).toBeLessThan(cell.x + cell.width)
      }

      /* THE SECTIONS BEFORE AND AFTER, numbered, with this one marked. */
      await expect(bar.locator('.position-bar-segment-num')).toHaveText(['1', '2', '3'])
      await expect(bar.locator('.position-bar-here .position-bar-segment-num')).toHaveText('2')

      /* NEIGHBOURS FROM BACK TO FRONT, this card between them, and the sentence says which is
         which (UX-186): index 5 is toward the back, index 8 toward the front. */
      await expect(current.locator('.nb')).toHaveAttribute(
        'aria-label',
        'It sits in front of Towering Combatant and behind Relentless Pursuit.',
      )
      await expect(current.locator('.nb-row')).toHaveCount(3)
      expect(await current.locator('.nb-row').evaluateAll((rows) => rows.map((r) => r.getAttribute('data-side')))).toEqual([
        'back',
        'this',
        'front',
      ])

      /* THE DEPARTED COPY names the place it left, marked and in the past tense, never worded. */
      const gone = page.locator('.card-locations-row.is-gone .card-locations-identity')
      await expect(gone).toHaveAttribute('data-departed', 'true')
      await expect(gone).toHaveAttribute('aria-label', 'Was at RB Origins, Section 2, Card 2')
      const strike = await gone.locator('.card-locations-identity-num').evaluate((el) => getComputedStyle(el).textDecorationLine)
      expect(strike).toContain('line-through')
      expect((await gone.innerText()).toLowerCase()).not.toMatch(/departed|sold|\bb\d+ #\d+/)
      await expect(page.locator('.card-locations-row.is-gone .nb')).toHaveAttribute('aria-label', /^It was in front of /)

      /* A SECTION TITLE KEEPS ITS NAME WHOLE AND SAYS ITS COUNT ONCE (LOC-21). */
      /* The walk list is on the page beside the card from 820 up; below that it is in the rail sheet. */
      if (size.width >= 820) {
        const heads = page.locator('.browse-secthead')
        const count = await heads.count()
        expect(count).toBeGreaterThan(0)
        for (let at = 0; at < count; at++) {
          const head = heads.nth(at).locator('.browse-secttitle-head')
          const cut = await head.evaluate((el) => el.scrollWidth > el.clientWidth + 1)
          expect(cut, `section title ${at} is whole`).toBe(false)
          await expect(heads.nth(at).locator('.browse-secttitle-count')).toHaveClass(/bn-sr/)
        }
      }
    })
  }
}

for (const size of SIZES) {
  for (const theme of THEMES) {
    test(`Review at ${size.width} ${theme}: the pill says the place as a sentence and opens the card`, async ({ page }) => {
      await frame(page, size, theme)
      await stubBox(page, 'Box 1')
      const place = placeOf(10, 'Box 1')
      await page.route(/\/queues$/, (route) =>
        json(route, {
          review: [
            {
              position: '1/10',
              box: BOX,
              index: 10,
              label: place.label,
              photo: 'photos/1/10.jpg',
              read: { name: 'Draven, Audacious', number: '148', printed_total: '221', set_hint: 'SFD' },
              confidence: null,
              reason: 'no_catalog_row',
              candidates: [],
              first_seen: '2026-09-01T12:00:00+00:00',
              market: null,
              cleared_by_human: false,
              place,
              cid: 'cid-10',
            },
          ],
          parked: [],
        }),
      )
      await page.goto('/#/review')
      await settleFonts(page)

      const pill = page.locator('a.review-caption-link').first()
      await expect(pill).toBeVisible()
      await expect(pill).toHaveAttribute('href', `#/inventory?box=${BOX}&card=cid-10`)
      await expect(pill.locator('.position-run')).toHaveAttribute('aria-label', 'Box 1, Section 3, Card 2')
      expect(await pill.innerText()).not.toMatch(/[·•]/)
      const height = (await pill.boundingBox())?.height ?? 0
      expect(height, 'the pill is a press, at the kit floor').toBeGreaterThanOrEqual(40)

      /* THE PILL SHOWS WHICH END IS THE BACK, AND ITS NEIGHBOURS (UX-228): back, the card toward
         the back (index 9), this card, the card toward the front (index 11), front. In that order
         on screen, left to right, and the sentence a screen reader hears says the same. */
      const order = pill.locator('.review-caption-order')
      await expect(order).toBeVisible()
      const parts = await order.locator(':scope > span').evaluateAll((els) =>
        els.map((el) => {
          const box = el.getBoundingClientRect()
          return { text: (el.textContent ?? '').trim(), x: box.x, y: box.y + box.height / 2 }
        }),
      )
      expect(parts.map((part) => part.text)).toEqual(['back', 'Punch First', 'this card', 'Hextech Anomaly', 'front'])
      /* In READING order, by each part's vertical centre: each part is right of the one before on
         its line, or on a later line (the line wraps between its parts, never inside one). */
      const inReadingOrder = parts.every((part, at) => {
        const before = parts[at - 1]
        if (before === undefined) return true
        return part.y > before.y + 4 || (Math.abs(part.y - before.y) <= 4 && part.x > before.x)
      })
      expect(inReadingOrder, 'drawn back to front').toBe(true)
      await expect(pill.locator('.bn-sr')).toHaveText('It sits in front of Punch First and behind Hextech Anomaly.')
      /* The pill stays inside the page at every width: no sideways scroll at 390. */
      const box = await pill.boundingBox()
      expect(box !== null && box.x + box.width <= size.width, 'the pill fits the width').toBe(true)
    })
  }
}

test('an unread neighbour is said in words on the ladder, never as a figure (LOC-28)', async ({ page }) => {
  await frame(page, SIZES[0], 'light')
  /* The card toward the front of index 7 has not been read, and neither has the one after it:
     the neighbour is "2 unread cards", the owner's words (amends D116). */
  await stubBox(page, 'RB Origins', (cards) => {
    const seven = cards[`${BOX}/7`]
    if (seven === undefined) return
    seven.place.neighbors = {
      prev: seven.place.neighbors.prev,
      next: { index: 8, slot: 7, name: null, unread: 2 },
    }
  })
  await page.goto(`/#/inventory?box=${BOX}&card=cid-7`)
  await settleFonts(page)

  const current = page.locator('.card-locations-row.is-current')
  await expect(current.locator('.nb-row[data-side="front"] .nb-unread')).toHaveText('2 unread cards')
  await expect(current.locator('.nb')).toHaveAttribute(
    'aria-label',
    'It sits in front of Towering Combatant and behind 2 unread cards.',
  )
})

test('a place link pressed while Inventory is open walks to that card', async ({ page }) => {
  await frame(page, SIZES[0], 'light')
  await stubBox(page, 'RB Origins')
  await page.goto(`/#/inventory?box=${BOX}&card=cid-7`)
  await settleFonts(page)
  const label = page.locator('.card-locations-row.is-current .card-locations-identity')
  await expect(label).toHaveAttribute('aria-label', 'RB Origins, Section 2, Card 2')

  /* A SECOND LINK, NO NEW MOUNT: the hash changes inside `#/inventory` (Review's pill, a copy
     link). The walk must follow it, not stay on the card the first link opened. */
  await page.evaluate(() => {
    window.location.hash = '#/inventory?box=1&card=cid-11'
  })
  await expect(label).toHaveAttribute('aria-label', 'RB Origins, Section 3, Card 3')
})
