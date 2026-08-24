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

/** What a run was over, in the fewest words that are true.
 *
 *  FALLS BACK TO THE CAPTURE DIRECTORY, because `scope` is written by the route that starts a
 *  run from this screen and every run made before it — including both of the ones this project
 *  has actually done — carries none. Reading the box out of the path is a derivation and not a
 *  claim, so it is drawn without the `whole box` / `N cards` distinction that only a real scope
 *  block can support: an old run genuinely does not record whether it covered the whole box.
 *  The alternative was an em dash, which says nothing about a run whose directory names its
 *  box in plain sight. */
function scopeOf(row: RunSummary): string {
  if (row.scope != null) {
    return row.scope.whole_box
      ? `box ${row.scope.box}`
      : `box ${row.scope.box} · ${row.scope.cards ?? '?'} cards`
  }
  const found = /box(\d+)/.exec(row.capture_dir ?? '')
  return found === null ? '—' : `box ${found[1]}`
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

  const [crop, setCrop] = useState(true)
  const [maxEdge, setMaxEdge] = useState(1200)
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
    () => `${scope.box ?? 'none'}:${[...scope.indices].sort((a, b) => a - b).join(',')}`,
    [scope],
  )

  const scoped = scope.box !== null
  const selection = scope.indices.length

  useEffect(() => {
    /* THE QUOTE IS VOID THE MOMENT THE SCOPE MOVES. Not merely stale — void: it is the first
     * step of a two-step confirm, and a confirm whose first step described a different set of
     * cards is not a confirm at all. Ticking one more card retires the estimate. */
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

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

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
      setStepOut({ step: result.step, ok: result.ok, console: result.console })
      setDetail(await getRun(openRun))
      await loadRuns()
    })

  const pickExports = () =>
    guard('exports', async () => {
      const chosen = Array.from(exportPick.current?.files ?? [])
      if (chosen.length === 0 || openRun === null) return
      const uploads = await Promise.all(chosen.map(readUpload))
      const result = await runStep(openRun, 'join', { exports: uploads, bypass })
      setStepOut({ step: result.step, ok: result.ok, console: result.console })
      setDetail(await getRun(openRun))
      await loadRuns()
      if (exportPick.current !== null) exportPick.current.value = ''
    })

  const pickStaged = () =>
    guard('staged', async () => {
      const chosen = stagedPick.current?.files?.[0]
      if (chosen === undefined || openRun === null) return
      const result = await runStep(openRun, 'reconcile', { stagedExport: await readUpload(chosen) })
      setStepOut({ step: result.step, ok: result.ok, console: result.console })
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

  const runRows = runs.map((row) => (
    <button
      key={row.run}
      type="button"
      className={`run-row${row.run === openRun ? ' run-row-open' : ''}`}
      aria-pressed={row.run === openRun}
      onClick={() => setOpenRun(row.run === openRun ? null : row.run)}
    >
      <span className="run-row-name">{row.run}</span>
      <span className={`run-phase run-phase-${row.phase}`}>
        {row.live ? 'running' : row.phase}
      </span>
      <span className="run-row-scope">{scopeOf(row)}</span>
    </button>
  ))

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
    /* FOLDED BY DEFAULT, and the argument is `BoxOps`' measured one applied to this panel: it
     * is ~250px tall, it sits above the card detail, and it is reached once a box — while the
     * question the operator arrives at this screen with is "where is this card", which the
     * detail beneath it answers. Drawing it open on every visit would spend a quarter of the
     * viewport, on every arrival, on a control used once per session.
     *
     * `<details>` and not a hand-rolled toggle, for the reason that file also gives: the
     * platform ships this, including the keyboard behaviour. A live run is what opens it on
     * its own — see `defaultOpen` below, which is deliberately not a persisted setting. */
    <details className="run-panel" open={live > 0}>
      <summary className="run-head">
        <span className="run-marker" aria-hidden="true" />
        <span className="run-title">Runs</span>
        <span className="run-hint">{hint}</span>
        <span className="run-scope">{scopeLine}</span>
      </summary>

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

        <div className="run-controls">
          <label className="run-toggle">
            <input
              type="checkbox"
              checked={crop}
              onChange={(event) => setCrop(event.target.checked)}
            />
            {/* D32: the crop is local, free and per-run, and it is OFF by default in the CLI
                because Gate B's only end-to-end run was full-frame. It is on by default here
                because every run since has used it and the box-2 measurement is what settled
                the max-edge beside it — a default this screen can state, rather than a change
                to the flag's own default, which would rewrite what an unflagged run means. */}
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
          </label>
        </div>

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
        ) : (
          runRows
        )}
      </div>

      {/* ------------------------------------------- the open run, and the three free steps */}
      {detail === null ? null : (
        <div className="run-open">
          <div className="run-open-head">
            <span className="run-open-name">{detail.run}</span>
            <span className={`run-phase run-phase-${detail.phase}`}>
              {detail.live ? 'running' : detail.phase}
            </span>
          </div>

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

          {STEPS.slice(1).map((step) => (
            <div className="run-step run-step-free" key={step.key}>
              <div className="run-step-head">
                <span className="run-step-title">{step.title}</span>
                <span className="run-step-cost">{step.cost}</span>
              </div>
              <p className="run-step-note">{step.note}</p>

              {step.key === 'join' && (
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

              {step.key === 'emit' && (
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

              {step.key === 'reconcile' && (
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
            </div>
          ))}

          {stepOut === null ? null : (
            <div className={`run-result${stepOut.ok ? '' : ' run-result-refused'}`}>
              <p className="run-result-head">
                {stepOut.step} {stepOut.ok ? 'finished' : 'refused'}
              </p>
              <Console text={stepOut.console} label={`What ${stepOut.step} printed`} />
            </div>
          )}

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
      )}
    </details>
  )
}
