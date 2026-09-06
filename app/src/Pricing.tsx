import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'

import {
  describeFailure,
  applyMarkdown,
  getMarkdownTable,
  getPriceHistory,
  getPriceTrends,
  markdownFileUrl,
  markdownHistory,
  markdownTrends,
  emitMerged,
  cropPreview,
  getPricingCorpus,
  getPricingWorklist,
  putPricingCorpus,
  getRun,
  getRuns,
  photoUrl,
  runStep,
  type Failure,
} from './server'
import type {
  DecisionsDocument,
  CorpusAnswer,
  MergedSku,
  RosterRun,
  PricingCorpus,
  MarkdownAnswer,
  MarkdownTable,
  PricingWorklist,
  PricingSku,
  RunDetail,
  RunFile,
  RunSummary,
  TrendRange,
  WithheldRecord,
} from './types'
import { WITHHOLD_KEYS, WITHHOLD_LABELS, WITHHOLD_REASONS, type WithholdReason } from './holds'
import { isEditableTarget } from './keys'
import { FLAT_KEY, owed, subThresholdSkus, type OwedReason } from './readiness'
import { PriceHistoryPanel, RANGE_LABEL, type HistoryRead } from './PriceHistory'
import { TrendCell, type TrendRead } from './PriceTrend'
import { RunFiles } from './RunFiles'
import { Markdown } from './Markdown'
import { LogWell } from './RunsLog'
import { runBoxLabel } from './runScope'
import {
  markdownInHash,
  markdownSource,
  runSource,
  runsInHash,
  type PricingSource,
  type SectionSpec,
} from './pricingSource'
import { Button, cropStyle, EmptyState, Icon, Kbd, Notice, Segmented, type Crop } from './kit'
import { toast } from './kit/toast'
import './Pricing.css'

/* #/pricing — THE HAND-PRICING WORKLIST (D49, D86).
 *
 * A hundred real decisions in a sitting: accept the rule's suggestion, type a price, snap to
 * an export column, or hold the card — then write the import files. One answer per card, for
 * the whole store, in `inventory/prices.json`. The client performs no arithmetic on money:
 * every figure it can put in a field came pre-rounded out of the join. */

/** How deep the undo stack goes. */
const UNDO_DEPTH = 10

/** How many SKUs one batched trend request asks about — a latency number, not a courtesy one. */
const TREND_CHUNK = 8

function runDay(stamp: string | null | undefined): string | null {
  if (typeof stamp !== 'string' || stamp.trim() === '') return null
  const at = new Date(stamp)
  if (Number.isNaN(at.getTime())) return null
  return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** The three presets, matching `cli/cmd_join.py:PRESETS` key for key AND rule for rule.
 *  Audited by `scripts/docs-audit.py`'s `pricing presets` row. Labels are free; the tuple is not. */
const PRESETS: { key: string; label: string; rule: string; basis: string; says: string }[] = [
  {
    key: 'market_match',
    label: 'Match market',
    rule: 'match',
    basis: 'market',
    says: 'The recent actual-sale average, matched exactly.',
  },
  {
    key: 'market_undercut_5',
    label: 'Market −5%',
    rule: 'undercut:5',
    basis: 'market',
    says: '5% under the recent actual-sale average, clamped at the floor after rounding.',
  },
  {
    key: 'low_undercut_1',
    label: 'TCG Low −1%',
    rule: 'undercut:1',
    basis: 'low',
    says: '1% under the cheapest current listing. Rows with no TCG Low price are left alone.',
  },
]

/* ---------------------------------------------------------------------- the custom rule */

/** THE FOURTH ANSWER, AND IT IS AN ANSWER RATHER THAN AN ESCAPE HATCH (the owner, 2026-09-03).
 *
 *  `pipeline/pricing.py` has always taken three rules over two bases — `match`, `undercut:PCT`,
 *  `markup:PCT`, priced against `market` or `low` — and the three presets above spend five of
 *  the combinations. Everything else was reachable only by hand-editing the file, which this
 *  screen documented in a sentence and offered no way to do. It is a control now: the same
 *  strip, the same standing `policy.rule` / `policy.basis`, written the same way a preset
 *  writes them.
 *
 *  The KIND is the grammar `Rule.parse` accepts, so it is composed here and never invented. */
const CUSTOM_KEY = 'custom'

type RuleKind = 'undercut' | 'markup'
type RuleBasis = 'market' | 'low'

/** The three answers the operator gives. `pct` is what is TYPED, which is wider than what may
 *  be written — the alphabet below admits `""` and a trailing dot on the way to a figure. */
type CustomRule = { kind: RuleKind; pct: string; basis: RuleBasis }

/** THE ACCEPTED ALPHABET FOR A PERCENTAGE, CLOSED, exactly as `PRICE` is for money: digits,
 *  at most one dot, at most two places after it, at most three before. A letter is refused at
 *  the keystroke rather than at the write. */
const PCT = /^\d{0,3}(\.\d{0,2})?$/

const KIND_LABEL: Record<RuleKind, string> = { undercut: 'Undercut', markup: 'Markup' }
const BASIS_LABEL: Record<RuleBasis, string> = { market: 'Market', low: 'TCG Low' }

/** What each basis IS, in the clause the presets' own sentences use, so a custom sentence and
 *  a preset sentence are the same English. */
const BASIS_SAYS: Record<RuleBasis, string> = {
  market: 'the recent actual-sale average',
  low: 'the cheapest current listing',
}

/** The standing rule read back as a custom answer, or null where it is a preset, unset, or a
 *  string this screen cannot compose (a hand-written `match` with a percentage, say). This is
 *  the whole round-trip: `policy.rule` is a free string on the wire and survives the PUT. */
function parseCustomRule(rule: string | undefined | null, basis: string | undefined | null): CustomRule | null {
  if (typeof rule !== 'string') return null
  const [kind, pct] = rule.trim().toLowerCase().split(':')
  if (kind !== 'undercut' && kind !== 'markup') return null
  if (pct === undefined || !/^\d{1,3}(\.\d{1,2})?$/.test(pct)) return null
  const where: RuleBasis = basis === 'low' ? 'low' : 'market'
  return { kind, pct: String(Number(pct)), basis: where }
}

/** Why this percentage cannot be written, in a sentence, or null when it can. The bounds are
 *  `pipeline/pricing.py:Rule.parse`'s own — a negative inverts the rule and an undercut of 100%
 *  or more prices at or below zero — refused here so the operator reads a sentence instead of
 *  emit refusing a run later. */
function badPercent(kind: RuleKind, pct: string): string | null {
  const text = pct.trim()
  if (text === '') return 'Type a percentage and this becomes the standing rule.'
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(text)) return 'A percentage is digits, with up to two places after the point.'
  const value = Number(text)
  if (!Number.isFinite(value)) return 'A percentage is digits, with up to two places after the point.'
  if (value === 0) return 'Nothing off the basis price is Match market — pick that instead.'
  if (kind === 'undercut' && value >= 100) return `Undercutting by ${text}% prices at or below zero.`
  return null
}

/** The rule as `pipeline/pricing.py` spells it. Never composed anywhere else. */
function customRuleText(rule: CustomRule): string {
  return `${rule.kind}:${rule.pct.trim()}`
}

/** The sentence under the strip, built from the presets' own clauses. */
function customSays(rule: CustomRule, floor: string | null): string {
  const move = rule.kind === 'undercut' ? 'under' : 'above'
  const head = `${rule.pct.trim()}% ${move} ${BASIS_SAYS[rule.basis]}`
  const tail =
    rule.basis === 'low'
      ? '. Rows with no TCG Low price are left alone.'
      : rule.kind === 'undercut'
        ? `, clamped at the $${floor} floor after rounding.`
        : '.'
  return head + tail
}

/** The rule in the shorthand a row has room for: `−7%`, `+12%`. */
function customShort(rule: CustomRule): string {
  return `${rule.kind === 'undercut' ? '−' : '+'}${rule.pct.trim()}%`
}

/** The four columns a letter key snaps the price to, in the order they are drawn. */
const SNAPS: { key: string; field: keyof PricingSku['snap']; label: string; says: string; column: string }[] = [
  { key: 'm', field: 'market', label: 'Market', says: 'Market', column: 'TCG Market Price' },
  { key: 'l', field: 'low', label: 'Low', says: 'Low', column: 'TCG Low Price' },
  { key: 's', field: 'low_with_shipping', label: '+Ship', says: 'Low with shipping', column: 'TCG Low Price With Shipping' },
  { key: 'd', field: 'direct_low', label: 'Direct', says: 'Direct low', column: 'TCG Direct Low' },
]

/* THE SECTION LIST STAYS HERE AND IS PASSED TO THE SOURCE, beside `PRESETS`, which
   `scripts/docs-audit.py`'s `pricing presets` row reads out of THIS FILE by path. The pricing
   vocabulary belongs at the screen's front door, and moving half of it would turn a passing
   mechanical check into a false alarm over the other half. */
const SECTIONS: SectionSpec[] = [
  {
    bucket: 'listable',
    title: 'Above the cut-off',
    icon: 'tag',
    note: (cut) => `Market at or above $${cut}. These are priced by the standing rule.`,
  },
  {
    bucket: 'sub_threshold',
    title: 'Under the cut-off',
    icon: 'minus',
    note: (cut) => `Market below $${cut}, so these go out at $${cut} — unless you type a price on the row.`,
  },
  {
    bucket: 'no_market_data',
    title: 'No market price',
    icon: 'alert',
    note: () => 'The catalog carries no price for these. A missing price is unknown, not low — the files cannot be written while any is unanswered.',
  },
]

/* THE LENS DRAWS ONE BAND, because the three above are a JOIN's partition. `bucket` decides
   which import file a row is bound for, and a live listing is bound for none — it is already
   listed. One section, named for what these rows actually are. */
const LIVE_SECTIONS: SectionSpec[] = [
  {
    bucket: 'listable',
    title: 'Live at TCGplayer',
    icon: 'tag',
    note: () => 'Every listing this export reported live. Type a price on any of them; nothing is sent until you press.',
  },
]

/** THE ACCEPTED ALPHABET, CLOSED. `[0-9.]`, at most one dot, at most two digits after it. Every
 *  letter is therefore a command rather than a character. */
const PRICE = /^\d*(\.\d{0,2})?$/

/* ---------------------------------------------------------------- the cheap-card answer */


/** The sub-threshold answer in either of its two shapes, or nothing written. */
type SubAnswer = string | { flat: string } | null

/** A figure that can be WRITTEN, which is narrower than what may be TYPED: the field's alphabet
 *  admits `""` and a trailing dot on the way to a price, and `Decimal("0.")` is an error on the
 *  other side of the wire. */
function priceable(text: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(text.trim())
}

/* ------------------------------------------------------------------------ the cut-off
 *
 * ONE FIGURE, TWO JOBS (the owner, 2026-09-03). D9 wrote the threshold and the cheap-card
 * price as two settings, and this screen drew them as two: a threshold of $0.40 deciding
 * which cards were cheap, and a separate flat answer of $0.49 those cards listed at. Held
 * apart they invert — a card at $0.38 is cheap and goes out at $0.49, a card at $0.42 is
 * listable and goes out at $0.42, so the cheap card lists ABOVE the one that cleared the bar.
 * The owner's ruling is that they are the same variable: everything under the cut-off lists
 * AT the cut-off, and nothing under it can ever price above something over it.
 *
 * SO ONE PRESS WRITES BOTH KEYS. `policy.threshold` is what `pipeline/join.py` partitions by
 * and `policy.sub_threshold` is what it prices the lower half at; this screen never writes one
 * without the other, at the store and at the run. */

/** The store's standing cut-off — a default, not a silent write (the owner, 2026-09-03). */
const STORE_DEFAULT_CUT = '0.49'

/** Money as integer cents, or null where the text is not a figure. Cents rather than floats
 *  because the comparison decides which file a card goes in: `0.1 + 0.2` has no business
 *  anywhere near a partition. */
function cents(text: string | null | undefined): number | null {
  if (typeof text !== 'string') return null
  const trimmed = text.trim()
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null
  return Math.round(Number(trimmed) * 100)
}

/** THE CHEAP-CARD PRICE AS IT STANDS ON DISK, where it is not the cut-off — `null` where the
 *  two agree, which is every store this screen has written since the figures became one.
 *
 *  A STORE WRITTEN UNDER THE OLD TWO-FIGURE MODEL CAN SAY BOTH THINGS AT ONCE, and this
 *  machine's own does: `threshold: "0.40"` beside `sub_threshold: {flat: "0.24"}`. Neither is
 *  wrong and the screen may not pick between them silently — drawing the cut-off alone would
 *  claim cheap cards go out at $0.40 while `emit` would write $0.24. So it is reported, and one
 *  press resolves it, because every commit here writes both keys. */
function strandedFlat(doc: DecisionsDocument, cut: string): string | null {
  const answer = doc.sub_threshold
  if (answer === null || answer === undefined) return null
  if (typeof answer === 'string') return 'the floor'
  const flat = String((answer as Record<string, unknown>)[FLAT_KEY] ?? '')
  return flat !== '' && cents(flat) !== cents(cut) ? `$${flat}` : null
}

/** A written cut-off on a policy object, or null where nothing is written. */
function writtenCut(policy: Record<string, unknown> | undefined): string | null {
  const value = policy?.['threshold']
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

/** Which section a row draws in, AT A GIVEN CUT-OFF.
 *
 *  `pipeline/pricing.py:is_listable` in the client's own terms: no market data is unpriced and
 *  never cheap (D9), and everything else is `market >= cut`. The market cell decides it and the
 *  basis is not consulted — a threshold reads Market whatever the rule is priced from.
 *
 *  THE OPERATOR STILL CANNOT MOVE A ROW BY TYPING ON IT, which is what D28 protects: the only
 *  input here is the cut-off, a policy figure, and a policy change is exactly the moment the
 *  list is SUPPOSED to re-partition. A price typed on a row moves nothing, as before. */
function bucketAt(sku: PricingSku, cut: string): PricingSku['bucket'] {
  if (sku.bucket === 'no_market_data') return sku.bucket
  const market = cents(sku.snap.market)
  const line = cents(cut)
  if (market === null || line === null) return sku.bucket
  return market >= line ? 'listable' : 'sub_threshold'
}


/** How old a reading is, in words. A live figure is never drawn without one (the owner,
 *  2026-09-03): a count with no age reads as a fact about the marketplace when it is a fact
 *  about the last time this store looked. */
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

/** This run's own sub-threshold override, or `undefined` where it follows the store.
 *
 *  `pipeline/corpus.py:policy_for` folds exactly this key over the standing policy —
 *  `over.get("sub_threshold", self.sub_threshold)` — so a run written here is a run the
 *  pipeline prices differently. D86 named the shape and left it unwritten; this screen is
 *  what writes it. */
function runOverride(book: PricingCorpus | null, run: string | null): SubAnswer | undefined {
  if (book === null || run === null) return undefined
  const table = book.policy?.per_run
  const entry = table?.[run]
  if (entry === undefined || !('sub_threshold' in entry)) return undefined
  const value = entry['sub_threshold']
  if (typeof value === 'string') return value
  if (typeof value === 'object' && value !== null && FLAT_KEY in value) return value as { flat: string }
  return undefined
}

/** This run's own cut-off, or `undefined` where it follows the store. */
function runCut(book: PricingCorpus | null, run: string | null): string | undefined {
  if (book === null || run === null) return undefined
  return writtenCut(book.policy?.per_run?.[run]) ?? undefined
}

/** Patch one run's policy, returning a NEW corpus. A key set to `undefined` is cleared, and an
 *  entry left empty — and `per_run` itself — is pruned, so following the store again leaves no
 *  trace of having differed from it.
 *
 *  `pipeline/corpus.py:policy_for` folds exactly these keys over the standing policy —
 *  `over.get("threshold", self.threshold)` and the same for `sub_threshold` — so a run written
 *  here is a run the pipeline partitions AND prices differently. D86 named the shape and left
 *  it unwritten; this screen is what writes it. */
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

/** Short chip labels for the hold reasons; the full sentence is drawn beneath the chips. */
const HOLD_SHORT: Record<WithholdReason, string> = {
  bullish: 'Bullish',
  keeping: 'Keeping this one',
  next_batch: 'A later batch',
}

/** A server word drawn as a label: the first letter is raised, the rest is left alone. */
function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function isWithheld(value: unknown): value is WithheldRecord | 'unlisted' {
  return value === 'unlisted' || (typeof value === 'object' && value !== null && 'withheld' in value)
}

function heldReason(value: WithheldRecord | 'unlisted'): string {
  return value === 'unlisted' ? '' : String(value.withheld ?? '')
}

/** Where a section's answer is written: a property of the SECTION, not the row. */
function targetOf(bucket: PricingSku['bucket']): 'overrides' | 'no_market_data' {
  return bucket === 'no_market_data' ? 'no_market_data' : 'overrides'
}

/** Why this run adds no row for this SKU, as a heading — or null for the ordinary row. */
function groupOf(sku: PricingSku): string | null {
  return sku.at_cap ? (sku.nothing_to_add ?? 'nothing to add this run') : null
}

const HELD_HEAD = 'held back from this run'

/** The SKUs drawn as held when the page opened — a snapshot, so a hold sinks on the REOPENING
 *  and never under the hand that just pressed H (D28, D78). */
function heldOnArrival(rows: readonly PricingSku[], doc: DecisionsDocument): ReadonlySet<string> {
  const overrides = (doc.overrides ?? {}) as Record<string, unknown>
  const unpriced = (doc.no_market_data ?? {}) as Record<string, unknown>
  const out = new Set<string>()
  for (const row of rows) {
    const standing = targetOf(row.bucket) === 'overrides' ? overrides[row.sku] : unpriced[row.sku]
    if (isWithheld(standing)) out.add(row.sku)
  }
  return out
}

type Drawn = { head: string; count: number } | { head: null; sku: MergedSku }

type Undo = {
  sku: string
  before: CorpusAnswer | undefined
  channel: 'price' | 'unknown'
}

/** The corpus as the document every reader on this screen understands. Read-only projection.
 *
 *  `run` FOLDS THAT RUN'S POLICY OVERRIDE OVER THE STORE'S, in `corpus.py:policy_for`'s own
 *  order, so the readiness line, the row labels and the panel all read one effective answer
 *  rather than three that can disagree. Null run — several loaded, or none — is the store's
 *  policy alone, which is what a merged send is priced by. */
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

/** Set or clear one card's answer, returning a NEW corpus. `undefined` deletes the key. */
function setAnswer(book: PricingCorpus, sku: string, value: unknown, channel: 'price' | 'unknown'): PricingCorpus {
  const skus = { ...(book.skus ?? {}) }
  if (value === undefined) delete skus[sku]
  else skus[sku] = { ...(skus[sku] ?? {}), value: value as never, channel }
  return { ...book, skus }
}

/** Close a popover on an outside press or Escape. */
function useDismiss(ref: RefObject<HTMLElement | null>, open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return
    const press = (event: PointerEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose()
    }
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('pointerdown', press)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('pointerdown', press)
      document.removeEventListener('keydown', key)
    }
  }, [ref, open, onClose])
}

/** Whether the shell is in its phone layout (top bar + tab bar), where popovers become sheets. */
function usePhone(): boolean {
  const [phone, setPhone] = useState(() => window.matchMedia('(max-width: 767px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)')
    const sync = () => setPhone(query.matches)
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])
  return phone
}

/** Where the shell's content column starts, so a drawer can sit beside the sidebar or the rail. */
function shellLeft(): number {
  const main = document.querySelector('.bn-shell-main')
  return main === null ? 0 : Math.round(main.getBoundingClientRect().left)
}

/** The run picker — a filter over the worklist, never a gate in front of it (D86). Multi-select,
 *  drawn in date-desc / box-asc order. The drawer large, the directory small beneath it (D56). */
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
      <div className="pricing-runs-head">
        <span className="bn-label">Runs</span>
        <span className="pricing-runs-count">
          {picked.size === 0 ? `${open} with pricing left · showing all of them` : `${picked.size} picked`}
        </span>
      </div>
      <div className="pricing-runs-list">
        {order.map((row) => {
          const label = runBoxLabel(row)
          const day = runDay(row.created_at)
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
                  {label === null || day === null ? null : ` · ${day}`}
                </span>
                <span className="pricing-run-meta">
                  {label === null ? null : <span className="pricing-run-id">{row.run}</span>}
                  <span>{row.counts?.skus ?? '?'} SKUs</span>
                </span>
              </span>
              <span className={`pricing-run-owes bn-pill ${row.open ? 'bn-pill-warn' : 'bn-pill-ok pricing-run-done'}`}>
                {row.owes.length === 0 ? 'Answered' : sentence(row.owes.join(' · '))}
              </span>
            </button>
          )
        })}
      </div>
      {picked.size === 0 ? null : (
        <div className="pricing-runs-foot">
          <Button size="sm" variant="ghost" icon="x" onClick={onClear}>
            Show everything unpriced
          </Button>
        </div>
      )}
    </div>
  )
}

/**
 * A LIVE COUNT IS NEVER DRAWN WITHOUT ITS AGE (the owner, 2026-09-03).
 *
 * `3 live` alone reads as a fact about the marketplace. It is a fact about the last time this
 * store looked: the figure was frozen into `pricing.json` when the run was joined, and the
 * listings row it came from was last moved by a `reconcile --live`. Zero is the sharpest case
 * — a SKU with copies pushed and none live is usually an unreconciled push rather than an
 * empty shelf — so it is drawn too, with the same age beside it.
 */
function LiveCount({ live, age }: { live: number; age: string | null }) {
  return (
    <span
      className="pricing-live"
      data-none={live === 0 ? 'true' : undefined}
      title={
        `What TCGplayer was holding live for this SKU when the run was joined${age === null ? '' : `, ${age}`}. ` +
        'A reconcile on Runs takes a fresh reading.'
      }
    >
      <span className="bn-dot bn-dot-live" aria-hidden="true" />
      {live} live
      {age === null ? null : <span className="pricing-live-age">· read {age}</span>}
    </span>
  )
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <section className="pricing-section" aria-hidden="true">
      <header className="pricing-section-head">
        <span className="bn-skeleton" style={{ width: 160, height: 18 }} />
      </header>
      <div className="pricing-list">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="pricing-row pricing-row-skel" style={{ '--i': String(i) } as CSSProperties}>
            <span className="bn-skeleton" style={{ width: 36, height: 48 }} />
            <span className="bn-skeleton" style={{ width: `${40 + ((i * 17) % 35)}%`, height: 14 }} />
            <span className="bn-skeleton" style={{ width: 110, height: 34 }} />
            <span className="bn-skeleton" style={{ width: 52, height: 12 }} />
            <span className="bn-skeleton" style={{ width: 52, height: 12 }} />
          </div>
        ))}
      </div>
    </section>
  )
}


/* THE ROW THUMBNAILS ARE CROPPED TO THE CARD (the same treatment the Home hero has).
 *
 * A rig photograph is mostly stand — on box 6 the card sits at [240, 1051, 1649, 3020] inside a
 * 2160x3840 frame — and at 36x48 that left the card a smudge in the middle of a dark rectangle,
 * which is no help at all to an operator pricing a hundred cards by eye. `POST
 * /pipeline/crop-preview` is the SAME detector the batch reading uses, it is free, it calls no
 * model, and it returns the rectangle; `cropStyle` (kit) turns it into a picture of the card.
 *
 * WHY THE FETCHING IS ITS OWN LITTLE MACHINE HERE, rather than a request per row:
 *
 *   - ONE CARD PER CALL, ALWAYS. `indices` is a scope, not a batch — the route answers with one
 *     `sample`, picked out of the scope by `offset`. So a row is a request, and the only levers
 *     left are how many rows ask and when.
 *   - STRICTLY SERIAL, and this one is not a preference. The route builds a scope directory named
 *     `box<n>-<count>-<unix seconds>` and deletes any directory already at that name; every
 *     single-index request for one box inside the same second therefore collides on the SAME
 *     name and rmtree's its neighbour mid-read. Measured against this server: 12 concurrent
 *     requests, 11 failed with a FileNotFoundError out of the symlink. One in flight at a time.
 *   - ONLY WHAT IS ON SCREEN. An IntersectionObserver asks when the row comes within 400px of
 *     the viewport, so an 11-row worklist costs 11 requests and a 109-row one costs the dozen
 *     that were actually looked at.
 *   - ANSWERED ONCE PER SESSION. The reading is a property of a photograph, and a photograph at
 *     `box/index` does not change under a pricing sitting, so the cache outlives the mount and a
 *     scroll back up costs nothing.
 *   - `max_edge: 256` because the response carries the prepared JPEG as a data URI and nothing
 *     here draws it: 523KB a row at the default, 20KB at the floor. The rectangle is computed
 *     against the ORIGINAL size and is identical either way.
 *
 * A refusal, a missing rect, or a server that is not there leaves `cover` in place. The row was
 * legible before this and must never be worse for it. */
type CropRead = Crop | null

/** Answered readings, `box/index` -> crop or null. Module scope: it survives the mount. */
const CROPS = new Map<string, CropRead>()
/** Asked for, not yet answered. Drained one at a time by `pumpCrops`. */
const CROP_QUEUE: string[] = []
const CROP_WATCH = new Map<string, Set<() => void>>()
let cropPumping = false

function cropKey(box: number, index: number): string {
  return `${box}/${index}`
}

function wantCrop(key: string): void {
  if (CROPS.has(key) || CROP_QUEUE.includes(key)) return
  CROP_QUEUE.push(key)
  void pumpCrops()
}

async function pumpCrops(): Promise<void> {
  if (cropPumping) return
  cropPumping = true
  try {
    for (;;) {
      const key = CROP_QUEUE.shift()
      if (key === undefined) return
      if (CROPS.has(key)) continue
      const [box, index] = key.split('/').map(Number)
      let read: CropRead = null
      try {
        const { sample } = await cropPreview({ box: box!, indices: [index!], crop: true, maxEdge: 256 })
        if (sample.rect != null && sample.frame != null && sample.crop_refused == null) {
          read = { frame: sample.frame, rect: sample.rect }
        }
        /* A REFUSAL IS AN ANSWER and is remembered: `crop_refused`, no rectangle, an unreadable
           frame. Asking again would get the same one out of the same photograph. */
        CROPS.set(key, read)
      } catch {
        /* A FAILURE IS NOT AN ANSWER, so nothing is written down. The row stays uncropped for
           this mount — its observer has already fired — and the next visit to the screen asks
           again, which is what a capture server that was restarting deserves. */
      }
      const told = CROP_WATCH.get(key)
      if (told !== undefined) for (const tell of told) tell()
    }
  } finally {
    cropPumping = false
  }
}

/** Where the window sits on the card, and it is the hero's figure for a different reason.
 *  36x48 over a detected rectangle averaging 0.55 wide-to-tall shows about three-quarters of
 *  the height, so a quarter goes; which quarter was decided by looking at eight real rows at
 *  0.50, 0.42 and 0.34. The detector's rectangle is generous BELOW the card — it takes in the
 *  stand's TRADING CARD GAME strip — so a centred window (0.50) cuts the top off the art and
 *  keeps the strip, and 0.34 puts the card's own top edge at the window's top and drops the
 *  strip instead. The art, the name and the first lines of text, which is what a name in the
 *  next column is being checked against. */
const THUMB_FOCUS = 0.34

/** The row's photograph: a press that opens the drawer, and the crop that makes it worth
 *  looking at. Its own component so one answered reading redraws one thumbnail rather than a
 *  hundred priced rows. */
function PricingThumb({ at, name, onOpen }: { at: PricingSku['positions'][number] | null; name: string; onOpen: () => void }) {
  const key = at === null ? null : cropKey(at.box, at.index)
  const [crop, setCrop] = useState<CropRead>(() => (key === null ? null : CROPS.get(key) ?? null))
  const host = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (key === null) return
    const answered = CROPS.get(key) ?? null
    setCrop(answered)
    if (CROPS.has(key)) return
    const tell = () => setCrop(CROPS.get(key) ?? null)
    let watching = CROP_WATCH.get(key)
    if (watching === undefined) {
      watching = new Set()
      CROP_WATCH.set(key, watching)
    }
    watching.add(tell)
    const node = host.current
    let eye: IntersectionObserver | null = null
    if (node !== null && typeof IntersectionObserver === 'function') {
      eye = new IntersectionObserver(
        (entries) => {
          if (!entries.some((entry) => entry.isIntersecting)) return
          eye?.disconnect()
          eye = null
          wantCrop(key)
        },
        { rootMargin: '400px 0px' },
      )
      eye.observe(node)
    } else {
      wantCrop(key)
    }
    return () => {
      watching?.delete(tell)
      if (watching?.size === 0) CROP_WATCH.delete(key)
      eye?.disconnect()
    }
  }, [key])

  return (
    <button
      ref={host}
      type="button"
      className="pricing-thumb"
      aria-label={`Photograph of ${name}`}
      title="Photograph · P"
      onClick={onOpen}
      data-cropped={crop !== null ? 'true' : undefined}
    >
      {at === null ? (
        <Icon name="image" size={14} />
      ) : (
        <img
          className="bn-crop"
          src={photoUrl(at.box, at.index)}
          alt=""
          loading="lazy"
          data-cropped={crop !== null ? 'true' : undefined}
          style={cropStyle(crop, THUMB_FOCUS)}
          /* Undone, re-shot or reclaimed (D89): leave the frame, never a broken image glyph. */
          onError={(event) => {
            event.currentTarget.style.visibility = 'hidden'
          }}
        />
      )}
    </button>
  )
}

export function Pricing() {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  /** Which runs the worklist is over; EMPTY means "whatever still has work in it" (D86). */
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set(runsInHash()))
  const [work, setWork] = useState<PricingWorklist | null>(null)
  /** THE MARKDOWN STAMP ON THE HASH, and the table it names (D103). Null is the runs mode,
   *  which is every visit that does not carry `?markdown=`. Separate state from `work` on
   *  purpose: the two are different documents and nothing folds them together. */
  const [stamp, setStamp] = useState<string | null>(() => markdownInHash())
  const [sheet, setSheet] = useState<MarkdownTable | null>(null)
  /** The lens's press, as a state machine rather than a call — for the emit press's reason:
   *  `reprice apply` reads `inventory/prices.json` OFF DISK, so it must not run while a save
   *  is still in flight. `checking`/`writing` park until the autosave is quiet. */
  /** Whether the markdown sheet is open (D105). It lives HERE now rather than on `#/runs`,
   *  because a markdown decides a price and this is where prices are decided — D100 placed it
   *  beside the store-wide reconcile on kinship of IMPLEMENTATION (both read one export), which
   *  is not kinship of work. */
  const [mdOpen, setMdOpen] = useState(false)
  const [push, setPush] = useState<'idle' | 'checking' | 'writing'>('idle')
  const [applied, setApplied] = useState<MarkdownAnswer | null>(null)
  const [wroteUpload, setWroteUpload] = useState(false)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  /** The pricing corpus — one document for the store, and the authority (D86). */
  const [book, setBook] = useState<PricingCorpus | null>(null)
  const [sendingAll, setSendingAll] = useState(false)
  const [listedOnly, setListedOnly] = useState(false)
  /* ONE PRESS WRITES ONE SPREADSHEET (D99), AND THE SPLIT IS AN OPTION BEHIND IT (the owner,
     2026-09-03). Off is the product's answer: across runs, across games and across the two
     sides of the cut-off, emit writes `import.csv`. On, it writes the pair back —
     `import-listed.csv` and `import-subthreshold.csv` — for the send that genuinely wants
     them staged separately. It is never on by default and never remembered. */
  const [splitFiles, setSplitFiles] = useState(false)

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
  const [holdFor, setHoldFor] = useState<string | null>(null)
  const [sunkHolds, setSunkHolds] = useState<ReadonlySet<string>>(() => new Set())
  const [photoFor, setPhotoFor] = useState<{ sku: string; at: number } | null>(null)

  /* The price history (D62): `peek` is the held `t`, `pinned` is the click. `peek ?? pinned`. */
  const [pinned, setPinned] = useState<string | null>(null)
  const [peek, setPeek] = useState<string | null>(null)
  const historyFor = peek ?? pinned
  const [history, setHistory] = useState<Record<string, HistoryRead>>({})

  /* The trend strip (D79): keyed by run, cleared when the loaded set changes. */
  const [trends, setTrends] = useState<Record<string, TrendRead>>({})
  const [trendRun, setTrendRun] = useState<{
    run: string
    total: number
    done: number
    skipped: number
    spans: TrendRange[] | null
    reading: boolean
  } | null>(null)
  const trendWalk = useRef(0)
  const [note, setNote] = useState<{ sku: string; text: string } | null>(null)
  const [filterHeld, setFilterHeld] = useState(false)
  /** WHICH LIVE LISTINGS ARE ON SCREEN (D103). `all` is the default and that is the owner's
   *  ruling — staleness is a filter they apply, not a gate applied before the data arrives.
   *  The alternative was measured and is why: against their own export the seven-day window
   *  selects 109 of 441 rows and the ten-day window selects NONE, because the oldest capture
   *  in the store is nine days old. A gate hands back an empty screen for a reason about the
   *  store's age rather than about the listings. */
  const [lens, setLens] = useState<'all' | 'offered' | 'refused'>('all')

  /* THE CUSTOM RULE'S THREE ANSWERS, HELD AS A DRAFT. The standing rule is the corpus's and
     the corpus is written on a valid figure only, so a half-typed percentage is a state of
     this screen and never a state of the document. `pressedCustom` is the segment being
     chosen before a figure exists — the one moment the strip shows Custom and the standing
     rule is still a preset's. */
  const [customDraft, setCustomDraft] = useState<CustomRule>({ kind: 'undercut', pct: '', basis: 'market' })
  const [pressedCustom, setPressedCustom] = useState(false)
  const [customBad, setCustomBad] = useState<string | null>(null)
  const customSeed = useRef<string | null>(null)
  const customPct = useRef<HTMLInputElement | null>(null)
  const [runsOpen, setRunsOpen] = useState(false)
  const [filesOpen, setFilesOpen] = useState(false)
  const [consoleOpen, setConsoleOpen] = useState(false)

  /* Shipping this run (D54): the emit press and its import CSVs live here. */
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [ship, setShip] = useState<'idle' | 'waiting' | 'sending'>('idle')
  const [receipt, setReceipt] = useState<{ ok: boolean; console: string; files: readonly RunFile[] } | null>(null)
  const [shipTrouble, setShipTrouble] = useState<Failure | null>(null)
  const [armed, setArmed] = useState(false)
  /* The landing deck flashes when the ship bar's verdict is pressed — the press is at the
     bottom of a long list and the account of it is at the top. */
  const deckRef = useRef<HTMLDivElement | null>(null)

  const inputs = useRef(new Map<string, HTMLInputElement>())
  const loadWalk = useRef(0)
  /** The digest of `inventory/prices.json` as this screen last saw it, sent with every write so
   *  the route can refuse one that would revert somebody else's. Empty until the first read. */
  const revision = useRef<string>('')
  const savedBook = useRef<PricingCorpus | null>(null)
  const inFlight = useRef(false)
  const failedBook = useRef<PricingCorpus | null>(null)
  const touched = useRef(new Set<string>())
  const pickerRef = useRef<HTMLDivElement | null>(null)
  const phone = usePhone()

  useEffect(() => {
    const fromHash = () => {
      const named = runsInHash()
      if (named.length > 0) setPicked(new Set(named))
      // THE STAMP FOLLOWS THE HASH IN BOTH DIRECTIONS, unlike the run list above, which only
      // ever widens. Leaving `#/pricing?markdown=…` has to put the screen back on runs, or the
      // lens would survive the operator navigating out of it.
      setStamp(markdownInHash())
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const rows = await getRuns()
        if (!live) return
        setRuns(rows)
        /* THE PUBLISHED DEMO PICKS A RUN, because two of them turn off the two things this
           screen is most worth showing. `run` below is `loaded.length === 1 ? … : null` — a
           price history and a trend strip are per-RUN routes — so with every run loaded the
           `t` hold opens a panel it can never fill and "Load trends" is disabled. That is
           correct for an operator, who wants all their unpriced work in one list and knows
           to narrow; it is a dead end for somebody who arrived from a link and will never
           open the Runs dropdown.

           So the demo starts narrowed and the viewer can WIDEN — the cross-run "2 runs · 2
           boxes · one file" story is one click away in the picker, and the rich per-row view
           is what they meet first. Only when the hash names no run, so a shared
           `#/pricing?run=…` link still wins. */
        if (__BN_DEMO__ && runsInHash().length === 0) {
          const joined = rows.filter((row) => row.joined)
          const first = joined[0]
          if (joined.length > 1 && first !== undefined) setPicked(new Set([first.run]))
        }
      } catch (err) {
        if (live) setFailure(describeFailure(err))
      }
    })()
    return () => {
      live = false
    }
  }, [])

  /** Fetch the rows and the corpus together. One read whatever the source (D103). */
  const load = useCallback(async (wanted: ReadonlySet<string>, markdown: string | null) => {
    trendWalk.current += 1
    setTrends({})
    setTrendRun(null)
    setLoading(true)
    loadWalk.current += 1
    const mine = loadWalk.current
    try {
      /* THE CORPUS IS READ EITHER WAY AND THE ROWS COME FROM WHICHEVER DOOR WAS ADDRESSED.
         One await for the pair, because the two have to describe one moment: a screen holding
         answers written against a table it did not fetch is pricing the wrong cards. */
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
      setSunkHolds(
        heldOnArrival(
          answer?.skus ?? ((table?.skus ?? []) as unknown as MergedSku[]),
          corpusAsDoc(held.corpus),
        ),
      )
      /* THE REVISION IS A REF AND NOT STATE, for the reason the whole guard is out of band: the
         dirty check is an identity comparison on `book`, and anything that re-renders on every
         landed write re-dirties the screen. */
      revision.current = held.revision
      savedBook.current = held.corpus
      failedBook.current = null
      setFailure(null)
      setUndo([])
      setReceipt(null)
      setArmed(false)
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
      setSunkHolds(new Set())
      setFailure(describeFailure(err))
    } finally {
      if (mine === loadWalk.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(picked, stamp)
  }, [picked, stamp, load])

  const loaded = useMemo(() => (work?.runs ?? []).map((row) => row.run), [work])
  const run = loaded.length === 1 ? (loaded[0] as string) : null

  /* WHERE THESE ROWS CAME FROM, AND WHAT MAY BE ASKED ABOUT THEM. Everything below reads
     `source.*` rather than `run` for the four capabilities that used to hang off that one
     sentinel — see `pricingSource.ts` for why a null run could not express a second door. */
  const source: PricingSource = useMemo(
    () =>
      stamp === null
        ? runSource(work, run, SECTIONS, { history: getPriceHistory, trends: getPriceTrends })
        : markdownSource(stamp, sheet, LIVE_SECTIONS, {
            history: markdownHistory,
            trends: markdownTrends,
          }),
    [stamp, sheet, work, run],
  )
  const doc = useMemo(() => corpusAsDoc(book, run), [book, run])

  /* THE CUT-OFF IN FORCE, IN THE ORDER `pipeline/corpus.py:policy_for` FOLDS IT: this run's own
     figure, then the store's, then what the server says the store's is.
     `work.threshold` IS IN THIS CHAIN AND MUST BE, which cost a test to learn. It is the server's
     own copy of the same policy — one fetch stale the moment a figure is typed, which is why the
     two written figures come first — but for a store that has never set one it is the ONLY true
     answer: `pipeline/corpus.py` defaults `policy.threshold` to `pricing.THRESHOLD`, so `emit`
     partitions an unwritten store at $0.40. A screen that offered its own default instead drew a
     split the pipeline would not write, which is the exact class of lie this file's "NO INVENTED
     FIGURES" rule exists to stop. The constant below it survives only for a payload that cannot
     be read at all. */
  const storeCut = writtenCut(book?.policy)
  const thisRunCut = runCut(book, run)
  const cut = thisRunCut ?? storeCut ?? work?.threshold ?? STORE_DEFAULT_CUT

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
        /* THE WRITE'S OWN REVISION BECOMES THE ONE WE HOLD. Without this every save after the
           first is stale against the file this screen just wrote, and the guard refuses the
           operator's own second keystroke. */
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
  const emitted =
    receipt?.ok === true || Boolean(detail?.manifest?.emitted) || detail?.phase === 'reconcile' || detail?.phase === 'done'

  /** Set the STORE-WIDE cut-off. BOTH KEYS, ALWAYS: `threshold` is the line the partition is
   *  drawn at and `sub_threshold` is what the half below it lists at, and the owner's ruling is
   *  that they are one figure. Writing one without the other is what let a cheap card price
   *  above a listable one, so this screen has no way to do it. */
  const setCut = useCallback((figure: string) => {
    setBook((current) =>
      current === null
        ? current
        : { ...current, policy: { ...current.policy, threshold: figure, sub_threshold: { [FLAT_KEY]: figure } } },
    )
  }, [])

  /** Set THIS RUN's own cut-off, or clear it back to the store's. `undefined` is the clear, and
   *  it clears both keys — a run that follows the store follows it on both halves of the one
   *  figure or on neither. */
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

  /* THE PRESS SEQUENCES RATHER THAN GATING ON `dirty`: `waiting` until the save loop is quiet. */
  useEffect(() => {
    if (ship !== 'waiting' || run === null) return
    if (book !== null && failedBook.current === book) {
      setShip('idle')
      setShipTrouble({
        code: 'answers_not_saved',
        message: 'Your answers could not be saved, so nothing was written. Fix the error above and the next keystroke will retry the save.',
      })
      return
    }
    if (dirty || saving || inFlight.current) return
    setShip('sending')
    void (async () => {
      try {
        const result = await runStep(run, 'emit', { splitThreshold: splitFiles })
        setReceipt({ ok: result.ok, console: result.console, files: result.files })
        setDetail((current) => (current === null ? current : { ...current, ...result.summary, files: result.files }))
        setShipTrouble(null)
        setArmed(false)
        const imports = (result.files ?? []).filter((file) => file.is_import)
        if (result.ok) {
          toast({
            kind: 'ok',
            title: `Import files written · ${imports.length} file${imports.length === 1 ? '' : 's'}`,
            body: 'Import them to Staged in TCGplayer, then reconcile on Runs.',
            action: { label: 'Files', onPress: () => setFilesOpen(true) },
          })
        } else {
          toast({
            kind: 'refusal',
            title: 'Emit refused',
            body: result.console.trim().split('\n').slice(-1)[0] ?? '',
            action: { label: 'Details', onPress: () => setFilesOpen(true) },
          })
        }
      } catch (err) {
        setShipTrouble(describeFailure(err))
      } finally {
        setShip('idle')
      }
    })()
  }, [ship, dirty, doc, book, run, saving, splitFiles])

  /** Write one answer, pushing the previous value — including its ABSENCE — onto the undo stack. */
  const write = useCallback(
    (sku: string, bucket: PricingSku['bucket'], value: unknown) => {
      const channel: 'price' | 'unknown' = targetOf(bucket) === 'no_market_data' ? 'unknown' : 'price'
      setBook((current) => (current === null ? current : setAnswer(current, sku, value, channel)))
      setUndo((stack) => [{ sku, before: book?.skus?.[sku], channel }, ...stack].slice(0, UNDO_DEPTH))
    },
    [book],
  )

  const boxesLoaded = useMemo(
    () =>
      [...new Set((work?.runs ?? []).map((row) => row.box).filter((box) => box !== null))].sort(
        (a, b) => (a as number) - (b as number),
      ),
    [work],
  )
  /* THE LIST, FROM WHICHEVER DOOR WAS ADDRESSED. `source.rows` is `work.skus` on a run and
     the projected survey on a lens — see `pricingSource.ts:asRow` for where the two shapes
     meet, and why the projection is documented there rather than asserted by the server. */
  const table = source.rows.length > 0 || stamp !== null ? source.rows : null
  const answers = useMemo(() => (doc?.overrides ?? {}) as Record<string, unknown>, [doc])
  const unpriced = useMemo(() => (doc?.no_market_data ?? {}) as Record<string, unknown>, [doc])
  /** Where the plan put each live listing. `offered` is what the rule proposed — the rows a
   *  `worklist.csv` would hold — and `refused` carries a code the strip can name. */
  const standingOf = useMemo(() => {
    const by = new Map<string, string>()
    for (const row of sheet?.skus ?? []) by.set(row.sku, row.standing)
    return by
  }, [sheet])

  /** What each live listing is asking, off the survey. The figure the manifest will judge a
   *  lowering against, so the row's own refusal is counted from it and never recomputed. */
  const askingOf = useMemo(() => {
    const by = new Map<string, string | null>()
    for (const row of sheet?.skus ?? []) by.set(row.sku, row.asking)
    return by
  }, [sheet])

  /* THE LIST IS PARTITIONED AT THE CUT-OFF THIS SCREEN IS SHOWING, not at the one the table
     was built with. The server draws the split at the figure stored when the table was fetched;
     the operator can type a new one, and the answer to "how many cards does that make cheap"
     has to be the list itself moving rather than a number that only comes true after a reload.
     `bucketAt` is `pipeline/pricing.py:is_listable` in the client's terms, so a cut-off equal to
     the stored one re-derives exactly the buckets the server sent. */
  const rows = useMemo(
    () =>
      !source.repartition
        ? (table ?? []).filter((sku) => lens === 'all' || standingOf.get(sku.sku) === lens)
        : (table ?? []).map((sku) => {
            const bucket = bucketAt(sku, cut)
            return bucket === sku.bucket ? sku : { ...sku, bucket }
          }),
    [table, cut, source.repartition, lens, standingOf],
  )

  /* READINESS READS THE PARTITION AS DRAWN, not the one the table arrived with: at a cut-off the
     operator has raised, rows that were listable are cheap now and `emit` will refuse over
     exactly those. Reading `work.skus` here would say the file is writable and then have the
     command refuse. */
  const owes = useMemo(() => owed(doc, subThresholdSkus(rows)), [doc, rows])


  /** THE PAIRS THIS SCREEN WOULD SEND — a typed price on a row the survey holds, and nothing
   *  else. Rows nobody touched are simply absent, which `read_back` reports as `dropped`:
   *  "left alone, which is what deleting a line means". */
  const pushable = useMemo(() => {
    const out: { sku: string; price: string }[] = []
    if (stamp === null) return out
    for (const row of rows) {
      const answer = answers[row.sku]
      if (typeof answer === 'string' && answer.trim() !== '') out.push({ sku: row.sku, price: answer.trim() })
    }
    return out
  }, [stamp, rows, answers])

  /* THE LENS'S PRESS, SEQUENCED THE WAY THE EMIT PRESS IS — and here it is not merely tidy:
     `reprice apply` reads `inventory/prices.json` off disk and refuses the whole file against a
     stale digest, so pressing with a save in flight would refuse for a write this screen was
     itself still making.

     AND IT RE-READS ON SUCCESS. `apply --write` writes the corpus from a subprocess, which
     `emit` never does, so the digest this screen holds is stale the moment the press lands and
     the operator's next keystroke would be refused `corpus_moved` — the screen fighting its own
     button. The route answers with the new digest and we adopt it. */
  useEffect(() => {
    if (push === 'idle' || stamp === null) return
    if (book !== null && failedBook.current === book) {
      setPush('idle')
      setShipTrouble({
        code: 'answers_not_saved',
        message: 'Your answers could not be saved, so nothing was sent. Fix the error above and the next keystroke will retry the save.',
      })
      return
    }
    if (dirty || saving || inFlight.current) return
    const write = push === 'writing'
    void (async () => {
      try {
        const result = await applyMarkdown(stamp, {
          edits: pushable,
          revision: revision.current,
          write,
        })
        setApplied(result)
        setWroteUpload(result.wrote)
        if (result.revision) revision.current = result.revision
        setShipTrouble(null)
        if (write && result.wrote) {
          toast({
            kind: 'ok',
            title: 'The upload file is written',
            body: 'Upload import.csv through TCGplayer’s My Pricing. Every row carries Add to Quantity 0.',
          })
        }
      } catch (err) {
        setShipTrouble(describeFailure(err))
      } finally {
        setPush('idle')
      }
    })()
  }, [push, stamp, pushable, dirty, saving, book])

  /* A NEW CHECK IS OWED THE MOMENT A PRICE MOVES. The write press only exists while a check
     stands, and a check that described a different set of edits is worse than none — it would
     offer a write over rows the operator has since changed. */
  useEffect(() => {
    setApplied(null)
    setWroteUpload(false)
  }, [pushable])


  /** The list as drawn: open rows, then the holds that were standing when the page opened,
   *  then the groups this run can add nothing for. */
  const sections = useMemo(
    () =>
      source.sections.map((section) => {
        const inSection = rows.filter((row) => row.bucket === section.bucket)
        const items: Drawn[] = []
        const holds: MergedSku[] = []
        const closed = new Map<string, MergedSku[]>()
        for (const sku of inSection) {
          const why = groupOf(sku)
          if (why !== null) {
            const group = closed.get(why)
            if (group === undefined) closed.set(why, [sku])
            else group.push(sku)
          } else if (sunkHolds.has(sku.sku)) holds.push(sku)
          else items.push({ head: null, sku })
        }
        if (holds.length > 0) {
          items.push({ head: HELD_HEAD, count: holds.length })
          for (const sku of holds) items.push({ head: null, sku })
        }
        for (const [why, group] of closed) {
          items.push({ head: why, count: group.length })
          for (const sku of group) items.push({ head: null, sku })
        }
        // Every row sharing one condition and one set says nothing per row; the meta line dims those two.
        const uniform =
          inSection.length > 1 &&
          new Set(inSection.map((sku) => sku.condition)).size === 1 &&
          new Set(inSection.map((sku) => sku.set_name)).size === 1
        // The DIRECT column is spent only in a section where at least one row carries a figure for it.
        const direct = inSection.some((sku) => sku.snap.direct_low !== null)
        return { ...section, total: inSection.length, items, uniform, direct }
      }).filter((section) => section.total > 0),
    [rows, sunkHolds, source.sections],
  )

  const order = useMemo(
    () => sections.flatMap((section) => section.items.flatMap((item) => (item.head === null ? [item.sku.sku] : []))),
    [sections],
  )

  const trendTally = useMemo(() => {
    let read = 0
    let refused = 0
    for (const value of Object.values(trends)) {
      if (value.kind === 'read') read += 1
      else if (value.kind === 'refused') refused += 1
    }
    return { read, refused }
  }, [trends])

  const answerFor = useCallback(
    (sku: PricingSku): unknown => (targetOf(sku.bucket) === 'overrides' ? answers[sku.sku] : unpriced[sku.sku]),
    [answers, unpriced],
  )

  const held = useMemo(() => rows.filter((sku) => isWithheld(answers[sku.sku])), [rows, answers])

  /** The header's progress figures: answered = typed or held, over the rows still open.
   *  `outRows`/`outCopies` are what a write would actually put in the file — every open row
   *  that is not held, and the copies behind them.
   *
   *  `rule` COUNTS TWO DIFFERENT THINGS AND `cheap` SEPARATES THEM. A row with no typed answer
   *  goes out at the rule's figure — unless it is sub-threshold, in which case
   *  `pipeline/join.py:prices_for` writes the cheap-card policy instead. Saying "on the rule"
   *  over both was false for every cheap row, so `cheap` is carried beside it and `rule`
   *  stays the total the meter is drawn from. */
  const progress = useMemo(() => {
    let total = 0
    let typed = 0
    let holds = 0
    let cheap = 0
    let closed = 0
    let outRows = 0
    let outCopies = 0
    for (const row of rows) {
      if (row.at_cap) {
        closed += 1
        continue
      }
      total += 1
      const standing = answerFor(row)
      if (isWithheld(standing)) {
        holds += 1
        continue
      }
      if (typeof standing === 'string') typed += 1
      else if (row.bucket === 'sub_threshold') cheap += 1
      outRows += 1
      outCopies += row.add_to_quantity
    }
    return {
      total,
      typed,
      held: holds,
      cheap,
      answered: typed + holds,
      rule: total - typed - holds,
      closed,
      outRows,
      outCopies,
    }
  }, [rows, answerFor])

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
      const text = raw.trim()
      write(sku.sku, sku.bucket, text === '' ? undefined : text)
      touched.current.delete(sku.sku)
    },
    [write],
  )

  const snap = useCallback((sku: PricingSku, field: keyof PricingSku['snap']) => {
    const value = sku.snap[field]
    const input = inputs.current.get(sku.sku)
    if (value === null) {
      const says = SNAPS.find((row) => row.field === field)?.says ?? field.replace(/_/g, ' ')
      setNote({ sku: sku.sku, text: `No ${says} price on this row` })
      return
    }
    if (input) {
      input.value = value
      flash(input)
    }
    touched.current.add(sku.sku)
    setNote(null)
  }, [])

  /** WHAT ONE CHEAP CARD IS ACTUALLY WRITTEN AT, as digits. `pipeline/join.py:prices_for`
   *  gives every sub-threshold row `sub_threshold.resolve()` — the policy figure — and never
   *  the rule's own per-SKU figure, which the server has already floored. Drawing the rule's
   *  figure in the column headed LISTS AT made the deck and the list state two different
   *  prices for the same card. `doc` has this run's override already folded over the store's,
   *  so this is one answer for the whole screen. Nothing written falls back to the offered
   *  default, which is the figure the deck is showing and the caption is naming. */
  const cheapDigits = useCallback((): string => cut, [cut])

  /** What a row would list at under the standing rule, or `''` where this screen has no
   *  figure for it. THE CLIENT PERFORMS NO ARITHMETIC ON MONEY: the three presets ship a
   *  precomputed column each, so a preset the document currently names has an honest per-SKU
   *  figure and is drawn.
   *
   *  A CUSTOM RULE DRAWS NOTHING, AND THAT IS THE HONEST ANSWER RATHER THAN A MISSING FEATURE.
   *  `rule_price` was computed by the LAST JOIN and frozen into `pricing.json` (D54), and
   *  NOTHING ON THE WIRE SAYS WHICH RULE THAT JOIN RAN UNDER — `PricingWorklist` carries the
   *  rows, the roster and two run-wide figures, and no per-run rule among them. This read a
   *  `work.defaults` that no route has ever sent, so the comparison it was making always came
   *  out false; the blank it produced was right, and it is written as the rule now instead of
   *  reached by accident. Drawing `rule_price` here would put the previous rule's price under
   *  a label naming this one, which is the D54 staleness the presets exist to avoid. */
  const ruleFigure = useCallback(
    (sku: PricingSku): string => {
      const match = PRESETS.find((p) => p.rule === doc?.rule && p.basis === doc?.basis)
      if (match !== undefined) return sku.presets[match.key] ?? ''
      /* No rule written at all: the join's own figure is the only rule there has been. */
      if (typeof doc?.rule !== 'string') return sku.rule_price ?? ''
      return ''
    },
    [doc],
  )

  /** The suggestion a row opens carrying: the cheap-card answer on a cheap row, the standing
   *  rule's own per-SKU figure everywhere else. */
  const suggestionFor = useCallback(
    (sku: PricingSku): string => (sku.bucket === 'sub_threshold' ? cheapDigits() : ruleFigure(sku)),
    [cheapDigits, ruleFigure],
  )

  /** A preset writes `rule`/`basis` and NO override; it refills only the rows the operator has
   *  not set, and lights each one it moved. */
  const applyPreset = useCallback(
    (key: string) => {
      if (table === null) return
      const chosen = PRESETS.find((row) => row.key === key)
      if (chosen === undefined) return
      const missing = rows.filter((row) => row.presets[key] === null)
      setBook((current) =>
        current === null ? current : { ...current, policy: { ...current.policy, rule: chosen.rule, basis: chosen.basis } },
      )
      for (const row of rows) {
        const input = inputs.current.get(row.sku)
        if (input && answerFor(row) === undefined) {
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
          : {
              sku: '',
              text:
                `${rows.length - missing.length} of ${rows.length} rows priced. ` +
                `${missing.length} have no price in that column and were left alone: ` +
                missing.slice(0, 6).map((row) => row.name).join(', ') +
                (missing.length > 6 ? '…' : ''),
            },
      )
    },
    [rows, table, answerFor],
  )

  /** THE CUSTOM RULE, WRITTEN THE WAY A PRESET IS WRITTEN: `policy.rule` and `policy.basis`
   *  on the corpus, no per-SKU override, and the untyped fields walked to whatever figure the
   *  screen honestly has for the new rule. A bad percentage writes NOTHING and says why —
   *  the same shape as a snap onto an empty column. */
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
      setBook((current) =>
        current === null ? current : { ...current, policy: { ...current.policy, rule, basis: draft.basis } },
      )
      /* THE UNTYPED FIELDS GO EMPTY, AND THERE IS NO CASE WHERE THEY DO NOT. `rule_price` is
         the figure the LAST JOIN computed and froze (D54), and nothing on this wire says which
         rule that join ran under — see `ruleFigure` above — so a per-SKU figure drawn under a
         custom rule would be the previous rule's price wearing this one's label. Emit prices
         these rows; the toast below says so. */
      let onRule = 0
      for (const row of rows) {
        if (row.bucket === 'sub_threshold') continue
        if (answerFor(row) !== undefined) continue
        onRule += 1
        const input = inputs.current.get(row.sku)
        if (!input || input.value === '') continue
        input.value = ''
        flash(input)
      }
      setNote(null)
      toast({
        kind: 'receipt',
        title: `Rule set · ${customShort(draft)} of ${BASIS_LABEL[draft.basis]}`,
        body:
          `${onRule} row${onRule === 1 ? '' : 's'} you have not set go out at this rule.` +
          ' Emit prices them — this screen has no per-row figure until the run is joined under it.',
        icon: 'tag',
        ttlMs: 9000,
      })
    },
    [doc, rows, answerFor],
  )

  const undoLast = useCallback(() => {
    const [top, ...rest] = undo
    if (top === undefined) return
    setBook((current) => {
      if (current === null) return current
      const skus = { ...(current.skus ?? {}) }
      if (top.before === undefined) delete skus[top.sku]
      else skus[top.sku] = top.before
      return { ...current, skus }
    })
    setUndo(rest)
    // The field is uncontrolled, so its digits are corrected here the way Escape and a preset
    // already correct them: the restored answer, or the rule's suggestion where there was none.
    const row = rows.find((one) => one.sku === top.sku)
    const input = inputs.current.get(top.sku)
    if (row !== undefined && input) {
      const before = top.before?.value
      input.value = typeof before === 'string' ? before : suggestionFor(row)
      flash(input)
    }
    touched.current.delete(top.sku)
  }, [undo, rows, suggestionFor])
  /* A toast's undo fires later than the closure it was made in; the ref always holds the latest. */
  const undoRef = useRef(undoLast)
  undoRef.current = undoLast

  /* THE CHEAP ROWS FOLLOW THE ANSWER. The price fields are uncontrolled, so a policy pressed
     on the deck has to be walked into them — without this the column keeps whatever figure it
     mounted with and the deck and the list disagree again the moment the answer changes. Only
     rows nobody has typed into and nobody has answered are moved, and on the first render the
     figure is already right, so nothing flashes on arrival. */
  const cheapNow = cheapDigits()
  useEffect(() => {
    for (const row of rows) {
      if (row.bucket !== 'sub_threshold') continue
      if (touched.current.has(row.sku)) continue
      const standing = answerFor(row)
      if (typeof standing === 'string' || isWithheld(standing)) continue
      const input = inputs.current.get(row.sku)
      if (!input || input.value === cheapNow) continue
      input.value = cheapNow
      flash(input)
    }
  }, [cheapNow, rows, answerFor])

  const toggleHold = useCallback(
    (sku: PricingSku) => {
      if (isWithheld(answers[sku.sku])) {
        write(sku.sku, sku.bucket, undefined)
        setHoldFor(null)
        toast({
          kind: 'receipt',
          title: `Released ${sku.name}`,
          body: 'Back on the rule until you set a price.',
          ttlMs: 8000,
          action: { label: 'Undo', kbd: 'U', onPress: () => undoRef.current() },
        })
        return
      }
      setHoldFor(sku.sku)
    },
    [answers, write],
  )

  const cancelHold = useCallback((sku: PricingSku) => {
    setHoldFor(null)
    inputs.current.get(sku.sku)?.focus()
  }, [])

  const setHold = useCallback(
    (sku: PricingSku, reason: WithholdReason, watch: string, text: string) => {
      const record: WithheldRecord = { withheld: reason }
      if (watch.trim() !== '') record.watch_above = watch.trim()
      if (text.trim() !== '') record.note = text.trim()
      write(sku.sku, 'listable', record)
      if (sku.bucket === 'no_market_data') write(sku.sku, sku.bucket, 'unlisted')
      setHoldFor(null)
      toast({
        kind: 'receipt',
        title: `Held ${sku.name}`,
        body: `${WITHHOLD_LABELS[reason]}${watch.trim() !== '' ? ` · tell me above $${watch.trim()}` : ''}`,
        ttlMs: 8000,
        action: { label: 'Undo', kbd: 'U', onPress: () => undoRef.current() },
      })
      inputs.current.get(sku.sku)?.focus()
    },
    [write],
  )

  /** Take the reading for one SKU, and ask nothing if this session already has it. */
  const readHistory = useCallback(
    (sku: PricingSku, force = false) => {
      const ask = source.history
      if (ask === null) return
      if (!force && history[sku.sku] !== undefined) return
      setHistory((current) => ({ ...current, [sku.sku]: { kind: 'reading' } }))
      ask(sku.sku)
        .then((payload) => setHistory((current) => ({ ...current, [sku.sku]: { kind: 'read', payload } })))
        .catch((error) =>
          setHistory((current) => ({ ...current, [sku.sku]: { kind: 'refused', why: describeFailure(error).message } })),
        )
    },
    [history, source.history],
  )

  /** Read the shape of every row still waiting on an answer — one press, chunked, sequential. */
  const loadTrends = useCallback(() => {
    const ask = source.trends
    const at = source.id
    if (ask === null || at === null) return
    /* SCOPED TO THE ROWS ON SCREEN, WHICH ON A LENS IS THE WHOLE POINT OF THE FILTER. The run
       route measured 46 SKUs at ~34s of courtesy delay; a survey of a real live inventory is
       ~441 rows, about five and a half minutes at a free public mirror. D62's rule is that
       this is a PRESS, and a walk that big makes the press meaningless rather than merely
       slow — so the operator narrows first and asks about what they narrowed to. */
    const open = rows.filter((row) => !row.at_cap).map((row) => row.sku)
    const walk = (trendWalk.current += 1)
    setTrends(Object.fromEntries(open.map((sku) => [sku, { kind: 'reading' } as TrendRead])))
    setTrendRun({ run: at, total: open.length, done: 0, skipped: rows.length - open.length, spans: null, reading: true })

    const chunks: string[][] = []
    for (let at = 0; at < open.length; at += TREND_CHUNK) chunks.push(open.slice(at, at + TREND_CHUNK))

    const read = async () => {
      for (const chunk of chunks) {
        if (trendWalk.current !== walk) return
        try {
          const payload = await ask(chunk)
          if (trendWalk.current !== walk) return
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk) {
              const found = payload.skus[sku]
              const why = payload.refused[sku]
              next[sku] =
                found !== undefined
                  ? { kind: 'read', ranges: found.ranges }
                  : { kind: 'refused', why: why ?? 'the batch answered without this SKU and without a reason.' }
            }
            return next
          })
          setTrendRun((current) =>
            current === null || current.run !== at
              ? current
              : {
                  ...current,
                  done: current.done + chunk.length,
                  spans:
                    current.spans ??
                    Object.values(payload.skus).find((entry) => entry.ranges.length > 0)?.ranges ??
                    null,
                },
          )
        } catch (error) {
          if (trendWalk.current !== walk) return
          const why = describeFailure(error).message
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk) next[sku] = { kind: 'refused', why }
            return next
          })
          setTrendRun((current) =>
            current === null || current.run !== at ? current : { ...current, done: current.done + chunk.length },
          )
        }
      }
      if (trendWalk.current === walk) {
        setTrendRun((current) => (current === null || current.run !== at ? current : { ...current, reading: false }))
      }
    }
    void read()
  }, [rows, source.trends, source.id])

  /* Which row the pointer is over, and which one a held key latched. Refs: nothing draws them. */
  const hovered = useRef<string | null>(null)
  const heldSku = useRef<string | null>(null)

  const focusedSku = useCallback(() => {
    for (const [sku, node] of inputs.current) if (node === document.activeElement) return sku
    return null
  }, [])

  const isPriceField = useCallback((target: EventTarget | null) => {
    for (const node of inputs.current.values()) if (node === target) return true
    return false
  }, [])

  /** Pin the drawer to one SKU. Closes the photograph: one drawer, one card. */
  const pinHistory = useCallback(
    (sku: PricingSku) => {
      if (source.history === null) return
      heldSku.current = null
      setPeek(null)
      setPhotoFor(null)
      setPinned(sku.sku)
      readHistory(sku)
    },
    [readHistory, source.history],
  )

  /** Publish the ship bar's measured height as `--pricing-ship-h` (D85); the drawer reads it. */
  const shipObserver = useRef<ResizeObserver | null>(null)
  const shipHost = useRef<HTMLElement | null>(null)
  const measureShip = useCallback((node: HTMLElement | null) => {
    shipObserver.current?.disconnect()
    shipObserver.current = null
    if (node === null) {
      shipHost.current?.style.removeProperty('--pricing-ship-h')
      document.documentElement.style.removeProperty('--pricing-ship-h')
      shipHost.current = null
      return
    }
    const host = node.closest<HTMLElement>('.pricing')
    if (host === null) return
    shipHost.current = host
    const publish = () => {
      host.style.setProperty('--pricing-ship-h', `${node.offsetHeight}px`)
      // The drawer is rendered on <body> (a filled page animation traps `fixed` inside <main>),
      // so the same figure is mirrored on :root for it.
      document.documentElement.style.setProperty('--pricing-ship-h', `${node.offsetHeight}px`)
    }
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(node)
    shipObserver.current = observer
  }, [])

  const unpin = useCallback(() => {
    heldSku.current = null
    setPeek(null)
    setPinned(null)
  }, [])

  const closeDrawer = useCallback(() => {
    unpin()
    setPhotoFor(null)
  }, [unpin])

  const openPhoto = useCallback(
    (sku: PricingSku) => {
      unpin()
      setPhotoFor((current) => (current !== null && current.sku === sku.sku ? null : { sku: sku.sku, at: 0 }))
    },
    [unpin],
  )

  /* HOLD `t`, SEE THE ROW UNDER THE POINTER, LET GO AND IT IS GONE (D62). On `window`, not on
     the field; `blur` releases it too. */
  useEffect(() => {
    const release = () => {
      if (heldSku.current === null) return
      heldSku.current = null
      setPeek(null)
    }
    const down = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 't' || event.repeat) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (heldSku.current !== null) return
      /* AND WHILE THE MARKDOWN SHEET IS OPEN (D105). This screen's unmodified keys enumerate
         the open surfaces they yield to BY NAME, and the sheet is a new one: a `t` typed into
         its "Cut, percent" field would otherwise pull a price history for whichever row the
         pointer happened to be over, behind the scrim. */
      if (holdFor !== null || mdOpen) return
      if (isEditableTarget(event.target) && !isPriceField(event.target)) return
      const aim = hovered.current ?? focusedSku()
      const row = aim === null ? undefined : rows.find((one) => one.sku === aim)
      if (row === undefined) return
      heldSku.current = row.sku
      setPeek(row.sku)
      readHistory(row)
    }
    const up = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 't') release()
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', release)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', release)
    }
  }, [focusedSku, holdFor, mdOpen, isPriceField, readHistory, rows])

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
        event.currentTarget.value = typeof standing === 'string' ? standing : suggestionFor(sku)
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
        openPhoto(sku)
        return
      }
      // `t` is the peek, handled on `window`; here it is only swallowed so it never reaches
      // `onBeforeInput` and blanks a suggestion on its way to being refused.
      if (lower === 't') {
        event.preventDefault()
        return
      }
      if (lower === 'n' && sku.snap.now !== null) {
        event.preventDefault()
        snap(sku, 'now')
      }
    },
    [answerFor, commit, move, snap, suggestionFor, toggleHold, undoLast, openPhoto],
  )

  const photoSku = useMemo(() => (photoFor === null ? null : rows.find((row) => row.sku === photoFor.sku) ?? null), [photoFor, rows])
  const photoAt = useMemo(
    () => (photoSku === null || photoFor === null ? null : photoSku.positions[photoFor.at % photoSku.positions.length] ?? null),
    [photoSku, photoFor],
  )
  const historySku = useMemo(() => (historyFor === null ? null : rows.find((row) => row.sku === historyFor) ?? null), [historyFor, rows])

  const scopeName = useMemo(() => {
    /* THE LENS NAMES THE EXPORT IT WAS READ FROM, because "Box 3 · RB Epics" is a run's answer
       to "what am I looking at" and a markdown's answer is a moment and a file. */
    if (stamp !== null) {
      const when = sheet?.at ? new Date(sheet.at) : null
      return when === null || Number.isNaN(when.getTime())
        ? 'Live listings'
        : `Live listings · read ${when.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
    }
    if (run === null) return null
    const row = detail !== null && detail.run === run ? detail : runs.find((r) => r.run === run)
    return row === undefined ? null : runBoxLabel(row)
  }, [stamp, sheet, run, detail, runs])

  const closeMarkdown = useCallback(() => setMdOpen(false), [])
  /** Take the digest a subprocess write produced, so the next keystroke is not refused for it. */
  const adoptRevision = useCallback((next: string) => {
    revision.current = next
  }, [])
  const closePicker = useCallback(() => setRunsOpen(false), [])
  useDismiss(pickerRef, runsOpen, closePicker)

  /* The popover is a dialog: focus moves into it on open and back to the Runs button on close. */
  const runsWasOpen = useRef(false)
  useEffect(() => {
    const anchor = pickerRef.current
    if (runsOpen) {
      runsWasOpen.current = true
      anchor?.querySelector<HTMLButtonElement>('.pricing-run')?.focus()
    } else if (runsWasOpen.current) {
      runsWasOpen.current = false
      anchor?.querySelector<HTMLButtonElement>('button[aria-haspopup="dialog"]')?.focus()
    }
  }, [runsOpen])

  useEffect(() => {
    if (!filesOpen) return
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFilesOpen(false)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [filesOpen])

  /* Escape closes the pinned drawer (history or photograph) the way it closes every other
     surface here. The price field keeps its own Escape (revert and blur), and a hold panel,
     the files dialog or the runs popover answers first while it is open. */
  useEffect(() => {
    if (pinned === null && photoFor === null) return
    const key = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || holdFor !== null || filesOpen || runsOpen || mdOpen || isPriceField(event.target)) return
      closeDrawer()
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [pinned, photoFor, holdFor, filesOpen, runsOpen, mdOpen, isPriceField, closeDrawer])

  /* R reloads, as it does on Review — outside a field, outside a panel, and never on a phone. */
  useEffect(() => {
    if (phone) return
    const key = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'r' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return
      if (holdFor !== null || filesOpen || runsOpen || mdOpen || loading) return
      if (isEditableTarget(event.target)) return
      event.preventDefault()
      void load(picked, stamp)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [phone, holdFor, filesOpen, runsOpen, mdOpen, loading, load, picked, stamp])

  const activePreset = PRESETS.find((p) => p.rule === doc?.rule && p.basis === doc?.basis) ?? null
  /* NO INVENTED FIGURES. The floor is the store's own and a screen that cannot read it says
     nothing about it rather than printing a plausible literal — this panel drew "$0.40" beside
     an answer of $0.24 and read as a rule when it was a fallback. The CUT-OFF is not read here
     at all: `cut`, above, is the live one, and `work.threshold` is the server's copy of the same
     policy from whenever the table was fetched. */
  const floor = work?.floor ?? null

  /* THE STANDING RULE READ BACK. A custom rule survives a reload because it is written where
     a preset's is — `policy.rule` / `policy.basis` on the corpus — so this is the whole of the
     round trip: the document says `undercut:7` over `low`, no preset owns that pair, and the
     strip lands on Custom with the fields filled from it. */
  const standingCustom = activePreset === null ? parseCustomRule(doc?.rule, doc?.basis) : null
  const customOn = pressedCustom || standingCustom !== null
  const ruleSegment = customOn ? CUSTOM_KEY : (activePreset?.key ?? '')

  /* The draft follows the document when the document moves under it — a reload, a run switch,
     an answer adopted from elsewhere — and never while a hand is mid-percentage: the seed is
     keyed on the rule itself, so a value already seeded is left alone. */
  const standingKey = standingCustom === null ? null : `${standingCustom.kind}:${standingCustom.pct}:${standingCustom.basis}`
  useEffect(() => {
    if (standingKey === null || customSeed.current === standingKey) return
    customSeed.current = standingKey
    const [kind, pct, basis] = standingKey.split(':')
    setCustomDraft({ kind: kind as RuleKind, pct: pct as string, basis: basis as RuleBasis })
    setCustomBad(null)
  }, [standingKey])

  /** Pressing a segment. A preset is an answer the moment it is pressed; Custom opens the
   *  fields and writes nothing until a percentage is in them, because `undercut:` is not a
   *  rule and a rule of 0% is a different preset. */
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
      window.setTimeout(() => customPct.current?.focus(), 0)
    },
    [applyPreset],
  )

  /** What the strip says while Custom is chosen: the refusal if there is one, the rule's own
   *  sentence once it is real, and the invitation before either. */
  const customLine = customBad ?? (standingCustom === null ? null : customSays(standingCustom, floor))
  const subCount = subThresholdSkus(rows).length
  const roster = work?.roster ?? []

  /* WHOSE CUT-OFF IS IN FORCE. `cut` above is the figure; this is where it came from, which is
     the only other thing a reader needs and the thing the section header names. */
  const cutFrom: 'run' | 'store' | 'default' =
    thisRunCut !== undefined ? 'run' : storeCut !== null ? 'store' : 'default'
  const stranded = strandedFlat(doc, cut)

  /* WHEN THE FIGURES ON THIS SCREEN WERE READ. Every `snap` price and every `listing.live`
     count was frozen into `pricing.json` by the join, so the join's own write time IS their
     age. (The moment TCGplayer was last asked — `listings.at` in the store — is not on the
     wire; this is the nearest honest stamp and it is never later than that one.) */
  const readAtOf = source.readAtOf
  const readAt = useMemo(() => {
    const stamps = Object.values(work?.written_at ?? {}).filter((n): n is number => typeof n === 'number')
    return stamps.length === 0 ? null : Math.max(...stamps)
  }, [work])
  const readAge = ageWords(readAt)

  /** Bring the deck into view and light it — the account is at the top, the press is at the
   *  bottom, and a person who reads "Not yet" on the bar needs the sentence that says why. */
  const showDeck = useCallback(() => {
    const node = deckRef.current
    if (node === null) return
    node.scrollIntoView({ block: 'start', behavior: 'smooth' })
    node.classList.remove('is-flash')
    void node.offsetWidth
    node.classList.add('is-flash')
    window.setTimeout(() => node.classList.remove('is-flash'), 1200)
  }, [])

  /* WHAT THE UNTYPED ROWS GO OUT AT, IN ONE PHRASE, and it is TWO figures rather than one.
     A row nobody typed into goes out at the rule's figure — unless it is sub-threshold, where
     the cheap-card answer is what `prices_for` writes. Every place on this screen that used to
     say "N on the rule" over both now says this, so the lede, the ship bar and the deck cannot
     state different prices for the same cards. */
  const cheapMoney = `$${cheapNow}`
  const ruleRows = Math.max(0, progress.rule - progress.cheap)
  const standingSays = [
    ruleRows > 0 ? `${ruleRows} on the rule` : null,
    progress.cheap > 0 ? `${progress.cheap} cheap at ${cheapMoney}` : null,
  ]
    .filter((part): part is string => part !== null)
    .join(' · ')

  /* The progress figure lives in the lede: "decided" counts what a hand typed or held, and the
     rows on a standing answer are named beside it so the ship bar's verdict and this line agree. */
  const pct = progress.total === 0 ? 0 : Math.round((progress.answered / progress.total) * 100)
  const progressLine =
    progress.total === 0 ? null : (
      <span
        className="pricing-scope-progress"
        title={`${progress.typed} typed · ${progress.held} held · ${ruleRows} on the rule · ${progress.cheap} cheap at ${cheapMoney}`}
      >
        {progress.answered} of {progress.total} decided
        {standingSays === '' ? '' : ` · ${standingSays}`}
        {progress.closed > 0 ? ` · ${progress.closed} nothing to add` : ''}
      </span>
    )

  const scopeLine =
    source.kind === 'markdown' ? (
      /* THE LENS SAYS WHAT IT IS AND WHEN IT WAS READ. `loaded.length` is a run count and is
         zero here forever, which would leave a screen full of live listings saying "Nothing
         loaded." — the sentence being false is the whole reason this branch is first. */
      <>
        {scopeName === null ? null : <span>{scopeName}</span>}
        <span className="pricing-scope-run bn-mono">{stamp}</span>
        <span>
          {rows.length} live SKU{rows.length === 1 ? '' : 's'}
        </span>
        {pushable.length === 0 ? null : (
          <span>
            {pushable.length} price{pushable.length === 1 ? '' : 's'} typed
          </span>
        )}
      </>
    ) : loaded.length === 0 ? (
      <span>Nothing loaded.</span>
    ) : run !== null ? (
      <>
        {scopeName === null ? null : <span>{scopeName}</span>}
        <span className="pricing-scope-run bn-mono">{run}</span>
        <span>{rows.length} SKUs</span>
        {progressLine}
      </>
    ) : (
      <>
        <span>
          {boxesLoaded.length || loaded.length} {boxesLoaded.length === 1 ? 'box' : 'boxes'}
        </span>
        <span>{loaded.length} runs</span>
        <span>{rows.length} SKUs</span>
        {picked.size === 0 ? <span>everything unpriced</span> : null}
        {progressLine}
      </>
    )

  const chrome = (
    <header className="bn-head pricing-head">
      <div className="bn-head-text">
        <span className="bn-eyebrow">Workflow · Price</span>
        <h1 className="bn-title pricing-title">
          <Icon name="tag" size={22} />
          Pricing
        </h1>
        <p className="bn-lede pricing-scope">{scopeLine}</p>
        {progress.total === 0 ? null : (
          <div
            className="bn-progress pricing-head-progress"
            role="progressbar"
            aria-label="Progress through the worklist"
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={progress.answered}
          >
            <span style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
      <div className="bn-head-actions">
        <span
          className={`bn-pill pricing-save ${saving ? 'bn-pill-accent' : dirty ? 'bn-pill-warn' : 'bn-pill-ok'}`}
          aria-live="polite"
          title="Every answer is written to inventory/prices.json as you go"
        >
          <Icon name={saving ? 'refresh' : dirty ? 'clock' : 'check'} size={12} />
          {saving ? 'Saving…' : dirty ? 'Unsaved' : 'Saved'}
        </span>
        {/* THE DOOR, WHERE THE WORK IS (D105). It was a header button on `#/runs`; the owner's
            objection was that a markdown is about inventory ALREADY LISTED and this is the
            screen that decides prices — D100 placed it beside the store-wide reconcile on
            kinship of implementation (both read one export), which is not kinship of work.
            Its own step-2 press writes `#/pricing?markdown=<stamp>`, which now lands on the
            screen the operator is standing on rather than navigating anywhere: `App.tsx` keys
            the view on the hash MINUS its query. */}
        <Button icon="trendDown" onClick={() => setMdOpen(true)} aria-label="Mark down stale listings">
          <span className="pricing-hide-sm">Mark down stale</span>
          <span className="pricing-only-sm">Mark down</span>
        </Button>
        <div className="pricing-runs-anchor" ref={pickerRef}>
          <Button
            icon="layers"
            iconRight="chevronDown"
            aria-expanded={runsOpen}
            aria-haspopup="dialog"
            onClick={() => setRunsOpen((open) => !open)}
            disabled={roster.length === 0}
          >
            Runs
            {picked.size > 0 ? <span className="bn-pill bn-pill-accent pricing-runs-badge">{picked.size}</span> : null}
          </Button>
          {runsOpen && roster.length > 0 ? (
            <>
              {/* On a phone the picker is a bottom sheet; the scrim sits inside the anchor so the
                  outside-press dismissal does not fire on it, and its own press closes. */}
              {phone ? <div className="bn-scrim pricing-runs-scrim" onClick={closePicker} /> : null}
              <div className="pricing-runs-pop bn-menu" role="dialog" aria-label="Which runs to price">
                <PickRuns runs={roster} picked={picked} onToggle={toggleRun} onClear={clearPicked} />
              </div>
            </>
          ) : null}
        </div>
        <Button
          variant="ghost"
          icon="refresh"
          iconOnly
          kbd={phone ? undefined : 'R'}
          className="pricing-reload"
          onClick={() => void load(picked, stamp)}
          disabled={loading}
          busy={loading}
          title={phone ? 'Reload' : 'Reload · R'}
        >
          Reload
        </Button>
      </div>
    </header>
  )

  /* THE SHEET, MOUNTED BESIDE THE CHROME SO IT EXISTS IN EVERY STATE OF THIS SCREEN — including
     the early-return empty states, which is where an operator with no joined runs will look for
     it. It carries this screen's corpus digest and hands back the one its write produced: two
     writers of `inventory/prices.json` now share a tab, and only one of them had the guard. */
  const markdownSheet = (
    <Markdown
      open={mdOpen}
      onClose={closeMarkdown}
      revision={revision.current || undefined}
      onCorpusWritten={adoptRevision}
    />
  )

  /* THE EMPTY STATES: the fetch failed, nothing is joined, the narrowing matched nothing, or
     every open run has been answered — and, on a lens, an export TCGplayer returned nothing
     live in. THE GUARD IS ABOUT ROWS AND NOT ABOUT `work`, because a markdown has no `runs`
     and would otherwise take the runs mode's "nothing joined" branch forever. */
  if (source.rows.length === 0) {
    const joined = work?.roster ?? []
    return (
      <main className="pricing bn-page">
        {chrome}
        {markdownSheet}
        {loading ? (
          <SkeletonRows count={6} />
        ) : failure !== null ? (
          /* The server did not answer: that is the whole state, and no claim about the runs is
             drawn beside it — "no joined runs" would be a false sentence under this one. */
          <EmptyState
            icon="alert"
            title={failure.message}
            body={
              <>
                Nothing on this screen can be shown until the capture server answers.
                {failure.code ? <span className="pricing-machine pricing-empty-code">{failure.code}</span> : null}
              </>
            }
            actions={
              <Button icon="refresh" onClick={() => void load(picked, stamp)}>
                Try again
              </Button>
            }
          />
        ) : source.kind === 'markdown' ? (
          /* THE LENS'S OWN EMPTY STATE, and the empty state is exactly the kind of thing that
             IS about which door it was: "no joined runs yet" is a false sentence over a
             markdown, and "no live listings" is a false one over a run picker. */
          <EmptyState
            icon="tag"
            title="Nothing live in that export"
            body="This markdown surveyed no live listings — every row TCGplayer returned was sold out. Fetch a fresh export and read it again."
            actions={
              /* THE DOOR IS HERE NOW (D105). This sent the operator to `#/runs` for a sheet
                 that is no longer on it — a screen naming a destination that cannot perform
                 the act it names, which is the defect D101 is about. */
              <Button variant="primary" icon="trendDown" onClick={() => setMdOpen(true)}>
                Read a fresh export
              </Button>
            }
          />
        ) : joined.length === 0 ? (
          <EmptyState
            icon="play"
            title="No joined runs yet"
            body="Identify and join a box on Runs first. Pricing opens on whatever that join leaves to answer."
            actions={
              <Button variant="primary" icon="play" onClick={() => (window.location.hash = '#/runs')}>
                Go to Runs
              </Button>
            }
          />
        ) : picked.size > 0 ? (
          <EmptyState
            icon="filter"
            title="Nothing to price in those runs"
            body="Every card in the runs you picked already has an answer."
            actions={
              <Button variant="primary" icon="x" onClick={clearPicked}>
                Show everything unpriced
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon="check"
            title="Everything is priced"
            body="Every joined run has been priced and emitted. Pick a run to look at it again, or join a box on Runs."
            actions={
              <>
                <Button variant="primary" icon="layers" onClick={() => setRunsOpen(true)}>
                  Pick a run
                </Button>
                <Button icon="play" onClick={() => (window.location.hash = '#/runs')}>
                  Runs
                </Button>
              </>
            }
          />
        )}
      </main>
    )
  }

  return (
    <main className="pricing bn-page" data-drawer={historySku !== null || (photoSku !== null && photoFor !== null) ? 'open' : undefined}>
      {chrome}
      {markdownSheet}

      <div className="pricing-body" data-trends={trendRun === null ? 'off' : 'on'}>
        {(work?.skipped ?? []).length === 0 ? null : (
          <Notice tone="warn" title="A run could not be read and is left out of this list" className="pricing-notice">
            {(work?.skipped ?? []).map((row) => (
              <span className="pricing-machine" key={row.run}>
                {row.run} · {row.code}
              </span>
            ))}
          </Notice>
        )}

        {failure === null ? null : (
          <Notice tone="danger" title={failure.message} code={failure.code} className="pricing-notice">
            {/* A CONFLICT IS THE ONE REFUSAL HERE WITH SOMEWHERE TO GO. The file moved under this
                screen — another tab, or an edit on disk — and the write was refused rather than
                allowed to revert it. Re-reading is the way back, and it costs whatever is typed
                and unsaved, so the button says that rather than presenting a reload as free. */}
            {failure.code !== 'corpus_moved' ? null : (
              <Button size="sm" variant="quiet" icon="refresh" onClick={() => void load(picked, stamp)}>
                Re-read the pricing file, losing what is unsaved here
              </Button>
            )}
          </Notice>
        )}

        {/* THE LANDING DECK — the two things a person needs before touching a row: what the
            cheap cards will list at, and whether this can be written at all. Both were
            further down the page (one behind a run selection, one under a sticky bar at the
            bottom of a hundred rows) and both are answers to questions asked on arrival. */}
        {/* THE CUT-OFF PANEL IS ALWAYS DRAWN. It was conditional on there being cards under the
            line, which was fine while the figure was only an answer ABOUT those cards — now that
            the figure IS the line, a cut-off typed low enough to empty the lower section would
            take its own control off the screen and leave no way back to it. */}
        <div className="pricing-deck" ref={deckRef} data-cards={source.kind === 'markdown' ? 'one' : 'two'}>
          {source.kind === 'markdown' ? (
            /* ONE OF THE TWO PLACES THAT ASK WHICH DOOR IT WAS, and it earns it: the run deck
               is a cut-off editor and a readiness verdict, and NEITHER is a fact about a live
               listing. The cut-off decides which import file a row goes in and this row goes
               in none; the verdict counts what `emit` would write and `emit` never runs here. */
            <MarkdownPanel table={sheet} rows={rows} answers={answers} />
          ) : (
            <>
          <CutoffPanel
            count={subCount}
            above={rows.length - subCount}
            cut={cut}
            from={cutFrom}
            stranded={stranded}
            runName={run}
            runLabel={scopeName ?? (run === null ? null : run)}
            runCount={loaded.length}
            onCut={setCut}
            onRunCut={setRunCut}
            onPickRun={() => setRunsOpen(true)}
          />
          <ReadyPanel
            owes={owes}
            progress={progress}
            cheapMoney={cheapMoney}
            queued={queued}
            runCount={loaded.length}
            boxCount={boxesLoaded.length}
            readAge={readAge}
            emitted={emitted}
          />
            </>
          )}
        </div>

        <div className="pricing-toolbar">
          {/* THE RULE STRIP — four answers, and the fourth is written the way the three are.
              The sentence and the custom fields share ONE line beneath the segments, with the
              height of a control reserved on it, so picking Custom fills that line instead of
              pushing the strip down. */}
          <div className="pricing-rule" role="group" aria-label="Suggest a price for every row">
            <Segmented<string>
              className="pricing-rule-seg"
              label="Rule for the rows you have not set"
              value={ruleSegment}
              options={[
                ...PRESETS.map((preset) => ({ value: preset.key, label: preset.label })),
                { value: CUSTOM_KEY, label: 'Custom' },
              ]}
              onChange={pickRule}
            />
            <div className="pricing-rule-line">
              {customOn ? (
                <div className="pricing-custom" data-bad={customBad === null ? undefined : 'true'}>
                  <Segmented<RuleKind>
                    className="pricing-custom-kind"
                    label="Price under or over the basis"
                    value={customDraft.kind}
                    options={[
                      { value: 'undercut', label: KIND_LABEL.undercut },
                      { value: 'markup', label: KIND_LABEL.markup },
                    ]}
                    onChange={(kind) => {
                      const next = { ...customDraft, kind }
                      setCustomDraft(next)
                      if (badPercent(kind, next.pct) === null) applyCustom(next)
                      else setCustomBad(null)
                    }}
                  />
                  <label className="pricing-flat pricing-pct">
                    <input
                      ref={customPct}
                      className="bn-input pricing-flat-input pricing-pct-input"
                      type="text"
                      inputMode="decimal"
                      placeholder="0"
                      aria-label="Percentage off the basis price"
                      aria-invalid={customBad === null ? undefined : true}
                      value={customDraft.pct}
                      onChange={(event) => {
                        const text = event.currentTarget.value
                        if (!PCT.test(text)) return
                        setCustomDraft((current) => ({ ...current, pct: text }))
                        setCustomBad(null)
                      }}
                      onBlur={(event) => applyCustom({ ...customDraft, pct: event.currentTarget.value })}
                      onKeyDown={(event) => {
                        if (event.key !== 'Enter') return
                        event.preventDefault()
                        applyCustom({ ...customDraft, pct: event.currentTarget.value })
                      }}
                    />
                    <span className="pricing-flat-sign pricing-pct-sign" aria-hidden="true">
                      %
                    </span>
                  </label>
                  <span className="pricing-custom-of">of</span>
                  <Segmented<RuleBasis>
                    className="pricing-custom-basis"
                    label="Which price to work from"
                    value={customDraft.basis}
                    options={[
                      { value: 'market', label: BASIS_LABEL.market },
                      { value: 'low', label: BASIS_LABEL.low },
                    ]}
                    onChange={(basis) => {
                      const next = { ...customDraft, basis }
                      setCustomDraft(next)
                      if (badPercent(next.kind, next.pct) === null) applyCustom(next)
                    }}
                  />
                </div>
              ) : null}
              <span
                className={`pricing-rule-says${customBad === null ? '' : ' pricing-rule-bad'}`}
                data-keep={customOn ? 'true' : undefined}
                title="A rule fills only the rows you have not set, and becomes the standing rule."
              >
                <Icon name={customBad === null ? 'info' : 'alert'} size={13} />
                {customOn
                  ? (customLine ?? 'Type a percentage and this becomes the standing rule.')
                  : activePreset === null
                    ? 'No rule matches the standing answer.'
                    : activePreset.says}
              </span>
            </div>
          </div>
          <div className="pricing-toolbar-right">
            {source.kind !== 'markdown' ? null : (
              /* THE LENS, AS A FILTER OVER WHAT IS ALREADY LOADED — never a second read. The
                 rows are all here; narrowing is instant and widening costs nothing, which is
                 exactly what a gate could not offer: on the owner's own store the ten-day
                 window selects zero rows and the only remedy was to change the number and
                 fetch again. `All` is first and is the default (D103). */
              <Segmented<'all' | 'offered' | 'refused'>
                value={lens}
                aria-label="Which live listings to show"
                options={[
                  { value: 'all', label: `All ${(sheet?.skus ?? []).length}` },
                  {
                    value: 'offered',
                    label: `Not selling ${Number(sheet?.counts?.offered ?? 0)}`,
                  },
                  {
                    value: 'refused',
                    label: `Passed over ${Number(sheet?.counts?.refused ?? 0)}`,
                  },
                ]}
                onChange={setLens}
              />
            )}
            {held.length === 0 ? null : (
              <Button
                size="sm"
                pill
                icon="lock"
                variant={filterHeld ? 'primary' : 'default'}
                className="pricing-filter-held"
                aria-pressed={filterHeld}
                onClick={() => setFilterHeld((on) => !on)}
              >
                Holding {held.length}
              </Button>
            )}
            {undo.length === 0 ? null : (
              <Button size="sm" variant="ghost" icon="undo" kbd="U" onClick={undoLast}>
                Undo
              </Button>
            )}
            <Button
              size="sm"
              icon="trendUp"
              className="pricing-trend-btn"
              onClick={loadTrends}
              disabled={source.trends === null || trendRun?.reading === true}
              busy={trendRun?.reading === true}
              title={
                source.trends === null
                  ? 'Trends read one run at a time — pick a single run'
                  : `Read the shape of the ${rows.length} row${rows.length === 1 ? '' : 's'} on screen off two public mirrors`
              }
            >
              {/* THE COUNT IS ON THE BUTTON, because on a lens this press is the one that can be
                  rude: the reading is a courtesy-delayed walk at a free public mirror, and the
                  operator deserves to know it is about to ask about four hundred cards rather
                  than forty before they press. */}
              {trendRun === null
                ? `Load trends${source.kind === 'markdown' ? ` · ${rows.length}` : ''}`
                : trendRun.reading
                  ? `Reading ${trendRun.done} of ${trendRun.total}…`
                  : 'Read again'}
            </Button>
          </div>
        </div>

        {trendRun === null ? null : (
          <div className="pricing-trendbar" aria-live="polite">
            {trendRun.reading ? (
              <>
                <div className="bn-progress pricing-trend-progress" aria-hidden="true">
                  <span style={{ width: `${trendRun.total === 0 ? 100 : Math.round((trendRun.done / trendRun.total) * 100)}%` }} />
                </div>
                <span className="pricing-trendbar-says">
                  Reading {trendRun.done} of {trendRun.total} rows — the strip fills in waves.
                </span>
              </>
            ) : (
              <span className="pricing-trendbar-says">
                {(trendRun.spans ?? []).map((range) => (
                  <span key={range.range} className="pricing-trendbar-span bn-pill bn-pill-mono">
                    {RANGE_LABEL[range.range] ?? range.range} {range.from ?? '?'} → {range.to ?? '?'}
                  </span>
                ))}
                <span className="pricing-trendbar-tally">
                  {trendTally.read} read
                  {trendRun.skipped > 0 ? ` · ${trendRun.skipped} not asked` : ''}
                  {trendTally.refused > 0 ? ` · ${trendTally.refused} refused` : ''}
                </span>
                <span
                  className="pricing-trendbar-why"
                  title="The ranges overlap and are read separately — the wider one includes these same recent days at a coarser width, so they can point opposite ways."
                >
                  <Icon name="info" size={13} /> ranges overlap
                </span>
              </span>
            )}
          </div>
        )}

        {note === null || note.sku !== '' ? null : (
          <Notice tone="warn" className="pricing-notice pricing-refusal">
            {note.text}
          </Notice>
        )}

        {sections.map((section) => (
          <section
            className="pricing-section"
            key={section.bucket}
            data-bucket={section.bucket}
            data-direct={section.direct ? 'some' : 'none'}
            /* THE THIRD GRID AXIS, and the only one whose absence is about the SOURCE rather
               than about this section's contents. A live listing is not a copy in a drawer, so
               the thumbnail and the quantity cell have nothing to say — see `pricingSource.ts`.
               The cells are NOT RENDERED rather than hidden: the thumb is a `<button>`, and
               CLAUDE.md's rule is that a control a persona may not use is not focusable and not
               reachable by a screen reader, not one specificity change from coming back. */
            data-copies={source.copies ? 'some' : 'none'}
          >
            <header className="pricing-section-head">
              <div className="pricing-section-lead">
                <span className={`pricing-section-icon pricing-section-icon-${section.bucket}`}>
                  <Icon name={section.icon} size={16} />
                </span>
                <div className="pricing-section-text">
                  <h2 className="pricing-section-title">
                    {section.title}
                    <span className="bn-pill pricing-section-count">{section.total} SKU{section.total === 1 ? '' : 's'}</span>
                  </h2>
                  <p className="pricing-section-note">{section.note(cut)}</p>
                </div>
              </div>
              {section.bucket !== 'sub_threshold' ? null : (
                /* THE ANSWER ITSELF IS ON THE LANDING DECK, NOT HERE (the owner, 2026-09-03).
                   What this says is which answer these rows are carrying, and where it came
                   from — one press away, above the fold, whether or not a run is picked. */
                <button
                  type="button"
                  className="pricing-section-answer"
                  data-state={cutFrom === 'default' ? 'unset' : cutFrom}
                  onClick={showDeck}
                  title="The cut-off is set at the top of this screen"
                >
                  <span className="pricing-section-answer-figure">${cut}</span>
                  <span className="pricing-section-answer-says">
                    {cutFrom === 'default'
                      ? 'store default · not written'
                      : cutFrom === 'store'
                        ? 'the store’s cut-off'
                        : 'this run only'}
                  </span>
                  <Icon name="chevronUp" size={13} />
                </button>
              )}
            </header>

            <div className="pricing-caption" aria-hidden="true">
              {!source.copies ? null : <span />}
              <span>Card</span>
              {!source.copies ? null : <span className="pricing-caption-qty">Qty</span>}
              <span className="pricetrend-keys">
                {['month', 'annual'].map((range) => (
                  <span key={range}>{RANGE_LABEL[range] ?? range}</span>
                ))}
              </span>
              {SNAPS.map((column) => (
                <span key={column.key} className={`pricing-caption-ref pricing-caption-${column.field}`}>
                  {column.label} <Kbd>{column.key.toUpperCase()}</Kbd>
                </span>
              ))}
              <span className="pricing-caption-price">{source.kind === 'markdown' ? 'New price' : 'Lists at'}</span>
              <span />
            </div>

            <div className="pricing-list">
              {section.items.map((item, index) => {
                if (item.head !== null) {
                  return (
                    <h3 className="pricing-group-head" key={`why:${item.head}`}>
                      <span className="pricing-group-why">{item.head}</span>
                      <span className="pricing-group-count">{item.count === 1 ? '1 SKU' : `${item.count} SKUs`}</span>
                    </h3>
                  )
                }
                const sku = item.sku
                const standing = answerFor(sku)
                const withheld = isWithheld(standing)
                const suggestion = suggestionFor(sku)
                const why = withheld && standing !== 'unlisted' && standing.note ? standing.note : null
                const first = sku.positions[0] ?? null
                const boxes = [...new Set(sku.positions.map((place) => place.box))].sort((a, b) => a - b)
                const state = fieldState(
                  sku,
                  standing,
                  doc,
                  cut,
                  cutFrom !== 'default',
                  source.kind === 'markdown' ? (askingOf.get(sku.sku) ?? null) : undefined,
                )
                const rowNote = note !== null && note.sku === sku.sku ? note.text : null
                return (
                  <div
                    className="pricing-row"
                    key={sku.sku}
                    style={{ '--i': String(Math.min(index, 14)) } as CSSProperties}
                    onPointerEnter={() => {
                      hovered.current = sku.sku
                    }}
                    onPointerLeave={() => {
                      if (hovered.current === sku.sku) hovered.current = null
                    }}
                    data-answer={withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'}
                    data-cap={sku.at_cap ? 'full' : 'room'}
                    data-dim={filterHeld && !withheld ? 'true' : undefined}
                    data-hold={holdFor === sku.sku ? 'open' : undefined}
                    data-drawn={(historySku?.sku ?? photoSku?.sku) === sku.sku ? 'true' : undefined}
                  >
                    {!source.copies ? null : (
                      <PricingThumb at={first} name={sku.name} onOpen={() => openPhoto(sku)} />
                    )}

                    <div className="pricing-id">
                      <span className="pricing-name" title={sku.name}>
                        {sku.name}
                      </span>
                      <span className="pricing-meta">
                        <span className={`pricing-cond${section.uniform ? ' pricing-meta-same' : ''}`}>{sku.condition}</span>
                        <span className="pricing-meta-sep">·</span>
                        <span className={section.uniform ? 'pricing-meta-same' : undefined}>{sku.set_name}</span>
                        <span className="pricing-meta-sep">·</span>
                        <span className="bn-mono">{sku.row['Number'] ?? ''}</span>
                        {sku.row['Rarity'] ? (
                          <>
                            <span className="pricing-meta-sep">·</span>
                            <span>{sku.row['Rarity']}</span>
                          </>
                        ) : null}
                        {sku.listing === null ? null : (
                          <span className="pricing-row-span">
                            <span className="pricing-meta-sep">·</span>
                            <LiveCount live={sku.listing.live} age={ageWords(readAtOf(sku))} />
                          </span>
                        )}
                        {sku.in.length < 2 && !sku.over_cap ? null : (
                          <span className="pricing-row-span">
                            <span className="pricing-meta-sep">·</span>
                            <span className="pricing-span-where">
                              {boxes.length === 0
                                ? `${sku.in.length} run${sku.in.length === 1 ? '' : 's'}`
                                : `${boxes.length === 1 ? 'Box' : 'Boxes'} ${boxes.join(', ')} · ${sku.in.length} run${sku.in.length === 1 ? '' : 's'}`}
                            </span>
                            {!sku.over_cap ? null : (
                              <span
                                className="pricing-span-cap bn-pill bn-pill-warn"
                                title={`The runs separately claim more copies than the cap has room for. The copies TCGplayer was holding were read ${ageWords(readAtOf(sku)) ?? 'at an unrecorded time'}.`}
                              >
                                Runs claim {sku.claimed_add} · {sku.add_to_quantity} can go
                              </span>
                            )}
                          </span>
                        )}
                        {why === null ? null : (
                          <span className="pricing-row-note">
                            <span className="pricing-meta-sep">·</span>
                            <span className="pricing-row-why" title={why}>
                              “{why}”
                            </span>
                          </span>
                        )}
                      </span>
                    </div>

                    <div className="pricing-facts">
                      {!source.copies ? null : (
                        <span className="pricing-qty" title={`${sku.add_to_quantity} of the ${sku.copies} copies on hand go in the file`}>
                          <span className="bn-sr">Quantity </span>
                          {sku.add_to_quantity} <span className="pricing-qty-of">of {sku.copies}</span>
                        </span>
                      )}

                      <TrendCell read={trends[sku.sku]} />

                      {SNAPS.map((column) => (
                        <span
                          key={column.key}
                          className={`pricing-ref pricing-ref-${column.field}${column.field === 'market' ? ' pricing-ref-market' : ''}`}
                          data-empty={sku.snap[column.field] === null ? 'true' : undefined}
                          title={`${column.column}: ${sku.row[column.column] || '—'} · press ${column.key.toUpperCase()} to use it`}
                        >
                          <span className="pricing-ref-label">{column.label} </span>
                          {sku.snap[column.field] === null ? '—' : `$${sku.snap[column.field]}`}
                        </span>
                      ))}
                    </div>

                    <div className="pricing-price" data-answer={withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'}>
                      {withheld ? (
                        <span className="pricing-held">
                          <Icon name="lock" size={13} />
                          Holding
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
                            placeholder={sku.bucket === 'no_market_data' ? '—' : undefined}
                            aria-label={`Price for ${sku.name}`}
                            defaultValue={typeof standing === 'string' ? standing : suggestion}
                            ref={(node) => {
                              if (node) inputs.current.set(sku.sku, node)
                              else inputs.current.delete(sku.sku)
                            }}
                            onFocus={(event) => event.currentTarget.select()}
                            onBeforeInput={(event) => {
                              const native = event.nativeEvent as InputEvent
                              const insert = native.data ?? ''
                              if (insert === '') return
                              const field = event.currentTarget
                              // THE PREFILL CLEARS ON THE FIRST CHARACTER, one shot per field.
                              const firstKey = !touched.current.has(sku.sku)
                              touched.current.add(sku.sku)
                              if (firstKey && typeof answerFor(sku) !== 'string') field.value = ''
                              const next =
                                field.value.slice(0, field.selectionStart ?? 0) + insert + field.value.slice(field.selectionEnd ?? 0)
                              if (!PRICE.test(next)) event.preventDefault()
                            }}
                            onKeyDown={(event) => onKey(event, sku)}
                            onBlur={(event) => commit(sku, event.currentTarget.value)}
                          />
                          <Icon name="check" size={13} className="pricing-price-check" />
                        </label>
                      )}
                      <span
                        className={`pricing-state pricing-state-${rowNote === null ? state.tone : 'warn'}${rowNote === null ? '' : ' pricing-refusal'}`}
                        title={rowNote ?? state.title ?? state.text}
                      >
                        {rowNote ?? state.text}
                      </span>
                    </div>

                    <div className="pricing-actions">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="history"
                        iconOnly
                        className="pricing-history"
                        aria-pressed={pinned === sku.sku}
                        aria-label={`Price history for ${sku.name}`}
                        title="Price history · hold T to peek"
                        disabled={source.history === null}
                        onClick={() => (pinned === sku.sku ? unpin() : pinHistory(sku))}
                      >
                        Price history
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={withheld ? 'unlock' : 'lock'}
                        iconOnly
                        className="pricing-hold"
                        aria-pressed={withheld}
                        aria-label={withheld ? `Release ${sku.name}` : `Hold ${sku.name}`}
                        title={withheld ? 'Release · H' : 'Hold back · H'}
                        onClick={() => toggleHold(sku)}
                      >
                        {withheld ? 'Release' : 'Hold'}
                      </Button>
                    </div>

                    {holdFor !== sku.sku ? null : phone ? (
                      createPortal(
                        <>
                          <div className="bn-scrim" onClick={() => cancelHold(sku)} />
                          <HoldPanel sku={sku} sheet onSet={setHold} onCancel={() => cancelHold(sku)} />
                        </>,
                        document.body,
                      )
                    ) : (
                      <HoldPanel sku={sku} onSet={setHold} onCancel={() => cancelHold(sku)} />
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>

      {/* THE DRAWER: the reading, or the photograph, for one card. Beside the sidebar on desktop,
          a bottom sheet on a phone. A held `t` outranks a pin while the key is down. */}
      {historySku !== null ? (
        createPortal(
        <aside
          className="bn-sheet bn-sheet-left pricing-drawer"
          aria-label={`Price history for ${historySku.name}`}
          data-peek={peek !== null ? 'true' : undefined}
          style={{ '--pricing-drawer-left': `${shellLeft()}px` } as CSSProperties}
        >
          <header className="pricing-drawer-head">
            <div className="bn-tabs pricing-drawer-tabs" role="tablist">
              <button type="button" role="tab" className="bn-tab" aria-selected="true">
                <Icon name="history" size={14} /> History
              </button>
              <button
                type="button"
                role="tab"
                className="bn-tab"
                aria-selected="false"
                onClick={() => {
                  unpin()
                  setPhotoFor({ sku: historySku.sku, at: 0 })
                }}
              >
                <Icon name="image" size={14} /> Photo
              </button>
            </div>
            <Button variant="ghost" size="sm" icon="x" iconOnly onClick={closeDrawer}>
              Close
            </Button>
          </header>
          <PriceHistoryPanel
            sku={historySku.sku}
            name={historySku.name}
            read={history[historySku.sku]}
            readAge={ageWords(readAtOf(historySku))}
            pinned={pinned === historySku.sku}
            onClose={unpin}
            onKeep={() => pinHistory(historySku)}
            onRetry={() => readHistory(historySku, true)}
          />
        </aside>,
        document.body,
        )
      ) : photoSku !== null && photoFor !== null ? (
        createPortal(
        <aside
          className="bn-sheet bn-sheet-left pricing-drawer"
          aria-label={`Photograph of ${photoSku.name}`}
          style={{ '--pricing-drawer-left': `${shellLeft()}px` } as CSSProperties}
        >
          <header className="pricing-drawer-head">
            <div className="bn-tabs pricing-drawer-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                className="bn-tab"
                aria-selected="false"
                disabled={source.history === null}
                onClick={() => pinHistory(photoSku)}
              >
                <Icon name="history" size={14} /> History
              </button>
              <button type="button" role="tab" className="bn-tab" aria-selected="true">
                <Icon name="image" size={14} /> Photo
              </button>
            </div>
            <Button variant="ghost" size="sm" icon="x" iconOnly onClick={closeDrawer}>
              Close
            </Button>
          </header>
          <div className="pricing-photo">
            <div className="pricing-photo-head">
              <h3 title={photoSku.name}>{photoSku.name}</h3>
              <span className="pricing-machine">sku {photoSku.sku}</span>
            </div>
            <div className="bn-photo pricing-photo-frame">
              <img src={photoUrl(photoAt?.box ?? 0, photoAt?.index ?? 0)} alt={photoSku.name} />
            </div>
            <p className="pricing-photo-caption">
              <Icon name="pin" size={13} />
              {photoAt === null ? null : photoAt.label ?? `no label · ${photoAt.box}/${photoAt.index}`}
              {' · '}
              {(photoFor.at % photoSku.positions.length) + 1} of {photoSku.positions.length}
            </p>
            <div className="pricing-photo-controls">
              <Button
                icon="chevronRight"
                onClick={() => setPhotoFor({ sku: photoFor.sku, at: photoFor.at + 1 })}
                disabled={photoSku.positions.length < 2}
              >
                Next copy
              </Button>
              <Button variant="quiet" onClick={() => setPhotoFor(null)}>
                Close
              </Button>
            </div>
          </div>
        </aside>,
        document.body,
        )
      ) : null}

      {/* THE SHIP BAR (D54): sticky, in flow, one primary. A merged send over several runs
          re-derives the cap once across them (D86). */}
      {loaded.length < 2 ? null : (
        <aside className="pricing-ship" ref={measureShip} role="region" aria-label="Ship these runs">
          <div className="pricing-ship-status">
            <span className="bn-pill bn-pill-accent">
              <Icon name="layers" size={12} />
              {loaded.length} runs · {boxesLoaded.length} {boxesLoaded.length === 1 ? 'box' : 'boxes'} · one file
            </span>
            <span className="pricing-ready pricing-ship-says">
              The cap is spent once across the send, so a card in three boxes gets one row.
            </span>
          </div>
          <div className="pricing-ship-act">
            <label className="bn-check pricing-ship-only">
              <input type="checkbox" checked={listedOnly} onChange={(event) => setListedOnly(event.currentTarget.checked)} />
              just the cards above the cut-off
            </label>
            {/* THE SPLIT IS MEANINGLESS OVER A FILTERED SEND — "listed only" has already left the
                lower half out, so there is no second file to write. Disabled rather than hidden:
                a control that vanishes reads as one you imagined. */}
            <label className="bn-check pricing-ship-only" data-off={listedOnly ? 'true' : undefined}>
              <input
                type="checkbox"
                checked={splitFiles && !listedOnly}
                disabled={listedOnly}
                onChange={(event) => setSplitFiles(event.currentTarget.checked)}
              />
              split it in two, either side of the cut-off
            </label>
            {receipt === null ? null : (
              <Button variant="ghost" icon={receipt.ok ? 'download' : 'alert'} onClick={() => setFilesOpen(true)}>
                {receipt.ok ? `${receipt.files.filter((f) => f.is_import).length} files` : 'Refused'}
              </Button>
            )}
            <Button
              variant="primary"
              size="lg"
              icon="send"
              className="pricing-emit"
              busy={sendingAll}
              disabled={sendingAll}
              onClick={() => {
                setSendingAll(true)
                setShipTrouble(null)
                void (async () => {
                  try {
                    const result = await emitMerged(loaded, { listedOnly, splitThreshold: splitFiles && !listedOnly })
                    setReceipt({ ok: result.ok, console: result.console, files: result.files })
                    const imports = (result.files ?? []).filter((file) => file.is_import)
                    toast(
                      result.ok
                        ? {
                            kind: 'ok',
                            title: `${imports.length} import file${imports.length === 1 ? '' : 's'} written`,
                            body: 'Import to Staged in TCGplayer, then reconcile on Runs.',
                            action: { label: 'Files', onPress: () => setFilesOpen(true) },
                          }
                        : {
                            kind: 'refusal',
                            title: 'Emit refused',
                            body: result.console.trim().split('\n').slice(-1)[0] ?? '',
                            action: { label: 'Details', onPress: () => setFilesOpen(true) },
                          },
                    )
                  } catch (err) {
                    setShipTrouble(describeFailure(err))
                  } finally {
                    setSendingAll(false)
                  }
                })()
              }}
            >
              {sendingAll ? 'Writing…' : splitFiles && !listedOnly ? 'Write two import files' : 'Write one import file'}
            </Button>
          </div>
          {shipTrouble === null ? null : (
            <Notice tone="danger" title={shipTrouble.message} code={shipTrouble.code} className="pricing-ship-trouble" />
          )}
          {!filesOpen || receipt === null ? null : (
            <ReceiptDialog
              receipt={receipt}
              run={loaded[loaded.length - 1] as string}
              consoleOpen={consoleOpen}
              onToggleConsole={() => setConsoleOpen((on) => !on)}
              onClose={() => setFilesOpen(false)}
            />
          )}
        </aside>
      )}

      {run === null ? null : (
        <aside className="pricing-ship" ref={measureShip} role="region" aria-label="Ship this run" data-ready={owes.length === 0 ? 'true' : 'false'}>
          {/* THE VERDICT IS A PRESS, AND THE ACCOUNT OF IT IS ON THE DECK. The bar carries the
              answer and the button; the sentence that says what is still owed lives at the top
              of the screen, where a person lands. This walks them back to it. */}
          <div className="pricing-ship-status">
            <button
              type="button"
              className="pricing-ship-verdict"
              data-ready={owes.length === 0 ? 'true' : 'false'}
              onClick={showDeck}
              title="What this means is at the top of the screen"
            >
              <span className={`bn-pill ${owes.length === 0 ? 'bn-pill-ok' : 'bn-pill-warn'}`}>
                <Icon name={owes.length === 0 ? 'check' : 'alert'} size={12} />
                {owes.length === 0 ? 'Ready' : 'Not yet'}
              </span>
              <span className="pricing-ready">
                {owes.length === 0 ? (
                  progress.rule > 0 ? (
                    <>
                      <strong>{standingSays}</strong>
                      {progress.answered === 0 ? ' · nothing typed or held' : ` · ${progress.answered} typed or held`}
                    </>
                  ) : (
                    <strong>Pricing is answered</strong>
                  )
                ) : (
                  <>
                    <strong>Emit will refuse</strong> · {owes.length} thing{owes.length === 1 ? '' : 's'} owed
                  </>
                )}
              </span>
              <Icon name="chevronUp" size={13} />
            </button>
          </div>

          <div className="pricing-keys" aria-hidden="true">
            <span>
              <Kbd>↵</Kbd> next
            </span>
            <span>
              <Kbd>M</Kbd>
              <Kbd>L</Kbd>
              <Kbd>S</Kbd>
              <Kbd>D</Kbd> snap
            </span>
            <span>
              <Kbd>H</Kbd> hold
            </span>
            <span>
              <Kbd>T</Kbd> history
            </span>
            <span>
              <Kbd>P</Kbd> photo
            </span>
            <span>
              <Kbd>U</Kbd> undo
            </span>
          </div>

          <div className="pricing-ship-act">
            <label className="bn-check pricing-ship-only">
              <input type="checkbox" checked={splitFiles} onChange={(event) => setSplitFiles(event.currentTarget.checked)} />
              split it in two, either side of the cut-off
            </label>
            {receipt === null ? null : (
              <Button variant="ghost" icon={receipt.ok ? 'download' : 'alert'} onClick={() => setFilesOpen(true)}>
                {receipt.ok ? `${receipt.files.filter((f) => f.is_import).length} files` : 'Refused'}
              </Button>
            )}
            {ship === 'waiting' ? (
              <>
                <span className="pricing-ship-key">Saving your answers…</span>
                <Button variant="quiet" onClick={() => setShip('idle')}>
                  Cancel
                </Button>
              </>
            ) : emitted && !armed ? (
              <>
                <span className="pricing-ship-key">
                  <Icon name="check" size={13} /> Already written
                </span>
                <Button icon="refresh" onClick={() => setArmed(true)}>
                  Write them again
                </Button>
              </>
            ) : emitted && armed ? (
              <>
                <span className="pricing-ship-key">Writing again sends only what has not been sent yet.</span>
                <Button variant="quiet" onClick={() => setArmed(false)}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="lg"
                  icon="send"
                  className="pricing-emit"
                  busy={ship === 'sending'}
                  disabled={ship === 'sending'}
                  onClick={() => setShip('waiting')}
                >
                  {ship === 'sending' ? 'Writing…' : 'Write again'}
                </Button>
              </>
            ) : (
              <Button
                variant="primary"
                size="lg"
                icon="send"
                className="pricing-emit"
                busy={ship === 'sending'}
                disabled={ship === 'sending'}
                onClick={() => setShip('waiting')}
              >
                {ship === 'sending' ? 'Writing…' : splitFiles ? 'Write the two import files' : 'Write the import file'}
              </Button>
            )}
          </div>

          {shipTrouble === null ? null : (
            <Notice tone="danger" title={shipTrouble.message} code={shipTrouble.code} className="pricing-ship-trouble" />
          )}

          {!filesOpen || receipt === null ? null : (
            <ReceiptDialog
              receipt={receipt}
              run={run}
              consoleOpen={consoleOpen}
              onToggleConsole={() => setConsoleOpen((on) => !on)}
              onClose={() => setFilesOpen(false)}
            />
          )}
        </aside>
      )}

      {/* THE LENS'S OWN PRESS — the second of the two places that ask which door it was, and
          the one place where getting it wrong costs money (D103). It is a THIRD sibling and
          never a mode of either bar above: `emit` writes a file that ADDS quantity, this one
          writes a file that only ever changes a price, and D100 §2's doubling — nine SKUs on
          this store at `2 x pushed - sold` — is what one file uploaded twice already did. Two
          presses that can never be confused for each other beats one press with a flag.

          BOTH BARS ABOVE HIDE THEMSELVES HERE WITH NO EDIT AT ALL: `loaded` derives from
          `work.runs`, which is null on a lens, so `loaded.length < 2` and `run === null` are
          both true. The run path is untouched by construction rather than by care. */}
      {source.kind !== 'markdown' || stamp === null ? null : (
        <aside className="pricing-ship" ref={measureShip} role="region" aria-label="Push these prices">
          <div className="pricing-ship-status">
            <span className="bn-pill bn-pill-accent">
              <Icon name="trendDown" size={12} />
              {pushable.length} {pushable.length === 1 ? 'price' : 'prices'} to push
            </span>
            <span className="pricing-ready pricing-ship-says">
              Every row carries <code className="bn-code">Add to Quantity</code> 0 — this changes
              prices and cannot move a single copy, so uploading it twice changes nothing.
            </span>
          </div>
          <div className="pricing-ship-act">
            {/* TWO PRESSES, MATCHING THE COMMAND AND `Markdown.tsx`'s OWN THREE-STEP REGISTER:
                the check answers first, and the write does not exist until it has. An absence
                rather than a disabled button, which is the rule that sheet already keeps. */}
            <Button
              icon="eye"
              size="lg"
              busy={push === 'checking'}
              disabled={push !== 'idle' || pushable.length === 0}
              onClick={() => setPush('checking')}
            >
              {push === 'checking' ? 'Checking…' : 'Check these prices'}
            </Button>
            {applied === null || !applied.ok ? null : (
              <Button
                variant="primary"
                size="lg"
                icon="trendDown"
                className="pricing-emit"
                busy={push === 'writing'}
                disabled={push !== 'idle'}
                onClick={() => setPush('writing')}
              >
                {push === 'writing' ? 'Writing…' : 'Write the upload file'}
              </Button>
            )}
            {!wroteUpload ? null : (
              <a className="bn-btn" href={markdownFileUrl(stamp, 'import.csv')} download="import.csv">
                <Icon name="download" size={16} />
                import.csv
              </a>
            )}
          </div>

          {applied === null ? null : (
            <LogWell
              text={applied.console}
              label={wroteUpload ? 'What the write printed' : 'What the check printed'}
              className="pricing-ship-console"
              maxHeight={220}
            />
          )}

          {shipTrouble === null ? null : (
            <Notice tone="danger" title={shipTrouble.message} code={shipTrouble.code} className="pricing-ship-trouble" />
          )}
        </aside>
      )}
    </main>
  )
}

/* ============================================================ the landing deck (2026-09-03)
 *
 * Two panels, above the list, answering the two questions a person has on arrival: where the
 * cut-off is, and whether this can be written at all. Both answers used to be somewhere else —
 * the first inside the sub-threshold section's header and only once a single run was picked,
 * the second under a sticky bar at the bottom of a hundred rows. */


/* THE BIG FIGURE, TYPED INTO DIRECTLY. It carries the display weight of a heading and the
   behaviour of a field: the `$` is drawn beside it rather than typed, the alphabet is closed to
   money, Enter and blur commit, Escape puts back what stood. It is an input at every size so
   there is no click-to-reveal state to discover — the thing that looks like the answer is the
   thing you change.

   IT HOLDS ITS OWN DRAFT AND PUBLISHES NOTHING UNTIL A COMMIT. Half-typed money — `0.`, `` —
   is a real keystroke on the way to a price and not a policy, and a field that told its parent
   about every one of them would re-partition the list under the hand typing into it. */
function BigMoney({
  value,
  onCommit,
  label,
}: {
  value: string
  onCommit: (next: string) => void
  label: string
}) {
  const [held, setHeld] = useState(value)
  useEffect(() => {
    setHeld(value)
  }, [value])
  /* A FIGURE THAT CANNOT BE WRITTEN SNAPS BACK TO THE ONE THAT STANDS. The field's alphabet
     admits `""` and a trailing dot on the way to a price, and `Decimal("0.")` is an error on
     the other side of the wire — so an empty field is a cleared draft and never a cut-off of
     nothing. */
  const commit = (text: string) => {
    const next = text.trim()
    if (!priceable(next)) {
      setHeld(value)
      return
    }
    setHeld(next)
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
        value={held}
        size={Math.max(4, held.length + 1)}
        onChange={(event) => {
          setHeld(event.currentTarget.value.replace(/[^0-9.]/g, ''))
        }}
        onFocus={(event) => event.currentTarget.select()}
        onBlur={(event) => commit(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault()
            setHeld(value)
            event.currentTarget.blur()
            return
          }
          if (event.key !== 'Enter') return
          event.preventDefault()
          commit(event.currentTarget.value)
          event.currentTarget.blur()
        }}
      />
    </span>
  )
}

/**
 * THE CUT-OFF — one figure doing two jobs (the owner, 2026-09-03).
 *
 * D9 wrote a threshold and a cheap-card price as two settings and this panel drew them as
 * two, which inverts: at a threshold of $0.40 and a cheap answer of $0.49, a card worth $0.38
 * lists at $0.49 and a card worth $0.42 lists at $0.42, so the cheap one goes out dearer than
 * the one that cleared the bar. They are the same variable. Everything under the cut-off lists
 * AT the cut-off, so nothing below the line can ever price above something over it.
 *
 * THE FIGURE IS THE CONTROL. It carries the display weight of a heading and the behaviour of a
 * field — the `$` is drawn beside it rather than typed, the alphabet is closed to money, Enter
 * and blur commit, Escape puts back what stood. It is an input at every size, so there is no
 * click-to-reveal state to discover: the thing that looks like the answer is the thing you
 * change. What it used to be was a read-out with a segmented row under it offering "a flat
 * price" or "the $X floor" plus a second small field, so the biggest thing on the panel was the
 * one thing you could not touch and the same number appeared twice.
 *
 * THE PANEL IS DRAWN WHETHER OR NOT ANY CARD IS UNDER THE LINE. A cut-off typed low enough to
 * empty the lower section would otherwise take its own control off the screen with it, and the
 * operator would have no way back to the figure they had just moved.
 */
function CutoffPanel({
  count,
  above,
  cut,
  from,
  stranded,
  runName,
  runLabel,
  runCount,
  onCut,
  onRunCut,
  onPickRun,
}: {
  count: number
  above: number
  cut: string
  from: 'run' | 'store' | 'default'
  stranded: string | null
  runName: string | null
  runLabel: string | null
  runCount: number
  onCut: (figure: string) => void
  onRunCut: (figure: string | undefined) => void
  onPickRun: () => void
}) {
  const overridden = from === 'run'
  const written = from !== 'default'
  const commit = overridden ? onRunCut : onCut

  return (
    <section
      className="bn-panel pricing-cheap"
      data-written={written ? 'yes' : 'no'}
      data-override={overridden ? 'true' : undefined}
      aria-label="The cut-off"
    >
      <header className="pricing-deck-head">
        <span className="pricing-deck-mark">
          <Icon name="dollar" size={16} />
        </span>
        <div className="pricing-deck-heading">
          {/* The eyebrow names WHOSE figure the number below is, so the panel cannot read as
              the store's while a run is quietly overriding it. */}
          <span className="bn-eyebrow">{overridden ? 'Store policy · overridden here' : 'Store policy'}</span>
          <h2 className="pricing-deck-title">The cut-off</h2>
        </div>
        <span className={`bn-pill ${written ? 'bn-pill-ok' : 'bn-pill-warn'}`}>
          <Icon name={written ? 'check' : 'alert'} size={12} />
          {written ? 'Written' : 'Default'}
        </span>
      </header>

      <div className="pricing-cheap-figure">
        <BigMoney
          value={cut}
          onCommit={commit}
          label={overridden ? "This run's cut-off" : "The store's cut-off"}
        />
        <span className="pricing-cheap-caption">
          <span className="pricing-cheap-says">
            {overridden ? 'this run only · ' : 'the line, and what everything under it lists at'}
          </span>
          {/* BOTH SIDES OF THE LINE, because the figure moves both. A count of what is under it
              alone reads as a warning; the pair reads as a partition, which is what it is. */}
          <span className="pricing-cheap-count">
            {count} under · {above} above
          </span>
        </span>
      </div>

      {stranded === null ? null : (
        /* TWO FIGURES WHERE THERE IS NOW ONE. Reported rather than resolved on the operator's
           behalf: which of the two they meant is not a thing this screen can know, and typing
           either — or pressing this — writes both keys and ends the disagreement. */
        <Notice tone="warn" title="This store still holds a separate cheap-card price" className="pricing-cheap-stranded">
          <span>
            Cards under the line are priced at <strong>{stranded}</strong> on disk, not at the cut-off. Emit
            uses that figure until one of them is written over.
          </span>
          <Button size="sm" variant="quiet" icon="check" onClick={() => commit(cut)}>
            Make them both ${cut}
          </Button>
        </Notice>
      )}

      <div className="pricing-cheap-run" data-on={overridden ? 'true' : undefined}>
        <div className="pricing-cheap-run-head">
          <span className="bn-label pricing-cheap-run-key">This run only</span>
          {runName === null ? null : (
            <span className="pricing-cheap-run-name" title={runName}>
              {runLabel ?? runName}
            </span>
          )}
          {overridden ? <span className="bn-pill bn-pill-accent">Overriding</span> : null}
        </div>
        {runName === null ? (
          <p className="pricing-cheap-run-off">
            {runCount} runs are loaded, and an override belongs to one lot. Pick a single run to give it
            a cut-off of its own.
            <Button size="sm" variant="ghost" icon="layers" onClick={onPickRun}>
              Pick a run
            </Button>
          </p>
        ) : (
          <>
            {/* ONE CONTROL, AND WHICH ONE DEPENDS ON WHAT IS WRITTEN. The figure above is where
                the number is typed, for whichever answer is in force, so the only thing left to
                decide here is WHOSE it is. Overriding starts from the store's own figure, so the
                first thing typed is a change to a number already on the screen rather than an
                empty field. */}
            <div className="pricing-cheap-controls">
              {overridden ? (
                <Button size="sm" variant="quiet" icon="undo" onClick={() => onRunCut(undefined)}>
                  Follow the store again
                </Button>
              ) : (
                <Button size="sm" variant="quiet" icon="tag" onClick={() => onRunCut(cut)}>
                  Give this run its own cut-off
                </Button>
              )}
            </div>
            <p className="pricing-cheap-run-says">
              {overridden ? (
                <>
                  This run splits at <strong>${cut}</strong>, and its cheap cards go out at that. Every
                  other run keeps the store’s.
                </>
              ) : (
                <>These cards follow the store’s cut-off. Nothing is written against this run.</>
              )}
            </p>
          </>
        )}
      </div>
    </section>
  )
}

/** The two reasons `emit` can refuse that this screen can see, said as a person would.
 *  `readiness.ts` owns the machine strings and the audited vocabulary; this is the wording,
 *  and the machine string is drawn beneath it rather than replaced by it. */
const OWED_SAYS: Record<OwedReason, string> = {
  sub_threshold_unset: 'The cheap-card answer',
  no_market_data_unanswered: 'A price for every card with no market value',
}

/**
 * WHETHER THIS CAN BE WRITTEN, ON THE LANDING (the owner, 2026-09-03).
 *
 * The verdict was only ever in the sticky bar at the bottom, which on a hundred-row worklist
 * is a sentence you meet after the work rather than before it. The press stays down there;
 * the account of it is here.
 */
/** THE LENS'S LANDING CARD — what this export says, and what the screen would push.
 *
 *  `ReadyPanel`'s SHAPE AND NOT ITS CONTENT. That panel counts what `emit` would write into an
 *  import file; nothing here is bound for one. What a markdown owes the operator before they
 *  start typing is different and shorter: how many live listings there are, how many the rule
 *  proposed, what they are asking in total, and — the one that can stop the press — how many
 *  of their own edits are RAISES.
 *
 *  THE RAISE COUNT IS THE POINT OF THIS PANEL. `pipeline/reprice.py:read_back` marks a price
 *  above the live one `RAISED`, and `Application.fatal` refuses THE WHOLE FILE over a single
 *  one. On a lens over four hundred live listings an operator will eventually type a higher
 *  number, so the count is drawn where they will see it before they press rather than
 *  discovered by a refusal afterwards.
 *
 *  IT IS A SECOND IMPLEMENTATION OF `after > before` AND IT CAN DRIFT, which is `readiness.ts`'s
 *  own confessed shape and the same trade: a server answer lags the keystroke that satisfies
 *  it. What keeps it honest is that it counts against the SURVEY's own `asking` — the figure
 *  the manifest will judge against — and never a figure this screen recomputed.
 */
function MarkdownPanel({
  table,
  rows,
  answers,
}: {
  table: MarkdownTable | null
  rows: readonly MergedSku[]
  answers: Record<string, unknown>
}) {
  const asking = useMemo(() => {
    const by = new Map<string, string | null>()
    for (const row of table?.skus ?? []) by.set(row.sku, row.asking)
    return by
  }, [table])

  const { typed, raises, copies } = useMemo(() => {
    let typedCount = 0
    let raiseCount = 0
    let live = 0
    for (const row of rows) {
      live += row.listing?.live ?? 0
      const answer = answers[row.sku]
      if (typeof answer !== 'string' || answer.trim() === '') continue
      typedCount += 1
      const was = asking.get(row.sku)
      const now = Number(answer)
      const before = was === null || was === undefined ? NaN : Number(was)
      if (!Number.isNaN(now) && !Number.isNaN(before) && now > before) raiseCount += 1
    }
    return { typed: typedCount, raises: raiseCount, copies: live }
  }, [rows, answers, asking])

  const counts = table?.counts ?? {}
  return (
    <section
      className="bn-panel pricing-verdict"
      data-ready={raises === 0 ? 'true' : 'false'}
      aria-label="What this export says, and what would be pushed"
    >
      <header className="pricing-deck-head">
        <span className="pricing-deck-mark">
          <Icon name={raises === 0 ? 'tag' : 'alert'} size={16} />
        </span>
        <div className="pricing-deck-heading">
          <span className="bn-eyebrow">Live inventory</span>
          <h2 className="pricing-deck-title">
            {raises === 0 ? `${rows.length} listing${rows.length === 1 ? '' : 's'} live` : 'A price went up'}
          </h2>
        </div>
      </header>

      {raises === 0 ? (
        <p className="pricing-verdict-says">
          {typed === 0 ? (
            <>
              <strong>Nothing typed yet.</strong> Every row here is a listing TCGplayer is holding
              right now. Type a price on any of them — nothing leaves this machine until you
              press.
            </>
          ) : (
            <>
              <strong>
                {typed} price{typed === 1 ? '' : 's'} typed
              </strong>{' '}
              — the rest are left exactly as they are listed.
            </>
          )}
        </p>
      ) : (
        /* A RAISE IS DRAWN, NOT REFUSED (D107). This said "this path only lowers, and one
           raised row refuses the whole upload" — true until the operator asked for raises, and
           the refusal it described is gone. What is left is worth saying anyway: the rule only
           ever proposes cuts, so every row here is one a person typed, and inside a screen
           called a markdown that is the row most worth a second look. */
        <p className="pricing-verdict-says">
          <strong>
            {raises} row{raises === 1 ? '' : 's'} priced above the live price.
          </strong>{' '}
          The rule only ever proposes a cut, so these are prices you typed. They will be sent as
          typed and named as raises on the receipt.
        </p>
      )}

      {/* THE SAME KEY STRIP `ReadyPanel` DRAWS UNDER ITS METER, without the bar: these three are
          not parts of one whole — a listing can be both proposed by the rule and typed over —
          so a proportional bar would be a picture of an arithmetic that does not hold. */}
      <ul className="pricing-meter-keys">
        {(
          [
            ['typed', copies, `live cop${copies === 1 ? 'y' : 'ies'}`],
            ['rule', Number(counts.offered ?? 0), 'proposed by the rule'],
            ['held', typed, 'typed by hand'],
          ] as const
        ).map(([part, count, says]) => (
          <li key={part} data-part={part} data-zero={count === 0 ? 'true' : undefined}>
            <span className="pricing-meter-dot" aria-hidden="true" />
            {count} {says}
          </li>
        ))}
      </ul>

      <p className="pricing-verdict-fine">
        Apply can still refuse for a reason this screen cannot see — the floor, a duplicate, or a
        price that has not moved. A raise is no longer one of them.
      </p>
    </section>
  )
}

function ReadyPanel({
  owes,
  progress,
  cheapMoney,
  queued,
  runCount,
  boxCount,
  readAge,
  emitted,
}: {
  owes: readonly { reason: OwedReason; count: number }[]
  progress: {
    total: number
    typed: number
    held: number
    cheap: number
    answered: number
    rule: number
    closed: number
    outRows: number
    outCopies: number
  }
  cheapMoney: string
  queued: number
  runCount: number
  boxCount: number
  readAge: string | null
  emitted: boolean
}) {
  const ready = owes.length === 0
  /* TWO KINDS OF UNTYPED ROW, AND THEY GO OUT AT DIFFERENT FIGURES. Everything below counts
     them apart: a listable row nobody typed into takes the rule's figure, a cheap one takes
     the cheap-card answer. Saying "on the rule" over both was false for every cheap row. */
  const ruleRows = Math.max(0, progress.rule - progress.cheap)
  const standing = [
    ruleRows > 0 ? `${ruleRows} row${ruleRows === 1 ? '' : 's'} still on the rule` : null,
    progress.cheap > 0 ? `${progress.cheap} cheap card${progress.cheap === 1 ? '' : 's'} on the cheap-card answer` : null,
  ]
    .filter((part): part is string => part !== null)
    .join(' · ')
  const writesAt =
    ruleRows > 0 && progress.cheap > 0
      ? `Emit will write the rule rows at the rule’s figure and the cheap ones at ${cheapMoney}.`
      : ruleRows > 0
        ? 'Emit will write them at the rule’s figure.'
        : `Emit will write them at ${cheapMoney}.`
  return (
    <section className="bn-panel pricing-verdict" data-ready={ready ? 'true' : 'false'} aria-label="Whether the import files can be written">
      <header className="pricing-deck-head">
        <span className="pricing-deck-mark">
          <Icon name={ready ? 'check' : 'alert'} size={16} />
        </span>
        <div className="pricing-deck-heading">
          <span className="bn-eyebrow">Before you write</span>
          <h2 className="pricing-deck-title">{ready ? 'Ready to write' : 'Not ready yet'}</h2>
        </div>
        {emitted ? (
          <span className="bn-pill bn-pill-ok">
            <Icon name="check" size={12} /> Written
          </span>
        ) : null}
      </header>

      {ready ? (
        <p className="pricing-verdict-says">
          {progress.rule > 0 ? (
            <>
              <strong>{standing}</strong>
              {progress.answered === 0 ? ' — nothing typed or held yet.' : ` · ${progress.answered} typed or held.`}{' '}
              {writesAt}
            </>
          ) : (
            <>
              <strong>Pricing is answered.</strong> Every row carries a price a hand put there.
            </>
          )}
        </p>
      ) : (
        <ul className="pricing-owes">
          {owes.map((one) => (
            <li key={one.reason} className="pricing-owes-row">
              <span className="pricing-owes-mark" aria-hidden="true">
                <Icon name="alert" size={12} />
              </span>
              <span className="pricing-owes-text">
                <span className="pricing-owes-what">{OWED_SAYS[one.reason]}</span>
                <span className="pricing-machine">{one.reason}</span>
              </span>
              <span className="pricing-owes-count">
                {one.count} card{one.count === 1 ? '' : 's'}
              </span>
            </li>
          ))}
        </ul>
      )}

      {queued === 0 ? null : (
        <p className="pricing-verdict-warn">
          <Icon name="inbox" size={13} />
          <span>
            This join sent {queued} card{queued === 1 ? '' : 's'} to <a href="#/review">review</a> — writing now leaves
            them out.
          </span>
        </p>
      )}

      {/* WHERE THE ANSWERS STAND, as one bar rather than three figures in a sentence. A held
          row writes nothing, so it is a third colour and not a shade of "done". */}
      {progress.total === 0 ? null : (
        <div className="pricing-meter">
          <div
            className="pricing-meter-bar"
            role="img"
            aria-label={`${progress.typed} typed, ${progress.held} held, ${ruleRows} on the rule, ${progress.cheap} cheap at ${cheapMoney}`}
          >
            <span data-part="typed" style={{ flexGrow: progress.typed }} />
            <span data-part="held" style={{ flexGrow: progress.held }} />
            <span data-part="rule" style={{ flexGrow: ruleRows }} />
            <span data-part="cheap" style={{ flexGrow: progress.cheap }} />
          </div>
          <ul className="pricing-meter-keys">
            {(
              [
                ['typed', progress.typed, 'typed'],
                ['held', progress.held, 'held back'],
                ['rule', ruleRows, 'on the rule'],
                ['cheap', progress.cheap, `cheap at ${cheapMoney}`],
              ] as const
            ).map(([part, count, says]) => (
              <li key={part} data-part={part} data-zero={count === 0 ? 'true' : undefined}>
                <span className="pricing-meter-dot" aria-hidden="true" />
                {count} {says}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="pricing-verdict-out">
        <Icon name="send" size={13} />
        <span>
          {progress.outRows === 0 ? (
            'Nothing would go in the file — every row is held, or at the cap.'
          ) : (
            <>
              <strong>
                {progress.outRows} row{progress.outRows === 1 ? '' : 's'}
              </strong>{' '}
              and {progress.outCopies} cop{progress.outCopies === 1 ? 'y' : 'ies'} would go in the import file.
            </>
          )}
        </span>
      </p>

      <dl className="pricing-verdict-facts">
        <div>
          <dt>Scope</dt>
          <dd>
            {runCount} run{runCount === 1 ? '' : 's'}
            {boxCount === 0 ? '' : ` · ${boxCount} box${boxCount === 1 ? '' : 'es'}`}
          </dd>
        </div>
        <div>
          <dt>Prices read</dt>
          <dd title="Every market figure and every live count on this screen was frozen into the run when it was joined.">
            {readAge ?? 'not recorded'}
          </dd>
        </div>
        {progress.closed === 0 ? null : (
          <div>
            <dt>Nothing to add</dt>
            <dd title="At the cap, or every copy already listed — this run writes no row for them.">
              {progress.closed} SKU{progress.closed === 1 ? '' : 's'}
            </dd>
          </div>
        )}
      </dl>

      <p className="pricing-verdict-fine">Emit can still refuse for a reason this screen cannot see.</p>
    </section>
  )
}

/** What the state label under a price field says, and in which tone. */
function fieldState(
  sku: MergedSku,
  standing: unknown,
  doc: DecisionsDocument,
  cut: string,
  cutWritten: boolean,
  /** The live asking price, on a lens. Absent on a run, where there is no live listing to be
   *  above or below. */
  asking?: string | null,
): { text: string; title?: string; tone: 'quiet' | 'ok' | 'warn' } {
  if (isWithheld(standing)) {
    // The human label is drawn; the machine string it stands for travels in the title.
    const reason = heldReason(standing)
    const label = (HOLD_SHORT as Record<string, string>)[reason] ?? reason
    return { text: label ? `Held · ${label}` : 'Held', title: reason ? `withheld: ${reason}` : 'withheld', tone: 'quiet' }
  }
  /* THE RAISE, ON THE ROW, AT THE KEYSTROKE (D103). `read_back` marks a price above the live
     one `RAISED` and `Application.fatal` refuses THE WHOLE FILE over one — so on a lens over
     four hundred live listings, an operator who types a higher number must find out here and
     not from a refusal after the press. */
  if (asking !== undefined && asking !== null && typeof standing === 'string') {
    const now = Number(standing)
    const was = Number(asking)
    if (!Number.isNaN(now) && !Number.isNaN(was)) {
      if (now > was) {
        return {
          text: 'Above the live price',
          title: `Listed at $${was.toFixed(2)}. Above it is a raise — the rule never proposes one, so it is sent as typed and named on the receipt (D107).`,
          tone: 'warn',
        }
      }
      if (now === was) return { text: 'Unchanged', title: `Already listed at $${was.toFixed(2)}.`, tone: 'quiet' }
      return { text: `Down from $${was.toFixed(2)}`, tone: 'ok' }
    }
  }
  /* AND ON A LENS, AN UNTYPED ROW IS NOT "on the rule" — no rule is going to write it. It is
     simply listed at what it is listed at, which is what the row already shows. */
  if (asking !== undefined && typeof standing !== 'string') {
    return { text: 'Listed', title: 'Nothing typed — this listing is left exactly as it is.', tone: 'quiet' }
  }
  if (typeof standing === 'string') return { text: 'Typed', tone: 'ok' }
  if (sku.bucket === 'no_market_data') return { text: 'Needs a price', tone: 'warn' }
  if (sku.bucket === 'sub_threshold') {
    // UNDER THE LINE IS AT THE LINE. One figure decides the section and prices it, so the row
    // draws the cut-off rather than a second number that could differ from it.
    if (cutWritten) return { text: `At the $${cut} cut-off`, tone: 'quiet' }
    // THE DEFAULT IS DRAWN, AND SO IS THE FACT THAT IT IS NOT WRITTEN. A bare "$0.49" here
    // would be a price nothing on disk agrees to; a bare "no answer" hides the figure the
    // landing is offering. Both, in the tone of the thing that stops the files being written.
    return {
      text: `Default $${cut}`,
      title: `The store default. Nothing is written, so emit refuses — the cut-off is at the top of this screen.`,
      tone: 'warn',
    }
  }
  /* ON THE RULE — AND THE ROW SAYS WHICH RULE WHEN IT IS THE OPERATOR'S OWN. A preset is
     named in the strip and priced in the field beside this label, so "On the rule" is the
     whole statement. A custom rule has no precomputed column on this wire, so the field can
     be empty and the label is then the only thing saying what the row goes out at: it carries
     the figure — `−7%` — and the basis travels in the title with the rule as emit spells it. */
  const custom = parseCustomRule(doc?.rule, doc?.basis)
  if (custom !== null) {
    return {
      text: `On the rule · ${customShort(custom)}`,
      title: `${customRuleText(custom)} of ${BASIS_LABEL[custom.basis]} — emit prices this row from the standing rule.`,
      tone: 'quiet',
    }
  }
  return { text: 'On the rule', tone: 'quiet' }
}

/** Light a field the screen just moved, so the operator sees which rows a preset changed. */
function flash(input: HTMLInputElement): void {
  const host = input.closest<HTMLElement>('.pricing-price')
  if (host === null) return
  host.classList.remove('is-flash')
  void host.offsetWidth
  host.classList.add('is-flash')
  window.setTimeout(() => host.classList.remove('is-flash'), 700)
}

/** The receipt: the files to import, what emit printed, and the errand that follows. */
function ReceiptDialog({
  receipt,
  run,
  consoleOpen,
  onToggleConsole,
  onClose,
}: {
  receipt: { ok: boolean; console: string; files: readonly RunFile[] }
  run: string
  consoleOpen: boolean
  onToggleConsole: () => void
  onClose: () => void
}) {
  return createPortal(
    <>
      <div className="bn-scrim" onClick={onClose} />
      <div className="bn-dialog pricing-ship-receipt" role="dialog" aria-label={receipt.ok ? 'The files to import' : 'What emit printed'}>
        <header className="pricing-receipt-head">
          <span className={`pricing-receipt-mark ${receipt.ok ? 'is-ok' : 'is-bad'}`}>
            <Icon name={receipt.ok ? 'check' : 'alert'} size={18} />
          </span>
          <div className="pricing-receipt-title">
            <h2>{receipt.ok ? 'Import files written' : 'Emit refused'}</h2>
            <p className={`pricing-receipt-sub${receipt.ok ? '' : ' pricing-ready-warn'}`}>
              {receipt.ok ? 'Written just now.' : 'The console below says why.'}
            </p>
          </div>
          <Button variant="ghost" size="sm" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="pricing-receipt-body">
          {!receipt.ok ? null : (
            <>
              <RunFiles run={run} files={receipt.files} only="import" />
              <ol className="pricing-errand">
                <li>
                  <span className="pricing-errand-n">1</span>
                  <span>Download the files above.</span>
                </li>
                <li>
                  <span className="pricing-errand-n">2</span>
                  <span>
                    In TCGplayer, <strong>Import to Staged</strong>, then <strong>Export From Staged</strong>.
                  </span>
                </li>
                <li>
                  <span className="pricing-errand-n">3</span>
                  <span>
                    Come back with that export and <a href="#/runs">reconcile on Runs</a>.
                  </span>
                </li>
              </ol>
            </>
          )}
          <button type="button" className="pricing-console-toggle" aria-expanded={consoleOpen || !receipt.ok} onClick={onToggleConsole}>
            <Icon name={consoleOpen || !receipt.ok ? 'chevronDown' : 'chevronRight'} size={14} />
            What emit printed
          </button>
          {consoleOpen || !receipt.ok ? (
            <pre className="pricing-ship-console" aria-label="What emit printed">
              {receipt.console}
            </pre>
          ) : null}
        </div>
      </div>
    </>,
    document.body,
  )
}

/** The hold popover, anchored to its row. Letters, not digits — the digits are price entry. */
function HoldPanel({
  sku,
  sheet,
  onSet,
  onCancel,
}: {
  sku: PricingSku
  sheet?: boolean
  onSet: (sku: PricingSku, reason: WithholdReason, watch: string, note: string) => void
  onCancel: () => void
}) {
  const [reason, setReason] = useState<WithholdReason>('bullish')
  const [watch, setWatch] = useState('')
  const [text, setText] = useState('')
  const chips = useRef(new Map<WithholdReason, HTMLButtonElement>())
  const panel = useRef<HTMLDivElement | null>(null)
  const [flip, setFlip] = useState(false)

  useEffect(() => {
    const head = WITHHOLD_REASONS[0]
    if (head !== undefined) chips.current.get(head)?.focus()
  }, [])

  // The popover opens downward off its row unless that would bury it under the sticky ship bar
  // or push it past the viewport; then it opens upward off the same row. Measured before paint.
  useLayoutEffect(() => {
    if (sheet) return
    const node = panel.current
    const row = node?.parentElement
    if (!node || !row) return
    const rowRect = row.getBoundingClientRect()
    const shipTop = document.querySelector('.pricing-ship')?.getBoundingClientRect().top ?? window.innerHeight
    const limit = Math.min(window.innerHeight, shipTop)
    const below = limit - (rowRect.bottom - 4)
    const above = rowRect.top + 4
    setFlip(node.offsetHeight > below && above > below)
  }, [sheet])

  return (
    <div
      ref={panel}
      className={`pricing-holdpanel bn-menu${sheet ? ' pricing-holdpanel-sheet' : ''}`}
      data-flip={flip ? 'up' : undefined}
      role="group"
      aria-label={`Hold ${sku.name}`}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault()
          onCancel()
          return
        }
        const typing = event.target instanceof HTMLInputElement && event.target.type === 'text' && event.target.dataset['note'] === 'true'
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
      <div className="pricing-holdpanel-head">
        <span className="pricing-holdpanel-title">
          <Icon name="lock" size={14} /> Hold back
        </span>
        <span className="pricing-holdpanel-name" title={sku.name}>
          {sku.name}
        </span>
      </div>
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
            <span className="pricing-hold-reason-label">{HOLD_SHORT[option]}</span>
            <Kbd>{WITHHOLD_KEYS[option].toUpperCase()}</Kbd>
            {WITHHOLD_LABELS[option] === HOLD_SHORT[option] ? null : <span className="bn-sr">{WITHHOLD_LABELS[option]}</span>}
          </button>
        ))}
      </div>
      <p className="pricing-holdpanel-says">{WITHHOLD_LABELS[reason]}</p>
      <div className="pricing-holdpanel-fields">
        <label className="bn-field">
          <span className="bn-field-label">Tell me when market is above $</span>
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
          <input
            className="bn-input"
            type="text"
            data-note="true"
            placeholder="why, in a few words"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
      </div>
      <div className="pricing-holdpanel-actions">
        <span className="pricing-holdpanel-fine">
          {/* A HOLD IS ONE ANSWER FOR THE WHOLE STORE (D86, amended 2026-09-02) and the fine
              print says so: it lives in `inventory/prices.json`, not in the run, so it
              outlives every run over this box rather than dying with the directory. */}
          Every copy stays out of every import file until you release it — one answer for the
          whole store, outliving every run over this box.
        </span>
        <Button variant="quiet" size={sheet ? 'lg' : 'sm'} onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" size={sheet ? 'lg' : 'sm'} icon="lock" onClick={() => onSet(sku, reason, watch, text)}>
          Hold it
        </Button>
      </div>
    </div>
  )
}
