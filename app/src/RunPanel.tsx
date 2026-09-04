import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  describeFailure,
  fetchExport,
  getExportScope,
  getRun,
  getRuns,
  getTcgSets,
  runStep,
  type Failure,
} from './server'
import type { ExportAsked, ExportFetched, ExportScope, RunDetail, RunSummary } from './types'
import { readUpload } from './csvUpload'
import { Button, EmptyState, Icon, Notice, Pill, Segmented, Stat } from './kit'
import { toast } from './kit/toast'
import { RunFiles } from './RunFiles'
import { FileButton } from './RunsDrop'
import { LogWell } from './RunsLog'
import { COMMANDS, StageBar, StagePill, runningFor, stageOf, whenLabel, type Command } from './RunsStage'
import type { CartBox } from './RunsComposer'
import { boxOf, runBoxLabel } from './runScope'
import './RunPanel.css'

export { runningFor }
export type { CartBox }

/* THE RUNS, AS MASTER AND DETAIL. The list on the left is every run directory on disk,
 * re-read while this panel is on screen; the detail on the right is the run the three free
 * commands act on — join, emit (on Pricing) and reconcile — drawn as a stepper.
 *
 * IT HOLDS NOTHING ABOUT A RUN BETWEEN RENDERS EXCEPT WHICH ONE IS OPEN. Every figure is read
 * from `GET /pipeline/runs/<name>`, so a run started in a terminal appears here and a run
 * started here survives this tab being closed. The paid step lives in `RunsComposer.tsx`. */

const POLL_MS = 4000
const IDLE_POLL_MS = 20000

/* THE EXPORT DELTA GUARD IS RETIRED, AND WITH IT BOTH "Fetch anyway" BUTTONS. It compared a
 * fetch against this run's last export and refused a file that was smaller or had nothing to
 * compare against — which refused the very improvement it existed to allow, and left the
 * operator pressing past it to get on with the work. The server still holds the two refusals,
 * so the client answers them once, up front, and never asks: a fetch produces a RECEIPT now,
 * not a question. */
const ACCEPT_ALWAYS = { acceptUnverified: true, acceptNarrower: true } as const

/* Why the fetch is asking for what it is asking for (D76), in the operator's words. */
const SCOPE_REASON: Record<string, string> = {
  game_policy: "this game's whole catalogue comes down in one file, so a set filter would buy nothing",
  operator_asked: 'you asked for the whole category',
  no_hints: 'no card in this run carries a set hint',
  partial_hints: 'some cards carry no set hint, and a filter built from the rest would drop them',
  unresolved_hints: 'a hint here matches no TCGplayer set, and guessing which one is not safe',
  no_hints_resolved: 'no hint here resolved to a TCGplayer set',
}

const SCOPE_CHOICES = [
  { key: 'rule', label: 'What this run implies' },
  { key: 'category', label: 'Every set in the category' },
  { key: 'sets', label: 'Only the sets I tick' },
] as const
type ScopeChoice = (typeof SCOPE_CHOICES)[number]['key']

const REVIEW_BELOW = [
  { key: 'low', label: 'Low (default)' },
  { key: 'medium', label: 'Medium — queue more' },
  { key: 'none', label: 'None — nothing queued on confidence' },
] as const

/* Who started a run, as words rather than the manifest's own token. */
const STARTER: Record<string, string> = { app: 'this app', cli: 'a terminal', terminal: 'a terminal' }
function capitalise(word: string): string {
  return word.length === 0 ? word : word[0]!.toUpperCase() + word.slice(1)
}

const TITLES: Record<Command, string> = {
  identify: 'Identify',
  join: 'Join',
  emit: 'Emit',
  reconcile: 'Reconcile',
}

function count(value: number | null | undefined): string {
  return typeof value === 'number' ? String(value) : '—'
}

/** The scope, in the words the receipt says it in: the third fact on its headline. */
function scopeWords(asked: ExportAsked): string {
  if (asked.scope === 'category') return 'whole category'
  const names = asked.sets
  if (names.length === 0) return 'no set named'
  if (names.length <= 2) return names.join(' and ')
  const rest = names.length - 2
  return `${names.slice(0, 2).join(', ')} and ${rest} more set${rest === 1 ? '' : 's'}`
}

/** THE EXPORT BEFORE THIS ONE — the receipt's second line, and the whole of its reassurance:
 *  it says the figure above is a normal size for this run.
 *
 *  NOT ON THE WIRE ON THIS BRANCH. The field this line reads once the server carries it is
 *  `ExportFetched.previous` — `{ rows: number; fetched_at: string }`, the export this run
 *  held before this fetch — and `whenLabel` already turns that timestamp into "two days ago".
 *  Until it lands, `verified` is the half that exists: it names the games this run DID have a
 *  previous export for, which is the same fact one figure short. */
type PreviousExport = { rows: number; fetched_at: string }
type PreviousPerGame = Record<string, { file?: string; rows: number; skus?: number }>

/* TWO SHAPES, BECAUSE THE WIRE CARRIES A DIFFERENT ONE ON EITHER SIDE OF THE MERGE, and
   reading the wrong one is not a wrong sentence, it is a crash that takes the Join step
   down after a fetch that SUCCEEDED. This branch expects `{rows, fetched_at}`; main's
   `ExportFetched.previous` is a per-game `Record<string, {file, rows, skus}>`. Both are
   read, neither is assumed, and an unrecognised shape falls through to the sentence that
   needs no figure at all. */
function previousLine(fetched: ExportFetched, display: (game: string) => string): string {
  const raw = (fetched as ExportFetched & { previous?: unknown }).previous
  if (raw != null && typeof raw === 'object') {
    const flat = raw as Partial<PreviousExport>
    if (typeof flat.rows === 'number') {
      const when = typeof flat.fetched_at === 'string' ? `, ${whenLabel(flat.fetched_at)}` : ''
      return `Last time: ${flat.rows.toLocaleString()} rows${when}`
    }
    const perGame = Object.entries(raw as PreviousPerGame).filter(
      ([, was]) => was != null && typeof was === 'object' && typeof was.rows === 'number',
    )
    if (perGame.length > 0) {
      return `Last time: ${perGame
        .map(([game, was]) => `${display(game)} ${was.rows.toLocaleString()} rows`)
        .join(' · ')}`
    }
  }
  if (fetched.verified.length > 0) return `Not the first export for ${fetched.verified.map(display).join(', ')} in this run.`
  return 'The first export this run has fetched.'
}

/** What a run was over, in the fewest words that are true. */
function scopeOf(row: RunSummary): string {
  const label = runBoxLabel(row)
  if (label === null) return '—'
  if (row.scope != null && !row.scope.whole_box) return `${label} · ${row.scope.cards ?? '?'} cards`
  return label
}

type BusyKey = 'join' | 'fetch' | 'exports' | 'staged'
type Trouble = { readonly key: BusyKey | 'poll' | 'detail'; readonly failure: Failure }

type StepState = 'done' | 'current' | 'live' | 'todo'

/** One step of the stepper: a head that folds, and a body drawn only when open. */
function StepCard({
  n,
  title,
  state,
  summary,
  cost,
  open,
  onToggle,
  children,
}: {
  readonly n: number
  readonly title: string
  readonly state: StepState
  readonly summary: string
  readonly cost: ReactNode
  readonly open: boolean
  readonly onToggle: () => void
  readonly children: ReactNode
}) {
  return (
    <section className={`runs-step runs-step-${state}`} data-open={open ? 'true' : undefined}>
      <button type="button" className="runs-step-head" aria-expanded={open} onClick={onToggle}>
        <span className="runs-step-mark" aria-hidden="true">
          {state === 'done' ? (
            <Icon name="check" size={14} strokeWidth={2.25} />
          ) : state === 'live' ? (
            <span className="bn-dot bn-dot-live" />
          ) : (
            n
          )}
        </span>
        <span className="runs-step-text">
          <span className="run-step-title">{title}</span>
          <span className="runs-step-summary">{summary}</span>
        </span>
        <span className="runs-step-cost">{cost}</span>
        <Icon name="chevronDown" size={16} className="runs-step-chev" />
      </button>
      {open ? <div className="runs-step-body">{children}</div> : null}
    </section>
  )
}

type RunPanelProps = {
  readonly cart: readonly CartBox[]
  readonly openRun: string | null
  readonly onOpenRun: (run: string | null) => void
  /** Bumped by the page's Reload; the list re-reads when it moves. */
  readonly reloadTick: number
  readonly onIdentify: () => void
  /** The page's own read failure (the box registry). Drawn here, once, in the list's column,
   *  so an unreachable server is said one time on the screen rather than by every column. */
  readonly pageFailure: Failure | null
}

export function RunPanel({ cart, openRun, onOpenRun, reloadTick, onIdentify, pageFailure }: RunPanelProps) {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])
  const [loaded, setLoaded] = useState(false)
  const [detail, setDetail] = useState<RunDetail | null>(null)

  const [reviewBelow, setReviewBelow] = useState<'none' | 'low' | 'medium'>('low')
  const [optionsOpen, setOptionsOpen] = useState(false)

  /* D76: the fetch's scope, as a lever. Read from the server, never recomputed. */
  const [scopeInfo, setScopeInfo] = useState<ExportScope | null>(null)
  const [scopeGame, setScopeGame] = useState<string | null>(null)
  const [scopeChoice, setScopeChoice] = useState<ScopeChoice>('rule')
  const [scopeTicked, setScopeTicked] = useState<number[]>([])
  const [setList, setSetList] = useState<{ name: string; id: string }[]>([])

  const [fetched, setFetched] = useState<ExportFetched | null>(null)
  const [fetchRefusal, setFetchRefusal] = useState<Failure | null>(null)
  const [stepOut, setStepOut] = useState<{ step: Command; ok: boolean; console: string } | null>(null)
  const stepOutRef = useRef(stepOut)
  stepOutRef.current = stepOut

  const [busy, setBusy] = useState<BusyKey | null>(null)
  const [trouble, setTrouble] = useState<Trouble | null>(null)

  const [openStep, setOpenStep] = useState<Command | null>(null)

  /* ---------------------------------------------------------------------- the list */
  const loadRuns = useCallback(async () => {
    try {
      setRuns(await getRuns())
      setLoaded(true)
    } catch (err) {
      setTrouble({ key: 'poll', failure: describeFailure(err) })
      setLoaded(true)
    }
  }, [])

  /* Re-read while on screen: fast while something is live, slow otherwise. Chained timeouts
     so a slow answer never stacks; the first failure is reported and later ones swallowed. */
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
        setLoaded(true)
        anyLive = rows.some((row) => row.live)
      } catch (err) {
        if (!cancelled && !announced) setTrouble({ key: 'poll', failure: describeFailure(err) })
        announced = true
        setLoaded(true)
      }
      if (!cancelled) timer = window.setTimeout(() => void tick(), anyLive ? POLL_MS : IDLE_POLL_MS)
    }
    void tick()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  const firstReload = useRef(true)
  useEffect(() => {
    if (firstReload.current) {
      firstReload.current = false
      return
    }
    void loadRuns()
  }, [reloadTick, loadRuns])

  /* Per-run state belongs to the run it was produced against. */
  useEffect(() => {
    setStepOut(null)
    setFetched(null)
    setFetchRefusal(null)
    setOptionsOpen(false)
    setTrouble((held) => (held !== null && held.key === 'poll' ? held : null))
  }, [openRun])

  /* The detail poll runs only while the open run is live. */
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
        if (!cancelled) setTrouble({ key: 'detail', failure: describeFailure(err) })
      }
    }
    void tick()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [openRun, loadRuns])

  /* The open step follows the run: a new run opens on the step it is waiting for, and a run
     whose phase moves under a poll follows it — unless a step's own answer is on screen. */
  const lastRun = useRef<string | null>(null)
  useEffect(() => {
    if (detail === null) return
    const changed = lastRun.current !== detail.run
    lastRun.current = detail.run
    if (!changed && stepOutRef.current !== null) return
    setOpenStep(COMMANDS[Math.min(stageOf(detail).step, 3)] ?? 'identify')
  }, [detail])

  /* ---------------------------------------------------------- D76: the export's scope */
  useEffect(() => {
    if (openRun === null) {
      setScopeInfo(null)
      return
    }
    let live = true
    void (async () => {
      try {
        const answer = await getExportScope(openRun, scopeGame === null ? {} : { game: scopeGame })
        if (!live) return
        setScopeInfo(answer)
        if (scopeGame === null && answer.asked !== null) setScopeGame(answer.asked.game)
      } catch {
        if (live) setScopeInfo(null)
      }
    })()
    return () => {
      live = false
    }
  }, [openRun, scopeGame])

  useEffect(() => {
    const game = scopeGame ?? scopeInfo?.asked?.game ?? scopeInfo?.games[0]?.game ?? null
    if (game === null || scopeChoice !== 'sets') return
    let live = true
    void (async () => {
      try {
        const answer = await getTcgSets(game)
        if (live) setSetList(answer.sets)
      } catch {
        if (live) setSetList([])
      }
    })()
    return () => {
      live = false
    }
  }, [scopeGame, scopeChoice, scopeInfo])

  const scopeOptions = useMemo(() => {
    const game = scopeGame ?? undefined
    if (scopeChoice === 'category') return { game, scope: 'category' as const }
    if (scopeChoice === 'sets') return { game, setIds: scopeTicked }
    return { game }
  }, [scopeGame, scopeChoice, scopeTicked])

  /* What the press will ask for and which voice chose it (D76), composed from the same three
     values `scopeOptions` sends so the sentence and the request cannot drift. */
  const scopeSentence = useMemo((): { what: string; why: string | null } | null => {
    const chosen = scopeInfo?.games.find((g) => g.game === (scopeGame ?? scopeInfo?.asked?.game)) ?? null
    const every = `every set in ${chosen?.display ?? 'this category'}`
    if (scopeChoice === 'category') return { what: every, why: 'you asked for the whole category' }
    if (scopeChoice === 'sets') {
      if (scopeTicked.length === 0) return { what: 'nothing yet', why: 'tick at least one set' }
      const names = setList.filter((row) => scopeTicked.includes(Number(row.id))).map((row) => row.name)
      return { what: names.join(', '), why: 'your tick, which outranks both the rule and the hints' }
    }
    const asked = scopeInfo?.asked ?? null
    if (asked === null) return null
    const what = asked.scope === 'category' ? every : asked.sets.join(', ')
    const why = asked.reason === null ? null : (SCOPE_REASON[asked.reason] ?? null)
    return { what, why }
  }, [scopeInfo, scopeGame, scopeChoice, scopeTicked, setList])

  /** A game's display name for the eye; the id only when the scope has not answered yet. */
  const gameDisplay = (game: string): string => scopeInfo?.games.find((row) => row.game === game)?.display ?? game

  /* ------------------------------------------------------------------ the commands */
  const guard = useCallback(async (key: BusyKey, work: () => Promise<void>) => {
    setBusy(key)
    setTrouble(null)
    try {
      await work()
    } catch (err) {
      setTrouble({ key, failure: describeFailure(err) })
    } finally {
      setBusy(null)
    }
  }, [])

  const settle = useCallback(
    async (step: Command, result: { ok: boolean; console: string }) => {
      if (openRun === null) return
      setStepOut({ step, ok: result.ok, console: result.console })
      setOpenStep(step)
      setDetail(await getRun(openRun))
      await loadRuns()
      toast({
        kind: result.ok ? 'ok' : 'refusal',
        title: `${TITLES[step]} ${result.ok ? 'finished' : 'refused'}`,
        body: result.ok ? 'The answer is in the step below.' : 'The command said why — read it in the step.',
        ttlMs: result.ok ? 4000 : 8000,
      })
    },
    [openRun, loadRuns],
  )

  const doStep = (step: 'join' | 'emit' | 'reconcile', extra: Parameters<typeof runStep>[2] = {}) =>
    guard(step === 'join' ? 'join' : 'staged', async () => {
      if (openRun === null) return
      const result = await runStep(openRun, step, extra)
      await settle(step, result)
    })

  /* One press, two calls: fetch the export, then join against it — only if it landed. */
  const doFetchExport = () =>
    guard('fetch', async () => {
      if (openRun === null) return
      setFetchRefusal(null)
      let answer: ExportFetched
      try {
        answer = await fetchExport(openRun, { ...scopeOptions, ...ACCEPT_ALWAYS })
      } catch (err) {
        setFetched(null)
        setFetchRefusal(describeFailure(err))
        return
      }
      setFetched(answer)
      const result = await runStep(openRun, 'join', { fetched: [answer.file], reviewBelowConfidence: reviewBelow })
      await settle('join', result)
    })

  const joinWithExports = (files: File[]) =>
    guard('exports', async () => {
      if (files.length === 0 || openRun === null) return
      const uploads = await Promise.all(files.map(readUpload))
      const result = await runStep(openRun, 'join', { exports: uploads, reviewBelowConfidence: reviewBelow })
      await settle('join', result)
    })

  const compareStaged = (files: File[]) =>
    guard('staged', async () => {
      const chosen = files[0]
      if (chosen === undefined || openRun === null) return
      const result = await runStep(openRun, 'reconcile', { stagedExport: await readUpload(chosen) })
      await settle('reconcile', result)
    })

  /* --------------------------------------------------------------------------- render */

  /* Partitioned, never filtered: running first, then runs over the boxes in the cart, then the
     rest — and only when there is a cart to group against. */
  const inCart = new Set(cart.map((row) => row.box))
  const running: RunSummary[] = []
  const mine: RunSummary[] = []
  const other: RunSummary[] = []
  for (const row of runs) {
    if (row.live) running.push(row)
    else if (inCart.has(boxOf(row) ?? -1)) mine.push(row)
    else other.push(row)
  }
  const grouped = cart.length > 0
  const groups: { readonly key: string; readonly caption: string | null; readonly rows: RunSummary[] }[] = grouped
    ? [
        { key: 'running', caption: 'Running', rows: running },
        { key: 'mine', caption: 'Picked boxes', rows: mine },
        { key: 'other', caption: 'Other boxes', rows: other },
      ].filter((group) => group.rows.length > 0)
    : [{ key: 'all', caption: null, rows: [...runs] }]

  const live = runs.filter((row) => row.live).length

  const runRow = (row: RunSummary, i: number) => {
    const stage = stageOf(row)
    const open = row.run === openRun
    return (
      <button
        key={row.run}
        type="button"
        className={`run-row${open ? ' run-row-open' : ''}`}
        aria-current={open ? 'true' : undefined}
        onClick={() => onOpenRun(open ? null : row.run)}
        style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
      >
        <span className="run-row-main">
          {/* The box label is what tells two runs apart, and the 320px master cuts it. */}
          <span className="run-row-scope" title={scopeOf(row)}>
            {scopeOf(row)}
          </span>
          <span className="run-row-name" title={row.run}>
            {row.run}
          </span>
        </span>
        <span className="run-row-side">
          <span className="run-row-when">{whenLabel(row.updated_at ?? row.created_at)}</span>
          <StagePill stage={stage} />
        </span>
        <StageBar stage={stage} className="run-row-bar" />
      </button>
    )
  }

  const stage = detail === null ? null : stageOf(detail)
  const stepState = (cmd: Command): StepState => {
    const i = COMMANDS.indexOf(cmd)
    const s = stage?.step ?? 0
    if (stage?.live && i === 0) return 'live'
    if (i < s) return 'done'
    if (i === s) return 'current'
    return 'todo'
  }

  const summaryOf = (cmd: Command): string => {
    if (detail === null) return ''
    const st = stepState(cmd)
    switch (cmd) {
      case 'identify':
        if (st === 'live') return `${runningFor(detail)} — identification takes minutes to hours`
        if (detail.phase === 'identify') return 'Submitted, not yet collected'
        if (st === 'done')
          return detail.counts.cards_in === undefined
            ? 'Collected'
            : `${count(detail.counts.cards_in)} photographs read by the model`
        return 'Reads every photograph with the model'
      case 'join':
        if (st === 'done')
          return `${count(detail.counts.skus)} SKUs · ${count(detail.counts.queued_main)} to review · ${count(
            detail.counts.queued_parked,
          )} parked`
        if (st === 'current') return 'Resolve each card against a TCGplayer export'
        return 'After identify'
      case 'emit':
        if (st === 'done') return 'Import files written'
        if (st === 'current') return 'Price the SKUs and write the import files — on Pricing'
        return 'After join'
      case 'reconcile':
        if (st === 'done') return 'Reconciled against Export From Staged'
        if (st === 'current') return 'Compare what TCGplayer staged with what emit wrote'
        return 'After emit'
      default:
        return ''
    }
  }

  const troubleFor = (keys: readonly Trouble['key'][]) =>
    trouble !== null && keys.includes(trouble.key) ? (
      <div className="runs-trouble">
        <Notice tone="danger" code={trouble.failure.code}>
          {trouble.failure.message}
        </Notice>
        <Button size="sm" variant="ghost" icon="x" iconOnly onClick={() => setTrouble(null)}>
          Dismiss
        </Button>
      </div>
    ) : null

  const result = (cmd: Command) =>
    stepOut === null || stepOut.step !== cmd ? null : (
      <div className={`run-result${stepOut.ok ? '' : ' run-result-refused'}`}>
        <div className="run-result-head">
          <Pill tone={stepOut.ok ? 'ok' : 'danger'} icon={stepOut.ok ? 'check' : 'alert'}>
            {TITLES[cmd]} {stepOut.ok ? 'finished' : 'refused'}
          </Pill>
          <Button size="sm" variant="ghost" onClick={() => setStepOut(null)}>
            Dismiss
          </Button>
        </div>
        <LogWell text={stepOut.console} label={`What ${TITLES[cmd]} printed`} />
      </div>
    )

  const toggleStep = (cmd: Command) => setOpenStep((held) => (held === cmd ? null : cmd))
  const pricingHref = openRun === null ? '#/pricing' : `#/pricing?run=${encodeURIComponent(openRun)}`

  /* One failure on the screen: the page's, or failing that the list's own poll. While it stands
     the list is not "empty" — it is unknown — and the detail column offers no second button. */
  const failure = pageFailure ?? (trouble !== null && trouble.key === 'poll' ? trouble.failure : null)

  const loadingPanel = (
    <div className="bn-panel runs-detail-panel runs-detail-loading" aria-busy="true">
      {troubleFor(['detail'])}
      <div className="bn-skeleton" style={{ height: 14, width: 140 }} />
      <div className="bn-skeleton" style={{ height: 28, width: 320 }} />
      <div className="bn-skeleton" style={{ height: 12, width: 200 }} />
      <div className="bn-skeleton" style={{ height: 56, marginTop: 12 }} />
      <div className="bn-skeleton" style={{ height: 120 }} />
    </div>
  )

  return (
    <div className="runs-body" data-open={openRun !== null ? 'true' : undefined}>
      {/* ---------------------------------------------------------------- the master */}
      <aside className="runs-master bn-panel" aria-label="Every run">
        <div className="runs-master-head">
          <span className="bn-section-title">
            <Icon name="history" size={16} /> Runs
          </span>
          {runs.length === 0 ? null : (
            <span className="run-list-head">
              {runs.length} run{runs.length === 1 ? '' : 's'}
              {live > 0 ? (
                <Pill tone="live" className="runs-pill-live">
                  <span className="bn-dot bn-dot-live" />
                  {live} running
                </Pill>
              ) : null}
            </span>
          )}
        </div>
        {pageFailure !== null ? (
          <div className="runs-trouble">
            <Notice tone="danger" code={pageFailure.code}>
              {pageFailure.message}
            </Notice>
          </div>
        ) : (
          troubleFor(['poll'])
        )}
        <div className="run-list">
          {!loaded ? (
            Array.from({ length: 5 }, (_, i) => <div key={i} className="bn-skeleton runs-skel-row" />)
          ) : runs.length === 0 ? (
            failure !== null ? null : (
              <EmptyState
                icon="play"
                className="run-empty"
                title="No runs yet"
                body="Identify a box to start the first one. It is the one step that spends money."
                actions={
                  <Button icon="zap" onClick={onIdentify}>
                    Identify a box
                  </Button>
                }
              />
            )
          ) : (
            groups.map((group) => (
              <div className="run-list-group" key={group.key}>
                {group.caption === null ? null : (
                  <p className="run-group">
                    {group.caption}
                    <span className="run-group-count">{group.rows.length}</span>
                  </p>
                )}
                {group.rows.map(runRow)}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* ---------------------------------------------------------------- the detail */}
      <section className="runs-detail">
        {openRun === null ? (
          !loaded ? (
            /* Until the list has answered once, nothing here is known — least of all that there
               is no run to pick. */
            loadingPanel
          ) : (
            <div className="bn-panel runs-detail-empty">
              {/* No button in this column: the header carries the screen's one primary. */}
              <EmptyState
                icon={failure === null && runs.length === 0 ? 'zap' : 'play'}
                title={failure === null && runs.length === 0 ? 'Identify a box first' : 'Pick a run'}
                body={
                  failure === null && runs.length === 0
                    ? 'Join, emit and reconcile all work on a run, and the first one starts with a paid identification.'
                    : 'Join, emit and reconcile act on the run you pick from the list.'
                }
              />
            </div>
          )
        ) : detail === null ? (
          loadingPanel
        ) : (
          <div
            className="bn-panel runs-detail-panel"
            key={detail.run}
            data-reconciled={stage !== null && stage.step === 4 ? 'true' : undefined}
          >
            <header className="runs-detail-head">
              <Button className="runs-back" variant="ghost" icon="arrowLeft" onClick={() => onOpenRun(null)}>
                All runs
              </Button>
              <div className="runs-detail-title">
                <span className="bn-eyebrow">
                  {detail.scope != null && !detail.scope.whole_box
                    ? `${count(detail.scope.cards)} ticked cards`
                    : 'Whole box'}
                  {' · '}
                  {whenLabel(detail.updated_at ?? detail.created_at)}
                  {detail.started_by
                    ? ` · started from ${STARTER[detail.started_by] ?? capitalise(detail.started_by)}`
                    : ''}
                </span>
                <h2 className="runs-detail-h">{runBoxLabel(detail) ?? detail.run}</h2>
                <span className="runs-detail-name">{detail.run}</span>
              </div>
              <div className="runs-detail-side">{stage === null ? null : <StagePill stage={stage} />}</div>
            </header>

            <ol className="runs-stepper" aria-label="The four steps">
              {COMMANDS.map((cmd, i) => {
                const st = stepState(cmd)
                return (
                  <li key={cmd} className={`runs-stepper-item runs-stepper-${st}`}>
                    <button
                      type="button"
                      className="runs-stepper-btn"
                      aria-current={st === 'current' || st === 'live' ? 'step' : undefined}
                      onClick={() => setOpenStep(cmd)}
                    >
                      <span className="runs-stepper-track" />
                      <span className="runs-stepper-label">
                        <span className="runs-stepper-n">
                          {st === 'done' ? (
                            <Icon name="check" size={11} strokeWidth={2.5} />
                          ) : st === 'live' ? (
                            <span className="bn-dot bn-dot-live" />
                          ) : (
                            i + 1
                          )}
                        </span>
                        {TITLES[cmd]}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>

            {troubleFor(['detail'])}

            {!detail.joined ? null : (
              <div className="runs-figures">
                <Stat value={count(detail.counts.cards_in)} label="Cards in" />
                <Stat value={count(detail.counts.skus)} label="SKUs" />
                <Stat
                  value={
                    <a
                      className="run-figure-link"
                      href="#/review"
                      aria-label={`Answer ${count(detail.counts.queued_main)} in the review queue`}
                    >
                      {count(detail.counts.queued_main)}
                    </a>
                  }
                  label="To review"
                />
                <Stat
                  value={
                    <a
                      className="run-figure-link"
                      href="#/review"
                      aria-label={`See ${count(detail.counts.queued_parked)} parked in the review queue`}
                    >
                      {count(detail.counts.queued_parked)}
                    </a>
                  }
                  label="Parked"
                />
                {/* A ghost: the Emit step below holds this route-out as its action. */}
                <a className="bn-btn bn-btn-ghost runs-price-btn" href={pricingHref}>
                  Price {count(detail.counts.skus)} SKUs
                  <Icon name="arrowRight" size={16} />
                </a>
              </div>
            )}

            <div className="runs-steps">
              {/* -------------------------------------------------------------- identify */}
              <StepCard
                n={1}
                title={TITLES.identify}
                state={stepState('identify')}
                summary={summaryOf('identify')}
                cost={
                  <Pill tone="warn" icon="dollar" className="run-step-money">
                    Costs money
                  </Pill>
                }
                open={openStep === 'identify'}
                onToggle={() => toggleStep('identify')}
              >
                <div className="runs-kv-row">
                  {detail.usage.input_tokens != null ? (
                    <span className="bn-muted">
                      {detail.usage.input_tokens.toLocaleString()} tokens in · {(detail.usage.output_tokens ?? 0).toLocaleString()}{' '}
                      out
                    </span>
                  ) : null}
                  {detail.batch_ids.length > 0 ? (
                    <span className="bn-mono runs-batch">{detail.batch_ids.join(' · ')}</span>
                  ) : null}
                </div>
                {detail.live ? (
                  <p className="runs-step-lede">
                    <span className="bn-dot bn-dot-live" /> {runningFor(detail)} — it keeps running if you close this
                    tab, and this panel re-reads it every few seconds.
                  </p>
                ) : null}
                {detail.console.trim() === '' ? (
                  <p className="runs-step-lede">Nothing was captured here — this run was started from a terminal.</p>
                ) : (
                  <LogWell text={detail.console} label="What Identify printed" />
                )}
              </StepCard>

              {/* ------------------------------------------------------------------ join */}
              <StepCard
                n={2}
                title={TITLES.join}
                state={stepState('join')}
                summary={summaryOf('join')}
                cost={<Pill>Free · re-runnable</Pill>}
                open={openStep === 'join'}
                onToggle={() => toggleStep('join')}
              >
                <p className="runs-step-lede">
                  Resolves each card against a TCGplayer export and writes the queues and the pricing questions.
                </p>
                {scopeInfo !== null && scopeSentence !== null ? (
                  <p className="run-scope-says">
                    <Icon name="external" size={14} />
                    <span>
                      Will ask TCGplayer for <strong>{scopeSentence.what}</strong>
                      {scopeSentence.why === null ? '.' : ` — ${scopeSentence.why}.`}
                    </span>
                  </p>
                ) : null}

                <div className="run-actions">
                  <Button
                    variant="primary"
                    icon="download"
                    busy={busy === 'fetch'}
                    disabled={busy !== null}
                    onClick={() => void doFetchExport()}
                  >
                    Fetch from TCGplayer
                  </Button>
                  <Button
                    icon="eye"
                    busy={busy === 'join'}
                    disabled={busy !== null}
                    onClick={() => void doStep('join', { dryRun: true, reviewBelowConfidence: reviewBelow })}
                  >
                    Preview
                  </Button>
                  <Button
                    icon="refresh"
                    disabled={busy !== null}
                    onClick={() => void doStep('join', { reviewBelowConfidence: reviewBelow })}
                  >
                    Join again
                  </Button>
                  <FileButton
                    label="Join with an export…"
                    multiple
                    disabled={busy !== null}
                    busy={busy === 'exports'}
                    onFiles={(files) => void joinWithExports(files)}
                  />
                  <Button
                    variant="ghost"
                    icon="settings"
                    iconRight={optionsOpen ? 'chevronUp' : 'chevronDown'}
                    aria-expanded={optionsOpen}
                    onClick={() => setOptionsOpen((v) => !v)}
                  >
                    Options
                  </Button>
                </div>

                {optionsOpen ? (
                  <div className="runs-options bn-well">
                    {/* Two labelled groups, in the same register: what the join queues, and what
                        the fetch asks for. The well used to open on a lone checkbox. */}
                    <div className="runs-optgroup">
                      <p className="run-scope-head">What the join queues</p>
                      <label className="runs-option runs-option-row">
                        <span className="bn-field-label">Send to review at or below</span>
                        <select
                          className="bn-select run-select"
                          value={reviewBelow}
                          onChange={(event) => setReviewBelow(event.target.value as 'none' | 'low' | 'medium')}
                        >
                          {REVIEW_BELOW.map((row) => (
                            <option key={row.key} value={row.key}>
                              {row.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <p className="run-step-fine">
                        A card the model read with less confidence than this goes to the review queue instead of
                        straight to a price.
                      </p>
                    </div>

                    {scopeInfo === null ? null : (
                      <div className="run-scope">
                        <p className="run-scope-head">The export this run will ask for</p>
                        {scopeInfo.games.length < 2 ? null : (
                          <label className="runs-option runs-option-row">
                            <span className="bn-field-label">Category</span>
                            <select
                              className="bn-select run-select"
                              value={scopeGame ?? ''}
                              onChange={(event) => {
                                setScopeGame(event.target.value)
                                setScopeTicked([])
                              }}
                            >
                              <option value="">Pick one…</option>
                              {scopeInfo.games.map((row) => (
                                <option key={row.game} value={row.game}>
                                  {row.display} · {row.cards} card{row.cards === 1 ? '' : 's'}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        {scopeInfo.games
                          .filter((row) => row.game === (scopeGame ?? scopeInfo.asked?.game))
                          .map((row) => (
                            <p className="run-step-fine" key={row.game}>
                              {row.hinted} of {row.cards} card{row.cards === 1 ? '' : 's'} carry a set hint
                              {row.hints.length === 0 ? '' : ` (${row.hints.join(', ')})`}. {row.display}&rsquo;s own
                              rule is{' '}
                              {row.policy === 'category'
                                ? 'the whole category — its catalogue comes down in one file.'
                                : 'the hinted sets — but only when every card carries a hint.'}
                            </p>
                          ))}
                        <Segmented<ScopeChoice>
                          className="run-scope-choices"
                          label="Which sets to ask for"
                          value={scopeChoice}
                          options={SCOPE_CHOICES.map((row) => ({ value: row.key, label: row.label }))}
                          onChange={setScopeChoice}
                        />
                        {scopeChoice !== 'sets' ? null : (
                          <div className="run-scope-sets">
                            {setList.length === 0 ? (
                              <p className="run-step-fine">
                                No set list — that needs the same TCGplayer session the fetch does. Pick another
                                option, or sign in to TCGplayer again so the fetch has a session.
                              </p>
                            ) : (
                              setList.map((row) => (
                                <label className="bn-check" key={row.id}>
                                  <input
                                    type="checkbox"
                                    checked={scopeTicked.includes(Number(row.id))}
                                    onChange={(event) =>
                                      setScopeTicked((held) =>
                                        event.target.checked
                                          ? [...held, Number(row.id)]
                                          : held.filter((id) => id !== Number(row.id)),
                                      )
                                    }
                                  />
                                  {row.name}
                                </label>
                              ))
                            )}
                          </div>
                        )}
                        {scopeInfo.message === null ? null : (
                          <Notice tone="warn" code={scopeInfo.reason ?? undefined}>
                            {scopeInfo.message}
                          </Notice>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}

                {troubleFor(['join', 'fetch', 'exports'])}

                {fetched === null ? null : (
                  /* THE RECEIPT. Reassurance, refusing nothing: what came down, how big it was,
                     and what the last one was — the two guards that used to stand here asked
                     the operator to argue with a number instead of reading it. */
                  <div className="run-receipt" role="status">
                    <span className="run-receipt-mark" aria-hidden="true">
                      <Icon name="check" size={13} strokeWidth={2.5} />
                    </span>
                    <div className="run-receipt-said">
                      <p className="run-receipt-head">
                        <span className="run-receipt-what">Export fetched</span>
                        <span className="run-receipt-rows">{fetched.rows.toLocaleString()} rows</span>
                        <span>{gameDisplay(fetched.asked.game)}</span>
                        <span>{scopeWords(fetched.asked)}</span>
                      </p>
                      <p className="run-receipt-was">{previousLine(fetched, gameDisplay)}</p>
                      <span className="run-receipt-tear" aria-hidden="true" />
                      {/* The counts only. WHY the scope is what it is stands two lines above this,
                          on the sentence that precedes the press — saying it twice in 200px reads
                          as a defence of the figure rather than a receipt for it. */}
                      <p className="run-receipt-fine">
                        {fetched.skus.toLocaleString()} SKUs · {fetched.sets.length} set
                        {fetched.sets.length === 1 ? '' : 's'} · {fetched.conditions.length} condition
                        {fetched.conditions.length === 1 ? '' : 's'}
                      </p>
                      {fetched.asked.unresolved_hints.length === 0 ? null : (
                        <p className="run-receipt-fine">
                          No TCGplayer set matched {fetched.asked.unresolved_hints.join(', ')} — those cards were
                          covered by the wider ask.
                        </p>
                      )}
                      <p className="run-receipt-file bn-mono">{fetched.file}</p>
                    </div>
                  </div>
                )}

                {fetchRefusal === null ? null : (
                  <div className="run-note run-result-refused">
                    <Notice tone="danger" code={fetchRefusal.code}>
                      {fetchRefusal.message}
                    </Notice>
                  </div>
                )}

                {result('join')}

                <p className="run-step-fine">
                  Preview writes nothing — it walks the ladder and says what it would queue. One export file per
                  game; fetching needs a TCGplayer session.
                </p>
              </StepCard>

              {/* ------------------------------------------------------------------ emit */}
              <StepCard
                n={3}
                title={TITLES.emit}
                state={stepState('emit')}
                summary={summaryOf('emit')}
                cost={<Pill>Free · re-runnable</Pill>}
                open={openStep === 'emit'}
                onToggle={() => toggleStep('emit')}
              >
                <p className="runs-step-lede">
                  Prices, holds and the sub-threshold answer are set on Pricing, and the same screen writes the
                  import files. Emit refuses while a sub-threshold price is unanswered.
                </p>
                <div className="run-actions">
                  <a className="bn-btn bn-btn-primary" href={pricingHref}>
                    <Icon name="tag" size={16} />
                    Price and emit this run
                    <Icon name="arrowRight" size={16} />
                  </a>
                </div>
                {/* The per-run rule/basis editor is gone with the file it wrote: the answer is one
                    document for the whole store (D86), and Pricing is the press that writes it. */}
                <p className="run-step-fine">
                  The pricing rule and basis are one answer for the whole store now. They are set on{' '}
                  <a className="run-fine-link" href={pricingHref}>
                    Pricing
                  </a>
                  , not in this run.
                </p>
                {result('emit')}
              </StepCard>

              {/* ------------------------------------------------------------- reconcile */}
              <StepCard
                n={4}
                title={TITLES.reconcile}
                state={stepState('reconcile')}
                summary={summaryOf('reconcile')}
                cost={<Pill>Free · re-runnable</Pill>}
                open={openStep === 'reconcile'}
                onToggle={() => toggleStep('reconcile')}
              >
                <p className="runs-step-lede">
                  After Import to Staged on TCGplayer, download its Export From Staged and compare it with what emit
                  wrote. Quantities move; nothing is marked sold.
                </p>
                <div className="run-actions">
                  <FileButton
                    label="Compare with Export From Staged…"
                    disabled={busy !== null}
                    busy={busy === 'staged'}
                    onFiles={(files) => void compareStaged(files)}
                  />
                </div>
                {troubleFor(['staged'])}
                {result('reconcile')}
              </StepCard>
            </div>

            <div className="runs-detail-files">
              <RunFiles run={detail.run} files={detail.files} only="run" />
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
