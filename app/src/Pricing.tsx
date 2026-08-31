import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  describeFailure,
  getPriceHistory,
  getPricing,
  getRun,
  getRuns,
  putDecisions,
  photoUrl,
  runStep,
  type Failure,
} from './server'
import type {
  DecisionsDocument,
  PricingPayload,
  PricingSku,
  RunDetail,
  RunFile,
  RunSummary,
  WithheldRecord,
} from './types'
import { WITHHOLD_KEYS, WITHHOLD_LABELS, WITHHOLD_REASONS, type WithholdReason } from './holds'
import { FLAT_KEY, FLOOR_CHOICE, OWED_LABELS, owed, subThresholdSkus } from './readiness'
import { PriceHistoryPanel, type HistoryRead } from './PriceHistory'
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
  { key: 'd', field: 'direct_low', label: 'DIRECT' },
  { key: 'l', field: 'low', label: 'LOW' },
  { key: 's', field: 'low_with_shipping', label: '+SHIP' },
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

type Undo = { sku: string; target: 'overrides' | 'no_market_data'; before: unknown }

export function Pricing() {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  const [run, setRun] = useState<string | null>(null)
  const [payload, setPayload] = useState<PricingPayload | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [doc, setDoc] = useState<DecisionsDocument | null>(null)
  const [saving, setSaving] = useState(false)
  const [undo, setUndo] = useState<Undo[]>([])
  const [holdFor, setHoldFor] = useState<string | null>(null)
  const [photoFor, setPhotoFor] = useState<{ sku: string; at: number } | null>(null)

  /* ------------------------------------------------------------- the price history (D62)
   *
   * WHICH SKU THE PANEL IS PINNED TO, AND IT DOES NOT FOLLOW FOCUS. That is the one way this
   * differs from the photograph above it, and it is not a preference: a reading is a request
   * to two public mirrors, so a panel that re-read on the focused row would fire one request
   * per arrow key — fifty for a walk down this list, at a free mirror, for readings nobody
   * asked for. `t` re-aims it, which is a press and therefore a deliberate act.
   *
   * The panel prints the SKU it is pinned to for the same reason, so a panel left open while
   * the hands move down the list cannot be read as describing the focused row. */
  const [historyFor, setHistoryFor] = useState<string | null>(null)
  /* Every reading this session has taken, by SKU. Kept across closes so re-opening a card is
   * free, and NOT cleared when the run changes: a SKU's sales history is a fact about the
   * card rather than about the run that priced it, so the same reading is correct on any run
   * that matched it. The server's own on-disk cache (`pipeline/pricehistory.py`'s TTLs) is
   * what decides staleness; this only avoids asking it twice in one sitting. */
  const [history, setHistory] = useState<Record<string, HistoryRead>>({})
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
  const savedDoc = useRef<DecisionsDocument | null>(null)
  /* ONE PUT IN FLIGHT. This was the `saving` STATE, read inside the effect — which put
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
  const failedDoc = useRef<DecisionsDocument | null>(null)
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
    const fromHash = () => {
      const query = window.location.hash.split('?')[1] ?? ''
      const named = new URLSearchParams(query).get('run')
      if (named !== null && named !== '') setRun(named)
    }
    fromHash()
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

  const load = useCallback(async (name: string) => {
    try {
      const answer = await getPricing(name)
      /* SEEDED FROM THE TABLE'S OWN RULE WHERE THE RUN HAS NO DOCUMENT YET (D54). This was
         `answer.decisions ?? {}`, so the first write `PUT` a document carrying no `rule` and
         no `basis` — and `Decisions.parse` then defaults them to `match`/`market` while
         `cli/cmd_join.py` treats the FILE as authoritative. A run joined at `markup:100` was
         one keystroke from being silently reset to market price. Seeding writes nothing on
         its own: `savedDoc` is set to the same object, so `dirty` is false. */
      const held =
        answer.decisions ?? { rule: answer.pricing.rule, basis: answer.pricing.basis }
      setPayload(answer)
      setDoc(held)
      savedDoc.current = held
      failedDoc.current = null
      setFailure(null)
      setUndo([])
      setReceipt(null)
      setArmed(false)
      setShipTrouble(null)
      /* THE RUN'S FILES AND ITS PHASE. Its own try, and its own trouble state: a failure here
         must not blank the pricing table, which is the thing this screen is for. */
      try {
        setDetail(await getRun(name))
      } catch (err) {
        setDetail(null)
        setShipTrouble(describeFailure(err))
      }
    } catch (err) {
      setPayload(null)
      setFailure(describeFailure(err))
    }
  }, [])

  useEffect(() => {
    if (run !== null) void load(run)
  }, [run, load])

  /* UNSAVED IS A COMPARISON, NOT A FLAG: the document on screen is not the document the
     server confirmed. Derived rather than stored so it cannot be cleared for a write that
     did not carry it. */
  const dirty = doc !== null && doc !== savedDoc.current

  /* ONE PUT IN FLIGHT, COALESCING. The route replaces the document wholesale, so the screen
     round-trips every key it does not understand — including `_note` and anything a later
     version of `decisions.py` adds. A commit schedules a write; a change during one re-runs
     when it lands — which is now true of this loop rather than merely intended, because the
     write clears only the document it sent. */
  useEffect(() => {
    if (!dirty || doc === null || run === null) return
    if (inFlight.current || doc === failedDoc.current) return
    const sent = doc
    inFlight.current = true
    setSaving(true)
    void (async () => {
      try {
        await putDecisions(run, sent as Record<string, unknown>)
        savedDoc.current = sent
        failedDoc.current = null
        setFailure(null)
      } catch (err) {
        failedDoc.current = sent
        setFailure(describeFailure(err))
      } finally {
        inFlight.current = false
        setSaving(false)
      }
    })()
    /* `saving` IS IN THE LIST TO RE-FIRE THE EFFECT WHEN A WRITE LANDS, AND IT IS ONLY SAFE
       THERE BECAUSE THE GUARD IS A REF. Everything the completion changes is a ref — the
       saved document and the in-flight flag — so a re-render is the only thing that can ask
       "is there more to send?", and lowering `saving` is that re-render. What made this
       dependency a hazard before was the CLEANUP: the effect owned an in-flight closure, so
       the extra run tore that closure down mid-write and the response landed on a dead one.
       There is no cleanup now, the early return above is what the extra runs hit, and the
       write outlives every one of them. */
  }, [dirty, doc, run, saving])

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
    () => owed(doc, subThresholdSkus(payload?.pricing.skus ?? [])),
    [doc, payload],
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
  const setSubThreshold = useCallback((answer: string | { flat: string } | null) => {
    setDoc((current) => ({ ...(current ?? {}), sub_threshold: answer }))
  }, [])

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
    if (doc !== null && failedDoc.current === doc) {
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
  }, [ship, dirty, doc, run, saving])

  /** Write one answer, pushing the previous value — including its ABSENCE — onto the undo
   *  stack. Recording absence is what lets an undo DELETE a key and return the row to its
   *  suggestion, rather than writing the suggestion into the file. Writing a suggestion is
   *  the one thing this screen may never do: an override is layer 1 of the ladder and beats
   *  the rule at layer 4, so a screen that wrote all 108 suggestions would produce a run
   *  where changing the preset silently changed nothing. */
  const write = useCallback(
    (sku: string, bucket: PricingSku['bucket'], value: unknown) => {
      const target = targetOf(bucket)
      setDoc((held) => {
        // BUILT AS A LOOSE RECORD AND RETURNED AS THE DOCUMENT, which is the honest shape
        // rather than a cast fighting itself. The two tables hold different value types —
        // `overrides` takes a price OR a hold, `no_market_data` a price or `"unlisted"` —
        // and `targetOf` is what decides which, per section. Indexing the typed document by
        // a union of both keys asks TypeScript for the INTERSECTION of their value types,
        // which nothing satisfies; narrowing instead would mean two near-identical writers,
        // and two writers is how one of them drifts into writing the wrong file.
        const next: Record<string, unknown> = { ...(held ?? {}) }
        const table = { ...((next[target] as Record<string, unknown>) ?? {}) }
        setUndo((stack) =>
          [{ sku, target, before: table[sku] }, ...stack].slice(0, UNDO_DEPTH),
        )
        if (value === undefined) delete table[sku]
        else table[sku] = value
        // CAST AT THE ONE SEAM, and the looseness is the point rather than a shortcut. The
        // two tables hold different value types — `overrides` takes a price OR a hold,
        // `no_market_data` takes a price or `"unlisted"` — and `targetOf` is what decides
        // which, per section. Narrowing here would mean two near-identical writers, which is
        // exactly the duplication that lets one of them drift into writing the wrong file.
        next[target] = table
        return next as DecisionsDocument
      })
    },
    [],
  )

  const table = payload?.pricing ?? null
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

  const rows = useMemo(() => table?.skus ?? [], [table])

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
      const order = rows.map((row) => row.sku)
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
    [rows],
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
      setDoc((current) => ({ ...(current ?? {}), rule: chosen.rule, basis: chosen.basis }))
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
    setDoc((current) => {
      const next: Record<string, unknown> = { ...(current ?? {}) }
      const tableFor = { ...((next[top.target] as Record<string, unknown>) ?? {}) }
      if (top.before === undefined) delete tableFor[top.sku]
      else tableFor[top.sku] = top.before
      next[top.target] = tableFor
      return next as DecisionsDocument
    })
    setUndo(rest)
  }, [undo])

  /* OPEN THE HISTORY PANEL FOR ONE SKU, AND FETCH IF THIS SESSION HAS NOT ALREADY.
   *
   * ONE PRESS, ONE READ, AND A SECOND PRESS IS FREE. The reading is kept by SKU, so toggling
   * the panel shut and open again asks nothing — which matters because the panel is closed by
   * the same key that opens it and an operator comparing two cards will bounce between them.
   *
   * `force` IS THE RETRY, and it is the only way past the cache. A refusal is cached like a
   * reading is: without that, a card whose mirror was down would re-fetch on every press, and
   * the panel would look like it were doing nothing while quietly hammering a host that is
   * already struggling. The button says `Try again` because retrying is the operator's call.
   *
   * IT CLOSES THE PHOTOGRAPH. Both panels are fixed in the same corner — `PriceHistory.css`
   * carries the reason that corner is the right one — so they are mutually exclusive rather
   * than overlapping. */
  const openHistory = useCallback(
    (sku: PricingSku, force = false) => {
      if (run === null) return
      setPhotoFor(null)
      setHistoryFor(sku.sku)
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

         THE SAME KEY CLOSES IT, matching `p` beside it, so the panel never takes a binding
         away from price entry and `Escape` keeps its two existing jobs in the field. */
      if (lower === 't') {
        event.preventDefault()
        if (historyFor === sku.sku) setHistoryFor(null)
        else openHistory(sku)
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
    [answerFor, commit, historyFor, move, openHistory, snap, suggestionFor, toggleHold, undoLast],
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

  /* THE PINNED CARD, RESOLVED AGAINST THE CURRENT ROWS. `rows` is what the section filter and
     the held filter leave, so a card filtered out from under an open panel resolves to null
     and the panel closes itself — which is right: a reading floating over a list that no
     longer contains its card is a panel about nothing the operator can see. */
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
          <span className="pricing-scope">
            {run === null
              ? 'Pick a run.'
              : [scopeName, run, `${rows.length} SKUs`].filter((part) => part !== null).join(' · ')}
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
            onClick={() => run !== null && void load(run)}
            disabled={run === null}
          >
            Reload
          </button>
        </div>
      </div>
      <p className="pricing-lede">
        Sets what every SKU this run matched will list at. Answers are saved to{' '}
        <code>decisions.json</code>; <a href="#/runs">emit on Runs</a> is what writes the CSVs.
      </p>
    </header>
  )

  if (run === null || payload === null) {
    return (
      <main className="pricing">
        {chrome}
        {failure === null ? null : (
          <div className="pricing-note-block">
            <p className="pricing-note-text">{failure.message}</p>
            <p className="pricing-machine">{failure.code}</p>
          </div>
        )}
        <div className="pricing-runs" role="group" aria-label="Which run to price">
          {runs.filter((row) => row.joined).length === 0 ? (
            <p className="pricing-empty">
              No joined runs yet. Identify and join a box on <a href="#/runs">Runs</a> first.
            </p>
          ) : (
            runs
              .filter((row) => row.joined)
              .map((row) => {
                /* THE DRAWER LARGE, THE DIRECTORY SMALL BENEATH IT (D56). This chip drew the
                   run name over a SKU count — a date, a box digit and a number — and the owner
                   named it exactly: *"not just the date and the raw box number."* It is
                   `docs/DESIGN.md`'s human-label-large, machine-string-small rule, which the
                   review queue already applies to its reason codes, pointed at a picker: the
                   box is what a person is choosing between, and the run directory is the
                   greppable identity of the thing they are choosing.

                   THE RUN NAME IS NOT DEMOTED OUT OF USEFULNESS, and it must not be. Two runs
                   over one box draw the SAME headline — box 1 does exactly this on the owner's
                   store today — so the date on the second line is the only thing telling them
                   apart. It stays in the utility face at the metadata size rather than
                   dropping to the 10px a count can afford.

                   A RUN WITH NO BOX FALLS BACK TO ITS OWN NAME AS THE HEADLINE, rather than
                   drawing an empty line above one. No run on this machine is in that state; a
                   manifest with neither a scope block nor a box-shaped capture directory would
                   be. */
                const label = runBoxLabel(row)
                const day = runDay(row.created_at)
                return (
                  <button
                    key={row.run}
                    type="button"
                    className={`pricing-run${row.run === run ? ' pricing-run-on' : ''}`}
                    aria-pressed={row.run === run}
                    onClick={() => setRun(row.run)}
                  >
                    <span className="pricing-run-name">
                      {label ?? row.run}
                      {label === null || day === null ? null : ` · ${day}`}
                    </span>
                    <span className="pricing-run-meta">
                      {label === null ? null : (
                        <span className="pricing-run-id">{row.run}</span>
                      )}
                      <span>{row.counts?.skus ?? '?'} SKUs</span>
                    </span>
                  </button>
                )
              })
          )}
        </div>
      </main>
    )
  }

  return (
    <main className="pricing">
      {chrome}

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

      {note === null ? null : <p className="pricing-refusal">{note.text}</p>}

      {SECTIONS.map((section) => {
        const inSection = rows.filter((row) => row.bucket === section.bucket)
        if (inSection.length === 0) return null
        return (
          <section className="pricing-section" key={section.bucket}>
            <div className="pricing-section-head">
              <h2 className="pricing-section-title">{section.title}</h2>
              <span className="pricing-section-count">{inSection.length} SKUs</span>
            </div>
            <p className="pricing-section-note">{section.note}</p>

            <div className="pricing-caption" aria-hidden="true">
              <span>Card</span>
              {SNAPS.map((column) => (
                <span key={column.key} className="pricing-caption-ref">
                  {column.label} <kbd>{column.key}</kbd>
                </span>
              ))}
              <span>Id</span>
              <span>Qty</span>
              <span>Lists at</span>
              {/* Two empty cells, for the two 32px controls at the end of every row — the
                  hold and the history. The caption reads the SAME `--pricing-cols` template
                  the rows do, so a cell missing here does not merely lose a heading: it
                  leaves the row with an item the grid has no column for, which wraps into an
                  implicit row and breaks the height invariant below. */}
              <span />
              <span />
            </div>

            <div className="pricing-list">
              {inSection.map((sku) => {
                const standing = answerFor(sku)
                const withheld = isWithheld(standing)
                const suggestion = suggestionFor(sku)
                /* The row's sentence, decided here rather than in the markup, because the
                   second line now composes it with the held token below and a ternary that
                   also had to yield a value would have been unreadable. `at_cap` still wins
                   over the hold's note: it is the fact about this run, and the note is the
                   operator's own aside. */
                const why = sku.at_cap
                  ? (sku.nothing_to_add ?? 'nothing to add this run')
                  : withheld && standing !== 'unlisted' && standing.note
                    ? standing.note
                    : null
                return (
                  <div
                    className="pricing-row"
                    key={sku.sku}
                    data-answer={
                      withheld ? 'held' : typeof standing === 'string' ? 'typed' : 'suggested'
                    }
                    data-cap={sku.at_cap ? 'full' : 'room'}
                    data-dim={filterHeld && !withheld ? 'true' : undefined}
                  >
                    <div className="pricing-id">
                      <span className="pricing-name" title={sku.name}>
                        {sku.name}
                      </span>
                      <span className="pricing-meta">
                        <span className="pricing-cond">{sku.condition}</span>
                        {` · ${sku.set_name} · ${sku.row['Number'] ?? ''} · ${sku.row['Rarity'] ?? ''}`}
                      </span>
                    </div>

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

                    <span className="pricing-sku">{sku.sku}</span>

                    <span className="pricing-qty">
                      {sku.add_to_quantity} of {sku.copies}
                    </span>

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

                    <button
                      type="button"
                      className="pricing-hold"
                      aria-pressed={withheld}
                      aria-label={withheld ? `Release ${sku.name}` : `Hold ${sku.name}`}
                      onClick={() => toggleHold(sku)}
                    >
                      H
                    </button>

                    {/* BESIDE THE HOLD, BECAUSE IT IS THE FACT THE HOLD WAS MISSING. D49
                        records that `bullish` and `watch_above` are set against the
                        operator's memory of what a card used to cost; this is the reading
                        that replaces the memory, so it sits against the control it informs.

                        A BUTTON AND NOT ONLY A KEY. docs/DESIGN.md: "every choice shows its
                        key" — and the converse, from D51, is that a binding nothing
                        advertises is one only the person who asked for it will ever press.
                        The letter IS the label here, the same way `H` is on the hold. */}
                    <button
                      type="button"
                      className="pricing-history"
                      aria-pressed={historyFor === sku.sku}
                      aria-label={`Price history for ${sku.name}`}
                      onClick={() =>
                        historyFor === sku.sku ? setHistoryFor(null) : openHistory(sku)
                      }
                    >
                      T
                    </button>

                    {/* THE SERVER SAYS WHY; THIS DRAWS IT. The sentence here used to be
                        "nothing to add this run — TCGplayer already holds {live_before}",
                        composed on the client out of the export's live column alone — which
                        reads 0 for every copy sitting on an import nobody has reconciled.
                        Measured on the owner's store: 167 pushed copies across 72 SKUs,
                        zero live and zero staged, and `live_before` reads 0 on every SKU of
                        both runs on disk — so wherever this note drew at all it read
                        "TCGplayer already holds 0" under a row adding nothing BECAUSE
                        TCGplayer was holding them. A row that stops appearing in an import
                        file is close enough to the silent drop `CLAUDE.md` forbids that
                        saying nothing would have beaten saying that.

                        `nothing_to_add` is composed in `pipeline/join.py` beside the numbers
                        and names which of the three reasons applies, because they have three
                        different remedies (D59). The fallback is not defensive padding: this
                        table is `pricing.json` READ OFF DISK, and a file written by an
                        earlier join carries `at_cap` with no sentence beside it — measured,
                        both runs in `runs/` today. So an older file states the bare fact,
                        which is exactly what `at_cap` means, and invents no reason for
                        it. */}
                    {/* ONE LINE, TWO REGISTERS, RIGHT-ALIGNED TOGETHER. The sentence and the
                        held row's machine token are both `--util` 10px muted and both belong
                        to this row, and the row reserves exactly ONE 13px line for that
                        register — so they share it rather than contend for it. The token is
                        last, which puts it flush right, directly under the `Holding` it
                        belongs to, and leaves the reading order human-then-machine that
                        docs/DESIGN.md's rule asks for.

                        THE SENTENCE YIELDS AND THE TOKEN NEVER DOES. `pricing-row-why`
                        ellipsizes and carries its full text in `title`; the token is
                        `flex: none`, because it is the greppable half — a `withheld: nex…`
                        finds nothing in `decisions.json`. Which way the line breaks under
                        pressure is a decision, and this is it. */}
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

      {/* THE READING, PINNED TO THE SKU IT WAS OPENED FOR. Not `photoSku`'s follow-focus
          shape, and `openHistory` carries the reason: a read leaves this machine, so a panel
          that re-read on the focused row would fire one request per arrow key.

          IT SURVIVES THE ROW SCROLLING AWAY, which is the other half of being pinned. The
          operator opens a reading, walks the list comparing it against other cards, and the
          panel goes on describing the card they opened it for — with its SKU printed, so
          which card that is stays answerable. */}
      {historySku === null ? null : (
        <PriceHistoryPanel
          sku={historySku.sku}
          name={historySku.name}
          read={history[historySku.sku]}
          onClose={() => setHistoryFor(null)}
          onRetry={() => openHistory(historySku, true)}
        />
      )}

      {photoSku === null || photoFor === null ? null : (
        <aside className="pricing-photo" aria-label={`Photograph of ${photoSku.name}`}>
          <img src={photoUrl(photoAt?.box ?? 0, photoAt?.index ?? 0)} alt={photoSku.name} />
          <p className="pricing-photo-caption">
            {/* THE SERVER'S STRING, COMPOSED ON THIS READ, never the one frozen into
                `pricing.json` at join time (D58, on D56's rule). It matters here more than
                anywhere the same string is drawn larger: `photoUrl` addresses the photograph
                above BY SLOT, so the picture has always been the index's current occupant
                while the stored caption was the join's. A copy sold since now reads
                `Box 3 · departed · 3/17` instead of pointing at the card that closed up
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
      {run === null ? null : (
        <aside className="pricing-ship" role="region" aria-label="Ship this run">
          {subThresholdSkus(payload?.pricing.skus ?? []).length === 0 ? null : (
            <div className="pricing-ship-row">
              <span className="pricing-ship-key">
                Below ${payload?.pricing.threshold ?? '0.40'} ·{' '}
                {subThresholdSkus(payload?.pricing.skus ?? []).length} SKUs
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
                At the ${payload?.pricing.floor ?? '0.40'} floor
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
              {payload?.remembered_sub_threshold == null ? null : (
                /* A LABEL AND NEVER A DEFAULT — D9 forbids answering this on the operator's
                   behalf, so this removes the time spent DECIDING and not the press. */
                <button
                  type="button"
                  className="pricing-plain"
                  onClick={() =>
                    setSubThreshold(payload.remembered_sub_threshold?.answer ?? null)
                  }
                >
                  {payload.remembered_sub_threshold.run} answered{' '}
                  {typeof payload.remembered_sub_threshold.answer === 'string'
                    ? payload.remembered_sub_threshold.answer
                    : `$${payload.remembered_sub_threshold.answer.flat}`}{' '}
                  · use it
                </button>
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
