import { useEffect, useMemo, useState } from 'react'
import { getCaptureSitting, getMatchSweep, getMatchState } from './server'
import type { MatchSweep } from './types'
import { usePoll } from './usePoll'
import { Button, Money } from './kit'
import { roundsToNothing } from './money'

/* THE REVIEW SUMMARY BAND (`docs/specs/identify-engine-pick.md`, section 8). It sits where the Identify strip sat.
 *
 * THE SCOPE IS THIS SITTING: the Capture head's own keys, so "matched free" here and "matched" there agree. With no
 * sitting open, it is the cards the pipeline says wait (`waiting`, the parent's one list). One poll, `usePoll`, about
 * 3 s while a worker reads and 20 s otherwise, over the keys-scoped sweep read.
 *
 * IT HOLDS ITS LOADED SIZE FROM THE FIRST PAINT (D313): the four figures sit in equal columns with the number above the
 * label, so a figure gaining a digit moves nothing; the health line and the press row always take their room. */

const COUNTS = [
  ['matched', 'matched free'],
  ['paid', 'waiting for a paid look'],
  ['unread', 'not yet looked at'],
  ['you', 'waiting for you'],
] as const

export function ReviewBand({
  waiting,
  reviewKeys,
  rate,
  busy,
  onRead,
}: {
  /** The cards a paid press would buy: captured, photographed, no identification, unclaimed. */
  readonly waiting: readonly string[]
  /** Position keys of the open review rows, or null while the queues load. */
  readonly reviewKeys: readonly string[] | null
  /** This store's past cost per card, or null when it has none. */
  readonly rate: number | null
  readonly busy: boolean
  /** Starts the paid look over the band's scope. */
  readonly onRead: (scope: readonly string[]) => void
}) {
  /* undefined until the sitting answers: the band reads no scope before it knows which one it is. */
  const [sitting, setSitting] = useState<readonly string[] | null | undefined>(undefined)
  useEffect(() => {
    let live = true
    void getCaptureSitting()
      .then((answer) => live && setSitting(answer.open ? answer.cards.map((card) => card.key) : null))
      .catch(() => live && setSitting(null))
    return () => {
      live = false
    }
  }, [])
  const [needsSetup, setNeedsSetup] = useState(false)
  useEffect(() => {
    let live = true
    void getMatchState()
      .then((state) => live && setNeedsSetup(!state.ready || state.runtime_missing))
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [])

  const keys = useMemo(() => (sitting === undefined ? null : (sitting ?? waiting)), [sitting, waiting])
  const [sweep, setSweep] = useState<MatchSweep | null>(null)
  usePoll<MatchSweep>({
    fn: () => getMatchSweep([...(keys ?? [])]),
    onData: setSweep,
    liveMs: 3_000,
    idleMs: 20_000,
    isLive: (answer) => answer.running,
    enabled: keys !== null,
    restartKey: keys === null ? null : keys.join(','),
  })

  /* Open review rows in the sitting. With no sitting the scope is every card nobody has answered, so every open row counts. */
  const you = useMemo(() => {
    if (reviewKeys === null) return null
    if (sitting === null || sitting === undefined) return reviewKeys.length
    const inside = new Set(sitting)
    return reviewKeys.filter((key) => inside.has(key)).length
  }, [reviewKeys, sitting])

  const loaded = sweep !== null && you !== null
  const figures = { matched: sweep?.matched_here ?? 0, paid: sweep?.paid ?? 0, unread: sweep?.unread ?? 0, you: you ?? 0 }
  const left = figures.paid
  const about = rate === null ? null : rate * left
  const health = !loaded
    ? null
    : sweep.blocked != null || needsSetup
      ? 'Needs setup'
      : sweep.running
        ? 'Matching now'
        : sweep.aside > 0
          ? `${sweep.aside} set aside`
          : null

  return (
    <section className="review-band" aria-label="Where this sitting stands">
      <div className="review-band-counts">
        {COUNTS.map(([id, label]) => (
          <div key={id} className="bn-stat review-band-count">
            <span className="bn-stat-value" style={loaded ? undefined : { visibility: 'hidden' }}>
              {figures[id]}
            </span>{' '}
            <span className="bn-stat-label">{label}</span>
          </div>
        ))}
      </div>
      <div className="review-band-foot">
        <span className="review-band-health" aria-live="polite">
          {health}
        </span>
        <span className="review-band-presses">
          <span className="review-band-slot">
            {!loaded || left === 0 ? null : (
              <Button variant="primary" icon="zap" busy={busy} disabled={busy} onClick={() => onRead(sweep?.paid_keys ?? [])} className="review-band-read">
                Read the {left} left
                {about === null ? null : roundsToNothing(about) ? (
                  ', under a cent'
                ) : (
                  <>
                    , about <Money value={about} />
                  </>
                )}
              </Button>
            )}
          </span>
          <Button variant="ghost" icon="camera" onClick={() => (window.location.hash = '#/capture')} className="review-band-back">
            Back to Capture
          </Button>
        </span>
      </div>
    </section>
  )
}
