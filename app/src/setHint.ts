/* WHAT A SET HINT HAS TO BE, ANSWERED ON THE CAPTURE SCREEN INSTEAD OF THREE STEPS LATER.
 *
 * D65 made the hint a whitelist field: the operator types shorthand, the export is scoped to
 * the sets it resolves to, and a hint that resolves to nothing widens to every set in the
 * category. That is safe — widening cannot miss a card — but it is SILENT, and the silence is
 * the defect this module exists to end. A `datalist` offers the vocabulary and says nothing
 * about whether what you typed is in it, so `Spiritforge` and `Spiritforged` looked identical
 * at the rig and diverged at the fetch, an hour of captures later.
 *
 * IT JUDGES; IT NEVER REFUSES. Every verdict here is drawn as a note beside a field that
 * still takes any text at all. D65's rule stands unamended: the rig does not stop for an
 * autocomplete, and a hint field that would not accept a string because a list disagreed
 * with it is a worse product than one with no list. `unchecked` is a first-class verdict
 * for exactly that reason — no cookie, no network, the portal down, and the screen says it
 * cannot tell rather than saying the hint is wrong.
 *
 * THE RULES ARE `pipeline/setnames.py`'S, IN THE SAME ORDER, AND THE COPY IS ASSERTED.
 * `scripts/set-hint-agreement.py` runs this module under node against the Python one over a
 * shared table of cases, because this repo has been bitten three times by a cross-language
 * seam nothing compared — the two game prompts whose identifier field `cli/resolve.py` did
 * not read, the port derivation `scripts/port-agreement.py` now guards, and the set matcher
 * itself, which was two different Python implementations answering one question differently
 * until they were merged into `setnames`.
 *
 * WHY NOT ASK THE SERVER PER KEYSTROKE. D65 refused that in as many words: the vocabulary
 * is fetched once per game and cached, because a screen that round-tripped an autocomplete
 * would spend the owner's session on it at a 623 ms feeder cadence (D19).
 */

/** One row of `GET /tcg/sets` — TCGplayer's own name for a set. The id is not read here:
 *  `server/pipeline_routes.py:do_tcg_sets` already drops the `All Set Names` row (`0`),
 *  which is the one id the Python side has to exclude by hand. */
export type SetOption = { name: string }

/** What the field can say about what is typed in it.
 *
 *  `blank` and `unchecked` are both "no opinion" and are deliberately two values: one is
 *  the operator having said nothing, the other is this screen being unable to check. They
 *  read the same in a boolean and want different sentences. */
export type HintVerdict =
  | { state: 'blank' }
  /** No vocabulary to check against — the fetch failed, or the game has no sets. */
  | { state: 'unchecked' }
  /** Resolves to exactly one set. `exact` is whether the hint IS that set's name, which is
   *  the only form that needs no completing; a code, an alias or a prefix resolves the same
   *  way but reads as shorthand, and the field offers to write the name out. */
  | { state: 'matched'; set: string; exact: boolean }
  /** More than one set answers to it. The Python side returns this as a MISS and widens, so
   *  this is not a near-hit; it is drawn apart from `unmatched` only because "three sets
   *  answer to that" is an instruction and "no match" is not. */
  | { state: 'ambiguous'; among: string[] }
  | { state: 'unmatched' }

/** A set code is short. Four is the longest TCGplayer publishes as a colon prefix (`SWSH`,
 *  `ME01`) and the longest the community uses (`OGN`, `SFD`, `PFL`). The cap is what keeps
 *  `abbreviates` off misspelled NAMES — uncapped it resolves `Spiritfoged` and `Vendeta` to
 *  their intended sets, which sounds like a feature until you notice it also means almost
 *  every string "names a set" and the typo warning below never fires again. */
const CODE_MAX = 4

/** AND THREE IS THE SHORTEST. Every code either game publishes is three characters or more,
 *  and two letters run in order through so many names that the rule stops discriminating.
 *  See `pipeline/setnames.py` for why this is NOT what stops `SP` reaching Spiritforged —
 *  that one resolves by prefix, and has since before either rule was written. */
const CODE_MIN = 3

/** Lowercase, drop everything that is not a letter or digit, unpad each digit run, so `sv09`
 *  and `sv9` fold together. `pipeline/setnames.py:fold`, character for character. */
export function fold(name: string): string {
  const text = (name ?? '').trim().toLowerCase()
  let out = ''
  let digits = ''
  for (const char of text) {
    if (char >= '0' && char <= '9') {
      digits += char
      continue
    }
    if (digits) {
      out += String(parseInt(digits, 10))
      digits = ''
    }
    if (/[\p{L}\p{N}]/u.test(char)) out += char
  }
  return digits ? out + String(parseInt(digits, 10)) : out
}

/** The whole label and each side of its colon, folded. `SV09: Journey Together` answers to
 *  `SV09`, to `Journey Together` and to itself — the operator labelled the divider with
 *  whichever one they had to hand. */
function sides(name: string): string[] {
  const parts = [name, ...(name ?? '').split(':')]
  return [...new Set(parts.map(fold).filter(Boolean))]
}

/** The set's own name with any TCGplayer block code taken off the front. `SV05: Temporal
 *  Forces` -> `temporalforces`, because the codes people type are built from the name — `TEF`,
 *  `JTG`, `MEG` — and against the whole label every one of them would have to start `sv`. */
function tail(name: string): string {
  const text = name ?? ''
  const cut = text.indexOf(':')
  return fold(cut === -1 ? text : text.slice(cut + 1))
}

/** A TRUNCATED WORD IS STILL THAT WORD; A TRUNCATED NUMBER IS A DIFFERENT NUMBER. `unl` is
 *  Unleashed and `sv` is every SV set, but `sv1` is NOT `SV19` — asserted in
 *  `harness/tests/t3_join_coverage.py` since before either matcher was merged. */
function prefixOk(needle: string, folded: string): boolean {
  if (!needle || !folded.startsWith(needle)) return false
  const rest = folded.slice(needle.length)
  const lastIsDigit = needle[needle.length - 1]! >= '0' && needle[needle.length - 1]! <= '9'
  const nextIsDigit = rest.length > 0 && rest[0]! >= '0' && rest[0]! <= '9'
  return !(lastIsDigit && nextIsDigit)
}

/** Is `needle` a set code for `name` — its letters, in order, anchored on the first?
 *
 *  There is no rule that derives the ONE official code from a name: `PAL` is the first three
 *  letters of Paldea, `TEF` is two-plus-one, `SFD` is a squeeze. Rather than guess which
 *  generator a set used, this accepts every ordered squeeze and lets ambiguity throw out the
 *  ones that answer to more than one set. It is tried LAST, so it can never take a hint that
 *  already resolves. */
function abbreviates(needle: string, name: string): boolean {
  if (!needle || needle.length < CODE_MIN || needle.length > CODE_MAX) return false
  const body = tail(name)
  if (!body || body[0] !== needle[0]) return false
  let at = 1
  for (const char of needle.slice(1)) {
    const found = body.indexOf(char, at)
    if (found === -1) return false
    at = found + 1
  }
  return true
}

/**
 * Does this hint name exactly one of these sets?
 *
 * Rule zero is the game's alias table (D22, hand-authored), which resolves a hint to another
 * HINT rather than to a set, so the shape rules below still do the matching. Then, in order,
 * first rule that answers at all:
 *
 *   label          equal to the whole set name
 *   side           equal to either side of its colon
 *   prefix         a prefix of the label, not splitting a number
 *   abbreviation   a short hint whose letters run in order through the set's own name
 *
 * LABEL AND SIDE ARE TWO TIERS, NOT ONE, AND THE ORDER IS LOAD-BEARING. `Origins` is a set,
 * and it is also the left side of `Origins: Proving Grounds` — collapsed into one tier they
 * tie, and a hint naming a base set exactly resolves to nothing.
 */
export function resolveSetHint(
  hint: string,
  sets: readonly SetOption[],
  aliases: Readonly<Record<string, string>> = {},
): HintVerdict {
  const raw = (hint ?? '').trim()
  if (raw === '') return { state: 'blank' }
  if (sets.length === 0) return { state: 'unchecked' }

  const table = new Map(Object.entries(aliases).map(([key, value]) => [fold(key), value]))
  const needle = fold(table.get(fold(raw)) ?? raw)
  // An alias pointing at whitespace is the registry's bug, not the operator's: it leaves
  // nothing to match, and the Python side skips such a hint rather than missing on it.
  if (needle === '') return { state: 'blank' }

  const rows = sets.map((row) => ({ name: row.name, folded: sides(row.name) }))
  const rules: ((row: { name: string; folded: string[] }) => boolean)[] = [
    (row) => fold(row.name) === needle,
    (row) => row.folded.includes(needle),
    (row) => row.folded.some((one) => prefixOk(needle, one)),
    (row) => abbreviates(needle, row.name),
  ]

  for (const rule of rules) {
    const found = [...new Set(rows.filter(rule).map((row) => row.name))]
    if (found.length === 1) {
      // EXACT MEANS THE STORED STRING IS THE SET'S NAME, not merely that a rule fired: an
      // alias or a code resolving to a set is still shorthand a reader has to expand, and
      // the field offers to complete it for exactly that reason.
      return { state: 'matched', set: found[0] as string, exact: fold(raw) === fold(found[0] as string) }
    }
    if (found.length > 1) return { state: 'ambiguous', among: found }
  }
  return { state: 'unmatched' }
}
