// Protects: The Slabs screen draws one ledger of the owner's slabs, never shows a cert or the settings key, and answers every Card Ladder refusal in words.
// Governs: D320, D196, D218, D221, D275, D313
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Locator, type Page } from '@playwright/test'
import { CAPTURE_PORT } from '../devPort'
import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { scanMachineWords } from './machineWords'
import { scanMoneyFace } from './moneyFace'
import { setViewport } from './phoneSwitch'
import { SLAB_CERT, SLAB_SALE_PLATFORMS, severalSlabs, slabDetailOf, slabRefusal, slabRow, slabSnapshot } from './routeFixtures'
import type { SlabRow } from '../src/types'

/* THE SLABS SCREEN (D320, `docs/specs/my-slabs.md` 4.1, 4.7, 4.8, 4.9), WRITTEN BEFORE IT EXISTS.
 *
 * It reads the four slab routes of `server/slabs_routes.py` and no others, so every case here
 * stubs those four (`stubApi`) and counts what the screen sends. Nothing reaches the capture
 * server: the seal below names any read this file forgot.
 *
 * WHAT IS PINNED AND WHAT IS NOT. Exact text only where the spec pins it: "Slabs", "Add a Slab",
 * "No slabs yet", "No sales", the five confidence words, the buttons "Remove", "Undo", "Add", the
 * labels "Cert" and "Grader". Everything else is a property: a visible sentence, a count, an order,
 * a refusal with no Retry. The wording of a sentence the spec does not quote is the builder's.
 *
 * EVERY NEGATIVE CHECK IS PAIRED WITH A POSITIVE ONE FIRST. With no screen, "no cert on the page"
 * and "no Retry button" are true of a blank page. So each case waits for the thing it is about,
 * the rows, the dialog, the sentence, before it asserts an absence.
 *
 * THE SERVER'S REFUSALS ARE THE REAL ONES, copied from `server/slabs_routes.py`, including the two
 * that name the settings key. The screen must not repeat that key (spec 4.8), so the stub sends it.
 *
 * VIEWPORTS: 1440 and 820. The phone-width specs are off (DEBT77, `phoneSwitch.ts`). */
sealEveryTest()

/* ---------------------------------------------------------------------------- the wire */

type Reply = { status: number; body: unknown }
const ok = (body: unknown): Reply => ({ status: 200, body })
const refuse = (status: number, code: string, message: string): Reply => ({ status, body: slabRefusal(code, message) })

/* `server/slabs_routes.py`, word for word. */
const RATE_LIMITED = refuse(429, 'cardladder_rate_limited', 'Card Ladder asked us to slow down. Nothing was saved. Try again tomorrow.')
const TOKEN_MISSING = refuse(409, 'cardladder_token_missing', 'Card Ladder cannot be read yet. Add CARDLADDER_REFRESH_TOKEN to the settings file, then try again.')
const TOKEN_REJECTED = refuse(409, 'cardladder_token_rejected', 'Card Ladder did not accept the saved login. Copy CARDLADDER_REFRESH_TOKEN again, then try again.')
const SETTINGS_KEY = 'CARDLADDER_REFRESH_TOKEN'
const UNREADABLE = refuse(502, 'cardladder_unreadable', 'Card Ladder sent an answer this app could not read. Nothing was saved. Try again later.')
const CERT_NOT_FOUND = refuse(404, 'cert_not_found', 'Card Ladder has no slab with that cert number for that grader. Nothing was saved.')
const ADD_BUSY = refuse(409, 'slab_add_busy', 'A slab is being added right now. Wait for it to finish, then try again.')

/** A response the stub holds back until a case opens it, so a press is in flight while the case looks. */
class Gate {
  readonly opened: Promise<void>
  open: () => void = () => {}
  constructor() {
    this.opened = new Promise<void>((done) => (this.open = done))
  }
}

type Grader = 'psa' | 'beckett' | 'bgs' | 'bvg' | 'sgc' | 'cgc'
type Wire = {
  /** What `GET /slabs` sends. A remove and an add change it, as the store would. */
  rows: SlabRow[]
  /** Taken off the list, kept so an add of the same cert and grader is a restore, as the route says. */
  removed: SlabRow[]
  /** Slabs Card Ladder knows and the list does not hold yet: what an add can find. */
  catalog: SlabRow[]
  lists: number
  details: string[]
  posts: Array<{ cert: string; grader: string }>
  deletes: string[]
  listReply: (() => Reply) | null
  postReply: ((body: { cert: string; grader: string }) => Reply) | null
  /** What `GET /slabs/<grader>/<cert>` sends for a slab on the list; null is `slabDetailOf(row)`. */
  detailReply: ((row: SlabRow) => Reply) | null
  hold: { list: Gate | null; post: Gate | null; del: Gate | null; detail: Gate | null }
}

/** `server/slabs_routes.py`'s answer when Card Ladder fails inside an add: not a rate limit, not a login. */
const BAD_GATEWAY_SAID = 'Card Ladder could not be read just now. Nothing was saved. Try again later.'
const BAD_GATEWAY = refuse(502, 'cardladder_failed', BAD_GATEWAY_SAID)

/** `server/capture_server.py`'s answers when the inventory lock times out and when the store file cannot be read, word
 *  for word. One names two jobs of the Mac and the other names a file; neither is the owner's to read as a title. */
const STORE_BUSY_SAID = 'The inventory is being used by another job, most likely an identify or a send that is still running. Wait for it to finish, then try again.'
const STORE_BUSY = refuse(503, 'store_busy', STORE_BUSY_SAID)
const STORE_UNAVAILABLE_SAID = 'The store file store.sqlite is damaged and could not be read. Restore it from a backup.'
const STORE_UNAVAILABLE = refuse(503, 'store_unavailable', STORE_UNAVAILABLE_SAID)

/** Card Ladder's grader for each name `store/slabs.GRADERS` accepts. */
const CARD_LADDER: Record<Grader, string> = { psa: 'psa', beckett: 'beckett', bgs: 'beckett', bvg: 'beckett', sgc: 'sgc', cgc: 'cgc' }

const GENGAR = slabRow({
  cert: '55507733',
  grader: 'beckett',
  label: 'Gengar ex Phantasmal Flames Special Illustration Rare',
  grade: 'g9_5',
  added: '2026-10-22',
})
const UNLABELED_NEW = slabRow({
  cert: '33309944',
  grader: 'psa',
  label: null,
  grade: 'g8',
  added: '2026-10-22',
  snapshot: slabSnapshot({ cl_value: '61.00', cl_confidence: 3, estimated_value: '62.00', estimated_confidence: 3, last_sale_price: '60.00', last_sale_date: '2026-10-10', population: 77 }),
})

const live: Wire[] = []
function makeWire(over: Partial<Wire> = {}): Wire {
  const wire: Wire = {
    rows: severalSlabs(),
    removed: [],
    catalog: [GENGAR, UNLABELED_NEW],
    lists: 0,
    details: [],
    posts: [],
    deletes: [],
    listReply: null,
    postReply: null,
    detailReply: null,
    hold: { list: null, post: null, del: null, detail: null },
    ...over,
  }
  live.push(wire)
  return wire
}
/* A gate left shut would leave a route handler waiting past the case. */
test.afterEach(() => {
  for (const wire of live.splice(0)) for (const gate of Object.values(wire.hold)) gate?.open()
})

const labelOf = (row: SlabRow): string => row.label ?? `slab ${row.cert}`

/** `POST /slabs` as `_add` answers it: a slab off the list comes back "Restored", a new one is "Added". */
function addReply(wire: Wire, body: { cert: string; grader: string }): Reply {
  const grader = CARD_LADDER[body.grader as Grader] ?? body.grader
  const same = (row: SlabRow) => row.cert === body.cert && row.grader === grader
  const held = wire.rows.find(same)
  const back = wire.removed.find(same)
  const row = held ?? back ?? wire.catalog.find(same)
  if (row === undefined) return refuse(404, 'cert_not_found', 'Card Ladder has no slab with that cert number for that grader. Nothing was saved.')
  if (back !== undefined) wire.removed = wire.removed.filter((r) => r !== back)
  if (held === undefined) wire.rows.unshift(row)
  const added = held === undefined && back === undefined
  const verb = added ? 'Added' : back !== undefined ? 'Restored' : 'Updated'
  return ok({ cert: row.cert, grader: row.grader, label: labelOf(row), day: '2026-10-22', added, restored: back !== undefined, message: `${verb} ${labelOf(row)}.` })
}

/** Answer the four slab routes from `wire`, on the capture port only. */
async function stubApi(page: Page, wire: Wire): Promise<void> {
  await page.route(
    (url) => url.port === String(CAPTURE_PORT) && /^\/slabs(\/|$)/.test(url.pathname),
    async (route) => {
      const request = route.request()
      const method = request.method()
      const [, , grader = '', cert] = new URL(request.url()).pathname.split('/').map(decodeURIComponent)
      const send = (reply: Reply) => route.fulfill({ status: reply.status, contentType: 'application/json', body: JSON.stringify(reply.body) })
      if (cert === undefined) {
        if (method === 'GET') {
          wire.lists += 1
          await wire.hold.list?.opened
          return send(wire.listReply?.() ?? ok({ slabs: wire.rows }))
        }
        if (method === 'POST') {
          const body = request.postDataJSON() as { cert: string; grader: string }
          wire.posts.push(body)
          await wire.hold.post?.opened
          return send((wire.postReply ?? ((b) => addReply(wire, b)))(body))
        }
      } else {
        const row = wire.rows.find((r) => r.grader === grader && r.cert === cert)
        if (method === 'GET') {
          wire.details.push(`${grader}/${cert}`)
          await wire.hold.detail?.opened
          if (row === undefined) return send(refuse(404, 'slab_unknown', 'That slab is not in the list. Add it by its cert number first.'))
          return send(wire.detailReply?.(row) ?? ok(slabDetailOf(row)))
        }
        if (method === 'DELETE') {
          wire.deletes.push(`${grader}/${cert}`)
          await wire.hold.del?.opened
          if (row === undefined) return send(refuse(404, 'slab_unknown', 'That slab is not in the list, so there is nothing to remove.'))
          wire.rows = wire.rows.filter((r) => r !== row)
          wire.removed.push(row)
          return send(ok({ cert: row.cert, grader: row.grader, label: labelOf(row), message: `Removed ${labelOf(row)}.` }))
        }
      }
      return route.fallback()
    },
  )
}

/** Open the screen and wait for its title. The rows are each case's own wait. */
async function open(page: Page, wire: Wire = makeWire(), width = 1440): Promise<Wire> {
  await stubApi(page, wire)
  await setViewport(page, { width, height: 1000 })
  await page.goto('/#/slabs')
  await settleFonts(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Slabs' }), 'the Slabs screen never drew its title').toBeVisible()
  return wire
}

/* ---------------------------------------------------------------------------- the ledger */

/** Spec 4.1: the owner's columns, in the owner's order. */
const COLUMNS = ['Pop', 'Graded', 'Rate', 'Top %', 'Best %', 'Grade', 'Set', 'Card', 'Var', 'Ask', 'Card Ladder', 'Conf', 'Last Sale', 'PSA 10', 'Raw NM', 'Slab vs Raw', '×', 'Do'] as const
type Column = (typeof COLUMNS)[number]
const at = (name: Column): number => COLUMNS.indexOf(name)

const view = (page: Page) => page.locator('main')
const headers = (page: Page) => view(page).getByRole('columnheader')
const cellsOf = (row: Locator) => row.getByRole('cell').or(row.getByRole('gridcell'))
const dataRows = (page: Page) => view(page).getByRole('row').filter({ has: page.getByRole('cell').or(page.getByRole('gridcell')) })
const cellAt = (row: Locator, name: Column) => cellsOf(row).nth(at(name))
const cardButton = (row: Locator) => cellAt(row, 'Card').getByRole('button')
const rowFor = (page: Page, label: string) => dataRows(page).filter({ has: page.getByRole('button', { name: label, exact: true }) })

/** What the kit draws for "nothing here": an em dash. An en dash is allowed too (D218 is about the dot). */
const DASH = /^[—–]$/
/** The cells no route fills in this build: the raw price, the PSA 10 price, what is asked, the sell rule, the
 *  set and variation (the list carries no identity) and the card's graded count. Each holds a dash. */
const NEVER_FILLED: readonly Column[] = ['Graded', 'Set', 'Var', 'Ask', 'PSA 10', 'Raw NM', 'Slab vs Raw', '×', 'Do']

const money = (text: string): number | null => {
  const found = /-?[\d,]+(?:\.\d+)?/.exec(text.replace('$', ''))
  return found === null ? null : Number(found[0].replace(/,/g, ''))
}

async function textsOf(row: Locator): Promise<string[]> {
  return (await cellsOf(row).allInnerTexts()).map((t) => t.trim())
}

/** The ledger's rows, top to bottom, each with its cells' text and the label of the slab it is. */
async function ledger(page: Page): Promise<Array<{ texts: string[]; label: string | null }>> {
  const labels = severalSlabs().map((s) => s.label).filter((l): l is string => l !== null)
  const rows = dataRows(page)
  const out: Array<{ texts: string[]; label: string | null }> = []
  for (let i = 0; i < (await rows.count()); i++) {
    const row = rows.nth(i)
    let found: string | null = null
    for (const label of labels) if ((await row.getByRole('button', { name: label, exact: true }).count()) > 0) found = label
    out.push({ texts: await textsOf(row), label: found })
  }
  return out
}

const LABEL = {
  umbreon: 'Umbreon VMAX Alternate Art Secret',
  terapagos: 'Terapagos ex Special Illustration Rare',
  charizard: 'Charizard ex Obsidian Flames Double Rare',
  mew: 'Mew ex 151 Special Illustration Rare',
} as const

/* ---------------------------------------------------------------------------- the page */

/** A label of "" is not null: the screen's own no-label sentence has to cover it too. */
const EMPTY_LABEL = slabRow({ cert: '99900111', grader: 'sgc', label: '', grade: 'g8', added: '2026-10-22' })

/** Every cert and the zero-stripped form of every one, so a cert that lost its zeros is still found. */
const CERTS = [...Object.values(SLAB_CERT), GENGAR.cert, UNLABELED_NEW.cert, EMPTY_LABEL.cert].flatMap((c) => [c, c.replace(/^0+/, '')])

/** All that is on the page for a reader: the text of every element, hidden disclosures included, and the
 *  words an element hands a screen reader. Scripts and styles are not on screen. The value of a field
 *  that is showing is read too, so a case must not call this with the Add sheet open and typed in. */
async function everything(page: Page): Promise<string> {
  return page.evaluate(() => {
    const body = document.body.cloneNode(true) as HTMLElement
    body.querySelectorAll('script, style, noscript, template').forEach((n) => n.remove())
    const parts = [body.textContent ?? '']
    for (const el of body.querySelectorAll('*')) {
      for (const name of ['aria-label', 'title', 'alt', 'placeholder', 'aria-description', 'aria-valuetext']) {
        const value = el.getAttribute(name)
        if (value) parts.push(value)
      }
    }
    for (const field of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea')) if (field.offsetParent !== null) parts.push(field.value)
    return parts.join('\n')
  })
}

async function expectNoCert(page: Page, where: string): Promise<void> {
  const text = await everything(page)
  for (const cert of CERTS) expect(text.includes(cert), `${where}: cert ${cert} is on the page`).toBe(false)
}

const sentenceLines = (text: string): string[] =>
  text.split('\n').map((l) => l.trim()).filter((l) => l.split(/\s+/).length >= 4)

/** Lines of a region that were not there before, long enough to be a sentence. */
async function newSentences(region: Locator, before: string[]): Promise<string[]> {
  const now = sentenceLines(await region.innerText())
  return now.filter((line) => !before.includes(line))
}

/** The text on screen that matches, visible only: a hidden disclosure does not count as said. */
const visibleText = (page: Page, pattern: RegExp) => page.getByText(pattern).filter({ visible: true }).first()
/** The kit's Retry is labelled "Try again"; the spec calls it Retry. Neither may be offered. */
const retryButtons = (page: Page) => page.getByRole('button', { name: /retry|try again/i })

/** TWO PRESSES IN ONE TASK. A mouse double click is not used because the first press may move the button (a line
 *  that says the read takes a while), and the second click would then miss it and prove nothing. A click on a
 *  disabled button does nothing, as a person's does. */
const doublePress = (button: Locator) => button.evaluate((el) => { (el as HTMLElement).click(); (el as HTMLElement).click() })

/* ---------------------------------------------------------------------------- the cases */

for (const width of [1440, 820]) {
  test(`the ledger draws all 18 headers in the owner's order, at ${width}`, async ({ page }) => {
    await open(page, makeWire(), width)
    await expect(dataRows(page), 'the ledger drew no rows').toHaveCount(5)
    const names = (await headers(page).allInnerTexts()).map((t) => t.trim())
    expect(names.length, 'every header shows, whether or not a route can fill it').toBe(COLUMNS.length)
    names.forEach((name, i) => {
      const want = COLUMNS[i] ?? ''
      expect(name === want || name.startsWith(`${want} `), `header ${i + 1} is "${name}", want "${want}"`).toBe(true)
    })
  })
}

test('every cell holds something, and the cells no route fills hold a typed dash', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  for (const [i, line] of (await ledger(page)).entries()) {
    expect(line.texts.length, `row ${i + 1} has the wrong number of cells`).toBe(COLUMNS.length)
    for (const name of NEVER_FILLED) expect(line.texts[at(name)], `row ${i + 1}, ${name}`).toMatch(DASH)
    COLUMNS.forEach((name, c) => {
      const noSale = line.label === LABEL.mew && (name === 'Conf' || name === 'Last Sale')
      if (!noSale) expect(line.texts[c], `row ${i + 1}, ${name} is blank`).not.toBe('')
    })
  }
})

test('the ledger sorts by Card Ladder value, highest first, and a slab that never sold comes last', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const lines = await ledger(page)
  /* The route sends the reverse of this order, and 1200 against 95.50 is what a sort on the text gets wrong.
     × is a dash on every row in this build, so this proves the fallback order and nothing more. */
  expect(lines.map((l) => l.label)).toEqual([LABEL.umbreon, LABEL.terapagos, null, LABEL.charizard, LABEL.mew])
  const values = lines.slice(0, 4).map((l) => money(l.texts[at('Card Ladder')] ?? ''))
  expect(values.every((v) => v !== null), 'a slab that sold shows a figure').toBe(true)
  expect(values, 'highest first').toEqual([...values].sort((a, b) => (b ?? 0) - (a ?? 0)))
  expect(lines[4]?.texts[at('Card Ladder')]).toBe('No sales')
})

test('a slab that never sold shows "No sales" and leaves Conf and Last Sale empty', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const row = rowFor(page, LABEL.mew)
  await expect(cellAt(row, 'Card Ladder')).toHaveText('No sales')
  for (const name of ['Conf', 'Last Sale'] as const) expect((await cellAt(row, name).innerText()).trim(), name).toMatch(/^[—–]?$/)
  expect(money(await cellAt(row, 'Pop').innerText()), 'its population is still known').toBe(301)
})

test('Conf is a word, and 2 or less is drawn as a warning', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const word = async (label: string) => (await cellAt(rowFor(page, label), 'Conf').innerText()).trim()
  expect(await word(LABEL.umbreon)).toBe('High')
  expect(await word(LABEL.terapagos)).toBe('Good')
  expect(await word(LABEL.charizard)).toBe('Low')
  /* The pikachu row has no label, so it is the one that is none of the others: confidence 3. */
  const unlabeled = dataRows(page).filter({ hasNot: page.getByRole('button', { name: new RegExp(`^(${Object.values(LABEL).join('|')})$`) }) })
  expect((await cellAt(unlabeled, 'Conf').innerText()).trim()).toBe('Fair')
  const look = (cell: Locator) =>
    cell.evaluate((el) => {
      const nodes = [el, ...Array.from(el.querySelectorAll('*'))]
      return JSON.stringify({ colors: nodes.map((n) => getComputedStyle(n).color), icons: el.querySelectorAll('svg').length })
    })
  const warn = await look(cellAt(rowFor(page, LABEL.charizard), 'Conf'))
  const good = await look(cellAt(rowFor(page, LABEL.terapagos), 'Conf'))
  expect(warn, 'a confidence of 2 looks the same as a confidence of 4').not.toEqual(good)
})

test('numbers sit right, and money is drawn in the money face', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const row = rowFor(page, LABEL.terapagos)
  expect(money(await cellAt(row, 'Pop').innerText()), 'Pop is the count at the grade').toBe(118)
  for (const name of ['Pop', 'Card Ladder', 'Last Sale'] as const) {
    const gaps = await cellAt(row, name).evaluate((el) => {
      const range = document.createRange()
      range.selectNodeContents(el)
      const text = range.getBoundingClientRect()
      const box = el.getBoundingClientRect()
      return { left: text.left - box.left, right: box.right - text.right }
    })
    expect(gaps.right, `${name} sits to the left of its cell`).toBeLessThanOrEqual(gaps.left + 1)
  }
  for (const name of ['Card Ladder', 'Last Sale'] as const) {
    const cell = cellAt(row, name)
    const marked = await cell.evaluate((el) => el.matches('.bn-money') || el.querySelector('.bn-money') !== null)
    expect(marked, `${name} is a dollar figure without .bn-money`).toBe(true)
  }
  /* The scan returns the figures NOT in the mono face, so the dollar figures asserted above are what make an empty answer mean something. */
  const face = await page.evaluate(scanMoneyFace)
  expect(face.noView, 'the scan found no .bn-view to read').toBe(false)
  expect(face.text, 'a dollar figure is drawn in a face that is not mono').toEqual([])
})

test('the header counts the slabs and those that never sold, and offers Reload and Add a Slab', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const text = await view(page).innerText()
  const head = text.slice(0, text.search(/\bPop\b/))
  expect(head, 'the line under the title counts the slabs').toMatch(/\b5\b/)
  expect(head, 'and those that never sold at their grade').toMatch(/\b1\b/)
  await expect(page.getByRole('button', { name: /^Reload/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add a Slab', exact: true })).toHaveCount(1)
})

test('Reload reads the list again', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const before = wire.lists
  await page.getByRole('button', { name: /^Reload/ }).click()
  await expect.poll(() => wire.lists).toBeGreaterThan(before)
})

for (const width of [1440, 820]) {
  test(`the page never scrolls sideways, at ${width}`, async ({ page }) => {
    await open(page, makeWire(), width)
    await expect(dataRows(page)).toHaveCount(5)
    const over = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth,
    }))
    expect(over.page, 'the page scrolls sideways').toBeLessThanOrEqual(0)
    expect(over.body, 'the body scrolls sideways').toBeLessThanOrEqual(0)
  })
}

test('at 820 the table scrolls sideways inside its own frame', async ({ page }) => {
  await open(page, makeWire(), 820)
  await expect(dataRows(page)).toHaveCount(5)
  const frame = await headers(page).first().evaluate((head) => {
    for (let el = head.parentElement; el !== null && el !== document.body; el = el.parentElement) {
      if (/auto|scroll/.test(getComputedStyle(el).overflowX)) {
        const wider = el.scrollWidth > el.clientWidth
        el.scrollLeft = 40
        return { wider, moved: el.scrollLeft > 0 }
      }
    }
    return null
  })
  expect(frame, 'no ancestor of the table scrolls sideways').not.toBeNull()
  expect(frame?.wider, '18 columns fit in 820 without a scroll').toBe(true)
  expect(frame?.moved, 'the frame did not move').toBe(true)
  const page820 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(page820, 'scrolling the frame scrolled the page').toBeLessThanOrEqual(0)
})

test('the header keeps its shape while the list loads (D313)', async ({ page }) => {
  const wire = makeWire()
  wire.hold.list = new Gate()
  await open(page, wire)
  await expect(headers(page), 'the header must show while the rows are on their way').toHaveCount(COLUMNS.length)
  const boxes = () => headers(page).evaluateAll((els) => els.map((el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width)] }))
  const held = await boxes()
  wire.hold.list.open()
  await expect(dataRows(page)).toHaveCount(5)
  expect(await boxes(), 'a column moved or changed width when the rows arrived').toEqual(held)
})

test('an empty list says so in one sentence and offers one Add a Slab', async ({ page }) => {
  await open(page, makeWire({ rows: [] }))
  await expect(page.getByText(/No slabs yet/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add a Slab', exact: true }), 'the header button hides while the list is empty').toHaveCount(1)
  await page.getByRole('button', { name: 'Add a Slab', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Add a Slab' })).toBeVisible()
})

test('a failed list read says why and offers a retry that works', async ({ page }) => {
  const wire = makeWire()
  wire.listReply = () => refuse(500, 'server_error', 'The server hit a problem.')
  await open(page, wire)
  const again = retryButtons(page)
  await expect(again, 'a server fault offers a retry').toBeVisible()
  wire.listReply = null
  await again.click()
  await expect(dataRows(page)).toHaveCount(5)
})

test('a rate limit on the list is a refusal in words, with no retry', async ({ page }) => {
  const wire = makeWire()
  wire.listReply = () => RATE_LIMITED
  await open(page, wire)
  await expect(visibleText(page, /tomorrow/i)).toBeVisible()
  await expect(retryButtons(page)).toHaveCount(0)
  await expect(page.locator('.bn-retry')).toHaveCount(0)
})

/* `server.ts` reads `import.meta.env` when it loads, so no unit case can import it: the page's own module graph can.
   A 429 is a retry for every other code (`failureKind`), so this is the case that goes red when Card Ladder's
   rate limit stops being named a refusal. The screen cases above are its other readers. */
test('a Card Ladder rate limit is a refusal though it arrives as a 429', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const kind = await page.evaluate(async () => {
    const path = '/src/server.ts'
    const { describeFailure, ServerError } = await import(/* @vite-ignore */ path)
    return describeFailure(new ServerError('cardladder_rate_limited', 'Card Ladder asked us to slow down.', 429)).kind
  })
  expect(kind, 'a rate limit would be offered a retry').toBe('refusal')
})

/* NO EMPTY BAND BETWEEN THE COUNT LINE AND THE TABLE. `Page` draws its `StatusSlot` only when the screen passes a
   status, and a slot with nothing in it still takes a notice's height, so a loaded list with no notice must hold no slot
   at all. Read by element, never by a gap in pixels: a slot that is absent has no text and no height. The count line and
   the rows are waited for first, so an unfinished page cannot pass for a clean one. */
const statusSlots = (page: Page) =>
  view(page).locator('.bn-status-slot').evaluateAll((els) => els.map((el) => ({ text: (el.textContent ?? '').trim(), height: el.getBoundingClientRect().height })))

test('a loaded list with no notice holds no status band between the count line and the table', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await expect(view(page).locator('.bn-verdict')).toContainText(/\b5\b/)
  expect(await statusSlots(page), 'a status slot is drawn with no notice in it').toEqual([])
})

test('the status band goes when a failed list read is retried and the list loads', async ({ page }) => {
  const wire = makeWire()
  wire.listReply = () => refuse(500, 'server_error', 'The server hit a problem.')
  await open(page, wire)
  const again = retryButtons(page)
  await expect(again, 'a server fault offers a retry').toBeVisible()
  expect((await statusSlots(page)).length, 'the refusal is drawn in the status slot').toBeGreaterThan(0)
  wire.listReply = null
  await again.click()
  await expect(dataRows(page)).toHaveCount(5)
  await expect(view(page).locator('.bn-verdict')).toContainText(/\b5\b/)
  expect(await statusSlots(page), 'the status slot stays after the notice has gone').toEqual([])
})

/* ---------------------------------------------------------------------------- the detail */

test('a press on the Card cell opens the slab in a sheet with its sections in order', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await cardButton(rowFor(page, LABEL.terapagos)).click()
  const sheet = page.getByRole('dialog', { name: LABEL.terapagos, exact: true })
  await expect(sheet, 'the sheet is named by the slab').toBeVisible()
  await expect.poll(() => wire.details).toContain('psa/84520917')
  await expect(sheet.getByRole('button', { name: 'Remove', exact: true }), 'Remove sits in the sheet').toBeVisible()
  await expect(dataRows(page), 'the ledger behind the sheet does not move').toHaveCount(5)

  /* innerText, so two blocks that sit one under the other are not one run of letters. */
  const inner = { useInnerText: true }
  await expect(sheet).toContainText('412.00', inner)
  await expect(sheet).toContainText('405.00', inner)
  await expect(sheet).toContainText(/\bGood\b/, inner)
  await expect(sheet).toContainText(/psa/i, inner)
  await expect(sheet, 'the day the slab joined the list').toContainText(/Sep(?:t(?:ember)?)?\.?\s+0?2(?!\d)|(?<!\d)0?2\s+Sep|2026-09-02|9\/2\/2026/, inner)

  const lines = (await sheet.innerText()).split('\n').map((l) => l.trim()).filter((l) => l !== '' && l.length <= 40)
  /* Each heading is looked for AFTER the one before it: Worth names the grade ladder as the source of a figure,
     and that line is not the ladder's own heading. */
  let from = 0
  const where = [/^worth/i, /^Sales at the Grade/, /^Sales Speed/, /^Population at the Grade/, /^Grade Ladder/, /^snapshots?/i].map((p) => {
    const found = lines.findIndex((l, i) => i >= from && p.test(l))
    if (found >= 0) from = found + 1
    return found
  })
  expect(where.every((i) => i >= 0), `a section is missing or out of order: ${JSON.stringify(where)}`).toBe(true)

  /* The newest five sales are linked, a sale with no link shows no link, and the older two are not there. */
  const links = await sheet.locator('a[href^="https://sales.example.test/lot/"]').evaluateAll((els) => els.map((el) => el.getAttribute('href')))
  expect(links).toEqual(['sale-1', 'sale-3', 'sale-4', 'sale-5'].map((id) => `https://sales.example.test/lot/${id}`))
})

test('Esc closes the sheet and focus goes back to the Card button', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const button = cardButton(rowFor(page, LABEL.charizard))
  await button.click()
  const sheet = page.getByRole('dialog', { name: LABEL.charizard, exact: true })
  await expect(sheet).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()
  await expect(button).toBeFocused()
})

test('no cert is on screen: not on the ledger, not in the sheet of a slab with a label or of one without', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await expectNoCert(page, 'the ledger')

  await cardButton(rowFor(page, LABEL.terapagos)).click()
  const sheet = page.getByRole('dialog', { name: LABEL.terapagos, exact: true })
  await expect(sheet).toContainText('412.00')
  await expectNoCert(page, 'the sheet of a labelled slab')
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()

  const unlabeled = dataRows(page).filter({ hasNot: page.getByRole('button', { name: new RegExp(`^(${Object.values(LABEL).join('|')})$`) }) })
  await cardButton(unlabeled).click()
  const bare = page.getByRole('dialog')
  await expect(bare, 'a slab with no label still opens its sheet').toBeVisible()
  await expect(bare).toContainText('128.00')
  await expect(bare, 'the sheet needs a name that is not blank').toHaveAccessibleName(/\S/)
  await expectNoCert(page, 'the sheet of a slab with no label')
})

/* The sheet while its detail is on the way (spec 4.9, D313). `open()`'s sheet draws every section at once from the
   row it already has, then the detail arrives. WHAT IS MEASURED IS THE TOP OF EACH SECTION, from the section's own
   heading, before and after: a section that is drawn on both sides of the arrival has to hold its place. The slab with
   two sales and the one with none are the shapes where the sales list is shorter than the five rows it held a place
   for. The ladder's first step is the thing that exists only once the detail has arrived. */
const frames = (page: Page, n = 2) =>
  page.evaluate(
    (k) =>
      new Promise<void>((done) => {
        const step = (left: number): void => (left === 0 ? done() : void requestAnimationFrame(() => step(left - 1)))
        step(k)
      }),
    n,
  )

async function sectionTops(sheet: Locator): Promise<Record<string, number>> {
  return sheet.getByRole('region').evaluateAll((els) =>
    Object.fromEntries(
      els.map((el) => {
        const id = el.getAttribute('aria-labelledby')
        const name = (id === null ? null : document.getElementById(id)?.textContent?.trim()) || '?'
        return [name, Math.round(el.getBoundingClientRect().top)]
      }),
    ),
  )
}

const ARRIVALS = [
  { name: 'two sales', label: LABEL.terapagos, firstStep: 'PSA 8', reply: (row: SlabRow): Reply => ok(slabDetailOf(row, { sales: slabDetailOf(row).sales.slice(0, 2) })) },
  { name: 'no sales', label: LABEL.mew, firstStep: 'SGC 8', reply: null },
] as const

for (const width of [1440, 820]) {
  for (const arrival of ARRIVALS) {
    test(`no section of the sheet moves when the detail of a slab with ${arrival.name} arrives, at ${width} (D313)`, async ({ page }) => {
      const wire = makeWire()
      const gate = new Gate()
      wire.hold.detail = gate
      wire.detailReply = arrival.reply
      await open(page, wire, width)
      await expect(dataRows(page)).toHaveCount(5)
      await cardButton(rowFor(page, arrival.label)).click()
      const sheet = page.getByRole('dialog', { name: arrival.label, exact: true })
      await expect(sheet).toBeVisible()
      await expect.poll(() => wire.details.length, { message: 'the sheet never asked for its detail' }).toBe(1)
      const before = await sectionTops(sheet)
      expect(Object.keys(before), 'the sheet draws Sales Speed while the detail is on its way').toContain('Sales Speed')

      gate.open()
      await expect(sheet.getByText(arrival.firstStep, { exact: true }), 'the detail never arrived').toBeVisible()
      await frames(page)
      const after = await sectionTops(sheet)
      expect(Object.keys(after), 'Sales Speed is still drawn once the detail has arrived').toContain('Sales Speed')
      const moved = Object.keys(before).filter((name) => name in after && Math.abs((after[name] ?? 0) - (before[name] ?? 0)) > 1)
      expect(moved.map((name) => `${name} ${before[name]} to ${after[name]}`), 'a section moved when the detail arrived').toEqual([])
    })
  }
}

test('a slab whose label is the empty string still has a Card button with a visible name, and it opens the sheet', async ({ page }) => {
  await open(page, makeWire({ rows: [EMPTY_LABEL] }))
  await expect(dataRows(page)).toHaveCount(1)
  const button = cardButton(dataRows(page))
  await expect(button, 'the Card button of a slab with an empty label shows nothing').toHaveText(/\S/)
  await expect(button, 'and it has no name for a screen reader').toHaveAccessibleName(/\S/)
  await button.click()
  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  await expect(sheet).toContainText('412.00')
  await expect(sheet, 'the sheet needs a name that is not blank').toHaveAccessibleName(/\S/)
  await expectNoCert(page, 'the sheet of a slab with an empty label')
})

/* The copy sweep (copy-checks.spec.ts) skips whatever sits under `[data-typed]`: that marker is for a value the owner
   or Card Ladder typed. The screen's own "Unnamed Slab" is copy and has to be graded, so it may not sit under one;
   the stored name has to, and the marker holds nothing but that name. The three blank labels are the empty string,
   null and spaces: each one is shown as "Unnamed Slab". */
test('the Card button marks only the stored name as typed, and the screen\'s own Unnamed Slab is not under a marker', async ({ page }) => {
  const SPACES = slabRow({ cert: '99900222', grader: 'sgc', label: '   ', grade: 'g8', added: '2026-10-22' })
  await open(page, makeWire({ rows: [EMPTY_LABEL, SPACES, ...severalSlabs()] }))
  await expect(dataRows(page)).toHaveCount(7)

  const named = new Set<string>(Object.values(LABEL))
  const rows = dataRows(page)
  const faults: string[] = []
  let blank = 0
  let stored = 0
  for (let i = 0; i < (await rows.count()); i++) {
    /* One entry per text node in the button: its words, and the words of the nearest `[data-typed]` above it, if any. */
    const nodes = await cardButton(rows.nth(i)).evaluate((button) => {
      const out: Array<{ text: string; marker: string | null }> = []
      const walk = document.createTreeWalker(button, NodeFilter.SHOW_TEXT)
      for (let n = walk.nextNode(); n !== null; n = walk.nextNode()) {
        const text = (n.textContent ?? '').replace(/\s+/g, ' ').trim()
        if (text === '') continue
        const marker = n.parentElement?.closest('[data-typed]') ?? null
        out.push({ text, marker: marker === null ? null : (marker.textContent ?? '').replace(/\s+/g, ' ').trim() })
      }
      return out
    })
    const whole = nodes.map((n) => n.text).join(' ')
    if (whole === 'Unnamed Slab') {
      blank++
      for (const n of nodes) if (n.marker !== null) faults.push(`row ${i}: the screen's own "${n.text}" is under a [data-typed] marker, so the copy sweep never reads it`)
    } else if (named.has(whole)) {
      stored++
      for (const n of nodes) {
        if (n.marker === null) faults.push(`row ${i}: the stored name "${n.text}" is under no [data-typed] marker`)
        else if (n.marker !== whole) faults.push(`row ${i}: the marker over "${whole}" holds "${n.marker}"`)
      }
    } else faults.push(`row ${i}: the Card button reads "${whole}", which is neither a stored name nor the screen's own Unnamed Slab`)
  }
  expect(blank, 'the empty string, null and spaces each show Unnamed Slab').toBe(3)
  expect(stored, 'every stored name is on a row').toBe(named.size)
  expect(faults).toEqual([])
})

/* ---------------------------------------------------------------------------- add */

/** The Add sheet, opened from the header. */
async function openAdd(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: 'Add a Slab', exact: true }).click()
  const sheet = page.getByRole('dialog', { name: 'Add a Slab' })
  await expect(sheet).toBeVisible()
  return sheet
}
const certField = (sheet: Locator) => sheet.getByRole('textbox', { name: 'Cert', exact: true })
/* The kit Select's trigger: a button named "Grader" then the picked value, e.g. "Grader PSA". */
const graderField = (sheet: Locator) => sheet.getByRole('button', { name: /^Grader\b/ })
/* Matched by its first word, so a button that reads "Adding" while it works is still found. */
const addButton = (sheet: Locator) => sheet.getByRole('button', { name: /^Add\b|^Adding/ })

/** Choose a grader by the string `store/slabs.GRADERS` holds, from the kit Select's list of options. */
async function pickGrader(sheet: Locator, grader: string): Promise<void> {
  await graderField(sheet).click()
  await sheet.page().getByRole('option', { name: new RegExp(`^${grader}$`, 'i') }).click()
}

async function graderChoices(sheet: Locator): Promise<string[]> {
  await graderField(sheet).click()
  const names = (await sheet.page().getByRole('option').allInnerTexts()).map((t) => t.trim().toLowerCase())
  await sheet.page().getByRole('option', { name: /^psa$/i }).click()
  return names
}

test('the Add sheet has a Cert, a Grader and an Add that stays off while the cert is empty', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await expect(certField(sheet)).toBeVisible()
  await expect(graderField(sheet)).toBeVisible()
  await expect(addButton(sheet)).toBeDisabled()
  await certField(sheet).fill('12345678')
  await expect(addButton(sheet)).toBeEnabled()
  await certField(sheet).fill('')
  await expect(addButton(sheet)).toBeDisabled()
})

test('the grader list on screen is the one in store/slabs.GRADERS, in its order', async ({ page }) => {
  /* A dynamic import, so only this case fails while `slabGraders.ts` is missing. */
  const { SLAB_GRADERS } = await import('../src/slabGraders')
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  expect(await graderChoices(sheet)).toEqual([...SLAB_GRADERS])
})

test('adding a slab sends its cert and grader once, closes the sheet and says what the route sent', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await certField(sheet).fill(GENGAR.cert)
  await pickGrader(sheet, 'bgs')
  await addButton(sheet).click()
  await expect(sheet).toBeHidden()
  await expect(visibleText(page, /Added Gengar ex Phantasmal Flames Special Illustration Rare\./)).toBeVisible()
  expect(wire.posts).toEqual([{ cert: GENGAR.cert, grader: 'bgs' }])
  await expect(dataRows(page), 'the new slab joins the ledger').toHaveCount(6)
  await expect(rowFor(page, labelOf(GENGAR))).toHaveCount(1)
})

test('adding a slab with no label writes its own sentence and never shows the cert', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await certField(sheet).fill(UNLABELED_NEW.cert)
  await pickGrader(sheet, 'psa')
  await addButton(sheet).click()
  await expect(sheet).toBeHidden()
  await expect(page.locator('.bn-toast'), 'the receipt is shown').not.toHaveCount(0)
  await expect(dataRows(page)).toHaveCount(6)
  expect(wire.posts).toHaveLength(1)
  /* The route's own sentence is "Added slab 33309944."; the screen must not relay it. */
  await expectNoCert(page, 'the add receipt of a slab with no label')
})

test('a double press of Add sends one request, and Add is busy while the read runs', async ({ page }) => {
  const wire = makeWire()
  wire.hold.post = new Gate()
  await open(page, wire)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await certField(sheet).fill(GENGAR.cert)
  await pickGrader(sheet, 'bgs')
  await doublePress(addButton(sheet))
  await expect.poll(() => wire.posts.length).toBe(1)
  const busy = await addButton(sheet).evaluate((el) => (el as HTMLButtonElement).disabled || el.getAttribute('aria-busy') === 'true' || el.getAttribute('aria-disabled') === 'true')
  expect(busy, 'Add looks pressable while the read runs').toBe(true)
  wire.hold.post.open()
  await expect(sheet).toBeHidden()
  expect(wire.posts, 'the second press sent a second request').toHaveLength(1)
})

for (const [name, reply] of [['missing', TOKEN_MISSING], ['rejected', TOKEN_REJECTED]] as const) {
  test(`a login that is ${name} says what to do in words, and never names the settings key`, async ({ page }) => {
    const wire = makeWire()
    wire.postReply = () => reply
    await open(page, wire)
    await expect(dataRows(page)).toHaveCount(5)
    const sheet = await openAdd(page)
    await certField(sheet).fill(GENGAR.cert)
    const before = sentenceLines(await sheet.innerText())
    await addButton(sheet).click()
    await expect.poll(() => wire.posts.length).toBe(1)
    /* Add is busy while the read runs, and a line says the read takes a while: wait that out, so the sentence found is the refusal's. */
    await expect(addButton(sheet)).toBeEnabled()
    await expect.poll(async () => (await newSentences(sheet, before)).length, { message: 'the sheet says nothing about the refusal' }).toBeGreaterThan(0)
    const text = await everything(page)
    expect(text.includes(SETTINGS_KEY), 'the settings key is on screen').toBe(false)
    expect(text, 'a Google host is on screen').not.toMatch(/googleapis|securetoken/i)
    await expect(sheet, 'a refusal keeps the sheet open').toBeVisible()
  })
}

test('a rate limit on add is one request, a sentence that says tomorrow, and no Retry', async ({ page }) => {
  const wire = makeWire()
  wire.postReply = () => RATE_LIMITED
  await open(page, wire)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await certField(sheet).fill(GENGAR.cert)
  await addButton(sheet).click()
  await expect(visibleText(page, /tomorrow/i)).toBeVisible()
  await expect(retryButtons(page)).toHaveCount(0)
  await expect(page.locator('.bn-retry')).toHaveCount(0)
  await page.waitForTimeout(600) // keep: a retry loop would send again within this window
  expect(wire.posts, 'a rate limit was sent again').toHaveLength(1)
})

/* A NOTICE'S TITLE IS THE SCREEN'S OWN SENTENCE, NEVER THE SERVER'S (D196): the server's words sit behind the
   notice's "What the server said", closed. These two codes are ones the screen has no wording for, and both servers'
   sentences name things that are not the owner's: the Mac's jobs, and the store file. The title is read first, with
   its own positive check, so a notice that is missing cannot pass for one that is clean. */
for (const [name, reply, said, words] of [
  ['the store is busy', STORE_BUSY, STORE_BUSY_SAID, /identify|send/i],
  ['the store is unavailable', STORE_UNAVAILABLE, STORE_UNAVAILABLE_SAID, /sqlite/i],
] as const) {
  test(`when ${name}, the Add sheet's notice is titled in the screen's own words, not the server's`, async ({ page }) => {
    const wire = makeWire()
    wire.postReply = () => reply
    await open(page, wire)
    await expect(dataRows(page)).toHaveCount(5)
    const sheet = await openAdd(page)
    await certField(sheet).fill(GENGAR.cert)
    await addButton(sheet).click()
    await expect.poll(() => wire.posts.length).toBe(1)
    await expect(addButton(sheet)).toBeEnabled() // the read is over; its "reading" line shares the notice's place
    const notice = sheet.locator('.bn-notice')
    const title = notice.locator('.bn-notice-title')
    await expect(title, 'the refusal has no title').toHaveText(/\S/)
    expect((await title.innerText()).trim(), 'the title is the server’s sentence').not.toBe(said)
    /* Everything the notice shows with its disclosure closed: the title and any body. */
    const shown = await notice.evaluate((el) => {
      const copy = el.cloneNode(true) as HTMLElement
      copy.querySelectorAll('details').forEach((d) => d.remove())
      return copy.textContent ?? ''
    })
    expect(shown, 'the server’s words are outside the disclosure').not.toMatch(words)
    await expect(sheet, 'a refusal keeps the sheet open').toBeVisible()
  })
}

test('the Add sheet opens empty again after a refusal: no old cert, no old refusal', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await openAdd(page)
  await certField(sheet).fill('12345678') // not in the catalog, so the route answers cert_not_found
  const before = sentenceLines(await sheet.innerText())
  await addButton(sheet).click()
  await expect.poll(() => wire.posts.length).toBe(1)
  await expect(addButton(sheet)).toBeEnabled()
  await expect.poll(async () => (await newSentences(sheet, before)).length, { message: 'the sheet says nothing about the refusal' }).toBeGreaterThan(0)
  const refusal = await newSentences(sheet, before)
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()

  const again = await openAdd(page)
  await expect(certField(again), 'the cert typed last time is still in the field').toHaveValue('')
  const now = sentenceLines(await again.innerText())
  for (const line of refusal) expect(now, `the last refusal is still in the sheet: ${line}`).not.toContain(line)
})

/* ---------------------------------------------------------------------------- remove */

/** Open a row's sheet and press Remove. Returns the sheet. */
async function removeFrom(page: Page, row: Locator): Promise<Locator> {
  await cardButton(row).click()
  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  await sheet.getByRole('button', { name: 'Remove', exact: true }).click()
  return sheet
}
const undoButton = (page: Page) => page.getByRole('button', { name: /^Undo\b/ })

test('Remove acts at once, its receipt carries Undo, and Undo adds the slab again', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const sheet = await removeFrom(page, rowFor(page, LABEL.terapagos))
  await expect(undoButton(page), 'the receipt has no Undo').toBeVisible()
  await expect(visibleText(page, /Removed Terapagos ex Special Illustration Rare\./)).toBeVisible()
  expect(wire.deletes).toEqual(['psa/84520917'])
  await expect(sheet, 'the sheet of a removed slab stays open').toBeHidden()
  await expect(dataRows(page)).toHaveCount(4)
  await expect(rowFor(page, LABEL.terapagos)).toHaveCount(0)

  await undoButton(page).click()
  await expect(dataRows(page)).toHaveCount(5)
  await expect(rowFor(page, LABEL.terapagos)).toHaveCount(1)
  expect(wire.posts, 'Undo adds the slab it removed, by cert and grader').toEqual([{ cert: SLAB_CERT.terapagos, grader: 'psa' }])
})

test('the remove and undo receipts of a slab with no label never show its cert', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  const unlabeled = dataRows(page).filter({ hasNot: page.getByRole('button', { name: new RegExp(`^(${Object.values(LABEL).join('|')})$`) }) })
  await removeFrom(page, unlabeled)
  await expect(undoButton(page)).toBeVisible()
  await expect(dataRows(page)).toHaveCount(4)
  /* The route's own sentence is "Removed slab 00481923."; the screen must not relay it. */
  await expectNoCert(page, 'the remove receipt of a slab with no label')

  await undoButton(page).click()
  await expect(dataRows(page)).toHaveCount(5)
  await expect(page.locator('.bn-toast:not([data-leaving])')).not.toHaveCount(0)
  expect(wire.posts).toEqual([{ cert: SLAB_CERT.pikachu, grader: 'cgc' }])
  await expectNoCert(page, 'the undo receipt of a slab with no label')
})

test('an Undo that Card Ladder refuses says so, with no retry', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await removeFrom(page, rowFor(page, LABEL.charizard))
  await expect(undoButton(page)).toBeVisible()
  wire.postReply = () => RATE_LIMITED
  await undoButton(page).click()
  await expect(visibleText(page, /tomorrow/i), 'Undo failed without a word').toBeVisible()
  await expect(retryButtons(page)).toHaveCount(0)
  expect(wire.posts).toHaveLength(1)
  await expect(rowFor(page, LABEL.charizard), 'a refused Undo put the slab back').toHaveCount(0)
})

test('an Undo that Card Ladder fails on shows the sentence the server sent, not a generic one', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await removeFrom(page, rowFor(page, LABEL.charizard))
  await expect(undoButton(page)).toBeVisible()
  wire.postReply = () => BAD_GATEWAY
  await undoButton(page).click()
  await expect(visibleText(page, /Card Ladder could not be read just now\./), 'Undo failed without the refusal’s own sentence').toBeVisible()
  expect(wire.posts).toHaveLength(1)
})

/* The toast form of the same rule: a refusal toast's title is the screen's own, and the server's sentence is its body. */
test('an Undo that Card Ladder fails on titles its toast in the screen’s own words and keeps the server’s sentence in the body', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await removeFrom(page, rowFor(page, LABEL.charizard))
  await expect(undoButton(page)).toBeVisible()
  wire.postReply = () => BAD_GATEWAY
  await undoButton(page).click()
  /* The receipt toast fades but stays in the stack, so the refusal is the one that is not leaving. */
  const refusal = page.locator('.bn-toast-refusal:not([data-leaving])')
  await expect(refusal, 'Undo failed without a refusal toast').toBeVisible()
  const title = refusal.locator('.bn-toast-title')
  await expect(title, 'the toast has no title').toHaveText(/\S/)
  expect((await title.innerText()).trim(), 'the toast’s title is the server’s sentence').not.toBe(BAD_GATEWAY_SAID)
  await expect(refusal.locator('.bn-toast-body'), 'the server’s sentence is not in the toast body').toHaveText(BAD_GATEWAY_SAID)
  expect(wire.posts).toHaveLength(1)
})

test('an Undo that never reaches the server says so in the client’s own sentence', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await removeFrom(page, rowFor(page, LABEL.charizard))
  await expect(undoButton(page)).toBeVisible()
  let dropped = 0
  await page.route(
    (url) => url.port === String(CAPTURE_PORT) && url.pathname === '/slabs',
    (route) => {
      if (route.request().method() !== 'POST') return route.fallback()
      dropped += 1
      return route.abort()
    },
  )
  await undoButton(page).click()
  /* `server.ts:request()` words this one itself. The shell's `/status` still answers, so it is the "will not accept changes" sentence. */
  await expect(visibleText(page, /will not accept changes from this address|server did not answer/i), 'Undo failed without the client’s sentence').toBeVisible()
  expect(dropped).toBe(1)
  expect(wire.posts, 'the dropped request reached the stub').toHaveLength(0)
})

test('after Remove succeeds, focus is on something on the page and never on the body', async ({ page }) => {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  /* The list read after the remove is held, so the Card button stays on the page while the sheet gives focus back to
     it. The row goes only when the read is let through, and focus has to be somewhere else by then. A build that
     closes the sheet only after that read is not held here: it has no Card button to give focus back to. */
  const gate = new Gate()
  wire.hold.list = gate
  const reads = wire.lists
  const sheet = await removeFrom(page, rowFor(page, LABEL.terapagos))
  await expect.poll(() => wire.lists, { message: 'the list was not read again after the remove' }).toBe(reads + 1)
  await sheet.waitFor({ state: 'hidden', timeout: 2000 }).catch(() => undefined)
  await frames(page)
  gate.open()
  await expect(undoButton(page)).toBeVisible()
  await expect(sheet).toBeHidden()
  await expect(dataRows(page)).toHaveCount(4)
  await expect(rowFor(page, LABEL.terapagos)).toHaveCount(0)
  const focused = () =>
    page.evaluate(() => {
      const el = document.activeElement
      if (el === null || el === document.body || el === document.documentElement) return 'nothing: the body has focus'
      if (!el.isConnected || !el.checkVisibility()) return `nothing: a hidden ${el.tagName.toLowerCase()} has focus`
      return `${el.tagName.toLowerCase()} ${(el.textContent ?? '').trim().slice(0, 30)}`
    })
  await expect.poll(focused, { message: 'the Card button focus went back to left the page', timeout: 3000 }).not.toMatch(/^nothing/)
  await frames(page) // it has to hold, not only pass through
  expect(await focused(), 'focus landed somewhere and then fell off the page').not.toMatch(/^nothing/)
})

/* FOCUS AFTER REMOVE WHEN THE LIST READ IS NOT HELD. The case above holds the read, so the Card button is still on the
   page when the sheet gives focus back. A real read is quick: the row is gone while the sheet is still leaving. Where
   focus is then decides it. A click that focuses Remove leaves focus on the body once Remove goes off, and the page
   moves it on to a Card button when the row goes. A press that leaves focus inside the sheet (a mouse press in Safari
   does not focus a button; `click()` on the element is that press) finds focus still in the sheet when the row goes.
   The sheet gives focus back one frame after it closes, to the button that opened it: if the row is still there the
   button takes it and the page moves it on, but if the list read has landed first that button is gone, and the kit
   sends focus to the page's h1. The stub's read is a race with that frame, so the second press holds the page's frames
   from the press until the row has gone, which makes the read land first every time. Either way focus must end on a
   Card button (on Add a Slab when the list is empty), never on the h1 or the body, and must stay there. The holder is
   named in words, so a red run says who had focus. */
const focusHolder = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement
    if (el === null || el === document.body || el === document.documentElement) return 'the body'
    if (!el.isConnected || !el.checkVisibility()) return `a hidden ${el.tagName.toLowerCase()}`
    const text = (el.textContent ?? '').trim().slice(0, 30)
    if (el.hasAttribute('data-bn-page-title')) return `the h1: ${text}`
    if (el.hasAttribute('data-slab')) return `card button: ${text}`
    if (el.hasAttribute('data-slabs-add')) return `add button: ${text}`
    return `${el.tagName.toLowerCase()}: ${text}`
  })

type FrameWindow = Window & { __held?: FrameRequestCallback[]; __real?: typeof requestAnimationFrame }
const holdFrames = (page: Page) =>
  page.evaluate(() => {
    const w = window as FrameWindow
    w.__held = []
    w.__real = window.requestAnimationFrame.bind(window)
    window.requestAnimationFrame = (callback) => w.__held?.push(callback) ?? 0
  })
const releaseFrames = (page: Page) =>
  page.evaluate(() => {
    const w = window as FrameWindow
    if (w.__real === undefined) return
    window.requestAnimationFrame = w.__real
    for (const callback of w.__held?.splice(0) ?? []) w.__real(callback)
  })

const LAST_SLAB = severalSlabs().filter((row) => row.label === LABEL.mew)

for (const [press, focusesRemove] of [['a click that focuses Remove and a quick list read', true], ['a press that leaves focus in the sheet and a list read that lands before the first frame', false]] as const) {
  for (const [name, rows, lands] of [
    ['a Card button', null, /^card button:/],
    ['Add a Slab when the list is empty', LAST_SLAB, /^add button:/],
  ] as const) {
    test(`after Remove by ${press}, focus lands on ${name} and stays there`, async ({ page }) => {
      await open(page, makeWire(rows === null ? {} : { rows: [...rows] }))
      const row = rows === null ? rowFor(page, LABEL.terapagos) : dataRows(page)
      await expect(dataRows(page)).toHaveCount(rows === null ? 5 : 1)
      await cardButton(row).click()
      const remove = page.getByRole('dialog').getByRole('button', { name: 'Remove', exact: true })
      await expect(remove).toBeVisible()
      if (focusesRemove) await remove.click()
      else {
        await holdFrames(page)
        await remove.evaluate((el) => (el as HTMLElement).click())
      }
      await expect(undoButton(page)).toBeVisible()
      await expect(dataRows(page)).toHaveCount(rows === null ? 4 : 0)
      await releaseFrames(page)
      await expect.poll(() => focusHolder(page), { message: `focus did not land on ${name}`, timeout: 3000 }).toMatch(lands)
      await frames(page, 10) // it has to hold, not only pass through
      expect(await focusHolder(page), `focus landed on ${name} and then left it`).toMatch(lands)
    })
  }
}

test('a double press of Remove sends one request', async ({ page }) => {
  const wire = makeWire()
  wire.hold.del = new Gate()
  await open(page, wire)
  await expect(dataRows(page)).toHaveCount(5)
  await cardButton(rowFor(page, LABEL.umbreon)).click()
  const sheet = page.getByRole('dialog', { name: LABEL.umbreon, exact: true })
  await expect(sheet).toBeVisible()
  await doublePress(sheet.getByRole('button', { name: 'Remove', exact: true }))
  await expect.poll(() => wire.deletes.length).toBe(1)
  wire.hold.del.open()
  await expect(undoButton(page)).toBeVisible()
  expect(wire.deletes, 'the second press sent a second DELETE').toHaveLength(1)
})

test('Remove is off while this tab has an add in flight', async ({ page }) => {
  const wire = makeWire()
  wire.hold.post = new Gate()
  await open(page, wire)
  await expect(dataRows(page)).toHaveCount(5)
  const add = await openAdd(page)
  await certField(add).fill(GENGAR.cert)
  await pickGrader(add, 'bgs')
  await addButton(add).click()
  await expect.poll(() => wire.posts.length).toBe(1)
  await page.keyboard.press('Escape')
  await expect(add, 'the Add sheet can be closed while its read runs').toBeHidden()

  await cardButton(rowFor(page, LABEL.terapagos)).click()
  const sheet = page.getByRole('dialog', { name: LABEL.terapagos, exact: true })
  await expect(sheet).toBeVisible()
  const remove = sheet.getByRole('button', { name: 'Remove', exact: true })
  await expect(remove).toBeDisabled()
  wire.hold.post.open()
  await expect(remove, 'Remove stays off after the add has finished').toBeEnabled()
})

/* ---------------------------------------------------------------------------- the polish rulings (spec 4.8) */

const HERE = dirname(fileURLToPath(import.meta.url))
/** `scripts/machine-words.json`, the one word list the repo keeps (D196). */
const DICTIONARY = (() => {
  const raw = JSON.parse(readFileSync(resolve(HERE, '..', '..', 'scripts', 'machine-words.json'), 'utf8')) as { words: Record<string, string>; repoTopDirs: string[] }
  return { words: raw.words, repoTopDirs: raw.repoTopDirs }
})()

const UNDO_SAID = 'The slab was not put back.'
const NO_ESTIMATE = 'No estimate without a sale.'

/* THE REASON UNDER A SHORT SENTENCE (4.8). The spec pins the two sentences and says each carries a reason that shows on
   hover, on keyboard focus and on a tap. It pins no wording, no markup and no kit part, so a reason is found by what a
   reader gets: a run of text that was not painted before, is a sentence (four words or more), sits near the sentence, is
   fully inside the window and is not covered by anything. A native `title` attribute is therefore not a reason: it is not
   in the DOM, and it never shows on focus or on a tap. A button's one-word tip ("Dismiss") is too short to count.
   The kit fades its tips by opacity, which Playwright's visibility counts as visible, so a run counts only at full opacity. */
type Box = { left: number; top: number; right: number; bottom: number }
type Run = Box & { text: string; painted: boolean }

/** Every run of text on the page this frame. `painted` is worked out only for a run not in `known`, when `paint` is set. */
const readRuns = (page: Page, known: string[], paint: boolean): Promise<Run[]> =>
  page.evaluate(
    (args) => {
      const had = new Set(args.known)
      const own = new Map<Element, { text: string; first: Text; last: Text }>()
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      for (let n = walk.nextNode(); n !== null; n = walk.nextNode()) {
        const node = n as Text
        const parent = node.parentElement
        const piece = (node.textContent ?? '').replace(/\s+/g, ' ').trim()
        if (parent === null || piece === '' || parent.closest('script, style, noscript, template') !== null) continue
        const held = own.get(parent)
        own.set(parent, { text: held === undefined ? piece : `${held.text} ${piece}`, first: held?.first ?? node, last: node })
      }
      const runs: Array<Box & { text: string; painted: boolean }> = []
      for (const [parent, { text, first, last }] of own) {
        if (!parent.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
        let seen = true
        for (let el: Element | null = parent; el !== null; el = el.parentElement) {
          const style = getComputedStyle(el)
          if (Number(style.opacity) < 0.99) seen = false
          const size = el.getBoundingClientRect()
          const clipped = style.overflow !== 'visible' || style.clip !== 'auto' || style.clipPath !== 'none'
          if ((size.width <= 1 || size.height <= 1) && style.display !== 'contents' && clipped) seen = false
        }
        if (!seen) continue
        const range = document.createRange()
        range.setStartBefore(first)
        range.setEndAfter(last)
        const r = range.getBoundingClientRect()
        if (r.width < 4 || r.height < 4 || r.right <= 0 || r.bottom <= 0 || r.left >= innerWidth || r.top >= innerHeight) continue
        let painted = false
        if (args.paint && !had.has(text)) {
          /* A tip is `pointer-events: none` so a click never lands on it, and hit-testing skips it. The probe sets it back
             to `auto` for these four reads, at the midpoint of each edge (a rounded corner hides the corner pixel). The
             element on top at each point must be the run's own, so a tip under the sheet is not painted. */
          const el = parent as HTMLElement
          const keep = el.style.pointerEvents
          el.style.pointerEvents = 'auto'
          const mx = (r.left + r.right) / 2
          const my = (r.top + r.bottom) / 2
          const probes: Array<[number, number]> = [[mx, r.top + 1], [mx, r.bottom - 1], [r.left + 1, my], [r.right - 1, my]]
          const inside = r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight
          painted = inside && probes.every(([x, y]) => {
            const top = document.elementFromPoint(x, y)
            return top !== null && (top === el || el.contains(top))
          })
          el.style.pointerEvents = keep
        }
        runs.push({ text, left: r.left, top: r.top, right: r.right, bottom: r.bottom, painted })
      }
      return runs
    },
    { known, paint },
  )

const boxOf = (sentence: Locator): Promise<Box> =>
  sentence.evaluate((el) => {
    const range = document.createRange()
    range.selectNodeContents(el)
    const r = range.getBoundingClientRect()
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom }
  })

const wordCount = (text: string): number => text.split(/\s+/).filter(Boolean).length
/** How far apart two boxes are on the axis they are furthest apart; 0 when they touch or overlap. */
const apart = (a: Box, b: Box): number =>
  Math.max(Math.max(0, a.left - b.right, b.left - a.right), Math.max(0, a.top - b.bottom, b.top - a.bottom))

/** Words that name machinery, read the way the repo reads them (`machineWords.ts` on `scripts/machine-words.json`), plus
 *  the shapes a refusal leaks: a decision id, a snake_case code, the settings key, a status number, a route, a cert.
 *  `scanMachineWords` reads `.bn-view`, and a tip may be drawn outside it, so the text is read through a probe that
 *  takes the first `.bn-view` for the length of the read. */
async function mechanismIn(page: Page, text: string): Promise<string[]> {
  await page.evaluate((t) => {
    const probe = document.createElement('div')
    probe.className = 'bn-view'
    probe.setAttribute('data-probe', '')
    probe.style.cssText = 'position: fixed; left: -9999px; top: 0'
    probe.textContent = t
    document.body.prepend(probe)
  }, text)
  const found = await page.evaluate(scanMachineWords, DICTIONARY)
  await page.evaluate(() => document.querySelector('[data-probe]')?.remove())
  const shapes: Array<[string, RegExp]> = [
    ['a decision id', /\bD\d+\b/],
    ['a snake_case code', /\b[a-z]+_[a-z_]+\b/],
    ['the settings key', /CARDLADDER|REFRESH_TOKEN/i],
    ['a status number', /\b[45]\d\d\b/],
    ['a route', /\/slabs\b/],
    ['a token', /\btoken\b/i],
    ['a cert', new RegExp(CERTS.join('|'))],
  ]
  return [...found.words.map((w) => w.word), ...found.paths.map((p) => p.path), ...shapes.filter(([, re]) => re.test(text)).map(([name]) => name)]
}

/** Press Tab until focus is on the sentence, or on a control that holds it and is no bigger than a sentence's block (a
 *  scroller that Chrome lets focus is not the sentence). Names what focus visited, so a red run says where Tab went. */
async function tabTo(page: Page, sentence: Locator, said: string): Promise<void> {
  const visited: string[] = []
  for (let press = 0; press < 120; press++) {
    await page.keyboard.press('Tab')
    const on = await sentence.evaluate((el) => {
      const held = document.activeElement
      if (held === null) return { name: 'nothing', mine: false }
      const name = `${held.tagName.toLowerCase()} "${(held.getAttribute('aria-label') ?? held.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 24)}"`
      if (held.matches('html, body, main, #root, [role="dialog"], [aria-live]')) return { name, mine: false }
      const small = held.getBoundingClientRect().height <= el.getBoundingClientRect().height * 3 + 80
      return { name, mine: el.contains(held) || (held.contains(el) && small) }
    })
    visited.push(on.name)
    if (on.mine) return
  }
  expect(false, `Tab never reached "${said}" in ${visited.length} presses. The stops Tab visited, in order: ${[...new Set(visited)].join(', ')}`).toBe(true)
}

/** Open the sheet of the Terapagos slab (or `label`'s) at `width` and wait for its detail. */
async function openSheet(page: Page, width = 1440, label: string = LABEL.terapagos, firstStep = 'PSA 8'): Promise<Locator> {
  await open(page, makeWire(), width)
  await expect(dataRows(page)).toHaveCount(5)
  await cardButton(rowFor(page, label)).click()
  const sheet = page.getByRole('dialog', { name: label, exact: true })
  await expect(sheet.getByText(firstStep, { exact: true }), 'the detail never arrived').toBeVisible()
  return sheet
}

/** Undo's request gets no answer. `blocked`: `/status` still answers, so the client words it `origin_blocked` (the existing
 *  never-reaches-the-server case). `down`: the one `/status` read that follows the dropped request fails too, so the client
 *  words it `unreachable`, and the shell's offline banner rises. */
async function dropUndo(page: Page, how: 'blocked' | 'down'): Promise<void> {
  let probe = false
  if (how === 'down') {
    await page.route(
      (url) => url.port === String(CAPTURE_PORT) && url.pathname === '/status',
      (route) => {
        if (!probe) return route.fallback()
        probe = false
        return route.abort()
      },
    )
  }
  await page.route(
    (url) => url.port === String(CAPTURE_PORT) && url.pathname === '/slabs',
    (route) => {
      if (route.request().method() !== 'POST') return route.fallback()
      probe = true
      return route.abort()
    },
  )
}

/** Remove Charizard, press Undo, and let Card Ladder refuse it with `reply`, or drop the request (`dropUndo`). Returns the refusal toast. */
async function refusedUndo(page: Page, reply: Reply | 'blocked' | 'down'): Promise<Locator> {
  const wire = await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  await removeFrom(page, rowFor(page, LABEL.charizard))
  await expect(undoButton(page)).toBeVisible()
  if (typeof reply === 'string') await dropUndo(page, reply)
  else wire.postReply = () => reply
  await undoButton(page).click()
  const refusal = page.locator('.bn-toast-refusal:not([data-leaving])')
  await expect(refusal, 'Undo failed without a refusal toast').toBeVisible()
  return refusal
}

type Subject = {
  readonly name: string
  readonly said: string
  /** What the reason says (4.8), as properties and never as wording. */
  readonly says: ReadonlyArray<readonly [string, RegExp]>
  readonly arrive: (page: Page) => Promise<Locator>
}
const SUBJECTS: readonly Subject[] = [
  {
    name: 'a refused Undo',
    said: UNDO_SAID,
    says: [['why the add-back failed, or what to do', /Card Ladder|limit|later|again|tomorrow/i]],
    arrive: async (page) => (await refusedUndo(page, BAD_GATEWAY)).getByText(UNDO_SAID, { exact: true }),
  },
  {
    name: 'the Worth line of a slab with no sales',
    said: NO_ESTIMATE,
    says: [
      ['that the slab has not sold', /\b(sold|sell|sells|sale|sales)\b/i],
      ['the grade', /\bgrade\b/i],
    ],
    arrive: async (page) => {
      const sheet = await openSheet(page, 1440, LABEL.mew, 'SGC 8')
      return sheet.getByText(NO_ESTIMATE, { exact: true })
    },
  },
]

/** The reasons a reader has now: sentences not painted before, near the sentence, whole and uncovered. Waits up to 4s for one. */
async function reasonsNear(page: Page, known: string[], said: string, box: Box, because: string): Promise<Run[]> {
  let reasons: Run[] = []
  await expect
    .poll(
      async () => {
        const now = await readRuns(page, known, true)
        reasons = now.filter((r) => !known.includes(r.text) && r.text !== said && wordCount(r.text) >= 4 && r.painted && apart(r, box) <= 240)
        return reasons.length
      },
      { message: `${because}: no new sentence of four words or more is painted, whole and uncovered, within 240px of it`, timeout: 4000 },
    )
    .toBeGreaterThan(0)
  return reasons
}

type Mode = 'hover' | 'focus' | 'tap'
/** Settle the page, open the reason under `sentence` the way `mode` says, and return the runs of the reason. */
async function openReason(page: Page, sentence: Locator, said: string, mode: Mode, who: string): Promise<Run[]> {
  await expect(sentence, `${who} never showed "${said}"`).toBeVisible()
  /* The pointer starts away from the sentence: an Undo press leaves it where the refusal lands. */
  await page.mouse.move(10, 10)
  await expect.poll(async () => (await readRuns(page, [], false)).some((r) => r.text === said), { message: `"${said}" is never fully painted` }).toBe(true)
  await frames(page, 4)
  const known = (await readRuns(page, [], false)).map((r) => r.text)
  const box = await boxOf(sentence)

  if (mode === 'hover') await sentence.hover()
  else if (mode === 'tap') await sentence.tap()
  else await tabTo(page, sentence, said)

  return reasonsNear(page, known, said, box, `${mode === 'hover' ? 'Hovering' : mode === 'tap' ? 'Tapping' : 'Tabbing to'} "${said}" shows no reason`)
}

async function expectReason(page: Page, subject: Subject, mode: Mode): Promise<void> {
  const sentence = await subject.arrive(page)
  const reason = (await openReason(page, sentence, subject.said, mode, subject.name)).map((r) => r.text).join(' ')
  for (const [what, pattern] of subject.says) expect(reason, `the reason does not say ${what}`).toMatch(pattern)
  expect(await mechanismIn(page, reason), `the reason names machinery: "${reason}"`).toEqual([])
}

for (const subject of SUBJECTS) {
  for (const mode of ['hover', 'focus'] as const) {
    test(`the reason of ${subject.name} shows on ${mode}, in words that name no mechanism`, async ({ page }) => {
      await expectReason(page, subject, mode)
    })
  }
}

/* THE TWO PROBES, SHOWN RED AND GREEN ON KNOWN TEXT (a guard is trusted once it has gone red on its defect, and the cases
   above are red on a screen that has no reason to find). The finder is given a sentence that draws three tips on hover:
   one a reader sees, one at zero opacity and one under the sheet. It must report the first and neither of the others. The
   machinery probe is given a sentence that names machinery and one that does not. */
test('the reason finder reports a tip a reader sees, and not one at zero opacity or under the page', async ({ page }) => {
  const sentence = await SUBJECTS[1]?.arrive(page)
  if (sentence === undefined) throw new Error('no Worth subject')
  await expect(sentence).toBeVisible()
  await sentence.evaluate((el) => {
    el.addEventListener('mouseenter', () => {
      const r = el.getBoundingClientRect()
      const tip = (text: string, style: string) => {
        const one = document.createElement('div')
        one.textContent = text
        one.style.cssText = `position: fixed; left: ${r.left}px; pointer-events: none; ${style}`
        document.body.appendChild(one)
      }
      tip('This slab has never sold here.', `top: ${r.bottom + 6}px; z-index: 9999; opacity: 1`)
      tip('This faded tip cannot be read.', `top: ${r.bottom + 40}px; z-index: 9999; opacity: 0`)
      tip('This covered tip cannot be read.', `top: ${r.bottom + 70}px; z-index: -1; opacity: 1`)
    })
  })
  await page.mouse.move(10, 10)
  await frames(page, 4)
  const known = (await readRuns(page, [], false)).map((r) => r.text)
  const box = await boxOf(sentence)
  await sentence.hover()
  const seen = (await reasonsNear(page, known, NO_ESTIMATE, box, 'The finder missed the tip a reader sees')).map((r) => r.text)
  expect(seen).toEqual(['This slab has never sold here.'])
})

test('the machinery probe names the resolver, a decision id and a code, and passes a plain sentence', async ({ page }) => {
  await open(page)
  await expect(dataRows(page)).toHaveCount(5)
  expect((await mechanismIn(page, 'The resolver sent slab_unknown for D320 with a 502.')).length, 'machinery in a tip went unseen').toBeGreaterThanOrEqual(3)
  expect(await mechanismIn(page, 'Card Ladder did not answer. Try again later.')).toEqual([])
  expect(await page.locator('[data-probe]').count(), 'the probe stayed on the page').toBe(0)
})

/* A TAP. The context has a touchscreen, and `tap()` sends touch events. Chromium also sends the mouse events a tap
   implies, so a build whose reason answers only to a pointer entering may pass this case; the focus case is what holds
   that build to account. */
test.describe('on a touchscreen', () => {
  test.use({ hasTouch: true })
  for (const subject of SUBJECTS) {
    test(`the reason of ${subject.name} shows on a tap, in words that name no mechanism`, async ({ page }) => {
      await expectReason(page, subject, 'tap')
    })
  }
})

/* 4.8: an Undo that Card Ladder refuses, a rate limit included, shows the one sentence. The server's own words stay behind
   the sentence (the toast cases above), and a rate limit still offers no Retry. */
for (const [name, reply] of [['a rate limit', RATE_LIMITED], ['a failed read', BAD_GATEWAY]] as const) {
  test(`an Undo refused by ${name} is titled "${UNDO_SAID}", offers no Retry and puts nothing back`, async ({ page }) => {
    const refusal = await refusedUndo(page, reply)
    await expect(refusal.getByText(UNDO_SAID, { exact: true }), 'the refusal is not titled with the screen’s sentence').toBeVisible()
    await expect(retryButtons(page)).toHaveCount(0)
    await expect(rowFor(page, LABEL.charizard), 'a refused Undo put the slab back').toHaveCount(0)
  })
}

/* 4.8, THE REASON OF A REFUSED UNDO IS TRUE FOR ITS CODE. Review round 1 found one reason, "Card Ladder did not answer", under
   every code the screen does not word, and that is false for most of them. Each case refuses Undo with one real code, opens the
   reason by keyboard focus and asserts the FACT the reason gives, never its wording. A fact is read off the reason's own text
   and never off the page: the toast's body holds the server's sentence, which says "sign in", "did not answer" and "cert number"
   for itself, so a page-wide match would pass on the defect. */
const codeOf = (reply: Reply): string => (reply.body as { error: { code: string } }).error.code

/** `holds`: the reason must match (a fact it gives) or must not match (a claim that would be false for the code). */
type Fact = readonly [what: string, pattern: RegExp, holds: boolean]
const UNDO_REASONS: ReadonlyArray<{ readonly reply: Reply; readonly facts: readonly Fact[] }> = [
  { reply: RATE_LIMITED, facts: [['it tells the owner to try again tomorrow', /tomorrow/i, true]] },
  {
    reply: TOKEN_MISSING,
    facts: [
      ['it tells the owner to sign in to Card Ladder again', /sign in/i, true],
      ['it speaks of a "saved" sign-in, when none was saved', /saved/i, false],
    ],
  },
  {
    reply: TOKEN_REJECTED,
    facts: [
      ['it tells the owner to sign in to Card Ladder again', /sign in/i, true],
      ['it speaks of a "saved" sign-in', /saved/i, false],
    ],
  },
  { reply: BAD_GATEWAY, facts: [['it says Card Ladder did not answer', /did not answer/i, true]] },
  { reply: UNREADABLE, facts: [['it says Card Ladder did not answer, when it answered and the answer could not be read', /did not answer/i, false]] },
  {
    reply: CERT_NOT_FOUND,
    facts: [
      ['it says Card Ladder did not answer, when it answered that the slab is not there', /did not answer/i, false],
      ['it carries digits, and a cert is never drawn', /\d/, false],
    ],
  },
  { reply: ADD_BUSY, facts: [['it names Card Ladder, when the wait is for another add on this app', /Card Ladder/i, false]] },
]

for (const { reply, facts } of UNDO_REASONS) {
  const code = codeOf(reply)
  test(`an Undo refused with ${code} gives a reason that is true for that code, opened by keyboard focus`, async ({ page }) => {
    const sentence = (await refusedUndo(page, reply)).getByText(UNDO_SAID, { exact: true })
    const reason = (await openReason(page, sentence, UNDO_SAID, 'focus', `the Undo refused with ${code}`)).map((r) => r.text).join(' ')
    for (const [what, pattern, holds] of facts) {
      const check = expect.soft(reason, holds ? `the reason for ${code} is missing a fact, ${what}: "${reason}"` : `the reason for ${code} makes a false claim, ${what}: "${reason}"`)
      if (holds) check.toMatch(pattern)
      else check.not.toMatch(pattern)
    }
    expect.soft(await mechanismIn(page, reason), `the reason for ${code} names machinery: "${reason}"`).toEqual([])
  })
}

/* A refusal with no cause the screen can name has the title and the body's own sentence, and no reason behind either: a reason
   guessed at is a lie. The first row is a real code `undoRefusalToast` does not name. The second is the app's own request
   dropped while `/status` still answers (`origin_blocked`, the client's own sentence), the third the same with the server
   down (`unreachable`, which raises the shell's offline banner, so the case clears it to leave the screen as it found it; the
   body's sentence is what tells the two apart). */
const NO_REASON: ReadonlyArray<{ readonly name: string; readonly how: Reply | 'blocked' | 'down'; readonly body: string | RegExp }> = [
  { name: 'a code the screen does not word (store_busy)', how: STORE_BUSY, body: STORE_BUSY_SAID },
  { name: 'a request the server will not take from this address (origin_blocked)', how: 'blocked', body: /will not accept changes from this address/ },
  { name: 'a server that does not answer (unreachable)', how: 'down', body: /server did not answer/ },
]

for (const { name, how, body } of NO_REASON) {
  test(`an Undo refused by ${name} keeps the title and the body's sentence and gives no reason`, async ({ page }) => {
    const refusal = await refusedUndo(page, how)
    const sentence = refusal.getByText(UNDO_SAID, { exact: true })
    await expect(sentence, `the refusal is not titled "${UNDO_SAID}"`).toBeVisible()
    await expect(refusal.locator('.bn-toast-body'), 'the sentence of the refusal is not in the toast body').toHaveText(body)
    await page.mouse.move(10, 10)
    await expect.poll(async () => (await readRuns(page, [], false)).some((r) => r.text === UNDO_SAID), { message: `"${UNDO_SAID}" is never fully painted` }).toBe(true)
    await frames(page, 4)
    const known = (await readRuns(page, [], false)).map((r) => r.text)
    const box = await boxOf(sentence)
    await sentence.hover()
    await frames(page, 45) // the 120ms fade in took 13 to 18 frames to finish when measured, so this holds for about three times that
    const reasons = (await readRuns(page, known, true)).filter((r) => !known.includes(r.text) && r.text !== UNDO_SAID && wordCount(r.text) >= 4 && r.painted && apart(r, box) <= 240)
    expect(reasons.map((r) => r.text), 'hovering the title shows a reason the screen cannot know is true').toEqual([])
    await expect(sentence, 'the title is given a reason that a screen reader reads').toHaveAccessibleDescription('')
    if (how === 'down') {
      /* The banner may clear by itself on the shell's next read, so Retry is pressed only if it is still there. */
      await page.locator('.bn-banner').getByRole('button', { name: 'Retry' }).click({ timeout: 2000 }).catch(() => undefined)
      await expect(page.locator('.bn-banner'), 'the offline banner stayed after Retry').toHaveCount(0)
    }
  })
}

/* ESCAPE CLOSES A REASON AND NOTHING UNDER IT. A reason opened by focus is a popover over the sheet; the sheet's own Escape
   is the shell's and must not hear this one. The reason is the Worth line's, in a sheet, because that is where a reason sits
   over another layer. The sheet leaves in 140ms (`useLeave`), so it is asserted after a hold well past that: a sheet still
   leaving counts as visible. */
test('Escape closes an open reason and leaves the sheet that holds it open', async ({ page }) => {
  const worth = SUBJECTS.find((one) => one.said === NO_ESTIMATE)
  if (worth === undefined) throw new Error('no Worth subject')
  const sentence = await worth.arrive(page)
  const sheet = page.getByRole('dialog', { name: LABEL.mew, exact: true })
  await frames(page, 90) // the sheet's sections fade in one after another; a section that is still arriving is not a reason
  const shown = (await openReason(page, sentence, NO_ESTIMATE, 'focus', worth.name)).map((r) => r.text)
  await expect(sheet, 'the sheet closed before Escape was pressed').toBeVisible()
  await page.keyboard.press('Escape')
  const stillOpen = async () => (await readRuns(page, [], true)).filter((r) => r.painted && shown.includes(r.text)).length
  await expect.poll(stillOpen, { message: 'Escape left the reason open' }).toBe(0)
  await frames(page, 40) // well past the sheet's 140ms leave
  expect(await stillOpen(), 'the reason came back while focus stayed on its sentence').toBe(0)
  await expect(sheet, 'Escape closed the sheet along with the reason').toBeVisible()
})

/* ---- Sales Speed (4.8). The section is read as text runs in rows, so the cells' markup is the builder's. */
type Cell = { text: string; right: number }
const speedRows = (sheet: Locator): Promise<Cell[][]> =>
  sheet.getByRole('region', { name: 'Sales Speed', exact: true }).evaluate((root) => {
    const cells: Array<{ text: string; left: number; right: number; mid: number }> = []
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    for (let n = walk.nextNode(); n !== null; n = walk.nextNode()) {
      const text = (n.textContent ?? '').replace(/\s+/g, ' ').trim()
      if (text === '' || n.parentElement?.closest('h1, h2, h3, h4, h5, h6') != null) continue
      const range = document.createRange()
      range.selectNodeContents(n)
      const r = range.getBoundingClientRect()
      if (r.width < 1) continue
      cells.push({ text, left: r.left, right: r.right, mid: (r.top + r.bottom) / 2 })
    }
    cells.sort((a, b) => a.mid - b.mid || a.left - b.left)
    const rows: Array<typeof cells> = []
    for (const cell of cells) {
      const row = rows[rows.length - 1]
      if (row !== undefined && Math.abs((row[0]?.mid ?? 0) - cell.mid) < 10) row.push(cell)
      else rows.push([cell])
    }
    return rows.map((row) => row.sort((a, b) => a.left - b.left).map((cell) => ({ text: cell.text, right: cell.right })))
  })

const dump = (rows: Cell[][]): string => rows.map((row) => row.map((cell) => cell.text).join(' | ')).join(' / ')

for (const [name, label, step] of [['a slab that sold', LABEL.terapagos, 'PSA 8'], ['a slab that never sold', LABEL.mew, 'SGC 8']] as const) {
  test(`Sales Speed heads its count column "Sales" and says Velocity nowhere, for ${name}`, async ({ page }) => {
    const sheet = await openSheet(page, 1440, label, step)
    const rows = await speedRows(sheet)
    expect(rows.length, `Sales Speed is a heading row and five windows: ${dump(rows)}`).toBe(6)
    expect(rows[0]?.[1]?.text, `the count column's heading, in: ${dump(rows.slice(0, 1))}`).toBe('Sales')
    expect(await everything(page), 'Velocity is on the page').not.toMatch(/velocity/i)
  })
}

test('Sales Speed lists the five windows Card Ladder sends, in order, and no 7-day window', async ({ page }) => {
  const sheet = await openSheet(page)
  const rows = await speedRows(sheet)
  expect(rows.slice(1).map((row) => row[0]?.text.toLowerCase()), 'the window labels').toEqual(['two weeks', 'one month', 'three months', 'six months', 'one year'])
  expect(await sheet.innerText(), 'the sheet invents a 7-day window').not.toMatch(/\b(7|seven)[- ]?days?\b|\b(1|one) week\b/i)
})

for (const width of [1440, 820]) {
  test(`the numbers in Sales Speed line up under their headings, at ${width}`, async ({ page }) => {
    const sheet = await openSheet(page, width)
    const [head, ...windows] = await speedRows(sheet)
    expect(head?.length, 'the heading row has a window, a count and an average price').toBe(3)
    expect(windows.length, 'five windows').toBe(5)
    /* The right edge of the text, as the ledger's own number case reads it: a cell can be wider than its figure. */
    const off: string[] = []
    for (const row of windows) {
      for (const col of [1, 2]) {
        const delta = (row[col]?.right ?? Number.NaN) - (head?.[col]?.right ?? Number.NaN)
        if (!(Math.abs(delta) <= 1)) off.push(`${row[0]?.text}: "${row[col]?.text}" ends ${delta.toFixed(1)}px from the right edge of "${head?.[col]?.text}"`)
      }
    }
    expect(off).toEqual([])
  })
}

/* ---- the platform of a sale (4.8). `slabDetailOf` gives the sales a platform but the third, which carries none. */
test('each sale at the grade shows its platform, and a sale with none shows none and no stray "on"', async ({ page }) => {
  const sheet = await openSheet(page)
  const sales = sheet.getByRole('region', { name: 'Sales at the Grade', exact: true }).getByRole('listitem')
  await expect(sales, 'the newest five sales').toHaveCount(5)
  const platforms = [...new Set(SLAB_SALE_PLATFORMS.filter((p): p is string => p !== null))]
  for (let sale = 0; sale < 5; sale++) {
    const text = (await sales.nth(sale).innerText()).replace(/\s+/g, ' ')
    expect(text, `row ${sale + 1} is not the sale it should be`).toContain((400 - sale * 6).toFixed(2))
    const own = SLAB_SALE_PLATFORMS[sale] ?? null
    expect(platforms.filter((name) => text.includes(name)), `row ${sale + 1} shows ${own === null ? 'a platform it does not have' : 'the wrong platform'}: ${text}`).toEqual(own === null ? [] : [own])
    if (own === null) expect(text, `row ${sale + 1} has no platform but reads "on": ${text}`).not.toMatch(/\bon\b/i)
  }
})
