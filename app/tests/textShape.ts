/* THE ONE MEASUREMENT `text-shape.spec.ts` READS, kept in its own module so the function
 * handed to `page.evaluate` stays a single, self-contained closure — Playwright serialises it
 * by `toString()`, so it may not read anything from this file's outer scope, only from its own
 * nested helpers and the live DOM. See D-text-shape-checks, which supersedes D194.
 *
 * TWO CHECKS, FOUR SIGNALS. The owner's ruling, 2026-09-23: kill the pinned word-count
 * ceilings ("I don't like keeping a stagnant static pin") and replace them with a repetition
 * check, a sentence-shape check, and the text-density reviewer as a repeatable on-demand pass
 * (that third one is `scripts/text-density/`, never a gate — D18). This module is the first
 * two, each in two shapes:
 *
 *   REPETITION
 *   - `repeatedSentences`: the same four-or-more-word sentence appearing on three or more
 *     REPEATING SIBLINGS — a card, a row, an entry — never once, incidentally, in unrelated
 *     prose. "Cards only, and under $50." on 166 Envelope cards (TXT-01) is exactly this
 *     shape: one lane header already says it, and every card repeats it.
 *   - `repeatedFacts`: one NUMBER + NOUN fact stated twice anywhere on the screen — "27
 *     copies" in the stage strip and again in Home's "Behind that" line (TXT-25). This one is
 *     screen-wide, not per repeating group, because the two places a figure repeats are
 *     usually two unrelated blocks, not two rows of one list.
 *
 *   SENTENCE SHAPE
 *   - `longSentences`: a single sentence over 25 words — the length past which a sentence
 *     reads as a paragraph the owner did not ask for (TXT-13's 52-word run-on is the case this
 *     was measured against).
 *   - `captionHeading`: a caption or subtitle sitting right under a heading, its own words
 *     60% or more contained in the heading's — "Pricing is answered." under a heading that
 *     already says the same thing a different way (TXT-10).
 *
 * WHAT COUNTS AS "PROSE" FOR THE FACT CHECK IS THE 2026-09-23 DENSITY REVIEW'S OWN RULER: a
 * block element with six or more visible words. `make text-density` prints the same blocks.
 * Reusing it rather than inventing a second threshold is why a fact buried in a short label
 * ("3 boxes") never trips this — those blocks fall under six words and are read as data, not
 * prose, the same distinction the density review drew.
 *
 * A CLOSED `<details>` CONTRIBUTES NOTHING, with no special-casing needed: the UA stylesheet
 * sets `display: none` on everything under it but the `<summary>`, and this walk already skips
 * anything `visible()` says is not painted — the same argument `D-notice-detail` makes for
 * `machine-words.spec.ts` reading `innerText` instead of `textContent`.
 */

/** Each hit carries a `key`: the text `text-shape-allow.json` lists it under. A repeated
 *  sentence is keyed by the sentence (lower-cased, punctuation dropped), a repeated fact by the
 *  fact ("27 copies"), a long sentence by its first 80 characters, and a caption by its own
 *  first 80 characters. The fixture is deterministic (`routeSweep.ts`), so a key is stable
 *  from run to run, and a NEW finding on a route that already has one listed is still red. */
export interface TextShapeResult {
  repeatedSentences: Array<{ key: string; groupClass: string; count: number }>
  repeatedFacts: Array<{ key: string; count: number }>
  longSentences: Array<{ key: string; words: number; sample: string }>
  captionHeading: Array<{ key: string; heading: string; overlap: number }>
  /** For `make text-density` only, never asserted: `.bn-view`'s visible word count, and its
   *  largest prose blocks, largest first. */
  words: number
  prose: Array<{ words: number; sample: string }>
}

/** Runs INSIDE the page via `page.evaluate(measureTextShape)`. Self-contained on purpose. */
export function measureTextShape(): TextShapeResult {
  const empty: TextShapeResult = {
    repeatedSentences: [],
    repeatedFacts: [],
    longSentences: [],
    captionHeading: [],
    words: 0,
    prose: [],
  }
  const found = document.querySelector('.bn-view')
  if (!found) return empty
  const root: Element = found

  function visible(el: Element): boolean {
    for (let e: Element | null = el; e; e = e.parentElement) {
      const s = getComputedStyle(e)
      if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false
    }
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }

  function isSrOnly(el: Element): boolean {
    return !!el.closest('.bn-sr, .sr-only, [aria-hidden="true"]')
  }

  function blockOf(el: Element): Element {
    let e: Element | null = el
    while (e && e !== root) {
      const d = getComputedStyle(e).display
      if (!d.startsWith('inline') && d !== 'contents') return e
      e = e.parentElement
    }
    return root
  }

  function words(s: string): string[] {
    return s.trim().split(/\s+/).filter(Boolean)
  }

  function splitSentences(s: string): string[] {
    return s
      .split(/(?<=[.!?])\s+(?=[A-Z0-9])|\n+/)
      .map((x) => x.trim())
      .filter(Boolean)
  }

  function normSentence(s: string): string {
    return s
      .toLowerCase()
      .replace(/[""''.,!?;:()]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
  }

  // Gather text BLOCKS: the nearest non-inline ancestor of every visible text node, with its
  // accumulated text. `make text-density` prints these same blocks. Two text nodes with the
  // SAME parent are joined as they are, so React's "3 order" + "s held" reads "3 orders held"
  // as the screen draws it. Text from two DIFFERENT elements is joined with a space, so two
  // adjacent spans ("Pushed 0", "Staged 0") stay two words apart.
  const blocks = new Map<Element, string>()
  const lastParent = new Map<Element, Element>()
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const raw = n.textContent || ''
    if (!raw.trim()) continue
    const parent = n.parentElement
    if (!parent || !visible(parent) || isSrOnly(parent)) continue
    const b = blockOf(parent)
    const sameParent = lastParent.get(b) === parent
    blocks.set(b, (blocks.get(b) ?? '') + (sameParent ? '' : ' ') + raw)
    lastParent.set(b, parent)
  }
  const blockList = [...blocks.entries()]
    .map(([el, text]) => ({ el, text: text.replace(/\s+/g, ' ').trim() }))
    .filter((b) => b.text !== '')

  // ---------------------------------------------------------------- repeated sentences
  // A repeating group: every element in the view that carries one BASE class, at least three
  // of them. A base class is a class token with any BEM modifier cut off (`card--envelope` ->
  // `card`), and a bare state token (`is-open`, `has-photo`) is never one. So a card that
  // carries a modifier (`shipping-card shipping-card--parcel`) still groups with its plain
  // siblings. An element joins the group of every base class it carries. Grouped by class
  // rather than "same parent" so a virtualised or paginated list still counts: the repeating
  // UNIT is the shape a card or a row draws, not where the DOM happens to nest it this render.
  function baseClasses(el: Element): string[] {
    const out = new Set<string>()
    el.classList.forEach((token) => {
      if (/^(is|has)-/.test(token)) return
      const base = token.split('--')[0] ?? ''
      if (base) out.add(base)
    })
    return [...out]
  }
  const byClass = new Map<string, Element[]>()
  root.querySelectorAll('*').forEach((el) => {
    for (const cls of baseClasses(el)) {
      const list = byClass.get(cls) ?? []
      list.push(el)
      byClass.set(cls, list)
    }
  })

  // One hit per SENTENCE, whichever group repeats it most: the same sentence reached through
  // two classes on one card is one finding, not two.
  const bySentence = new Map<string, { groupClass: string; count: number }>()
  for (const [cls, els] of byClass) {
    if (els.length < 3) continue
    // Keep only the LEAVES of the group: a member that CONTAINS another member is the list
    // wrapper, not the repeating card. Marked by walking each member's ancestors once.
    const members = new Set(els)
    const wrappers = new Set<Element>()
    for (const el of els) {
      for (let up = el.parentElement; up && up !== root.parentElement; up = up.parentElement) {
        if (members.has(up)) wrappers.add(up)
      }
    }
    const leaves = els.filter((el) => !wrappers.has(el) && visible(el) && !isSrOnly(el))
    if (leaves.length < 3) continue
    const owners = new Map<string, Set<number>>()
    leaves.forEach((el, i) => {
      const text = (el as HTMLElement).innerText || el.textContent || ''
      for (const sentence of splitSentences(text)) {
        if (words(sentence).length < 4) continue
        const norm = normSentence(sentence)
        if (!norm) continue
        const set = owners.get(norm) ?? new Set<number>()
        set.add(i)
        owners.set(norm, set)
      }
    })
    for (const [norm, set] of owners) {
      if (set.size < 3) continue
      const had = bySentence.get(norm)
      if (had === undefined || set.size > had.count) bySentence.set(norm, { groupClass: cls, count: set.size })
    }
  }
  const repeatedSentences: TextShapeResult['repeatedSentences'] = [...bySentence].map(([key, hit]) => ({
    key,
    groupClass: hit.groupClass,
    count: hit.count,
  }))

  // -------------------------------------------------------------------- repeated facts
  // Screen-wide, over PROSE blocks only (>= 6 words — `text-density`'s own ruler), so an
  // ordinary data column ("3 boxes" on ten different rows, ten different facts) never trips
  // this — only the SAME number-plus-noun pair, stated in two different prose sentences.
  const prose = blockList.filter((b) => words(b.text).length >= 6)
  const factOwners = new Map<string, Set<number>>()
  const factRe = /\b(\d[\d,]*)\s+([a-z]+)\b/gi
  prose.forEach((b, i) => {
    const seen = new Set<string>()
    let m: RegExpExecArray | null
    factRe.lastIndex = 0
    while ((m = factRe.exec(b.text))) {
      const num = m[1] ?? ''
      const noun = m[2] ?? ''
      if (!num || !noun) continue
      seen.add(`${num.replace(/,/g, '')} ${noun.toLowerCase()}`)
    }
    for (const key of seen) {
      const set = factOwners.get(key) ?? new Set<number>()
      set.add(i)
      factOwners.set(key, set)
    }
  })
  const repeatedFacts: TextShapeResult['repeatedFacts'] = []
  for (const [fact, set] of factOwners) {
    if (set.size >= 2) repeatedFacts.push({ key: fact, count: set.size })
  }

  // ------------------------------------------------------------------- long sentences
  const longSentences: TextShapeResult['longSentences'] = []
  for (const b of blockList) {
    if (!visible(b.el) || isSrOnly(b.el)) continue
    for (const sentence of splitSentences(b.text)) {
      const wc = words(sentence).length
      if (wc > 25) longSentences.push({ key: sentence.slice(0, 80), words: wc, sample: sentence.slice(0, 160) })
    }
  }

  // ------------------------------------------------------------- caption repeats heading
  const captionHeading: TextShapeResult['captionHeading'] = []
  function tokenSet(s: string): Set<string> {
    return new Set(
      s
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter((w) => w.length > 2),
    )
  }
  // The caption is the first visible element after the heading, at most two hops on. When
  // the heading is the LAST thing in its `<header>` or `<hgroup>` (`<header><h2/></header>
  // <p/>`), the search climbs out of the wrapper and continues after it.
  function captionAfter(h: Element): Element | null {
    let from: Element = h
    for (let climb = 0; climb < 3; climb++) {
      let sib: Element | null = from.nextElementSibling
      let hops = 0
      while (sib && hops < 2) {
        if (visible(sib) && !isSrOnly(sib)) return sib
        sib = sib.nextElementSibling
        hops++
      }
      const parent = from.parentElement
      if (!parent || parent === root || !/^(HEADER|HGROUP)$/.test(parent.tagName)) return null
      from = parent
    }
    return null
  }
  root.querySelectorAll('h1, h2, h3, h4, [role="heading"]').forEach((h) => {
    if (!visible(h) || isSrOnly(h)) return
    const headingText = ((h as HTMLElement).innerText || h.textContent || '').trim()
    if (!headingText) return
    const cap = captionAfter(h)
    if (cap === null) return
    const capText = ((cap as HTMLElement).innerText || cap.textContent || '').trim()
    const capWords = words(capText).length
    if (capWords < 3 || capWords > 30) return
    const a = tokenSet(headingText)
    const b = tokenSet(capText)
    // A ONE-TOKEN HEADING (most routes' own H1 — "Pricing", "Shipping") is skipped: any
    // caption that so much as NAMES the screen would otherwise read as "100% overlap" against
    // a heading with exactly one token to overlap, which is topical mention, not repetition.
    // Two or more tokens is where "repeats its heading" starts meaning something (TXT-10's
    // "Pricing is answered." under a heading that already draws the same sentence a
    // different way).
    if (a.size < 2 || b.size === 0) return
    let hit = 0
    for (const t of b) if (a.has(t)) hit++
    const overlap = hit / Math.min(a.size, b.size)
    if (overlap >= 0.6) {
      captionHeading.push({
        key: capText.slice(0, 80),
        heading: headingText.slice(0, 80),
        overlap: Math.round(overlap * 100),
      })
    }
  })

  // ------------------------------------------------------- for `make text-density` only
  const total = words((root as HTMLElement).innerText || '').length
  const topProse = blockList
    .map((b) => ({ words: words(b.text).length, sample: b.text.slice(0, 140) }))
    .filter((b) => b.words >= 6)
    .sort((x, y) => y.words - x.words)
    .slice(0, 8)

  return { repeatedSentences, repeatedFacts, longSentences, captionHeading, words: total, prose: topProse }
}

/* THE MUTATION HOOK (`TEXT_SHAPE_MUTATE=<hash>`), through `page.evaluate`, never an edit
 * under `app/src`. It trips all four assertions at once, each with a key no real screen draws,
 * so every line it adds to the failure is a NEW finding:
 *   - one sentence on three cards whose classes differ by a modifier (`card`, `card card--wide`,
 *     `card is-open`), so only base-class grouping sees one group: `repeated-sentence`;
 *   - that sentence carries "4321 widgets", in three prose blocks: `repeated-fact`;
 *   - a 30-word sentence: `long-sentence`;
 *   - a heading wrapped alone in a `<header>`, its caption AFTER the wrapper, so only the
 *     climb out of `<header>` finds it: `caption-heading`.
 * Run from `app/`: `TEXT_SHAPE_MUTATE='#/' npx playwright test tests/text-shape.spec.ts`. */
export function injectRepeatedSentence(): void {
  const root = document.querySelector('.bn-view')
  if (!root) return
  const classes = ['text-shape-mutation-card', 'text-shape-mutation-card text-shape-mutation-card--wide', 'text-shape-mutation-card is-open']
  for (const className of classes) {
    const card = document.createElement('div')
    card.className = className
    const p = document.createElement('p')
    p.textContent = 'This mutation sentence repeats 4321 widgets on purpose to prove the check catches it.'
    card.appendChild(p)
    root.appendChild(card)
  }
  const long = document.createElement('p')
  long.textContent =
    'This one mutation sentence runs on for thirty words so that the sentence shape check has a real run on ' +
    'sentence to find and to name in its failure here.'
  root.appendChild(long)
  const header = document.createElement('header')
  const heading = document.createElement('h2')
  heading.textContent = 'Mutation heading carries these words'
  header.appendChild(heading)
  root.appendChild(header)
  const caption = document.createElement('p')
  caption.textContent = 'Mutation heading carries these words again'
  root.appendChild(caption)
}
