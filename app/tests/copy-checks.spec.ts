// Protects: no user-visible string on a screen speaks in the first person (R4, R4a), and every label, heading, button, tab, nav link, column header and chip takes Chicago Title Case (R5).
// Governs: DESIGN.md "Copy rules" (R4, R4a, R5), D196, D284, D173
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'
import { sweepEveryRoute } from './routeSweep'
import { setViewport } from './phoneSwitch'
import { casingProblems, isSentence, voiceHits } from './copyRules'

/* ONE SWEEP, TWO CHECKS (D284, the shape `text-checks.spec.ts` set). Each screen is opened ONCE by
 * `routeSweep.ts:sweepEveryRoute`, the same owner routes and the same populated store the text checks
 * read. The Fulfiller's `#/fulfillment` is NOT in that sweep (`routeExclusions.ts` excludes it for the
 * text checks), so it is read here after the sweep, at 1440 only. The kit, `#/gallery`, stays out.
 *
 * WHAT IS READ. Each screen's landing state, as the browser draws it: every rendered text node
 * (sidebar, bars and view), plus every rendered `aria-label`, `title`, `placeholder` and `alt`. A sheet,
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
  text: string
  mono: boolean
  upper: boolean
  typed: boolean
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
    if (el.matches('[class*="title"]')) return 'title'
    if (el.matches('[class*="chip"]')) return 'chip'
    return null
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
    'a.bn-nav-link, a[aria-label], th, [role="tab"], [role="radio"], button, [role="button"], h1, h2, h3, [class*="title"], [class*="chip"]',
  )
  for (const el of Array.from(candidates)) {
    const role = roleOf(el)
    if (role === null || !shown(el)) continue
    // THE LABEL IS THE FIRST LINE. A button or heading often carries a sentence under its name (the
    // description on a `Read a box` card). That sentence is not read for casing. It is prose, not a label, so only the first non-empty line is read.
    const inner = ((el as HTMLElement).innerText ?? '').split('\n').map((line) => line.replace(/\s+/g, ' ').trim()).find((line) => line !== '') ?? ''
    const text = inner !== '' ? inner : (el.getAttribute('aria-label') ?? '').trim()
    if (text === '') continue
    casing.push({
      role,
      text,
      mono: el.closest('.bn-mono, code, kbd') !== null,
      upper: getComputedStyle(el).textTransform === 'uppercase',
      typed: el.closest('[data-typed]') !== null,
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
    if (text !== '') casing.push({ role: 'tooltip', text, mono: false, upper: getComputedStyle(tip).textTransform === 'uppercase', typed: tip.closest('[data-typed]') !== null })
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
      // A HEADING (h2, h3) OR A TITLE MAY BE A SENTENCE: an empty state or a greeting. A control, and a page title (h1),
      // is a label whatever its ending, so `Cards to pull.` on a control or an h1 is still checked.
      if ((one.role === 'heading' || one.role === 'title') && isSentence(one.text)) continue
      const problems = casingProblems(one.text)
      if (problems.length === 0) continue
      // A FINDING IS KEYED BY ITS TEXT, not its role: a control's label often shows twice (its tip and its
      // accessible name), and one string is one offender.
      const id = JSON.stringify(one.text)
      if (seen.has(`c|${id}`)) continue
      seen.add(`c|${id}`)
      if (casingAllow[route]?.[id] !== undefined) {
        casingUsed.add(`${route}\u0000${id}`)
        continue
      }
      findings.push({ check: 'copy-casing', route, id, text: one.text, kind: one.role, detail: problems.join('; ') })
    }
  }

  const swept = await sweepEveryRoute(page, async (route) => {
    // THE MUTATION PROOF, one variable per check, as `text-checks.spec.ts` does. Set it to a route's hash
    // and that route gets the check's own defect, painted into `.bn-view` through `page.evaluate`, so
    // only that check goes red on it. From `app/`:
    //   COPY_VOICE_MUTATE='#/pricing'  npx playwright test tests/copy-checks.spec.ts   (a first-person line)
    //   COPY_CASING_MUTATE='#/'        npx playwright test tests/copy-checks.spec.ts   (a lower-case button)
    if (process.env.COPY_VOICE_MUTATE === route) await page.evaluate(paintVoiceDefect)
    if (process.env.COPY_CASING_MUTATE === route) await page.evaluate(paintCasingDefect)
    read(route, await page.evaluate(scanCopy))
  })

  await setViewport(page, { width: 1440, height: 1000 })
  await settleBody(page, FULFILLER)
  read(FULFILLER, await page.evaluate(scanCopy))
  swept.add(FULFILLER)

  const casingTotal = reads.reduce((sum, one) => sum + one.casing, 0)
  expect(casingTotal, `the sweep read ${casingTotal} labels, under the floor of ${CASING_FLOOR}`).toBeGreaterThan(CASING_FLOOR)

  // THE RECEIPT. Counts and the top ten, written before any assertion so a red run still leaves it.
  const tally = (check: Finding['check']) => {
    const mine = findings.filter((one) => one.check === check)
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
