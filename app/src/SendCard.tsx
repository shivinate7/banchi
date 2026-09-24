/* THE SEND CARD: ONE PRESS FROM PRICED TO LIVE (`D-one-press-sends-and-makes-live`).
 *
 * Drawn inside Pricing's send bar. Everything the owner reads between "these are priced" and
 * "these are live" is here, in owner words:
 *
 *  - the press, "Send 17 copies to TCGplayer". The server reads what is live first, writes the
 *    file behind the double-send guard, sends it and makes it live, in one request;
 *  - what the guard held back ("2 held back: TCGplayer already had them"), by card;
 *  - a refusal with "Try again" when the live read cannot run (signed out, slow);
 *  - "Download the file instead", the second door, with the split option behind it (the Send
 *    menu ruling: nothing sits beside Send);
 *  - copies written to a file and not yet found at TCGplayer, with "Take them back" (Q8);
 *  - the live check after the lag, and a manual "Check what is live" (Q3, Q7).
 *
 * NO PIPELINE WORD REACHES THE SCREEN (D196): not emit, not staged, not reconcile. */

import { useEffect, useState } from 'react'
import { Button, Icon, Notice, Refusal, Retry } from './kit'
import { clockTime } from './dates'
import { describeFailure, sendCopies, sendFileUrl, takeBackSend } from './server'
import type { Failure } from './server'
import type { SendSummary, SendTrim } from './types'
import { refresh as refreshLive, useLiveCheck } from './liveCheck'
import './SendCard.css'

const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`
const DAY_MS = 24 * 60 * 60 * 1000

/** The failures a second press can fix. Everything else is a refusal: pressing again gets the
 *  same answer, so the card offers no retry for it. */
const RETRYABLE = new Set(['live_check_failed', 'tcg_write_refused', 'tcg_write_unreadable', 'tcg_session_expired', 'step_timed_out', 'unreachable'])

/** One sentence for why a press was refused, in owner words. The server's own text sits behind
 *  "What the server said" (D196, D-notice-detail). */
function refusalTitle(code: string): string {
  switch (code) {
    case 'live_check_failed':
      return 'Banchi could not read what is live at TCGplayer, so nothing was sent.'
    case 'nothing_to_send':
      return 'Nothing to send. Every copy on this list is already at TCGplayer or held back.'
    case 'already_sent':
      return 'These copies were already sent, so nothing was sent again.'
    case 'write_refused':
      return 'The file could not be written, so nothing was sent.'
    case 'answers_not_saved':
      return 'Your prices could not be saved, so nothing was sent.'
    default:
      return 'TCGplayer did not take the send. Nothing is live, and the copies are back on the list.'
  }
}

function TrimList({ trimmed }: { readonly trimmed: readonly SendTrim[] }) {
  if (trimmed.length === 0) return null
  const held = trimmed.reduce((total, trim) => total + (trim.would - trim.goes), 0)
  return (
    <Notice tone="info" compact className="send-trimmed" title={`${plural(held, 'copy', 'copies')} held back: TCGplayer already had them.`}>
      <ul className="send-names">
        {trimmed.slice(0, 6).map((trim) => (
          <li key={trim.sku}>
            <span className="send-name">{trim.name || trim.sku}</span>
            <span className="send-figure">
              {trim.live} of {trim.on_hand} already live
            </span>
          </li>
        ))}
        {trimmed.length > 6 ? <li className="send-more">and {trimmed.length - 6} more</li> : null}
      </ul>
    </Notice>
  )
}

/** Where the newest send stands, in one sentence and at most one list. */
function SendStanding({ send }: { readonly send: SendSummary }) {
  if (send.state === 'waiting') {
    return (
      <Notice tone="ok" compact className="send-standing" title={`${plural(send.copies, 'copy', 'copies')} went live at ${clockTime(send.published_at)}.`}>
        Banchi checks TCGplayer again after {clockTime(send.check_after)}.
      </Notice>
    )
  }
  if (send.state === 'checked' && send.check !== null) {
    return (
      <Notice tone="ok" compact className="send-standing" title={`Live and checked at ${clockTime(send.checked_at)}.`}>
        {send.check.found} of {send.check.expected} found at TCGplayer.
      </Notice>
    )
  }
  if (send.state === 'short' && send.check !== null) {
    return (
      <Notice tone="warn" compact className="send-standing" title={`${send.check.found} of ${send.check.expected} found at TCGplayer at ${clockTime(send.checked_at)}.`}>
        <ul className="send-names">
          {send.check.missing.slice(0, 6).map((row) => (
            <li key={row.sku}>
              <span className="send-name">{row.name || row.sku}</span>
              <span className="send-figure">
                {row.found} of {row.sent} found
              </span>
            </li>
          ))}
        </ul>
      </Notice>
    )
  }
  return null
}

export function SendCard({
  runs,
  copies,
  settled,
  saveFailed,
  quantities,
  onSent,
}: {
  /** The runs whose copies this send carries: the worklist's own list. */
  readonly runs: readonly string[]
  /** Copies the worklist says are ready, for the button's words. Null when not known. */
  readonly copies: number | null
  /** True when every price typed on the screen is saved. A press waits for it. */
  readonly settled: boolean
  /** True when the last save failed. A press refuses rather than sending old prices. */
  readonly saveFailed: () => boolean
  /** The per-row quantities typed for this press. */
  readonly quantities: () => Record<string, number>
  /** A send or a download landed: the worklist should read again. */
  readonly onSent: () => void
}) {
  const live = useLiveCheck()
  const [phase, setPhase] = useState<'idle' | 'waiting' | 'sending' | 'downloading'>('idle')
  const [intent, setIntent] = useState<'send' | 'download'>('send')
  const [failure, setFailure] = useState<Failure | null>(null)
  const [sent, setSent] = useState<SendSummary | null>(null)
  const [downloadOpen, setDownloadOpen] = useState(false)
  const [split, setSplit] = useState(false)
  const [takingBack, setTakingBack] = useState(false)

  /* THE PRESS WAITS FOR THE SAVE RATHER THAN RACING IT: the server writes the file from the
     prices on disk, so a press with a save in flight would send the price before the last one
     typed. `waiting` until the screen is settled, then one request. */
  useEffect(() => {
    if (phase !== 'waiting') return
    if (saveFailed()) {
      setPhase('idle')
      setFailure({ code: 'answers_not_saved', message: 'Your prices could not be saved. Fix the error above and press again.', kind: 'refusal' })
      return
    }
    if (!settled) return
    const download = intent === 'download'
    setPhase(download ? 'downloading' : 'sending')
    void (async () => {
      try {
        const answer = await sendCopies(runs, { download, splitThreshold: download && split, quantities: quantities() })
        setSent(answer.send)
        setFailure(null)
        onSent()
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setPhase('idle')
        void refreshLive()
      }
    })()
  }, [phase, settled, saveFailed, intent, runs, split, quantities, onSent])

  const press = (next: 'send' | 'download') => {
    setIntent(next)
    setFailure(null)
    setPhase('waiting')
  }

  /* THE NEWEST RECEIPT IS WHAT THE CARD STANDS ON, unless this visit's own press is newer than
     the status read has caught up with. A settled send older than a day says nothing here: a
     clock time with no date on it would read as today's. */
  const newest = live.status?.sends[0] ?? null
  const latest = newest !== null && (sent === null || newest.stamp >= sent.stamp) ? newest : sent
  const settledAt = Date.parse(latest?.checked_at ?? latest?.published_at ?? '')
  const standing =
    latest === null
      ? null
      : latest.state === 'waiting' || latest.state === 'short'
        ? latest
        : latest.state === 'checked' && Number.isFinite(settledAt) && Date.now() - settledAt < DAY_MS
          ? latest
          : null
  const unconfirmed = live.status?.unconfirmed ?? { copies: 0, stamps: [] }
  const busy = phase !== 'idle'
  const label =
    phase === 'waiting'
      ? 'Saving your prices…'
      : phase === 'sending'
        ? 'Checking TCGplayer, then sending…'
        : copies !== null && copies > 0
          ? `Send ${plural(copies, 'copy', 'copies')} to TCGplayer`
          : 'Send to TCGplayer'

  const takeBack = async () => {
    setTakingBack(true)
    try {
      for (const stamp of unconfirmed.stamps) await takeBackSend(stamp)
      onSent()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setTakingBack(false)
      void refreshLive()
    }
  }

  return (
    <div className="send-card">
      <div className="send-act">
        <Button
          variant="primary"
          size="lg"
          icon="send"
          className="pricing-emit send-press"
          busy={phase === 'sending' || phase === 'waiting'}
          disabled={busy}
          onClick={() => press('send')}
        >
          {label}
        </Button>
        <Button
          variant="quiet"
          icon="download"
          aria-expanded={downloadOpen}
          disabled={busy}
          onClick={() => setDownloadOpen((open) => !open)}
        >
          {/* THE SAME PRESS, SHORTER ON A PHONE (UX-007): both quiet doors fit on the line under
              the send, so the bar stays two lines high. */}
          <span className="send-long">Download the file instead</span>
          <span className="send-short">Download file</span>
        </Button>
        <Button variant="quiet" icon="refresh" busy={live.checking} disabled={live.checking} onClick={() => void live.checkNow()}>
          <span className="send-long">Check what is live</span>
          <span className="send-short">Check live</span>
        </Button>
      </div>

      {!downloadOpen ? null : (
        <div className="send-download">
          <label className="bn-check">
            <input type="checkbox" checked={split} onChange={(event) => setSplit(event.currentTarget.checked)} />
            <span>Split in two files at the cut-off</span>
          </label>
          <Button icon="download" busy={phase === 'downloading'} disabled={busy} onClick={() => press('download')}>
            {phase === 'downloading' ? 'Writing…' : split ? 'Write the two files' : 'Write the file'}
          </Button>
          {sent === null || sent.kind !== 'download' ? null : (
            <span className="send-files">
              {sent.files.map((file) => (
                <a key={file} className="bn-btn bn-btn-ghost" href={sendFileUrl(sent.stamp, file)} download={file}>
                  <Icon name="download" size={16} />
                  {file}
                </a>
              ))}
            </span>
          )}
        </div>
      )}

      {failure === null ? null : RETRYABLE.has(failure.code) ? (
        <Retry
          compact
          className="send-failure"
          title={refusalTitle(failure.code)}
          code={failure.code}
          detail={failure.message}
          busy={busy}
          onRetry={() => press(intent)}
        />
      ) : (
        <Refusal compact className="send-failure" title={refusalTitle(failure.code)} code={failure.code} detail={failure.message} />
      )}

      {standing === null ? null : (
        <>
          <SendStanding send={standing} />
          {/* WHAT THE GUARD HELD BACK, ANSWERED TO THE PRESS THAT MADE IT. It is read once,
              right after this visit's own send; a later visit does not carry it in the bar. */}
          {sent !== null && sent.stamp === standing.stamp && standing.kind === 'send' ? <TrimList trimmed={standing.trimmed} /> : null}
        </>
      )}

      {unconfirmed.copies === 0 ? null : (
        <Notice
          tone="warn"
          compact
          className="send-unconfirmed"
          title={`${plural(unconfirmed.copies, 'copy', 'copies')} written, not confirmed at TCGplayer`}
          action={
            <Button size="sm" busy={takingBack} disabled={takingBack} onClick={() => void takeBack()}>
              Take them back
            </Button>
          }
        />
      )}

      {live.failure === null ? null : (
        <Retry
          compact
          className="send-failure"
          title="Banchi could not check what is live at TCGplayer."
          code={live.failure.code}
          detail={live.failure.message}
          busy={live.checking}
          onRetry={() => void live.checkNow()}
        />
      )}
    </div>
  )
}
