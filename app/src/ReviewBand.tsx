import { useEffect, useMemo, useRef, useState } from 'react'
import { getCaptureSitting, getMatchSweep, getMatchState, getQueues, getRuns } from './server'
import type { MatchSweep } from './types'
import { usePoll } from './usePoll'
import { Button, Money } from './kit'
import { roundsToNothing } from './money'

/* THE REVIEW SUMMARY BAND (`docs/specs/identify-engine-pick.md`, section 8). It sits where the Identify strip sat.
 *
 * THE SCOPE: a selection handed to Review (`carried`) wins; else this sitting, the Capture head's own keys, so "matched
 * free" here and "matched" there agree; else the cards the pipeline says wait (`waiting`, the parent's one list). One poll,
 * `usePoll`, about 3 s while a worker reads and 20 s otherwise, over the keys-scoped sweep read.
 *
 * EVERY CARD IN SCOPE LANDS IN EXACTLY ONE COUNT. The server splits the unanswered ones (matched, paid, unread, unhinted);
 * a card that also has an open review row counts only in "waiting for you".
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
  carried,
  reviewKeys,
  rate,
  busy,
  onRead,
}: {
  /** The cards a paid press would buy: captured, photographed, no identification, unclaimed. */
  readonly waiting: readonly string[]
  /** The keys a selection handed to Review names, or null. */
  readonly carried: readonly string[] | null
  /** Position keys of the open review rows, or null while the queues load. */
  readonly reviewKeys: readonly string[] | null
  /** This store's past cost per card, or null when it has none. */
  readonly rate: number | null
  readonly busy: boolean
  /** Starts the paid look over exactly these keys. */
  readonly onRead: (keys: readonly string[]) => Promise<void>
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

  /* The keys the scope names, or null when the scope is every waiting card. */
  const named = carried ?? sitting ?? null
  const keys = useMemo(() => (carried !== null ? carried : sitting === undefined ? null : (sitting ?? waiting)), [carried, sitting, waiting])
  const [sweep, setSweep] = useState<MatchSweep | null>(null)
  /* After a press, runs are reading: poll at the live pace until nothing is left to read. */
  const pressed = useRef(false)
  /* Two answers alike after a press (a refused press, a reader that never starts) end it: back to the slow pace. */
  const runLive = useRef(false)
  const last = useRef<{ left: number; alike: number }>({ left: -1, alike: 0 })
  const { refresh } = usePoll<MatchSweep>({
    fn: async () => {
      const answer = await getMatchSweep([...(keys ?? [])])
      /* Runs are read only while a press is pending, never on an idle tick. */
      if (pressed.current) runLive.current = await getRuns().then((runs) => runs.some((run) => run.live)).catch(() => false)
      return answer
    },
    onData: setSweep,
    liveMs: 3_000,
    idleMs: 20_000,
    isLive: (answer) => {
      const left = (answer.paid ?? 0) + (answer.unread ?? 0)
      if (answer.running || (pressed.current && runLive.current)) {
        last.current = { left, alike: 0 }
        return true
      }
      if (!pressed.current || left === 0) return false
      last.current = { left, alike: last.current.left === left ? last.current.alike + 1 : 0 }
      if (last.current.alike >= 2) pressed.current = false
      return pressed.current
    },
    enabled: keys !== null,
    restartKey: keys === null ? null : keys.join(','),
  })

  /* Open review rows in scope; with no named scope every open row counts. A card with one counts here and nowhere else.
     The parent's own queue read is the answer (`reviewKeys`), so a visit and an answered card cost no read here. Only the
     matched set moving AFTER its first answer asks the queues again, so a card a reader just matched while it waits on
     a row is never counted twice; that read is good for the rows it was made against and no longer. */
  const [reread, setReread] = useState<{ sig: string; keys: readonly string[] } | null>(null)
  const matchedSig = (sweep?.matched_keys ?? []).join(',')
  const reviewSig = reviewKeys === null ? null : reviewKeys.join(',')
  const baseline = useRef<string | null>(null)
  useEffect(() => {
    if (sweep === null) return
    const first = baseline.current === null
    const moved = baseline.current !== matchedSig
    baseline.current = matchedSig
    if (first || !moved || reviewSig === null) return
    let live = true
    void getQueues()
      .then((snapshot) => {
        if (live) setReread({ sig: reviewSig, keys: snapshot.review.filter((entry) => !entry.cleared_by_human).map((entry) => `${entry.box}/${entry.index}`) })
      })
      .catch(() => undefined)
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the matched signature is WHEN to read; the rest is read as it stands
  }, [matchedSig])
  const openKeys = reread !== null && reread.sig === reviewSig ? reread.keys : null
  const reviewing = useMemo(() => {
    const open = openKeys ?? reviewKeys
    if (open === null) return null
    if (named === null) return open
    const inside = new Set(named)
    return open.filter((key) => inside.has(key))
  }, [openKeys, reviewKeys, named])
  const matchedAlso = useMemo(() => {
    const open = new Set(reviewing ?? [])
    return (sweep?.matched_keys ?? []).filter((key) => open.has(key)).length
  }, [sweep, reviewing])

  const loaded = sweep !== null && reviewing !== null
  const figures = {
    matched: Math.max(0, (sweep?.matched_here ?? 0) - matchedAlso),
    paid: sweep?.paid ?? 0,
    unread: sweep?.unread ?? 0,
    you: reviewing?.length ?? 0,
  }
  const left = figures.paid
  const about = rate === null ? null : rate * left
  const parts: string[] = []
  if (loaded) {
    if (sweep.blocked != null || needsSetup) parts.push('Needs setup')
    else if (sweep.running) parts.push('Matching now')
    if (sweep.aside > 0) parts.push(`${sweep.aside} set aside`)
    const unhinted = sweep.unhinted ?? 0
    if (unhinted > 0) parts.push(unhinted === 1 ? '1 needs a set named' : `${unhinted} need a set named`)
  }
  const health = parts.length === 0 ? null : parts.join(', ')

  const read = async () => {
    pressed.current = true
    runLive.current = false
    last.current = { left: (sweep?.paid ?? 0) + (sweep?.unread ?? 0), alike: 0 }
    await onRead(sweep?.paid_keys ?? [])
    refresh()
  }

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
              <Button variant="primary" icon="zap" busy={busy} disabled={busy} onClick={() => void read()} className="review-band-read">
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
