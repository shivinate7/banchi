import { Icon, Pill, type PillTone } from './kit'
import type { RunSummary } from './types'
import './Runs.css'

/* WHERE A RUN IS, in one vocabulary for the list, the detail and the home screen. Labels are
 * sentence case — every pill on the product is, and Home's own label rule restyles them.
 *
 * The server's `phase` says which of the four commands a run is WAITING FOR (`ready`,
 * `identifying`, `identify`, `join`, `emit`, `reconcile`, `done`). The screen draws that as
 * six stages — identify, join, review, price, emit and reconcile — because review and
 * pricing are the two things a run waits on between join and emit, and a bar that skipped
 * them would jump from a third to five sixths. */

/** How long a live run has been going, from its own `created_at`. Live only — on a finished
 *  run the same arithmetic is age, which is a different fact. Used by `BoxRuns` too. */
export function runningFor(row: { created_at?: string | null }): string {
  const at = row.created_at == null ? NaN : Date.parse(row.created_at)
  const mins = Number.isNaN(at) ? 0 : Math.max(0, Math.floor((Date.now() - at) / 60000))
  if (mins < 1) return 'Running'
  return mins < 60 ? `Running ${mins}m` : `Running ${Math.floor(mins / 60)}h ${mins % 60}m`
}

export const STAGES = ['Identify', 'Match', 'Review', 'Price', 'Send', 'Compare'] as const

/** The four commands this screen drives, in order. */
export const COMMANDS = ['identify', 'join', 'emit', 'reconcile'] as const
export type Command = (typeof COMMANDS)[number]

export type Stage = {
  readonly label: string
  readonly tone: PillTone
  /** Segments of the six-stage bar that are done. */
  readonly filled: number
  readonly live: boolean
  /** Index of the command the run is waiting for; 4 when it is done. */
  readonly step: 0 | 1 | 2 | 3 | 4
}

export function stageOf(row: RunSummary): Stage {
  if (row.live || row.phase === 'identifying') {
    return { label: runningFor(row), tone: 'live', filled: 0, live: true, step: 0 }
  }
  switch (row.phase) {
    case 'ready':
      return { label: 'Not started', tone: 'default', filled: 0, live: false, step: 0 }
    case 'identify':
      return { label: 'Not read', tone: 'warn', filled: 0, live: false, step: 0 }
    case 'join':
      /* THE MATCH RUNS BY ITSELF (flow interview, Q4), so "needs matching" is no longer a job
         for the owner. What the row says is the match in progress, or the problem that stopped
         it — which is then the run's next step, in two words. */
      if (row.match_problem != null) {
        return { label: matchProblemLabel(row.match_problem.code), tone: 'warn', filled: 1, live: false, step: 1 }
      }
      return { label: 'Matching…', tone: 'accent', filled: 1, live: false, step: 1 }
    case 'emit': {
      const review = row.counts.queued_main ?? 0
      if (review > 0) {
        return { label: `${review} to review`, tone: 'warn', filled: 2, live: false, step: 2 }
      }
      /* THE REAL NEXT STEP, NOT A GUESS ABOUT PRICES (UX-006). This row cannot see whether a
         price is owed — that is Pricing's worklist, too heavy for the polled list — so it names
         the screen the step is on, which is one screen and one press whatever the prices say.
         Two words, the same as the label it replaced: Inventory draws this pill too, and its
         word ceiling holds (D194). Home's line reads the worklist and says which. */
      return { label: 'Next: Pricing', tone: 'accent', filled: 3, live: false, step: 2 }
    }
    case 'reconcile':
      return { label: 'Written', tone: 'ok', filled: 5, live: false, step: 3 }
    case 'done':
      return { label: 'Compared', tone: 'ok', filled: 6, live: false, step: 4 }
    default:
      return { label: 'Unknown', tone: 'default', filled: 0, live: false, step: 0 }
  }
}

/** A match problem in two words, for the pill. The sentence is the detail panel's. */
export function matchProblemLabel(code: string): string {
  switch (code) {
    case 'export_needs_set_hint':
      return 'Needs sets'
    case 'tcg_session_expired':
    case 'tcg_cookie_missing':
    case 'tcg_cookie_malformed':
      return 'Sign in again'
    default:
      return 'Match stopped'
  }
}

/** The problem as one sentence and the one thing to do about it. */
export function matchProblemTitle(code: string): string {
  switch (code) {
    case 'export_needs_set_hint':
      return 'Some cards need a set before they can be matched. Add the sets, then try again.'
    case 'tcg_session_expired':
    case 'tcg_cookie_missing':
    case 'tcg_cookie_malformed':
      return 'The TCGplayer sign-in has expired. Sign in again, then try again.'
    case 'tcg_unreachable':
      return 'TCGplayer did not answer, so the cards were not matched.'
    default:
      return 'The cards could not be matched.'
  }
}

/** The six, in the order the bar draws them — the bar's one tooltip teaches them. */
const STAGE_NAMES = STAGES.map((name) => name.toLowerCase())
const STAGE_WORDS = `${STAGE_NAMES.slice(0, -1).join(', ')} and ${STAGE_NAMES[STAGE_NAMES.length - 1]}`

/** When something happened, in the words a person uses for it. */
export function whenLabel(iso: string | null | undefined): string {
  if (!iso) return ''
  const at = new Date(iso)
  const t = at.getTime()
  if (Number.isNaN(t)) return ''
  const mins = Math.floor((Date.now() - t) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** The six-segment stage bar. */
export function StageBar({ stage, className }: { readonly stage: Stage; readonly className?: string }) {
  const done = stage.filled >= STAGES.length
  const says = `${stage.label} (${Math.min(stage.filled, STAGES.length)} of ${STAGES.length} stages done)`
  return (
    <span
      className={['runs-stagebar', done ? 'runs-stagebar-done' : '', className ?? ''].filter(Boolean).join(' ')}
      role="img"
      aria-label={says}
      title={`${says}. Stages: ${STAGE_WORDS}.`}
    >
      {STAGES.map((name, i) => (
        <span
          key={name}
          data-state={i < stage.filled ? 'done' : i === stage.filled ? (stage.live ? 'live' : 'current') : 'todo'}
        />
      ))}
    </span>
  )
}

/** The stage as a pill: a pulsing dot while live, a check once it is through. */
export function StagePill({ stage }: { readonly stage: Stage }) {
  return (
    <Pill tone={stage.tone} className={stage.live ? 'runs-pill-live' : ''}>
      {stage.live ? <span className="bn-dot bn-dot-live" /> : stage.tone === 'ok' ? <Icon name="check" size={12} /> : null}
      {stage.label}
    </Pill>
  )
}
