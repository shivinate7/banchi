/* THE PAGE'S WRITE LINE (D329, a press that must wait says so at once). One line per screen, at module level so it
   outlives any mounted screen: leaving the screen does not stop the writes already pressed, and coming back must not
   start a second worker beside the first. A line sends its writes in the order they were pressed, one at a time,
   because the capture server is threaded and a burst of clients kills it. Writes on different screens never wait on
   each other. */

/** One write handed to a line. `done` settles when the write has answered, and also when it was cancelled. */
export type LineJob = { readonly done: Promise<void> }

type Entry = {
  readonly run: () => Promise<void>
  readonly line: Line
  readonly resolve: () => void
  /** What the write is, in the words a press waiting behind it uses (`sayQueued`). */
  readonly what: string | null
  /** `waiting` until the worker takes it, `out` while it runs, `over` once answered or cancelled. */
  state: 'waiting' | 'out' | 'over'
}

type Line = {
  readonly waiting: Entry[]
  draining: boolean
  /** The write out now. */
  out: Entry | null
  /** Writes not yet answered: those waiting and the one out. */
  unanswered: number
}

/** The line a caller that names no screen gets. */
const SHARED = 'page'

const lines = new Map<string, Line>()
const entries = new WeakMap<LineJob, Entry>()

function lineOf(screen: string): Line {
  let line = lines.get(screen)
  if (line === undefined) {
    line = { waiting: [], draining: false, out: null, unanswered: 0 }
    lines.set(screen, line)
  }
  return line
}

/** THE LINE'S ONE WORKER. The first write starts in the press's own turn, so a screen that guards on "a write is out"
 *  sees it at once. A write that throws does not strand the ones behind it: its own caller reports its trouble, and the
 *  line goes on. */
function pump(line: Line): void {
  if (line.draining) return
  line.draining = true
  void (async () => {
    try {
      for (let entry = line.waiting.shift(); entry !== undefined; entry = line.waiting.shift()) {
        entry.state = 'out'
        line.out = entry
        try {
          await entry.run()
        } catch {
          // The write's own caller says what went wrong; the line only keeps moving.
        } finally {
          entry.state = 'over'
          line.out = null
          line.unanswered -= 1
          entry.resolve()
        }
        /* The next write goes out a turn later, so the screen has drawn this answer before it is asked for the next one. */
        if (line.waiting.length > 0) await new Promise<void>((next) => setTimeout(next, 0))
      }
    } finally {
      line.draining = false
    }
  })()
}

/** Run `run` on a screen's line, after every write already in it. `what` names the write for a press that waits behind it. */
export function queueWrite(run: () => Promise<void>, { screen = SHARED, what = null }: { readonly screen?: string; readonly what?: string | null } = {}): LineJob {
  const line = lineOf(screen)
  let resolve: () => void = () => {}
  const done = new Promise<void>((settle) => {
    resolve = settle
  })
  const job: LineJob = { done }
  entries.set(job, { run, line, resolve, what, state: 'waiting' })
  line.unanswered += 1
  line.waiting.push(entries.get(job) as Entry)
  pump(line)
  return job
}

/** Is this write waiting its turn? False once it is out, answered or cancelled. */
export function isQueued(job: LineJob): boolean {
  return entries.get(job)?.state === 'waiting'
}

/** Drop a write still waiting, before it is sent. False for a write already out. */
export function cancel(job: LineJob): boolean {
  const entry = entries.get(job)
  if (entry === undefined || entry.state !== 'waiting') return false
  entry.line.waiting.splice(entry.line.waiting.indexOf(entry), 1)
  entry.state = 'over'
  entry.line.unanswered -= 1
  entry.resolve()
  return true
}

/** The writes of one screen's line not yet answered, waiting or out. */
export function writesInLine(screen: string = SHARED): number {
  return lines.get(screen)?.unanswered ?? 0
}

/** What the write out on a screen's line is (the `what` it was queued with), or null when none is out. A press that must wait
 *  reads it to say what it waits for. */
export function writeOut(screen: string = SHARED): string | null {
  return lines.get(screen)?.out?.what ?? null
}

/** The words beside a press that waits: what it waits for. The one sentence every screen shares. */
export function sayQueued(what: string): string {
  return `Waits for the ${what} to save.`
}
