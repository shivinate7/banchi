// Protects: no user-visible string on a screen speaks in the first person (R4, R4a), and every label, heading, button, tab, nav link, column header and chip takes Chicago Title Case (R5).
// Governs: DESIGN.md "Copy rules" (R4, R4a, R5), D196, D284, D173
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { card, sealEveryTest } from './shell'
import { POPULATED_ROUTE_SEEDS } from './routeFixtures'
import { sweepEveryRoute } from './routeSweep'
import { setViewport } from './phoneSwitch'
import { casingProblems, isSentence, isSpokenSentences, labelsOf, stripTyped, voiceHits } from './copyRules'

/* ONE SWEEP, TWO CHECKS (D284, the shape `text-checks.spec.ts` set). Each screen is opened ONCE by
 * `routeSweep.ts:sweepEveryRoute`, the same owner routes and the same populated store the text checks
 * read. The Fulfiller's `#/fulfillment` is NOT in that sweep (`routeExclusions.ts` excludes it for the
 * text checks), so it is read here after the sweep, at 1440 only. The kit, `#/gallery`, stays out.
 *
 * WHAT IS READ. Each screen's landing state, as the browser draws it: every rendered text node
 * (sidebar, bars and view), plus every rendered `aria-label`, `title`, `placeholder` and `alt`. A control's
 * labels are every line that carries a letter, is not a key cap and is not a sentence (`copyRules.ts:labelsOf`), so a tile's
 * figure above its label is skipped, and a stat label (`dt`) is read as a label. Four states the landing
 * sweep never builds are read after it (the two Review states and the two Pricing send states, see
 * `MATCH_SWEEP`). A sheet,
 * modal, toast or palette is NOT opened, so its copy is not read. Key caps (`kbd`, the chord letters the
 * rail draws) and machine strings (`.bn-mono`, `code`) are NOT prose, so the voice check skips them.
 *
 * THE RULES LIVE IN `copyRules.ts`, one home. The browser sends raw strings in; Node classifies them.
 *
 *   copy-voice   R4, R4a. A visible line or an attribute holds "I", "my", "me" or "mine" as a whole word.
 *                Pending list `copy-voice-allow.json`: route -> finding -> lane.
 *   copy-casing  R5. A heading, title, button, tab, radio option, nav link, column header or chip is not
 *                Chicago Title Case. Skipped: prose (text nodes and description lines), anything inside `.bn-mono`,
 *                `code` or `kbd`, anything CSS draws in uppercase, a value under a `data-typed` marker, and numbers or units.
 *                Pending list `copy-casing-allow.json`: route -> finding -> lane.
 *
 * A PENDING ENTRY EXCUSES ONE FINDING AND NO OTHER, and an entry that matches nothing this run is STALE
 * and red until deleted, so each list only shrinks. Both lists start EMPTY: the sweep in a later lane
 * fixes the strings, not the list.
 *
 * THE RECEIPT. Every run writes `.serve/copy-checks.json`: the offender counts, the ten most common
 * texts, and the full casing list. It gates nothing. It is what a reader needs to count the work.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const RECEIPT_PATH = resolve(ROOT, '.serve', 'copy-checks.json')

/** The one route the owner sweep does not read, opened here by hash. */
const FULFILLER = '#/fulfillment'
/** A floor on how much casing text the sweep found, so an empty read cannot pass green. */
const CASING_FLOOR = 20

type Allow = Record<string, Record<string, string>>

function readAllow(name: string): Allow {
  const { _about, ...rest } = JSON.parse(readFileSync(resolve(HERE, name), 'utf8')) as Allow & { _about?: string }
  void _about
  return rest
}

interface Attr {
  tag: string
  attr: string
  value: string
}

interface Casing {
  role: string
  // The control's visible lines, in order, as the browser draws them (innerText split on newlines, blanks dropped).
  lines: string[]
  // The text of each key cap (`kbd`) inside the control. A key cap is never the label (`H` before `Set hint`).
  keyCaps: string[]
  // The accessible name, read when no line is a label (an icon control with no visible text of its own).
  aria: string
  mono: boolean
  upper: boolean
  typed: boolean
  // The text of each data-typed element inside this control. That text is taken out of the label before the check.
  marked: string[]
}

interface CopyScan {
  /** The body's rendered text, for the "drew text" floor only. */
  text: string
  /** Each rendered text node outside key caps (`kbd`), machine strings (`.bn-mono`) and `code`. */
  prose: string[]
  attrs: Attr[]
  casing: Casing[]
}

/** Runs INSIDE the page via `page.evaluate(scanCopy)`. It closes over nothing from this file, because
 *  `page.evaluate` sends the function by `toString()`. Every inner helper is declared here for that reason. */
function scanCopy(): CopyScan {
  const shown = (el: Element): boolean => {
    for (let node: Element | null = el; node; node = node.parentElement) {
      const style = getComputedStyle(node)
      if (style.display === 'none' || style.visibility === 'hidden') return false
    }
    return el.getClientRects().length > 0
  }

  const roleOf = (el: Element): string | null => {
    const tag = el.tagName.toLowerCase()
    const role = el.getAttribute('role')
    if (el.matches('a.bn-nav-link')) return 'nav link'
    if (tag === 'a') return 'icon link'
    if (tag === 'th') return 'column header'
    if (role === 'tab') return 'tab'
    if (role === 'radio') return 'option'
    if (tag === 'button' || role === 'button') return 'button'
    if (tag === 'h1') return 'page title'
    if (tag === 'h2' || tag === 'h3') return 'heading'
    if (tag === 'dt') return 'stat label'
    if (el.matches('[class*="title"]')) return 'title'
    if (el.matches('[class*="chip"]')) return 'chip'
    return null
  }

  // THE VISIBLE LINES, WALKED. innerText glues inline siblings that have no whitespace between them (`SV commons`
  // then `Section 1` read as `SV commonsSection 1`), so this walk adds a space at each inline edge and a line break
  // at each block edge, the way innerText breaks lines, and skips what is not drawn.
  const linesOf = (root: HTMLElement): string[] => {
    let text = ''
    const walk = (node: Node): void => {
      if (node.nodeType === Node.TEXT_NODE) {
        text += node.textContent ?? ''
        return
      }
      if (!(node instanceof HTMLElement)) return
      // SPOKEN-ONLY TEXT AND DATA VALUES ARE NOT LABEL LINES: `.bn-sr` is read aloud and never drawn (a section title's count
      // clause), and `data-value` marks a figure beside a label (a box cell's `797 stored`). Their text stays out of the lines.
      if (node.classList.contains('bn-sr') || node.hasAttribute('data-value')) return
      const style = getComputedStyle(node)
      if (style.display === 'none' || style.visibility === 'hidden') return
      if (node.tagName === 'BR') {
        text += '\n'
        return
      }
      // innerText breaks a line only at block-level boxes, so every inline-level display (inline, inline-block, inline-flex) takes a space.
      const edge = style.display.startsWith('inline') || style.display === 'contents' ? ' ' : '\n'
      text += edge
      node.childNodes.forEach(walk)
      text += edge
    }
    walk(root)
    return text.split('\n').map((line) => line.replace(/\s+/g, ' ').trim()).filter((line) => line !== '')
  }

  const attrs: Attr[] = []
  for (const el of Array.from(document.querySelectorAll('[aria-label], [title], [placeholder], [alt]'))) {
    if (!shown(el)) continue
    for (const attr of ['aria-label', 'title', 'placeholder', 'alt']) {
      const value = (el.getAttribute(attr) ?? '').trim()
      if (value !== '') attrs.push({ tag: el.tagName.toLowerCase(), attr, value })
    }
  }

  const casing: Casing[] = []
  // THE ICON LINK. An icon control drawn as a link (`IconButton` with an `href`, such as the Fulfiller's
  // `Cards to pull` on Orders) is an `<a>`, not a button, so the list below must name it too.
  const candidates = document.querySelectorAll(
    'a.bn-nav-link, a[aria-label], th, [role="tab"], [role="radio"], button, [role="button"], h1, h2, h3, dt, [class*="title"], [class*="chip"]',
  )
  for (const el of Array.from(candidates)) {
    const role = roleOf(el)
    if (role === null || !shown(el)) continue
    // THE LINES AND THE KEY CAPS ARE SENT; Node picks the label (`copyRules.ts:labelsOf`). A tile draws its figure
    // above its label, and a row draws its key cap before its name, so the first line is not always the label.
    const lines = linesOf(el as HTMLElement)
    const keyCaps = Array.from(el.querySelectorAll('kbd'), (key) => (key.textContent ?? '').replace(/\s+/g, ' ').trim()).filter((key) => key !== '')
    casing.push({
      role,
      lines,
      keyCaps,
      aria: (el.getAttribute('aria-label') ?? '').trim(),
      mono: el.closest('.bn-mono, code, kbd') !== null,
      upper: getComputedStyle(el).textTransform === 'uppercase',
      typed: el.matches('[data-typed]'),
      marked: Array.from(el.querySelectorAll('[data-typed]'), (m) => (m.textContent ?? '').replace(/\s+/g, ' ').trim()),
    })
  }

  // THE ICON TIP. An icon control's visible label is its `.bn-icon-tip`, a tooltip portaled into <body>. It
  // is always mounted and hidden until a hover, so the `shown` test above never reaches it. The control's
  // accessible name can differ from its label (`name` overrides the label), so the tip is read on its own.
  // Its key cap (`kbd`) is not part of the label.
  for (const tip of Array.from(document.querySelectorAll('.bn-icon-tip'))) {
    const text = Array.from(tip.childNodes)
      .filter((node) => !(node instanceof HTMLElement && node.tagName === 'KBD'))
      .map((node) => node.textContent ?? '')
      .join('')
      .replace(/\s+/g, ' ')
      .trim()
    if (text !== '') casing.push({ role: 'tooltip', lines: [text], keyCaps: [], aria: '', mono: false, upper: getComputedStyle(tip).textTransform === 'uppercase', typed: tip.matches('[data-typed]'), marked: [] })
  }

  const prose: string[] = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement
    if (!parent || parent.closest('script, style, kbd, code, .bn-mono') !== null || !shown(parent)) continue
    const value = (node.textContent ?? '').replace(/\s+/g, ' ').trim()
    if (value !== '') prose.push(value)
  }

  return { text: document.body.innerText, prose, attrs, casing }
}

/** Runs INSIDE the page. Paints one first-person line into the view (the mutation for copy-voice). */
function paintVoiceDefect(): void {
  const line = document.createElement('p')
  line.textContent = 'Under my price'
  document.querySelector('.bn-view')?.appendChild(line)
}

/** Runs INSIDE the page. Paints one lower-case button into the view (the mutation for copy-casing). */
function paintCasingDefect(): void {
  const button = document.createElement('button')
  button.textContent = 'Show all'
  document.querySelector('.bn-view')?.appendChild(button)
}

/** Runs INSIDE the page. Paints a visible two-sentence button label (must fail) and an icon button whose spoken name is
 *  two sentences with no visible text (must pass). The mutation for the spoken-name rule. */
function paintSentenceDefect(): void {
  const visible = document.createElement('button')
  visible.textContent = 'Mark sold. Undo'
  const icon = document.createElement('button')
  icon.setAttribute('aria-label', 'Order: High to low. Press to reverse.')
  document.querySelector('.bn-view')?.append(visible, icon)
}

/** Runs INSIDE the page. Paints a button that holds a typed box name and one lower-case word (the mutation for the
 *  typed-descendant rule). The name is taken out; the lower-case word must still go red. */
function paintTypedDefect(): void {
  const button = document.createElement('button')
  const name = document.createElement('span')
  name.setAttribute('data-typed', '')
  name.textContent = 'SV commons'
  button.append(name, ' card')
  document.querySelector('.bn-view')?.appendChild(button)
}

/** Waits until the body's text holds still, for four samples 150ms apart. Fulfiller's screen has no
 *  `.bn-shell`, so `routeSweep.ts:openSettled` cannot be used for it. */
async function settleBody(page: Page, route: string): Promise<void> {
  await page.goto(`/${route}`)
  await settleFonts(page)
  const deadline = Date.now() + 10_000
  let previous = ''
  let stable = 0
  while (Date.now() < deadline) {
    await new Promise((resolveWait) => setTimeout(resolveWait, 150)) // keep: the sample interval of the settle wait
    const next = await page.evaluate(() => document.body.innerText)
    stable = next === previous ? stable + 1 : 0
    previous = next
    if (stable >= 4 && next.trim() !== '') return
  }
  throw new Error(`${route}: the body never settled to readable text`)
}

/* THE STATES THE LANDING SWEEP NEVER BUILDS. Each is opened by its own stubs, after the sweep, and read by the same
 * classifier under its screen's route, so the allow lists apply to it too. Each one is asserted built before it is
 * read, so a green read cannot be a state that never drew. Review: the matched figure above zero, which makes its
 * tile a button (`ReviewBand`'s `Stat press`), and the empty queue, which draws `All caught up` and its two buttons.
 * Pricing: a run with two SKUs and copies to send, which draws the press `Send all 2 SKUs`, and a send that the
 * server says can be taken back, which draws `Take N copies back`. */
const MATCH_SWEEP = /\/pipeline\/match\/sweep(\?.*)?$/
const QUEUES = /\/queues$/
const PRICING_WORKLIST = /\/pipeline\/pricing/
const SENDS = /\/pipeline\/sends$/
const RUN = '2026-09-24-box7-01'

const answer = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

const NO_SWEEP = { on: true, running: false, blocked: null, aside: 0, matched: 0, matched_here: 0, matched_keys: [], paid: 0, paid_keys: [], unread: 0, unhinted: 0 }
const SENDS_NONE = { sends: [], unconfirmed: { copies: 0, stamps: [] }, due: false, check_at: null, now: '2026-09-24T12:00:00+00:00' }

/** One SKU of the worklist, in the shape `Pricing` reads. A worklist of one run, two SKUs, three copies each. */
function worklistSku(sku: string, name: string) {
  return {
    sku,
    game: 'pokemon',
    row: {
      'TCGplayer Id': sku,
      'Product Line': 'Pokemon',
      'Set Name': 'SV: Prismatic Evolutions',
      'Product Name': name,
      Title: '',
      Number: '161/159',
      Rarity: 'Secret Rare',
      Condition: 'Near Mint Holofoil',
      'TCG Market Price': '22.03',
      'TCG Direct Low': '21.98',
      'TCG Low Price With Shipping': '22.98',
      'TCG Low Price': '21.98',
      'Total Quantity': '0',
      'Add to Quantity': '0',
      'TCG Marketplace Price': '',
      'Photo URL': '',
    },
    bucket: 'listable',
    copies: 3,
    add_to_quantity: 3,
    backstock: 0,
    live_before: 0,
    committed: 0,
    copies_out: 0,
    nothing_to_add: null,
    at_cap: false,
    condition: 'Near Mint Holofoil',
    set_name: 'SV: Prismatic Evolutions',
    name,
    image_url: null,
    snap: { market: '22.03', direct_low: null, low: '21.98', low_with_shipping: '22.98', now: null },
    presets: { market_match: '22.03', market_undercut_5: '20.93', low_undercut_1: '21.76' },
    rule_price: '22.03',
    positions: [
      { box: 7, index: 1, label: 'Box 7, Section 1, Card 1' },
      { box: 7, index: 2, label: 'Box 7, Section 1, Card 2' },
      { box: 7, index: 3, label: 'Box 7, Section 1, Card 3' },
    ],
    listing: null,
    in: [{ run: RUN, add_to_quantity: 3 }],
    claimed_add: 3,
    over_cap: false,
  }
}

/** A worklist row whose live copies sit on the store at `now`. A `capped` row adds no copies (`at_cap`), so a price typed on it
 *  is a price change; an uncapped row adds copies, so a changed price moves its live copies. */
function liveSku(sku: string, name: string, live: number, now: string, capped: boolean) {
  return {
    ...worklistSku(sku, name),
    listing: { pushed: live, staged: 0, live },
    snap: { market: '10.00', direct_low: null, low: '9.50', low_with_shipping: '10.50', now },
    ...(capped ? { at_cap: true, add_to_quantity: 0, live_before: live, nothing_to_add: 'Every copy in this run is already listed or has left the box.' } : {}),
  }
}

/** The worklist over these rows: one run when there are rows, and none when there are not (the screen then draws its
 *  own `Price your live listings` empty state). */
function worklistOf(skus: readonly unknown[]) {
  const run = { run: RUN, path: `/tmp/runs/${RUN}`, box: 7, box_name: 'Riftbound epics', created_at: null, live: false, phase: 'emit', joined: true, collected: true, counts: { skus: skus.length, cards_in: 3 * skus.length, queued_main: 0, queued_parked: 0 }, batch_ids: [], usage: {} }
  return {
    runs: skus.length > 0 ? [run] : [],
    roster: skus.length > 0 ? [{ ...run, owes: ['never emitted'], owed: [{ code: 'never_emitted', count: null }], open: true, unsent: 0 }] : [],
    skus,
    written_at: {},
    skipped: [],
    asked: [],
    threshold: '0.40',
    floor: '0.40',
  }
}

/** The stored answers, by SKU, in the corpus's own shape. A press that moves live copies reads these. */
async function stubCorpus(page: Page, prices: Record<string, string>): Promise<void> {
  await page.route(/\/pricing$/, (route) => {
    if (route.request().url().includes('/pipeline/')) return route.fallback()
    if (route.request().method() === 'PUT') return route.fulfill(answer({ ok: true, written: '/tmp/prices.json', answers: 0, revision: 'rev-2' }))
    const skus = Object.fromEntries(Object.entries(prices).map(([sku, value]) => [sku, { value }]))
    return route.fulfill(answer({ corpus: { version: 1, policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' } }, skus }, path: '/tmp/prices.json', revision: 'rev-1' }))
  })
}

/** Types one price into a row's price field and leaves it, as the owner does. A price typed this visit is what a change counts. */
async function typePrice(page: Page, name: string, price: string): Promise<void> {
  const field = page.getByRole('textbox', { name: `Price for ${name}` })
  await field.fill(price)
  await field.press('Tab')
}

function worklist() {
  const run = { run: RUN, path: `/tmp/runs/${RUN}`, box: 7, box_name: 'Riftbound epics', created_at: null, live: false, phase: 'emit', joined: true, collected: true, counts: { skus: 2, cards_in: 6, queued_main: 0, queued_parked: 0 }, batch_ids: [], usage: {} }
  return {
    runs: [run],
    roster: [{ ...run, owes: ['never emitted'], owed: [{ code: 'never_emitted', count: null }], open: true, unsent: 0 }],
    skus: [worklistSku('8608859', 'Articuno - 161/159'), worklistSku('8608860', 'Articuno - 162/159')],
    written_at: {},
    skipped: [],
    asked: [],
    threshold: '0.40',
    floor: '0.40',
  }
}

/** One send the server says can be taken back: a check ran past the wait, and six copies were not found. */
const TAKEABLE = {
  stamp: '20260924-120000',
  kind: 'send',
  state: 'short',
  at: '2026-09-24T12:00:00+00:00',
  copies: 6,
  prices: 0,
  price_check: null,
  rows: 2,
  published_at: '2026-09-24T12:00:05+00:00',
  check_after: '2026-09-24T12:15:05+00:00',
  checked_at: '2026-09-24T12:18:00+00:00',
  check: { export: 'live.csv', found: 0, expected: 6, missing: [] },
  trimmed: [],
  trimmed_copies: 0,
  accepted: 2,
  turned_away: 0,
  failure: null,
  unknown: null,
  held: false,
  staged: false,
  takeable: 6,
  take_back_after: null,
  files: ['import.csv'],
  taken_back_at: null,
  warning: null,
  prices_left: [],
  moves: [],
}

async function visit(page: Page, route: string): Promise<void> {
  await page.goto('/')
  await settleBody(page, route)
}

interface Finding {
  check: 'copy-voice' | 'copy-casing'
  route: string
  id: string
  text: string
  kind: string
  detail: string
}

sealEveryTest({ store: true, cards: 122 })

test('one sweep: every screen is read once by the copy-voice and copy-casing checks', async ({ page }) => {
  // THE SWEEP READS EVERY SCREEN AND EVERY STATE, one after another. On the owner's loaded machine (load average near 150) it took
  // 28 to 49 seconds, past the 30-second default, so the case gets room of its own.
  test.setTimeout(180_000)
  const voiceAllow = readAllow('copy-voice-allow.json')
  const casingAllow = readAllow('copy-casing-allow.json')
  const voiceUsed = new Set<string>()
  const casingUsed = new Set<string>()
  const findings: Finding[] = []
  const reads: Array<{ route: string; words: number; casing: number }> = []

  const read = (route: string, scan: CopyScan): void => {
    expect(scan.text.trim(), `${route} drew no text, so nothing was read`).not.toBe('')
    reads.push({ route, words: scan.text.split(/\s+/).length, casing: scan.casing.length })
    const seen = new Set<string>()

    const voice = (id: string, finding: Omit<Finding, 'check' | 'route' | 'id'>): void => {
      if (seen.has(`v|${id}`)) return
      seen.add(`v|${id}`)
      if (voiceAllow[route]?.[id] !== undefined) {
        voiceUsed.add(`${route}\u0000${id}`)
        return
      }
      findings.push({ check: 'copy-voice', route, id, ...finding })
    }
    for (const text of scan.prose) {
      for (const word of voiceHits(text)) {
        voice(`text ${word} ${JSON.stringify(text)}`, { text, kind: 'text', detail: `the word "${word}" in the rendered text` })
      }
    }
    for (const one of scan.attrs) {
      for (const word of voiceHits(one.value)) {
        voice(`${one.attr} ${word} ${JSON.stringify(one.value)}`, {
          text: one.value,
          kind: one.attr,
          detail: `the word "${word}" in the ${one.attr} of a <${one.tag}>`,
        })
      }
    }

    for (const one of scan.casing) {
      if (one.mono || one.upper || one.typed) continue
      // THE LABELS ARE THE CONTROL'S LABEL LINES (`copyRules.ts:labelsOf`): every lettered line that is not a sentence, so
      // a second label (`New` over `Set Hint`) is graded too. A control with none is a spoken name, read as its accessible name.
      const labels = labelsOf(one.lines, one.keyCaps)
      const spoken = labels.length === 0
      for (const text of spoken ? [one.aria] : labels) {
        if (text === '') continue
        const checked = stripTyped(text, one.marked)
        if (checked === '' || (spoken && isSpokenSentences(checked))) continue
        // A HEADING (h2, h3) OR A TITLE MAY BE A SENTENCE: an empty state or a greeting. A control, and a page title (h1),
        // is a label whatever its ending, so `Cards to pull.` on a control or an h1 is still checked.
        if ((one.role === 'heading' || one.role === 'title') && isSentence(checked)) continue
        const problems = casingProblems(checked)
        if (problems.length === 0) continue
        // A FINDING IS KEYED BY ITS TEXT, not its role: a control's label often shows twice (its tip and its
        // accessible name), and one string is one offender.
        const id = JSON.stringify(text)
        if (seen.has(`c|${id}`)) continue
        seen.add(`c|${id}`)
        if (casingAllow[route]?.[id] !== undefined) {
          casingUsed.add(`${route}\u0000${id}`)
          continue
        }
        findings.push({ check: 'copy-casing', route, id, text, kind: one.role, detail: problems.join('; ') })
      }
    }
  }

  const swept = await sweepEveryRoute(page, async (route) => {
    // THE MUTATION PROOF, one variable per check, as `text-checks.spec.ts` does. Set it to a route's hash
    // and that route gets the check's own defect, painted into `.bn-view` through `page.evaluate`, so
    // only that check goes red on it. From `app/`:
    //   COPY_VOICE_MUTATE='#/pricing'  npx playwright test tests/copy-checks.spec.ts   (a first-person line)
    //   COPY_CASING_MUTATE='#/'        npx playwright test tests/copy-checks.spec.ts   (a lower-case button)
    //   COPY_SENTENCE_MUTATE='#/inventory' npx playwright test tests/copy-checks.spec.ts   (a visible two-sentence label must fail; a spoken one must pass)
    //   COPY_TYPED_MUTATE='#/'         npx playwright test tests/copy-checks.spec.ts   (a typed name beside a lower-case word)
    if (process.env.COPY_VOICE_MUTATE === route) await page.evaluate(paintVoiceDefect)
    if (process.env.COPY_CASING_MUTATE === route) await page.evaluate(paintCasingDefect)
    if (process.env.COPY_TYPED_MUTATE === route) await page.evaluate(paintTypedDefect)
    if (process.env.COPY_SENTENCE_MUTATE === route) await page.evaluate(paintSentenceDefect)
    read(route, await page.evaluate(scanCopy))
  })

  await setViewport(page, { width: 1440, height: 1000 })
  await settleBody(page, FULFILLER)
  read(FULFILLER, await page.evaluate(scanCopy))
  swept.add(FULFILLER)

  // THE REVIEW STATE WITH A MATCHED FIGURE: its tile is a button, so its label is read. Asserted drawn first.
  await setViewport(page, { width: 1440, height: 1000 })
  // EVERY COUNT ABOVE ZERO: the three tiles are buttons, so their labels are read; then the matched tile opens its sheet,
  // whose title (`N matched free`) is read too. Each tile and the sheet is asserted drawn first.
  await page.route(MATCH_SWEEP, (route) =>
    route.fulfill(answer({ ...NO_SWEEP, matched: 2, matched_here: 2, matched_keys: ['3/1', '3/2'], paid: 2, paid_keys: ['3/3', '3/4'], unread: 3 })),
  )
  await visit(page, '#/review')
  // Case-insensitive on purpose: the copy sweep is the casing guard; these specs check behaviour.
  await expect(page.locator('.review-band-count', { hasText: /matched free/i }).getByRole('button'), 'the matched tile is a button').toHaveCount(1)
  await expect(page.locator('.review-band-count', { hasText: /waiting for a paid look/i }).getByRole('button'), 'the paid tile is a button').toHaveCount(1)
  await expect(page.locator('.review-band-count', { hasText: /not looked at yet/i }).getByRole('button'), 'the unread tile is a button').toHaveCount(1)
  read('#/review', await page.evaluate(scanCopy))
  await page.locator('.review-band-count', { hasText: /matched free/i }).getByRole('button').click()
  await expect(page.getByRole('dialog'), 'the matched sheet opens').toBeVisible()
  read('#/review', await page.evaluate(scanCopy))

  // THE SHELF'S LIFT BAR: a section lifted in Layout mode draws its scope picker (`This section`, `This and the next`,
  // `The whole box`, `Some Cards`). The grip is pressed from the keyboard, so the bar opens the same way for every reader.
  // THE SHELF READS `/boxes?...` (WITH A QUERY), which the shell's `/boxes$` stub does not answer. One box with two sections
  // gives the bar both range scopes (`This and the next`, `The whole box`).
  await page.route(/\/boxes\?.*$/, (route) =>
    route.fulfill(
      answer({
        boxes: [
          {
            box: 2,
            bid: 12,
            name: 'SV commons',
            sections: [1, 2],
            state: 'open',
            capacity: 100,
            fill: 4,
            next_index: 5,
            cards: 4,
            on_hand: 3,
            sold: 1,
            retired: 0,
            moved: 0,
            listed: 0,
            sections_detail: [
              { section: 1, start: 1, end: 2, count: 2, name: 'Commons' },
              { section: 2, start: 3, end: 4, count: 2, name: 'Uncommons' },
            ],
          },
        ],
        facets: { games: [], sets: {}, rarities: {} },
      }),
    ),
  )
  await visit(page, '#/inventory?view=shelf')
  await page.getByRole('button', { name: 'Layout' }).click()
  const grip = page.getByRole('button', { name: /^(Drag|Move) section/ }).first()
  await grip.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.shelf-lift'), 'the lift bar is drawn once a section is lifted').toBeVisible()
  read('#/inventory', await page.evaluate(scanCopy))
  await page.keyboard.press('Escape')

  // THE REVIEW BAND'S UNHINTED LINE: two cards with no set hint. Its health button is read, then its sheet opens and is read.
  await page.route(MATCH_SWEEP, (route) => route.fulfill(answer({ ...NO_SWEEP, unhinted: 2 })))
  await visit(page, '#/review')
  const needSet = page.locator('.review-band-health').getByRole('button', { name: /need a set named/i })
  await expect(needSet, 'the unhinted line is a button').toHaveCount(1)
  read('#/review', await page.evaluate(scanCopy))
  await needSet.click()
  await expect(page.getByRole('dialog'), 'the unhinted sheet opens').toBeVisible()
  read('#/review', await page.evaluate(scanCopy))

  // THE PRICE FACTS SALES LABELS: the product view with sales saved, so the sales grid draws its five labels.
  await page.route(/\/pipeline\/price-facts/, (route) =>
    route.fulfill(
      answer({
        sku: '9191486',
        name: 'Volcanion',
        at: 1,
        through: '2026-10-01',
        prices: null,
        shelf: null,
        days: [
          ['2026-09-30', 2, 2, '14.00', '17.00', '16.00'],
          ['2026-10-01', 1, 1, '15.00', '15.00', '15.00'],
        ],
        facts: { sold_30d: 3, avg_30d: '15.67', low_30d: '14.00', high_30d: '17.00', sold_7d: 1, avg_7d: '15.00', low_7d: '15.00', high_7d: '15.00', best_day: ['2026-09-30', 2] },
      }),
    ),
  )
  await visit(page, '#/product?sku=9191486')
  await expect(page.locator('.pricefacts-grid'), 'the sales grid is drawn').toBeVisible()
  read('#/product?sku=9191486', await page.evaluate(scanCopy))

  // THE CODES LOT LINE: one built lot, so the meta reads `N lots built` rather than `No Lots Built Yet`.
  await page.route(/\/codes\/lots$/, (route) =>
    route.fulfill(
      answer({
        lots: [
          {
            lot_id: 'LOT-1',
            scope: 'all',
            delivery: 'mail',
            venue: 'Mail',
            box: null,
            count: 2,
            by_product: [{ product: 'booster', display: 'Booster pack', premium: false, count: 2 }],
            sets: [],
            built_at: '2026-10-01T10:00:00Z',
          },
        ],
      }),
    ),
  )
  await visit(page, '#/codes')
  read('#/codes', await page.evaluate(scanCopy))

  // THE CLAIM EDITOR ON A CARD: the walk's first card, Actions, then Correct. The sheet's field labels are read.
  await visit(page, '#/inventory')
  // The walk's section folds start shut, and a row exists only inside an open fold: open every shut one first.
  const shutFold = page.locator('.browse-sectfold[aria-expanded="false"]')
  for (let guard = 0; guard < 40 && (await shutFold.count()) > 0; guard += 1) await shutFold.first().click()
  await page.locator('.browse-row').first().click()
  await page.getByRole('button', { name: 'Actions' }).click()
  await page.getByRole('menuitem', { name: 'Correct' }).click()
  await expect(page.getByRole('dialog'), 'the correct-claims sheet opens').toBeVisible()
  read('#/inventory', await page.evaluate(scanCopy))
  await page.keyboard.press('Escape')

  // THE CLAIM EDITOR ON A BOX: Manage, then Claims. The box's set-claims editor is read.
  await visit(page, '#/inventory')
  await page.getByRole('button', { name: 'Manage' }).click()
  await page.getByRole('button', { name: /^Claims/ }).click()
  await expect(page.getByRole('dialog'), 'the set-claims sheet opens').toBeVisible()
  read('#/inventory', await page.evaluate(scanCopy))

  // THE REVIEW STATE WITH AN EMPTY QUEUE: `All caught up`, and its two buttons. Asserted drawn first.
  await page.route(QUEUES, (route) => route.fulfill(answer({ review: [], parked: [] })))
  await page.route(MATCH_SWEEP, (route) => route.fulfill(answer(NO_SWEEP)))
  await visit(page, '#/review')
  await expect(page.locator('.review-done'), 'the empty queue draws its card').toBeVisible()
  read('#/review', await page.evaluate(scanCopy))

  // THE PRICING STATE WITH A RUN TO SEND: the press names all two SKUs. Asserted drawn first.
  await page.route(PRICING_WORKLIST, (route) => route.fulfill(answer(worklist())))
  await page.route(SENDS, (route) => route.fulfill(answer(SENDS_NONE)))
  await page.route(/\/pipeline\/runs\/[^/]+$/, (route) =>
    route.fulfill(
      answer({ run: RUN, path: `/tmp/runs/${RUN}`, box: 7, box_name: 'Riftbound epics', live: false, phase: 'emit', joined: true, collected: true, counts: { skus: 2, cards_in: 6, queued_main: 0, queued_parked: 0 }, batch_ids: [], usage: {}, console: '', files: [], manifest: {} }),
    ),
  )
  await visit(page, '#/pricing')
  await expect(page.getByRole('button', { name: /^Send all 2 SKUs/i }), 'the send press names two SKUs').toBeVisible()
  read('#/pricing', await page.evaluate(scanCopy))

  // THE PRICING STATE WITH A TAKEABLE SEND: the card offers `Take N copies back`. Asserted drawn first.
  await page.route(SENDS, (route) => route.fulfill(answer({ ...SENDS_NONE, sends: [TAKEABLE] })))
  await visit(page, '#/pricing')
  await expect(page.getByRole('button', { name: /^Take \d+ copies back$/i }), 'the takeable send offers its take back').toBeVisible()
  read('#/pricing', await page.evaluate(scanCopy))

  // THE PRICE-CHANGE PRESS: two rows at cap carry live copies, and the owner types a new price on each this visit (a change
  // needs a typed price). The press names the SKUs and the changes as one label, read whole. Asserted drawn first.
  await page.route(SENDS, (route) => route.fulfill(answer(SENDS_NONE)))
  await page.route(PRICING_WORKLIST, (route) =>
    route.fulfill(
      answer(worklistOf([liveSku('8608459', 'Dunsparce', 2, '9.99', true), liveSku('8608659', 'Wattrel', 1, '4.00', true), worklistSku('8608559', 'Riftbound Ember'), worklistSku('8608560', 'Riftbound Tide')])),
    ),
  )
  await visit(page, '#/pricing')
  await typePrice(page, 'Dunsparce', '12.50')
  await typePrice(page, 'Wattrel', '5.50')
  await expect(page.getByRole('button', { name: /^Send all 2 SKUs and 2 price changes$/i }), 'the press names the two price changes').toBeVisible()
  read('#/pricing', await page.evaluate(scanCopy))

  // THE MOVES PRESS: two uncapped rows add copies over live ones at new stored prices, so the press also names the moved copies.
  await stubCorpus(page, { '8608859': '11.00', '8608959': '8.00' })
  await page.route(PRICING_WORKLIST, (route) =>
    route.fulfill(answer(worklistOf([liveSku('8608859', 'Articuno', 2, '9.99', false), liveSku('8608959', 'Kled', 3, '7.00', false)]))),
  )
  await visit(page, '#/pricing')
  await expect(page.getByRole('button', { name: /^Send all 2 SKUs, 5 live copies move to new prices$/i }), 'the press names the moved copies').toBeVisible()
  read('#/pricing', await page.evaluate(scanCopy))

  // THE EMPTY WORKLIST: nothing to price yet, and the button that opens the Live tab. Asserted drawn first.
  await page.route(PRICING_WORKLIST, (route) => route.fulfill(answer(worklistOf([]))))
  await visit(page, '#/pricing')
  await expect(page.getByRole('button', { name: /^Price your live listings$/i }), 'the empty worklist offers the Live tab').toBeVisible()
  read('#/pricing', await page.evaluate(scanCopy))

  const casingTotal = reads.reduce((sum, one) => sum + one.casing, 0)
  expect(casingTotal, `the sweep read ${casingTotal} labels, under the floor of ${CASING_FLOOR}`).toBeGreaterThan(CASING_FLOOR)

  // THE RECEIPT. Counts and the top ten, written before any assertion so a red run still leaves it.
  // One offender is one (check, route, text), however many reads saw it: a state read repeats the screen's landing copy.
  const offenders = findings.filter((one, at) => findings.findIndex((other) => other.check === one.check && other.route === one.route && other.id === one.id) === at)
  const tally = (check: Finding['check']) => {
    const mine = offenders.filter((one) => one.check === check)
    const byText = new Map<string, number>()
    for (const one of mine) byText.set(one.text, (byText.get(one.text) ?? 0) + 1)
    const top = [...byText.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 10)
    return { offenders: mine.length, texts: byText.size, top: top.map(([text, count]) => ({ text, count })), all: mine }
  }
  const voiceTally = tally('copy-voice')
  const casingTally = tally('copy-casing')
  mkdirSync(dirname(RECEIPT_PATH), { recursive: true })
  writeFileSync(
    RECEIPT_PATH,
    `${JSON.stringify(
      {
        routes: [...swept].sort(),
        voice: { offenders: voiceTally.offenders, distinctTexts: voiceTally.texts, top: voiceTally.top },
        casing: { offenders: casingTally.offenders, distinctTexts: casingTally.texts, top: casingTally.top, all: casingTally.all },
      },
      null,
      2,
    )}\n`,
  )

  for (const [check, list, allow, used] of [
    ['copy-voice', voiceTally.all, voiceAllow, voiceUsed],
    ['copy-casing', casingTally.all, casingAllow, casingUsed],
  ] as const) {
    const problems: string[] = list.map(
      (one) =>
        `[${check}] ${one.route} ${one.kind} ${JSON.stringify(one.text)}: ${one.detail}. Not on the pending list: fix the string, or add a pending entry naming the lane that owes it.`,
    )
    for (const [route, ids] of Object.entries(allow)) {
      for (const [id, lane] of Object.entries(ids)) {
        if (!swept.has(route)) {
          problems.push(`[${check}] ${route} ${id}: pending for lane ${lane}, but that route was not swept. Delete the entry.`)
        } else if (!used.has(`${route}\u0000${id}`)) {
          problems.push(`[${check}] ${route} ${id}: pending for lane ${lane}, but nothing matched it this run, so the entry is stale. Delete it.`)
        }
      }
    }
    expect.soft(problems, problems.join('\n')).toEqual([])
  }
})

/* THE CLIP CASES (copy map: Pricing at 820, and Orders' hero once the chips load). A line clips when its `scrollWidth` is
 * above its `clientWidth`: its last fact is drawn past the edge of its box, and the box hides it or cuts it to an ellipsis.
 * Each screen is opened with the populated seeds the route sweep registers, so it draws the rows the sweep reads. */
async function seedEverySweepScreen(page: Page): Promise<void> {
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
}

test.describe('clip: no fact is cut off at 1440 or 820', () => {
  for (const width of [1440, 820, 360] as const) {
    // THE PRICING LINES ARE CHECKED AT 1440 AND 820 ONLY. The Orders hero is also checked at 360, where its meta line is narrowest.
    if (width !== 360) test(`pricing: no item line clips its last fact at ${width}`, async ({ page }) => {
      await setViewport(page, { width, height: 1000 })
      await seedEverySweepScreen(page)
      await page.goto('/#/pricing')
      await settleFonts(page)
      const lines = page.locator('.pricing-meta:not(.pricing-where)')
      await expect(lines.first(), 'the item rows are drawn').toBeVisible()
      const clipped = await lines.evaluateAll((els) =>
        els
          .filter((el) => el.scrollWidth > el.clientWidth + 1)
          .map((el) => `${(el.textContent ?? '').replace(/\s+/g, ' ').trim()} (drawn ${el.scrollWidth}px, box ${el.clientWidth}px)`),
      )
      expect(clipped, 'item lines whose last fact is cut off').toEqual([])
    })

    test(`orders: the card number stays whole once the chips load at ${width}`, async ({ page }) => {
      await setViewport(page, { width, height: 1000 })
      await seedEverySweepScreen(page)
      /* THE HERO'S OWN CARD, with a printed total and the rarity and finish chips a real walk shows. The seeds' copy has no
       * printed total, so its number is short and nothing can clip. */
      await page.route(/\/inventory\/copies$/, (route) => {
        const copy = {
          ...card({ box: 3, index: 21, section: 2, card: 17, name: 'Volcanion', boxName: 'SV commons', boxTotal: 3 }),
          /* `number_display` is the server's own fold and wins over `number` and `printed_total` (`cardNumber.ts`). */
          number_display: '078/076',
          number: '078',
          printed_total: '076',
          set_hint: 'Prismatic Evolutions',
          rarity_claim: ['Common', 'Uncommon'],
          metadata_finish: 'Normal',
          /* THE LINE'S OWN SKU (`routeFixtures.ts`'s `PRODUCT_SKU`): the store is indexed by it, so another SKU leaves the hero on its fallback. */
          sku: '9191486',
        }
        /* KEYED BY THE PICK'S OWN POSITION (`routeFixtures.ts`'s `pick`: box 3, index 21), the key the store indexes the hero by. */
        return route.fulfill(answer({ cards: { '3/21': copy } }))
      })
      await page.goto('/#/orders')
      await settleFonts(page)
      /* THE REVERT PROOF. `HERO_NUMBER_REVERT=1` puts the number back under the rule that clipped it: `overflow: hidden` from
       * `.browse-hero-parts > span`, with the override that exempted it removed. The case must then go red. */
      if (process.env.HERO_NUMBER_REVERT === '1') {
        await page.addStyleTag({ content: '.browse-hero-parts > .browse-hero-number { overflow: hidden; text-overflow: ellipsis; }' })
      }
      await expect(page.locator('.orders-pick-chip'), 'the pick chip has loaded').toBeVisible()
      /* NOT `toBeVisible`: once the chips take their room the meta line can shrink to no width at all, and Playwright then
       * calls it hidden. That is the clip itself, so the check measures what the line draws against the box it has. */
      const parts = page.locator('.browse-hero-parts').first()
      await expect(parts, 'the hero meta line is in the page').toHaveCount(1)
      await expect(parts, 'the hero meta line carries the card number').toHaveAttribute('title', /078\/076/)
      const measure = await parts.evaluate((el) => ({ drawn: el.scrollWidth, box: el.clientWidth }))
      expect(measure.drawn - measure.box, `the meta line draws ${measure.drawn}px in a ${measure.box}px box, so its number, set or game is cut off`).toBeLessThanOrEqual(1)
      /* THE NUMBER ITSELF. Its span has `overflow: hidden` and shrinks inside the line, so the line can pass while the digits are cut. */
      const number = page.locator('.browse-hero-number').first()
      await expect(number, 'the card number is drawn in its own span').toHaveText('078/076')
      const digits = await number.evaluate((el) => ({ drawn: el.scrollWidth, box: el.clientWidth }))
      expect(digits.drawn - digits.box, `the card number draws ${digits.drawn}px of text in a ${digits.box}px box, so its digits are cut off`).toBeLessThanOrEqual(1)
    })
  }
})

// SPOKEN-ONLY TEXT AND DATA VALUES ARE NOT LABELS. A section title's sr-only count clause is prose the screen reader hears
// (`Head, 3 cards`), and a box cell's figure (`797 stored`) is a data value beside a label. A real label of the same shape still flags.
test.describe('reader: sr-only text and data values are not labels', () => {
  test('a screen-reader-only clause is spoken, not drawn, so it is not in the label', async ({ page }) => {
    await page.setContent('<main><button type="button"><div>Head<span class="bn-sr">, 3 cards</span></div></button></main>')
    const scan = await page.evaluate(scanCopy)
    const one = scan.casing.find((c) => c.role === 'button')
    expect(one?.lines, 'the drawn words are the label, and the spoken clause is not in it').toEqual(['Head'])
  })

  test('a data value is a figure beside a label, not a label of its own', async ({ page }) => {
    await page.setContent('<main><button type="button"><div>Box 1</div><div><span data-value="">797 stored</span></div></button></main>')
    const scan = await page.evaluate(scanCopy)
    const one = scan.casing.find((c) => c.role === 'button')
    expect(one?.lines, 'the data value is not a label line').toEqual(['Box 1'])
  })

  test('a real label of the same shape still flags, so the rule is not a blanket pass', async ({ page }) => {
    await page.setContent('<main><button type="button"><div>Box 1</div><div>797 stored</div></button></main>')
    const scan = await page.evaluate(scanCopy)
    const one = scan.casing.find((c) => c.role === 'button')
    expect(one?.lines, 'an unmarked second line is still a label line').toEqual(['Box 1', '797 stored'])
  })
})

// THE READER JOINS ADJACENT ELEMENTS WITH A SPACE. innerText glued `SV commons` and `Section 1` into one word.
test.describe('reader: adjacent elements join with a space, not glued', () => {
  test('two inline spans in an icon link read as two words', async ({ page }) => {
    await page.setContent('<main><a href="#/x" aria-label="Set"><span>SV commons</span><span>Section 1</span></a></main>')
    const scan = await page.evaluate(scanCopy)
    const link = scan.casing.find((one) => one.role === 'icon link')
    expect(link?.lines, 'the two spans are two words, not one glued word').toEqual(['SV commons Section 1'])
  })
})
