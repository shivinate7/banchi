import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeFailure, getPricing, getRuns, putDecisions, photoUrl, type Failure } from './server'
import type {
  DecisionsDocument,
  PricingPayload,
  PricingSku,
  RunSummary,
  WithheldRecord,
} from './types'
import { WITHHOLD_KEYS, WITHHOLD_LABELS, WITHHOLD_REASONS, type WithholdReason } from './holds'
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

/** The three presets, named to match `cli/cmd_join.py:PRESETS` key for key. The owner chose
 *  these three and their percentages in the interview; a fourth is a change to that tuple
 *  and to this table, and to nothing else. */
const PRESETS: { key: string; label: string; says: string }[] = [
  {
    key: 'market_match',
    label: 'Match market',
    says: 'The recent actual-sale average, matched exactly. What every run has done so far.',
  },
  {
    key: 'market_undercut_5',
    label: 'Market −5%',
    says: '5% under the recent actual-sale average, clamped at the $0.40 floor after rounding.',
  },
  {
    key: 'low_undercut_1',
    label: 'TCG Low −1%',
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
  const [note, setNote] = useState<{ sku: string; text: string } | null>(null)
  const [filterHeld, setFilterHeld] = useState(false)

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
      const held = answer.decisions ?? {}
      setPayload(answer)
      setDoc(held)
      savedDoc.current = held
      failedDoc.current = null
      setFailure(null)
      setUndo([])
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
  const answers = (doc?.overrides ?? {}) as Record<string, unknown>
  const unpriced = (doc?.no_market_data ?? {}) as Record<string, unknown>

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

  const applyPreset = useCallback(
    (key: string) => {
      if (table === null) return
      // A PRESET WRITES `rule`/`basis` AND NO OVERRIDE. It re-renders suggestions and is
      // structurally incapable of touching a hand-typed price, which is the payoff of
      // suggestions staying unwritten.
      const missing = rows.filter((row) => row.presets[key] === null)
      setDoc((current) => ({ ...(current ?? {}), preset: key }))
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
          typeof standing === 'string' ? standing : (sku.rule_price ?? '')
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
      if (lower === 'n' && sku.snap.now !== null) {
        event.preventDefault()
        snap(sku, 'now')
      }
    },
    [answerFor, commit, move, snap, toggleHold, undoLast],
  )

  /* THE PHOTO PANEL FOLLOWS FOCUS WHILE IT IS OPEN, and the same key closes it — so
     `Escape` keeps its existing two jobs in the field and the panel never takes a binding
     away from price entry. */
  const photoSku = useMemo(
    () => (photoFor === null ? null : rows.find((row) => row.sku === photoFor.sku) ?? null),
    [photoFor, rows],
  )

  const chrome = (
    <header className="pricing-head">
      <div className="pricing-head-top">
        <h1 className="pricing-title">Pricing</h1>
        <div className="pricing-controls">
          <span className="pricing-scope">
            {run === null ? 'Pick a run.' : `${run} · ${rows.length} SKUs`}
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
              .map((row) => (
                <button
                  key={row.run}
                  type="button"
                  className={`pricing-run${row.run === run ? ' pricing-run-on' : ''}`}
                  aria-pressed={row.run === run}
                  onClick={() => setRun(row.run)}
                >
                  <span className="pricing-run-name">{row.run}</span>
                  <span className="pricing-run-meta">{row.counts?.skus ?? '?'} SKUs</span>
                </button>
              ))
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
            onClick={() => applyPreset(preset.key)}
            title={preset.says}
          >
            {preset.label}
          </button>
        ))}
        <span className="pricing-preset-says">
          A preset only fills rows you have not set. Anything else — a different rule or basis
          — is typed into <code>decisions.json</code> on <a href="#/runs">Runs</a>.
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
              <span />
            </div>

            <div className="pricing-list">
              {inSection.map((sku) => {
                const standing = answerFor(sku)
                const withheld = isWithheld(standing)
                const suggestion = sku.rule_price ?? ''
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

                    {withheld ? (
                      <span className="pricing-held">
                        Holding
                        <span className="pricing-machine">
                          withheld{heldReason(standing) ? `: ${heldReason(standing)}` : ''}
                        </span>
                      </span>
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

                    {sku.at_cap ? (
                      <p className="pricing-row-note">
                        nothing to add this run — TCGplayer already holds {sku.live_before}
                      </p>
                    ) : withheld && standing !== 'unlisted' && standing.note ? (
                      <p className="pricing-row-note">{standing.note}</p>
                    ) : null}

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

      {photoSku === null || photoFor === null ? null : (
        <aside className="pricing-photo" aria-label={`Photograph of ${photoSku.name}`}>
          <img
            src={photoUrl(
              photoSku.positions[photoFor.at % photoSku.positions.length]?.box ?? 0,
              photoSku.positions[photoFor.at % photoSku.positions.length]?.index ?? 0,
            )}
            alt={photoSku.name}
          />
          <p className="pricing-photo-caption">
            {photoSku.positions[photoFor.at % photoSku.positions.length]?.label}
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
