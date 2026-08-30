import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'

import {
  cropPreview,
  describeFailure,
  getRun,
  getRuns,
  photoUrl,
  preflightRun,
  putDecisions,
  runFileUrl,
  runStep,
  startRun,
  type Failure,
} from './server'
import type {
  CropPreview,
  CsvUpload,
  RunDetail,
  RunPreflight,
  RunStartFailure,
  RunSummary,
} from './types'
import { RunFiles } from './RunFiles'
import { boxLabel, boxOf, runBoxLabel } from './runScope'
import './RunPanel.css'

/* THE PIPELINE, ON THE SCREEN THE OPERATOR IS ALREADY STANDING ON.
 *
 * The owner's report, and it was correct: "i also don't see any of the UI you stated you'd be
 * building that let me do all of this within the app???" The four commands had been designed,
 * interviewed and drawn as a mockup, and none of it was built — which is precisely the failure
 * `CLAUDE.md`'s route-is-not-a-feature rule was written for, committed in the same session that
 * wrote the rule.
 *
 * IT SAT ON `#/inventory` UNTIL 2026-08-29 AND NOW HAS A ROUTE OF ITS OWN — `#/runs`, the
 * owner's ruling, recorded as D39, with `Runs.tsx` as the screen. D33's argument for the old
 * address was about SCOPE, and it is worth having in full because it is the specification D39
 * had to satisfy rather than a prediction it disproved: a run is something you do TO a box, or
 * to the cards you have just ticked inside one, so "a separate route would have to re-implement
 * the box strip, the search and the mass-select, and would then be free to disagree with them
 * about what the selection is".
 *
 * THAT COST WAS PAID RATHER THAN WAIVED, AND THE SPLIT IS WHAT THIS FILE CARES ABOUT. The box is
 * re-answered by a strip of its own, which is cheap and cannot disagree with anything. The
 * SELECTION is not re-implemented at all: `#/inventory` keeps the one mass-select in the product
 * and HANDS the ticked indices over (`runHandoff.ts`), so there is still exactly one place a
 * selection can be made. What the move buys is that the four commands stopped being housed on
 * the route `App.tsx`'s own table calls `look` — "reached when asked, not on a rhythm" — while
 * being the loop a session actually is.
 *
 * THIS FILE IS GIVEN A SCOPE AND OWNS EVERYTHING ELSE. The picker, the handoff and the page
 * chrome are `Runs.tsx`'s; every figure, console, poll and the whole money gate are this
 * component's and did not move. That is the same split `BoxBrowse` and `Inventory.tsx` keep.
 *
 * THE FOUR STEPS ARE DRAWN IN ORDER AND ONLY ONE OF THEM SPENDS. That is D1's two-phase split
 * made visible: identify is slow, costs money and is spawned; join, emit and reconcile are free,
 * re-runnable and answer inside the request. The panel says which is which in as many words,
 * because the whole reason the split exists is that the operator should be able to re-run the
 * free half without thinking about it.
 *
 * THE MONEY GATE IS TWO STEPS AND NO TYPING (the owner's ruling). Press Check cost, read the
 * card count and the estimate the command itself printed, then press the confirm that appears
 * beneath them. The confirm cannot be reached without the preflight, which is the point:
 * `docs/DESIGN.md` allows a gate on a genuinely destructive action, and the cheapest honest gate
 * here is making the number impossible not to have seen. A typed confirmation was considered and
 * is what the owner ruled out.
 *
 * EVERY COMMAND'S STDOUT IS SHOWN VERBATIM AND NOTHING HERE SUMMARISES ONE. `docs/DESIGN.md`'s
 * copy rule makes the owner's screens the place the pipeline's own words appear — being able to
 * grep what you saw is worth more than a consistent register — and a join report names SKUs,
 * prices, reason codes and positions that no paraphrase would keep. The one thing this panel
 * adds on top is the download link for a file the console can only name.
 *
 * IT HOLDS NOTHING ABOUT A RUN BETWEEN RENDERS EXCEPT WHICH ONE IS OPEN. Every figure is read
 * from `GET /pipeline/runs/<name>`, which reads the run directory — so a run started in a
 * terminal appears here, a run started here survives this tab being closed, and there is no
 * state in this component that can disagree with the disk.
 */

/** How often a live run is re-read. A Batch takes minutes to hours, so this is about a screen
 *  that does not look frozen rather than about latency — and the poll stops the moment the run
 *  stops being live, which the server derives from the child's own pid. */
const POLL_MS = 4000

/** The idle cadence. The only event an idle poll can catch is a person starting a run in a
 *  TERMINAL (D33 makes a run outlive the tab that started it), which is a human act with a
 *  human's tolerance. `POLL_MS` is for a screen that must not look frozen while a batch runs,
 *  which is a different question and a different number. */
const IDLE_POLL_MS = 20000

/** How long a live run has been going, from its own `created_at`.
 *
 *  THE ONE FACT ABOUT A LIVE RUN THAT IS ON NO OTHER PART OF THIS SCREEN. `identify/batch.py`
 *  logs only when the batch's `processing_status` CHANGES, so the console goes silent for
 *  minutes to hours and a tail written forty minutes ago is indistinguishable from a hang.
 *  There is no per-card signal on the wire and none is invented here — elapsed is MEASURED, and
 *  it is the smallest true thing that separates working from stuck. A progress bar would be a
 *  guess, and this panel does not draw guesses.
 *
 *  LIVE ONLY. On a finished run the same arithmetic is AGE, which is a different fact wearing
 *  the same shape. Under a minute, and on a run carrying no `created_at`, it reads exactly what
 *  it read before this existed. */
export function runningFor(row: { created_at?: string | null }): string {
  const at = row.created_at == null ? NaN : Date.parse(row.created_at)
  const mins = Number.isNaN(at) ? 0 : Math.max(0, Math.floor((Date.now() - at) / 60000))
  if (mins < 1) return 'running'
  return mins < 60 ? `running ${mins}m` : `running ${Math.floor(mins / 60)}h ${mins % 60}m`
}

/* The steps, in the order they are performed, with the two facts the panel repeats about each:
 * whether it spends, and whether it can be run again. Authored here rather than derived from
 * `phase`, because `phase` answers "what is this run waiting for" and this answers "what are
 * the four things there are" — a screen that only drew the current step would leave the
 * operator unable to see that emit exists until join had finished. */
const STEPS = [
  {
    key: 'identify',
    title: 'Identify',
    cost: 'Costs money',
    note: 'Reads every photograph with Haiku, in batch. Minutes to hours; it keeps running if you close this tab.',
  },
  {
    key: 'join',
    title: 'Join',
    cost: 'Free · re-runnable',
    note: 'Resolves each card against a TCGplayer export. Writes the queues and the pricing questions.',
  },
  {
    key: 'emit',
    title: 'Emit',
    cost: 'Free · re-runnable',
    note: 'Writes the import CSVs. Refuses while a sub-threshold price is unanswered.',
  },
  {
    key: 'reconcile',
    title: 'Reconcile',
    cost: 'Free · re-runnable',
    note: 'Compares what TCGplayer actually staged against what emit wrote.',
  },
] as const

/* HOW THE CARDS ARE READ, as three named PAIRS and an escape hatch — and the pairing is the
 * whole reason this is not two controls any more.
 *
 * D32's finding is that the crop and the max edge are ONE decision, and that the arithmetic
 * runs backwards from intuition: `max_edge` normalises the LONG EDGE, not the area, and a card
 * (aspect 0.72) is a fatter shape than the frame (0.56) — so cropping at an unchanged max edge
 * sends MORE pixels, not fewer. Measured at +26%. That entry says in as many words that it got
 * the cost model wrong in public first and recorded the correction so a later session would not
 * re-derive it the same way; a checkbox sitting beside a free-form number offers precisely that
 * mistake and says nothing about it. A pair cannot be got wrong.
 *
 * EVERY NUMBER BELOW IS A ROW OF D32'S OWN MEASURED FRONTIER over box 2, against a full-frame
 * @1568 baseline of $0.72. Nothing is invented here and nothing is extrapolated to another box,
 * which is why each sentence names the box it was measured on rather than quoting a rate.
 *
 * `Sharpest · 1400` is deliberately not one of the three. It is the row of that table that is
 * strictly dearer than the baseline, and three buttons fit the 340px end of this column where
 * four do not — so it lives behind `Custom`, which reveals the raw controls unchanged. Demoted,
 * not taken away. */
const READINGS = [
  {
    key: 'measured',
    label: 'Measured best',
    crop: true,
    maxEdge: 1200,
    says:
      'Finds the card in each photograph and sends only that, at 1200px on its longest side — ' +
      'the card, not the desk. Your photographs on disk are never touched. Box 2 measured it: ' +
      '$0.62 against the whole frame’s $0.72, and sharper on the collector number. One it ' +
      'cannot find a card in is sent whole; on box 2 that was none of 544.',
  },
  {
    key: 'cheapest',
    label: 'Cheapest',
    crop: true,
    maxEdge: 900,
    says:
      'The same crop to the card, sent smaller at 900px. The cheapest row measured on box 2 — ' +
      '$0.44 — and the softest: about 13% fewer pixels on the collector number than the whole ' +
      'frame gives. A photograph it cannot find a card in is sent whole.',
  },
  {
    key: 'whole',
    label: 'Whole frame',
    crop: false,
    maxEdge: 1568,
    says:
      'Sends the whole photograph, desk and all, at 1568px. This is the command’s own default ' +
      'and the only setting a run has been through end to end — Gate B’s 53 cards. $0.72 on box 2.',
  },
] as const

/* The sentence for the escape hatch, and it carries the warning the presets make unnecessary.
 * This is where the mistake is reachable again, so this is where it is named. */
const CUSTOM_SAYS =
  'Crop and max edge are one decision. Cropping on its own makes the picture BIGGER, not ' +
  'smaller — a card is a fatter shape than the frame, so a crop at an unchanged 1568 cost 26% ' +
  'MORE when it was measured. The rig’s useful range runs 900 to 1400.'

/** What a run was over, in the fewest words that are true.
 *
 *  IT NAMES THE DRAWER NOW AND NOT JUST THE NUMBER (D56). `runBoxLabel` joins the run's box
 *  against the registry server-side, so this reads `Box 3 · RB Epics` where the owner has
 *  named the box and `Box 3` where they have not — which is most of what a person scanning
 *  this list is actually trying to tell apart. The number stays beside the name because the
 *  number is the shelf, the capture directory and what every refusal here says.
 *
 *  THE `whole box` / `N cards` HALF STILL NEEDS A REAL SCOPE BLOCK. A box read out of a
 *  capture directory is a derivation, not a claim about what was submitted, and an old run
 *  genuinely does not record whether it covered the whole box — so that clause is drawn only
 *  where the manifest supports it. The alternative was an em dash, which says nothing about a
 *  run whose directory names its box in plain sight. */
function scopeOf(row: RunSummary): string {
  const label = runBoxLabel(row)
  if (label === null) return '—'
  if (row.scope != null && !row.scope.whole_box) {
    return `${label} · ${row.scope.cards ?? '?'} cards`
  }
  return label
}

function money(value: number | null | undefined): string {
  return typeof value === 'number' ? `$${value.toFixed(2)}` : '—'
}

function count(value: number | null | undefined): string {
  return typeof value === 'number' ? String(value) : '—'
}

/** A file the operator chose, read as text.
 *
 *  TEXT AND NOT BYTES, because a TCGplayer export is a CSV and the route takes it as a string —
 *  and because reading it here means the app can refuse an obviously-wrong file before it costs
 *  a round trip. The encoding is the browser's default UTF-8, which is what the export is;
 *  `pipeline/tcgcsv.py` is the only thing in this repo allowed to have an opinion about the
 *  bytes beyond that. */
function readUpload(file: File): Promise<CsvUpload> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`))
    reader.onload = () => resolve({ name: file.name, content: String(reader.result ?? '') })
    reader.readAsText(file)
  })
}

/** The console, drawn as the command printed it.
 *
 *  Scrolled to the bottom on every change, because the interesting part of a long command is
 *  always what it said most recently — the same reason the server serves the TAIL of the log
 *  rather than its head. */
function Console({ text, label }: { text: string; label: string }) {
  const box = useRef<HTMLPreElement | null>(null)
  useEffect(() => {
    if (box.current !== null) box.current.scrollTop = box.current.scrollHeight
  }, [text])
  if (text.trim() === '') return null
  return (
    <pre className="run-console" ref={box} aria-label={label} tabIndex={0}>
      {text}
    </pre>
  )
}

/** One box in the cart, as the picker hands it over: which box, what it is called, and which
 *  cards inside it. The READING is not here — it is chosen per box on this panel, beside the
 *  estimate it moves, because it is part of what the confirm is agreeing to buy.
 *
 *  `name` IS DRAWN AND NEVER SENT (D56). `legs` below projects a cart row to what the route
 *  reads, and the name is not in it — so it cannot reach `scopeKey`, which is what voids the
 *  estimate. That matters: renaming a drawer does not change a single byte of the send, and an
 *  estimate retired by a rename would be the money gate crying wolf. It comes from the picker's
 *  own `GET /boxes` rather than from the run list, because a cart row is a box the operator
 *  just chose and no run over it may yet exist. */
export type CartBox = { box: number; name?: string | null; indices: readonly number[] }

/** How a box is read until somebody says otherwise: D32's measured-best pair.
 *
 *  STATED HERE RATHER THAN READ OUT OF `READINGS[0]`, because a lazy initialiser indexing
 *  that table would be a second place the default lives and the two would drift the first
 *  time a row was reordered. The CLI's own defaults are the OTHER corner — crop off, 1568 —
 *  which is what `Whole frame` selects: this screen states a default rather than changing
 *  what an unflagged terminal run means. */
const DEFAULT_READING = { crop: true, maxEdge: 1200, custom: false }

type Reading = typeof DEFAULT_READING

type RunPanelProps = {
  /** THE CART: every box this send is over, in the order the picker offers them, each with
   *  the cards ticked inside it. `Runs.tsx` owns which boxes are in it and where a ticked
   *  selection came from; this panel owns how each is read and everything after the press. */
  cart: readonly CartBox[]
}

export function RunPanel({ cart }: RunPanelProps) {
  /* WHICH RUN IS OPEN, and nothing else about it. Every figure below is read from the server
   * on the next poll, so this component cannot hold a stale count — the failure that would
   * otherwise be invisible, because a wrong number on a run panel looks exactly like a right
   * one. */
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  const [detail, setDetail] = useState<RunDetail | null>(null)

  /* The preflight's answer, which is step one of the money gate. Cleared whenever the scope
   * moves, because an estimate for box 2 shown beside a confirm that would run box 3 is the
   * exact shape this gate exists to prevent. */
  const [quote, setQuote] = useState<RunPreflight | null>(null)
  const [ticketScope, setTicketScope] = useState<string>('')

  /* THE READING, PER BOX, AND THAT IS THE WHOLE REASON THIS IS A CART RATHER THAN ONE RUN
   * OVER SEVERAL BOXES. D32's frontier is a cost-against-sharpness trade measured on real
   * frames, and which end of it is right depends on what is IN the drawer: a box of bulk
   * commons wants `Cheapest · 900`, a box worth reading a collector number off wants
   * `Measured best · 1200`. One reading stretched across a send would make the cart a
   * convenience bought with accuracy.
   *
   * SPARSE, AND `DEFAULT_READING` FILLS THE GAPS. A box the operator has not touched has no
   * entry, so adding one to the cart cannot be a write — and a box that LEAVES the cart keeps
   * its entry, which is deliberate: re-ticking a box you just unticked should not silently
   * reset a reading you chose on purpose. Nothing is sent for a box that is not in the cart,
   * so a stale entry costs a few bytes of state and no correctness at all.
   *
   * `custom` IS AN ACT RATHER THAN A DERIVATION, unchanged from when there was one of these.
   * With the pair set by the presets, the only way to reach an arbitrary number is to ask for
   * one, and a `custom` that switched itself on whenever the pair stopped matching a row would
   * leave the operator unable to see which of the two states they were in. */
  const [readings, setReadings] = useState<Record<number, Reading>>({})
  const readingFor = useCallback(
    (box: number): Reading => readings[box] ?? DEFAULT_READING,
    [readings],
  )
  const setReading = useCallback((box: number, patch: Partial<Reading>) => {
    setReadings((held) => ({ ...held, [box]: { ...(held[box] ?? DEFAULT_READING), ...patch } }))
    /* AND THE PICTURE FOLLOWS THE READING THAT WAS JUST TOUCHED. Setting a chip on box 7's row
     * is the act that says "I am deciding about box 7", so the preview is of box 7 from that
     * press onward — one line, in the one function every reading change goes through, rather
     * than four call sites each remembering to do it. */
    setPreviewBox(box)
  }, [])

  const [bypass, setBypass] = useState(false)

  /* THE CROP PREVIEW'S STATE. `previewFor` is the reading-and-offset the strip on screen was
   * drawn for, compared against the one the controls currently name — the same shape
   * `ticketScope` uses against the estimate, and for the same reason: a picture of a reading
   * that is no longer selected is worse than no picture, because it is believed. */
  const [preview, setPreview] = useState<CropPreview | null>(null)
  const [previewFor, setPreviewFor] = useState('')
  const [previewOffset, setPreviewOffset] = useState(0)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewTrouble, setPreviewTrouble] = useState<string | null>(null)
  /* WHERE THE 1:1 VIEW IS LOOKING, in the SENT image's own pixels, or null for its resting
   * aim — the collector number where the registry claims one, the middle of the card where it
   * does not. Null rather than a computed default so that leaving the frame returns the view
   * to the thing worth reading rather than to wherever the pointer happened to exit. */
  const [aim, setAim] = useState<{ x: number; y: number } | null>(null)
  const detailRef = useRef<HTMLDivElement | null>(null)

  const [busy, setBusy] = useState<string | null>(null)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  /** Boxes whose child could not be spawned, from the last send. See `doStart`. */
  const [partial, setPartial] = useState<RunStartFailure[] | null>(null)
  const [stepOut, setStepOut] = useState<{ step: string; ok: boolean; console: string } | null>(
    null,
  )

  const exportPick = useRef<HTMLInputElement | null>(null)
  const stagedPick = useRef<HTMLInputElement | null>(null)

  /* THE SCOPE AS ONE STRING, so an effect can compare it. Two numbers and an array cannot be
   * compared by identity across renders — the array is rebuilt every time `BoxBrowse` reports
   * — and a deep compare written by hand here would be a second answer to a question a key
   * already answers. */
  /* WHAT WOULD ACTUALLY BE SENT, box by box, in the shape `server.ts` puts on the wire. One
   * derivation feeding the preflight, the confirm and the key below, so the three can never
   * describe different sends — which is the failure the whole two-step gate exists to
   * prevent. */
  const legs = useMemo(
    () =>
      cart.map((row) => {
        const reading = readings[row.box] ?? DEFAULT_READING
        return {
          box: row.box,
          indices: row.indices.length > 0 ? [...row.indices] : undefined,
          crop: reading.crop,
          maxEdge: reading.maxEdge,
        }
      }),
    [cart, readings],
  )

  /* WHETHER EVERY BOX IS READ THE SAME WAY, which decides where the sentence goes.
   *
   * THE SENTENCE IS PER READING, NOT PER BOX, AND A CART MADE THAT VISIBLE. D32's amendment
   * puts three or four lines under the chips saying what the pair costs and what it buys —
   * right for one box, and a wall for five, because the common case is a cart whose boxes are
   * all read the same way and the paragraph is then rendered identically once per box.
   * Observed at two boxes; at five it is fifteen lines of duplicate prose above the control
   * that spends.
   *
   * Derived, never stored: a second piece of state would let the sentence disagree with the
   * chips, which is the failure `reading` above is written to avoid one register down. Null
   * when the readings differ, and then each box says its own — which is the case where the
   * repetition is not repetition at all. */
  const sharedReading = useMemo(() => {
    if (cart.length === 0) return null
    const first = readings[cart[0]?.box ?? -1] ?? DEFAULT_READING
    const same = cart.every((row) => {
      const held = readings[row.box] ?? DEFAULT_READING
      return held.crop === first.crop && held.maxEdge === first.maxEdge && held.custom === first.custom
    })
    return same ? first : null
  }, [cart, readings])

  /* THE WHOLE SEND AS ONE STRING, so an effect can compare it. Boxes, their ticked cards and
   * their readings cannot be compared by identity across renders — the arrays are rebuilt
   * every time the picker reports — and a deep compare written by hand here would be a second
   * answer to a question a key already answers.
   *
   * ORDER-SENSITIVE ON PURPOSE, ON THE CARDS AND NOT ON THE BOXES: the indices are sorted
   * because ticking 4 then 2 is the same send as ticking 2 then 4, and the boxes are left in
   * cart order because that is the order the legs are sent and the order the answer comes back
   * in. A key that sorted the boxes would call two different-looking answers the same quote. */
  const scopeKey = useMemo(
    () =>
      legs
        .map(
          (leg) =>
            `${leg.box}:${(leg.indices ?? []).slice().sort((a, b) => a - b).join(',')}` +
            `:${leg.crop ? 'crop' : 'whole'}:${leg.maxEdge}`,
        )
        .join('|'),
    [legs],
  )

  const scoped = cart.length > 0

  /* WHAT THE CART CALLS A BOX, for the rows the SERVER answers about. The preflight replies
     per leg with a scope block — a box number and a card count — and no name, correctly: the
     route is answering what a send would cost, and what the drawer is called is not part of
     that. The name is already on screen for these boxes because the operator just picked them,
     so it is looked up here rather than added to a response that has no use for it. */
  const cartName = useCallback(
    (box: number) => cart.find((row) => row.box === box)?.name ?? null,
    [cart],
  )

  useEffect(() => {
    /* THE QUOTE IS VOID THE MOMENT THE SCOPE MOVES. Not merely stale — void: it is the first
     * step of a two-step confirm, and a confirm whose first step described a different set of
     * cards is not a confirm at all. Ticking one more card retires the estimate, and so does
     * adding a box to the cart or changing any box's reading — which is the same rule, now
     * that a send can be several boxes and each carries its own.
     *
     * AND THE READING IS PART OF THE SCOPE, which this key did not say until 2026-08-25. The
     * estimate is computed from the BYTES each card is sent as, and the crop and the max edge
     * are what decide those — so unticking the crop after Check cost left a stale figure
     * standing above a live `Spend $0.62 and identify 36 cards` button, describing a send that
     * was no longer the one about to happen. The rule above already covered it; the key just
     * named cards where it should also have named bytes. */
    if (ticketScope !== '' && ticketScope !== scopeKey) {
      setQuote(null)
      setTicketScope('')
    }
  }, [scopeKey, ticketScope])

  const loadRuns = useCallback(async () => {
    try {
      setRuns(await getRuns())
    } catch (err) {
      setTrouble(describeFailure(err))
    }
  }, [])

  /* THE LIST IS RE-READ WHILE THIS PANEL IS ON SCREEN, and the condition is deliberately NOT
   * "while something is live". A run started in a terminal BEGINS live, so a poll gated on a
   * snapshot that holds nothing live could never discover the one case D33 says this route
   * exists for — it would need the operator to reload the page to see their own run. What
   * varies with liveness is the CADENCE, not whether we look.
   *
   * Chained `setTimeout`, never `setInterval`: the detail poll below makes the same choice for
   * the same reason, which is that a slow answer must not stack requests behind it. No
   * dependencies, and liveness is read off the response just received rather than off `runs` —
   * depending on `runs` would tear the timer down and rebuild it on every tick.
   *
   * THE FIRST FAILURE IS REPORTED AND EVERY LATER ONE IS SWALLOWED. A dead server on arrival is
   * worth a sentence; the same sentence rewritten every twenty seconds is a note nobody asked
   * for, painted over the refusal `emit` printed a minute ago. */
  useEffect(() => {
    let cancelled = false
    let timer = 0
    let announced = false
    const tick = async () => {
      let anyLive = false
      try {
        const rows = await getRuns()
        if (cancelled) return
        setRuns(rows)
        anyLive = rows.some((row) => row.live)
      } catch (err) {
        if (!cancelled && !announced) setTrouble(describeFailure(err))
        announced = true
      }
      if (!cancelled) {
        timer = window.setTimeout(() => void tick(), anyLive ? POLL_MS : IDLE_POLL_MS)
      }
    }
    void tick()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  /* PER-RUN STATE BELONGS TO THE RUN IT WAS PRODUCED AGAINST, and none of it was cleared when
   * the open run changed. Opening run A, pressing Preview, then clicking run B left A's answer
   * on screen under B — and `saveDecisions` posts the textarea to whatever `openRun` is at the
   * moment of the press, so A's edited `decisions.json` could be written into B. Rendering a
   * step's answer inside its own step box makes a stale one MORE believable, not less, which is
   * what turns this from latent into worth fixing. One effect rather than an edit at each
   * `setOpenRun` call site, so a later caller cannot forget it. */
  useEffect(() => {
    setStepOut(null)
    setDecisions(null)
    setDecisionsBad(null)
  }, [openRun])

  /* THE POLL, and it runs only while the open run is live. A run the server says is not live
   * is a directory that is not changing, so polling it would be a request per four seconds
   * asking a question already answered. */
  useEffect(() => {
    if (openRun === null) {
      setDetail(null)
      return
    }
    let cancelled = false
    let timer = 0

    const tick = async () => {
      try {
        const next = await getRun(openRun)
        if (cancelled) return
        setDetail(next)
        if (next.live) timer = window.setTimeout(() => void tick(), POLL_MS)
        else void loadRuns()
      } catch (err) {
        if (!cancelled) setTrouble(describeFailure(err))
      }
    }
    void tick()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [openRun, loadRuns])

  const guard = useCallback(
    async (key: string, work: () => Promise<void>) => {
      setBusy(key)
      setTrouble(null)
      try {
        await work()
      } catch (err) {
        setTrouble(describeFailure(err))
      } finally {
        setBusy(null)
      }
    },
    [],
  )

  /* WHICH BOX THE PICTURE IS OF, once a send can be several (D48). The preview's whole job is
   * showing what THIS reading sends, and a reading belongs to a box now — so the box whose
   * chip was last pressed is the one being decided about, and the picture follows it. Null
   * means "the first in the cart", which makes a cart of one behave exactly as it did before
   * the cart existed.
   *
   * NOT one preview per row: that is N photographs decoded to answer one question, and the
   * owner already rejected three-abreast on the plainer ground that three pictures in a row
   * are three pictures too small to read. */
  const [previewBox, setPreviewBox] = useState<number | null>(null)

  const previewLeg = useMemo(
    () => legs.find((leg) => leg.box === previewBox) ?? legs[0] ?? null,
    [legs, previewBox],
  )

  const previewArgs = useMemo(
    () =>
      previewLeg === null
        ? null
        : {
            box: previewLeg.box,
            indices: previewLeg.indices,
            crop: previewLeg.crop,
            maxEdge: previewLeg.maxEdge,
          },
    [previewLeg],
  )

  /* THE PREVIEW'S OWN KEY, AND IT IS NOT THE CART'S. `scopeKey` covers every box and every
   * reading, because the ESTIMATE is about the whole send; the picture is about one leg. Keyed
   * on the cart, adding an unrelated box to it would refetch and redraw a photograph that had
   * not changed. */
  const previewKey =
    previewArgs === null
      ? ''
      : `${previewArgs.box}:${(previewArgs.indices ?? []).join(',')}` +
        `:${previewArgs.crop ? 'crop' : 'whole'}:${previewArgs.maxEdge}`

  /* THE PREVIEW FOLLOWS THE READING, and it is keyed on `scopeKey` — the same string that
   * voids the estimate below. The crop and the max edge are in that key already (D32's
   * amendment put them there when unticking the crop left a stale figure over a live spend
   * button), so a reading change redraws the picture and clears the number together. It runs
   * BEFORE `Check cost` rather than after: this is what the pair is chosen from, and the
   * estimate is what the choice then costs.
   *
   * DEBOUNCED, BECAUSE THE WALK IS HELD DOWN AS OFTEN AS IT IS TAPPED. An arrow key repeating
   * at ~30/s against a route that decodes a photograph would queue a request per frame for a
   * card nobody is looking at. 140ms is under the interval a key repeat produces and over the
   * one a human tapping produces, so a tap is immediate and a hold costs one request when it
   * stops.
   *
   * THE PREVIOUS CARD STAYS UP WHILE THE NEXT IS FETCHED. Blanking would make every press
   * flash the tallest block in this column out of and back into the document, and the column
   * beside it holds the button that spends. */
  useEffect(() => {
    if (!scoped || previewArgs === null) {
      setPreview(null)
      setPreviewFor('')
      return
    }
    const want = `${previewKey}:${previewOffset}`
    if (previewFor === want) return
    let live = true
    const timer = setTimeout(() => {
      setPreviewBusy(true)
      void (async () => {
        try {
          const answer = await cropPreview({ ...previewArgs, offset: previewOffset })
          if (!live) return
          setPreview(answer)
          setPreviewTrouble(null)
        } catch (err) {
          if (!live) return
          /* NAMED, NOT SWALLOWED. The one refusal an operator will actually meet is
           * `imaging_unavailable` — Pillow missing from the SERVER's interpreter — and its
           * remedy is a `make venv` and a restart they cannot guess at from an empty panel. */
          setPreview(null)
          setPreviewTrouble(describeFailure(err).message)
        } finally {
          if (live) {
            setPreviewFor(want)
            setPreviewBusy(false)
          }
        }
      })()
    }, 140)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [scoped, previewKey, previewOffset, previewFor, previewArgs])

  /* THE AIM IS RELEASED WHEN THE PICTURE CHANGES. It is a position in the SENT image's
   * pixels, and those move when the reading or the card does — so an aim carried across a
   * change would be pointing at a coordinate that no longer means what it meant. */
  useEffect(() => {
    setAim(null)
  }, [previewFor])

  /* A NEW BOX STARTS AT THE FRONT OF ITS OWN WALK. Without this, stepping through box 2 and
   * then picking box 6 would open box 6 at somebody else's offset.
   *
   * KEYED ON THE RESOLVED BOX AND NOT ON `previewBox`, WHICH IS THE DIFFERENCE BETWEEN A NEW
   * BOX AND A NEW READING. `previewBox` starts null and `previewLeg` falls back to the first
   * leg, so the first chip press changes the STATE from null to a box without changing which
   * box is being previewed — and keyed on the state, that press reset the walk. Caught by
   * `run-panel.spec.ts`'s arrow-key case: step to card 2, press Custom, and the caption fell
   * back to card 1. Setting the reading of the box you are already looking at must not throw
   * away where you are in it. */
  useEffect(() => {
    setPreviewOffset(0)
  }, [previewLeg?.box])

  /* THE WALK WRAPS RATHER THAN STOPPING, and it wraps HERE as well as on the route: the
   * server takes `offset % total` so a stale client can never send a negative, and this keeps
   * the number the caption prints inside the box the operator is looking at. */
  const stepPreview = useCallback(
    (by: number) =>
      setPreviewOffset((was) => {
        const total = preview?.total ?? 0
        return total > 0 ? (was + by + total) % total : Math.max(0, was + by)
      }),
    [preview],
  )

  /* ARROW KEYS WALK THE BOX — the owner asked for them by name, and the buttons beside the
   * card do the same thing because a key with no visible control is a key nobody finds.
   *
   * GUARDED ON THE EVENT'S TARGET, which is the whole subtlety. This panel holds a number
   * input (Custom's max edge) and a textarea (`decisions.json`), and an unguarded window
   * listener would steal the caret keys from both — the operator would be unable to move
   * through a number they were editing. Modifier chords are left alone too: they belong to
   * the browser and to `App.tsx`'s route chords. */
  useEffect(() => {
    if (!scoped) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) {
        return
      }
      event.preventDefault()
      stepPreview(event.key === 'ArrowRight' ? 1 : -1)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [scoped, stepPreview])

  /* THE 1:1 VIEW'S POSITION, in the sent image's own pixels.
   *
   * `background-size: auto` paints the file at its natural size and `background-position`
   * picks which natural pixel sits in the corner — that pair IS 1:1, with no scaling
   * arithmetic to get wrong. It is the review queue's loupe, aimed at the PAYLOAD instead of
   * at the stored photograph, and for the reason that screen gives: FADGI and Metamorfoze
   * both require this class of judgement at 100%, and a downscale is exactly what is being
   * judged here.
   *
   * CLAMPED INTO THE IMAGE, so the window never shows more empty ground than picture at the
   * edges of a card. */
  const detailPosition = useMemo(() => {
    const sample = preview?.sample
    if (sample?.sent == null) return undefined
    const [sentW, sentH] = sample.sent
    const node = detailRef.current
    const viewW = node?.offsetWidth ?? 320
    const viewH = node?.offsetHeight ?? 140
    let x: number
    let y: number
    if (aim !== null) {
      x = aim.x
      y = aim.y
    } else if (sample.band_rect != null) {
      /* THE RESTING AIM IS THE COLLECTOR NUMBER, left-aligned and vertically centred on the
         band — the registry knows where it is on a Pokemon card, so the operator should not
         have to go looking for the one region that decides the run. */
      x = sample.band_rect[0]
      y = sample.band_rect[1] + (sample.band_rect[3] - sample.band_rect[1] - viewH) / 2
    } else {
      x = (sentW - viewW) / 2
      y = (sentH - viewH) / 2
    }
    x = Math.max(0, Math.min(x, Math.max(0, sentW - viewW)))
    y = Math.max(0, Math.min(y, Math.max(0, sentH - viewH)))
    return `${-Math.round(x)}px ${-Math.round(y)}px`
  }, [preview, aim])

  /* POINTING AT THE FRAME AIMS THE 1:1 VIEW. The frame is drawn at a fraction of the sent
   * image's size, so a pointer position has to travel two coordinate systems: the box is the
   * ORIGINAL frame, and the view reads the SENT one. `rect` is the map between them, and its
   * absence is the whole-frame case where the two differ only by scale.
   *
   * IT IS WHAT MAKES A GAME WITH NO BAND USABLE AT ALL. The registry cannot say where a
   * Riftbound card prints its identifier, and it does not have to: the operator can. */
  const aimAt = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      const sample = preview?.sample
      if (sample?.frame == null || sample.sent == null) return
      const node = detailRef.current
      const box = event.currentTarget.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) return
      const [frameW, frameH] = sample.frame
      const cut = sample.rect ?? [0, 0, frameW, frameH]
      const originalX = ((event.clientX - box.left) / box.width) * frameW
      const originalY = ((event.clientY - box.top) / box.height) * frameH
      const sentX = ((originalX - cut[0]) / (cut[2] - cut[0])) * sample.sent[0]
      const sentY = ((originalY - cut[1]) / (cut[3] - cut[1])) * sample.sent[1]
      setAim({
        x: sentX - (node?.offsetWidth ?? 320) / 2,
        y: sentY - (node?.offsetHeight ?? 140) / 2,
      })
    },
    [preview],
  )

  const doQuote = () =>
    guard('quote', async () => {
      const answer = await preflightRun(legs)
      setQuote(answer)
      setTicketScope(scopeKey)
    })

  const doStart = () =>
    guard('start', async () => {
      const answer = await startRun(legs)
      /* The quote is spent. Clearing it forces a fresh preflight before a second send can be
       * started, which is what stops a confirm being pressed twice on one estimate. */
      setQuote(null)
      setTicketScope('')
      /* WHAT DID NOT START, KEPT ON SCREEN UNTIL THE NEXT PRESS. `Popen` can fail on the
       * fourth leg after three have started and no validation sees that coming, so the route
       * answers with both halves and this is where the failed half is drawn. Swallowing it
       * would report a partial send as a whole one, which is an invoice nobody can account
       * for. */
      setPartial(answer.failed.length > 0 ? answer.failed : null)
      /* The FIRST run started, which for a cart of one is the only one. Opening it is what
       * the operator wants next either way — the rest are one click down the list, and a
       * panel that opened the last of five would be answering a question nobody asked. */
      const first = answer.started[0]
      if (first !== undefined) setOpenRun(first.run)
      await loadRuns()
    })

  const doStep = (step: 'join' | 'emit' | 'reconcile', extra: Parameters<typeof runStep>[2] = {}) =>
    guard(step, async () => {
      if (openRun === null) return
      const result = await runStep(openRun, step, extra)
      /* THE STEP WE ASKED FOR, NOT THE ONE THE SERVER ECHOED, now that the answer renders
         inside its own step box. `result.step` is the echo, and it is demonstrably not the
         local truth: `app/tests/run-panel.spec.ts` mocks all three routes and returns
         `step: 'join'` for every one. That was harmless while this rendered unconditionally
         and would now put an emit result inside the Join box — or, on a real mismatch, make
         the answer vanish from the screen entirely. */
      setStepOut({ step, ok: result.ok, console: result.console })
      setDetail(await getRun(openRun))
      await loadRuns()
    })

  const pickExports = () =>
    guard('exports', async () => {
      const chosen = Array.from(exportPick.current?.files ?? [])
      if (chosen.length === 0 || openRun === null) return
      const uploads = await Promise.all(chosen.map(readUpload))
      const result = await runStep(openRun, 'join', { exports: uploads, bypass })
      setStepOut({ step: 'join', ok: result.ok, console: result.console })
      setDetail(await getRun(openRun))
      await loadRuns()
      if (exportPick.current !== null) exportPick.current.value = ''
    })

  const pickStaged = () =>
    guard('staged', async () => {
      const chosen = stagedPick.current?.files?.[0]
      if (chosen === undefined || openRun === null) return
      const result = await runStep(openRun, 'reconcile', { stagedExport: await readUpload(chosen) })
      setStepOut({ step: 'reconcile', ok: result.ok, console: result.console })
      setDetail(await getRun(openRun))
      if (stagedPick.current !== null) stagedPick.current.value = ''
    })

  /* ------------------------------------------------------ D9's pricing answer, as a document
   *
   * A TEXT EDITOR AND NOT A FORM, and that is a considered choice rather than a shortcut. The
   * route it writes through says in its own comment that it does not validate what a
   * disposition MEANS — `emit` owns that refusal — and a typed form here would have to encode
   * the schema a second time, in TypeScript, where nothing audits it against
   * `pipeline/decisions.py`. That is the drift D16 exists to catch, and the same argument
   * `docs/DESIGN.md` makes for showing reason codes verbatim.
   *
   * The file already explains itself: `join` writes a `_note` block naming every field and
   * what `emit` will refuse without. Showing the operator that block is worth more than any
   * label this component could write over the top of it. */
  const [decisions, setDecisions] = useState<string | null>(null)
  const [decisionsBad, setDecisionsBad] = useState<string | null>(null)

  const openDecisions = () =>
    guard('decisions-read', async () => {
      if (openRun === null) return
      const response = await fetch(runFileUrl(openRun, 'decisions.json'), { cache: 'no-store' })
      if (!response.ok) {
        setTrouble({
          code: 'decisions_not_written',
          message:
            'This run has no decisions.json yet. Join is what writes it, with every SKU that ' +
            'needs an answer already filled in.',
        })
        return
      }
      setDecisions(await response.text())
      setDecisionsBad(null)
    })

  const saveDecisions = () =>
    guard('decisions-write', async () => {
      if (openRun === null || decisions === null) return
      let parsed: Record<string, unknown>
      try {
        parsed = JSON.parse(decisions) as Record<string, unknown>
      } catch (err) {
        /* Parsed HERE rather than sent, because a body that is not JSON would come back as
         * `body_invalid` from the request layer and the operator would have lost their edit in
         * the round trip. The message is the browser's own parse error, which names the
         * character — the one thing this side of the wire knows better than the server. */
        setDecisionsBad(err instanceof Error ? err.message : String(err))
        return
      }
      await putDecisions(openRun, parsed)
      setDecisionsBad(null)
      setDecisions(null)
    })

  /* ------------------------------------------------------------------------------- render */

  const runRow = (row: RunSummary) => (
    <button
      key={row.run}
      type="button"
      className={`run-row${row.run === openRun ? ' run-row-open' : ''}`}
      aria-pressed={row.run === openRun}
      onClick={() => setOpenRun(row.run === openRun ? null : row.run)}
    >
      <span className="run-row-name">{row.run}</span>
      <span className={`run-phase run-phase-${row.phase}`}>
        {row.live ? runningFor(row) : row.phase}
      </span>
      <span className="run-row-scope">{scopeOf(row)}</span>
    </button>
  )

  /* THE RUNS FOR THE BOX YOU ARE STANDING IN, FIRST — AND NOTHING IS EVER FILTERED OUT. D33
     makes a run outlive the tab that started it, so a live run over another box is exactly the
     thing this list must not hide; `aria-label="Every run"` stays literally true under a
     reordering and would become a lie under a filter.
     
     PARTITIONED, NOT SORTED. The server already returns newest-first — `sorted(..., reverse=True)`
     over date-prefixed run names — so walking once and pushing into three buckets keeps each
     group newest-first for free. Comparing `created_at` would be worse than useless: it is
     `string | null | undefined`, and a run missing it would sort to an arbitrary end. */
  const inCart = new Set(cart.map((row) => row.box))
  const running: RunSummary[] = []
  const mine: RunSummary[] = []
  const other: RunSummary[] = []
  for (const row of runs) {
    if (row.live) running.push(row)
    else if (inCart.has(boxOf(row) ?? -1)) mine.push(row)
    else other.push(row)
  }

  /* No box in the cart means no box to group against, so the list is drawn exactly as the
     server sent it — a distinction with nothing to distinguish is chrome.

     THIS TEST WAS INVERTED AND THE GROUPING IT COMPUTED WAS THROWN AWAY. It read
     `scope.box === null`, so the partition above ran, produced `mine`, and then rendered
     `runs` in server order whenever a box actually WAS selected — while an unscoped screen,
     where `mine` is empty by construction, got the three-group order and could draw an
     `other boxes` caption with no box to be other than. Both halves were backwards at once,
     which is why neither looked wrong on its own. */
  const grouped = cart.length > 0
  const runRows = grouped
    ? [...running, ...mine, ...other].map(runRow)
    : runs.map(runRow)

  /* ONLY THE THIRD GROUP IS CAPTIONED, and the useful case is when it is the whole list —
     that is the caption saying none of these runs are about the box you are in. A live row
     needs no caption: `.run-phase-identifying` already draws `running` in ink at 600, which
     is this file's own emphasis grammar. */
  const otherCaption =
    grouped && other.length > 0 && other.length < runs.length ? (
      <p className="run-group" key="other-caption">
        other boxes
      </p>
    ) : null


  /* THE LIVE COUNT, WHICH USED TO RIDE THE PANEL'S OWN HEAD BESIDE THE FOUR COMMAND NAMES.
   * That head is gone: on `#/runs` the page draws the title and the scope, and a panel titled
   * `Runs` under a page titled `Runs` is one of them saying nothing. The four command names
   * moved to the page's lede, where they are the sentence that says what this screen is.
   *
   * THE COUNT MOVED ONTO THE LIST INSTEAD OF DYING WITH THE HEAD, and it belongs there better
   * than it did on the head: it is a caption for the rows directly beneath it, and `live` is the
   * one figure on this screen that changes without anybody pressing anything. */
  const live = runs.filter((row) => row.live).length
  const tally =
    runs.length === 0
      ? null
      : [
          `${runs.length} run${runs.length === 1 ? '' : 's'}`,
          live > 0 ? `${live} running` : null,
        ]
          .filter(Boolean)
          .join(' · ')

  return (
    /* NOT FOLDED, AND THE COMMENT THAT USED TO SIT HERE SAID OTHERWISE FOR LONGER THAN THE
     * CODE DID. It argued the fold on `BoxOps`' measured grounds — ~250px, above the card
     * detail, reached once a box — and pointed at a `defaultOpen` prop and a `<details>` that
     * were removed when D33 was amended. The markup below is a plain `<div>`: no disclosure,
     * no triangle, nothing to press before the four commands are reachable.
     *
     * The owner overruled the fold in three messages, the last unambiguous: "both box and
     * run, i don't want click in functionality, i want their buttons just there." D33 carries
     * the argument — reached once a box IS every box, which is the definition of the primary
     * task rather than an exception to it, and NN/g prices a collapsed panel at five
     * accumulating substeps before the first click of real work.
     *
     * WHAT REPLACES THE FOLD'S SAVING IS THE COLUMN, and that sentence has been rewritten once.
     * It first said the ROW — `.browse-boxrun` at `1fr 1fr`, this panel beside `BoxOps` beneath
     * the card, so the pair cost one panel's height rather than two. On 2026-08-25 the owner
     * moved the pair off the card's column entirely: "put box top right, and runs below it."
     * Beside the card rather than under it, the pair costs the card's column NOTHING, which is
     * the same argument at its limit rather than a different one. */
    <div className="run-panel">
      {/* NO HEAD. It drew `Runs`, the scope and the four command names while this was a panel on
          somebody else's screen and had to say what it was; on a route of its own the page says
          all three above it, and a second title under the first is the drift docs/DESIGN.md's
          page-chrome rule exists to stop — a title block over a toolbar, measured at 240px on
          this product's worst screen. `Runs.tsx` carries the three pieces: title, scope on its
          line, command names in the lede. */}
      {trouble === null ? null : (
        <div className="run-note">
          <p className="run-note-text">{trouble.message}</p>
          {/* The greppable token beneath the sentence — docs/DESIGN.md's human-label-large,
              machine-string-small rule, the same shape Inventory.tsx draws a refusal in. */}
          <p className="run-machine">{trouble.code}</p>
        </div>
      )}

      {/* ------------------------------------------------------------- step 1: identify */}
      <div className="run-step">
        <div className="run-step-head">
          <span className="run-step-title">{STEPS[0].title}</span>
          <span className="run-step-cost run-step-money">{STEPS[0].cost}</span>
        </div>
        <p className="run-step-note">{STEPS[0].note}</p>

        <div className="run-identify">
          <div className="run-identify-controls">

        {/* ------------------------------------------------------------------- the cart

            ONE ROW PER BOX, EACH WITH ITS OWN READING. The strip on this page decides WHICH
            boxes; this decides how each is read, because the reading is part of what the
            confirm below is agreeing to buy — the estimate is computed from the bytes each
            card is sent as, and the crop and the max edge are what decide those.

            EVERY BOX IN THE CART IS ITS OWN RUN. One press starts several children, and
            nothing downstream learns a new shape: each box gets a run directory, a manifest,
            a queue, its own `--bypass` decision at join and its own `decisions.json`. What is
            new is a fact about the REQUEST, not about a run.

            THE READING IS DRAWN AS A PAIR RATHER THAN AS TWO CONTROLS — see `READINGS` above
            for the measurement that decides it, and for why a checkbox beside a free number
            was an invitation to spend more by asking for less. */}
        {cart.length === 0 ? (
          <p className="run-needs">Pick a box above. You can pick several.</p>
        ) : (
          cart.map((row) => {
            const held = readingFor(row.box)
            /* WHICH ROW THE PAIR IS, and the sentence that goes under it. Derived rather than
               stored, so the chip that reads as chosen and the values actually sent cannot
               come apart — the failure a second piece of state here would eventually produce.
               `custom` wins the tie: with the raw controls revealed, the operator is holding
               the knob whatever the numbers happen to say. */
            const match =
              READINGS.find((r) => r.crop === held.crop && r.maxEdge === held.maxEdge) ?? null
            return (
              <div className="run-leg" key={row.box}>
                <p className="run-leg-head">
                  {/* THE DRAWER BY NAME, ON THE ROW THAT DECIDES WHAT IT COSTS TO READ IT.
                      D33's gate is two presses over a number the operator cannot miss, and
                      what that number buys is a box — which until D56 this row could only
                      call by its digit, on the one screen in the product that spends. */}
                  <span className="run-leg-box">{boxLabel(row.box, row.name)}</span>
                  <span className="run-leg-scope">
                    {row.indices.length > 0
                      ? `${row.indices.length} ticked card${row.indices.length === 1 ? '' : 's'}`
                      : 'the whole box'}
                  </span>
                </p>

                <div
                  className="run-controls run-readings"
                  role="group"
                  aria-label={`How box ${row.box} is read`}
                >
                  {READINGS.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      className="run-button run-reading"
                      aria-pressed={!held.custom && match?.key === option.key}
                      onClick={() =>
                        setReading(row.box, {
                          custom: false,
                          crop: option.crop,
                          maxEdge: option.maxEdge,
                        })
                      }
                    >
                      {option.label}
                      <span className="run-reading-edge">{option.maxEdge}</span>
                    </button>
                  ))}
                  <button
                    type="button"
                    className="run-button run-reading"
                    aria-pressed={held.custom}
                    onClick={() => setReading(row.box, { custom: true })}
                  >
                    Custom
                  </button>
                </div>

                {held.custom && (
                  /* THE RAW CONTROLS, UNCHANGED AND DEMOTED RATHER THAN DELETED.
                     `Sharpest · 1400` and everything else on D32's frontier is reachable
                     here, and so is every pairing the three chips refuse to offer —
                     including the wrong one, which is why the sentence beneath this block is
                     the one that names it. */
                  <div className="run-controls">
                    <label className="run-toggle">
                      <input
                        type="checkbox"
                        checked={held.crop}
                        onChange={(event) =>
                          setReading(row.box, { crop: event.target.checked })
                        }
                      />
                      Crop to the card
                    </label>
                    <label className="run-field">
                      Max edge
                      <input
                        type="number"
                        min={256}
                        max={4096}
                        step={100}
                        value={held.maxEdge}
                        onChange={(event) =>
                          setReading(row.box, { maxEdge: Number(event.target.value) })
                        }
                      />
                      px
                    </label>
                  </div>
                )}

                {/* WHAT THE READING MEANS, BEFORE Check cost IS PRESSED. The command prints
                    its own crop line into the preflight stdout below, and that line is the
                    receipt — but a receipt arrives after the decision, and this is the
                    decision.

                    DRAWN HERE ONLY WHERE THE BOXES DISAGREE. Where they all read the same way
                    it is hoisted to one line beneath the cart, because the sentence is about
                    the READING and not about the box — see `sharedReading`. */}
                {sharedReading !== null ? null : (
                  <p className="run-step-note run-step-fine">
                    {held.custom || match === null ? CUSTOM_SAYS : match.says}
                  </p>
                )}
              </div>
            )
          })
        )}

        {sharedReading === null ? null : (
          /* ONE SENTENCE FOR A CART READ ONE WAY. Same text, same register, same place in the
             reading order — what changes is that it is said once. */
          <p className="run-step-note run-step-fine">
            {sharedReading.custom
              ? CUSTOM_SAYS
              : (READINGS.find(
                  (row) => row.crop === sharedReading.crop && row.maxEdge === sharedReading.maxEdge,
                )?.says ?? CUSTOM_SAYS)}
          </p>
        )}

        <div className="run-actions">
          <button
            type="button"
            className="run-button"
            disabled={!scoped || busy !== null}
            onClick={() => void doQuote()}
          >
            {busy === 'quote'
              ? 'Checking…'
              : cart.length > 1
                ? `Check cost for ${cart.length} boxes`
                : 'Check cost'}
          </button>
        </div>

        {partial === null ? null : (
          /* WHAT DID NOT GO, FROM THE LAST PRESS. Drawn as loudly as a refusal because it is
             one, arriving after the rest of the send already succeeded — the boxes named here
             have no run and no invoice, and pressing again is what starts them. */
          <div className="run-note">
            <p className="run-note-text">
              {partial.length} box{partial.length === 1 ? '' : 'es'} did not start. The rest of
              the send did. Press again for {partial.length === 1 ? 'it' : 'them'}.
            </p>
            {partial.map((row) => (
              <p className="run-machine" key={row.box}>
                box {row.box} · {row.code} · {row.message}
              </p>
            ))}
          </div>
        )}

        {quote === null ? null : (
          <div className="run-quote">
            {/* STEP ONE OF THE TWO-STEP CONFIRM, and the confirm below cannot be reached
                without it. The numbers are the commands' own — lifted out of each box's
                preflight stdout rather than recomputed anywhere — and the TOTAL is summed on
                the server, because the figure the confirm is gated on must not be a `reduce`
                in TypeScript sitting beside the per-box figures it claims to add up. */}
            <dl className="run-figures">
              <div>
                <dt>Photographs</dt>
                <dd>{count(quote.total.photographs)}</dd>
              </div>
              <div>
                <dt>Already answered</dt>
                <dd>{count(quote.total.cache_hits)}</dd>
              </div>
              <div>
                <dt>To send</dt>
                <dd>{count(quote.total.to_send)}</dd>
              </div>
              <div className="run-figure-money">
                <dt>Estimated cost</dt>
                <dd>{money(quote.total.estimate_usd)}</dd>
              </div>
            </dl>

            {quote.scopes.length < 2 ? null : (
              /* PER BOX, ONLY WHERE THERE IS MORE THAN ONE. For a single box the total IS the
                 box, and a second row restating it is chrome that says nothing — the same
                 judgement `otherCaption` makes about a group with nothing to be grouped
                 against. One line each rather than four figures, because what a person checks
                 here is that the boxes are the ones they meant and that no single one is
                 wildly dearer than they expected. */
              <dl className="run-legs">
                {quote.scopes.map((leg) => (
                  <div key={leg.scope.box}>
                    <dt>{boxLabel(leg.scope.box, cartName(leg.scope.box))}</dt>
                    <dd>
                      {count(leg.to_send)} to send · {money(leg.estimate_usd)}
                      {leg.scope.whole_box ? '' : ` · ${count(leg.scope.cards)} ticked`}
                    </dd>
                  </div>
                ))}
              </dl>
            )}

            {(quote.total.cache_hits ?? 0) > 0 && (
              /* WHAT `Already answered` COSTS YOU, said where that figure is drawn. D32
                 records it as a known gap kept deliberately: neither the crop nor the max
                 edge is part of the cache identity, so a box re-read at a different reading
                 serves the answers it was first read with and reports them as hits. That is
                 safe and it is not obvious, and the controls it silently ignores are directly
                 above. Stated as what it means to the person about to press the button rather
                 than as a fact about a hash — the panel has no business naming
                 `prompt_fingerprint`. */
              <p className="run-step-note run-step-fine">
                Cards already answered keep the answer they were first read with. The readings
                above only reach the cards being sent.
              </p>
            )}

            {quote.total.busy.length > 0 ? (
              <p className="run-blocked">
                {quote.total.busy
                  .map((row) => `${row.run} is already identifying box ${row.box}`)
                  .join('. ')}
                . Two runs over one box is two invoices for one answer — open it below and
                watch it instead. Nothing in this send would start while that is true.
              </p>
            ) : quote.total.to_send === 0 ? (
              <p className="run-blocked">
                Every one of these cards is already answered and cached. There is nothing to
                send and nothing to spend.
              </p>
            ) : (
              <button
                type="button"
                className="run-button run-button-money"
                disabled={busy !== null}
                onClick={() => void doStart()}
              >
                {busy === 'start'
                  ? 'Starting…'
                  : `Spend ${money(quote.total.estimate_usd)} and identify ` +
                    `${count(quote.total.to_send)} cards` +
                    (quote.scopes.length > 1 ? ` in ${quote.scopes.length} boxes` : '')}
              </button>
            )}

            {/* EVERY COMMAND'S STDOUT, VERBATIM, BENEATH THE CONTROL RATHER THAN ABOVE IT.
                D33's copy rule is that the pipeline's own words appear on the owner's screens
                unsummarised, and they do — one console per box, each labelled with its box.
                What moved is the ORDER, and only once a cart can hold several: a console is
                capped at 260px, so five of them above the button would put the confirm most
                of a screen below the figures it is confirming, which is the one thing the
                money gate may not allow. The figures are the decision and the consoles are
                the evidence; the decision goes first. */}
            {quote.scopes.map((leg) => (
              <Console
                key={leg.scope.box}
                text={leg.console}
                label={
                  `What the preflight printed for ${boxLabel(leg.scope.box, cartName(leg.scope.box))}`
                }
              />
            ))}
          </div>
        )}
          </div>

          {/* WHAT THE READING SENDS, AS A PICTURE, BESIDE THE CONTROL THAT SETS IT.
              D32's amendment answered "walk me through how im supposed to understand crop with
              just this dialog box" with three named pairs and a sentence each. The sentences are
              true and they are prose about pixels; this is the same answer in the medium the
              decision is actually about.

              ONE CARD, AT THE SIZE OF ITS OWN COLUMN (the owner, 2026-08-29). It was three
              abreast under the chips for a few hours, sampled evenly across the box because
              cards move on the tray — sound about sampling, and it lost to a plainer fact: three
              pictures in a row are three small pictures, and the operator could not see what
              they were being shown. The spread is reached by WALKING now, which is also the only
              version of it that lets you look at a card you actually suspect. */}
          {scoped && (previewTrouble !== null || preview !== null) && (
            <div className="run-preview">
              <div className="run-preview-head">
                <h4 className="run-preview-title">What this sends</h4>
                {preview !== null && (
                  <span className="run-preview-count">
                    card {preview.offset + 1} of {count(preview.total)}
                  </span>
                )}
              </div>

              {previewTrouble !== null ? (
                <p className="run-step-note run-step-fine">{previewTrouble}</p>
              ) : preview === null ? null : preview.sample.unreadable !== undefined ||
                preview.sample.frame === undefined ? (
                <p className="run-preview-fact">
                  #{preview.sample.index} — this photograph cannot be decoded, so nothing is
                  sent for it.
                </p>
              ) : (
                <div className="run-preview-card" aria-busy={previewBusy}>
                  <div
                    className="run-preview-frame"
                    onPointerMove={aimAt}
                    onPointerLeave={() => setAim(null)}
                  >
                    {/* WHAT IS THROWN AWAY, AND IT IS DRAWN AS SUCH. The stored photograph
                        sits underneath at a low opacity, so the margin outside the cut is
                        visible as something the run will never see rather than as an equal
                        part of the picture. */}
                    <img
                      className="run-preview-ghost"
                      src={photoUrl(preview.sample.box, preview.sample.index)}
                      alt=""
                      aria-hidden="true"
                      draggable={false}
                    />
                    {/* THE PAYLOAD ITSELF, at the cut's own position. This is the half the
                        owner asked for: the frame used to draw the stored file, which is the
                        same bytes at every reading — so the one thing being changed was the
                        one thing the picture could not show. Positioned in PERCENTAGES of the
                        frame, so it is right at whatever size the column happens to give it. */}
                    {preview.sample.sent_image != null && (
                      <img
                        className="run-preview-sent"
                        src={preview.sample.sent_image}
                        alt={`Box ${preview.sample.box}, card ${preview.sample.index}, as this reading sends it`}
                        draggable={false}
                        style={
                          preview.sample.rect != null && preview.sample.frame != null
                            ? {
                                left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                                top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                                width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                                height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                              }
                            : { left: 0, top: 0, width: '100%', height: '100%' }
                        }
                      />
                    )}
                    {preview.sample.rect != null && preview.sample.frame != null && (
                      <div
                        className="run-preview-cut"
                        style={{
                          left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                          top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                          width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                          height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                        }}
                      />
                    )}
                  </div>

                  {/* THE 1:1 WINDOW, onto the SAME file the frame is drawing. `background-size:
                      auto` paints it at its natural size, so this is where the reading is
                      actually legible: the frame is ~28% of the sent pixels and no downscale is
                      distinguishable at that size, while here 1200 and 900 cannot look alike.

                      IT RESTS ON THE COLLECTOR NUMBER and follows the pointer over the frame.
                      The registry knows where the number is on a Pokemon card; on a game where
                      it does not, the operator points at it themselves — which is what makes
                      this usable for Riftbound at all. */}
                  <div
                    ref={detailRef}
                    className="run-preview-detail"
                    style={{
                      backgroundImage:
                        preview.sample.sent_image != null
                          ? `url(${preview.sample.sent_image})`
                          : undefined,
                      backgroundPosition: detailPosition,
                    }}
                    role="img"
                    aria-label={`Card ${preview.sample.index} at full size, as this reading sends it`}
                  />
                  <p className="run-preview-fact">
                    <span>{aim === null ? 'resting on the collector number' : 'where you are pointing'}</span>
                    <span>at 1:1</span>
                    {preview.sample.band_px != null && (
                      <span>
                        number {preview.sample.band_px[0]}×{preview.sample.band_px[1]}
                      </span>
                    )}
                  </p>
                  {preview.sample.band_absent != null && (
                    /* THE REGISTRY REFUSED A RESTING AIM AND SAYS SO. `pipeline/games.py` holds
                       which bands a game claims, and only `pokemon` claims a number band — the
                       fractions in `geometry/crop.py` were measured on a Pokemon card. This
                       block drew them over a Riftbound card for one afternoon and rendered its
                       rules text as though it were a collector number. */
                    <p className="run-step-note run-step-fine">{preview.sample.band_absent}</p>
                  )}

                  <p className="run-preview-fact">
                    <span className="run-preview-slot">#{preview.sample.index}</span>
                    {/* THE CARD ABOVE IS THE PAYLOAD, DRAWN SMALL, AND THAT HAS TO BE SAID.
                        It is ~28% of the sent pixels, and no two downscales are
                        distinguishable at that size — so an operator comparing 1200 against
                        900 up there will correctly see no difference and wrongly conclude
                        there is none. This sentence points at the window that can show it. */}
                    {preview.sample.sent != null && (
                      <span>
                        sends {preview.sample.sent[0]}×{preview.sample.sent[1]}, shown reduced
                      </span>
                    )}
                    {/* A REFUSAL IS NOT THE SAME FACT AS THE CROP BEING OFF, and `rect` alone
                        cannot tell them apart. */}
                    {preview.sample.method == null && <span>no card found — sent whole</span>}
                  </p>

                  {/* THE WALK. Arrow keys do the same thing, which is what the owner asked
                      for; these exist because a key with no visible control is a key nobody
                      finds, and because a pointer is sometimes already in the hand. */}
                  <div className="run-preview-walk">
                    <button
                      type="button"
                      className="run-button run-preview-step"
                      aria-label="The card before this one"
                      onClick={() => setPreviewOffset((was) => was - 1)}
                    >
                      ←
                    </button>
                    <span className="run-preview-hint">arrow keys walk the box</span>
                    <button
                      type="button"
                      className="run-button run-preview-step"
                      aria-label="The card after this one"
                      onClick={() => setPreviewOffset((was) => was + 1)}
                    >
                      →
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------ the run list */}
      {tally === null ? null : <p className="run-list-head">{tally}</p>}
      <div className="run-list" aria-label="Every run">
        {runRows.length === 0 ? (
          <p className="run-empty">No runs yet.</p>
        ) : otherCaption === null ? (
          runRows
        ) : (
          <>
            {runRows.slice(0, running.length + mine.length)}
            {otherCaption}
            {runRows.slice(running.length + mine.length)}
          </>
        )}
      </div>

      {/* --------------------------------------------------------- the run the steps act on */}
      {detail === null ? (
        /* SAID ONCE, ABOVE THE THREE BOXES IT GOVERNS, rather than three times inside them.
           The steps below are drawn whatever happens (see the STEPS comment at the top of this
           file); what they cannot do without a run is act, and this is the sentence that says
           which of those two states the operator is in. */
        <p className="run-needs">
          {runs.length === 0
            ? 'Identify a box first — join, emit and reconcile all work on a run.'
            : 'Pick a run above to point these three at it.'}
        </p>
      ) : (
        <div className="run-open">
          <div className="run-open-head">
            <span className="run-open-name">{detail.run}</span>
            <span className={`run-phase run-phase-${detail.phase}`}>
              {detail.live ? runningFor(detail) : detail.phase}
            </span>
          </div>

          {!detail.joined ? null : (
            /* WHAT CAME OUT OF THE RUN, on the run rather than in a file. Neither run on disk
               has a `console.log` — `_console_tail` reads a file only the spawned identify
               child writes, and both existing runs were started from a terminal — so before
               this an open run drew its name, its phase and its files and NOTHING about its
               result. `counts` has ridden every poll since `cli/cmd_join.py` wrote it and the
               panel discarded it. `docs/GATES.md` names exactly this as what Gate B did not
               close.

               `.run-figures` VERBATIM, and the reuse is the point: that grid's own comment
               records the measurement that FOUR figures pack a balanced 2x2 at 96px in this
               column where three per row was a ragged 123px. Four is the measured-good number,
               which is why `no_market_data` and `sub_threshold` are deliberately not here — a
               fifth figure is a third row, and emit's note already states that refusal.

               REVIEW AND PARKED ARE TWO FIGURES AND MUST NEVER BE SUMMED. `report.txt` prints
               them as two lines because they are two facts: main is worked expensive-first
               behind a starvation tier, parked is sub-threshold and not listed (D9). A combined
               "46 queued" is a number no log in this repo carries.

               DRAWN ONLY WHEN `joined`, because counts are written by join. Before it there are
               none, and four em-dashes are chrome that says nothing. */
            <dl className="run-figures">
              <div>
                <dt>Cards in</dt>
                <dd>{count(detail.counts.cards_in)}</dd>
              </div>
              <div>
                <dt>SKUs</dt>
                <dd>{count(detail.counts.skus)}</dd>
              </div>
              {/* THE TWO QUEUE FIGURES ARE THE WAY INTO THE QUEUE, and until 2026-08-29 they
                  were the only numbers on this screen that named a place the app could not
                  reach: join writes a queue and the panel reported its depth with no route out
                  of the report. That is `CLAUDE.md`'s route-is-not-a-feature rule in miniature —
                  a capability with a screen, a screen with no way to it — and it cost one anchor
                  each.

                  BOTH GO TO `#/review`, which is the one screen that holds either. The parked
                  queue is not a second route: `ReviewQueue.tsx` draws both files and its reason
                  chips filter between them, so a link that promised otherwise would be
                  promising a screen that does not exist.

                  `aria-label` BECAUSE THE LINK TEXT IS A BARE NUMBER. "46" is a fine thing to
                  read beside its `dt` and a useless accessible name on its own, and a screen
                  reader announcing links out of context is exactly the case this attribute is
                  for. */}
              <div>
                <dt>Review</dt>
                <dd>
                  <a
                    className="run-figure-link"
                    href="#/review"
                    aria-label={`Answer ${count(detail.counts.queued_main)} in the review queue`}
                  >
                    {count(detail.counts.queued_main)}
                  </a>
                </dd>
              </div>
              <div>
                <dt>Parked</dt>
                <dd>
                  <a
                    className="run-figure-link"
                    href="#/review"
                    aria-label={`See ${count(detail.counts.queued_parked)} parked in the review queue`}
                  >
                    {count(detail.counts.queued_parked)}
                  </a>
                </dd>
              </div>
              <div>
                {/* THE WAY INTO PRICING, AND IT IS A LINK RATHER THAN A HANDOFF (D49). A run
                    name has ONE source of truth — `GET /pipeline/runs` reads the runs
                    directory — so `#/pricing` draws its own picker and cannot disagree with
                    anything, which is the property D39's ticked selection did not have and
                    the reason that one needed `sessionStorage`. Carrying the name in the URL
                    removes the double-pick at no cost: no second storage key, no clearing
                    rules, and `,P` on its own still lands on a picker that works. */}
                <dt>Price</dt>
                <dd>
                  <a
                    className="run-figure-link"
                    href={`#/pricing?run=${encodeURIComponent(detail.run)}`}
                    aria-label={`Price the ${count(detail.counts.skus)} SKUs in ${detail.run}`}
                  >
                    {count(detail.counts.skus)}
                  </a>
                </dd>
              </div>
            </dl>
          )}

          {detail.bypass_detection && (
            /* NAMED ON THE RUN, not only in its log. D3's amendment: a run joined with the
               detection cross-check off resolved some cards by the operator's own claim, and
               they chose "resolved by the claim, and the run report says so". A count that
               appeared only in a file nobody opened would not be that. */
            <p className="run-flagged">
              Joined with the photo cross-check off — {count(detail.bypassed)} card
              {detail.bypassed === 1 ? '' : 's'} resolved by your finish claim.
            </p>
          )}

          <Console text={detail.console} label={`What ${detail.run} printed`} />
        </div>
      )}

      {/* ------------------------------------- the other three steps, drawn in every state */}
      {/* THE PROMISE AT THE TOP OF THIS FILE, KEPT AT LAST. `STEPS` says it is authored rather
          than derived from `phase` because "a screen that only drew the current step would
          leave the operator unable to see that emit exists until join had finished" — and that
          was true of `phase` and false of `detail`: these three lived inside the open-run guard,
          so with no run picked the panel drew Identify and nothing else, and with no runs at all
          they existed nowhere on the screen. `app/tests/run-panel.spec.ts` demonstrated the gap
          in its own body, having to click a run row before it could assert the four titles.

          THE HEADS AND NOTES ALWAYS DRAW; THE CONTROLS DO NOT. What a step IS does not depend on
          a run — what it can be pressed against does. Absent rather than disabled, which is the
          discipline the money gate already keeps two blocks up and for the reason `.run-button`'s
          own comment gives: a disabled button is one attribute away from being pressable. */}
      {STEPS.slice(1).map((step) => (
            <div className="run-step run-step-free" key={step.key}>
              <div className="run-step-head">
                <span className="run-step-title">{step.title}</span>
                <span className="run-step-cost">{step.cost}</span>
              </div>
              <p className="run-step-note">{step.note}</p>

              {/* THE WAY TO EMIT, AND IT DRAWS IN EVERY STATE — including with no runs on
                  disk at all (D54). The button it replaces was conditional on a run being
                  open, so a first-time operator could see that Emit EXISTS (this head, this
                  note) and nothing on the screen said where it is. That is strictly stronger
                  than what it replaces rather than a loss.

                  A TEXT LINK RATHER THAN A CONTROL, which is `.run-figure-link`'s own
                  argument: underline is the web's convention for "this goes somewhere", it
                  needs no colour of its own, and the accent stays reserved. */}
              {step.key !== 'emit' ? null : (
                <p className="run-step-note">
                  <a
                    className="run-figure-link"
                    href={
                      openRun === null
                        ? '#/pricing'
                        : `#/pricing?run=${encodeURIComponent(openRun)}`
                    }
                  >
                    {openRun === null
                      ? 'Price and emit a run →'
                      : 'Price and emit this run →'}
                  </a>
                </p>
              )}

              {step.key === 'join' && detail !== null && (
                <>
                  <label className="run-toggle">
                    <input
                      type="checkbox"
                      checked={bypass}
                      onChange={(event) => setBypass(event.target.checked)}
                    />
                    {/* The plain-English form of D3's amendment, and it is the sentence the
                        owner asked for when they said the question had not been put in plain
                        English. The rule underneath it is one line: where a finish claim
                        exists, the photo may not contradict it. */}
                    Trust my finish claim over the photo
                  </label>
                  <p className="run-step-note run-step-fine">
                    Box 2 measured this: 230 of 544 cards had the photo disagreeing with a
                    claim that was right every time. Cards with no claim are unaffected —
                    there is nothing to resolve them by.
                  </p>
                  <div className="run-actions">
                    <button
                      type="button"
                      className="run-button"
                      disabled={busy !== null}
                      onClick={() => void doStep('join', { dryRun: true, bypass })}
                    >
                      {busy === 'join' ? 'Working…' : 'Preview'}
                    </button>
                    <button
                      type="button"
                      className="run-button"
                      disabled={busy !== null}
                      onClick={() => void doStep('join', { bypass })}
                    >
                      Join again
                    </button>
                    <label className="run-upload">
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        multiple
                        ref={exportPick}
                        onChange={() => void pickExports()}
                      />
                      <span>Join with an export…</span>
                    </label>
                  </div>
                  <p className="run-step-note run-step-fine">
                    Preview writes nothing at all — it walks the ladder twice, with the trust
                    switch and without, and tells you what each would queue. One export file
                    per game; leave the picker alone to re-use the last one.
                  </p>
                </>
              )}

              {step.key === 'emit' && detail !== null && (
                <>
                  <div className="run-actions">
                    <button
                      type="button"
                      className="run-button"
                      disabled={busy !== null}
                      onClick={() => void openDecisions()}
                    >
                      The rule and basis…
                    </button>
                  </div>
                  <p className="run-step-note run-step-fine">
                    The advanced door, not the pricing door: a rule outside the three presets
                    — <code>undercut:7</code> — is typed here. Prices, holds and the
                    sub-threshold answer are on Pricing.
                  </p>
                  {decisions === null ? null : (
                    <div className="run-decisions">
                      <label className="run-field run-field-wide">
                        decisions.json
                        <textarea
                          className="run-textarea"
                          rows={16}
                          spellCheck={false}
                          value={decisions}
                          onChange={(event) => setDecisions(event.target.value)}
                        />
                      </label>
                      {decisionsBad === null ? null : (
                        <p className="run-blocked">{decisionsBad}</p>
                      )}
                      <div className="run-actions">
                        <button
                          type="button"
                          className="run-button"
                          disabled={busy !== null}
                          onClick={() => void saveDecisions()}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="run-plain"
                          onClick={() => {
                            setDecisions(null)
                            setDecisionsBad(null)
                          }}
                        >
                          Close
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}

              {step.key === 'reconcile' && detail !== null && (
                <div className="run-actions">
                  <label className="run-upload">
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      ref={stagedPick}
                      onChange={() => void pickStaged()}
                    />
                    <span>
                      {busy === 'staged' ? 'Comparing…' : 'Compare with Export From Staged…'}
                    </span>
                  </label>
                </div>
              )}
          {/* THE ANSWER INSIDE THE STEP THAT PRODUCED IT. It rendered after all three boxes,
              so pressing Preview under Join put the reply ~300px further down the column than
              the button that asked for it — and `_run_sync` does not append to `console.log`,
              only the detached identify child does, which makes this the ONLY place a join,
              emit or reconcile answer ever appears on this screen.

              MATCHED ON THE STEP THE CLICK REQUESTED, never on the server's echo. `doStep` now
              records its own `step` argument, so the value is by construction one of these
              three keys and no orphan fallback can fire. The echo is not the local truth:
              `app/tests/run-panel.spec.ts` mocks all three routes and returns `step: 'join'`
              for every one, which was harmless only while this rendered unconditionally. */}
          {stepOut === null || stepOut.step !== step.key ? null : (
            <div className={`run-result${stepOut.ok ? '' : ' run-result-refused'}`}>
              <p className="run-result-head">
                {stepOut.step} {stepOut.ok ? 'finished' : 'refused'}
              </p>
              <Console text={stepOut.console} label={`What ${stepOut.step} printed`} />
            </div>
          )}
        </div>
      ))}

      {/* EVERYTHING EXCEPT THE IMPORT CSVs (D54). `report.txt`, `pricing.json` and
          `reconcile.txt` are written by the commands pressed on THIS screen, so their
          receipts belong beside those buttons. The two import files went to `#/pricing` with
          the press that writes them — docs/GATES.md's recorded gap was that the press and
          the receipt were in different places, and splitting them again here would
          reproduce it with a nicer font. */}
      {detail === null ? null : (
        <RunFiles run={detail.run} files={detail.files} only="run" />
      )}
    </div>
  )
}
