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
 * WHAT COUNTS AS "PROSE" FOR THE FACT CHECK IS `docs/specs/text-density.md`'s (née the
 * 2026-09-23 density review's) OWN RULER: a block element with six or more visible words.
 * Reusing it rather than inventing a second threshold is why a fact buried in a short label
 * ("3 boxes") never trips this — those blocks fall under six words and are read as data, not
 * prose, the same distinction the density review drew.
 *
 * A CLOSED `<details>` CONTRIBUTES NOTHING, with no special-casing needed: the UA stylesheet
 * sets `display: none` on everything under it but the `<summary>`, and this walk already skips
 * anything `visible()` says is not painted — the same argument `D-notice-detail` makes for
 * `machine-words.spec.ts` reading `innerText` instead of `textContent`.
 */

export interface TextShapeResult {
  repeatedSentences: Array<{ groupClass: string; count: number; sample: string }>
  repeatedFacts: Array<{ fact: string; count: number }>
  longSentences: Array<{ words: number; sample: string }>
  captionHeading: Array<{ heading: string; caption: string; overlap: number }>
}

/** Runs INSIDE the page via `page.evaluate(measureTextShape)`. Self-contained on purpose. */
export function measureTextShape(): TextShapeResult {
  const empty: TextShapeResult = {
    repeatedSentences: [],
    repeatedFacts: [],
    longSentences: [],
    captionHeading: [],
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
  // accumulated text — the same grouping `scripts/text-density/density.mjs` uses, so both
  // tools read "one prose unit" the same way.
  const blocks = new Map<Element, string>()
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = (n.textContent || '').trim()
    if (!text) continue
    const parent = n.parentElement
    if (!parent || !visible(parent) || isSrOnly(parent)) continue
    const b = blockOf(parent)
    blocks.set(b, (blocks.get(b) ? blocks.get(b) + ' ' : '') + text)
  }
  const blockList = [...blocks.entries()].map(([el, text]) => ({ el, text }))

  // ---------------------------------------------------------------- repeated sentences
  // A repeating group: every element in the view sharing one exact, non-empty class
  // attribute, at least three of them. Grouped by class alone rather than "same parent" so a
  // virtualised or paginated list still counts — the repeating UNIT is the shape a card or a
  // row draws, not where the DOM happens to nest it this render.
  const byClass = new Map<string, Element[]>()
  root.querySelectorAll('*').forEach((el) => {
    const cls = typeof el.className === 'string' ? el.className.trim() : ''
    if (!cls) return
    const list = byClass.get(cls) ?? []
    list.push(el)
    byClass.set(cls, list)
  })

  const repeatedSentences: TextShapeResult['repeatedSentences'] = []
  for (const [cls, els] of byClass) {
    if (els.length < 3) continue
    // Keep only the LEAVES of the group — an element in the group that itself CONTAINS
    // another member is the list wrapper, not the repeating card.
    const leaves = els.filter(
      (el) => visible(el) && !isSrOnly(el) && !els.some((other) => other !== el && el.contains(other)),
    )
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
      if (set.size >= 3) {
        repeatedSentences.push({ groupClass: cls, count: set.size, sample: norm.slice(0, 140) })
      }
    }
  }

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
    if (set.size >= 2) repeatedFacts.push({ fact, count: set.size })
  }

  // ------------------------------------------------------------------- long sentences
  const longSentences: TextShapeResult['longSentences'] = []
  for (const b of blockList) {
    if (!visible(b.el) || isSrOnly(b.el)) continue
    for (const sentence of splitSentences(b.text)) {
      const wc = words(sentence).length
      if (wc > 25) longSentences.push({ words: wc, sample: sentence.slice(0, 160) })
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
  root.querySelectorAll('h1, h2, h3, h4, [role="heading"]').forEach((h) => {
    if (!visible(h) || isSrOnly(h)) return
    const headingText = ((h as HTMLElement).innerText || h.textContent || '').trim()
    if (!headingText) return
    let sib: Element | null = h.nextElementSibling
    let hops = 0
    while (sib && hops < 2) {
      if (visible(sib) && !isSrOnly(sib)) {
        const capText = ((sib as HTMLElement).innerText || sib.textContent || '').trim()
        const capWords = words(capText).length
        if (capWords >= 3 && capWords <= 30) {
          const a = tokenSet(headingText)
          const b = tokenSet(capText)
          // A ONE-TOKEN HEADING (most routes' own H1 — "Pricing", "Shipping") is skipped:
          // any caption that so much as NAMES the screen would otherwise read as "100%
          // overlap" against a heading with exactly one token to overlap, which is topical
          // mention, not repetition. Two or more tokens is where "repeats its heading"
          // starts meaning something (TXT-10's "Pricing is answered." under a heading that
          // already draws the same sentence a different way).
          if (a.size >= 2 && b.size) {
            let hit = 0
            for (const t of b) if (a.has(t)) hit++
            const overlap = hit / Math.min(a.size, b.size)
            if (overlap >= 0.6) {
              captionHeading.push({
                heading: headingText.slice(0, 80),
                caption: capText.slice(0, 120),
                overlap: Math.round(overlap * 100),
              })
            }
          }
        }
        break
      }
      sib = sib.nextElementSibling
      hops++
    }
  })

  return { repeatedSentences, repeatedFacts, longSentences, captionHeading }
}

/* THE MUTATION HOOK, mirroring `copy-budget.spec.ts`'s own `COPY_BUDGET_MUTATE` exactly —
 * never by editing a file under `app/src`, which this task is not permitted to touch.
 * `TEXT_SHAPE_MUTATE=<hash>` injects the SAME four-word-plus sentence into three elements
 * sharing one class, inside that route's `.bn-view`, so `repeatedSentences` catches it —
 * proving the check on "a repeated sentence on a Shipping card" without touching
 * `Shipping.tsx`. Run: `TEXT_SHAPE_MUTATE='#/shipping' npx playwright test
 * tests/text-shape.spec.ts` from `app/`. */
export function injectRepeatedSentence(): void {
  const root = document.querySelector('.bn-view')
  if (!root) return
  for (let i = 0; i < 3; i++) {
    const card = document.createElement('div')
    card.className = 'text-shape-mutation-card'
    const p = document.createElement('p')
    p.textContent = 'This mutation sentence repeats on purpose to prove the check catches it.'
    card.appendChild(p)
    root.appendChild(card)
  }
}
