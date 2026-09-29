import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react'

import {
  describeFailure,
  applyMarkdown,
  fetchLiveExport,
  getMarkdownTable,
  getMarkdowns,
  getPriceHistory,
  getPriceTrends,
  markdownFileUrl,
  markdownListings,
  markdownTrends,
  markdownHistory,
  sendMarkdown,
  getPricingCorpus,
  getPricingWorklist,
  restoreLastClear,
  restoreClear,
  type KeptClear,
  putPricingCorpus,
  restorePricingAnswers,
  getRun,
  getRuns,
  photoUrl,
  type Failure,
  failureTone,
  refusalToast,
} from './server'
import type {
  DecisionsDocument,
  CorpusAnswer,
  MergedSku,
  RosterRun,
  PricingCorpus,
  PricingClearable,
  PricingClearResult,
  PricingRestoreSkip,
  MarkdownAnswer,
  MarkdownSummary,
  MarkdownTable,
  PricingWorklist,
  Unreachable,
  LiveMove,
  PricingSku,
  RunDetail,
  RunSummary,
  WithheldRecord,
} from './types'
import { WITHHOLD_KEYS, WITHHOLD_LABELS, WITHHOLD_REASONS, type WithholdReason } from './holds'
import { isEditableTarget } from './keys'
import { FLAT_KEY, subThresholdSkus } from './readiness'
import { isWithheld, rowShare, runChip } from './standing'
import { TrendCell, type TrendRead } from './PriceTrend'
import { ClearPrices } from './ClearPrices'
import { runBoxLabel } from './runScope'
import {
  liveInHash,
  markdownInHash,
  markdownSource,
  runSource,
  runsInHash,
  type PricingSource,
  type SectionSpec,
} from './pricingSource'
import { forSale, soldSince } from './cardState'
import { useCardCropWhenSeen } from './cardCrop'
import { readUpload } from './csvUpload'
import { absoluteDate, clockTime } from './dates'
import { moneyField } from './money'
import {
  Button,
  cropStyle,
  EmptyState,
  FailureNotice,
  FilterBar,
  Icon,
  IconButton,
  Kbd,
  Location,
  Money,
  Notice,
  Page,
  Pill,
  Popover,
  ProductLink,
  ReloadButton,
  Retry,
  Segmented,
  Sheet,
  countFacets,
  filterRows,
  matchQuery,
  openSheet,
  useFacetParams,
  useSortParam,
  useUndoHotkey,
  useViewParam,
} from './kit'
import type { FilterFacet, SortOption, SortValue } from './kit'
import { toast } from './kit/toast'
import './Pricing.css'
import { SendCard } from './SendCard'
import { ABSENT_SENTENCE, AbsentPhotoNote, gameLabel, noPhotoSentence } from './CardHero'

/* #/pricing — THE HAND-PRICING WORKLIST (D49, D86), REBUILT TO THE OWNER'S RE-INTERVIEW (D277).
 *
 * Every row, the rows that need the owner on top, then the rest by value (Q1, Q2). One slim bar
 * holds Send, sticky at the top on a desk and pinned above the tab bar on a phone (Q4). The rule
 * and the cut-off are one line with "Change" (Q5). Mark-downs are the Live tab, same rows, one
 * press (Q6, Q7). The value list is an Inventory sort now (Q8). Every product name opens the one
 * product view (D278), which is where the old drawer went.
 *
 * The client performs no arithmetic on money beyond the comparisons that pick a flag: every
 * figure it can put in a field came pre-rounded out of the join. */

/** How deep the undo stack goes. */
const UNDO_DEPTH = 10

/** How many SKUs one batched trend request asks about — a latency number, not a courtesy one. */
const TREND_CHUNK = 8

/** A row worth this much or more needs the owner (D277, Q2), in cents. */
const WORTH_A_LOOK = 500

/** A typed price this far from today's market needs the owner (D277, Q2), in percent. */
const DRIFT_PCT = 25

/** The three presets, matching `cli/cmd_join.py:PRESETS` key for key AND rule for rule.
 *  Audited by `scripts/docs-audit.py`'s `pricing presets` row. Labels are free; the tuple is not. */
const PRESETS: { key: string; label: string; rule: string; basis: string; says: string }[] = [
  {
    key: 'market_match',
    label: 'Match market',
    rule: 'match',
    basis: 'market',
    says: 'New cards list at market',
  },
  {
    key: 'market_undercut_5',
    label: 'Market −5%',
    rule: 'undercut:5',
    basis: 'market',
    says: 'New cards list 5% under market',
  },
  {
    key: 'low_undercut_1',
    label: 'TCG Low −1%',
    rule: 'undercut:1',
    basis: 'low',
    says: 'New cards list 1% under the lowest listing',
  },
]

/* ---------------------------------------------------------------------- the custom rule */

/** THE FOURTH ANSWER (the owner, 2026-09-03): `pipeline/pricing.py` takes `undercut:PCT` and
 *  `markup:PCT` over `market` or `low`, written where a preset writes its rule. */
const CUSTOM_KEY = 'custom'

type RuleKind = 'undercut' | 'markup'
type RuleBasis = 'market' | 'low'
type CustomRule = { kind: RuleKind; pct: string; basis: RuleBasis }

/** THE ACCEPTED ALPHABET FOR A PERCENTAGE, CLOSED: at most three digits, one dot, two places. */
const PCT = /^\d{0,3}(\.\d{0,2})?$/

const KIND_LABEL: Record<RuleKind, string> = { undercut: 'Under', markup: 'Over' }
const BASIS_LABEL: Record<RuleBasis, string> = { market: 'Market', low: 'TCG Low' }
const BASIS_SAYS: Record<RuleBasis, string> = { market: 'market', low: 'the lowest listing' }

function parseCustomRule(rule: string | undefined | null, basis: string | undefined | null): CustomRule | null {
  if (typeof rule !== 'string') return null
  const [kind, pct] = rule.trim().toLowerCase().split(':')
  if (kind !== 'undercut' && kind !== 'markup') return null
  if (pct === undefined || !/^\d{1,3}(\.\d{1,2})?$/.test(pct)) return null
  const where: RuleBasis = basis === 'low' ? 'low' : 'market'
  return { kind, pct: String(Number(pct)), basis: where }
}

/** Why this percentage cannot be written, or null when it can (`Rule.parse`'s own bounds). */
function badPercent(kind: RuleKind, pct: string): string | null {
  const text = pct.trim()
  if (text === '') return 'Type a percentage.'
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(text)) return 'A percentage is digits, with up to two places after the point.'
  const value = Number(text)
  if (!Number.isFinite(value)) return 'A percentage is digits, with up to two places after the point.'
  if (value === 0) return 'Nothing off the basis price is Match market. Pick that instead.'
  if (kind === 'undercut' && value >= 100) return `Undercutting by ${text}% prices at or below zero.`
  return null
}

/** The rule as `pipeline/pricing.py` spells it. Never composed anywhere else. */
function customRuleText(rule: CustomRule): string {
  return `${rule.kind}:${rule.pct.trim()}`
}

function customSays(rule: CustomRule): string {
  return `New cards list ${rule.pct.trim()}% ${rule.kind === 'undercut' ? 'under' : 'over'} ${BASIS_SAYS[rule.basis]}`
}

/** The snap keys (D49's closed alphabet: every letter is a command). Only the columns the row
 *  draws have a key: `m` Market and `l` Lowest. `n` is the asking price on the Live tab. */
const SNAPS: { key: string; field: keyof PricingSku['snap']; says: string }[] = [
  { key: 'm', field: 'market', says: 'Market' },
  { key: 'l', field: 'low', says: 'Lowest' },
]

/* The section list is passed to the source. It stays here beside `PRESETS`, which
   `scripts/docs-audit.py`'s `pricing presets` row reads out of THIS FILE by path. */
const SECTIONS: SectionSpec[] = [
  { bucket: 'listable', title: 'Above the cut-off', icon: 'tag', note: () => '' },
  { bucket: 'sub_threshold', title: 'Under the cut-off', icon: 'minus', note: () => '' },
  { bucket: 'no_market_data', title: 'No market price', icon: 'alert', note: () => '' },
]
const LIVE_SECTIONS: SectionSpec[] = SECTIONS.slice(0, 2)

/** THE ACCEPTED ALPHABET, CLOSED: `[0-9.]`, at most one dot, at most two digits after it. */
const PRICE = /^\d*(\.\d{0,2})?$/

type SubAnswer = string | { flat: string } | null

function priceable(text: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(text.trim())
}

/** The store's standing cut-off — a default, not a silent write (the owner, 2026-09-03). */
const STORE_DEFAULT_CUT = '0.49'

/** Money as integer cents, or null where the text is not a figure. */
function cents(text: string | null | undefined): number | null {
  if (typeof text !== 'string') return null
  const trimmed = text.trim()
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null
  return Math.round(Number(trimmed) * 100)
}

/** Money as integer cents off any money text, four places included (`349.9900`). */
function centsOf(text: string | null | undefined): number | null {
  return cents(moneyField(text))
}

/** THE LIVE TAB'S TWO LENSES (D103): the rule's picks (`offered`, and `deferred`, which also
 *  qualified), and the rows it passed over. One predicate, so a lens's count and its rows agree. */
function liveLens(standing: string | undefined): 'offered' | 'refused' {
  return standing === 'offered' || standing === 'deferred' ? 'offered' : 'refused'
}

/** Which kind of live listing the Live tab shows (the owner's ruling, 2026-09-26): '' is both. */
type LiveKind = '' | 'singles' | 'sealed'

/** THE CHEAP-CARD PRICE AS IT STANDS ON DISK, where it is not the cut-off — `null` where the two
 *  agree. A store written under the old two-figure model can say both at once, and one press
 *  resolves it, because every commit here writes both keys. */
function strandedFlat(doc: DecisionsDocument, cut: string): string | null {
  const answer = doc.sub_threshold
  if (answer === null || answer === undefined) return null
  if (typeof answer === 'string') return 'the floor'
  const flat = String((answer as Record<string, unknown>)[FLAT_KEY] ?? '')
  return flat !== '' && cents(flat) !== cents(cut) ? flat : null
}

function writtenCut(policy: Record<string, unknown> | undefined): string | null {
  const value = policy?.['threshold']
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

/** Which bucket a row is in AT A GIVEN CUT-OFF: `pipeline/pricing.py:is_listable` in the client's
 *  terms. Typing on a row moves nothing; only the cut-off, a policy figure, re-partitions. */
function bucketAt(sku: PricingSku, cut: string): PricingSku['bucket'] {
  if (sku.bucket === 'no_market_data') return sku.bucket
  const market = cents(sku.snap.market)
  const line = cents(cut)
  if (market === null || line === null) return sku.bucket
  return market >= line ? 'listable' : 'sub_threshold'
}

/** How old a reading is, in words. A live figure is never drawn without one. */
function ageWords(at: number | null | undefined): string | null {
  if (typeof at !== 'number' || !Number.isFinite(at) || at <= 0) return null
  const seconds = Math.max(0, Date.now() / 1000 - at)
  if (seconds < 90) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.max(1, Math.round(hours / 24))
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  const months = Math.round(days / 30)
  return `${months} month${months === 1 ? '' : 's'} ago`
}

function runOverride(book: PricingCorpus | null, run: string | null): SubAnswer | undefined {
  if (book === null || run === null) return undefined
  const entry = book.policy?.per_run?.[run]
  if (entry === undefined || !('sub_threshold' in entry)) return undefined
  const value = entry['sub_threshold']
  if (typeof value === 'string') return value
  if (typeof value === 'object' && value !== null && FLAT_KEY in value) return value as { flat: string }
  return undefined
}

function runCut(book: PricingCorpus | null, run: string | null): string | undefined {
  if (book === null || run === null) return undefined
  return writtenCut(book.policy?.per_run?.[run]) ?? undefined
}

/** Patch one run's policy, returning a NEW corpus. A key set to `undefined` is cleared, and an
 *  empty entry — and `per_run` itself — is pruned (`pipeline/corpus.py:policy_for` folds these). */
function withRunPolicy(book: PricingCorpus, run: string, patch: Record<string, unknown>): PricingCorpus {
  const table: Record<string, Record<string, unknown>> = { ...(book.policy?.per_run ?? {}) }
  const entry: Record<string, unknown> = { ...(table[run] ?? {}) }
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) delete entry[key]
    else entry[key] = value
  }
  if (Object.keys(entry).length === 0) delete table[run]
  else table[run] = entry
  const policy = { ...book.policy }
  if (Object.keys(table).length === 0) delete policy.per_run
  else policy.per_run = table
  return { ...book, policy }
}

/** Short labels for the hold reasons; the full sentence is drawn beneath the chips. */
const HOLD_SHORT: Record<WithholdReason, string> = {
  bullish: 'Bullish',
  keeping: 'Keeping this one',
  next_batch: 'A later batch',
}

function heldReason(value: WithheldRecord | 'unlisted'): string {
  return value === 'unlisted' ? '' : String(value.withheld ?? '')
}

/** The Undo toast's body, off the server's own reason per skipped SKU — never re-guessed on
 *  the screen. A SKU the operator priced again since the clear reads differently from one a
 *  later kept clear already holds; the old string called both "answered again since", which
 *  was wrong for the second case. */
function restoreSkipBody(skipped: PricingRestoreSkip[]): string {
  if (skipped.length === 0) return 'Each one carries the date it was first typed on.'
  const answered = skipped.filter((row) => row.reason === 'answered_since').length
  const newer = skipped.length - answered
  if (newer === 0) {
    return `${answered} had been answered again since, and ${answered === 1 ? 'that answer was' : 'those answers were'} kept.`
  }
  if (answered === 0) {
    return `${newer} ${newer === 1 ? 'is' : 'are'} held by a later clear instead.`
  }
  return `${answered} answered again since, ${newer} held by a later clear.`
}

/** What TCGplayer holds of a row NOW: the newest live export on disk (`live_now`, round 7), or
 *  the join's own figures where no live export was ever fetched. */
function liveOf(row: PricingSku): { copies: number; price: string | null } {
  if (row.live_now) return { copies: row.live_now.copies, price: row.live_now.price }
  return { copies: Math.max(row.live_before, row.listing?.live ?? 0), price: row.snap.now }
}

function targetOf(bucket: PricingSku['bucket']): 'overrides' | 'no_market_data' {
  return bucket === 'no_market_data' ? 'no_market_data' : 'overrides'
}

/** Why this run adds no row for this SKU, as a heading — or null for the ordinary row. */
function groupOf(sku: PricingSku): string | null {
  return sku.at_cap ? (sku.nothing_to_add ?? 'nothing to add this run') : null
}

/* ONE VOCABULARY (UN-5, finding #15, the Opus review round): a reversal reads "<what it
 * undid> undone" (`docs/specs/undo.md` §11.10). `id` (finding #2) lets a toast's own Undo
 * reverse THE CHANGE IT NAMES, never whatever the stack's front holds by the time the
 * button is actually pressed — a hold set on one row and then another must not let the
 * second row's toast undo the first's write. */
/** UN-12 (the delta review round): `writes` is an ARRAY, so a batch of writes is ONE stack
 *  entry and `U` reverses all of it in one press. Every caller today writes one answer. */
type Undo = { id: number } & (
  | { kind: 'answer'; writes: readonly { sku: string; before: CorpusAnswer | undefined; channel: 'price' | 'unknown' }[] }
  | { kind: 'cutoff'; before: { threshold: string | undefined; sub_threshold: PricingCorpus['policy']['sub_threshold'] | undefined } }
)

/** The corpus as the document every reader on this screen understands, with one run's policy
 *  override folded over the store's in `corpus.py:policy_for`'s own order. */
function corpusAsDoc(book: PricingCorpus | null, run: string | null = null): DecisionsDocument {
  if (book === null) return {}
  const overrides: Record<string, unknown> = {}
  const unpriced: Record<string, unknown> = {}
  for (const [sku, answer] of Object.entries(book.skus ?? {})) {
    if (answer === null || answer === undefined) continue
    const table = answer.channel === 'unknown' ? unpriced : overrides
    table[sku] = answer.value
  }
  const over = (run === null ? undefined : book.policy?.per_run?.[run]) ?? {}
  const sub = runOverride(book, run)
  return {
    rule: (typeof over['rule'] === 'string' ? over['rule'] : undefined) ?? book.policy?.rule,
    basis: (typeof over['basis'] === 'string' ? over['basis'] : undefined) ?? book.policy?.basis,
    sub_threshold: sub ?? book.policy?.sub_threshold ?? null,
    overrides: overrides as DecisionsDocument['overrides'],
    no_market_data: unpriced as DecisionsDocument['no_market_data'],
  }
}

/** Every kept clear the server offers, newest first. An older server sends `last_clear` only. */
function keptOf(held: { last_clear?: KeptClear | null; clears?: KeptClear[] }): KeptClear[] {
  if (held.clears !== undefined) return held.clears
  return held.last_clear ? [held.last_clear] : []
}

/** The corpus with a clear's answers put back — ONLY the SKUs the server said it restored. */
function withRestored(
  book: PricingCorpus,
  restored: readonly string[],
  answers: PricingClearResult['cleared'],
): PricingCorpus {
  const skus = { ...(book.skus ?? {}) }
  for (const sku of restored) {
    const was = answers[sku]
    if (was !== undefined) skus[sku] = was
  }
  return { ...book, skus }
}

function setAnswer(book: PricingCorpus, sku: string, value: unknown, channel: 'price' | 'unknown'): PricingCorpus {
  const skus = { ...(book.skus ?? {}) }
  if (value === undefined) delete skus[sku]
  else {
    /* A NEW VALUE DROPS THE OLD DATE (the Opus review of the first-date ruling, HIGH). The
     * server dates a new price, and this book never reads that date back. So a date kept here
     * would be one the server has already replaced, and a hold would carry it forward. */
    const old = skus[sku]
    const same = old !== undefined && old !== null && JSON.stringify(old.value) === JSON.stringify(value)
    const { at: _stale, ...rest } = old ?? {}
    skus[sku] = { ...(same ? (old ?? {}) : rest), value: value as never, channel }
  }
  return { ...book, skus }
}

/** Whether the shell is in its phone layout, where a popover becomes a sheet. */
function usePhone(): boolean {
  const [phone, setPhone] = useState(() => window.matchMedia('(max-width: 639px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 639px)')
    const sync = () => setPhone(query.matches)
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])
  return phone
}

/** THE NUMBER'S OWN TRAILING FORM IN A NAME, never a stray digit inside a longer word (the
 *  coordinator's review, 2026-09-26, catching a defect in the first cut of this same lane: a
 *  plain `name.includes(number)` hid the chip on any name that happened to CONTAIN the
 *  number's characters anywhere, with nothing marking it as the same fact). The two real
 *  forms this repo's names take are parenthesised ("Calm Rune (R02a)") and a trailing "- "
 *  ("Garganacl - 084/132"), both anchored at the end of the string — never a bare substring
 *  match. */
function numberSuffix(number: string): RegExp | null {
  const trimmed = number.trim()
  if (trimmed === '') return null
  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`\\s*(\\(${escaped}\\)|-\\s*${escaped})\\s*$`)
}

/** THE NUMBER LIVES IN ONE PLACE ON A ROW, THE META LINE, NEVER BOTH THERE AND IN THE NAME (the
 *  owner's review, 2026-09-26: "Garganacl - 084/132" carried it in the name while every other
 *  row carried it in the meta line — the same fact stated two ways, in two different spots,
 *  depending on which name happened to already hold it). The meta line always draws the
 *  number when the row has one; this strips a trailing repeat off the DISPLAYED name only —
 *  the stored name is never touched. */
/* F3 (the owner's word, 2026-09-29): THE FILTERS ARE VIEW-ONLY. `docs/reviews/ux-2026-09-23/F3-pricing-filters.md`
   is the design. Price bands read the MARKET cell and nothing else. A row with no market price is
   its own band (D49: a missing price is unknown, never low). */
const BANDS = [
  { value: 'none', text: 'No market price', label: <>No market price</>, within: (c: number | null) => c === null },
  { value: 'under1', text: 'Under one dollar', label: <>Under <Money value={1} /></>, within: (c: number | null) => c !== null && c < 100 },
  { value: 'to5', text: 'One to five dollars', label: <><Money value={1} /> to <Money value={5} /></>, within: (c: number | null) => c !== null && c >= 100 && c < 500 },
  { value: 'to20', text: 'Five to twenty dollars', label: <><Money value={5} /> to <Money value={20} /></>, within: (c: number | null) => c !== null && c >= 500 && c < 2000 },
  { value: 'over20', text: 'Twenty dollars and up', label: <><Money value={20} /> and up</>, within: (c: number | null) => c !== null && c >= 2000 },
] as const

function bandOf(row: PricingSku): string {
  const c = cents(row.snap.market)
  return BANDS.find((band) => band.within(c))?.value ?? 'none'
}

type PricingSortKey = 'arranged' | 'price' | 'name'
const SORT_OPTIONS: readonly SortOption<PricingSortKey>[] = [
  { key: 'arranged', label: 'Suggested', asc: 'Needs you first', desc: 'Needs you first', first: 'desc' },
  { key: 'price', label: 'Market price', desc: 'High to low', asc: 'Low to high', first: 'desc' },
  { key: 'name', label: 'Name', desc: 'Z to A', asc: 'A to Z', first: 'asc' },
]
const SORT_AT_REST: SortValue<PricingSortKey> = { key: 'arranged', dir: 'desc' }

function facetValueOf(row: PricingSku, key: string): string {
  return key === 'game' ? row.game : key === 'set' ? row.set_name : bandOf(row)
}

function displayName(name: string, number: string): string {
  const pattern = numberSuffix(number)
  return pattern === null ? name : name.replace(pattern, '')
}

/* ------------------------------------------------------------------- the needs-you flags */

/** WHY A ROW NEEDS THE OWNER (D277, Q2): no market price, worth $5 or more, or a typed price
 *  25% or more away from today's market. A held row and a row with nothing to add need nothing:
 *  both are answered. */
type Flag = { kind: 'no-market' | 'worth' | 'drift'; text: ReactNode; tone: 'danger' | 'warn' }

function flagOf(row: PricingSku, standing: unknown, locked: boolean, cut: string): Flag | null {
  if (row.at_cap || locked || isWithheld(standing)) return null
  const market = cents(row.snap.market)
  if (market === null) {
    return typeof standing === 'string' ? null : { kind: 'no-market', text: 'No market price', tone: 'danger' }
  }
  const typed = typeof standing === 'string' ? cents(standing) : null
  /* THE CUT-OFF IS NOT A DRIFT. A card worth less than the cut-off lists AT the cut-off (D99), so
     a typed price equal to it is the floor doing its job: nothing can list lower. Flagging it
     would put every cheap card on top, which is the opposite of "zero attention per card". */
  const floor = cents(cut)
  const clamped = typed !== null && floor !== null && typed === floor && market < floor
  /* EXACT, IN WHOLE CENTS (Q2 says "25% or more"): no rounding decides which side of the edge
     a row is on. Only the words round the figure they print. */
  if (typed !== null && market > 0 && !clamped && Math.abs(typed - market) * 100 >= DRIFT_PCT * market) {
    const pct = Math.round((Math.abs(typed - market) / market) * 100)
    return { kind: 'drift', text: `${pct}% ${typed < market ? 'under' : 'over'} market`, tone: 'warn' }
  }
  if (market >= WORTH_A_LOOK) {
    return {
      kind: 'worth',
      text: (
        <>
          Worth <Money value={WORTH_A_LOOK / 100} /> or more
        </>
      ),
      tone: 'warn',
    }
  }
  return null
}

/** ON THE LIVE TAB A LISTING'S WORTH IS NOT A REASON TO LOOK (the owner's ruling, 2026-09-26):
 *  it is already live at a price somebody chose. No market price and a typed drift still say so. */
function liveFlag(flag: Flag | null, live: boolean): Flag | null {
  return live && flag?.kind === 'worth' ? null : flag
}

/** Highest market first; a row with no market price is the most urgent, so it leads. */
function byValue(a: PricingSku, b: PricingSku): number {
  const va = cents(a.snap.market) ?? Number.POSITIVE_INFINITY
  const vb = cents(b.snap.market) ?? Number.POSITIVE_INFINITY
  return vb - va || a.name.localeCompare(b.name)
}

/** THE ORDER IS TAKEN ONCE, ON ARRIVAL (D118, D181). A price typed on a row may give it a flag,
 *  and the chip appears on the row; the row does not move under the hand. The next load re-ranks. */
type Arrival = { key: object; needs: ReadonlySet<string>; order: ReadonlyMap<string, number> }

function takeArrival(
  key: object,
  rows: readonly PricingSku[],
  answerOf: (row: PricingSku) => unknown,
  locked: (sku: string) => string | null,
  cut: string,
  live = false,
): Arrival {
  const needs = new Set<string>()
  const flagged: PricingSku[] = []
  const rest: PricingSku[] = []
  const closed: PricingSku[] = []
  /* ON THE LIVE TAB ONLY A ROW WITH NO MARKET PRICE NEEDS THE OWNER (the owner's ruling,
     2026-09-26, "Skip no-market cards"): the rule never lowers it, so a price there is the
     owner's to type. A live listing worth $5 or more already carries a price somebody chose. */
  const needsOwner = (row: PricingSku): boolean =>
    live
      ? row.snap.market === null && locked(row.sku) === null && !isWithheld(answerOf(row))
      : flagOf(row, answerOf(row), locked(row.sku) !== null, cut) !== null
  for (const row of rows) {
    if (row.at_cap) closed.push(row)
    else if (needsOwner(row)) {
      needs.add(row.sku)
      flagged.push(row)
    } else rest.push(row)
  }
  flagged.sort(byValue)
  rest.sort(byValue)
  closed.sort(byValue)
  const order = new Map<string, number>()
  for (const row of [...flagged, ...rest, ...closed]) order.set(row.sku, order.size)
  return { key, needs, order }
}

/* ------------------------------------------------------------------------ small parts */

/** The run picker — a filter over the worklist, never a gate in front of it (D86). */
function PickRuns({
  runs,
  picked,
  onToggle,
  onClear,
}: {
  runs: readonly RosterRun[]
  picked: ReadonlySet<string>
  onToggle: (run: string) => void
  onClear: () => void
}) {
  const order = [...runs].sort((a, b) => {
    const day = (b.created_at ?? '').slice(0, 10).localeCompare((a.created_at ?? '').slice(0, 10))
    if (day !== 0) return day
    return (a.box ?? 0) - (b.box ?? 0) || a.run.localeCompare(b.run)
  })
  const open = runs.filter((row) => row.open).length
  return (
    <div className="pricing-runs" role="group" aria-label="Which runs to price">
      <p className="pricing-runs-count">
        {picked.size === 0 ? `Showing all ${open} with work left` : `${picked.size} picked`}
      </p>
      <div className="pricing-runs-list">
        {order.map((row) => {
          const label = runBoxLabel(row)
          const day = row.created_at ? absoluteDate(row.created_at) : null
          const on = picked.has(row.run)
          return (
            <button
              key={row.run}
              type="button"
              className={`pricing-run${on ? ' pricing-run-on' : ''}${row.open ? ' pricing-run-open' : ''}`}
              aria-pressed={on}
              onClick={() => onToggle(row.run)}
            >
              <span className="pricing-run-check" aria-hidden="true">
                <Icon name="check" size={12} />
              </span>
              <span className="pricing-run-text">
                <span className="pricing-run-name">
                  {label ?? row.run}
                  {label === null || day === null ? null : <span className="pricing-run-day">{day}</span>}
                </span>
                <span className="pricing-run-meta">
                  {/* THE DIRECTORY IS WHAT TELLS TWO RUNS OVER ONE BOX APART: drawn small (D56). */}
                  {label === null ? null : <span className="pricing-run-id">{row.run}</span>}
                  <span>{row.counts?.skus ?? '?'} SKUs</span>
                </span>
              </span>
              {/* THREE STATES, NOT TWO (D156): a run that owes nothing and still holds unsent
                  copies is OPEN, and the chip says how many. */}
              <Pill tone={row.open ? 'warn' : 'ok'} className="pricing-run-owes">
                {runChip(row)}
              </Pill>
            </button>
          )
        })}
      </div>
      {picked.size === 0 ? null : (
        <Button size="sm" variant="ghost" icon="x" onClick={onClear}>
          Show everything unsent
        </Button>
      )}
    </div>
  )
}

/** A LIVE COUNT IS NEVER DRAWN WITHOUT ITS AGE (the owner, 2026-09-03), and the big figure is
 *  the estimate: the reading less what has sold here since (D115), through `forSale`. */
function LiveCount({ live, soldHere, age }: { live: number; soldHere: number | undefined; age: string | null }) {
  const forSaleNow = forSale(live, soldHere)
  const sold = soldSince(soldHere)
  return (
    <span
      className="pricing-live"
      data-none={forSaleNow === 0 ? 'true' : undefined}
      title={
        sold > 0
          ? `TCGplayer held ${live} when this was read${age === null ? '' : `, ${age}`}. ${sold} sold here since.`
          : `What TCGplayer held when this was read${age === null ? '' : `, ${age}`}.`
      }
    >
      {forSaleNow === 0 ? 'None' : forSaleNow} listed
    </span>
  )
}

/* THE ROW THUMBNAILS ARE CROPPED TO THE CARD (D125): one card per call, only what an observer
   has brought near the viewport, answered once per session. 0.34 keeps the art and the name. */
const THUMB_FOCUS = 0.34

function PricingThumb({
  at,
  name,
  onOpen,
  imageUrl,
}: {
  at: PricingSku['positions'][number] | null
  name: string
  onOpen: () => void
  /** The stock photo (`D301`), the MAIN view here per the owner's own ask — "if
   *  it'd be easy to live pull all the photos without much lag I'd be happy to have the
   *  stock photos show as the main view". `null` on a join miss, and a load failure falls
   *  back to the owner's own photograph below exactly as if `imageUrl` had been `null` —
   *  never a broken-image icon. */
  imageUrl: string | null
}) {
  const host = useRef<HTMLButtonElement | null>(null)
  const crop = useCardCropWhenSeen(at, host)
  const [stockFailed, setStockFailed] = useState(false)
  const showStock = imageUrl !== null && !stockFailed
  return (
    <button ref={host} type="button" className="pricing-thumb" aria-label={`Photograph of ${name}`} onClick={onOpen}>
      {showStock ? (
        <img
          className="bn-crop pricing-stock-img"
          src={imageUrl}
          alt=""
          loading="lazy"
          onError={() => setStockFailed(true)}
        />
      ) : at === null || photoUrl(at.box, at.index, at) === null ? (
        <Icon name="image" size={14} />
      ) : (
        <img
          className="bn-crop"
          /* BY NAME (D172): `_relabel_positions` decorates each position with the card's cid at read
             time. The frozen run file is untouched; the slot route remains where none is found. */
          src={photoUrl(at.box, at.index, at) ?? undefined}
          alt=""
          loading="lazy"
          /* `data-cropped` BELONGS ON THE IMG, NOT THE BUTTON (the owner's review, 2026-09-26):
             `kit.css`'s `img.bn-crop[data-cropped='true']` rule reads the attribute off the
             element it draws on. Set on the button instead, the selector never matched, the
             image kept the base rule's `inset: 0`, and `cropStyle`'s own translate then shoved
             a same-sized box up past the tile's edge — a sliver of the card in the corner over
             empty grey, on every row. `Home.tsx`'s hero already sets it on its own `<img>`; this
             was the one place `.bn-crop` disagreed with its own contract. */
          data-cropped={crop === null ? undefined : 'true'}
          style={cropStyle(crop, THUMB_FOCUS)}
          onError={(event) => {
            event.currentTarget.style.visibility = 'hidden'
          }}
        />
      )}
    </button>
  )
}

/** One sentence for a mark-down send that did not land. None of the three first answers is a
 *  retry (the server answers them 409), so no press here can send the prices twice. */
function shipTroubleTitle(code: string): string {
  switch (code) {
    case 'send_unknown':
      return 'TCGplayer did not confirm these prices. Do not send them again. Banchi checks after the wait.'
    case 'send_in_progress':
      return 'A send to TCGplayer is already running, so nothing was sent again.'
    case 'send_held':
      return 'These prices wait on a send TCGplayer has not confirmed, so nothing was sent.'
    default:
      return 'Nothing was sent. The prices at TCGplayer did not change.'
  }
}

/** What the rule says, in words, for the one line above the list (D277, Q5). */
function ruleWords(doc: DecisionsDocument): string {
  const preset = PRESETS.find((p) => p.rule === doc.rule && p.basis === doc.basis)
  if (preset !== undefined) return preset.says
  const custom = parseCustomRule(doc.rule, doc.basis)
  if (custom !== null) return customSays(custom)
  return 'New cards list at the rule your pricing file names'
}

/** The mark-down settings the newest read was taken with, in words. */
function markdownWords(asked: Record<string, unknown> | undefined): string {
  const days = Number(asked?.['days'] ?? 7)
  const rule = asked?.['rule']
  const pct = asked?.['percent']
  const basis = asked?.['basis']
  const off =
    rule === 'match'
      ? 'priced at'
      : `${pct === undefined || pct === null || pct === '' ? '10' : String(pct)}% under`
  const from = basis === 'market' ? 'market' : basis === 'low' ? 'the lowest listing' : 'your asking price'
  return `Not sold in ${Number.isFinite(days) ? days : 7} days, ${off} ${from}`
}

/** The read's dollar cap as a number, or null where it has none (the owner's ruling, 2026-09-26).
 *  A `match` read takes nothing off, so it has no cap to say. */
function markdownCap(asked: Record<string, unknown> | undefined): number | null {
  if (asked?.['rule'] === 'match') return null
  const cap = moneyField(typeof asked?.['cap'] === 'string' ? asked['cap'] : null)
  return cap === null ? null : Number(cap)
}

/* ============================================================================== the screen */

export function Pricing() {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  /** Which runs the worklist is over; EMPTY means "whatever still has work in it" (D86, D156). */
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set(runsInHash()))
  const [work, setWork] = useState<PricingWorklist | null>(null)
  /** THE MARKDOWN STAMP ON THE HASH, and the table it names (D103). Null is the Unsent tab. */
  const [stamp, setStamp] = useState<string | null>(() => markdownInHash())
  const [liveTab, setLiveTab] = useState<boolean>(() => liveInHash())
  const [sheet, setSheet] = useState<MarkdownTable | null>(null)
  const [push, setPush] = useState<'idle' | 'sending' | 'writing'>('idle')
  const [applied, setApplied] = useState<MarkdownAnswer | null>(null)
  const [wroteUpload, setWroteUpload] = useState(false)
  /* WHETHER THE FILE'S LINK WAS ON SCREEN WHEN THE PRESS BEGAN (round 9, R9-1): nothing appears
     or vanishes beside the press while it runs (D118). */
  const [linkHeld, setLinkHeld] = useState(false)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  /** The pricing corpus — one document for the store, and the authority (D86). */
  const [book, setBook] = useState<PricingCorpus | null>(null)
  /* A NUMBER ON A CARD'S ROW, THIS PRESS ONLY (D7, amended 2026-09-11): the copies that go in
     this file, as typed. Blank is blank and not zero. Spent by the write. */
  const [sendQty, setSendQty] = useState<Record<string, string>>({})
  const askedFor = useCallback(
    (sku: string): number | undefined => {
      const text = sendQty[sku]
      if (text === undefined || text === '') return undefined
      const asked = Number.parseInt(text, 10)
      return Number.isFinite(asked) ? asked : undefined
    },
    [sendQty],
  )
  const setAsked = useCallback((sku: string, text: string) => {
    setSendQty((held) => {
      const now = { ...held }
      if (text === '') delete now[sku]
      else now[sku] = text
      return now
    })
  }, [])
  const clearAsked = useCallback(() => setSendQty({}), [])
  /* WHAT THE PRESS SENDS: every drawn row with a figure typed on it, as SKU -> copies. */
  const latestRows = useRef<readonly PricingSku[]>([])
  const quantitiesAsked = useCallback((): Record<string, number> => {
    const out: Record<string, number> = {}
    for (const row of latestRows.current) {
      if (row.at_cap) continue
      const asked = askedFor(row.sku)
      if (asked !== undefined) out[row.sku] = asked
    }
    return out
  }, [askedFor])

  const toggleRun = useCallback((name: string) => {
    setPicked((held) => {
      const now = new Set(held)
      if (now.has(name)) now.delete(name)
      else now.add(name)
      return now
    })
  }, [])
  const clearPicked = useCallback(() => setPicked(new Set()), [])
  const [saving, setSaving] = useState(false)
  const [undo, setUndo] = useState<Undo[]>([])
  const nextUndoId = useRef(1)
  const [holdFor, setHoldFor] = useState<string | null>(null)
  const holdAnchor = useRef<HTMLElement | null>(null)
  const holdButtons = useRef(new Map<string, HTMLButtonElement>())
  const [photoFor, setPhotoFor] = useState<{ sku: string; at: number } | null>(null)

  /* The trend strip (D79), cleared when the loaded set changes. */
  const [trends, setTrends] = useState<Record<string, TrendRead>>({})
  const [trendRun, setTrendRun] = useState<{ total: number; done: number; reading: boolean } | null>(null)
  const trendWalk = useRef(0)
  const [note, setNote] = useState<{ sku: string; text: string } | null>(null)
  /** Holding: the held rows alone (UX-212). */
  const [filterHeld, setFilterHeld] = useState(false)
  /** WHICH LIVE LISTINGS ARE ON SCREEN (D103): a filter the owner applies, never a gate. */
  const [lens, setLens] = useState<'all' | 'offered' | 'refused'>('all')
  /** SINGLES OR SEALED, IN THE URL (D285; the owner's ruling, 2026-09-26). '' shows both. */
  const [kindParam, setKindParam] = useViewParam('kind')
  const kind: LiveKind = kindParam === 'singles' || kindParam === 'sealed' ? kindParam : ''

  const [customDraft, setCustomDraft] = useState<CustomRule>({ kind: 'undercut', pct: '', basis: 'market' })
  const [pressedCustom, setPressedCustom] = useState(false)
  const [customBad, setCustomBad] = useState<string | null>(null)
  const customSeed = useRef<string | null>(null)
  const [runsOpen, setRunsOpen] = useState(false)
  const runsAnchor = useRef<HTMLButtonElement | null>(null)
  const [ruleOpen, setRuleOpen] = useState(false)

  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [shipTrouble, setShipTrouble] = useState<Failure | null>(null)

  const inputs = useRef(new Map<string, HTMLInputElement>())
  const loadWalk = useRef(0)
  /** The digest of `inventory/prices.json` as this screen last saw it (D86's stale-write guard). */
  const revision = useRef<string>('')
  const savedBook = useRef<PricingCorpus | null>(null)
  const inFlight = useRef(false)
  const failedBook = useRef<PricingCorpus | null>(null)
  const touched = useRef(new Set<string>())
  const phone = usePhone()

  useEffect(() => {
    const fromHash = () => {
      if (!window.location.hash.startsWith('#/pricing')) return
      const named = runsInHash()
      if (named.length > 0) setPicked(new Set(named))
      setStamp(markdownInHash())
      setLiveTab(liveInHash())
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  /* THE LINK OPENS WHAT ITS LABEL COUNTED (UX-078): no run is picked for the visitor. The old
     demo auto-pick existed because the drawer and the trends were per-run; the product view reads
     by SKU and the trends ask each row's own run, so the whole worklist works. */
  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const rows = await getRuns()
        if (live) setRuns(rows)
      } catch (err) {
        if (live) setFailure(describeFailure(err))
      }
    })()
    return () => {
      live = false
    }
  }, [])

  /* THE LIVE TAB WITH NO STAMP OPENS THE NEWEST READ, or says there is none (D277, Q6). */
  const [markdowns, setMarkdowns] = useState<readonly MarkdownSummary[] | null>(null)
  useEffect(() => {
    if (!liveTab) return
    let live = true
    void getMarkdowns()
      .then((answer) => {
        if (!live) return
        setMarkdowns(answer.markdowns)
        const newest = answer.markdowns[0]
        if (stamp === null && newest !== undefined) window.location.hash = `#/pricing?markdown=${newest.stamp}`
      })
      .catch((err) => {
        if (live) setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [liveTab, stamp])

  /** Fetch the rows and the corpus together. One read whatever the tab (D103). */
  const load = useCallback(async (wanted: ReadonlySet<string>, markdown: string | null, live: boolean) => {
    trendWalk.current += 1
    setTrends({})
    setTrendRun(null)
    loadWalk.current += 1
    const mine = loadWalk.current
    if (live && markdown === null) {
      setWork(null)
      setSheet(null)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [rowsFrom, held] = await Promise.all([
        markdown === null ? getPricingWorklist([...wanted].sort()) : getMarkdownTable(markdown),
        getPricingCorpus(),
      ])
      if (mine !== loadWalk.current) return
      const answer = markdown === null ? (rowsFrom as PricingWorklist) : null
      const table = markdown === null ? null : (rowsFrom as MarkdownTable)
      setWork(answer)
      setSheet(table)
      setBook(held.corpus)
      setClearable(held.clearable ?? null)
      setKept(keptOf(held))
      revision.current = held.revision
      savedBook.current = held.corpus
      failedBook.current = null
      setFailure(null)
      setUndo([])
      setShipTrouble(null)
      if (answer !== null && answer.runs.length === 1) {
        try {
          setDetail(await getRun(answer.runs[0]?.run as string))
        } catch (err) {
          setDetail(null)
          setShipTrouble(describeFailure(err))
        }
      } else {
        setDetail(null)
      }
    } catch (err) {
      if (mine !== loadWalk.current) return
      setWork(null)
      setSheet(null)
      setBook(null)
      setClearable(null)
      setFailure(describeFailure(err))
    } finally {
      if (mine === loadWalk.current) setLoading(false)
    }
  }, [])

  const reload = useCallback(() => void load(picked, stamp, liveTab), [load, picked, stamp, liveTab])

  useEffect(() => {
    void load(picked, stamp, liveTab)
  }, [picked, stamp, liveTab, load])

  const loaded = useMemo(() => (work?.runs ?? []).map((row) => row.run), [work])
  const run = loaded.length === 1 ? (loaded[0] as string) : null

  const source: PricingSource = useMemo(
    () =>
      stamp === null
        ? runSource(work, run, SECTIONS, { history: getPriceHistory, trends: getPriceTrends })
        : markdownSource(stamp, sheet, LIVE_SECTIONS, { history: markdownHistory, trends: markdownTrends }),
    [stamp, sheet, work, run],
  )
  const doc = useMemo(() => corpusAsDoc(book, run), [book, run])

  /* THE CUT-OFF IN FORCE, in `pipeline/corpus.py:policy_for`'s order: this run's own figure,
     then the store's, then the server's copy of the store's (which is the only true answer for
     a store that never set one), then the default. */
  const storeCut = writtenCut(book?.policy)
  const thisRunCut = runCut(book, run)
  const cut = thisRunCut ?? storeCut ?? work?.threshold ?? sheet?.floor ?? STORE_DEFAULT_CUT

  /* UNSAVED IS A COMPARISON, NOT A FLAG — and deliberately not memoised: `savedBook` is a ref. */
  const dirty = book !== null && book !== savedBook.current

  /* ONE PUT IN FLIGHT, COALESCING. */
  useEffect(() => {
    if (!dirty || book === null) return
    if (inFlight.current || book === failedBook.current) return
    const sent = book
    inFlight.current = true
    setSaving(true)
    void (async () => {
      try {
        const receipt = await putPricingCorpus(sent, revision.current)
        revision.current = receipt.revision
        savedBook.current = sent
        failedBook.current = null
        setFailure(null)
      } catch (err) {
        failedBook.current = sent
        setFailure(describeFailure(err))
      } finally {
        inFlight.current = false
        setSaving(false)
      }
    })()
  }, [dirty, book, saving])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || saving) event.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty, saving])

  const queued = runs.find((row) => row.run === run)?.counts?.queued_main ?? 0

  /** Set the STORE-WIDE cut-off. BOTH KEYS, ALWAYS: the line and what the half below it lists at
   *  are one figure (the owner, 2026-09-03), so this screen has no way to write one alone.
   *  UN-13 (finding #15, `docs/specs/undo.md` §11.10): a cut-off change is a reversal too, so
   *  it gets the same "<subject> undone" toast every other write on this screen gets. */
  const setCut = useCallback((figure: string) => {
    /* FINDING #6 (the delta review round): a no-op guard, only when the STORED policy already
     * reads this figure — never when the field simply shows a default nobody has written yet.
     * The prior guard sat in `BigMoney` and compared its own `value` prop, which is the
     * suggestion for an unwritten policy — a store that has never set one reads $0.40 from
     * the constant, and the field shows it too, so typing that same default in was wrongly
     * read as a no-op and its write silently swallowed. `book?.policy` is the actual stored
     * answer, undefined until a PUT has landed, so an unwritten policy never matches here. */
    const storedThreshold = book?.policy?.threshold
    const storedFlat = book?.policy?.sub_threshold
    const storedFlatValue = typeof storedFlat === 'string' ? storedFlat : storedFlat !== null && storedFlat !== undefined ? storedFlat[FLAT_KEY] : undefined
    if (storedThreshold === figure && storedFlatValue === figure) return
    const id = nextUndoId.current++
    setUndo((stack) =>
      [
        { id, kind: 'cutoff' as const, before: { threshold: book?.policy?.threshold, sub_threshold: book?.policy?.sub_threshold } },
        ...stack,
      ].slice(0, UNDO_DEPTH),
    )
    toast({
      kind: 'receipt',
      title: 'Cut-off changed',
      body: `The store-wide rule now reads ${figure}.`,
      ttlMs: 8000,
      action: { label: 'Undo', kbd: 'U', onPress: () => undoByIdRef.current(id) },
    })
    setBook((current) =>
      current === null
        ? current
        : { ...current, policy: { ...current.policy, threshold: figure, sub_threshold: { [FLAT_KEY]: figure } } },
    )
  }, [book])

  const setRunCut = useCallback(
    (figure: string | undefined) => {
      if (run === null) return
      const patch =
        figure === undefined
          ? { threshold: undefined, sub_threshold: undefined }
          : { threshold: figure, sub_threshold: { [FLAT_KEY]: figure } }
      setBook((current) => (current === null ? current : withRunPolicy(current, run, patch)))
    },
    [run],
  )

  const saveFailed = useCallback(() => book !== null && failedBook.current === book, [book])

  /* THE PRICES THE OWNER TYPED ON THIS WORKLIST, THIS VISIT (round 6). Only these may ride a send
     as a price change. Remembered nowhere, and spent by a send. */
  const [typedHere, setTypedHere] = useState<ReadonlySet<string>>(() => new Set())

  const afterSend = useCallback(() => {
    clearAsked()
    setTypedHere(new Set())
    reload()
  }, [clearAsked, reload])

  /** Write one or more answers as ONE undo entry (UN-12), pushing each one's previous value —
   *  including its ABSENCE — onto the undo stack together. Returns the entry's own id
   *  (finding #2), so a toast can reverse THIS write and never whatever the stack's front
   *  holds by the time the button is pressed. `before` is read off the SAME `book` for every
   *  op in the batch — the state before any of them landed, never a later op's own write. */
  const writeMany = useCallback(
    (ops: readonly { sku: string; bucket: PricingSku['bucket']; value: unknown; channel?: 'price' | 'unknown'; at?: string }[]): number => {
      /* `channel` NAMES THE CHANNEL OUTRIGHT, for a release that puts back the answer a hold
       * replaced on the channel it was stored on. Otherwise the bucket decides. */
      const writes = ops.map(({ sku, bucket, channel }) => ({
        sku,
        before: book?.skus?.[sku],
        channel: channel ?? ((targetOf(bucket) === 'no_market_data' ? 'unknown' : 'price') as 'price' | 'unknown'),
      }))
      setBook((current) => {
        if (current === null) return current
        let next = current
        for (let i = 0; i < ops.length; i += 1) {
          const op = ops[i]!
          next = setAnswer(next, op.sku, op.value, writes[i]!.channel)
          /* A RELEASE NAMES THE DATE IT BRINGS BACK, or none. Never the hold's own slot's date. */
          if ('at' in op && next.skus?.[op.sku] !== undefined) {
            const { at: _dropped, ...rest } = next.skus[op.sku]!
            next = { ...next, skus: { ...next.skus, [op.sku]: op.at === undefined ? rest : { ...rest, at: op.at } } }
          }
        }
        return next
      })
      const id = nextUndoId.current++
      setUndo((stack) => [{ id, kind: 'answer' as const, writes }, ...stack].slice(0, UNDO_DEPTH))
      setTypedHere((held) => {
        const next = new Set(held)
        for (const { sku, value } of ops) {
          if (typeof value === 'string' && value !== 'unlisted') next.add(sku)
          else next.delete(sku)
        }
        return next
      })
      return id
    },
    [book],
  )
  const write = useCallback(
    (sku: string, bucket: PricingSku['bucket'], value: unknown): number => writeMany([{ sku, bucket, value }]),
    [writeMany],
  )

  const table = source.rows.length > 0 || stamp !== null ? source.rows : null
  const answers = useMemo(() => (doc?.overrides ?? {}) as Record<string, unknown>, [doc])
  const unpriced = useMemo(() => (doc?.no_market_data ?? {}) as Record<string, unknown>, [doc])
  const standingOf = useMemo(() => {
    const by = new Map<string, string>()
    for (const row of sheet?.skus ?? []) by.set(row.sku, row.standing)
    return by
  }, [sheet])
  const askingOf = useMemo(() => {
    const by = new Map<string, string | null>()
    for (const row of sheet?.skus ?? []) by.set(row.sku, row.asking)
    return by
  }, [sheet])

  /* THE LIST IS PARTITIONED AT THE CUT-OFF THIS SCREEN IS SHOWING, and the Live lens filter
     composes with it (D103). */
  const partitioned = useMemo(
    () =>
      (table ?? []).map((sku) => {
        const bucket = source.repartition ? bucketAt(sku, cut) : sku.bucket
        return bucket === sku.bucket ? sku : { ...sku, bucket }
      }),
    [table, cut, source.repartition],
  )
  const sealedOf = useMemo(() => {
    const by = new Map<string, boolean>()
    for (const row of sheet?.skus ?? []) by.set(row.sku, row.sealed === true)
    return by
  }, [sheet])
  const kindOk = useCallback(
    (sku: string) => kind === '' || (sealedOf.get(sku) === true) === (kind === 'sealed'),
    [kind, sealedOf],
  )
  const rows = useMemo(
    () =>
      standingOf.size === 0
        ? partitioned
        : partitioned.filter(
            (sku) => kindOk(sku.sku) && (lens === 'all' || liveLens(standingOf.get(sku.sku)) === lens),
          ),
    [partitioned, lens, standingOf, kindOk],
  )
  /** THE LENS COUNTS, OFF THE ROWS THE KIND FILTER KEEPS, so All is always Not selling plus
   *  Passed over. The survey's own `counts.refused` also counts sold-out rows it never draws. */
  const lensCounts = useMemo(() => {
    let offered = 0
    let refused = 0
    for (const row of sheet?.skus ?? []) {
      if (!kindOk(row.sku)) continue
      if (liveLens(row.standing) === 'offered') offered += 1
      else refused += 1
    }
    return { all: offered + refused, offered, refused }
  }, [sheet, kindOk])

  /** WHETHER THIS READ IS TOO OLD TO SEND FROM (the owner's ruling, 2026-09-26: "require a fresh
   *  read"). The limit is the server's own constant (`reprice.READ_FRESH_S`); a table that does
   *  not carry it, or a read nothing can date, is stale. */
  const readStale = useMemo(() => {
    if (sheet === null) return false
    const at = sheet.at ? Date.parse(sheet.at) : NaN
    const limit = sheet.stale_after_s
    return typeof limit !== 'number' || Number.isNaN(at) || Date.now() - at > limit * 1000
  }, [sheet])
  /* A NEW READ STARTS A NEW VISIT: what was typed over another read is not typed over this one. */
  useEffect(() => {
    setTypedHere(new Set())
  }, [stamp])


  const answerFor = useCallback(
    /* `standing.ts:corpusAnswer`'s rule: an answer on the `price` channel is read on every
     * row, a hold or a typed price (the owner's ruling). A no-market row reads the `unknown`
     * channel only when nothing sits on the `price` one. One SKU holds one answer. */
    (sku: PricingSku): unknown =>
      targetOf(sku.bucket) === 'overrides' ? answers[sku.sku] : (answers[sku.sku] ?? unpriced[sku.sku]),
    [answers, unpriced],
  )

  /* THE ARRIVAL ORDER, TAKEN ONCE PER LOAD. */
  const [arrival, setArrival] = useState<Arrival | null>(null)
  useEffect(() => {
    if (table === null || book === null) return
    if (arrival !== null && arrival.key === table) return
    setArrival(takeArrival(table, partitioned, answerFor, source.locked, cut, stamp !== null))
  }, [table, book, arrival, partitioned, answerFor, source.locked, cut, stamp])

  /** THE PAIRS THE LIVE TAB WOULD SEND, and nothing else. A price written ON THIS VISIT (typed,
   *  a preset, or "Mark down") that is not the price the read showed. And a price stored on an
   *  EARLIER visit only when it is higher than the live price (the owner's ruling, 2026-09-26:
   *  "if the price i've typed is higher yea"). A lower earlier price never goes unless it is
   *  written again here. A locked row is not pushable. A read older than a day offers none: its
   *  prices are not current. The dollar cap is the rule's only ("Rule only"): a typed price goes
   *  as typed. `earlier` is the rows that ride from an earlier visit, named on the bar (D273). */
  const { pushable, earlierRides } = useMemo(() => {
    const out: { sku: string; price: string }[] = []
    const earlier: { sku: string; name: string; price: string; was: string }[] = []
    if (stamp === null || readStale) return { pushable: out, earlierRides: earlier }
    for (const row of rows) {
      if (source.locked(row.sku) !== null) continue
      const answer = answers[row.sku]
      if (typeof answer !== 'string' || answer.trim() === '') continue
      const now = centsOf(answer)
      const was = centsOf(askingOf.get(row.sku))
      if (now !== null && was !== null && now === was) continue
      const price = moneyField(answer) ?? answer.trim()
      if (!typedHere.has(row.sku)) {
        if (now === null || was === null || now < was) continue
        earlier.push({ sku: row.sku, name: row.name, price, was: moneyField(askingOf.get(row.sku)) ?? '' })
      }
      /* SENT AS SHOWN: the field draws the answer to the cent, so the pair carries that string. */
      out.push({ sku: row.sku, price })
    }
    return { pushable: out, earlierRides: earlier }
  }, [stamp, readStale, rows, answers, source, askingOf, typedHere])

  /* THE LIVE TAB'S PRESS, SEQUENCED AFTER THE SAVE: `reprice apply` reads `prices.json` off disk
     and refuses a stale digest. It re-reads on success and adopts the new digest. ONE PRESS
     (D277, Q7): the file is written, then the server reads what is live, sends it and makes it
     live. "Download the file instead" stops after the write. There is no press that puts the old
     prices back. */
  useEffect(() => {
    if (push === 'idle' || stamp === null) return
    if (book !== null && failedBook.current === book) {
      setPush('idle')
      setShipTrouble({
        code: 'answers_not_saved',
        message: 'Your answers could not be saved, so nothing was sent. The next keystroke tries the save again.',
      })
      return
    }
    if (dirty || saving || inFlight.current) return
    const sending = push === 'sending'
    void (async () => {
      try {
        const result = await applyMarkdown(stamp, {
          edits: pushable,
          revision: revision.current,
          write: true,
          kind: kind === '' ? undefined : kind,
          /* THE SKUS TYPED THIS VISIT, so the server never reads `earlier_lower` off a
             timestamp `stamp_answers` left in the past for an unchanged value (round 8). */
          typed: pushable.map((edit) => edit.sku).filter((sku) => typedHere.has(sku)),
        })
        setApplied(result)
        setWroteUpload(result.wrote)
        if (result.revision) revision.current = result.revision
        setShipTrouble(null)
        if (sending && result.wrote) {
          await sendMarkdown(stamp)
          setTypedHere(new Set())
          void load(picked, stamp, liveTab)
          toast({
            kind: 'ok',
            title: `${pushable.length} ${pushable.length === 1 ? 'price is' : 'prices are'} live`,
            body: 'Banchi checks TCGplayer again after the wait.',
          })
        } else if (result.wrote) {
          toast({ kind: 'ok', title: 'The file is written', body: 'Download it from the bar.' })
        }
      } catch (err) {
        setShipTrouble(describeFailure(err))
      } finally {
        setPush('idle')
      }
    })()
  }, [push, stamp, pushable, dirty, saving, book, load, picked, liveTab, kind, typedHere])

  /* A NEW WRITE IS OWED THE MOMENT A PRICE MOVES. */
  useEffect(() => {
    setApplied(null)
    setWroteUpload(false)
  }, [pushable])

  const held = useMemo(() => rows.filter((sku) => isWithheld(answerFor(sku))), [rows, answerFor])

  /* F3: THE VIEW'S OWN FILTERS. Search, sort and the facets live in the URL (`?q=`, `?sort=`, `?game=`),
     narrow what is DRAWN and touch nothing else: Send, the presets and the counts read every row. */
  const [query, setQuery] = useViewParam('q')
  const [sort, setSort] = useSortParam<PricingSortKey>(SORT_AT_REST, { options: SORT_OPTIONS })
  const facetShape = useMemo<readonly FilterFacet[]>(() => {
    const games = [...new Set(rows.map((row) => row.game))].filter((game) => game !== '').sort()
    const sets = [...new Set(rows.map((row) => row.set_name))].filter((name) => name !== '').sort((a, b) => a.localeCompare(b))
    return [
      ...(games.length > 1 ? [{ key: 'game', label: 'Game', options: games.map((game) => ({ value: game, label: gameLabel(game) })) }] : []),
      ...(sets.length > 0 ? [{ key: 'set', label: 'Set', options: sets.map((name) => ({ value: name, label: name })) }] : []),
      { key: 'band', label: 'Market price', options: BANDS.map(({ value, label, text }) => ({ value, label, text })) },
    ]
  }, [rows])
  const [facetPicks, setFacetPicks] = useFacetParams(facetShape)
  const keepRow = useCallback(
    (row: MergedSku) =>
      (!filterHeld || isWithheld(answerFor(row))) &&
      matchQuery(query, { text: [row.name, row.set_name, gameLabel(row.game), row.condition], numbers: [row.row['Number']], skus: [row.sku] }),
    [filterHeld, answerFor, query],
  )
  /** The facets, each option counted under the OTHER picks and the search; a band nothing is in is not offered. */
  const facets = useMemo(
    () =>
      countFacets(rows, facetShape, facetPicks, facetValueOf, keepRow).map((facet) =>
        facet.key === 'band'
          ? { ...facet, options: facet.options.filter((option) => (option.count ?? 0) > 0 || (facetPicks.band ?? []).includes(option.value)) }
          : facet,
      ),
    [rows, facetShape, facetPicks, keepRow],
  )
  const filtering = query.trim() !== '' || Object.values(facetPicks).some((values) => values.length > 0) || filterHeld

  /** The bar's figures: what a write would put in the file, and what stays back. */
  const progress = useMemo(() => {
    let heldCount = 0
    let closed = 0
    let outRows = 0
    let outCopies = 0
    let byHand = 0
    for (const row of rows) {
      const standing = answerFor(row)
      /* A HOLD IS A FACT ABOUT THE ROW, SENT OR NOT: counted before the cap branch, so this figure
         and the "Held" press (`held`, above) read the same rows (F3). */
      const isHeld = isWithheld(standing)
      if (isHeld) heldCount += 1
      if (row.at_cap) {
        closed += 1
        continue
      }
      if (isHeld) continue
      /* THE ONE ROW RULE HOME ALSO READS (`standing.ts:rowShare`): a row with no market price
         and no answer is left out of the send, so it is never among the ready copies (Q3). */
      const share = rowShare(row, standing)
      if (share.needsPrice) continue
      const asked = askedFor(row.sku)
      if (asked !== undefined) byHand += 1
      const going = asked === undefined ? share.ready : Math.min(asked, share.ready)
      if (going === 0) continue
      outRows += 1
      outCopies += going
    }
    return { held: heldCount, closed, outRows, outCopies, byHand }
  }, [rows, answerFor, askedFor])

  /* ROWS WITH NO MARKET PRICE AND NO ANSWER: they stay on the list and stay out of a send (Q3,
     D49: a missing price is unknown, not low). Counted off the rows, which is what is drawn. */
  const needsPrice = rows.filter((row) => rowShare(row, answerFor(row)).needsPrice).length

  /* THE MIXED SEND'S PRICE CHANGES (the owner's ruling, 2026-09-24: "Allow mixed"). A row this
     press adds no copy of, already live, whose TYPED price is not the live one. The server
     applies `pipeline/sendguard.py:price_changes` against a fresh read; this only gives the
     press its words. */
  const priceChanges = useMemo(() => {
    const out: { sku: string; price: string; was: string | null }[] = []
    if (source.kind !== 'run') return out
    for (const row of rows) {
      if (!typedHere.has(row.sku)) continue
      const typed = answerFor(row)
      if (typeof typed !== 'string') continue
      const addsNone = row.at_cap || askedFor(row.sku) === 0
      const now = liveOf(row)
      if (!addsNone || now.copies <= 0) continue
      if (now.price !== null && Number(typed) === Number(now.price)) continue
      out.push({ sku: row.sku, price: typed, was: now.price })
    }
    return out
  }, [rows, answerFor, askedFor, typedHere, source.kind])

  useEffect(() => {
    latestRows.current = rows
  }, [rows])

  /** The rule's per-SKU figure, where this screen has one honestly: a preset ships a column; a
   *  custom rule does not, so the field is left empty and the send prices it (D54). */
  const ruleFigure = useCallback(
    (sku: PricingSku): string => {
      const match = PRESETS.find((p) => p.rule === doc?.rule && p.basis === doc?.basis)
      if (match !== undefined) return sku.presets[match.key] ?? ''
      if (typeof doc?.rule !== 'string') return sku.rule_price ?? ''
      return ''
    },
    [doc],
  )

  const suggestionFor = useCallback(
    (sku: PricingSku): string => (sku.bucket === 'sub_threshold' ? cut : ruleFigure(sku)),
    [cut, ruleFigure],
  )

  /* THE LIVE COPIES A LISTING ROW MOVES (the owner's ruling, round 7): a new copy of a card
     already live carries the stored price, and the live copies move with it. */
  const liveMoves = useMemo(() => {
    const out: LiveMove[] = []
    if (source.kind !== 'run') return out
    for (const row of rows) {
      if (row.at_cap) continue
      const asked = askedFor(row.sku)
      const going = asked === undefined ? row.add_to_quantity : Math.min(asked, row.add_to_quantity)
      if (going <= 0) continue
      const standing = answerFor(row)
      if (isWithheld(standing)) continue
      const price = typeof standing === 'string' ? standing : suggestionFor(row)
      const now = liveOf(row)
      if (price === '' || now.copies <= 0) continue
      if (now.price !== null && Number(price) === Number(now.price)) continue
      out.push({ sku: row.sku, name: row.name, copies: now.copies, price, was: now.price })
    }
    return out
  }, [rows, answerFor, askedFor, suggestionFor, source.kind])

  /* THE LIST AS DRAWN: arrival order, needs-you on top. A row the arrival did not see (a later
     re-partition cannot add one, but a reload race could) goes last rather than vanishing. */
  const drawn = useMemo(() => {
    const order = arrival?.order ?? new Map<string, number>()
    const shown = filterRows(rows, facetShape, facetPicks, facetValueOf, keepRow)
    const place = (row: MergedSku) => order.get(row.sku) ?? Number.MAX_SAFE_INTEGER
    /* A SORT ORDERS WITHIN EACH GROUP, never across them: the rows that need the owner stay on top
       (D277). A row with no market price goes last in both directions; ties keep arrival order. */
    const by = (a: MergedSku, b: MergedSku): number => {
      if (sort.key === 'name') return a.name.localeCompare(b.name) * (sort.dir === 'asc' ? 1 : -1)
      const [ca, cb] = [cents(a.snap.market), cents(b.snap.market)]
      if (ca === null || cb === null) return ca === cb ? 0 : ca === null ? 1 : -1
      return (ca - cb) * (sort.dir === 'asc' ? 1 : -1)
    }
    const sorted = [...shown].sort((a, b) => (sort.key === 'arranged' ? 0 : by(a, b)) || place(a) - place(b))
    const needs: MergedSku[] = []
    const ready: MergedSku[] = []
    const closed = new Map<string, MergedSku[]>()
    for (const row of sorted) {
      const why = groupOf(row)
      if (why !== null) {
        const group = closed.get(why)
        if (group === undefined) closed.set(why, [row])
        else group.push(row)
      } else if (arrival?.needs.has(row.sku)) needs.push(row)
      else ready.push(row)
    }
    const groups: { head: string; rows: MergedSku[] }[] = []
    /* ON THE LIVE TAB THE HEADS SAY WHAT THEY HOLD: the rows with no market price, which the rule
       never lowers and the owner prices by hand, then every other live listing. */
    const live = stamp !== null
    if (needs.length > 0) groups.push({ head: live ? 'No market price' : 'Needs you', rows: needs })
    if (ready.length > 0) {
      groups.push({ head: needs.length > 0 ? (live ? 'With a market price' : 'Ready') : '', rows: ready })
    }
    /* THE SERVER'S SENTENCE, VERBATIM (D59): the client never composes a reason. */
    for (const [why, group] of closed) groups.push({ head: why, rows: group })
    return groups
  }, [arrival, rows, facetShape, facetPicks, keepRow, sort, stamp])

  const order = useMemo(() => drawn.flatMap((group) => group.rows.map((row) => row.sku)), [drawn])

  const move = useCallback(
    (sku: string, by: number) => {
      const at = order.indexOf(sku)
      const next = order[at + by]
      if (next === undefined) return
      const field = inputs.current.get(next)
      field?.focus()
      field?.select()
      field?.scrollIntoView({ block: 'nearest' })
    },
    [order],
  )

  const commit = useCallback(
    (sku: PricingSku, raw: string) => {
      if (!touched.current.has(sku.sku)) return
      let text = raw.trim()
      /* ON THE LIVE TAB A TYPED PRICE IS KEPT TO THE CENT (D221, D267): `17.5` is written, shown
         and sent as `17.50`, so the field shows exactly what the press sends. */
      if (source.kind === 'markdown' && text !== '') {
        text = moneyField(text) ?? text
        const input = inputs.current.get(sku.sku)
        if (input && input.value !== text) input.value = text
      }
      write(sku.sku, sku.bucket, text === '' ? undefined : text)
      touched.current.delete(sku.sku)
    },
    [write, source.kind],
  )

  const snap = useCallback((sku: PricingSku, field: keyof PricingSku['snap']) => {
    const value = sku.snap[field]
    const input = inputs.current.get(sku.sku)
    if (value === null) {
      const says = SNAPS.find((row) => row.field === field)?.says ?? (field === 'now' ? 'asking' : field)
      setNote({ sku: sku.sku, text: `No ${says} price on this row` })
      return
    }
    if (input) {
      input.value = moneyField(value) ?? value
      flash(input)
    }
    touched.current.add(sku.sku)
    setNote(null)
  }, [])

  /** A preset writes `rule`/`basis` and NO override on a run (the send prices the unanswered
   *  rows by it). On the Live tab it writes answers, only on rows nobody answered, with one undo. */
  const applyPreset = useCallback(
    (key: string) => {
      if (table === null) return
      const chosen = PRESETS.find((row) => row.key === key)
      if (chosen === undefined) return
      const missing = rows.filter((row) => row.presets[key] === null)
      if (source.proposes) {
        setBook((current) =>
          current === null ? current : { ...current, policy: { ...current.policy, rule: chosen.rule, basis: chosen.basis } },
        )
        for (const row of rows) {
          const input = inputs.current.get(row.sku)
          if (input && answerFor(row) === undefined && row.bucket !== 'sub_threshold') {
            const next = row.presets[key] ?? ''
            if (input.value !== next) {
              input.value = next
              flash(input)
            }
          }
        }
        setNote(
          missing.length === 0
            ? null
            : { sku: '', text: `${missing.length} of ${rows.length} rows have no price in that column and were left alone.` },
        )
        return
      }
      const moving = rows.filter(
        (row) => source.locked(row.sku) === null && answerFor(row) === undefined && typeof row.presets[key] === 'string',
      )
      if (moving.length === 0) {
        setNote({ sku: '', text: 'No row you have not answered has a price in that column.' })
        return
      }
      const before = new Map(moving.map((row) => [row.sku, book?.skus?.[row.sku]]))
      setBook((current) => {
        if (current === null) return current
        let next = current
        for (const row of moving) next = setAnswer(next, row.sku, row.presets[key] as string, 'price')
        return next
      })
      for (const row of moving) {
        const input = inputs.current.get(row.sku)
        if (!input) continue
        input.value = row.presets[key] as string
        flash(input)
        touched.current.delete(row.sku)
      }
      setTypedHere((held) => new Set([...held, ...moving.map((row) => row.sku)]))
      setNote(null)
      toast({
        kind: 'receipt',
        title: `${moving.length} ${moving.length === 1 ? 'row' : 'rows'} priced, ${chosen.label}`,
        body: missing.length === 0 ? 'Every row you had not answered.' : `${missing.length} have no price in that column.`,
        action: {
          label: 'Undo',
          onPress: () => {
            setBook((current) => {
              if (current === null) return current
              const skus = { ...(current.skus ?? {}) }
              for (const row of moving) {
                const was = before.get(row.sku)
                if (was === undefined) delete skus[row.sku]
                else skus[row.sku] = was
              }
              return { ...current, skus }
            })
            for (const row of moving) {
              const input = inputs.current.get(row.sku)
              if (!input) continue
              input.value = ''
              flash(input)
            }
          },
        },
      })
    },
    [rows, table, answerFor, source, book],
  )

  /** The live rows a cut-off press would move: under the line, and nobody answered them. */
  const cheapRows = useMemo(
    () =>
      rows.filter((row) => {
        if (row.bucket !== 'sub_threshold') return false
        if (source.locked(row.sku) !== null) return false
        const standing = answers[row.sku]
        return !(typeof standing === 'string' && standing.trim() !== '') && !isWithheld(standing)
      }),
    [rows, answers, source],
  )

  /** THE ROWS THE RULE MARKS DOWN, ON SCREEN (the owner's rulings, 2026-09-26). The rule's picks
   *  (`offered`) with the server's own proposal, which already carries the read's dollar cap and
   *  never exists on a row with no market price. A row the owner priced away from its live price
   *  keeps the owner's price. None off a stale read. */
  const ruleRows = useMemo(() => {
    if (stamp === null || readStale) return []
    return rows.filter((row) => {
      if (liveLens(standingOf.get(row.sku)) !== 'offered') return false
      if (source.locked(row.sku) !== null) return false
      const proposed = centsOf(row.rule_price)
      if (proposed === null) return false
      const standing = answers[row.sku]
      if (isWithheld(standing)) return false
      const typed = typeof standing === 'string' && standing.trim() !== '' ? centsOf(standing) : null
      if (typed !== null && typed !== centsOf(askingOf.get(row.sku))) return false
      return typed !== proposed
    })
  }, [stamp, readStale, rows, standingOf, source, answers, askingOf])

  /** Write the rule's price onto those rows, in ONE press and ONE undo — the Live tab's presets'
   *  own shape (D103): nothing moves until a press writes an answer, and a blank box keeps its
   *  live price. The price is the server's, cut to two places, so the field shows what the send
   *  carries. */
  const markDown = useCallback(() => {
    const moving = ruleRows.map((row) => ({ sku: row.sku, price: moneyField(row.rule_price) as string }))
    if (moving.length === 0) return
    const before = new Map(moving.map(({ sku }) => [sku, book?.skus?.[sku]]))
    setBook((current) => {
      if (current === null) return current
      let next = current
      for (const { sku, price } of moving) next = setAnswer(next, sku, price, 'price')
      return next
    })
    for (const { sku, price } of moving) {
      const input = inputs.current.get(sku)
      if (!input) continue
      input.value = price
      flash(input)
      touched.current.delete(sku)
    }
    setTypedHere((held) => new Set([...held, ...moving.map(({ sku }) => sku)]))
    toast({
      kind: 'receipt',
      title: `${moving.length} ${moving.length === 1 ? 'listing' : 'listings'} marked down`,
      body: 'Nothing changes at TCGplayer until you send.',
      action: {
        label: 'Undo',
        onPress: () => {
          setBook((current) => {
            if (current === null) return current
            const skus = { ...(current.skus ?? {}) }
            for (const { sku } of moving) {
              const was = before.get(sku)
              if (was === undefined) delete skus[sku]
              else skus[sku] = was
            }
            return { ...current, skus }
          })
          setTypedHere((held) => {
            const next = new Set(held)
            for (const { sku } of moving) next.delete(sku)
            return next
          })
          for (const { sku } of moving) {
            const input = inputs.current.get(sku)
            if (!input) continue
            const was = before.get(sku)?.value
            input.value = typeof was === 'string' ? was : ''
            flash(input)
          }
        },
      },
    })
  }, [ruleRows, book])

  /** Write the cut-off onto every unanswered live row under it, in ONE press and ONE undo. Live
   *  tab only: a run's cheap half is priced by policy at the send (D9/D98). */
  const applyCut = useCallback(() => {
    const price = cut.trim()
    if (price === '' || cheapRows.length === 0) return
    const moved = cheapRows.map((row) => row.sku)
    const before = new Map(moved.map((sku) => [sku, book?.skus?.[sku]]))
    setBook((current) => {
      if (current === null) return current
      let next = current
      for (const sku of moved) next = setAnswer(next, sku, price, 'price')
      return next
    })
    for (const sku of moved) {
      const input = inputs.current.get(sku)
      if (!input) continue
      input.value = price
      flash(input)
      touched.current.delete(sku)
    }
    setTypedHere((held) => new Set([...held, ...moved]))
    toast({
      kind: 'receipt',
      title: `${moved.length} ${moved.length === 1 ? 'row' : 'rows'} priced at the cut-off`,
      body: 'Every live row under the cut-off that you had not answered.',
      action: {
        label: 'Undo',
        onPress: () => {
          setBook((current) => {
            if (current === null) return current
            const skus = { ...(current.skus ?? {}) }
            for (const sku of moved) {
              const was = before.get(sku)
              if (was === undefined) delete skus[sku]
              else skus[sku] = was
            }
            return { ...current, skus }
          })
          for (const sku of moved) {
            const input = inputs.current.get(sku)
            if (!input) continue
            input.value = ''
            flash(input)
          }
        },
      },
    })
  }, [cut, cheapRows, book])

  /** THE CUSTOM RULE, WRITTEN THE WAY A PRESET IS: `policy.rule` and `policy.basis`, no override.
   *  The untyped fields go empty: a per-SKU figure under a custom rule would be the last join's
   *  price wearing this rule's label (D54). The send prices them. */
  const applyCustom = useCallback(
    (draft: CustomRule) => {
      const bad = badPercent(draft.kind, draft.pct)
      if (bad !== null) {
        setCustomBad(bad)
        return
      }
      setCustomBad(null)
      const rule = customRuleText(draft)
      if (doc?.rule === rule && (doc?.basis ?? 'market') === draft.basis) return
      setBook((current) => (current === null ? current : { ...current, policy: { ...current.policy, rule, basis: draft.basis } }))
      for (const row of rows) {
        if (row.bucket === 'sub_threshold' || answerFor(row) !== undefined) continue
        const input = inputs.current.get(row.sku)
        if (!input || input.value === '') continue
        input.value = ''
        flash(input)
      }
      setNote(null)
    },
    [doc, rows, answerFor],
  )

  /** Reverses one entry, whichever kind it is — shared by `undoLast` (`U`, the toolbar) and
   *  `undoById` (a toast's own Undo, finding #2). */
  const applyReversal = useCallback(
    (top: Undo) => {
      if (top.kind === 'cutoff') {
        setBook((current) =>
          current === null
            ? current
            : { ...current, policy: { ...current.policy, threshold: top.before.threshold, sub_threshold: top.before.sub_threshold } },
        )
        return
      }
      /* UN-12: every op in the batch reverses together, in the SAME setBook call. */
      setBook((current) => {
        if (current === null) return current
        const skus = { ...(current.skus ?? {}) }
        for (const w of top.writes) {
          if (w.before === undefined) delete skus[w.sku]
          else skus[w.sku] = w.before
        }
        return { ...current, skus }
      })
      setTypedHere((held) => {
        /* AN UNDONE ANSWER WAS NOT TYPED THIS VISIT (round 7, R6-2). */
        const next = new Set(held)
        for (const w of top.writes) next.delete(w.sku)
        return next
      })
      for (const w of top.writes) {
        const row = rows.find((one) => one.sku === w.sku)
        const input = inputs.current.get(w.sku)
        if (row !== undefined && input) {
          const before = w.before?.value
          input.value = typeof before === 'string' ? before : suggestionFor(row)
          flash(input)
        }
        touched.current.delete(w.sku)
      }
    },
    [rows, suggestionFor],
  )

  /* THE NEWEST, AND ONLY THE NEWEST (`U` and the toolbar's own Undo): `docs/specs/undo.md`
   * §11.1's own rank rule. */
  const undoLast = useCallback(() => {
    const [top, ...rest] = undo
    if (top === undefined) return
    applyReversal(top)
    setUndo(rest)
  }, [undo, applyReversal])

  /** A SPECIFIC PRESS, BY ID (finding #2): a toast's own Undo calls this with the id it was
   *  given at push time, so it reverses THE CHANGE IT NAMES — never whatever the stack's
   *  front holds by the time the button is actually pressed. A newer press standing on top
   *  is untouched; an id no longer in the stack (already undone, or the depth cap dropped
   *  it) does nothing, silently — the toast itself is long gone by then. */
  const undoById = useCallback(
    (id: number) => {
      const top = undo.find((entry) => entry.id === id)
      if (top === undefined) return
      applyReversal(top)
      setUndo((stack) => stack.filter((entry) => entry.id !== id))
    },
    [undo, applyReversal],
  )
  /* A toast's undo fires later than the closure it was made in; the ref always holds the
   * latest. */
  const undoByIdRef = useRef(undoById)
  undoByIdRef.current = undoById

  /* THE CHEAP ROWS FOLLOW THE CUT-OFF on a run: the field shows what the send will write. */
  useEffect(() => {
    if (!source.proposes) return
    for (const row of rows) {
      if (row.bucket !== 'sub_threshold') continue
      if (touched.current.has(row.sku)) continue
      const standing = answerFor(row)
      if (typeof standing === 'string' || isWithheld(standing)) continue
      const input = inputs.current.get(row.sku)
      if (!input || input.value === cut) continue
      input.value = cut
      flash(input)
    }
  }, [cut, rows, answerFor, source])

  const openHold = useCallback((sku: PricingSku) => {
    holdAnchor.current = holdButtons.current.get(sku.sku) ?? null
    setHoldFor(sku.sku)
  }, [])

  const toggleHold = useCallback(
    (sku: PricingSku) => {
      /* THE ROW'S OWN ANSWER, read the way the row is drawn (`answerFor`), so a hold stored as
       * 'unlisted' on the `unknown` channel releases too, and not only one on `price`. */
      const held = answerFor(sku)
      if (isWithheld(held)) {
        /* A RELEASE PUTS BACK THE ANSWER THE HOLD REPLACED (the owner's ruling, "Bring back
         * $5.16"), on its own channel, so the toast's "next send" is true. A hold with no
         * earlier answer releases to none. */
        const prior = typeof held === 'object' ? held.before : undefined
        const empty = prior === undefined || prior.value === null
        const id = empty
            ? write(sku.sku, sku.bucket, undefined)
            : writeMany([{ sku: sku.sku, bucket: sku.bucket, value: prior.value, channel: prior.channel === 'unknown' ? 'unknown' : 'price', at: prior.at }])
        setHoldFor(null)
        toast({
          kind: 'receipt',
          title: `Released ${sku.name}`,
          /* THE TOAST SAYS WHAT THE NEXT SEND WILL DO. A row left with no answer and no market
           * price is left out of a send until it has a price. */
          body: empty && sku.bucket === 'no_market_data' ? 'It needs a price before it can go out.' : 'It goes out with the next send.',
          ttlMs: 8000,
          action: { label: 'Undo', kbd: 'U', onPress: () => undoByIdRef.current(id) },
        })
        return
      }
      openHold(sku)
    },
    [answerFor, write, writeMany, openHold],
  )

  const closeHold = useCallback(() => {
    const at = holdFor
    setHoldFor(null)
    if (at !== null) inputs.current.get(at)?.focus()
  }, [holdFor])

  const setHold = useCallback(
    (sku: PricingSku, reason: WithholdReason, watch: string, text: string) => {
      const record: WithheldRecord = { withheld: reason }
      if (watch.trim() !== '') record.watch_above = watch.trim()
      if (text.trim() !== '') record.note = text.trim()
      /* THE ANSWER THIS HOLD REPLACES, kept inside it so a release can put it back (the
       * owner's ruling, "Bring back $5.16"). Only a real answer: none, or an earlier hold, is
       * not kept. */
      const prior = book?.skus?.[sku.sku]
      if (prior !== undefined && prior !== null && prior.value !== null && !isWithheld(prior.value)) {
        record.before = { value: prior.value as string | number, channel: prior.channel ?? 'price' }
        /* AND ITS FIRST DATE, so a release keeps it (the owner's ruling, "Keep the first date"). */
        if (prior.at !== undefined) record.before.at = prior.at
      }
      /* ONE ANSWER, ON THE `price` CHANNEL, FOR EVERY ROW (the final Pricing review, HIGH).
       * `book.skus[sku]` holds ONE answer per SKU, so the old second write ('unlisted' on the
       * `unknown` channel) replaced this record and lost the reason, watch and note. A hold
       * cannot ride the `unknown` channel: `decisions.parse` refuses a record under
       * `no_market_data` as "not a price". On the `price` channel it lands in `withheld()`,
       * and `join.prices_for` skips a held SKU before it reads `no_market_data`, so a no-market
       * row is left out exactly as 'unlisted' left it out. `answerFor` reads it back. */
      const id = write(sku.sku, 'listable', record)
      setHoldFor(null)
      toast({
        kind: 'receipt',
        title: `Held ${sku.name}`,
        body: WITHHOLD_LABELS[reason],
        ttlMs: 8000,
        action: { label: 'Undo', kbd: 'U', onPress: () => undoByIdRef.current(id) },
      })
      inputs.current.get(sku.sku)?.focus()
    },
    [write, book],
  )

  /** Read the shape of every row still waiting — one press, chunked, sequential. EACH ROW ASKS
   *  ITS OWN RUN, so the whole worklist can be read and not only a single run (the old per-run
   *  address left the default landing with no trends at all). */
  const loadTrends = useCallback(() => {
    const open = rows.filter((row) => !row.at_cap)
    const walk = (trendWalk.current += 1)
    setTrends(Object.fromEntries(open.map((row) => [row.sku, { kind: 'reading' } as TrendRead])))
    setTrendRun({ total: open.length, done: 0, reading: true })
    const byDoor = new Map<string, string[]>()
    for (const row of open) {
      const door = stamp ?? row.in[row.in.length - 1]?.run ?? run
      if (door === null || door === undefined) continue
      const list = byDoor.get(door)
      if (list === undefined) byDoor.set(door, [row.sku])
      else list.push(row.sku)
    }
    const chunks: { door: string; skus: string[] }[] = []
    for (const [door, skus] of byDoor) {
      for (let at = 0; at < skus.length; at += TREND_CHUNK) chunks.push({ door, skus: skus.slice(at, at + TREND_CHUNK) })
    }
    const ask = (door: string, skus: string[]) => (stamp !== null ? markdownTrends(door, skus) : getPriceTrends(door, skus))
    const read = async () => {
      for (const chunk of chunks) {
        if (trendWalk.current !== walk) return
        try {
          const payload = await ask(chunk.door, chunk.skus)
          if (trendWalk.current !== walk) return
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk.skus) {
              const found = payload.skus[sku]
              next[sku] =
                found !== undefined
                  ? { kind: 'read', ranges: found.ranges }
                  : { kind: 'refused', why: payload.refused[sku] ?? 'No answer for this card.' }
            }
            return next
          })
        } catch (error) {
          if (trendWalk.current !== walk) return
          const why = describeFailure(error).message
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk.skus) next[sku] = { kind: 'refused', why }
            return next
          })
        }
        setTrendRun((current) => (current === null ? current : { ...current, done: current.done + chunk.skus.length }))
      }
      if (trendWalk.current === walk) setTrendRun((current) => (current === null ? current : { ...current, reading: false }))
    }
    void read()
  }, [rows, stamp, run])

  const trendTally = useMemo(() => {
    let read = 0
    let none = 0
    for (const value of Object.values(trends)) {
      if (value.kind !== 'read') continue
      read += 1
      if (value.ranges.length === 0) none += 1
    }
    return { read, none }
  }, [trends])

  /* Which row the pointer is over. A ref: nothing draws it. */
  const hovered = useRef<string | null>(null)
  const focusedSku = useCallback(() => {
    for (const [sku, node] of inputs.current) if (node === document.activeElement) return sku
    return null
  }, [])

  const openProduct = useCallback((sku: PricingSku) => openSheet('product', { sku: sku.sku, name: sku.name }), [])

  const openPhoto = useCallback((sku: PricingSku) => {
    setPhotoFor((current) => (current !== null && current.sku === sku.sku ? null : { sku: sku.sku, at: 0 }))
  }, [])

  /* `T` OPENS THE PRODUCT VIEW for the row under the pointer or the focused one, from anywhere
     that is not a field (UX-075). An open overlay owns the keyboard. */
  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || event.repeat || event.defaultPrevented) return
      if (holdFor !== null || ruleOpen || runsOpen || photoFor !== null) return
      if (document.querySelector('[aria-modal="true"]') !== null) return
      if (isEditableTarget(event.target)) return
      if (event.key.toLowerCase() !== 't') return
      const aim = hovered.current ?? focusedSku()
      const row = aim === null ? undefined : rows.find((one) => one.sku === aim)
      if (row === undefined) return
      event.preventDefault()
      openProduct(row)
    }
    window.addEventListener('keydown', down)
    return () => window.removeEventListener('keydown', down)
  }, [focusedSku, holdFor, ruleOpen, runsOpen, photoFor, rows, openProduct])

  /* FINDING #11 (the Opus review round): `U` used to be a second, hand-rolled copy of the
   * shared hotkey (`kit/undo.ts`'s own comment: "a screen that still binds `U` itself is
   * what `make kit-adoption` fails"). `useUndoHotkey` is the one `U` primitive now — it
   * already yields to a repeat, a modifier and an editable target on its own; the panels
   * this screen owns (`holdFor`/`ruleOpen`/`runsOpen`/`photoFor`, any open dialog) are what
   * only this screen knows about, so they gate the callback it is given. */
  useUndoHotkey(() => {
    if (holdFor !== null || ruleOpen || runsOpen || photoFor !== null) return null
    if (document.querySelector('[aria-modal="true"]') !== null) return null
    return undo.length === 0 ? null : () => undoLast()
  })

  const onKey = useCallback(
    (event: ReactKeyboardEvent<HTMLInputElement>, sku: PricingSku) => {
      const key = event.key
      if (key === 'Enter') {
        event.preventDefault()
        commit(sku, event.currentTarget.value)
        move(sku.sku, event.shiftKey ? -1 : 1)
        return
      }
      if (key === 'Escape') {
        event.preventDefault()
        const standing = answerFor(sku)
        event.currentTarget.value = typeof standing === 'string' ? standing : source.proposes ? suggestionFor(sku) : ''
        touched.current.delete(sku.sku)
        event.currentTarget.blur()
        return
      }
      if (key === 'ArrowDown' || key === 'ArrowUp') {
        event.preventDefault()
        commit(sku, event.currentTarget.value)
        move(sku.sku, key === 'ArrowDown' ? 1 : -1)
        return
      }
      if (key.length !== 1 || event.metaKey || event.ctrlKey || event.altKey) return
      // EVERY LETTER IS A COMMAND, BY CONSTRUCTION: the field's alphabet is closed to `[0-9.]`.
      const lower = key.toLowerCase()
      const found = SNAPS.find((row) => row.key === lower)
      if (found) {
        event.preventDefault()
        snap(sku, found.field)
        return
      }
      if (lower === 'h') {
        event.preventDefault()
        toggleHold(sku)
        return
      }
      if (lower === 'u') {
        event.preventDefault()
        undoLast()
        return
      }
      if (lower === 'p') {
        event.preventDefault()
        if (source.copies) openPhoto(sku)
        return
      }
      if (lower === 't') {
        event.preventDefault()
        openProduct(sku)
        return
      }
      if (lower === 'n' && sku.snap.now !== null) {
        event.preventDefault()
        snap(sku, 'now')
      }
    },
    [answerFor, commit, move, snap, suggestionFor, toggleHold, undoLast, openPhoto, openProduct, source],
  )

  const photoSku = useMemo(() => (photoFor === null ? null : rows.find((row) => row.sku === photoFor.sku) ?? null), [photoFor, rows])

  /* THE MASS-CLEAR (D168): the owner's ask, "a lot of pricing is pre typed but stale and there's
     no way to mass clear". The server says which answers may go; absent disables the control. */
  const [clearOpen, setClearOpen] = useState(false)
  const [clearable, setClearable] = useState<PricingClearable | null>(null)
  /** UN-11 (`docs/specs/undo.md` SS11.3): EVERY kept clear that can still be undone, newest
   *  first, read off the server rather than kept only in a toast's own closure. This is what
   *  still offers "Restore N cleared" after the toast has faded, or after a reload, for each
   *  clear (the owner's standing undo ruling, "Anytime, from a history"). A clear a send has
   *  carried a SKU of (`clear_built_on`) is not offered, the "built on" limit every undo has. */
  const [kept, setKept] = useState<readonly KeptClear[]>([])
  const [allClears, setAllClears] = useState(false)
  const clearableTotal = Object.keys(clearable?.days ?? {}).length
  /** THE SCOPE IS THE WORKLIST AS LOADED, never the filtered rows: a destructive press whose
   *  radius depends on a chip is a press nobody can predict. */
  const worklistSkus = useMemo(() => (table ?? []).map((row) => row.sku), [table])
  const scopeName = useMemo(() => {
    if (stamp !== null) return 'Live listings'
    if (run === null) return null
    const row = detail !== null && detail.run === run ? detail : runs.find((r) => r.run === run)
    return row === undefined ? null : runBoxLabel(row)
  }, [stamp, run, detail, runs])
  const worklistName =
    scopeName ?? (loaded.length === 0 ? 'the cards on this screen' : `${loaded.length} run${loaded.length === 1 ? '' : 's'}`)

  /** Re-read what may still be cleared, and the digest — NOT the answers (StrictMode runs an
   *  updater twice, and adopting them there re-dirtied the screen; see D168's receipt case). */
  const refreshCorpus = useCallback(async () => {
    const answer = await getPricingCorpus()
    setClearable(answer.clearable ?? null)
    setKept(keptOf(answer))
    revision.current = answer.revision
  }, [])

  /** UN-11: put back the newest clear, off the server's own memory of it rather than a
   *  toast's closure. Unlike the toast's own Undo, this answer carries no SKU-keyed values
   *  to walk into the fields, only which SKUs came back — so this reads the corpus fresh and
   *  takes each restored SKU's answer off IT, the same "the response decides which rows come
   *  back" rule `withRestored` already follows for the toast's own path. */
  const doRestoreClear = useCallback(async (clear: KeptClear) => {
    try {
      const back = clear.id === undefined ? await restoreLastClear(revision.current) : await restoreClear(clear.id, revision.current)
      const held = await getPricingCorpus()
      setKept(keptOf(held))
      revision.current = held.revision
      savedBook.current = held.corpus
      setBook(held.corpus)
      setClearable(held.clearable ?? null)
      for (const sku of back.restored) {
        const input = inputs.current.get(sku)
        const was = held.corpus.skus?.[sku]
        if (input === undefined || was === undefined) continue
        input.value = typeof was.value === 'string' ? was.value : String(was.value ?? '')
        flash(input)
        touched.current.delete(sku)
      }
      toast({
        kind: 'ok',
        title: `${back.restored.length} price${back.restored.length === 1 ? '' : 's'} undone`,
        body: restoreSkipBody(back.skipped),
      })
    } catch (err) {
      const trouble = describeFailure(err)
      toast({ kind: 'refusal', tone: failureTone(trouble), title: 'Not undone', body: trouble.message })
    }
  }, [])

  /** A clear landed: drop those answers, clear the fields, re-read, and offer the way back. */
  const onCleared = useCallback(
    (result: PricingClearResult) => {
      const gone = Object.keys(result.cleared)
      const current = savedBook.current
      if (current !== null) {
        const skus = { ...(current.skus ?? {}) }
        for (const sku of gone) delete skus[sku]
        const next = { ...current, skus }
        savedBook.current = next
        setBook(next)
      }
      revision.current = result.revision
      for (const sku of gone) {
        const input = inputs.current.get(sku)
        if (input === undefined) continue
        input.value = ''
        flash(input)
        touched.current.delete(sku)
      }
      void refreshCorpus()
      toast({
        kind: 'receipt',
        title: `${result.count} typed price${result.count === 1 ? '' : 's'} cleared`,
        body:
          result.holds === 0
            ? 'Those rows go back to the rule. Nothing at TCGplayer changed.'
            : `Those rows go back to the rule. ${result.holds} held back on purpose ${result.holds === 1 ? 'was' : 'were'} left alone, and nothing at TCGplayer changed.`,
        action: {
          label: 'Undo',
          onPress: () => {
            void (async () => {
              try {
                const back = await restorePricingAnswers(result.cleared, revision.current, result.clear_id)
                revision.current = back.revision
                const kept = savedBook.current
                if (kept !== null) {
                  const next = withRestored(kept, back.restored, result.cleared)
                  savedBook.current = next
                  setBook(next)
                }
                void refreshCorpus()
                for (const sku of back.restored) {
                  const input = inputs.current.get(sku)
                  const was = result.cleared[sku]
                  if (input === undefined || was === undefined) continue
                  input.value = typeof was.value === 'string' ? was.value : String(was.value ?? '')
                  flash(input)
                }
                toast({
                  kind: 'ok',
                  title: `${back.restored.length} price${back.restored.length === 1 ? '' : 's'} undone`,
                  body: restoreSkipBody(back.skipped),
                })
              } catch (err) {
                toast({ ...refusalToast(err) })
              }
            })()
          },
        },
      })
    },
    [refreshCorpus],
  )

  const activePreset = PRESETS.find((p) => p.rule === doc?.rule && p.basis === doc?.basis) ?? null
  const standingCustom = activePreset === null ? parseCustomRule(doc?.rule, doc?.basis) : null
  const customOn = pressedCustom || standingCustom !== null
  const ruleSegment = customOn ? CUSTOM_KEY : (activePreset?.key ?? '')
  const standingKey = standingCustom === null ? null : `${standingCustom.kind}:${standingCustom.pct}:${standingCustom.basis}`
  useEffect(() => {
    if (standingKey === null || customSeed.current === standingKey) return
    customSeed.current = standingKey
    const [kind, pct, basis] = standingKey.split(':')
    setCustomDraft({ kind: kind as RuleKind, pct: pct as string, basis: basis as RuleBasis })
    setCustomBad(null)
  }, [standingKey])

  const pickRule = useCallback(
    (key: string) => {
      if (key !== CUSTOM_KEY) {
        setPressedCustom(false)
        setCustomBad(null)
        applyPreset(key)
        return
      }
      setPressedCustom(true)
      setNote(null)
    },
    [applyPreset],
  )

  const subCount = subThresholdSkus(rows).length
  const roster = work?.roster ?? []
  const cutFrom: 'run' | 'store' | 'default' = thisRunCut !== undefined ? 'run' : storeCut !== null ? 'store' : 'default'
  const stranded = strandedFlat(doc, cut)

  /* ---------------------------------------------------------------------- the Live tab */

  const [liveSettings, setLiveSettings] = useState(false)
  const [liveBusy, setLiveBusy] = useState(false)
  const [liveFailure, setLiveFailure] = useState<Failure | null>(null)
  const newest = markdowns?.find((one) => one.stamp === stamp) ?? markdowns?.[0] ?? null

  /** READ WHAT IS LIVE AGAIN: fetch the live export, then write a new read with these settings,
   *  and open it. The Mark-down sheet's two presses, as one (D277, Q6). */
  const readLive = useCallback(
    async (ask: LiveAsk, file: File | null) => {
      setLiveBusy(true)
      setLiveFailure(null)
      try {
        const options: Record<string, unknown> = { basis: 'asking', write: true }
        if (ask.days.trim() !== '') options['days'] = Number(ask.days)
        if (ask.match) options['rule'] = 'match'
        else if (ask.percent.trim() !== '') options['percent'] = ask.percent.trim()
        if (!ask.match && ask.cap.trim() !== '') options['cap'] = ask.cap.trim()
        let answer: MarkdownAnswer
        if (file !== null) {
          answer = await markdownListings(await readUpload(file), options)
        } else {
          const fetched = await fetchLiveExport()
          answer = await markdownListings(null, { ...options, fetched: fetched.fetched })
        }
        setLiveSettings(false)
        const list = await getMarkdowns()
        setMarkdowns(list.markdowns)
        if (answer.stamp !== null) window.location.hash = `#/pricing?markdown=${answer.stamp}`
      } catch (err) {
        setLiveFailure(describeFailure(err))
      } finally {
        setLiveBusy(false)
      }
    },
    [],
  )

  const goTab = useCallback((tab: 'send' | 'live') => {
    window.location.hash = tab === 'live' ? '#/pricing?live' : '#/pricing'
  }, [])

  /* ------------------------------------------------------------------------ the chrome */

  const actions = (
    <>
      <IconButton
        icon="eraser"
        label="Clear typed prices"
        onClick={() => setClearOpen(true)}
        disabled={clearableTotal === 0}
      />
      {/* A FIXED SLOT FOR UNDO (UX-135): always drawn, disabled until there is something to take
          back, so the first write moves nothing beside it. `U` works from anywhere (UX-075). */}
      <IconButton icon="undo" label="Undo" kbd="U" onClick={undoLast} disabled={undo.length === 0} />
      <ReloadButton onReload={reload} busy={loading} hotkey={!phone} />
    </>
  )

  const toolbar = (
    <div className="pricing-tools">
      <Segmented<'send' | 'live'>
        className="pricing-tabs"
        label="Which list"
        value={liveTab ? 'live' : 'send'}
        options={[
          { value: 'send', label: 'Unsent' },
          { value: 'live', label: 'Live' },
        ]}
        onChange={goTab}
      />
      {liveTab || roster.length === 0 ? null : (
        <Button
          ref={runsAnchor}
          size="sm"
          icon="layers"
          iconRight="chevronDown"
          aria-expanded={runsOpen}
          aria-haspopup="dialog"
          onClick={() => setRunsOpen((open) => !open)}
        >
          {picked.size === 0 ? 'All' : `${picked.size} ${picked.size === 1 ? 'run' : 'runs'}`}
        </Button>
      )}
      {!liveTab || sheet === null ? null : (
        <Segmented<'all' | 'offered' | 'refused'>
          size="sm"
          value={lens}
          label="Which live listings to show"
          options={[
            /* A STALE READ'S COUNTS ARE NOT OFFERED AS CURRENT (the owner's ruling, 2026-09-26). */
            { value: 'all', label: readStale ? 'All' : `All ${lensCounts.all}` },
            { value: 'offered', label: readStale ? 'Not selling' : `Not selling ${lensCounts.offered}` },
            { value: 'refused', label: readStale ? 'Passed over' : `Passed over ${lensCounts.refused}` },
          ]}
          onChange={setLens}
        />
      )}
      {!liveTab || sheet === null ? null : (
        <Segmented<'both' | 'singles' | 'sealed'>
          size="sm"
          value={kind === '' ? 'both' : kind}
          label="Singles or sealed"
          options={[
            { value: 'both', label: 'Both' },
            { value: 'singles', label: 'Singles' },
            { value: 'sealed', label: 'Sealed' },
          ]}
          onChange={(next) => setKindParam(next === 'both' ? '' : next)}
        />
      )}
      {held.length === 0 && !filterHeld ? null : (
        <Button
          size="sm"
          icon="lock"
          variant={filterHeld ? 'primary' : 'default'}
          aria-pressed={filterHeld}
          onClick={() => setFilterHeld((on) => !on)}
        >
          {`Held ${held.length}`}
        </Button>
      )}
      {table === null || table.length === 0 ? null : (
        <Button size="sm" icon="trendUp" className="pricing-trends-press" onClick={loadTrends} busy={trendRun?.reading === true} disabled={trendRun?.reading === true}>
          Trends
        </Button>
      )}
    </div>
  )

  const trendSays =
    trendRun === null
      ? ''
      : trendRun.reading
        ? `Reading trends, ${trendRun.done} of ${trendRun.total}…`
        : `Trends for ${trendTally.read} ${trendTally.read === 1 ? 'card' : 'cards'}.${trendTally.none === 0 ? '' : ` ${trendTally.none} ${trendTally.none === 1 ? 'has' : 'have'} no sales.`}`

  /* THE RULE LINE (D277, Q5): what the rule does and the cut-off, once, with "Change". */
  const readAgain = () =>
    void readLive(
      {
        days: String(newest?.asked?.['days'] ?? '7'),
        percent: String(newest?.asked?.['percent'] ?? '10'),
        match: newest?.asked?.['rule'] === 'match',
        cap: typeof newest?.asked?.['cap'] === 'string' ? (newest.asked['cap'] as string) : '',
      },
      null,
    )
  const ruleLine = liveTab ? (
    <p className="pricing-rule-line">
      <span>
        {newest === null ? (
          'Nothing read from TCGplayer yet.'
        ) : markdownCap(newest.asked) === null ? (
          `${markdownWords(newest.asked)}.`
        ) : (
          /* THE CAP IS A DOLLAR FIGURE, SO IT IS DRAWN IN THE MONEY FACE (D221). */
          <>
            {markdownWords(newest.asked)}, at most <Money value={markdownCap(newest.asked)} /> off a card.
          </>
        )}{' '}
        {newest?.at ? <span className="pricing-rule-when">Read {clockTime(newest.at)}, {absoluteDate(newest.at)}.</span> : null}
      </span>
      {ruleRows.length === 0 ? null : (
        <Button size="sm" icon="trendDown" onClick={markDown}>
          {`Mark down ${ruleRows.length}`}
        </Button>
      )}
      <Button size="sm" variant="quiet" onClick={() => setLiveSettings(true)}>
        Change
      </Button>
      {readStale ? null : (
        <Button size="sm" icon="refresh" busy={liveBusy} disabled={liveBusy} onClick={readAgain}>
          Read again
        </Button>
      )}
      <span className="bn-sr" role="status">
        {liveBusy ? 'Reading what is live at TCGplayer…' : ''}
      </span>
      <span className="pricing-trend-says" aria-live="polite">
        {trendSays}
      </span>
    </p>
  ) : (
    <p className="pricing-rule-line">
      <span>
        {/* F5 verbiage cut: "Nothing lists under the cut-off" restated the number that
            follows it — the dollar figure plus "floor" says the same thing (the data rule
            keeps the percentage and the cut-off, only the words around them shrink). */}
        {ruleWords(doc)}, <Money value={Number(cut)} /> floor.
      </span>
      <Button size="sm" variant="quiet" onClick={() => setRuleOpen(true)}>
        Change
      </Button>
      <span className="pricing-trend-says" aria-live="polite">
        {trendSays}
      </span>
    </p>
  )

  /* THE SLIM BAR (D277, Q4): where pricing stands and the one press. Its height is published so
     the list clears it where it is pinned to the bottom, on a phone. */
  const barObserver = useRef<ResizeObserver | null>(null)
  const measureBar = useCallback((node: HTMLElement | null) => {
    barObserver.current?.disconnect()
    barObserver.current = null
    if (node === null) {
      document.body.style.removeProperty('--pricing-bar-h')
      return
    }
    const host = node.closest<HTMLElement>('.pricing')
    if (host === null) return
    /* ALSO ON `document.body` (finding #9, the delta review round): the toast stack
       (`kit/toast.tsx`'s `Toaster`) mounts as a sibling of `.pricing`, not a descendant of it,
       so a variable set only on `host` never reaches it — a CSS custom property inherits
       down the tree, never sideways. Setting it on `body` too is what lets
       `body:has(.pricing-bar) .bn-toasts` in Pricing.css read the bar's real height. */
    const publish = () => {
      host.style.setProperty('--pricing-bar-h', `${node.offsetHeight}px`)
      document.body.style.setProperty('--pricing-bar-h', `${node.offsetHeight}px`)
    }
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(node)
    barObserver.current = observer
  }, [])

  /* F5 verbiage cut: the reviewer's own "Status" word would drop the multi-way split this
     line is the only place to see broken out, which the data rule refuses (numbers stay,
     only the words around them shrink). */
  const summary = [
    `${progress.outCopies} ready`,
    needsPrice > 0 ? `${needsPrice} need a price` : null,
    progress.byHand > 0 ? `${progress.byHand} typed` : null,
    progress.held > 0 ? `${progress.held} held` : null,
    progress.closed > 0 ? `${progress.closed} sent` : null,
  ].filter((part): part is string => part !== null)

  const bar =
    !liveTab && loaded.length > 0 ? (
      <aside className="pricing-bar" ref={measureBar} role="region" aria-label="Send to TCGplayer">
        <p className="pricing-bar-says">{summary.join(', ')}</p>
        <SendCard
          runs={loaded}
          copies={progress.outCopies}
          priceChanges={priceChanges}
          liveMoves={liveMoves}
          settled={!dirty && !saving}
          saveFailed={saveFailed}
          quantities={quantitiesAsked}
          onSent={afterSend}
        />
      </aside>
    ) : liveTab && stamp !== null && readStale ? (
      <aside className="pricing-bar" ref={measureBar} role="region" aria-label="Send these prices">
        <p className="pricing-bar-says">
          {sheet?.at ? `This read is from ${absoluteDate(sheet.at)}, more than a day ago. ` : 'This read has no date. '}
          Read again to see what would change.
        </p>
        <div className="send-card">
          <div className="send-act">
            <Button variant="primary" size="lg" icon="refresh" className="send-press" busy={liveBusy} disabled={liveBusy} onClick={readAgain}>
              Read again
            </Button>
          </div>
        </div>
      </aside>
    ) : liveTab && stamp !== null ? (
      <aside className="pricing-bar" ref={measureBar} role="region" aria-label="Send these prices">
        <p className="pricing-bar-says">
          {pushable.length === 0 ? 'Type a price on a listing to change it.' : `${pushable.length} new ${pushable.length === 1 ? 'price' : 'prices'} ready`}
        </p>
        {/* A PRICE THE BUTTON DID NOT NAME IS NEVER SENT (D273): the earlier prices that ride are
            named here, card by card, before the press. */}
        {earlierRides.length === 0 ? null : (
          <details className="pricing-earlier">
            <summary>
              {`${earlierRides.length} of them ${earlierRides.length === 1 ? 'is a price' : 'are prices'} you typed before, above the live price`}
            </summary>
            <ul>
              {earlierRides.map((row) => (
                <li key={row.sku}>
                  {row.name}: <Money value={Number(row.was)} /> to <Money value={Number(row.price)} />
                </li>
              ))}
            </ul>
          </details>
        )}
        <div className="send-card">
          <div className="send-act">
            <Button
              variant="primary"
              size="lg"
              icon="send"
              className="pricing-emit send-press"
              busy={push === 'sending'}
              disabled={push !== 'idle' || pushable.length === 0}
              onClick={() => {
                setLinkHeld(wroteUpload)
                setPush('sending')
              }}
            >
              {`Send ${pushable.length} ${pushable.length === 1 ? 'price' : 'prices'} to TCGplayer`}
            </Button>
            <span className="bn-sr" role="status">
              {push === 'sending' ? 'Checking TCGplayer, then sending…' : push === 'writing' ? 'Writing the file…' : ''}
            </span>
            {/* THE PRESS KEEPS ITS WORDS WHILE IT RUNS (D118, b-runs round 9): the spinner says it
                is busy, and the status line says what it is doing. */}
            <Button
              variant="quiet"
              icon="download"
              busy={push === 'writing'}
              disabled={push !== 'idle' || pushable.length === 0}
              onClick={() => {
                setLinkHeld(wroteUpload)
                setPush('writing')
              }}
            >
              <span className="send-long">Download the file instead</span>
              <span className="send-short">Download file</span>
            </Button>
            {!wroteUpload || (push !== 'idle' && !linkHeld) ? null : (
              <a className="bn-btn" href={markdownFileUrl(stamp, 'import.csv')} download="import.csv">
                <Icon name="download" size={16} />
                import.csv
              </a>
            )}
          </div>
          {applied === null || applied.ok ? null : (
            <Notice
              tone="warn"
              title="These prices could not be written, so nothing was sent."
              detail={applied.console.trim().split('\n').slice(-1)[0]}
              compact
            />
          )}
          {shipTrouble === null ? null : (
            <FailureNotice failure={shipTrouble} title={shipTroubleTitle(shipTrouble.code)} onRetry={() => setPush('sending')} busy={push !== 'idle'} />
          )}
        </div>
      </aside>
    ) : null

  /* THE STATUS SLOT: what a press or a read answered, in one place (D118: it never moves rows). */
  const status = (
    <>
      {failure === null || table === null ? null : (
        <Notice tone={failureTone(failure)} title={failure.message} code={failure.code} compact>
          {/* A CONFLICT HAS SOMEWHERE TO GO: the file moved under this screen, and re-reading
              costs what is unsaved, so the press says so. */}
          {failure.code !== 'corpus_moved' ? null : (
            <Button size="sm" variant="quiet" icon="refresh" onClick={reload}>
              Read the file again, losing what is unsaved here
            </Button>
          )}
        </Notice>
      )}
      {(work?.skipped ?? []).length === 0 ? null : (
        <Notice tone="warn" compact title={`${(work?.skipped ?? []).length} run(s) could not be read, and are left out of this list.`} />
      )}
      {queued === 0 ? null : (
        <Notice tone="warn" compact title={`${queued} ${queued === 1 ? 'card waits' : 'cards wait'} in Review, and a send now leaves them out.`} />
      )}
      {liveFailure === null ? null : (
        <Retry compact title="Banchi could not read what is live." code={liveFailure.code} detail={liveFailure.message} busy={liveBusy} onRetry={() => setLiveSettings(true)} />
      )}
    </>
  )
  /* THE STATUS SLOT IS DRAWN ONLY WHEN IT HOLDS SOMETHING. Its answers here are states of a load
     (a run that could not be read, cards waiting in Review) or a failed save, never the answer to
     a press on a row: the trend sentence has its own reserved place on the rule line, and a
     preset's note is said in the sheet that was pressed. So an empty slot would only be a band of
     nothing above the list. */
  const hasStatus =
    (failure !== null && table !== null) || (work?.skipped ?? []).length > 0 || queued > 0 || liveFailure !== null

  /* ------------------------------------------------------------------------ the empty states */

  const empty: ReactNode =
    loading || table !== null
      ? null
      : failure !== null ? (
          /* THE SERVER'S OWN SENTENCE NAMES THE CAUSE (UX-126), and the retry looks like every
             other retry. No claim about the runs is drawn under it. */
          <Retry title={failure.message} code={failure.code} detail={failure.message} busy={loading} onRetry={reload} />
        ) : liveTab ? (
          <EmptyState
            icon="tag"
            title="Empty"
            actions={
              <Button variant="primary" icon="refresh" busy={liveBusy} disabled={liveBusy} onClick={() => setLiveSettings(true)}>
                Refresh
              </Button>
            }
          />
        ) : roster.length === 0 ? (
          <EmptyState
            icon="tag"
            title="Nothing to price yet"
            body="Price your live listings on the Live tab, or read a box on Review."
            actions={
              <>
                <Button variant="primary" icon="tag" onClick={() => goTab('live')}>
                  Price my live listings
                </Button>
                <Button icon="play" onClick={() => (window.location.hash = '#/review')}>
                  Go to Review
                </Button>
              </>
            }
          />
        ) : picked.size > 0 ? (
          <EmptyState
            icon="filter"
            title="Nothing to price in those runs"
            body="Every card there already has an answer."
            actions={
              <Button variant="primary" icon="x" onClick={clearPicked}>
                Show everything unsent
              </Button>
            }
          />
        ) : (
          <EmptyState icon="check" title="Everything is sent" body="Every copy is at TCGplayer, held, or has left its box." />
        )

  const showList = table !== null && (table.length > 0 || liveTab)

  /* THE OVERLAYS SIT BESIDE THE PAGE, NOT IN IT: `Page` draws `empty` in place of its children,
     and the empty states have presses that open these sheets. */
  return (
    <>
      <Page
      className="pricing"
      icon="tag"
      actions={actions}
      toolbar={toolbar}
      toolbarLabel="Which rows"
      status={hasStatus ? status : undefined}
      loading={loading && table === null}
      empty={showList ? undefined : empty}
    >
      <div className="pricing-body" data-live={liveTab ? 'true' : undefined}>
        {bar}
        {ruleLine}
        {/* UN-11: outlives the toast, and a reload. Gone once a send has carried a cleared
            SKU (`clear_built_on`) — the next read finds no `last_clear`. */}
        {kept.length === 0 ? null : (
          <Notice tone="info" className="pricing-restore-clear">
            {/* ONE LINE PER KEPT CLEAR, newest first, each with its own Restore. Past three,
                the rest fold behind "and N more". */}
            {(allClears ? kept : kept.slice(0, 3)).map((clear) => (
              <span key={clear.id ?? clear.at} className="pricing-restore-clear-row">
                <Button size="sm" variant="quiet" icon="undo" onClick={() => void doRestoreClear(clear)} words="word-only-control">
                  Restore {clear.count} cleared, {clockTime(clear.at * 1000)}
                </Button>
              </span>
            ))}
            {!allClears && kept.length > 3 ? (
              <Button size="sm" variant="quiet" onClick={() => setAllClears(true)} words="word-only-control">
                and {kept.length - 3} more
              </Button>
            ) : null}
          </Notice>
        )}
        {liveTab ? null : <UnreachableLine at={work?.unreachable ?? null} />}

        {table !== null && table.length === 0 && liveTab ? (
          <EmptyState icon="tag" title="Nothing live in that read" body="Every row TCGplayer returned was sold out." />
        ) : (
          <>
          {rows.length === 0 ? null : (
            <FilterBar<PricingSortKey>
              className="pricing-filterbar"
              facets={facets}
              value={facetPicks}
              onChange={setFacetPicks}
              count={{ shown: drawn.reduce((sum, group) => sum + group.rows.length, 0), total: rows.length, noun: { one: 'item', many: 'items' } }}
              search={{ query, onChange: setQuery, placeholder: 'Name, set, number or SKU', label: 'Search this list' }}
              sort={{ options: SORT_OPTIONS, value: sort, onChange: setSort, defaultValue: SORT_AT_REST }}
            />
          )}
          {filtering ? <p className="pricing-filter-note">Filters hide rows only. Send covers all.</p> : null}
          {filtering && drawn.length === 0 ? (
            <EmptyState icon="search" title="Nothing matches" body="Loosen a filter." />
          ) : null}
          <div className="pricing-list" data-copies={source.copies ? 'some' : 'none'}>
            <div className="pricing-caption" aria-hidden="true">
              {source.copies ? <span /> : null}
              {/* "ITEM", NOT "CARD" (the owner's add-on, 2026-09-26): the rows include sealed
                  product too, which is not a card. */}
              <span>Item</span>
              <span className="pricing-col-market">Market</span>
              <span className="pricing-col-low">Lowest</span>
              <span className="pricing-col-trend">Trend</span>
              {source.copies ? <span className="pricing-col-qty">Qty</span> : null}
              <span className="pricing-col-price">{liveTab ? 'New price' : 'Price'}</span>
              <span />
            </div>
            {drawn.map((group) => (
              <section className="pricing-group" key={group.head || 'ready'} aria-label={group.head || 'Ready'}>
                {group.head === '' ? null : (
                  <h2 className="pricing-group-head">
                    <span className="pricing-group-why">{group.head}</span>
                    <span className="pricing-group-count">{group.rows.length}</span>
                  </h2>
                )}
                {group.rows.map((sku, index) => (
                  <PricingRow
                    key={sku.sku}
                    sku={sku}
                    index={index}
                    source={source}
                    standing={answerFor(sku)}
                    flag={liveFlag(flagOf(sku, answerFor(sku), source.locked(sku.sku) !== null, cut), liveTab)}
                    suggestion={suggestionFor(sku)}
                    asking={liveTab ? (askingOf.get(sku.sku) ?? null) : undefined}
                    note={note !== null && note.sku === sku.sku ? note.text : null}
                    readAge={ageWords(source.readAtOf(sku))}
                    trend={trends[sku.sku]}
                    asked={sendQty[sku.sku] ?? ''}
                    onAsked={(text) => setAsked(sku.sku, text)}
                    holding={holdFor === sku.sku}
                    registerInput={(node) => {
                      if (node) inputs.current.set(sku.sku, node)
                      else inputs.current.delete(sku.sku)
                    }}
                    registerHold={(node) => {
                      if (node) holdButtons.current.set(sku.sku, node)
                      else holdButtons.current.delete(sku.sku)
                    }}
                    onHover={(on) => {
                      if (on) hovered.current = sku.sku
                      else if (hovered.current === sku.sku) hovered.current = null
                    }}
                    onPhoto={() => openPhoto(sku)}
                    onHold={() => toggleHold(sku)}
                    onKey={(event) => onKey(event, sku)}
                    onCommit={(value) => commit(sku, value)}
                    onFirstKey={() => {
                      const firstKey = !touched.current.has(sku.sku)
                      touched.current.add(sku.sku)
                      return firstKey && typeof answerFor(sku) !== 'string'
                    }}
                  />
                ))}
              </section>
            ))}
          </div>
          </>
        )}
      </div>
      </Page>

      <Popover open={runsOpen} onClose={() => setRunsOpen(false)} anchor={runsAnchor} label="Which runs to price" className="pricing-runs-pop">
        <PickRuns runs={roster} picked={picked} onToggle={toggleRun} onClear={clearPicked} />
      </Popover>

      {holdFor === null
        ? null
        : (() => {
            const sku = rows.find((one) => one.sku === holdFor)
            if (sku === undefined) return null
            const panel = <HoldPanel sku={sku} onSet={setHold} onCancel={closeHold} />
            return phone ? (
              <Sheet open onClose={closeHold} title={`Hold ${sku.name}`} icon="lock">
                {panel}
              </Sheet>
            ) : (
              <Popover open onClose={closeHold} anchor={holdAnchor} label={`Hold ${sku.name}`} className="pricing-holdpop">
                {panel}
              </Popover>
            )
          })()}

      <RuleSheet
        open={ruleOpen}
        onClose={() => setRuleOpen(false)}
        ruleSegment={ruleSegment}
        onRule={pickRule}
        customOn={customOn}
        customDraft={customDraft}
        customBad={customBad}
        onCustomDraft={(next, apply) => {
          setCustomDraft(next)
          if (apply && badPercent(next.kind, next.pct) === null) applyCustom(next)
          else setCustomBad(null)
        }}
        onCustomCommit={applyCustom}
        note={note !== null && note.sku === '' ? note.text : null}
        cut={cut}
        from={cutFrom}
        under={subCount}
        above={rows.length - subCount}
        stranded={stranded}
        runName={run === null ? null : (scopeName ?? run)}
        onCut={cutFrom === 'run' ? setRunCut : setCut}
        onRunCut={setRunCut}
      />

      <LiveSheet
        open={liveSettings}
        onClose={() => setLiveSettings(false)}
        asked={newest?.asked}
        busy={liveBusy}
        failure={liveFailure}
        cheap={cheapRows.length}
        cut={cut}
        note={note !== null && note.sku === '' ? note.text : null}
        onApplyCut={stamp === null ? null : applyCut}
        onPreset={stamp === null ? null : applyPreset}
        onRead={(ask, file) => void readLive(ask, file)}
      />

      <PhotoSheet
        sku={photoSku}
        at={photoFor?.at ?? 0}
        onNext={() => setPhotoFor((current) => (current === null ? current : { sku: current.sku, at: current.at + 1 }))}
        onClose={() => setPhotoFor(null)}
      />

      <ClearPrices
        open={clearOpen}
        onClose={() => setClearOpen(false)}
        clearable={clearable}
        worklist={worklistSkus}
        worklistName={worklistName}
        revision={revision.current || undefined}
        unsaved={dirty || saving}
        onCleared={onCleared}
      />
    </>
  )
}

/* ============================================================================== one row */

/** What the line under a price says, and only where it is NOT the default (UX-084): a held
 *  reason, a missing price, a live listing's move. A typed price is the field's own check. */
function fieldState(
  sku: MergedSku,
  standing: unknown,
  asking: string | null | undefined,
): { text: ReactNode; tone: 'quiet' | 'ok' | 'warn'; title?: string } | null {
  if (isWithheld(standing)) {
    // The human label is drawn; the machine string it stands for travels in the title (D49).
    const reason = heldReason(standing)
    const label = (HOLD_SHORT as Record<string, string>)[reason] ?? ''
    return label === '' ? null : { text: label, tone: 'quiet', title: `withheld: ${reason}` }
  }
  if (asking !== undefined && asking !== null && typeof standing === 'string') {
    const now = Number(standing)
    const was = Number(asking)
    if (!Number.isNaN(now) && !Number.isNaN(was)) {
      if (now > was) return { text: 'Above the live price', tone: 'warn' }
      if (now === was) return { text: 'Unchanged', tone: 'quiet' }
      return {
        text: (
          <>
            Down from <Money value={was} />
          </>
        ),
        tone: 'ok',
      }
    }
  }
  /* A TYPED PRICE ON A ROW WITH NO MARKET PRICE IS WHAT THE SEND LISTS AT (the owner's ruling), so
     the row says only that there is no market to compare it with. */
  if (sku.bucket === 'no_market_data') {
    return typeof standing === 'string' ? { text: 'No market price', tone: 'quiet' } : { text: 'Needs a price', tone: 'warn' }
  }
  return null
}

function PricingRow({
  sku,
  index,
  source,
  standing,
  flag,
  suggestion,
  asking,
  note,
  readAge,
  trend,
  asked,
  onAsked,
  holding,
  registerInput,
  registerHold,
  onHover,
  onPhoto,
  onHold,
  onKey,
  onCommit,
  onFirstKey,
}: {
  sku: MergedSku
  index: number
  source: PricingSource
  standing: unknown
  flag: Flag | null
  suggestion: string
  asking: string | null | undefined
  note: string | null
  readAge: string | null
  trend: TrendRead | undefined
  asked: string
  onAsked: (text: string) => void
  holding: boolean
  registerInput: (node: HTMLInputElement | null) => void
  registerHold: (node: HTMLButtonElement | null) => void
  onHover: (on: boolean) => void
  onPhoto: () => void
  onHold: () => void
  onKey: (event: ReactKeyboardEvent<HTMLInputElement>) => void
  onCommit: (value: string) => void
  onFirstKey: () => boolean
}) {
  const withheld = isWithheld(standing)
  const lockedWhy = source.locked(sku.sku)
  const why = withheld && standing !== 'unlisted' && standing.note ? standing.note : null
  const first = sku.positions[0] ?? null
  const state = fieldState(sku, standing, asking)
  /* THE QTY FIELD SHOWS ONLY WHERE IT CAN SAY SOMETHING (UX-084, TXT-08): more than one copy, or a
     figure already typed. A single copy goes, or is held; there is no quantity to choose. */
  const showQty = source.copies && !sku.at_cap && (sku.copies > 1 || asked !== '')
  /* ONE SENTENCE FOR "HOW MANY", NEVER TWO NUMBERS THAT DISAGREE (the owner's review,
     2026-09-26): the runs' own claim (`claimed_add`) never appears beside the copy count —
     it rode only the title, below — because "11 copies" next to "1 of 13 can go" read as a
     contradiction when the two are really different questions (what is on hand, and what a
     cap still lets go out). */
  const copiesLine =
    [sku.copies > 1 ? `${sku.copies} copies` : null, sku.over_cap ? `${sku.add_to_quantity} sendable` : null]
      .filter((part): part is string => part !== null)
      .join(', ') || null
  return (
    <div
      className="pricing-row"
      style={{ '--i': String(Math.min(index, 14)) } as CSSProperties}
      onPointerEnter={() => onHover(true)}
      onPointerLeave={() => onHover(false)}
      data-answer={withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'}
      data-cap={sku.at_cap ? 'full' : 'room'}
      data-flag={flag?.kind}
      data-hold={holding ? 'open' : undefined}
    >
      {!source.copies ? null : (
        <PricingThumb at={first} name={sku.name} onOpen={onPhoto} imageUrl={sku.image_url} />
      )}

      <div className="pricing-id">
        <span className="pricing-name-line">
          <ProductLink sku={sku.sku} name={sku.name} className="pricing-name">
            {displayName(sku.name, sku.row['Number'] ?? '')}
          </ProductLink>
        </span>
        {/* A REASON ONLY WHERE IT TELLS THE OWNER SOMETHING THE ROW DOES NOT ALREADY SHOW (the
            owner's review, 2026-09-26, and the add-on that followed it). "Worth $5 or more"
            repeats the Market figure two columns over. "No market price" repeats the Market
            column's own "—". Neither draws here — the row's place in "Needs you" already says
            it matters, and the empty Market cell already says why. A typed price adrift from
            market is the one real comparison nothing else on the row states, so it is the one
            case left, in plain words and never a coloured pill: colour marks a problem, never
            "this is worth money" or "this has no listing".
            ITS OWN LINE, NEVER INLINE AFTER THE NAME (the owner's review, 2026-09-26: "i
            dislike not having uniform centering" — inline after a name of variable length put
            the chip at a different x on every row). Every row's flag, when it has one, starts
            at the same x: the id column's own left edge. */}
        {flag === null || flag.kind !== 'drift' ? null : (
          <span className="pricing-flag" data-tone={flag.tone}>
            {flag.text}
          </span>
        )}
        <span className="pricing-meta">
          {/* "NEAR MINT" STAYS ON EVERY ROW (the owner's ruling, D137). */}
          <span className="pricing-cond">{sku.condition}</span>
          <span>{sku.set_name}</span>
          {/* THE NUMBER ALWAYS DRAWS HERE, NEVER IN THE NAME (the owner's review, 2026-09-26:
              "Garganacl - 084/132" carried its number in the name while every other row carried
              it here — one fact, stated in two different places depending on the name). The
              name strips its own trailing copy of the number instead (`displayName`), so this
              is the one place the number reads, on every row alike. */}
          {sku.row['Number'] ? <span className="pricing-number">{sku.row['Number']}</span> : null}
          {sku.row['Rarity'] ? <span className="pricing-rarity">{sku.row['Rarity']}</span> : null}
        </span>
        {/* HOW MANY, IN ONE FACT (the owner's review, 2026-09-26): the single BOX/SECTION/CARD
            location is gone from this row — pricing is over every copy at once, and the one
            location for one copy answered a question nobody here is asking. The photograph's own
            sheet (PhotoSheet) still opens onto every copy's place, one at a time, for whoever
            wants it. "N copies" and "M can go" are stated once each, never against a third,
            unshown "claimed" figure that made an 11-copy row read "1 of 13 can go". */}
        <span className="pricing-meta pricing-where">
          {!source.copies || copiesLine === null ? null : (
            <span
              className="pricing-copies"
              /* F5 verbiage cut (row 97): the visible span below already says "sendable" —
                 this tooltip said "can go" for the same fact and would read as a second word
                 for one idea. */
              title={sku.over_cap ? `The runs claim ${sku.claimed_add}. ${sku.add_to_quantity} sendable.` : undefined}
            >
              {copiesLine}
            </span>
          )}
          {sku.listing === null || (sku.listing.live ?? 0) === 0 ? null : (
            <LiveCount live={sku.listing.live} soldHere={sku.listing.sold_here} age={readAge} />
          )}
          {why === null ? null : <span className="pricing-why">“{why}”</span>}
        </span>
      </div>

      <span className="pricing-ref pricing-col-market" data-empty={sku.snap.market === null ? 'true' : undefined}>
        <span className="pricing-ref-label">Market </span>
        {/* The exact string `m` writes into the field; `Money` draws it to the same two places. */}
        {sku.snap.market === null ? '—' : <Money value={Number(sku.snap.market)} />}
      </span>
      <span className="pricing-ref pricing-col-low" data-empty={sku.snap.low === null ? 'true' : undefined}>
        <span className="pricing-ref-label">Lowest </span>
        {sku.snap.low === null ? '—' : <Money value={Number(sku.snap.low)} />}
      </span>
      <span className="pricing-col-trend">
        <TrendCell read={trend} />
      </span>

      {!source.copies ? null : (
        <span className="pricing-qty pricing-col-qty" data-asked={asked === '' ? undefined : 'true'}>
          {!showQty ? null : (
            <input
              className="bn-input pricing-qty-input"
              type="text"
              inputMode="numeric"
              placeholder={String(sku.add_to_quantity)}
              aria-label={`How many of the ${sku.copies} copies of ${sku.name} go in this file`}
              title={`Blank sends ${sku.add_to_quantity}, every copy that can go. Type fewer to send fewer, or 0 for none. It clears once the file is written.`}
              value={asked}
              onChange={(event) => {
                const text = event.currentTarget.value
                if (/^\d{0,3}$/.test(text)) onAsked(text)
              }}
              onBlur={(event) => {
                const value = Number.parseInt(event.currentTarget.value, 10)
                if (!Number.isFinite(value)) return
                const kept = Math.min(value, sku.add_to_quantity)
                if (String(kept) !== event.currentTarget.value) onAsked(String(kept))
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') event.currentTarget.blur()
                if (event.key === 'Escape') {
                  onAsked('')
                  event.currentTarget.blur()
                }
              }}
            />
          )}
        </span>
      )}

      <div
        className="pricing-price pricing-col-price"
        data-answer={lockedWhy !== null ? 'locked' : withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'}
      >
        {lockedWhy !== null ? (
          <span className="pricing-locked" title={lockedWhy}>
            <Icon name="lock" size={13} />
            {lockedWhy}
          </span>
        ) : withheld ? (
          <span className="pricing-held">
            <Icon name="lock" size={13} />
            Held
          </span>
        ) : (
          <label className="pricing-field">
            <span className="pricing-currency" aria-hidden="true">
              $
            </span>
            <input
              className="pricing-input"
              type="text"
              inputMode="decimal"
              /* THE GHOST IS WHAT YOU ARE ASKING NOW, on the Live tab: a placeholder, so the first
                 digit replaces it and nothing is written by looking at it. A run opens FILLED with
                 the rule's answer, which is a value (D109). */
              placeholder={
                sku.bucket === 'no_market_data'
                  ? ''
                  : source.proposes
                    ? undefined
                    : (moneyField(sku.snap.now) ?? moneyField(suggestion) ?? undefined)
              }
              aria-label={`Price for ${sku.name}`}
              defaultValue={
                typeof standing === 'string'
                  ? source.kind === 'markdown'
                    ? (moneyField(standing) ?? standing)
                    : standing
                  : source.proposes
                    ? suggestion
                    : ''
              }
              ref={registerInput}
              onFocus={(event) => event.currentTarget.select()}
              onBeforeInput={(event) => {
                const native = event.nativeEvent as InputEvent
                const insert = native.data ?? ''
                if (insert === '') return
                const field = event.currentTarget
                // THE PREFILL CLEARS ON THE FIRST CHARACTER, one shot per field.
                if (onFirstKey()) field.value = ''
                const next = field.value.slice(0, field.selectionStart ?? 0) + insert + field.value.slice(field.selectionEnd ?? 0)
                if (!PRICE.test(next)) event.preventDefault()
              }}
              onKeyDown={onKey}
              onBlur={(event) => onCommit(event.currentTarget.value)}
            />
            <Icon name="check" size={13} className="pricing-price-check" aria-label="Your price" />
          </label>
        )}
        {note !== null ? (
          <span className="pricing-state pricing-state-warn pricing-refusal">{note}</span>
        ) : state === null ? null : (
          <span className={`pricing-state pricing-state-${state.tone}`} title={state.title}>
            {state.text}
          </span>
        )}
      </div>

      <IconButton
        ref={registerHold}
        icon={withheld ? 'unlock' : 'lock'}
        label={withheld ? 'Release' : 'Hold back'}
        name={withheld ? `Release ${sku.name}` : `Hold back ${sku.name}`}
        kbd="H"
        pressed={withheld}
        className="pricing-hold"
        onClick={onHold}
      />
    </div>
  )
}

/* ======================================================================= the sheets */

/* THE BIG FIGURE, TYPED INTO DIRECTLY (D98): the `$` is drawn beside it, the alphabet is closed
   to money, Enter and blur commit, Escape puts back what stood. It holds its own draft and
   publishes nothing until a commit, so a half-typed figure never re-partitions the list. */
function BigMoney({ value, onCommit, label }: { value: string; onCommit: (next: string) => void; label: string }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => {
    setDraft(value)
  }, [value])
  /* FINDING #6 (the Opus review round): Enter used to commit, then blur the field, whose own
   * `onBlur` committed AGAIN — one keystroke, two `onCommit` calls (two undo entries, two
   * toasts). `justCommitted` is set the instant Enter or Escape has already resolved the
   * field's own value; `onBlur` reads it once and clears it, so it never repeats a commit —
   * or a REVERT — that already landed.
   *
   * THE FINDING'S OTHER HALF — "only when the value changed" — is dropped on purpose. A
   * `commit(next) === value` guard silently ate the very first write for a field showing
   * its own default: `'the sub-threshold policy is answered from the start...'` types the
   * store's own $0.40 floor into a field already reading '0.40' and asserts one PUT lands.
   * Telling "the operator re-typed what was already there" from "this field's default
   * happens to match" needs a `written` flag this component has no way to hold — Pricing
   * never re-derived one after the rebuild took `BigMoney` down to its single cut-off call
   * site. The double-commit is the real defect (finding #6's own repro); the no-op guard
   * was this round's own regression, caught by the pricing.spec.ts run below. */
  const justCommitted = useRef(false)
  const commit = (text: string) => {
    const next = text.trim()
    if (!priceable(next)) {
      setDraft(value)
      return
    }
    setDraft(next)
    onCommit(next)
  }
  return (
    <span className="pricing-cheap-amount">
      <span aria-hidden="true" className="pricing-cheap-currency">
        $
      </span>
      <input
        className="pricing-cheap-input"
        inputMode="decimal"
        aria-label={label}
        value={draft}
        size={Math.max(4, draft.length + 1)}
        onChange={(event) => setDraft(event.currentTarget.value.replace(/[^0-9.]/g, ''))}
        onFocus={(event) => event.currentTarget.select()}
        onBlur={(event) => {
          if (justCommitted.current) {
            justCommitted.current = false
            return
          }
          commit(event.currentTarget.value)
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            justCommitted.current = true
            setDraft(value)
            event.currentTarget.blur()
            return
          }
          if (event.key !== 'Enter') return
          event.preventDefault()
          justCommitted.current = true
          commit(event.currentTarget.value)
          event.currentTarget.blur()
        }}
      />
    </span>
  )
}

/** THE ONE "CHANGE" SHEET (D277, Q5): the rule, the cut-off, and a run's own cut-off. */
function RuleSheet({
  open,
  onClose,
  ruleSegment,
  onRule,
  customOn,
  customDraft,
  customBad,
  onCustomDraft,
  onCustomCommit,
  note,
  cut,
  from,
  under,
  above,
  stranded,
  runName,
  onCut,
  onRunCut,
}: {
  open: boolean
  onClose: () => void
  ruleSegment: string
  onRule: (key: string) => void
  customOn: boolean
  customDraft: CustomRule
  customBad: string | null
  onCustomDraft: (next: CustomRule, apply: boolean) => void
  onCustomCommit: (draft: CustomRule) => void
  note: string | null
  cut: string
  from: 'run' | 'store' | 'default'
  under: number
  above: number
  stranded: string | null
  runName: string | null
  onCut: (figure: string) => void
  onRunCut: (figure: string | undefined) => void
}) {
  const overridden = from === 'run'
  return (
    <Sheet open={open} onClose={onClose} title="Pricing rule" icon="tag">
      <section className="pricing-sheet-part" aria-labelledby="pricing-rule-head">
        <h3 className="pricing-sheet-head" id="pricing-rule-head">
          New cards
        </h3>
        <Segmented<string>
          className="pricing-rule-seg"
          label="How new cards are priced"
          value={ruleSegment}
          options={[...PRESETS.map((preset) => ({ value: preset.key, label: preset.label })), { value: CUSTOM_KEY, label: 'Custom' }]}
          onChange={onRule}
        />
        {!customOn ? null : (
          <div className="pricing-custom" data-bad={customBad === null ? undefined : 'true'}>
            <Segmented<RuleKind>
              label="Under or over"
              value={customDraft.kind}
              options={[
                { value: 'undercut', label: KIND_LABEL.undercut },
                { value: 'markup', label: KIND_LABEL.markup },
              ]}
              onChange={(kind) => onCustomDraft({ ...customDraft, kind }, true)}
            />
            <label className="pricing-pct">
              <input
                className="bn-input pricing-pct-input"
                type="text"
                inputMode="decimal"
                placeholder="0"
                aria-label="Percentage"
                aria-invalid={customBad === null ? undefined : true}
                value={customDraft.pct}
                onChange={(event) => {
                  const text = event.currentTarget.value
                  if (PCT.test(text)) onCustomDraft({ ...customDraft, pct: text }, false)
                }}
                onBlur={(event) => onCustomCommit({ ...customDraft, pct: event.currentTarget.value })}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter') return
                  event.preventDefault()
                  onCustomCommit({ ...customDraft, pct: event.currentTarget.value })
                }}
              />
              <span aria-hidden="true">%</span>
            </label>
            <Segmented<RuleBasis>
              label="Which price to work from"
              value={customDraft.basis}
              options={[
                { value: 'market', label: BASIS_LABEL.market },
                { value: 'low', label: BASIS_LABEL.low },
              ]}
              onChange={(basis) => onCustomDraft({ ...customDraft, basis }, true)}
            />
          </div>
        )}
        {customBad === null ? null : <p className="pricing-sheet-bad">{customBad}</p>}
        {note === null ? null : <p className="pricing-sheet-bad">{note}</p>}
      </section>

      <section className="pricing-sheet-part" aria-labelledby="pricing-cut-head">
        <h3 className="pricing-sheet-head" id="pricing-cut-head">
          The cut-off{overridden ? ', this run only' : ''}
        </h3>
        <div className="pricing-cheap-figure">
          <BigMoney value={cut} onCommit={onCut} label={overridden ? 'Cut-off for this run' : 'Cut-off'} />
          <span className="pricing-cheap-caption">
            Cards worth less list at this price. {under} under, {above} above.
          </span>
        </div>
        {stranded === null ? null : (
          <Notice tone="warn" compact title="Cards under the cut-off still list at a second, older price." className="pricing-stranded">
            {Number.isFinite(Number(stranded)) ? (
              <span>
                That price is <Money value={Number(stranded)} />.{' '}
              </span>
            ) : null}
            <Button size="sm" variant="quiet" onClick={() => onCut(cut)}>
              Use the cut-off for both
            </Button>
          </Notice>
        )}
        {runName === null ? null : (
          <p className="pricing-sheet-run">
            <span className="pricing-sheet-run-name">{runName}</span>
            {overridden ? (
              <Button size="sm" variant="quiet" onClick={() => onRunCut(undefined)}>
                Follow the store again
              </Button>
            ) : (
              <Button size="sm" variant="quiet" onClick={() => onRunCut(cut)}>
                Give this run its own cut-off
              </Button>
            )}
          </p>
        )}
      </section>
    </Sheet>
  )
}

/** What a read is asked for: the Live tab's settings. `cap` is dollars, '' for no cap. */
type LiveAsk = { days: string; percent: string; match: boolean; cap: string }

/** THE LIVE TAB'S SETTINGS (D277, Q6): the Mark-down sheet's form, as one short sheet. */
function LiveSheet({
  open,
  onClose,
  asked,
  busy,
  failure,
  cheap,
  cut,
  note,
  onApplyCut,
  onPreset,
  onRead,
}: {
  open: boolean
  onClose: () => void
  asked: Record<string, unknown> | undefined
  busy: boolean
  failure: Failure | null
  cheap: number
  cut: string
  note: string | null
  onApplyCut: (() => void) | null
  onPreset: ((key: string) => void) | null
  onRead: (ask: LiveAsk, file: File | null) => void
}) {
  const [days, setDays] = useState('7')
  const [percent, setPercent] = useState('10')
  const [cap, setCap] = useState('')
  const [match, setMatch] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  useEffect(() => {
    if (!open) return
    setDays(String(asked?.['days'] ?? '7'))
    setPercent(String(asked?.['percent'] ?? '10'))
    /* NO CAP UNLESS THE LAST READ HAD ONE (the owner's ruling, 2026-09-26). */
    setCap(typeof asked?.['cap'] === 'string' ? (moneyField(asked['cap'] as string) ?? '') : '')
    setMatch(asked?.['rule'] === 'match')
    setFile(null)
  }, [open, asked])
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="What to mark down"
      icon="trendDown"
      footer={
        <Button variant="primary" icon="refresh" busy={busy} disabled={busy} onClick={() => onRead({ days, percent, match, cap }, file)}>
          {file === null ? 'Read what is live' : 'Read this file'}
        </Button>
      }
    >
      <p className="pricing-sheet-says">Edits live listings. Deletes nothing.</p>
      <div className="pricing-sheet-fields">
        <label className="bn-field">
          <span className="bn-field-label">Not sold in this many days</span>
          <input className="bn-input" inputMode="numeric" value={days} onChange={(event) => setDays(event.currentTarget.value.replace(/\D/g, ''))} />
        </label>
        <Segmented<'cut' | 'match'>
          label="Price"
          value={match ? 'match' : 'cut'}
          options={[
            { value: 'cut', label: 'Under my price' },
            { value: 'match', label: 'At my price' },
          ]}
          onChange={(next) => setMatch(next === 'match')}
        />
        {match ? null : (
          <label className="bn-field">
            <span className="bn-field-label">Percent under</span>
            <input className="bn-input" inputMode="decimal" value={percent} onChange={(event) => setPercent(event.currentTarget.value.replace(/[^0-9.]/g, ''))} />
          </label>
        )}
        {match ? null : (
          <label className="bn-field">
            <span className="bn-field-label">At most this much off a card, in dollars</span>
            <input
              className="bn-input pricing-cap-field"
              inputMode="decimal"
              placeholder="No limit"
              value={cap}
              onChange={(event) => {
                const next = event.currentTarget.value.replace(/[^0-9.]/g, '')
                if (/^\d{0,6}(\.\d{0,2})?$/.test(next)) setCap(next)
              }}
            />
          </label>
        )}
        <label className="bn-field">
          <span className="bn-field-label">Or read an export file</span>
          <input className="pricing-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.currentTarget.files?.[0] ?? null)} />
        </label>
      </div>
      {onPreset === null ? null : (
        <div className="pricing-sheet-part">
          <h3 className="pricing-sheet-head">Price every listing you have not typed</h3>
          <div className="pricing-sheet-presets">
            {PRESETS.map((preset) => (
              <Button key={preset.key} size="sm" onClick={() => onPreset(preset.key)}>
                {preset.label}
              </Button>
            ))}
            {onApplyCut === null ? null : (
              <Button size="sm" onClick={onApplyCut} disabled={cheap === 0}>
                {`Price ${cheap} at the cut-off`}
              </Button>
            )}
          </div>
          <p className="pricing-sheet-says">
            The cut-off is <Money value={Number(cut)} />.
          </p>
          {note === null ? null : <p className="pricing-sheet-bad">{note}</p>}
        </div>
      )}
      {failure === null ? null : <Notice tone={failureTone(failure)} compact title={failure.message} code={failure.code} />}
    </Sheet>
  )
}

/** The photograph in the sheet, or the shared missing-photo panel when it has none or the file
 *  will not load. Keyed by the copy, so `broken` starts over on "Next copy". */
function SheetPhoto({ name, place }: { name: string; place: MergedSku['positions'][number] | null }) {
  const [broken, setBroken] = useState(false)
  const url = photoUrl(place?.box ?? 0, place?.index ?? 0, place)
  if (url === null) {
    return <AbsentPhotoNote sentence={noPhotoSentence(place?.cid, null)} at={place === null ? null : { box: place.box, cid: place.cid }} />
  }
  if (broken) return <AbsentPhotoNote sentence={ABSENT_SENTENCE} icon="alert" at={place === null ? null : { box: place.box, cid: place.cid }} />
  return <img src={url} alt={name} onError={() => setBroken(true)} />
}

/** One card's photograph, and the next copy of it (the drawer's Photo tab, as a sheet). */
function PhotoSheet({ sku, at, onNext, onClose }: { sku: MergedSku | null; at: number; onNext: () => void; onClose: () => void }) {
  const count = sku?.positions.length ?? 0
  const place = sku === null || count === 0 ? null : (sku.positions[at % count] ?? null)
  return (
    <Sheet
      open={sku !== null}
      onClose={onClose}
      title={sku?.name ?? 'Photograph'}
      icon="image"
      footer={
        <Button icon="chevronRight" onClick={onNext} disabled={count < 2}>
          Next copy
        </Button>
      }
    >
      {sku === null ? null : (
        <div className="pricing-photo">
          <div className="pricing-photo-frame">
            <SheetPhoto key={`${place?.box}/${place?.index}/${place?.cid}`} name={sku.name} place={place} />
          </div>
          <p className="pricing-photo-caption">
            <Location label={place?.label ?? null} flow="run" />
            <span>
              {count === 0 ? 0 : (at % count) + 1} of {count}
            </span>
          </p>
        </div>
      )}
    </Sheet>
  )
}

/** WHAT NO PRESS ON THIS SCREEN CAN SEND, NAMED WITH A DOOR EACH (D156): nothing is dropped
 *  silently from a list the owner counts against a shelf. */
function UnreachableLine({ at }: { at: Unreachable | null }) {
  if (at === null) return null
  const parts: ReactNode[] = []
  if (at.captured > 0)
    parts.push(
      <a key="captured" href="#/review">
        {at.captured} never identified
      </a>,
    )
  if (at.in_review > 0)
    parts.push(
      <a key="review" href="#/review">
        {at.in_review} in Review
      </a>,
    )
  const heldBack = (list: { cards: number | null }[]) => list.filter((row) => row.cards === null || row.cards > 0)
  const unjoinedRuns = heldBack(at.unjoined)
  const unjoined = unjoinedRuns.reduce((n, one) => n + (one.cards ?? 0), 0)
  if (unjoinedRuns.length > 0)
    parts.push(
      <a key="unjoined" href="#/runs">
        {unjoined > 0 ? `${unjoined} in ` : ''}
        {unjoinedRuns.length} {unjoinedRuns.length === 1 ? 'reading' : 'readings'} not matched
      </a>,
    )
  /* "OVER A DELETED BOX" NAMED NO ACTION AND SOUNDED LIKE A LOSS (the owner's review,
     2026-09-26: "gives me anxiety unnecessarily"). It is neither: D36's `bid` means the box
     was only renumbered, and every one of these runs already has its fix — `#/runs` offers a
     Rebind press the moment it opens a stranded run (`RunPanel.tsx`, D165). So this reads as
     the other unreachable reasons do, a link straight to that action. */
  const strandedRuns = heldBack(at.reallocated)
  const stranded = strandedRuns.reduce((n, one) => n + (one.cards ?? 0), 0)
  if (strandedRuns.length > 0)
    parts.push(
      <a key="reallocated" href="#/runs">
        {stranded > 0 ? `${stranded} in ` : ''}
        {strandedRuns.length} {strandedRuns.length === 1 ? 'reading' : 'readings'} need a rebind
      </a>,
    )
  if (parts.length === 0) return null
  return (
    <p className="pricing-unreachable" data-testid="pricing-unreachable">
      <Icon name="alert" size={13} />
      <span>
        Excluded:{' '}
        {parts.map((part, at) => (
          <span key={at}>
            {at === 0 ? null : ', '}
            {part}
          </span>
        ))}
        .
      </span>
    </p>
  )
}

/** Light a field the screen just moved, so the owner sees which rows a press changed. */
function flash(input: HTMLInputElement): void {
  const host = input.closest<HTMLElement>('.pricing-price')
  if (host === null) return
  host.classList.remove('is-flash')
  void host.offsetWidth
  host.classList.add('is-flash')
  window.setTimeout(() => host.classList.remove('is-flash'), 700)
}

/** THE HOLD, as a popover beside its row (a sheet on a phone). Letters, not digits: the digits
 *  are price entry. One sentence says what it does (UX-131). */
function HoldPanel({
  sku,
  onSet,
  onCancel,
}: {
  sku: PricingSku
  onSet: (sku: PricingSku, reason: WithholdReason, watch: string, note: string) => void
  onCancel: () => void
}) {
  const [reason, setReason] = useState<WithholdReason>('bullish')
  const [watch, setWatch] = useState('')
  const [text, setText] = useState('')
  const chips = useRef(new Map<WithholdReason, HTMLButtonElement>())
  useEffect(() => {
    const head = WITHHOLD_REASONS[0]
    if (head !== undefined) chips.current.get(head)?.focus()
  }, [])
  return (
    <div
      className="pricing-holdpanel"
      role="group"
      aria-label={`Hold ${sku.name}`}
      onKeyDown={(event) => {
        const typing = event.target instanceof HTMLInputElement && event.target.type === 'text'
        if (event.key === 'Enter' && !typing) {
          event.preventDefault()
          onSet(sku, reason, watch, text)
          return
        }
        if (typing || event.metaKey || event.ctrlKey || event.altKey) return
        const hit = WITHHOLD_REASONS.find((option) => WITHHOLD_KEYS[option] === event.key.toLowerCase())
        if (hit !== undefined) {
          event.preventDefault()
          setReason(hit)
          chips.current.get(hit)?.focus()
        }
      }}
    >
      <p className="pricing-holdpanel-says">This card stays out of every file until you release it.</p>
      <div className="pricing-holdpanel-reasons" role="group" aria-label="Why">
        {WITHHOLD_REASONS.map((option) => (
          <button
            key={option}
            type="button"
            ref={(node) => {
              if (node) chips.current.set(option, node)
              else chips.current.delete(option)
            }}
            className="pricing-hold-reason"
            aria-pressed={reason === option}
            title={WITHHOLD_LABELS[option]}
            onClick={() => setReason(option)}
          >
            <span>{HOLD_SHORT[option]}</span>
            <Kbd>{WITHHOLD_KEYS[option].toUpperCase()}</Kbd>
          </button>
        ))}
      </div>
      <div className="pricing-holdpanel-fields">
        <label className="bn-field">
          <span className="bn-field-label">Tell me when market is above</span>
          <input
            className="bn-input bn-input-mono"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={watch}
            onChange={(event) => setWatch(event.target.value)}
          />
        </label>
        <label className="bn-field">
          <span className="bn-field-label">Note</span>
          <input className="bn-input" type="text" placeholder="why, in a few words" value={text} onChange={(event) => setText(event.target.value)} />
        </label>
      </div>
      <div className="pricing-holdpanel-actions">
        <Button variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" icon="lock" onClick={() => onSet(sku, reason, watch, text)}>
          Hold it
        </Button>
      </div>
    </div>
  )
}
