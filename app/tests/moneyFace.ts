/* D221 — MONEY STAYS MONO, EVERYWHERE, INPUTS AND CHIPS INCLUDED. The owner's ruling,
 * 2026-09-23, confirmed after seeing both options drawn: "mono everywhere (inputs and chips
 * included) plus a check that refuses a dollar figure drawn any other way." D221's own
 * premise — "Pricing's worklist … agree[s] on the mono face already" — was measured false
 * (COH-15, VIS-04): the Market column, the price field, Shipping's chips and Review's total
 * were all Inter. This is that check, over what the browser actually PAINTS rather than a
 * source-level class name, because the requirement is a VISUAL one: `getComputedStyle`'s
 * `font-family`, not `closest('.bn-money')`, is what tells a real Inter dollar figure from a
 * real mono one, and a descendant that merely INHERITS the mono face from an ancestor without
 * carrying the class itself still satisfies the rule this row exists to enforce.
 *
 * TWO SOURCES OF A VISIBLE DOLLAR FIGURE: ordinary text (`.bn-view`'s text nodes) and a live
 * form control (`<input>`/`<textarea>`), whose typed VALUE is never a text node at all — the
 * owner's own "inputs … included" is this second half. Both are checked against the same
 * pattern.
 */

export interface MoneyFaceResult {
  text: Array<{ amount: string; fontFamily: string; sample: string }>
  fields: Array<{ amount: string; fontFamily: string; tag: string }>
}

/** Runs INSIDE the page via `page.evaluate(scanMoneyFace)`. Self-contained on purpose — see
 *  `textShape.ts`'s header for why `page.evaluate` functions may not close over outer scope.
 *  `MONEY_RE` and `MONO_FACE` are declared INSIDE the function for the same reason: a
 *  module-level `const` is not part of the function's own `toString()`, so the browser
 *  would see `MONEY_RE is not defined` the moment this ran — measured the first time this
 *  file was built. */
export function scanMoneyFace(): MoneyFaceResult {
  // `$1.23`, `$66,334.71`, `+$1.20`, `−$0.35` (U+2212, `moneySigned`'s own minus) or
  // `-$1.20` (a plain hyphen, in case a value was typed rather than formatted) — always two
  // decimal places, matching `money.ts`'s own `toFixed(2)`.
  const MONEY_RE = /[+−-]?\$\d[\d,]*\.\d{2}/g

  // JetBrains Mono is `--bn-font-mono`'s first, named face (`tokens.css`) — the only font
  // this repo ships that is actually monospaced, so a resolved `font-family` string is
  // checked for its presence rather than for the CSS variable, which `getComputedStyle`
  // never returns.
  const MONO_FACE = 'jetbrains mono'

  const empty: MoneyFaceResult = { text: [], fields: [] }
  const view = document.querySelector('.bn-view')
  if (!view) return empty

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

  function isMono(el: Element): boolean {
    return getComputedStyle(el).fontFamily.toLowerCase().includes(MONO_FACE)
  }

  const textHits: MoneyFaceResult['text'] = []
  const walker = document.createTreeWalker(view, NodeFilter.SHOW_TEXT)
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const raw = n.textContent || ''
    if (!raw.includes('$')) continue
    const parent = n.parentElement
    if (!parent || !visible(parent) || isSrOnly(parent)) continue
    MONEY_RE.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = MONEY_RE.exec(raw))) {
      if (!isMono(parent)) {
        const start = Math.max(0, m.index - 30)
        const end = Math.min(raw.length, m.index + m[0].length + 30)
        textHits.push({
          amount: m[0],
          fontFamily: getComputedStyle(parent).fontFamily,
          sample: raw.slice(start, end).replace(/\s+/g, ' ').trim(),
        })
      }
    }
  }

  const fieldHits: MoneyFaceResult['fields'] = []
  view.querySelectorAll('input, textarea').forEach((el) => {
    const field = el as HTMLInputElement | HTMLTextAreaElement
    if (!visible(field) || isSrOnly(field)) return
    const value = field.value ?? ''
    const placeholder = field.getAttribute('placeholder') ?? ''
    const probe = value || placeholder
    if (!probe.includes('$') && !/^\d*\.?\d*$/.test(value)) return
    // A bare numeric value with no `$` still needs the mono face when the FIELD is a money
    // field — read from its own placeholder or a leading `$`-shaped value, the only signals
    // available with no semantic `type="money"` in HTML.
    const looksLikeMoney = MONEY_RE.test(`$${value}`) || MONEY_RE.test(placeholder)
    MONEY_RE.lastIndex = 0
    if (!looksLikeMoney) return
    if (!isMono(field)) {
      fieldHits.push({
        amount: value || placeholder,
        fontFamily: getComputedStyle(field).fontFamily,
        tag: field.tagName.toLowerCase(),
      })
    }
  })

  return { text: textHits, fields: fieldHits }
}
