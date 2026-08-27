import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  describeFailure,
  getRun,
  getRuns,
  preflightRun,
  putDecisions,
  runFileUrl,
  runStep,
  startRun,
  type Failure,
} from './server'
import type { CsvUpload, RunDetail, RunPreflight, RunSummary } from './types'
import './RunPanel.css'

/* THE PIPELINE, ON THE SCREEN THE OPERATOR IS ALREADY STANDING ON.
 *
 * The owner's report, and it was correct: "i also don't see any of the UI you stated you'd be
 * building that let me do all of this within the app???" The four commands had been designed,
 * interviewed and drawn as a mockup, and none of it was built — which is precisely the failure
 * `CLAUDE.md`'s route-is-not-a-feature rule was written for, committed in the same session that
 * wrote the rule.
 *
 * WHY IT SITS ON `#/inventory` RATHER THAN ON A ROUTE OF ITS OWN. D31 collapsed three screens
 * into this one on the finding that they were separate instances of one thing, and a run is not
 * a different thing again: a run is something you do TO a box, or to the cards you have just
 * ticked inside one. The scope this panel offers is the scope the walk is already showing, which
 * is only true because they are the same screen — a separate route would have to re-implement
 * the box strip, the search and the mass-select, and would then be free to disagree with them
 * about what "the selection" is.
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
function runningFor(row: { created_at?: string | null }): string {
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
 *  FALLS BACK TO THE CAPTURE DIRECTORY, because `scope` is written by the route that starts a
 *  run from this screen and every run made before it — including both of the ones this project
 *  has actually done — carries none. Reading the box out of the path is a derivation and not a
 *  claim, so it is drawn without the `whole box` / `N cards` distinction that only a real scope
 *  block can support: an old run genuinely does not record whether it covered the whole box.
 *  The alternative was an em dash, which says nothing about a run whose directory names its
 *  box in plain sight. */
/** Which box a run was over, by the same derivation the row prints.
 *
 *  SHARED WITH `scopeOf` ON PURPOSE, so the string a row draws and the group it is sorted into
 *  can never disagree. It matters immediately rather than in principle: `scope` is written only
 *  by the route that starts a run from this screen, and NEITHER run this project has actually
 *  done carries one — so grouping on `row.scope.box` alone would file both of them under "other
 *  boxes", including the one the panel's own head is naming. */
function boxOf(row: RunSummary): number | null {
  if (row.scope != null) return row.scope.box
  const found = /box(\d+)/.exec(row.capture_dir ?? '')
  return found === null ? null : Number(found[1])
}

function scopeOf(row: RunSummary): string {
  const box = boxOf(row)
  if (box === null) return '—'
  /* The whole-box / N-cards distinction only a real scope block can support — a box parsed out
     of a capture directory is a derivation, not a claim about what was submitted. */
  if (row.scope != null) {
    return row.scope.whole_box ? `box ${box}` : `box ${box} · ${row.scope.cards ?? '?'} cards`
  }
  return `box ${box}`
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

type RunPanelProps = {
  /** The box the walk is standing in, and the cards ticked inside it — `BoxBrowse`'s own
   *  `onScope`. A run is scoped to what is already on screen, which is the whole reason this
   *  panel lives on this route. */
  scope: { box: number | null; indices: readonly number[] }
}

export function RunPanel({ scope }: RunPanelProps) {
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

  /* The default is `READINGS[0]` — the measured pair — restated here rather than read off the
   * table, because `useState` wants a value and a lazy initialiser reading an index would be a
   * second place the default lives. The CLI's own defaults are the OTHER corner (crop off,
   * 1568), which is deliberate and is what `Whole frame` selects: this screen states a default
   * rather than changing what an unflagged terminal run means. */
  const [crop, setCrop] = useState(true)
  const [maxEdge, setMaxEdge] = useState(1200)
  /* Whether the raw controls are revealed. An ACT rather than a derivation: with the pair set
   * by the presets, the only way to reach an arbitrary number is to ask for one, and a `custom`
   * that switched itself on whenever the pair stopped matching a row would leave the operator
   * unable to see which of the two states they were in. */
  const [custom, setCustom] = useState(false)
  const [bypass, setBypass] = useState(false)

  const [busy, setBusy] = useState<string | null>(null)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [stepOut, setStepOut] = useState<{ step: string; ok: boolean; console: string } | null>(
    null,
  )

  const exportPick = useRef<HTMLInputElement | null>(null)
  const stagedPick = useRef<HTMLInputElement | null>(null)

  /* THE SCOPE AS ONE STRING, so an effect can compare it. Two numbers and an array cannot be
   * compared by identity across renders — the array is rebuilt every time `BoxBrowse` reports
   * — and a deep compare written by hand here would be a second answer to a question a key
   * already answers. */
  const scopeKey = useMemo(
    () =>
      `${scope.box ?? 'none'}:${[...scope.indices].sort((a, b) => a - b).join(',')}` +
      `:${crop ? 'crop' : 'whole'}:${maxEdge}`,
    [scope, crop, maxEdge],
  )

  const scoped = scope.box !== null
  const selection = scope.indices.length

  /* WHICH ROW THE PAIR IS, and the sentence that goes under it. Derived rather than stored, so
   * the chip that reads as chosen and the values actually sent cannot come apart — the failure
   * a second piece of state here would eventually produce. `custom` wins the tie: with the raw
   * controls revealed, the operator is holding the knob whatever the numbers happen to say. */
  const reading = READINGS.find((row) => row.crop === crop && row.maxEdge === maxEdge) ?? null
  const readingSays = custom || reading === null ? CUSTOM_SAYS : reading.says

  useEffect(() => {
    /* THE QUOTE IS VOID THE MOMENT THE SCOPE MOVES. Not merely stale — void: it is the first
     * step of a two-step confirm, and a confirm whose first step described a different set of
     * cards is not a confirm at all. Ticking one more card retires the estimate.
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

  const scopeArgs = useMemo(
    () => ({
      box: scope.box ?? 0,
      indices: selection > 0 ? [...scope.indices] : undefined,
      crop,
      maxEdge,
    }),
    [scope, selection, crop, maxEdge],
  )

  const doQuote = () =>
    guard('quote', async () => {
      const answer = await preflightRun(scopeArgs)
      setQuote(answer)
      setTicketScope(scopeKey)
    })

  const doStart = () =>
    guard('start', async () => {
      const started = await startRun(scopeArgs)
      /* The quote is spent. Clearing it forces a fresh preflight before a second run can be
       * started, which is what stops a confirm being pressed twice on one estimate. */
      setQuote(null)
      setTicketScope('')
      setOpenRun(started.run)
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

  const scopeLine = !scoped
    ? 'Pick a box in the walk to run it.'
    : selection > 0
      ? `Box ${scope.box} · ${selection} ticked card${selection === 1 ? '' : 's'}`
      : `Box ${scope.box} · the whole box`

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
  const running: RunSummary[] = []
  const mine: RunSummary[] = []
  const other: RunSummary[] = []
  for (const row of runs) {
    if (row.live) running.push(row)
    else if (scope.box !== null && boxOf(row) === scope.box) mine.push(row)
    else other.push(row)
  }

  /* No box in the walk means no box to group against, so the list is drawn exactly as the
     server sent it — a distinction with nothing to distinguish is chrome. */
  const grouped = scope.box === null
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

  const files = (detail?.files ?? []).filter((file) => file.name !== 'manifest.json')
  const fileRows = files.map((file) => (
    <a
      key={file.name}
      className={`run-file${file.is_import ? ' run-file-import' : ''}`}
      href={runFileUrl(detail?.run ?? '', file.name)}
      download={file.name}
    >
      <span className="run-file-name">{file.name}</span>
      <span className="run-file-size">{(file.bytes / 1000).toFixed(1)} kB</span>
    </a>
  ))

  /* WHAT IS BEHIND THE FOLD, NAMED ON THE OUTSIDE OF IT. `BoxOps` on this same screen states
   * the rule in its own comment — "a disclosure that under-sold its contents is exactly how
   * three routes came to have no reachable control" — and the pipeline is the largest instance
   * of that failure this repo has had, so the hint names all four commands and the live count. */
  const live = runs.filter((row) => row.live).length
  const hint = [
    'identify · join · emit · reconcile',
    live > 0 ? `${live} running` : runs.length > 0 ? `${runs.length} run${runs.length === 1 ? '' : 's'}` : null,
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
      {/* TITLE, SCOPE, THEN THE HINT — reordered in the DOM on 2026-08-25 rather than with
          `order`, so the tab ring and a screen reader walk what the eye walks. In the 400px column
          this panel now lives in, the hint needs ~323px of Martian Mono and can share a line with
          nothing; ordered between the other two it pushed BOTH onto lines of their own and the
          head became three. Last, it takes one full-width line and reads on one line, and the
          title keeps its line with the scope — which is docs/DESIGN.md's rule as written, "the
          page title shares a line with the screen's controls and counts". Where a panel is wide
          enough for all three, nothing wraps and this is one line again. */}
      <p className="run-head">
        <span className="run-title">Runs</span>
        <span className="run-scope">{scopeLine}</span>
        <span className="run-hint">{hint}</span>
      </p>

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

        {/* THE READING, AS A PAIR RATHER THAN AS TWO CONTROLS — see `READINGS` above for the
            measurement that decides it, and for why a checkbox beside a free number was an
            invitation to spend more by asking for less. */}
        <div
          className="run-controls run-readings"
          role="group"
          aria-label="How the cards are read"
        >
          {READINGS.map((row) => (
            <button
              key={row.key}
              type="button"
              className="run-button run-reading"
              aria-pressed={!custom && reading?.key === row.key}
              onClick={() => {
                setCustom(false)
                setCrop(row.crop)
                setMaxEdge(row.maxEdge)
              }}
            >
              {row.label}
              <span className="run-reading-edge">{row.maxEdge}</span>
            </button>
          ))}
          <button
            type="button"
            className="run-button run-reading"
            aria-pressed={custom}
            onClick={() => setCustom(true)}
          >
            Custom
          </button>
        </div>

        {custom && (
          /* THE RAW CONTROLS, UNCHANGED AND DEMOTED RATHER THAN DELETED. `Sharpest · 1400` and
             everything else on D32's frontier is reachable here, and so is every pairing the
             three rows above refuse to offer — including the wrong one, which is why the
             sentence beneath this block is the one that names it. */
          <div className="run-controls">
            <label className="run-toggle">
              <input
                type="checkbox"
                checked={crop}
                onChange={(event) => setCrop(event.target.checked)}
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
                value={maxEdge}
                onChange={(event) => setMaxEdge(Number(event.target.value))}
              />
              px
            </label>
          </div>
        )}

        {/* WHAT THE READING MEANS, BEFORE Check cost IS PRESSED. The command prints its own
            crop line into the preflight stdout below, and that line is the receipt — but a
            receipt arrives after the decision, and this is the decision. */}
        <p className="run-step-note run-step-fine">{readingSays}</p>

        <div className="run-actions">
          <button
            type="button"
            className="run-button"
            disabled={!scoped || busy !== null}
            onClick={() => void doQuote()}
          >
            {busy === 'quote' ? 'Checking…' : 'Check cost'}
          </button>
        </div>

        {quote === null ? null : (
          <div className="run-quote">
            {/* STEP ONE OF THE TWO-STEP CONFIRM, and the confirm below cannot be reached
                without it. The numbers are the command's own — lifted out of its preflight
                stdout rather than recomputed anywhere — so what is on this screen and what is
                in the run's log are the same string. */}
            <dl className="run-figures">
              <div>
                <dt>Photographs</dt>
                <dd>{count(quote.photographs)}</dd>
              </div>
              <div>
                <dt>Already answered</dt>
                <dd>{count(quote.cache_hits)}</dd>
              </div>
              <div>
                <dt>To send</dt>
                <dd>{count(quote.to_send)}</dd>
              </div>
              <div className="run-figure-money">
                <dt>Estimated cost</dt>
                <dd>{money(quote.estimate_usd)}</dd>
              </div>
            </dl>

            {(quote.cache_hits ?? 0) > 0 && (
              /* WHAT `Already answered` COSTS YOU, said where that figure is drawn. D32 records
                 it as a known gap kept deliberately: neither the crop nor the max edge is part
                 of the cache identity, so a box re-read at a different reading serves the
                 answers it was first read with and reports them as hits. That is safe and it is
                 not obvious, and the two controls it silently ignores are directly above.
                 Stated as what it means to the person about to press the button rather than as
                 a fact about a hash — the panel has no business naming `prompt_fingerprint`. */
              <p className="run-step-note run-step-fine">
                Cards already answered keep the answer they were first read with. The reading
                above only reaches the cards being sent.
              </p>
            )}

            <Console text={quote.console} label="What the preflight printed" />

            {quote.busy_run !== null ? (
              <p className="run-blocked">
                {quote.busy_run} is already identifying these cards. Two runs over one box is
                two invoices for one answer — open it below and watch it instead.
              </p>
            ) : quote.to_send === 0 ? (
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
                  : `Spend ${money(quote.estimate_usd)} and identify ${count(quote.to_send)} cards`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ the run list */}
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
              <div>
                <dt>Review</dt>
                <dd>{count(detail.counts.queued_main)}</dd>
              </div>
              <div>
                <dt>Parked</dt>
                <dd>{count(detail.counts.queued_parked)}</dd>
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
                      onClick={() => void doStep('emit')}
                    >
                      {busy === 'emit' ? 'Writing…' : 'Write the import files'}
                    </button>
                    <button
                      type="button"
                      className="run-button"
                      disabled={busy !== null}
                      onClick={() => void openDecisions()}
                    >
                      Pricing answers
                    </button>
                  </div>
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

      {fileRows.length === 0 ? null : (
        <div className="run-files">
          {/* THE WHOLE REASON THE DOWNLOAD EXISTS. docs/GATES.md, on what Gate B did not
              close: emit's import files existed only as filenames in terminal output the
              owner never saw, because someone else was driving the commands. */}
          <p className="run-files-head">Files</p>
          {fileRows}
        </div>
      )}
    </div>
  )
}
