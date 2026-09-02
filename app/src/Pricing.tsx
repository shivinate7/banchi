import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  describeFailure,
  getPriceHistory,
  getPriceTrends,
  emitMerged,
  getPricingCorpus,
  getPricingWorklist,
  putPricingCorpus,
  getRun,
  getRuns,
  photoUrl,
  runFileUrl,
  runStep,
  type Failure,
} from './server'
import type {
  DecisionsDocument,
  CorpusAnswer,
  MergedSku,
  RosterRun,
  PricingCorpus,
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
import { FLAT_KEY, FLOOR_CHOICE, OWED_LABELS, owed, subThresholdSkus } from './readiness'
import { PriceHistoryPanel, RANGE_LABEL, type HistoryRead } from './PriceHistory'
import { TrendCell, type TrendRead } from './PriceTrend'
import { RunFiles } from './RunFiles'
import { runBoxLabel } from './runScope'
import './Pricing.css'

/* HAND-PRICING, ON A ROUTE OF ITS OWN — D49, from an interview the owner asked for.
 *
 * They had never been asked what they wanted a listing price to BE: `match` on `market` was
 * the CLI default running by accident through every run this project has done. Their answer
 * was two sentences and both of them shape this file. *"I want all the data from the CSV
 * shown when I make the decision, but I actually intend to be hand-pricing for now"* — so
 * every export cell is on the row and nothing is summarised. And *"almost everything coming
 * next is all above 0.40"*, which inverts the only measurement anyone had: across the two
 * Pokemon runs on disk the total value of every per-item pricing decision available was
 * ZERO, and the next boxes are the other thing.
 *
 * SO THIS IS A WORKLIST, NOT A REPORT. It is built for a hundred real decisions in a
 * sitting, which is why the whole of the interaction is one unmodified keystroke per common
 * act and why the list is forbidden from moving under a finger.
 *
 * WHAT IT REFUSES TO BE. Not a second review queue: which card this is was settled upstream
 * by D3, D4 and D35, so this screen asks only what it is worth. Not a spreadsheet in the
 * sense `docs/DESIGN.md` names Collectr and Discogs by — the hierarchy is carried by the
 * sort and by the decimal point, and there are deliberately NO price type-size bands, since
 * `ReviewQueue.css`'s own comment calls its breakpoints a guess. Not a second answer to a
 * question another screen owns: the box, the cart and the money gate stay on `#/runs`
 * (D39, D48), and NOTHING HERE SPENDS.
 *
 * THE CLIENT PERFORMS NO ARITHMETIC ON MONEY. Every number it can put in a field came
 * pre-rounded out of `pricing.json`, which `cli/cmd_join.py` computed through
 * `pipeline/pricing.py` — the one place allowed to. Re-implementing `Rule.apply` +
 * `round_money` + `clamp_floor` here would put that module's rounding-before-clamping order
 * in two languages with nothing auditing the second.
 */

/** How long a receipt stands. A COUNT would be wrong here and a clock is right, which is the
 *  opposite of the review queue's ruling and for a reason that inverts cleanly: there, an
 *  answer is irreversible at the store and the window is the only way back. Here the write
 *  is `decisions.json`, `join` merges it and `emit` is free and re-runnable, so the receipt
 *  is a courtesy and the undo stack behind it is what matters. */
const UNDO_DEPTH = 10

/** How many SKUs one batched trend request asks about — D79.
 *
 *  IT IS A LATENCY NUMBER AND NOT A COURTESY ONE. The server sleeps `COURTESY_DELAY_SECONDS`
 *  between live fetches whatever the chunking, so this changes nothing the mirrors see; what
 *  it decides is how long the operator looks at an empty column. Eight SKUs is two ranges each
 *  — sixteen requests, about five seconds — so a 46-row box arrives as six waves instead of
 *  one 37-second blank. Larger wastes the wait; smaller pays a round trip per two cards. */
const TREND_CHUNK = 8

/** The three presets, matching `cli/cmd_join.py:PRESETS` key for key AND rule for rule. The
 *  owner chose these three and their percentages in the interview; a fourth is a change to
 *  that tuple and to this table, and to nothing else.
 *
 *  THE `rule`/`basis` PAIR IS HERE BECAUSE A PRESS HAS TO WRITE IT, and it is duplicated
 *  under the same guard D49 put on `WITHHOLD_REASONS`: `scripts/docs-audit.py`'s
 *  `pricing presets` row reconciles this table against that tuple and BLOCKS on a mismatch.
 *  `PUT /pipeline/runs/<name>/decisions` validates nothing, so two declarations agreeing is
 *  the only thing standing between this screen and a `decisions.json` that `emit` refuses.
 *
 *  It is not arithmetic and must never become arithmetic. `cli/cmd_join.py:PRESETS` prices
 *  every row in Python precisely so `Rule.apply` + `round_money` + `clamp_floor` are not
 *  re-implemented here; what travels is the NAME of a rule, which the pipeline then applies. */
/** A run's date, short, for the picker's headline. Null when there is no usable stamp.
 *
 *  THE HEADLINE IS `Box 1 · UNL Rares` AND A BOX GETS MORE THAN ONE RUN, so without this two
 *  buttons over one drawer are the same string and the only thing separating them is the run
 *  id in the meta line — which `docs/DESIGN.md`'s human-label-large rule deliberately draws
 *  small. Reported as "why does pricing show two box 1s".
 *
 *  DAY AND MONTH, NO CLOCK. Two runs over one box on one day is possible and this would not
 *  separate them; the run id underneath still does, and a timestamp in a headline spends the
 *  width that made the label readable in the first place. The year is omitted for
 *  `BoxBrowse.tsx:capturedAt`'s reason — every run on this machine is from this one, so
 *  printing it on all four says nothing. */
function runDay(stamp: string | null | undefined): string | null {
  if (typeof stamp !== 'string' || stamp.trim() === '') return null
  const at = new Date(stamp)
  if (Number.isNaN(at.getTime())) return null
  return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const PRESETS: { key: string; label: string; rule: string; basis: string; says: string }[] = [
  {
    key: 'market_match',
    label: 'Match market',
    rule: 'match',
    basis: 'market',
    says: 'The recent actual-sale average, matched exactly. What every run has done so far.',
  },
  {
    key: 'market_undercut_5',
    label: 'Market −5%',
    rule: 'undercut:5',
    basis: 'market',
    says: '5% under the recent actual-sale average, clamped at the $0.40 floor after rounding.',
  },
  {
    key: 'low_undercut_1',
    label: 'TCG Low −1%',
    rule: 'undercut:1',
    basis: 'low',
    says:
      '1% under the cheapest current listing, so you are the cheapest rather than tied with ' +
      'it. Rows with no TCG Low Price are left alone and named.',
  },
]

/** The four columns a letter key snaps the price to, in the order they are drawn. */
const SNAPS: { key: string; field: keyof PricingSku['snap']; label: string }[] = [
  { key: 'm', field: 'market', label: 'MARKET' },
  { key: 'l', field: 'low', label: 'LOW' },
  { key: 's', field: 'low_with_shipping', label: '+SHIP' },
  { key: 'd', field: 'direct_low', label: 'DIRECT' },
]

const SECTIONS: { bucket: PricingSku['bucket']; title: string; note: string }[] = [
  {
    bucket: 'listable',
    title: 'Listed',
    note: 'At or above the $0.40 threshold. These become import-listed.csv.',
  },
  {
    bucket: 'sub_threshold',
    title: 'Sub-threshold',
    note:
      'Below $0.40. The run-wide answer prices them unless you set one here; they become ' +
      'import-subthreshold.csv.',
  },
  {
    bucket: 'no_market_data',
    title: 'No market price',
    note:
      'The catalog carries no price for these. D9: a missing price is an unknown price, not ' +
      'a low one — emit refuses while any is unanswered.',
  },
]

/** THE ACCEPTED ALPHABET, CLOSED. `[0-9.]`, at most one dot, at most two digits after it.
 *  That closure is what makes every letter unambiguously a command rather than a character,
 *  which is the entire safety argument for a keyboard that works with the hands in a field. */
const PRICE = /^\d*(\.\d{0,2})?$/

function isWithheld(value: unknown): value is WithheldRecord | 'unlisted' {
  return value === 'unlisted' || (typeof value === 'object' && value !== null && 'withheld' in value)
}

function heldReason(value: WithheldRecord | 'unlisted'): string {
  return value === 'unlisted' ? '' : String(value.withheld ?? '')
}

/** Where a section's answer is written. THE WRITE TARGET IS A PROPERTY OF THE SECTION, NOT OF
 *  THE ROW, and getting it wrong ships a run `emit` refuses: a price typed on a
 *  `no_market_data` row and written to `overrides` WOULD price the card — `prices_for`
 *  short-circuits on the override — and would STILL block `emit`, because `blocking` reads
 *  `no_market_data` alone. The operator would be told to edit the file they had just
 *  edited. */
function targetOf(bucket: PricingSku['bucket']): 'overrides' | 'no_market_data' {
  return bucket === 'no_market_data' ? 'no_market_data' : 'overrides'
}

/** WHY THIS RUN ADDS NO ROW FOR THIS SKU, AS A HEADING — or null for the ordinary row that
 *  adds one. The sentence is `pipeline/join.py:SkuMatch.nothing_to_add` verbatim and is never
 *  reassembled here (D59); the fallback states the bare fact `at_cap` means, for a
 *  `pricing.json` an older join wrote with no sentence beside it.
 *
 *  IT IS A GROUP KEY AND NOT A ROW NOTE, which is the whole of the change. Every row that
 *  cannot add carried the same sentence in its own right margin — 51 SKUs deep, that is one
 *  sentence drawn twenty times down a list whose remaining rows are the ones with an answer
 *  still to give. Rows sharing a reason share a heading, and the reason is stated once.
 *
 *  THE SERVER SAYS WHY AND THE SCREEN DRAWS IT, WHICH IS THE PART THAT WAS PAID FOR. This
 *  sentence used to be "nothing to add this run — TCGplayer already holds {live_before}",
 *  composed on the client out of the export's live column alone — which reads 0 for every copy
 *  sitting on an import nobody has reconciled. Measured on the owner's store: 167 pushed copies
 *  across 72 SKUs, zero live and zero staged, and `live_before` reads 0 on every SKU of both
 *  runs on disk — so wherever it drew at all it read "TCGplayer already holds 0" under a row
 *  adding nothing BECAUSE TCGplayer was holding them. A row that stops appearing in an import
 *  file is close enough to the silent drop `CLAUDE.md` forbids that saying nothing would have
 *  beaten saying that.
 *
 *  THE FALLBACK IS NOT DEFENSIVE PADDING. This table is `pricing.json` READ OFF DISK, and a
 *  file an earlier join wrote carries `at_cap` with no sentence beside it — measured, both runs
 *  in `runs/` today. An older file states the bare fact, which is exactly what `at_cap` means,
 *  and invents no reason for it. Those rows group under it together, which is the honest
 *  reading: one heading over the cards this run adds nothing for and no claim as to why. */
function groupOf(sku: PricingSku): string | null {
  return sku.at_cap ? (sku.nothing_to_add ?? 'nothing to add this run') : null
}

/** THE HEADING OVER THE ROWS THE OPERATOR HAS ALREADY ANSWERED WITH A HOLD. The screen's own
 *  sentence and not the server's, because a hold is this screen's answer (D49) and
 *  `decisions.json` records the reason per SKU rather than one for the group — the machine
 *  token stays on each row, which is where a `withheld: bullish` is greppable from. */
const HELD_HEAD = 'held back from this run'

/** THE SKUs DRAWN AS HELD WHEN THE PAGE OPENED — a snapshot, taken in `load` and untouched
 *  until the next one, which is what makes a hold sink on the REOPENING and never under the
 *  hand that just pressed `H` (D28, D78).
 *
 *  READ THE WAY THE ROW READS IT, and that is why this walks the table rather than the two
 *  answer maps: `targetOf` decides which map a row's answer lives in, so a stale `overrides`
 *  key for a `no_market_data` SKU draws nothing and must sink nothing. The group and the word
 *  `Holding` are then the same test, run once each.
 *
 *  `'unlisted'` COUNTS, and it is not an edge case: it is the answer a `no_market_data` row
 *  takes to say this card is not being listed, it draws `Holding` in the price column exactly
 *  as a reasoned hold does, and it keeps the card out of the same import file. A group of rows
 *  that will not list is the honest set; one that took the reasoned half alone would leave the
 *  other half sitting among the unanswered rows looking like work. */
function heldOnArrival(
  rows: readonly PricingSku[],
  doc: DecisionsDocument,
): ReadonlySet<string> {
  const overrides = (doc.overrides ?? {}) as Record<string, unknown>
  const unpriced = (doc.no_market_data ?? {}) as Record<string, unknown>
  const out = new Set<string>()
  for (const row of rows) {
    const standing = targetOf(row.bucket) === 'overrides' ? overrides[row.sku] : unpriced[row.sku]
    if (isWithheld(standing)) out.add(row.sku)
  }
  return out
}

/** One thing the list draws: a heading, or a row. Discriminated on `head` because the two are
 *  SIBLINGS in the list rather than a heading owning a nested list of its own — the caption
 *  above them is a sibling of the rows for the same reason, and a wrapper would stop the rows
 *  being what the section's own grid template applies to. */
type Drawn = { head: string; count: number } | { head: null; sku: MergedSku }

/** One keystroke, and what the card was answered before it.
 *
 *  ONE VALUE AGAIN. It was a per-run map for as long as the answers were, and `undefined`
 *  still means the key was absent and undoing DELETES it — D49's rule for clearing an answer,
 *  since there is deliberately no delete verb anywhere for this. */
type Undo = {
  sku: string
  before: CorpusAnswer | undefined
  channel: 'price' | 'unknown'
}

/* ------------------------------------------------------- the corpus, as this screen (D86)
 *
 * ONE DOCUMENT, AND EVERY READER ON THIS SCREEN UNCHANGED. The answers used to be one
 * `decisions.json` per run, which is why this file briefly carried a merge, a fan-out write
 * and a conflict detector — machinery whose only job was to reconcile a duplication. The owner
 * retired the duplication instead: *"why is it we've made a federalist state system when this
 * is best done as a centralized system?"*
 *
 * `corpusAsDoc` IS THE WHOLE SEAM. `answers`, `unpriced`, the preset chips, the sub-threshold
 * controls and `owed` all read a `DecisionsDocument`, and they keep doing so — the corpus is
 * projected into that shape rather than every reader learning a new one. The projection is
 * one-way; writes go through `setAnswer` below, into the corpus.
 */

/** The corpus as the document every reader on this screen already understands.
 *
 *  THE TWO TABLES ARE KEPT APART BY `channel`, and that is not cosmetic:
 *  `pipeline/decisions.py:blocking` reads `no_market_data` ALONE to decide whether `emit` must
 *  refuse, and `app/src/readiness.ts` mirrors it. Route a hand-entered answer for a card the
 *  catalog has no price for through `overrides` instead and the price is still right while the
 *  gate stops being able to see it — a screen reporting nothing owed for a run `emit` refuses. */
function corpusAsDoc(book: PricingCorpus | null): DecisionsDocument {
  if (book === null) return {}
  const overrides: Record<string, unknown> = {}
  const unpriced: Record<string, unknown> = {}
  for (const [sku, answer] of Object.entries(book.skus ?? {})) {
    if (answer === null || answer === undefined) continue
    const table = answer.channel === 'unknown' ? unpriced : overrides
    table[sku] = answer.value
  }
  return {
    rule: book.policy?.rule,
    basis: book.policy?.basis,
    sub_threshold: book.policy?.sub_threshold ?? null,
    overrides: overrides as DecisionsDocument['overrides'],
    no_market_data: unpriced as DecisionsDocument['no_market_data'],
  }
}

/** Set or clear one card's answer, returning a NEW corpus.
 *
 *  `undefined` DELETES THE KEY and returns the row to its suggestion, which is D49's rule for
 *  clearing an answer — there is deliberately no delete verb anywhere for this. Every other key
 *  in the document is spread through untouched, so a hand-written `_note` and anything a later
 *  version adds survive a screen that has never heard of them. */
function setAnswer(
  book: PricingCorpus,
  sku: string,
  value: unknown,
  channel: 'price' | 'unknown',
): PricingCorpus {
  const skus = { ...(book.skus ?? {}) }
  if (value === undefined) delete skus[sku]
  else skus[sku] = { ...(skus[sku] ?? {}), value: value as never, channel }
  return { ...book, skus }
}

/** The run picker — a filter over the worklist since D86, and no longer a gate in front of it.
 *
 *  MULTI-SELECT, MIRRORING `Runs.tsx`'s BOX CART (D48). Nothing ever argued for the
 *  single-select this replaces: D49 defends where the run comes from — *"a picker here cannot
 *  disagree with anything"*, because `GET /pipeline/runs` is the single source — and says
 *  nothing about how many may be picked. A set over that same single source has the identical
 *  property. D39's one-mass-select rule is about CARDS and is untouched; `#/inventory` still
 *  owns the only one.
 *
 *  FOUR THINGS ARE PINNED BY `app/tests/pricing.spec.ts` AND ALL FOUR SURVIVE: one
 *  `.pricing-run` chip per joined run, `.pricing-run-name` exactly `runBoxLabel(row)`, an
 *  unnamed box drawing its number alone, and `.pricing-run-id` still carrying the full run
 *  directory. What is added is the fifth line the chip never had.
 *
 *  THE FIGURE IS A REMAINDER AND NOT A TOTAL. `counts.skus` is the SIZE of a job — box 2's
 *  109 SKUs are one `floor` press and box 3's 199 are 117 real decisions — so a picker
 *  drawing it could not answer the only question being asked of it. `owes` comes from
 *  `Decisions.blocking`, the Python that actually refuses an emit.
 *
 *  ASCENDING BY BOX, WHICH IS THE ORDER THE SHELF IS IN. `GET /pipeline/runs` sorts by
 *  directory name reversed, so within a day this drew box 5, box 4, box 3 — backwards against
 *  `Runs.tsx`'s stated rule, *"the order they sit on a shelf and the order the strip on
 *  `#/inventory` already draws"*. Date descending between days, because the newest sitting is
 *  the one being worked. */
function PickRuns({
  runs,
  picked,
  onToggle,
}: {
  runs: readonly RosterRun[]
  picked: ReadonlySet<string>
  onToggle: (run: string) => void
}) {
  const order = [...runs].sort((a, b) => {
    const day = (b.created_at ?? '').slice(0, 10).localeCompare((a.created_at ?? '').slice(0, 10))
    if (day !== 0) return day
    return (a.box ?? 0) - (b.box ?? 0) || a.run.localeCompare(b.run)
  })
  return (
    <div className="pricing-runs" role="group" aria-label="Which runs to price">
      {order.map((row) => {
        /* THE DRAWER LARGE, THE DIRECTORY SMALL BENEATH IT (D56). This chip drew the run name
           over a SKU count — a date, a box digit and a number — and the owner named it
           exactly: *"not just the date and the raw box number."* It is `docs/DESIGN.md`'s
           human-label-large, machine-string-small rule pointed at a picker: the box is what a
           person is choosing between, and the run directory is the greppable identity of the
           thing they are choosing.

           THE RUN NAME IS NOT DEMOTED OUT OF USEFULNESS, and it must not be. Two runs over
           one box draw the SAME headline — box 1 and box 3 both do this on the owner's store
           — so the second line is the only thing telling them apart.

           A RUN WITH NO BOX FALLS BACK TO ITS OWN NAME AS THE HEADLINE, rather than drawing
           an empty line above one. */
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
            <span className="pricing-run-name">
              {label ?? row.run}
              {label === null || day === null ? null : ` · ${day}`}
            </span>
            <span className="pricing-run-meta">
              {label === null ? null : <span className="pricing-run-id">{row.run}</span>}
              <span>{row.counts?.skus ?? '?'} SKUs</span>
            </span>
            {/* WHAT IS LEFT, OR THAT NOTHING IS. Both are worth a line: a run that owes
                nothing is the one an operator should not open, and before this the only way
                to learn that was to open it. */}
            <span className={`pricing-run-owes${row.open ? '' : ' pricing-run-done'}`}>
              {row.owes.length === 0 ? 'answered' : row.owes.join(' · ')}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** The runs named on the hash. `run` REPEATS rather than carrying a comma list, matching the
 *  wire (`getPricingWorklist`) and `/trends` behind it, for their reason: a comma inside a
 *  value is indistinguishable from the separator. A single `?run=` is the link `#/runs` has
 *  always written and still resolves to a worklist of one, so every URL made before D86 lands
 *  on exactly the screen it did. */
function runsInHash(): string[] {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).getAll('run').filter((name) => name !== '')
}

export function Pricing() {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  /** WHICH RUNS THE WORKLIST IS OVER, AND EMPTY MEANS "WHATEVER STILL HAS WORK IN IT".
   *
   *  THE EMPTY SET IS A REAL STATE AND NOT AN UNSET ONE, which is the whole shape of D86.
   *  `#/pricing` used to open on a picker and hold `run: string | null`, so the operator's
   *  first act on a screen built for *"a hundred real decisions in a sitting"* was always to
   *  answer a question — which box — that the pipeline can already answer for them. With no
   *  selection the server chooses every run that still owes something, so the screen opens on
   *  the work rather than on a menu. Picking runs NARROWS that; it no longer gates it.
   *
   *  A SET OF RUN NAMES, MIRRORING `Runs.tsx`'s `picked: ReadonlySet<number>` (D48). Same
   *  name, same shape, same toggle, and drawn in the server's order rather than the order
   *  they were ticked — selection order would make the picker and the list disagree about
   *  which run comes first for no reason anybody chose. */
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set(runsInHash()))
  const [work, setWork] = useState<PricingWorklist | null>(null)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  /** THE PRICING CORPUS — one document for the store, and the authority (D86, amended).
   *
   *  IT WAS A MAP KEYED BY RUN AND THE OWNER RETIRED THAT: *"why is it we've made a
   *  federalist state system when this is best done as a centralized system?"* A price is a
   *  fact about a SKU, so one stored per run meant one answer per drawer a card had been
   *  photographed in — 66 SKUs on this machine, 8 answered twice, 3 of those a hold overridden
   *  by a later price. `doc` below is a `DecisionsDocument`-shaped READ of this, which is what
   *  lets every reader on this screen stay exactly as it was.
   *
   *  THE FAN-OUT WRITE IS GONE WITH IT. `write` sets one key here and one `PUT /pricing`
   *  follows; there is no second file for it to disagree with. */
  const [book, setBook] = useState<PricingCorpus | null>(null)

  /** The merged press: whether it is sending, and whether the operator wants only the
   *  above-threshold rows. `listedOnly` is the owner's checkbox — *"i can hit a checkmark to
   *  export just the valuable cards (splitting off the threshold ones) otherwise it defaults
   *  to all"* — so the default is everything and the split is opt-in. */
  const [sendingAll, setSendingAll] = useState(false)
  const [listedOnly, setListedOnly] = useState(false)

  /* TOGGLING A RUN NARROWS OR WIDENS THE WORKLIST, and un-ticking the last one returns it to
     "everything unpriced" rather than to an empty screen. The empty set is the default state
     and means the server chooses, so there is no way to arrive at a deliberately blank
     worklist by pressing chips — which is the state that would look like a bug. */
  const toggleRun = useCallback((name: string) => {
    setPicked((held) => {
      const now = new Set(held)
      if (now.has(name)) now.delete(name)
      else now.add(name)
      return now
    })
  }, [])
  const [saving, setSaving] = useState(false)
  const [undo, setUndo] = useState<Undo[]>([])
  const [holdFor, setHoldFor] = useState<string | null>(null)

  /* THE HOLDS AS THE SERVER LAST HANDED THEM OVER. State and not a memo over `doc`: the whole
   * property is that it does NOT track the document the operator is editing. */
  const [sunkHolds, setSunkHolds] = useState<ReadonlySet<string>>(() => new Set())
  const [photoFor, setPhotoFor] = useState<{ sku: string; at: number } | null>(null)

  /* ------------------------------------------------------------- the price history (D62)
   *
   * TWO WAYS IN, AND WHAT SEPARATES THEM IS WHAT ENDS THEM. `peek` is the HELD one: point at
   * a row, hold `t`, and the panel stands for exactly as long as the key is down. `pinned` is
   * the `T` button's click and the panel's own Keep, and it stands until it is closed. The
   * owner asked for the first on 2026-08-31 and gave the gesture whole — "it holds as my
   * cursor moves as long as i hold T, and then as soon as i release it goes away" — because
   * the reading is worth having on a card being weighed and the panel outliving the glance
   * is the part that grates.
   *
   * `peek ?? pinned` RATHER THAN ONE SLOT, SO A GLANCE CANNOT SPEND A PIN. An operator holding
   * one card open who points at another row and holds `t` gets that row for the hold and their
   * own card back on the release. One slot would have handed the pin to whatever was glanced
   * at last, and a pin quietly re-aimed is worse than no pin: the panel prints its SKU, so it
   * would not be WRONG on screen, merely no longer the card the operator asked about.
   *
   * NEITHER ONE FOLLOWS FOCUS, which is the property D62 closed structurally rather than with
   * a debounce: a reading is a request to two public mirrors, so a panel re-read on the
   * focused row would fire one request per arrow key — fifty for a walk down this list, at a
   * free mirror, for readings nobody asked for. Nor does either follow the POINTER: pointing
   * at a row asks for nothing at all, and only the press reads. */
  const [pinned, setPinned] = useState<string | null>(null)
  const [peek, setPeek] = useState<string | null>(null)
  const historyFor = peek ?? pinned
  /* Every reading this session has taken, by SKU. Kept across closes so re-opening a card is
   * free, and NOT cleared when the run changes: a SKU's sales history is a fact about the
   * card rather than about the run that priced it, so the same reading is correct on any run
   * that matched it. The server's own on-disk cache (`pipeline/pricehistory.py`'s TTLs) is
   * what decides staleness; this only avoids asking it twice in one sitting. */
  const [history, setHistory] = useState<Record<string, HistoryRead>>({})

  /* ---------------------------------------------------------------- the trend strip (D79)
   *
   * D62 MADE THE HISTORY A PRESS PER CARD AND NAMED WHAT WOULD REOPEN IT — *"the panel being
   * opened on every card… the honest answer is a batched route and a column on the row"*. The
   * owner asked for that on 2026-08-31. This is the state behind that column, and it is
   * SEPARATE from `history` above rather than a widening of it: the two carry different
   * payloads for different drawings, and merging them would put the panel's every-figure
   * reading and the row's shape-and-sign in one bag whose shape neither consumer could trust.
   *
   * IT IS KEYED BY RUN AND CLEARED WHEN THE RUN CHANGES, which is the opposite of `history`
   * above and correct for the opposite reason. A reading is a fact about a CARD, so it is
   * kept across runs. This is a reading over a run's OPEN rows — which rows those are is a
   * fact about the run — so a strip carried across a run change would draw the last run's
   * answer set against this run's list. */
  const [trends, setTrends] = useState<Record<string, TrendRead>>({})
  const [trendRun, setTrendRun] = useState<{
    run: string
    /** How many rows the walk will ask about, and how many it has heard back on. The row
     *  strip fills in waves and this is what lets the screen say so — 37.7s of courtesy delay
     *  arriving as six partial answers rather than one blank half-minute. */
    total: number
    done: number
    /** The rows never asked about: this run can add nothing for them, so the batch skips them
     *  on the owner's instruction. COUNTED rather than hidden — a strip drawn over 46 of 60
     *  rows with no number beside it reads as fourteen failures. */
    skipped: number
    /** The two ranges' spans, off the first answer that carried them. STATED ONCE HERE and
     *  never on a row: they are identical across every SKU of a run (measured, all 46 on
     *  `2026-08-31-box3-01`), and a row has no width for a date. */
    spans: TrendRange[] | null
    reading: boolean
  } | null>(null)
  /* WHICH WALK IS LIVE. A run change or a second press abandons the one in flight, and every
   * chunk checks this before it writes — without it, a walk started over run A keeps filling
   * the strip after the operator has moved to run B, one chunk at a time, for half a minute.
   * A ref and not state: nothing draws it, and a re-render per chunk boundary is already paid
   * for by the answer that chunk carries. */
  const trendWalk = useRef(0)
  const [note, setNote] = useState<{ sku: string; text: string } | null>(null)
  const [filterHeld, setFilterHeld] = useState(false)

  /* ------------------------------------------------------------------ shipping this run (D54)
   *
   * `emit`'s press and its import CSVs live HERE now, on the screen where every answer it
   * refuses without is made. `#/runs` keeps the step's head, its note and a link over, so the
   * pipeline still reads as four parts.
   *
   * `detail` IS REQUIRED, NOT DECORATIVE: once the import rows leave `#/runs`, an
   * already-emitted run's CSVs are reachable from no screen at all without it. NO POLL —
   * `RunPanel` polls because a run STARTS live, and this screen is entered on one that has
   * finished; a poll here would re-render a hundred rows to bookkeep a file list. */
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [ship, setShip] = useState<'idle' | 'waiting' | 'sending'>('idle')
  const [receipt, setReceipt] = useState<{
    ok: boolean
    console: string
    files: readonly RunFile[]
  } | null>(null)
  /* ITS OWN TROUBLE STATE. `failure` already has two owners — the load and the save — and a
     third would let a save success clear an emit error out from under the operator. */
  const [shipTrouble, setShipTrouble] = useState<Failure | null>(null)
  const [flatOpen, setFlatOpen] = useState(false)
  const [armed, setArmed] = useState(false)

  const inputs = useRef(new Map<string, HTMLInputElement>())
  /* THE DOCUMENT THE SERVER LAST CONFIRMED, AND IT IS WHAT `dirty` IS MEASURED AGAINST.
   * `dirty` was a flag, and a flag cannot tell "the write I just sent" from "the write that
   * landed while it was in flight" — so clearing it on a response threw away whatever had
   * been typed since that response left. Comparing the object identity instead makes the
   * coalescing promise below structural: a write clears the state only for the exact
   * document it carried, and anything typed during the flight is still unequal when it
   * lands, so the effect runs again.
   *
   * Refs and not state: nothing here draws, and the save loop must not re-render a hundred
   * rows to bookkeep itself. */
  /** Which worklist fetch is live — see `load`. */
  const loadWalk = useRef(0)

  /** WHAT THE SERVER LAST CONFIRMED. `dirty` is a comparison against this rather than a flag,
   *  so it cannot be cleared for a write that did not carry the answer. */
  const savedBook = useRef<PricingCorpus | null>(null)
  /* ONE PUT IN FLIGHT. A boolean again: there is one document, so there is one write, and the
   * per-run `Set` this briefly was existed only because there were eight files.
   *
   * This was the `saving` STATE, read inside the effect — which put
   * `saving` in the dependency list, so raising it re-ran the effect, and the re-run's
   * CLEANUP set the in-flight closure's `live` to false. The response then landed on a dead
   * closure: neither the clear nor `setSaving(false)` ever fired, so the indicator read
   * `saving…` for the rest of the session, on every save, from the first one. The guard has
   * to be a value the effect can read without depending on it. */
  const inFlight = useRef(false)
  /* THE DOCUMENT A WRITE FAILED ON, so a refused PUT is not retried in a spin. `dirty` stays
   * true after a failure — correctly, the server does not have these answers — and without
   * this the effect would re-fire the moment `saving` went false, forever. The next keystroke
   * makes a new document and the retry happens then. */
  const failedBook = useRef<PricingCorpus | null>(null)
  /* WHICH FIELDS HAVE BEEN TYPED INTO THIS SESSION, and it has to be its own fact rather than
   * derived from whether an answer is stored. The first draft asked "is there a committed
   * answer for this SKU?" and cleared the field when there was not — so it cleared on EVERY
   * keystroke, not just the first, and typing `4.50` left `0` in the field. The clear is a
   * one-shot per field and the only thing that knows it has fired is this.
   *
   * A ref and not state: it must not re-render a hundred rows on the first character of a
   * price, and nothing draws from it. */
  const touched = useRef(new Set<string>())

  /* THE RUN COMES FROM THE HASH OR FROM THE PICKER, AND NEVER FROM STORAGE. D39's handoff
     exists because `#/inventory`'s mass-select is the only one in the product and a second
     would be two answers to "which cards". A run name has no such property — `GET
     /pipeline/runs` reads the runs directory and is the single source — so a picker here
     cannot disagree with anything, and `#/runs` links a specific run through the URL rather
     than through a second `sessionStorage` key with its own clearing rules. */
  useEffect(() => {
    /* THE MOUNT READ IS THE `useState` INITIALISER ABOVE AND NOT THIS EFFECT, WHICH IS A
       CORRECTNESS FIX RATHER THAN A TIDY-UP. Reading it here meant the screen mounted with an
       empty selection, fired a load for "everything unpriced", then set `picked` from the hash
       and fired a SECOND load — two responses in flight over one mount. Whichever landed last
       won `docs`, but `savedDocs` is a ref written outside React's batching, so a render could
       see the first load's documents against the second load's saved marker. They compare
       unequal, `dirty` goes true with nothing typed, and the screen PUTs a document the
       operator never touched — the one write D49 calls the load-bearing absence of this whole
       screen. Caught by the snap case, which asserts a letter press writes nothing.

       This listener now handles only what it is named for: the hash CHANGING while the screen
       is mounted, which is `#/runs` linking a specific run at a screen already open. */
    const fromHash = () => {
      const named = runsInHash()
      if (named.length > 0) setPicked(new Set(named))
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

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

  /** Fetch the worklist and seed a document per run. One request whatever the run count.
   *
   *  ONE ROUTE RATHER THAN N FETCHES, which is D86's own argument and not an optimisation.
   *  The default landing is every open run — eight tables and ~909KB on this machine — and
   *  two of them fetched either side of a `join` describe different worlds. `GET
   *  /pipeline/pricing` reads them together for the reason `do_pipeline_pricing` already
   *  reads one run's two files together. */
  const load = useCallback(async (wanted: ReadonlySet<string>) => {
    /* THE TREND STRIP IS THE LOADED SET'S AND DIES WITH IT (D79). `history` above
       deliberately survives a reload — a card's sales history is a fact about the CARD — but
       the strip is a reading over the rows still wanting an answer, and which rows those are
       is a fact about what is loaded. Abandoning the walk is the other half: a chunked read
       started over the old set would otherwise keep filling the new one's column, one chunk
       at a time, for the rest of the half-minute. */
    trendWalk.current += 1
    setTrends({})
    setTrendRun(null)
    setLoading(true)
    /* WHICH LOAD IS LIVE. Two selections in quick succession are two requests, and the slower
       one must not land on top of the faster: it would seat `docs` and `savedDocs` for a
       worklist the screen is no longer showing. The trend walk one line up has had this guard
       since D79 and for the same reason; this is the same shape over the table itself. */
    loadWalk.current += 1
    const mine = loadWalk.current
    try {
      // TWO READS, ONE MOMENT. The worklist says which cards are in front of the operator;
      // the corpus says what has been decided about them. Fetched together so a render can
      // never draw one against the other's world — the same argument `do_pipeline_pricing`
      // makes for reading a run's two files in one handler, one level up.
      const [answer, held] = await Promise.all([
        getPricingWorklist([...wanted].sort()),
        getPricingCorpus(),
      ])
      if (mine !== loadWalk.current) return
      setWork(answer)
      setBook(held.corpus)
      setSunkHolds(heldOnArrival(answer.skus, corpusAsDoc(held.corpus)))
      savedBook.current = held.corpus
      failedBook.current = null
      setFailure(null)
      setUndo([])
      setReceipt(null)
      setArmed(false)
      setShipTrouble(null)
      /* THE RUN'S FILES AND ITS PHASE — ONLY WHERE THERE IS ONE RUN. `emit` is per run (D48)
         and so is everything this detail feeds; a worklist over several has no single answer
         to "which files", and drawing one run's would be a caption over the wrong list. Its
         own try, and its own trouble state: a failure here must not blank the pricing table,
         which is the thing this screen is for. */
      if (answer.runs.length === 1) {
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
      setBook(null)
      setSunkHolds(new Set())
      setFailure(describeFailure(err))
    } finally {
      if (mine === loadWalk.current) setLoading(false)
    }
  }, [])

  /* THE WORKLIST LOADS ON ARRIVAL, WITH NO SELECTION AND NO PRESS. That is the change D86
     is: an empty `picked` is a real question — "what still has pricing in it" — and the
     server answers it, so a screen built for a hundred decisions in a sitting stops opening
     on a menu. Re-runs whenever the selection changes, which is what makes the picker a
     filter over the list rather than a gate in front of it. */
  useEffect(() => {
    void load(picked)
  }, [picked, load])

  /** The runs actually drawn, in the server's order — ascending by name and so by date.
   *  This and never `picked`: with no selection the server chose, and every fan-out, every
   *  merge and every write walks what came back rather than what was asked for. */
  const loaded = useMemo(() => (work?.runs ?? []).map((row) => row.run), [work])

  /** The one run, where there is one. `null` for a worklist over several, which is what
   *  disables `emit` and the run's file list without either of them needing to ask how many
   *  runs there are: `emit` is per run (D48), so a press that had to choose between eight
   *  would be the cross-run over-push this screen exists to surface. */
  const run = loaded.length === 1 ? (loaded[0] as string) : null

  /** The corpus as the document every reader here already understands. Read-only; writes go
   *  through `write` below, into the corpus itself. */
  const doc = useMemo(() => corpusAsDoc(book), [book])

  /* UNSAVED IS A COMPARISON, NOT A FLAG: the document on screen is not the document the
     server confirmed. Derived rather than stored so it cannot be cleared for a write that
     did not carry it.

     COMPUTED INLINE AND DELIBERATELY NOT MEMOISED, WHICH IS THE ONE THING THIS LINE CANNOT
     DO. `savedBook` is a REF, so it changes without a render — that is the whole reason it is
     a ref, and it is what the completion of a write updates. A `useMemo` over it therefore
     never recomputes when a write LANDS: the screen stayed dirty after the PUT succeeded and
     the effect below re-fired on its own `saving` dependency forever. Measured as an endless
     unsaved → saving… → unsaved oscillation against the three race cases this file pins. A
     plain boolean recomputed every render reads the ref fresh and is stable by VALUE, which is
     what the effect's dependency needs. */
  const dirty = book !== null && book !== savedBook.current

  /* ONE PUT IN FLIGHT, COALESCING. The route replaces the document wholesale, so the screen
     round-trips every key it does not understand — including `_note` and anything a later
     version of `decisions.py` adds. A commit schedules a write; a change during one re-runs
     when it lands — which is now true of this loop rather than merely intended, because the
     write clears only the document it sent. */
  useEffect(() => {
    /* ONE ANSWER, ONE PUT — and this is what centralising the corpus bought at the write path.
       It was one PUT per run holding the card, over N documents that could disagree; there is
       one document now, so there is one write and nothing to reconcile after it. */
    if (!dirty || book === null) return
    if (inFlight.current || book === failedBook.current) return
    const sent = book
    inFlight.current = true
    setSaving(true)
    void (async () => {
      try {
        await putPricingCorpus(sent)
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
    /* `saving` IS IN THE LIST TO RE-FIRE THE EFFECT WHEN A WRITE LANDS, AND IT IS ONLY SAFE
       THERE BECAUSE THE GUARD IS A REF. Everything the completion changes is a ref — the saved
       document and the in-flight flag — so a re-render is the only thing that can ask "is there
       more to send?", and lowering `saving` is that re-render. What made this dependency a
       hazard before was the CLEANUP: the effect owned an in-flight closure, so the extra run
       tore that closure down mid-write and the response landed on a dead one. There is no
       cleanup now, the early return above is what the extra runs hit, and the write outlives
       every one of them. */
  }, [dirty, book, saving])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty || saving) event.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty, saving])

  /* ------------------------------------------------------------------- shipping this run (D54) */

  /** What pricing still owes, recomputed live from the document on screen — never fetched.
   *  See `app/src/readiness.ts` for why this is a second implementation and what audits it. */
  const owes = useMemo(
    () => owed(doc, subThresholdSkus(work?.skus ?? [])),
    [doc, work],
  )

  /** What THIS RUN'S JOIN sent to review, from the run list already in hand. Zero new fetches.
   *
   *  IT IS A JOIN-TIME FIGURE AND THE COPY SAYS SO. `counts` is written by `join` and nothing
   *  rewrites it until the next one, so it goes stale the instant the operator answers a card
   *  — stale in the "there is more to do" direction, which is the one `_queue_depth` forbids
   *  claiming as live. Worded as what the join sent rather than what remains, it is a fact
   *  about the run and stays true. The live depth is `GET /status`, and it is not per-run. */
  const queued =
    runs.find((row) => row.run === run)?.counts?.queued_main ?? 0

  /** Whether this run has already written import rows. Derived, newest evidence first — the
   *  receipt from a press this session, then the manifest, then the phase. All three are on
   *  the wire already, and `_phase` reads the same manifest key, so the guard survives even a
   *  record written by an older checkout. */
  const emitted =
    receipt?.ok === true ||
    Boolean(detail?.manifest?.emitted) ||
    detail?.phase === 'reconcile' ||
    detail?.phase === 'done'

  /** Set the run-wide sub-threshold answer. THE LITERALS COME FROM `readiness.ts`, never from
   *  a label: `pipeline/decisions.py` compares with a bare `==` and does no trim or case
   *  fold, so a value derived from a button's text is a `MalformedDecisions` at the next join.
   *
   *  The spread is what round-trips `_note`, `rule`, `basis`, `overrides` and every key a
   *  later `decisions.py` adds — `PUT .../decisions` replaces the document wholesale and
   *  validates nothing, so this is the only thing standing between a press and a lost block. */
  const setSubThreshold = useCallback(
    (answer: string | { flat: string } | null) => {
      /* ONE PRESS, ONE ANSWER, FOR THE WHOLE STORE. It was one write per loaded run, over
         files that could disagree — the 2026-09-01 sitting answered `sub_threshold` three
         times in eleven minutes and gave two different answers. The policy is the corpus's
         now; a lot that genuinely wants its own keeps a per-run override, which is D48's
         argument surviving in the one place it is actually about. */
      setBook((current) =>
        current === null
          ? current
          : { ...current, policy: { ...current.policy, sub_threshold: answer } },
      )
    },
    [],
  )

  /* THE PRESS SEQUENCES RATHER THAN GATING ON `dirty`, AND THIS IS THE WRITE RACE CLOSED.
   *
   * The common gesture is type a price, then press emit. The click blurs the field, which
   * commits and calls `setDoc`; the handler then runs in the SAME event with the old `doc` in
   * its closure, so a POST fired there emits against the file as it was before the last
   * answer. Gating on `dirty` is not the fix — it is true from the first keystroke until the
   * PUT lands, so the button would flicker on every commit.
   *
   * Instead the press raises `waiting`. React batches that with the blur's `setDoc`, so the
   * very next render carries BOTH the new document and the waiting state, and this effect —
   * declared AFTER the save effect, so it runs after it — waits for the save loop to go
   * quiet. The render that releases it is the one the save loop already documents as its only
   * signal: the write's `finally` lowering `saving`. It rides an existing mechanism rather
   * than adding one. */
  useEffect(() => {
    if (ship !== 'waiting' || run === null) return
    if (book !== null && failedBook.current === book) {
      // THE SAVE LOOP DELIBERATELY STOPS RETRYING A REFUSED DOCUMENT, so without this the
      // wait would never end. Emitting against answers the server does not have would be
      // worse than saying so.
      setShip('idle')
      setShipTrouble({
        code: 'answers_not_saved',
        message:
          'Your answers could not be saved, so nothing was emitted. Fix the error above and ' +
          'the next keystroke will retry the save.',
      })
      return
    }
    /* A BOOLEAN AGAIN. It was briefly one entry per run, and an empty `Set` is TRUTHY — so
       this guard, written against the boolean, went from "a write is in flight" to "always"
       and the emit press silently did nothing at all. Caught by four cases in this file that
       had been green for the whole life of the boolean; recorded here because the corpus made
       it a boolean again and the trap would be re-set by anything that makes it a collection. */
    if (dirty || saving || inFlight.current) return
    setShip('sending')
    void (async () => {
      try {
        const result = await runStep(run, 'emit')
        setReceipt({ ok: result.ok, console: result.console, files: result.files })
        // NO REFETCH: the step reply carries both the files and the new summary.
        setDetail((current) =>
          current === null ? current : { ...current, ...result.summary, files: result.files },
        )
        setShipTrouble(null)
        setArmed(false)
      } catch (err) {
        setShipTrouble(describeFailure(err))
      } finally {
        setShip('idle')
      }
    })()
  }, [ship, dirty, doc, book, run, saving])

  /** Write one answer, pushing the previous value — including its ABSENCE — onto the undo
   *  stack. Recording absence is what lets an undo DELETE a key and return the row to its
   *  suggestion, rather than writing the suggestion into the file. Writing a suggestion is
   *  the one thing this screen may never do: an override is layer 1 of the ladder and beats
   *  the rule at layer 4, so a screen that wrote all 108 suggestions would produce a run
   *  where changing the preset silently changed nothing. */
  const write = useCallback(
    (sku: string, bucket: PricingSku['bucket'], value: unknown) => {
      /* ONE ANSWER, ONE KEY, AND NO FAN-OUT — which is the amendment to D86 as it lands in
         this function. It briefly wrote the same value into every run holding the card,
         because the answer lived in each run's own `decisions.json`; the owner retired that
         shape and the corpus keys by SKU, so a card has one answer by construction. The
         conflict this file used to detect and draw cannot occur.

         THE UNDO REMEMBERS THE PREVIOUS VALUE, INCLUDING ITS ABSENCE. Recording absence is
         what lets an undo DELETE the key and return the row to its suggestion rather than
         writing the suggestion into the file — which is the one thing this screen may never
         do: an override is layer 1 of the ladder and beats the rule at layer 4, so a screen
         that wrote its hundred suggestions would produce a run where changing the preset
         silently changed nothing. */
      const channel: 'price' | 'unknown' =
        targetOf(bucket) === 'no_market_data' ? 'unknown' : 'price'
      setBook((current) => {
        if (current === null) return current
        return setAnswer(current, sku, value, channel)
      })
      setUndo((stack) =>
        [{ sku, before: book?.skus?.[sku], channel }, ...stack].slice(0, UNDO_DEPTH),
      )
    },
    [book],
  )

  /** Every box the loaded runs touch, for the header's count. Ascending, deduped. */
  const boxesLoaded = useMemo(
    () => [...new Set((work?.runs ?? []).map((row) => row.box).filter((box) => box !== null))]
      .sort((a, b) => (a as number) - (b as number)),
    [work],
  )
  const table = work?.skus ?? null
  /* MEMOISED BECAUSE `?? {}` BUILDS A NEW OBJECT EVERY RENDER, and both of these are read as
     dependencies rather than as values — `answerFor` and `held` below, and the key handler
     through them. Unmemoised they defeated every memo downstream: `answerFor` was rebuilt on
     every paint, so `onKey` was too, so the whole chain memoised nothing while looking as
     though it did. Found by `react-hooks/exhaustive-deps` on the day it was switched on.

     `[doc]` and not `[doc?.overrides]`: the document is replaced wholesale on every write
     (see the autosave effect), so the narrower key would be a second way of saying the same
     thing and a third thing to keep in step. */
  const answers = useMemo(
    () => (doc?.overrides ?? {}) as Record<string, unknown>,
    [doc],
  )
  const unpriced = useMemo(
    () => (doc?.no_market_data ?? {}) as Record<string, unknown>,
    [doc],
  )

  const rows = useMemo(() => table ?? [], [table])

  /** THE LIST AS IT IS DRAWN, SECTION BY SECTION, AND THE ONLY PLACE THAT ORDER IS DECIDED.
   *
   *  A ROW THAT WANTS NOTHING FROM THE OPERATOR SINKS. `cli/cmd_join.py` writes
   *  `pricing.json` market-descending and that stands — inside every group it is untouched —
   *  but a SKU whose every copy is already listed, or one already answered with a hold, is not
   *  a decision this run is waiting on, and at the top of the section it puts the run's most
   *  expensive non-questions in front of the operator's eye. Three tiers, in the order the
   *  operator asked for them: the rows that still want a price, then the ones they have
   *  already held, then the ones this run can add nothing for at all.
   *
   *  THE SUNK TIER IS THE DEEPER FACT WHERE A ROW IS BOTH. A held row that is ALSO at the cap
   *  goes under the cap's heading, because the hold changes nothing about a SKU this run was
   *  never going to add a row for — and its `withheld` token still draws beside it, so the
   *  hold is not lost by being outranked.
   *
   *  THE CAP TIER IS GROUPED BY THE SENTENCE, IN FIRST-APPEARANCE ORDER, and there are three
   *  of them (D59): every copy gone, at the cap, or held by an import this pipeline has not
   *  seen land. They have three different remedies, so they are three headings and never one
   *  bucket of leftovers. `Map` insertion order is what orders them — an alphabetical or
   *  count-based rule would be a second opinion about importance that nothing here has grounds
   *  for. The hold tier is ONE heading over all of them, because the reason is per SKU and
   *  already drawn on the row.
   *
   *  D28 IS WHY THIS IS SAFE AT ALL, AND IT IS WHY THE HOLDS COME FROM A SNAPSHOT. The list
   *  must not move under a finger already travelling to the next field. `bucket`, `at_cap` and
   *  `nothing_to_add` are written by the join and read off disk, so they cannot move a row
   *  mid-session at all; a hold is this screen's own answer and could, so `sunkHolds` is the
   *  set as it stood when the page opened and a press of `H` does not move the row under the
   *  hand that pressed it. It sinks on the reopening, which is what the owner asked for.
   *
   *  SO A ROW CAN OUTLIVE ITS GROUP FOR ONE SESSION, and that is the trade taken deliberately:
   *  release a hold and the row keeps its place under the heading until the next load, drawing
   *  a price field. The row tells the truth about itself; the heading says why the group is
   *  there. The alternative is the list moving under the release, which D28 closed. */
  const sections = useMemo(
    () =>
      SECTIONS.map((section) => {
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
        return { ...section, total: inSection.length, items }
      }).filter((section) => section.total > 0),
    [rows, sunkHolds],
  )

  /** Every drawn row's SKU, top to bottom, across every section — what Enter and the arrows
   *  step through.
   *
   *  IT IS THE DRAWN ORDER AND NOT `rows`, AND THE TWO AGREED UNTIL THE GROUPS SANK.
   *  `cli/cmd_join.py` sorts the wire market-descending with `None` last, which happens to put
   *  the three buckets in the three sections' own order — so stepping the wire array walked the
   *  screen by coincidence, and this array was `rows.map` for as long as that held. Sinking a
   *  group moves a row within its section and ends it: the advance reads what is drawn, rather
   *  than a second sequence that has to keep agreeing with it. */
  const order = useMemo(
    () =>
      sections.flatMap((section) =>
        section.items.flatMap((item) => (item.head === null ? [item.sku.sku] : [])),
      ),
    [sections],
  )

  /** What the strip has actually got, for the one line above the list that says so. Counted
   *  rather than tracked: `trends` IS the record, and a second counter kept in step with it
   *  would be a second answer to the same question. */
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
    (sku: PricingSku): unknown =>
      targetOf(sku.bucket) === 'overrides' ? answers[sku.sku] : unpriced[sku.sku],
    [answers, unpriced],
  )

  const held = useMemo(
    () => rows.filter((sku) => isWithheld(answers[sku.sku])),
    [rows, answers],
  )

  const move = useCallback(
    (sku: string, by: number) => {
      const at = order.indexOf(sku)
      const next = order[at + by]
      if (next === undefined) return
      const field = inputs.current.get(next)
      field?.focus()
      field?.select()
      // `nearest` AND NOT `center`: D28's finding is that the list must stop MOVING, and
      // scrolling on every advance — including when the next row is already on screen — is
      // that defect re-introduced by the fix for it.
      field?.scrollIntoView({ block: 'nearest' })
    },
    [order],
  )

  const commit = useCallback(
    (sku: PricingSku, raw: string) => {
      /* AN UNTOUCHED FIELD COMMITS NOTHING, which is what makes Tab safe. A held Tab through a
       * hundred rows blurs a hundred fields, and a blur that wrote would turn every one of
       * those suggestions into an override — layer 1 of the ladder, beating the run's rule at
       * layer 4, so the next preset press would silently change nothing. Focus is not a
       * decision and neither is leaving a field you did not type in. */
      if (!touched.current.has(sku.sku)) return
      const text = raw.trim()
      // EMPTY CLEARS AND RETURNS THE ROW TO ITS SUGGESTION. It is not zero and it is not a
      // hold; `null` in `overrides` is dropped by the next join, which is how a key is
      // removed without inventing a delete verb.
      write(sku.sku, sku.bucket, text === '' ? undefined : text)
      touched.current.delete(sku.sku)
    },
    [write],
  )

  const snap = useCallback(
    (sku: PricingSku, field: keyof PricingSku['snap']) => {
      const value = sku.snap[field]
      const input = inputs.current.get(sku.sku)
      if (value === null) {
        // A SNAP ONTO A BLANK COLUMN REFUSES AND SAYS SO. Writing "" would reach `_price` in
        // `decisions.py` and raise at the next join, an hour later. Measured: Direct Low is
        // blank on 2,060 of 2,476 listable rows, so this is the common case, not the edge.
        setNote({ sku: sku.sku, text: `this row has no ${field.replace(/_/g, ' ')}` })
        return
      }
      if (input) input.value = value
      // A SNAP IS A DELIBERATE ACT ON THIS ROW, so it counts as having touched the field —
      // otherwise the value it set would be discarded unwritten by the very next blur.
      touched.current.add(sku.sku)
      setNote(null)
    },
    [],
  )

  /** The suggestion a row opens carrying.
   *
   *  `rule_price` WAS COMPUTED BY THE LAST JOIN AND CAN BE STALE (D54). Pressing a preset now
   *  writes `rule`/`basis` into the document, and `pricing.json` is not rewritten until the
   *  next join — so a screen that only ever read `rule_price` would say `decisions.json`
   *  prices at `undercut:5` while every suggestion on it showed `match`. Where the document's
   *  pair matches a served preset, that preset's own per-SKU figure is the honest suggestion.
   *
   *  STILL NO ARITHMETIC ON MONEY: both numbers came pre-rounded out of `pricing.json`, which
   *  `cli/cmd_join.py:_preset_prices` computed through `pipeline/pricing.py`. `join` already
   *  prices all three presets per SKU, which is why this costs a lookup rather than a rule.
   */
  const suggestionFor = useCallback(
    (sku: PricingSku): string => {
      const match = PRESETS.find((p) => p.rule === doc?.rule && p.basis === doc?.basis)
      if (match !== undefined) return sku.presets[match.key] ?? ''
      return sku.rule_price ?? ''
    },
    [doc],
  )

  const applyPreset = useCallback(
    (key: string) => {
      if (table === null) return
      // A PRESET WRITES `rule`/`basis` AND NO OVERRIDE. It re-renders suggestions and is
      // structurally incapable of touching a hand-typed price, which is the payoff of
      // suggestions staying unwritten.
      //
      // THIS COMMENT DESCRIBED THE DESIGN AND THE LINE UNDER IT WROTE `preset` — A KEY NO
      // READER ANYWHERE HAS. `pipeline/decisions.py:parse` does not know the field and
      // `to_payload` does not emit it, so the next join dropped it, and `rule`/`basis` sat at
      // `match`/`market` throughout. Pressing `Market -5%` restyled every suggestion on screen
      // and changed nothing `emit` reads, so a run priced that way emitted at market. Measured
      // on the owner's riftbound run: that dead key beside `rule: match`, with 2 overrides
      // across 50 SKUs — 48 cards about to list at a price nobody had chosen.
      //
      // It is D49's own named failure — "a run where changing the preset silently changed
      // nothing" — reached by the other road. That entry refuses to write the suggestions as
      // overrides, correctly, because an override is layer 1 and beats the rule at layer 4;
      // what it needs INSTEAD is the rule at layer 4 actually moving, which is this.
      const chosen = PRESETS.find((row) => row.key === key)
      if (chosen === undefined) return
      const missing = rows.filter((row) => row.presets[key] === null)
      /* THE RULE AND THE BASIS ARE THE CORPUS'S, for `setSubThreshold`'s reason. */
      setBook((current) =>
        current === null
          ? current
          : { ...current, policy: { ...current.policy, rule: chosen.rule, basis: chosen.basis } },
      )
      for (const row of rows) {
        const input = inputs.current.get(row.sku)
        if (input && answerFor(row) === undefined) input.value = row.presets[key] ?? ''
      }
      setNote(
        missing.length === 0
          ? null
          : {
              sku: '',
              text:
                `${rows.length - missing.length} of ${rows.length} rows priced. ` +
                `${missing.length} have no price in that column and were left alone: ` +
                missing.slice(0, 6).map((row) => row.name).join(', '),
            },
      )
    },
    [rows, table, answerFor],
  )

  const toggleHold = useCallback(
    (sku: PricingSku) => {
      if (isWithheld(answers[sku.sku])) {
        write(sku.sku, sku.bucket, undefined)
        setHoldFor(null)
        return
      }
      setHoldFor(sku.sku)
    },
    [answers, write],
  )

  const setHold = useCallback(
    (sku: PricingSku, reason: WithholdReason, watch: string, text: string) => {
      const record: WithheldRecord = { withheld: reason }
      if (watch.trim() !== '') record.watch_above = watch.trim()
      if (text.trim() !== '') record.note = text.trim()
      write(sku.sku, 'listable', record)
      // A HOLD ON A `no_market_data` ROW ALSO WRITES ITS OWN CHANNEL'S ANSWER. `blocking`
      // reads `no_market_data` alone and would go on refusing the emit otherwise; the
      // override short-circuits pricing and never reads the second, which is correct.
      if (sku.bucket === 'no_market_data') write(sku.sku, sku.bucket, 'unlisted')
      setHoldFor(null)
      inputs.current.get(sku.sku)?.focus()
    },
    [write],
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
  }, [undo])

  /* TAKE THE READING FOR ONE SKU, AND ASK NOTHING IF THIS SESSION ALREADY HAS IT.
   *
   * ONE READ PER CARD PER SITTING, WHICHEVER GESTURE ASKED FOR IT. The reading is kept by SKU,
   * so an operator comparing two cards — pinning one, holding `t` over the other, bouncing
   * back — asks once each and never again. That cache is what makes a gesture cheap enough to
   * repeat affordable at all: the hold added no new spending, only a second way to reach a
   * read that was already free after the first.
   *
   * `force` IS THE RETRY, and it is the only way past the cache. A refusal is cached like a
   * reading is: without that, a card whose mirror was down would re-fetch on every press, and
   * the panel would look like it were doing nothing while quietly hammering a host that is
   * already struggling. The button says `Try again` because retrying is the operator's call.
   *
   * IT OPENS NOTHING. Aiming the panel is `pinHistory` and `peekIn` below, because the two
   * gestures differ in what they aim and in what closes it, and only this part is common. */
  const readHistory = useCallback(
    (sku: PricingSku, force = false) => {
      if (run === null) return
      if (!force && history[sku.sku] !== undefined) return
      setHistory((current) => ({ ...current, [sku.sku]: { kind: 'reading' } }))
      /* `.then().catch()` AND NOT `.then(ok, fail)` — `app/eslint.config.js` refuses the
         second form and names the morning it cost: a success handler that throws becomes an
         unhandled rejection, so the panel would sit on `reading…` forever with no failure
         shown and no control to press. This handler walks a response body, which is exactly
         the throw that rule is about. */
      getPriceHistory(run, sku.sku)
        .then((payload) =>
          setHistory((current) => ({ ...current, [sku.sku]: { kind: 'read', payload } })),
        )
        .catch((error) =>
          setHistory((current) => ({
            ...current,
            [sku.sku]: { kind: 'refused', why: describeFailure(error).message },
          })),
        )
    },
    [history, run],
  )

  /**
   * READ THE SHAPE OF EVERY ROW STILL WAITING ON AN ANSWER — one press, D79.
   *
   * IT IS A PRESS AND MAY NEVER BECOME AN EFFECT. D62 closed the follow-focus read
   * structurally because a walk down this list would fire one request per arrow key at a free
   * public mirror. Batching does not make that cheap — this is ~92 requests, 37.7s cold and
   * 0.15s warm, measured on `2026-08-31-box3-01` — it makes it ONE DECISION instead of fifty.
   * Firing this from a `useEffect` on mount would spend that on every visit to this screen for
   * readings nobody asked for, which is the rudeness D62 named, arriving by the other door.
   *
   * IT SKIPS THE ROWS THIS RUN CAN ADD NOTHING FOR, on the owner's instruction of 2026-08-31:
   * *"I don't need the prices for the rows that have none left."* `at_cap` is the field
   * `cli/cmd_join.py` writes and the same one those rows are grouped under, so the filter and
   * the grouping agree by construction rather than by two rules kept in step. They stay
   * reachable: `T` reads any one of them, which is the right shape for a row an operator has a
   * reason to be curious about and no reason to be shown.
   *
   * CHUNKED, WHICH IS WHY THE STRIP FILLS IN WAVES. One request for 46 SKUs is 37 seconds of
   * nothing; six requests of eight are six partial answers, and the first arrives in about
   * five. The server applies its own courtesy delay between live fetches either way, so this
   * costs the mirrors nothing extra — it is the same walk, reported as it goes.
   *
   * SEQUENTIAL AND NOT PARALLEL, DELIBERATELY. `Promise.all` over the chunks would finish in a
   * sixth of the time by making six sockets race at a host that publishes no rate limit and
   * asks nothing of us — which is precisely the courtesy `pipeline/pricehistory.py` spends a
   * constant on. The wall clock is not the thing being optimised; the blank screen is.
   */
  const loadTrends = useCallback(() => {
    if (run === null) return
    const open = rows.filter((row) => !row.at_cap).map((row) => row.sku)
    const walk = (trendWalk.current += 1)
    setTrends(
      Object.fromEntries(open.map((sku) => [sku, { kind: 'reading' } as TrendRead])),
    )
    setTrendRun({
      run,
      total: open.length,
      done: 0,
      skipped: rows.length - open.length,
      spans: null,
      reading: true,
    })

    const chunks: string[][] = []
    for (let at = 0; at < open.length; at += TREND_CHUNK) {
      chunks.push(open.slice(at, at + TREND_CHUNK))
    }

    const read = async () => {
      for (const chunk of chunks) {
        /* THE ABANDON CHECK, BEFORE THE REQUEST AND AGAIN AFTER IT. Before, so a walk the
           operator has already replaced stops spending requests; after, so a chunk that was
           in flight when they did cannot write into the strip that replaced it. */
        if (trendWalk.current !== walk) return
        try {
          const payload = await getPriceTrends(run, chunk)
          if (trendWalk.current !== walk) return
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk) {
              const found = payload.skus[sku]
              const why = payload.refused[sku]
              /* EVERY ASKED SKU LANDS SOMEWHERE. The route promises both directions and this
                 is where that promise is spent: a SKU in neither map would otherwise sit on
                 `reading…` for the rest of the session, which is the silent drop CLAUDE.md
                 forbids wearing a spinner. */
              next[sku] =
                found !== undefined
                  ? { kind: 'read', ranges: found.ranges }
                  : {
                      kind: 'refused',
                      why: why ?? 'the batch answered without this SKU and without a reason.',
                    }
            }
            return next
          })
          setTrendRun((current) =>
            current === null || current.run !== run
              ? current
              : {
                  ...current,
                  done: current.done + chunk.length,
                  /* THE SPANS COME OFF THE FIRST ANSWER THAT HAS THEM and are not replaced.
                     Every SKU of a run carries the same two, so a later chunk would rewrite
                     them with themselves; taking the first keeps the caption still while the
                     list fills underneath it. */
                  spans:
                    current.spans ??
                    Object.values(payload.skus).find((entry) => entry.ranges.length > 0)
                      ?.ranges ??
                    null,
                },
          )
        } catch (error) {
          if (trendWalk.current !== walk) return
          /* A DEAD CHUNK IS EIGHT REFUSALS AND NOT A STOPPED WALK. A mirror having a bad
             minute should cost the rows it was asked about, not the thirty behind them —
             `describeFailure` carries the server's own sentence where there is one. */
          const why = describeFailure(error).message
          setTrends((current) => {
            const next = { ...current }
            for (const sku of chunk) next[sku] = { kind: 'refused', why }
            return next
          })
          setTrendRun((current) =>
            current === null || current.run !== run
              ? current
              : { ...current, done: current.done + chunk.length },
          )
        }
      }
      if (trendWalk.current === walk) {
        setTrendRun((current) =>
          current === null || current.run !== run ? current : { ...current, reading: false },
        )
      }
    }
    void read()
  }, [rows, run])

  /* WHICH ROW THE POINTER IS OVER, AND WHICH ONE A HELD KEY LATCHED. BOTH ARE REFS BECAUSE
     NOTHING DRAWS EITHER. A hovered row in state re-renders a hundred rows on every crossing
     to bookkeep a fact no row draws — the row's own `:hover` is CSS and needs no help — and
     the only reader of these two is a key press. */
  const hovered = useRef<string | null>(null)
  const heldSku = useRef<string | null>(null)

  /** The SKU whose price field has focus, or null. Read off the DOM rather than mirrored into
   *  a third piece of state: `inputs` already maps every field, and a mirror would be one more
   *  thing to keep true across a filter, a re-sort, a hold and a row that stops having a
   *  field at all. */
  const focusedSku = useCallback(() => {
    for (const [sku, node] of inputs.current) if (node === document.activeElement) return sku
    return null
  }, [])

  /** Whether an event landed in one of THIS screen's price fields, which is the one place a
   *  letter is a command rather than a character. */
  const isPriceField = useCallback((target: EventTarget | null) => {
    for (const node of inputs.current.values()) if (node === target) return true
    return false
  }, [])

  /** PIN THE PANEL TO ONE SKU. The deliberate gesture, and the only one that outlives itself.
   *
   *  IT CLOSES THE PHOTOGRAPH. Both panels are fixed in the same corner — `PriceHistory.css`
   *  carries the reason that corner is the right one — so they are mutually exclusive rather
   *  than overlapping. A peek does NOT close it: a gesture that lasts as long as a key is down
   *  must not destroy a panel the operator opened on purpose. It hides it while it is up
   *  instead, at the one render below that draws the corner. */
  const pinHistory = useCallback(
    (sku: PricingSku) => {
      if (run === null) return
      heldSku.current = null
      setPeek(null)
      setPhotoFor(null)
      setPinned(sku.sku)
      readHistory(sku)
    },
    [readHistory, run],
  )

  /** PUBLISH THE SHIP BAR'S MEASURED HEIGHT AS `--pricing-ship-h` (D85).
   *
   *  `Pricing.css` and `PriceHistory.css` have read this property since D54 and NOTHING HAS
   *  EVER SET IT. Three declarations took the `64px` fallback every time, against a bar that
   *  is 125px closed and 433px with an emit receipt up — so the two fixed panels, which are
   *  positioned to sit above the bar, sat on top of its sub-threshold controls instead. Those
   *  controls are the answer `emit` refuses to run without, which is what made this worth
   *  measuring rather than worth another constant.
   *
   *  A CALLBACK REF AND NOT AN EFFECT, because the bar is conditional — it is absent until a
   *  run is picked — and an effect would need the node in state to know when it arrived,
   *  which is a re-render to bookkeep a number no React code reads. The property is written
   *  straight to the DOM for the same reason: only the stylesheets read it.
   *
   *  `closest` AND NOT A SECOND REF ON THE `<main>`. React assigns child refs before parent
   *  refs, so a `mainRef.current` read from here would be null on the first mount and the
   *  panels would take the fallback on exactly the render that matters. The host is one hop up
   *  and asking the DOM for it has no ordering to get wrong.
   *
   *  A `ResizeObserver` AND NOT A ONE-SHOT MEASUREMENT: the bar grows when the receipt lands,
   *  when a refusal is drawn, and when the window narrows enough to wrap its rows. Every one
   *  of those is a height change with no re-render of this component behind it. */
  const shipObserver = useRef<ResizeObserver | null>(null)
  const shipHost = useRef<HTMLElement | null>(null)
  const measureShip = useCallback((node: HTMLElement | null) => {
    shipObserver.current?.disconnect()
    shipObserver.current = null
    if (node === null) {
      /* The bar went away with the run. Clear rather than freeze the last height: a stale
         clearance would hold a gap open under panels that no longer have anything to clear. */
      shipHost.current?.style.removeProperty('--pricing-ship-h')
      shipHost.current = null
      return
    }
    const host = node.closest<HTMLElement>('.pricing')
    if (host === null) return
    shipHost.current = host
    const publish = () => host.style.setProperty('--pricing-ship-h', `${node.offsetHeight}px`)
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(node)
    shipObserver.current = observer
  }, [])

  /** Close the panel both ways, so nothing that was showing survives the press. */
  const unpin = useCallback(() => {
    heldSku.current = null
    setPeek(null)
    setPinned(null)
  }, [])

  /* HOLD `t`, SEE THE ROW UNDER THE POINTER, LET GO AND IT IS GONE (D62, amended 2026-08-31).
   *
   * THE POINTER AIMS AND THE KEY HOLDS, which is the owner's gesture in their own words: "if
   * i then push T i see that row's T, and it holds as my cursor moves as long as i hold T,
   * and then as soon as i release it goes away". The row is LATCHED at the press and hover
   * changes are ignored until the release — re-aiming continuously would swap the panel out
   * from under a hand that is only crossing the screen to reach it, and the hand crossing to
   * `Try again` passes over forty other rows on the way.
   *
   * IT IS A PRESS, WHICH IS THE PROPERTY D62 SPENT ITSELF ON. A reading is a request to two
   * public mirrors, so nothing may take one on a movement: hovering a row asks for nothing at
   * all, and this handler is the whole of what asks.
   *
   * ON `window` AND NOT ON THE FIELD. The gesture starts at the pointer, so the hands need not
   * be in any field for it — and a keyup has to arrive even where the press moved focus, which
   * a per-field handler cannot promise. The field's own handler still swallows the letter; the
   * `t` branch in `onKey` is that and nothing else now.
   *
   * `blur` RELEASES IT TOO, because a window that loses focus mid-hold never delivers the
   * keyup. Cmd-Tab away holding `t` and the panel would otherwise be standing when you came
   * back — which is precisely the thing this gesture exists to stop. */
  useEffect(() => {
    const release = () => {
      if (heldSku.current === null) return
      heldSku.current = null
      setPeek(null)
    }
    const down = (event: KeyboardEvent) => {
      // `repeat` IS THE WHOLE REASON A HELD KEY IS AFFORDABLE: a key held down fires keydown
      // over and over, and without this the read would be re-asked at the OS repeat rate.
      if (event.key.toLowerCase() !== 't' || event.repeat) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (heldSku.current !== null) return
      // THE HOLD PANEL OWNS THE KEYBOARD WHILE IT IS UP — D49's reasons are letter keys too.
      if (holdFor !== null) return
      /* EVERY OTHER FIELD ON THIS SCREEN IS ONE SOMEBODY TYPES PROSE OR DIGITS INTO — a note,
         a rule, a basis, the run search. Only the price field's alphabet is closed, so only
         there is a letter free to mean something. */
      if (isEditableTarget(event.target) && !isPriceField(event.target)) return
      /* THE POINTER WINS OVER FOCUS, deliberately: the hands are in a field while the eyes and
         the pointer are on some other row, and the row being ASKED ABOUT is the one being
         pointed at. Focus is the fallback for the case where nothing is pointed at, so the
         gesture still works with the mouse parked off the list. */
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
      /* AND NOTHING ELSE. This effect re-subscribes whenever `readHistory` gets a new identity
         — which the first `setHistory({kind: 'reading'})` of the hold guarantees — so a
         `release()` here would close the panel one render after it opened, every time. It cost
         seven red cases to learn. There is nothing to release on the real unmount either: the
         refs and the state go with the screen. */
    }
  }, [focusedSku, holdFor, isPriceField, readHistory, rows])

  const onKey = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>, sku: PricingSku) => {
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
        event.currentTarget.value =
          typeof standing === 'string' ? standing : suggestionFor(sku)
        // Reverted, so the field is untouched again — an Escape that left it marked would
        // have the next blur write back the value Escape just undid.
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
      // EVERY LETTER IS A COMMAND, BY CONSTRUCTION. The field's alphabet is closed to
      // `[0-9.]`, so there is nothing to disambiguate — which is the entire reason this
      // screen can have a keyboard while the hands are in a field, where every other screen
      // in the app returns on `isEditableTarget`.
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
        /* AND IT CLOSES THE READING, which is the half of the mutual exclusion that was never
           built: `t` cleared the photograph and `p` did not clear the history, so the two
           drew over each other in one corner. A press ends a pin; only the pointer ends a
           peek, and one showing when this fires is hidden rather than closed. */
        unpin()
        setPhotoFor((current) =>
          current !== null && current.sku === sku.sku ? null : { sku: sku.sku, at: 0 },
        )
        return
      }
      /* `t` FOR TREND, AND `h` WOULD HAVE BEEN THE OBVIOUS LETTER. It is spent on the hold —
         which is the control this sits beside and exists to inform, so the collision is with
         exactly the thing it is for. `t` is unspent on this screen and is a word the owner
         would say out loud naming what the panel shows, which is the rule `App.tsx` states
         for the route chords one level up.

         THE ACT ITSELF IS ON `window` NOW, because the pointer aims it and the release ends
         it — see the effect above. What is left here is the SWALLOW, and it is not optional:
         without it the letter reaches `onBeforeInput`, which marks the field touched and
         clears the suggestion on its way to rejecting the character. So `t` in a price field
         would silently blank a suggested price. */
      if (lower === 't') {
        event.preventDefault()
        return
      }
      if (lower === 'n' && sku.snap.now !== null) {
        event.preventDefault()
        snap(sku, 'now')
      }
    },
    /* `suggestionFor` IS LISTED BECAUSE THE MEMO ABOVE MADE THIS HANDLER STABLE. It was
       omitted and harmless while `answers` and `unpriced` were rebuilt every render: this
       callback was rebuilt with them, so its closure could never go stale. Memoising them
       fixed that churn and would have ARMED the omission — a preset change gives
       `suggestionFor` a new identity off `[doc]`, and a handler holding the old one would
       apply the PREVIOUS preset's suggested price to a key the operator pressed after
       switching. A wrong number on a listing, silently.

       Adding it costs nothing: `suggestionFor` changes exactly when `doc` does, and `doc`
       already reaches this array through `answerFor`. What it buys is that the two stop
       being correct by coincidence. */
    [answerFor, commit, move, snap, suggestionFor, toggleHold, undoLast, unpin],
  )

  /* THE PHOTO PANEL FOLLOWS FOCUS WHILE IT IS OPEN, and the same key closes it — so
     `Escape` keeps its existing two jobs in the field and the panel never takes a binding
     away from price entry. */
  const photoSku = useMemo(
    () => (photoFor === null ? null : rows.find((row) => row.sku === photoFor.sku) ?? null),
    [photoFor, rows],
  )

  /* THE COPY THE STRIP IS CURRENTLY ON, resolved once instead of four times inside the panel.
     The photograph, its caption and the `n of m` all have to name the SAME copy, and four
     independent `positions[at % length]` expressions were four chances for them not to.
     `null` where the row carries no position at all — `positions[NaN]` for an empty list —
     which `cli/cmd_join.py:_pricing_table` never writes (`pipeline/join.py`: no matched SKU
     may hold zero positions) and so means a hand-edited file rather than a state the pipeline
     produces. The panel degrades to the no-label form rather than throwing. */
  const photoAt = useMemo(
    () =>
      photoSku === null || photoFor === null
        ? null
        : photoSku.positions[photoFor.at % photoSku.positions.length] ?? null,
    [photoSku, photoFor],
  )

  /* THE CARD THE PANEL IS DRAWN FOR, RESOLVED AGAINST THE CURRENT ROWS. A held `t` outranks a
     pin while the key is down — `historyFor` is `peek ?? pinned` — so the glance shows the row
     it latched and the pinned card comes back underneath it on the release.

     `rows` is what the section filter and the held filter leave, so a card filtered out from
     under an open panel resolves to null and the panel closes itself — which is right: a
     reading floating over a list that no longer contains its card is a panel about nothing
     the operator can see. */
  const historySku = useMemo(
    () => (historyFor === null ? null : rows.find((row) => row.sku === historyFor) ?? null),
    [historyFor, rows],
  )

  /** `Box 3 · RB Epics` for the run being priced, or `null` where nothing can say (D56).
   *
   *  `detail` FIRST AND THE LIST SECOND, AND THEY CANNOT DISAGREE — both come out of
   *  `server/pipeline_routes.py:_summary`, which joins the box against the registry on every
   *  read. What separates them is freshness: `runs` is fetched once at mount and never again,
   *  while `detail` is re-read by `load()` and therefore by the Reload button — so a box
   *  renamed on `#/inventory` shows up here on a press rather than on a page reload. The list
   *  covers the window before `getRun` has answered and the case where it refused. */
  const scopeName = useMemo(() => {
    if (run === null) return null
    const row = detail !== null && detail.run === run ? detail : runs.find((r) => r.run === run)
    return row === undefined ? null : runBoxLabel(row)
  }, [run, detail, runs])

  const chrome = (
    <header className="pricing-head">
      <div className="pricing-head-top">
        <h1 className="pricing-title">Pricing</h1>
        <div className="pricing-controls">
          {/* THE DRAWER, THEN THE RUN, THEN THE COUNT (D56). It read `<run> · N SKUs`, which
              names the directory and the size of the job and never says what is in the box —
              the owner's complaint, in the place they were looking when they made it. The run
              name stays because it is what `emit` and `join` are pointed at and what
              `decisions.json` is written under; what goes in front of it is the answer to
              which drawer these hundred prices are for. */}
          {/* THE SCOPE NAMES WHAT IS LOADED, AND A WORKLIST OVER SEVERAL RUNS SAYS SO RATHER
              THAN NAMING ONE. `scopeName` is the single-run answer and stays exactly as it
              was; the multi-run line counts the drawers, because there is no one drawer these
              prices are for and picking one to print would be a caption over the wrong list. */}
          <span className="pricing-scope">
            {loaded.length === 0
              ? 'Nothing loaded.'
              : run !== null
                ? [scopeName, run, `${rows.length} SKUs`]
                    .filter((part) => part !== null)
                    .join(' · ')
                : [
                    `${boxesLoaded.length || loaded.length} ${
                      boxesLoaded.length === 1 ? 'box' : 'boxes'
                    }`,
                    `${loaded.length} runs`,
                    `${rows.length} SKUs`,
                    picked.size === 0 ? 'everything unpriced' : null,
                  ]
                    .filter((part) => part !== null)
                    .join(' · ')}
          </span>

          {held.length === 0 ? null : (
            <button
              type="button"
              className={`pricing-plain${filterHeld ? ' pricing-plain-on' : ''}`}
              aria-pressed={filterHeld}
              onClick={() => setFilterHeld((on) => !on)}
            >
              holding {held.length}
            </button>
          )}
          <span className="pricing-save">
            {saving ? 'saving…' : dirty ? 'unsaved' : 'saved'}
          </span>
          <button
            type="button"
            className="pricing-plain"
            onClick={() => void load(picked)}
            disabled={loading}
          >
            Reload
          </button>
        </div>
      </div>
      <p className="pricing-lede">
        Sets what every SKU here will list at. One answer per card, for the whole store, in{' '}
        <code>inventory/prices.json</code> — a price is a fact about the card, not about the
        drawer it came out of. <a href="#/runs">Emit on Runs</a> writes one run&rsquo;s CSVs;
        the press below writes one file for everything on screen.
      </p>
    </header>
  )

  /* THE PICKER SHOWS WHEN THERE IS NOTHING TO DRAW, NOT WHEN NOTHING IS PICKED. Before
     D86 this read `run === null`, so the screen's opening state was always the menu; now an
     empty selection is answered by the server and the list is what lands. What is left here
     is the genuine empty: the fetch failed, or every open run has been answered. */
  if (work === null || work.runs.length === 0) {
    const joined = work?.roster ?? []
    return (
      <main className="pricing">
        {chrome}
        {failure === null ? null : (
          <div className="pricing-note-block">
            <p className="pricing-note-text">{failure.message}</p>
            <p className="pricing-machine">{failure.code}</p>
          </div>
        )}
        {loading ? (
          <p className="pricing-empty">Reading the runs…</p>
        ) : joined.length === 0 ? (
          <p className="pricing-empty">
            No joined runs yet. Identify and join a box on <a href="#/runs">Runs</a> first.
          </p>
        ) : picked.size > 0 ? (
          /* A NARROWING THAT MATCHED NOTHING IS NOT THE SAME EMPTY AS HAVING NO WORK, and
             saying so is the difference between "you are done" and "you filtered it away". */
          <p className="pricing-empty">
            Nothing to price in the runs you picked.{' '}
            <button type="button" className="pricing-plain" onClick={() => setPicked(new Set())}>
              Show everything unpriced
            </button>
          </p>
        ) : (
          /* THE TERMINAL STATE D49 PREDICTED AND THE SCREEN NEVER GOT. That entry read the
             history — 596 cards, 153 SKUs, zero per-item decisions available — and said in as
             many words that the honest reading was *"a screen whose job is to report there is
             nothing to do"*. It could never say it: the only empty state fired when NO run had
             ever been joined, so eight fully-answered runs drew eight chips and cost ~909KB and
             sixteen round trips to discover they owed nothing. */
          <p className="pricing-empty">
            Nothing owes a pricing answer. Every joined run has been priced and emitted — pick
            one below to look at it again, or <a href="#/runs">join a box on Runs</a>.
          </p>
        )}
        {joined.length === 0 ? null : (
          <PickRuns runs={joined} picked={picked} onToggle={toggleRun} />
        )}
      </main>
    )
  }

  return (
    <main className="pricing">
      {chrome}

      {/* THE PICKER IS A FILTER OVER THE LIST, NOT A GATE IN FRONT OF IT (D86). It used to be
          the screen's whole first state; it stays visible now because narrowing is something
          an operator does DURING a sitting — "just box 3 for a minute" — and a control you
          have to empty the screen to reach is one nobody uses. Un-ticking the last run returns
          the worklist to everything unpriced rather than to nothing. */}
      <PickRuns runs={work.roster} picked={picked} onToggle={toggleRun} />

      {work.skipped.length === 0 ? null : (
        /* A RUN THAT COULD NOT BE READ IS NAMED, NEVER DROPPED. An eight-run worklist must not
           silently become a seven-run one because a directory predates `pricing.json` — that
           is the silent drop `CLAUDE.md` forbids, wearing a shorter list. */
        <div className="pricing-note-block">
          {work.skipped.map((row) => (
            <p className="pricing-machine" key={row.run}>
              {row.run} skipped · {row.code}
            </p>
          ))}
        </div>
      )}

      {failure === null ? null : (
        <div className="pricing-note-block">
          <p className="pricing-note-text">{failure.message}</p>
          <p className="pricing-machine">{failure.code}</p>
        </div>
      )}

      <div className="pricing-presets" role="group" aria-label="Suggest a price for every row">
        {PRESETS.map((preset) => (
          <button
            key={preset.key}
            type="button"
            className="pricing-preset"
            /* THE ACTIVE CHIP IS DERIVED FROM `rule`/`basis`, NEVER STORED. A remembered
               selection would be a second answer to "what will an untouched row list at", and
               the pair the pipeline reads is the only one that can be right — so a rule typed
               by hand into `decisions.json` on `#/runs` correctly lights no chip rather than
               lighting a stale one. It is drawn at all because nothing on this screen said
               which rule was live, which is most of why the dead write survived: pressing a
               chip appeared to work, because the suggestions really did change. */
            aria-pressed={doc?.rule === preset.rule && doc?.basis === preset.basis}
            onClick={() => applyPreset(preset.key)}
            title={preset.says}
          >
            {preset.label}
          </button>
        ))}
        <span className="pricing-preset-says">
          A preset only fills rows you have not set, and sets the run’s rule. Anything else —
          a different rule or basis — is typed into <code>decisions.json</code> on{' '}
          <a href="#/runs">Runs</a>.
        </span>
      </div>

      {/* THE TREND STRIP'S ONE PRESS — D79, and D62's condition discharged.
          That entry made the history a press per card so a walk down the list could not fire a
          request per arrow key, and named what would reopen it: the panel wanted on every card,
          answered by a batched route and a column on the row. This is that press. It is still a
          press: nothing polls it and no render fires it, because batching makes ~92 requests at
          a free public mirror ONE DECISION rather than fifty, not cheap. */}
      <div className="pricing-trendbar">
        <button
          type="button"
          className="pricing-plain"
          onClick={loadTrends}
          disabled={run === null || trendRun?.reading === true}
        >
          {trendRun === null
            ? 'Load trends'
            : trendRun.reading
              ? `Reading ${trendRun.done} of ${trendRun.total}…`
              : 'Read again'}
        </button>
        <span className="pricing-trendbar-says">
          {trendRun === null ? (
            <>
              A shape and a sign per row, off two public mirrors. Free, about 35s for a box,
              and it skips the rows this run can add nothing for — <kbd>T</kbd> still reads
              any one of those. Every figure stays on the panel.
            </>
          ) : (
            <>
              {/* THE SPANS, STATED ONCE. Each range draws its own because the WIDER one is the
                  STALER — weekly buckets are stamped at the start of their week, so `annual`
                  ran six days behind `month` on one card at one moment (D62, measured). A
                  shared caption would be wrong for one of them, and forty-six copies of two
                  dates would be the panel drawn badly. */}
              {(trendRun.spans ?? []).map((range) => (
                <span key={range.range} className="pricing-trendbar-span">
                  {RANGE_LABEL[range.range] ?? range.range} {range.from ?? '?'} → {range.to ?? '?'}
                </span>
              ))}
              {/* THE ONE SENTENCE THIS COLUMN OWES A READER, and the reason it is here rather
                  than on the row: two ranges disagreeing is the ordinary case and not a fault,
                  and without it a `+54%` beside a `−30%` on one row reads as a broken screen. */}
              <span>
                The ranges overlap and are read separately — the wider one includes these same
                recent days at a coarser width, so they can point opposite ways.
              </span>
              <span className="pricing-machine">
                {trendTally.read} read
                {trendRun.skipped > 0 ? ` · ${trendRun.skipped} not asked` : ''}
                {trendTally.refused > 0 ? ` · ${trendTally.refused} refused` : ''}
              </span>
            </>
          )}
        </span>
      </div>

      {note === null ? null : <p className="pricing-refusal">{note.text}</p>}

      {sections.map((section) => {
        return (
          <section className="pricing-section" key={section.bucket}>
            <div className="pricing-section-head">
              <h2 className="pricing-section-title">{section.title}</h2>
              <span className="pricing-section-count">{section.total} SKUs</span>
            </div>
            <p className="pricing-section-note">{section.note}</p>

            <div className="pricing-caption" aria-hidden="true">
              {/* Two empty cells, for the two 32px controls at the front of every row — the
                  history and the hold. The caption reads the SAME `--pricing-cols` template
                  the rows do, so a cell missing here does not merely lose a heading: it
                  leaves the row with an item the grid has no column for, which wraps into an
                  implicit row and breaks the height invariant below. */}
              <span />
              <span />
              <span>Qty</span>
              <span className="pricing-caption-card">Card</span>
              {/* ONE LABEL PER RANGE, HERE AND NOT ON THE ROW — the same argument the snap
                  keys beside it make: the two ranges are the same two on every row, so the
                  name belongs where the eye already is when reading the column. `RANGE_LABEL`
                  is `PriceHistory.tsx`'s own table, imported rather than restated, so the
                  panel and the strip cannot come to call one range two things. */}
              <span className="pricetrend-keys">
                {['month', 'annual'].map((range) => (
                  <span key={range}>{RANGE_LABEL[range] ?? range}</span>
                ))}
              </span>
              <span>Lists at</span>
              {SNAPS.map((column) => (
                <span key={column.key} className="pricing-caption-ref">
                  {column.label} <kbd>{column.key}</kbd>
                </span>
              ))}
            </div>

            <div className="pricing-list">
              {section.items.map((item) => {
                /* THE HEADING FOR THE ROWS UNDER IT, AND IT IS AN `h3` BECAUSE THAT IS WHAT IT
                   IS. The section's own title is the `h2` above; these rows are a named part
                   of it, so the reason is announced once to a screen reader on the way in
                   rather than repeated in the right margin of every row it covers. No
                   wrapper: the rows stay direct children of the list, which is what the
                   section's grid template is written against. */
                if (item.head !== null) {
                  return (
                    <h3 className="pricing-group-head" key={`why:${item.head}`}>
                      <span className="pricing-group-why">{item.head}</span>
                      <span className="pricing-group-count">
                        {item.count === 1 ? '1 SKU' : `${item.count} SKUs`}
                      </span>
                    </h3>
                  )
                }
                const sku = item.sku
                const standing = answerFor(sku)
                const withheld = isWithheld(standing)
                const suggestion = suggestionFor(sku)
                /* The row's sentence, decided here rather than in the markup, because the
                   second line composes it with the held token below and a ternary that also
                   had to yield a value would have been unreadable.

                   IT IS THE OPERATOR'S NOTE AND NOTHING ELSE NOW. `at_cap`'s sentence used to
                   win this line, which meant a row that was BOTH at the cap and withheld with
                   a note drew the reason and swallowed the note — the one string on the row
                   nobody else on the screen holds a copy of. The reason moved up to the
                   group's heading, where it is stated once for every row it covers, so the
                   row keeps the aside. */
                const why = withheld && standing !== 'unlisted' && standing.note
                  ? standing.note
                  : null
                return (
                  <div
                    className="pricing-row"
                    key={sku.sku}
                    /* THE WHOLE ROW IS THE TARGET, not the `T` alone: the gesture is "point at
                       a row and hold `t`", and asking the operator to find a 32px button
                       first would make a pointing gesture into an aiming one. Writing a ref
                       renders nothing, so this costs a crossing what a CSS `:hover` costs.

                       THE LEAVE IS GUARDED because enter and leave are not promised in an
                       order: A's leave arriving after B's enter would otherwise null out the
                       row the pointer is now on. */
                    onPointerEnter={() => {
                      hovered.current = sku.sku
                    }}
                    onPointerLeave={() => {
                      if (hovered.current === sku.sku) hovered.current = null
                    }}
                    data-answer={
                      withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'
                    }
                    data-cap={sku.at_cap ? 'full' : 'room'}
                    data-dim={filterHeld && !withheld ? 'true' : undefined}
                  >
                    {/* THE PIN, NOT THE PANEL. `aria-pressed` is this control's own state,
                        and a `t` held over the row draws the panel without this button having
                        been pressed at all — reporting that as pressed would announce a state
                        to a screen reader that nothing on the page is in. */}
                    <button
                      type="button"
                      className="pricing-history"
                      aria-pressed={pinned === sku.sku}
                      aria-label={`Price history for ${sku.name}`}
                      /* THE CLICK IS THE PIN, AND IT IS THE ONLY WAY TO ONE. Holding `t` is
                         the glance; this is the panel that stays — which is what a refusal's
                         `Try again`, a scroll through both ranges, and reading while typing a
                         price all need, none of which can be done with a key held down. */
                      onClick={() => (pinned === sku.sku ? unpin() : pinHistory(sku))}
                    >
                      T
                    </button>

                    {/* BESIDE THE HISTORY, BECAUSE IT IS THE FACT THE HOLD WAS MISSING. D49
                        records that `bullish` and `watch_above` are set against the
                        operator's memory of what a card used to cost; the reading beside it
                        replaces the memory, so the two sit together.

                        A BUTTON AND NOT ONLY A KEY. docs/DESIGN.md: "every choice shows its
                        key" — and the converse, from D51, is that a binding nothing
                        advertises is one only the person who asked for it will ever press.
                        The letter IS the label here, the same way `T` is on the history. */}
                    <button
                      type="button"
                      className="pricing-hold"
                      aria-pressed={withheld}
                      aria-label={withheld ? `Release ${sku.name}` : `Hold ${sku.name}`}
                      onClick={() => toggleHold(sku)}
                    >
                      H
                    </button>

                    <span className="pricing-qty">
                      {sku.add_to_quantity} of {sku.copies}
                    </span>

                    <div className="pricing-id">
                      <span className="pricing-name" title={sku.name}>
                        {sku.name}
                      </span>
                      <span className="pricing-meta">
                        <span className="pricing-cond">{sku.condition}</span>
                        {` · ${sku.set_name} · ${sku.row['Number'] ?? ''} · ${sku.row['Rarity'] ?? ''}`}
                      </span>
                    </div>

                    {/* WHICH OF THESE IS MOVING — the question a list answers and a panel
                        cannot (D79). A shape and a sign; every figure a reading has stays on
                        `T`'s panel, where there is room to draw the anchor at size and its
                        bound muted beneath it. `undefined` draws an empty cell, which is the
                        honest rendering of a row nobody has asked about. */}
                    <TrendCell read={trends[sku.sku]} />

                    {/* THE HUMAN LABEL HERE, THE MACHINE STRING ON THE ROW'S SECOND LINE —
                        and the split is arithmetic rather than taste. This column is 120px
                        and `withheld: next_batch` measures 152px in Martian Mono at 10px
                        (7px per character, before the 0.06em), so the token CANNOT be drawn
                        inside the cell on one line. Stacked in here it wrapped to three
                        lines, stood 54px tall in a 32px track, and overprinted the note
                        below it — the two strings a held row draws were literally on top of
                        each other. The second line already spans nine columns and is already
                        this exact register, so that is where the token goes. */}
                    {withheld ? (
                      <span className="pricing-held">Holding</span>
                    ) : (
                      <input
                        className="pricing-input"
                        type="text"
                        inputMode="decimal"
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
                          // THE PREFILL CLEARS ON THE FIRST CHARACTER, LITERALLY AS ASKED:
                          // "if i type numbers they ought to immediately clear and now my
                          // typing be inputed as the price". Done at `beforeinput` rather
                          // than relying on the select() above, because a click plants a
                          // collapsed caret and an arrow key collapses a selection — and
                          // neither may be allowed to produce `0.412`.
                          //
                          // ONE SHOT PER FIELD, and getting that wrong is not subtle: keyed
                          // on the STORED answer instead, it cleared on every keystroke and
                          // typing `4.50` left `0`.
                          const first = !touched.current.has(sku.sku)
                          touched.current.add(sku.sku)
                          if (first && typeof answerFor(sku) !== 'string') field.value = ''
                          const next =
                            field.value.slice(0, field.selectionStart ?? 0) +
                            insert +
                            field.value.slice(field.selectionEnd ?? 0)
                          if (!PRICE.test(next)) event.preventDefault()
                        }}
                        onKeyDown={(event) => onKey(event, sku)}
                        onBlur={(event) => commit(sku, event.currentTarget.value)}
                      />
                    )}

                    {SNAPS.map((column) => (
                      <span
                        key={column.key}
                        className={`pricing-ref${column.field === 'market' ? ' pricing-ref-market' : ''}`}
                        title={sku.row[
                          column.field === 'market'
                            ? 'TCG Market Price'
                            : column.field === 'direct_low'
                              ? 'TCG Direct Low'
                              : column.field === 'low'
                                ? 'TCG Low Price'
                                : 'TCG Low Price With Shipping'
                        ]}
                      >
                        {sku.snap[column.field] === null ? '—' : `$${sku.snap[column.field]}`}
                      </span>
                    ))}

                    {/* WHAT THIS ROW ALONE HOLDS. The run's reason for adding nothing is
                        the group's heading above these rows — `groupOf` carries why — so what
                        is left here is the operator's own note on a hold, which is per-row by
                        nature and is the one string on the screen nothing else keeps a copy
                        of. */}
                    {/* ONE LINE, TWO REGISTERS, RIGHT-ALIGNED TOGETHER. The note and the held
                        row's machine token are both `--util` 10px muted and both belong to
                        this row, and the row reserves exactly ONE 13px line for that register
                        — so they share it rather than contend for it. The token is last, which
                        puts it flush right, directly under the `Holding` it belongs to, and
                        leaves the reading order human-then-machine that docs/DESIGN.md's rule
                        asks for.

                        THE SENTENCE YIELDS AND THE TOKEN NEVER DOES. `pricing-row-why`
                        ellipsizes and carries its full text in `title`; the token is
                        `flex: none`, because it is the greppable half — a `withheld: nex…`
                        finds nothing in `decisions.json`. Which way the line breaks under
                        pressure is a decision, and this is it. */}
                    {/* WHERE THIS CARD IS, WHEN IT IS IN MORE THAN ONE DRAWER — and the
                        disagreement, where the runs already answered it two ways.

                        THIS IS THE ROW THAT PAYS FOR THE WORKLIST. 78 of 423 SKUs on this
                        machine sit in more than one run, 8 carried two answers, and 3 of those
                        were a `withheld` hold answered with a price in a later sitting: SKU
                        9191210 was held `bullish` above $5 out of box 3 and listed at $3.45 out
                        of box 4 the next day. Nothing could have said so — a hold lives in its
                        run and dies with it (D49) — and this line is what says it.

                        THE BOXES AND NOT THE RUN NAMES. A person owns drawers, not
                        directories; the runs are on the chips above. Deduped and ascending,
                        which is the order the shelf is in. */}
                    {sku.in.length < 2 && !sku.over_cap ? null : (
                      <p className="pricing-row-span">
                        <span className="pricing-span-where">
                          {(() => {
                            const boxes = [
                              ...new Set(sku.positions.map((place) => place.box)),
                            ].sort((a, b) => a - b)
                            return boxes.length === 0
                              ? `${sku.in.length} runs`
                              : `${boxes.length === 1 ? 'Box' : 'Boxes'} ${boxes.join(', ')} · ${sku.in.length} runs`
                          })()}
                        </span>
                        {/* THE CAP, WHERE THE RUNS SEPARATELY CLAIM MORE THAN CAN GO. Each run
                            spends `live_cap - copies_out` believing it is alone, so runs joined
                            before either emitted double-spend the same room — measured, two SKUs
                            reached `pushed: 6` against a cap of 4. The Qty cell already shows the
                            true figure; this says the runs disagree with it. */}
                        {!sku.over_cap ? null : (
                          <span className="pricing-span-cap">
                            runs claim {sku.claimed_add}, {sku.add_to_quantity} can go
                          </span>
                        )}
                      </p>
                    )}

                    {why === null && !withheld ? null : (
                      <p className="pricing-row-note">
                        {why === null ? null : (
                          <span className="pricing-row-why" title={why}>
                            {why}
                          </span>
                        )}
                        {withheld ? (
                          <span className="pricing-machine">
                            withheld{heldReason(standing) ? `: ${heldReason(standing)}` : ''}
                          </span>
                        ) : null}
                      </p>
                    )}

                    {holdFor !== sku.sku ? null : (
                      <HoldPanel sku={sku} onSet={setHold} onCancel={() => setHoldFor(null)} />
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        )
      })}

      {/* THE READING, AIMED AT ONE SKU AND NEVER AT THE FOCUSED ROW. `readHistory` carries
          the reason: a read leaves this machine, so a panel that re-read on the focused row
          would fire one request per arrow key.

          A PIN SURVIVES THE ROW SCROLLING AWAY, which is the other half of being pinned. The
          operator opens a reading, walks the list comparing it against other cards, and the
          panel goes on describing the card they opened it for — with its SKU printed, so
          which card that is stays answerable. A held `t` ends with the key instead, and the
          panel says which of the two it is: `Keep open` where letting go would end it,
          `Close` where a press is what it will take. */}
      {historySku === null ? null : (
        <PriceHistoryPanel
          sku={historySku.sku}
          name={historySku.name}
          read={history[historySku.sku]}
          pinned={pinned === historySku.sku}
          onClose={unpin}
          onKeep={() => pinHistory(historySku)}
          onRetry={() => readHistory(historySku, true)}
        />
      )}

      {/* ONE CORNER, ONE PANEL. `p` clears a pinned reading outright, and this guard covers
          the case a press cannot reach: a held `t` arriving over an open photograph. It hides
          rather than closes, so the photograph is back on the release and a gesture this
          cheap to make has spent nothing the operator must restore by hand. */}
      {photoSku === null || photoFor === null || historyFor !== null ? null : (
        <aside className="pricing-photo" aria-label={`Photograph of ${photoSku.name}`}>
          <img src={photoUrl(photoAt?.box ?? 0, photoAt?.index ?? 0)} alt={photoSku.name} />
          <p className="pricing-photo-caption">
            {/* THE SERVER'S STRING, COMPOSED ON THIS READ, never the one frozen into
                `pricing.json` at join time (D58, on D56's rule). It matters here more than
                anywhere the same string is drawn larger: `photoUrl` addresses the photograph
                above BY SLOT, so the picture has always been the index's current occupant
                while the stored caption was the join's. A copy sold since now reads
                `Box 3 · departed · B3 #17` instead of pointing at the card that closed up
                behind it, and a divider moved since reads against the layout in the box
                today. Nothing is composed here — `server/pipeline_routes.py` sends the
                finished string, as every other position on every other screen arrives.

                `no label · <key>` IS `BoxBrowse`'s OWN FALLBACK and is one vocabulary with
                it, for its reason: the server answers null where it will not name a place,
                and `3/17` bare reads like a position and is not one. */}
            {photoAt === null
              ? null
              : photoAt.label ?? `no label · ${photoAt.box}/${photoAt.index}`}
            {' · '}
            {(photoFor.at % photoSku.positions.length) + 1} of {photoSku.positions.length}
          </p>
          <div className="pricing-photo-controls">
            <button
              type="button"
              className="pricing-plain"
              onClick={() => setPhotoFor({ sku: photoFor.sku, at: photoFor.at + 1 })}
              disabled={photoSku.positions.length < 2}
            >
              Next copy
            </button>
            <button type="button" className="pricing-plain" onClick={() => setPhotoFor(null)}>
              Close
            </button>
          </div>
        </aside>
      )}

      {/* ------------------------------------------------------- the ship bar (D54)
          STICKY AND IN FLOW, NOT `fixed`, AND THAT IS THE ANSWER TO "HOW DOES THE LIST AVOID
          BEING COVERED". A sticky last child reserves its own height in the document, so the
          padding under a ~6,500px list is exactly the bar's height BY CONSTRUCTION —
          including when the receipt appears and the bar grows. A fixed bar needs a
          hand-maintained `padding-bottom` on `.pricing` equal to a height that changes, which
          is the two-declarations-that-must-agree drift this stylesheet already argues against
          for its grid template. */}
      {/* THE MERGED PRESS — one import file over every run on screen (D86).
          `emit` is per run and stays so; what this adds is a send, because the CAP has to be
          re-derived across it. `pipeline/join.py` spends `live_cap - copies_out` per run
          against a cap that is global, so pressing the per-run button N times IS the
          over-push: measured from an identical cleared ledger, three separate emits over
          three real runs wrote two SKUs past the cap of four and one merged emit wrote none.
          The bar only exists for a send of more than one, because for one run the press
          below is that same command with nothing to merge. */}
      {loaded.length < 2 ? null : (
        <aside
          className="pricing-ship"
          ref={measureShip}
          role="region"
          aria-label="Ship these runs"
        >
          <div className="pricing-ship-row">
            <span className="pricing-ship-key">
              {loaded.length} runs · {boxesLoaded.length}{' '}
              {boxesLoaded.length === 1 ? 'box' : 'boxes'} · one file
            </span>
            <span className="pricing-ship-says">
              The cap is spent once across the send, so a card in three drawers gets one row.
            </span>
            <label className="pricing-ship-only">
              <input
                type="checkbox"
                checked={listedOnly}
                onChange={(event) => setListedOnly(event.currentTarget.checked)}
              />
              just the above-threshold cards
            </label>
            <button
              type="button"
              className="pricing-emit"
              disabled={sendingAll}
              onClick={() => {
                setSendingAll(true)
                setShipTrouble(null)
                void (async () => {
                  try {
                    const result = await emitMerged(loaded, { listedOnly })
                    setReceipt({
                      ok: result.ok,
                      console: result.console,
                      files: result.files,
                    })
                  } catch (err) {
                    setShipTrouble(describeFailure(err))
                  } finally {
                    setSendingAll(false)
                  }
                })()
              }}
            >
              {sendingAll ? 'Writing…' : 'Write one import file'}
            </button>
          </div>
          {receipt === null ? null : (
            <div className="pricing-ship-receipt">
              <pre className="pricing-console">{receipt.console}</pre>
              {(receipt.files ?? [])
                .filter((file) => file.is_import)
                .map((file) => (
                  <a
                    key={file.name}
                    className="pricing-plain"
                    href={runFileUrl(loaded[loaded.length - 1] as string, file.name)}
                    download={file.name}
                  >
                    {file.name}
                  </a>
                ))}
            </div>
          )}
          {shipTrouble === null ? null : (
            <div className="pricing-note-block">
              <p className="pricing-note-text">{shipTrouble.message}</p>
              <p className="pricing-machine">{shipTrouble.code}</p>
            </div>
          )}
        </aside>
      )}

      {run === null ? null : (
        <aside className="pricing-ship" ref={measureShip} role="region" aria-label="Ship this run">
          {subThresholdSkus(work?.skus ?? []).length === 0 ? null : (
            <div className="pricing-ship-row">
              <span className="pricing-ship-key">
                Below ${work?.threshold ?? '0.40'} ·{' '}
                {subThresholdSkus(work?.skus ?? []).length} SKUs
              </span>
              {/* THE ANSWER `emit` REFUSES WITHOUT, ON THE SCREEN WHERE PRICING IS DONE. It
                  was settable only by typing JSON on another route, and `blocking` never
                  consults `overrides` — so hand-pricing every row still left emit refusing.
                  Two of the three runs on disk are parked on exactly this. */}
              <button
                type="button"
                className="pricing-plain"
                aria-pressed={doc?.sub_threshold === FLOOR_CHOICE}
                onClick={() =>
                  setSubThreshold(
                    doc?.sub_threshold === FLOOR_CHOICE ? null : FLOOR_CHOICE,
                  )
                }
              >
                At the ${work?.floor ?? '0.40'} floor
              </button>
              <button
                type="button"
                className="pricing-plain"
                aria-pressed={flatOpen || typeof doc?.sub_threshold === 'object'}
                onClick={() => setFlatOpen((on) => !on)}
              >
                A flat price
              </button>
              {!flatOpen && typeof doc?.sub_threshold !== 'object' ? null : (
                <input
                  className="pricing-ship-flat"
                  /* DELIBERATELY NOT MATCHING `/^Price for /`: `pricing.spec.ts` locates the
                     row field by that name and asserts a held row has none of them. */
                  aria-label="A flat price for every sub-threshold card"
                  defaultValue={
                    typeof doc?.sub_threshold === 'object' && doc.sub_threshold !== null
                      ? doc.sub_threshold[FLAT_KEY]
                      : ''
                  }
                  onBeforeInput={(event) => {
                    const next =
                      event.currentTarget.value + (event as { data?: string }).data
                    if (!PRICE.test(next)) event.preventDefault()
                  }}
                  /* WRITES ONLY ON A COMMITTED, NON-EMPTY, WELL-FORMED VALUE. `{"flat": ""}`
                     reaches `Decimal("")` and raises `MalformedDecisions` at the next join —
                     an hour later, on another screen, about a keystroke nobody remembers. */
                  onBlur={(event) => {
                    const text = event.currentTarget.value.trim()
                    if (text !== '' && PRICE.test(text)) setSubThreshold({ [FLAT_KEY]: text })
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== 'Enter') return
                    event.preventDefault()
                    const text = event.currentTarget.value.trim()
                    if (text !== '' && PRICE.test(text)) setSubThreshold({ [FLAT_KEY]: text })
                  }}
                />
              )}
            </div>
          )}

          <div className="pricing-ship-row">
            {/* IT CLAIMS ONLY WHAT IT CHECKED. `readiness.ts` sees two of emit's roughly eight
                refusals, so "ready to emit" would be a promise this screen cannot keep — and
                a screen that overstates a check is worse than one that runs none. */}
            <p className="pricing-ready">
              {owes.length === 0
                ? 'Pricing is answered. Emit can still refuse for a reason this line cannot see.'
                : `Emit will refuse: still needs ${owes
                    .map((o) => `${OWED_LABELS[o.reason]} (${o.count})`)
                    .join(', ')}.`}
            </p>
            {queued === 0 ? null : (
              /* WHAT *JOIN* QUEUED, worded as such: nothing rewrites `counts` until the next
                 join, so this is a fact about the run rather than a live queue depth. A
                 queued card is not in `report.matches`, so it is genuinely left out of the
                 file — the cost is real and the remedy is a re-join. */
              <p className="pricing-ready pricing-ready-warn">
                This run’s join sent {queued} card{queued === 1 ? '' : 's'} to{' '}
                <a href="#/review">review</a>. Emitting now leaves them out of the file.
              </p>
            )}
          </div>

          <div className="pricing-ship-row pricing-ship-act">
            {ship === 'waiting' ? (
              <>
                <span className="pricing-ship-key">Saving your answers…</span>
                <button
                  type="button"
                  className="pricing-plain"
                  onClick={() => setShip('idle')}
                >
                  Cancel
                </button>
              </>
            ) : emitted && !armed ? (
              <>
                {/* ABSENT, NOT DISABLED. A second press used to overwrite the good CSV with a
                    header-only file and blank the manifest, after which `reconcile` refused a
                    run that had emitted perfectly — D54 fixed that in the command, and this
                    is the half that stops the press being made by momentum. */}
                <span className="pricing-ship-key">
                  This run has already written its import files.
                </span>
                <button
                  type="button"
                  className="pricing-plain"
                  onClick={() => setArmed(true)}
                >
                  Write them again
                </button>
              </>
            ) : emitted && armed ? (
              <>
                <span className="pricing-ship-key">
                  Writing again sends only what has not been sent yet.
                </span>
                <button
                  type="button"
                  className="pricing-emit"
                  disabled={ship === 'sending'}
                  onClick={() => setShip('waiting')}
                >
                  {ship === 'sending' ? 'Writing…' : 'Write again'}
                </button>
                <button type="button" className="pricing-plain" onClick={() => setArmed(false)}>
                  Cancel
                </button>
              </>
            ) : (
              /* AN OUTLINE, NEVER A SOLID FILL. `docs/DESIGN.md` reserves the fill for a
                 screen with exactly one thing to do, and a hundred-row worklist is the
                 definition of more than one; `pricing.spec.ts` asserts zero accent grounds
                 here. Emphasis comes from position — the right end of a bar that is always on
                 screen — rather than from colour. NO KEYBOARD SHORTCUT: every letter on this
                 screen is typed with the hands in a price field, and a typo that ships a run
                 is not a mistake worth trading a keystroke for. */
              <button
                type="button"
                className="pricing-emit"
                disabled={ship === 'sending'}
                onClick={() => setShip('waiting')}
              >
                {ship === 'sending' ? 'Writing…' : 'Write the import files'}
              </button>
            )}
          </div>

          {shipTrouble === null ? null : (
            <div className="pricing-note-block">
              <p className="pricing-note-text">{shipTrouble.message}</p>
              <p className="pricing-machine">{shipTrouble.code}</p>
            </div>
          )}

          {receipt === null ? null : (
            <div className="pricing-ship-receipt">
              <p className={`pricing-ready${receipt.ok ? '' : ' pricing-ready-warn'}`}>
                {receipt.ok ? 'emit finished' : 'emit refused'}
              </p>
              <pre className="pricing-ship-console" aria-label="What emit printed">
                {receipt.console}
              </pre>
              {!receipt.ok ? null : (
                <>
                  <RunFiles run={run} files={receipt.files} only="import" />
                  {/* THE NEXT STEP IS SOMEWHERE ELSE, AND IT IS AN ERRAND. Between these
                      files and `reconcile` the operator leaves the app entirely. */}
                  <p className="pricing-ready">
                    Import these to Staged in TCGplayer, then come back with Export From
                    Staged and run <a href="#/runs">reconcile on Runs</a>.
                  </p>
                </>
              )}
            </div>
          )}
        </aside>
      )}
    </main>
  )
}

/** The hold panel. It owns the keyboard while it is up, and its choices are keyed on LETTERS
 *  rather than the digits `#/review`'s panel uses — the digits here are price entry, so a
 *  digit inside a panel raised from a focused price field is unresolvable. */
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

  return (
    <div className="pricing-holdpanel" role="group" aria-label={`Hold ${sku.name}`}>
      <p className="pricing-holdpanel-lede">
        Every copy stays out of this run&rsquo;s import file. The card does not move, does not
        change state and is sellable the moment you release it.
      </p>
      <div className="pricing-holdpanel-reasons">
        {WITHHOLD_REASONS.map((option) => (
          <button
            key={option}
            type="button"
            className="pricing-plain"
            aria-pressed={reason === option}
            onClick={() => setReason(option)}
          >
            {WITHHOLD_LABELS[option]} <kbd>{WITHHOLD_KEYS[option]}</kbd>
          </button>
        ))}
      </div>
      <label className="pricing-field">
        Tell me when market is above $
        <input
          type="text"
          inputMode="decimal"
          value={watch}
          onChange={(event) => setWatch(event.target.value)}
        />
      </label>
      <label className="pricing-field pricing-field-wide">
        Note
        <input type="text" value={text} onChange={(event) => setText(event.target.value)} />
      </label>
      <div className="pricing-holdpanel-actions">
        <button
          type="button"
          className="pricing-plain"
          onClick={() => onSet(sku, reason, watch, text)}
        >
          Hold it
        </button>
        <button type="button" className="pricing-plain" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <p className="pricing-holdpanel-fine">
        Holds live in this run&rsquo;s <code>decisions.json</code>. A new run over this box
        starts with none.
      </p>
    </div>
  )
}
