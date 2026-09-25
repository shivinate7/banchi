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
 *  - the live check after the lag, and a manual "Check what is live" (Q3, Q7);
 *  - a press still running, which a dropped connection reads instead of offering a second press;
 *  - a send TCGplayer did not confirm, whose cards are held and which is never offered again;
 *  - "Take them back" ONLY after a live check has run past the wait (the owner's ruling,
 *    2026-09-24). Before that the card says when it will be safe;
 *  - after Take back, what must not happen next: an upload that may wait in Staged is not
 *    published, and a downloaded file is not uploaded. Drawn until the owner dismisses it.
 *
 * NO PIPELINE WORD REACHES THE SCREEN (D196): not emit, not staged, not reconcile. */

import { useEffect, useState } from 'react'
import { Button, Icon, Notice, Refusal, Retry } from './kit'
import { clockTime } from './dates'
import { describeFailure, dismissSendWarning, sendCopies, sendFileUrl, takeBackSend } from './server'
import type { Failure } from './server'
import type { SendSummary, SendTrim } from './types'
import { current as liveState, refresh as refreshLive, useLiveCheck } from './liveCheck'
import './SendCard.css'

const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`
const DAY_MS = 24 * 60 * 60 * 1000

/** The failures a second press can fix. Everything else is a refusal: pressing again gets the
 *  same answer, so the card offers no retry for it. */
const RETRYABLE = new Set(['live_check_failed', 'tcg_write_refused', 'tcg_write_unreadable', 'tcg_session_expired', 'tcg_unreachable', 'step_timed_out', 'unreachable'])

/** The failures where the press's own answer never arrived. The server may still be sending,
 *  so the card reads the receipts before it offers anything (a dropped connection must not
 *  invite a second send while the first still runs). `origin_blocked` is here because the
 *  client names a failed fetch that way whenever `/status` still answers — which is also what
 *  a connection dropped mid-send looks like from the page. */
const DROPPED = new Set(['unreachable', 'bad_response', 'origin_blocked'])

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
    case 'send_in_progress':
      return 'A send to TCGplayer is already running, so nothing was sent again.'
    case 'send_held':
      return 'Some of these cards wait on a send TCGplayer has not confirmed, so nothing was sent.'
    case 'price_change_held':
      return 'Some of these cards wait on a price change TCGplayer has not confirmed, so nothing was sent.'
    case 'send_unknown':
      return 'TCGplayer did not confirm this send. Do not send these copies again.'
    case 'take_back_not_yet':
      return 'Not yet. Banchi checks TCGplayer first.'
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

function MissingList({ send }: { readonly send: SendSummary }) {
  if (send.check === null || send.check.missing.length === 0) return null
  return (
    <ul className="send-names">
      {send.check.missing.slice(0, 6).map((row) => (
        <li key={row.sku}>
          <span className="send-name">{row.name || row.sku}</span>
          <span className="send-figure">
            {row.found} of {row.sent} found
          </span>
        </li>
      ))}
      {send.check.missing.length > 6 ? <li className="send-more">and {send.check.missing.length - 6} more</li> : null}
    </ul>
  )
}

/** The upload TCGplayer never confirmed may still wait in its Staged list. SAID FOR AS LONG AS
 *  THE RECEIPT IS DRAWN, before the check and after it, beside Take back too (the round-2
 *  review, F3): nothing here can see that upload leave Staged, and publishing it by hand after
 *  a take-back would list the same copies twice. */
const STAGED_WARNING = 'The upload may still wait in TCGplayer’s Staged list. Do not publish it there.'

function StagedWarning({ send }: { readonly send: SendSummary }) {
  if (!send.unknown?.staged) return null
  return <p className="send-staged">{STAGED_WARNING}</p>
}

/** A TAKEN-BACK RECEIPT'S WARNING, until the owner dismisses it (the round-3 review, H2). The
 *  moment after Take back is the one it matters most: the copies are on the list again, so the
 *  old upload published by hand, or the old file uploaded, would list them twice. */
function TakenBackWarning({
  send,
  dismiss,
  dismissing,
}: {
  readonly send: SendSummary
  readonly dismiss: (stamp: string) => void
  readonly dismissing: boolean
}) {
  if (send.warning === null) return null
  return (
    <Notice
      tone="warn"
      compact
      className="send-standing send-taken-back"
      title={`Copies taken back at ${clockTime(send.taken_back_at)}.`}
      action={
        <Button size="sm" busy={dismissing} disabled={dismissing} onClick={() => dismiss(send.stamp)}>
          Dismiss
        </Button>
      }
    >
      {send.warning === 'staged'
        ? STAGED_WARNING
        : `Do not upload the file written at ${clockTime(send.at)}. Its copies are back on the list.`}
    </Notice>
  )
}

/** One receipt, in one sentence and at most one list. `takeBack` is drawn only when the server
 *  says the copies are takeable, which it says only after a check past the wait. */
function SendStanding({
  send,
  takeBack,
  takingBack,
}: {
  readonly send: SendSummary
  readonly takeBack: (stamp: string) => void
  readonly takingBack: boolean
}) {
  const copies = plural(send.copies, 'copy', 'copies')
  const safeAfter = send.take_back_after ? `You can take them back after ${clockTime(send.take_back_after)}, once Banchi has checked.` : null
  const action =
    send.takeable > 0 ? (
      <Button size="sm" busy={takingBack} disabled={takingBack} onClick={() => takeBack(send.stamp)}>
        {`Take ${plural(send.takeable, 'copy', 'copies')} back`}
      </Button>
    ) : undefined
  switch (send.state) {
    case 'sending':
      return (
        <Notice tone="info" compact className="send-standing send-sending" title={send.copies > 0 ? `Sending ${copies} to TCGplayer.` : 'Sending to TCGplayer.'}>
          Started at {clockTime(send.at)}. The result shows here when TCGplayer answers.
        </Notice>
      )
    case 'unknown':
      return (
        <Notice tone="warn" compact className="send-standing send-unknown" title={`TCGplayer has not confirmed ${copies}.`}>
          {/* A PRESS THAT STOPPED BEFORE IT SENT (the round-2 review, F1) is still held until the
              check, and says so plainly rather than "they may be live". */}
          {send.unknown?.staged
            ? STAGED_WARNING
            : send.unknown?.stage === 'deciding'
              ? 'Banchi stopped partway through this send.'
              : 'They may be live.'}{' '}
          {send.held
            ? `Until Banchi checks, after ${clockTime(send.check_after)}, they stay out of every send.`
            : `Banchi checks after ${clockTime(send.check_after)}.`}{' '}
          Any not found can come back then.
        </Notice>
      )
    case 'written':
      return (
        <Notice tone="warn" compact className="send-standing send-unconfirmed" title={`${copies} written, not confirmed at TCGplayer`} action={action}>
          {safeAfter}
        </Notice>
      )
    case 'waiting':
      if (send.turned_away > 0 && send.accepted !== null) {
        return (
          <Notice tone="warn" compact className="send-standing send-turned-away" title={`TCGplayer took ${send.accepted} of ${plural(send.rows, 'card', 'cards')}.`}>
            Banchi names the rest after {clockTime(send.check_after)}, and they can come back to the list then.
          </Notice>
        )
      }
      return (
        <Notice tone="ok" compact className="send-standing" title={`${copies} went live at ${clockTime(send.published_at)}.`}>
          Banchi checks TCGplayer again after {clockTime(send.check_after)}.
        </Notice>
      )
    case 'checked':
      if (send.check === null) return null
      return (
        <Notice tone="ok" compact className="send-standing" title={`Live and checked at ${clockTime(send.checked_at)}.`}>
          {send.check.found} of {send.check.expected} found at TCGplayer.
          <StagedWarning send={send} />
        </Notice>
      )
    case 'short':
      if (send.check === null) return null
      return (
        <Notice
          tone="warn"
          compact
          className="send-standing send-short-check"
          title={`${send.check.found} of ${send.check.expected} found at TCGplayer at ${clockTime(send.checked_at)}.`}
          action={action}
        >
          <StagedWarning send={send} />
          <MissingList send={send} />
        </Notice>
      )
    default:
      return null
  }
}

/** Receipts the owner still has to know about: a press running, one not confirmed, a file not
 *  found, or copies a check says can come back. Newest first, at most three. */
function openReceipts(sends: readonly SendSummary[]): SendSummary[] {
  return sends
    .filter(
      (send) =>
        send.state === 'sending' ||
        send.state === 'unknown' ||
        send.state === 'written' ||
        (send.state === 'short' && send.takeable > 0),
    )
    .slice(0, 3)
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
  const [dismissing, setDismissing] = useState(false)
  /* A TAKE BACK OR A DISMISS THAT FAILED IS ITS OWN LINE, never the press's failure: that one
     offers "Try again", which SENDS, and says the copies are back on the list. */
  const [undoFailure, setUndoFailure] = useState<{ title: string; failure: Failure } | null>(null)

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
        const failed = describeFailure(err)
        if (DROPPED.has(failed.code)) {
          /* THE ANSWER NEVER ARRIVED. Read the receipts first: a press still running shows as
             "Sending", and the card offers no second press over it. */
          await refreshLive()
          if (liveState().status?.sends.some((send) => send.state === 'sending')) {
            setFailure(null)
            return
          }
        }
        setFailure(failed)
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
  const open = openReceipts(live.status?.sends ?? [])
  const warned = (live.status?.sends ?? []).filter((send) => send.state === 'taken_back' && send.warning !== null)
  const standing =
    latest === null || open.some((send) => send.stamp === latest.stamp)
      ? null
      : latest.state === 'waiting' || latest.state === 'short'
        ? latest
        : latest.state === 'checked' && Number.isFinite(settledAt) && Date.now() - settledAt < DAY_MS
          ? latest
          : null
  const running = open.some((send) => send.state === 'sending')
  const busy = phase !== 'idle' || running
  const label =
    phase === 'waiting'
      ? 'Saving your prices…'
      : phase === 'sending' || running
        ? 'Checking TCGplayer, then sending…'
        : copies !== null && copies > 0
          ? `Send ${plural(copies, 'copy', 'copies')} to TCGplayer`
          : 'Send to TCGplayer'

  const takeBack = async (stamp: string) => {
    setTakingBack(true)
    setUndoFailure(null)
    try {
      await takeBackSend(stamp)
      onSent()
    } catch (err) {
      const failed = describeFailure(err)
      setUndoFailure({ title: failed.code === 'take_back_not_yet' ? refusalTitle(failed.code) : 'Banchi could not take these copies back.', failure: failed })
    } finally {
      setTakingBack(false)
      void refreshLive()
    }
  }

  const dismiss = async (stamp: string) => {
    setDismissing(true)
    setUndoFailure(null)
    try {
      /* THE ANSWER IS THE RECEIPT AS IT NOW STANDS: folded in where this card holds it, and the
         receipts list is read again below. */
      const answer = await dismissSendWarning(stamp)
      setSent((prev) => (prev !== null && prev.stamp === answer.send.stamp ? answer.send : prev))
    } catch (err) {
      setUndoFailure({ title: 'Banchi could not dismiss this warning.', failure: describeFailure(err) })
    } finally {
      setDismissing(false)
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
          busy={phase === 'sending' || phase === 'waiting' || running}
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

      {undoFailure === null ? null : (
        <Refusal compact className="send-failure send-undo-failure" title={undoFailure.title} code={undoFailure.failure.code} detail={undoFailure.failure.message} />
      )}

      {open.map((send) => (
        <SendStanding key={send.stamp} send={send} takeBack={(stamp) => void takeBack(stamp)} takingBack={takingBack} />
      ))}

      {warned.map((send) => (
        <TakenBackWarning key={send.stamp} send={send} dismiss={(stamp) => void dismiss(stamp)} dismissing={dismissing} />
      ))}

      {standing === null ? null : (
        <>
          <SendStanding send={standing} takeBack={(stamp) => void takeBack(stamp)} takingBack={takingBack} />
          {/* WHAT THE GUARD HELD BACK, ANSWERED TO THE PRESS THAT MADE IT. It is read once,
              right after this visit's own send; a later visit does not carry it in the bar. */}
          {sent !== null && sent.stamp === standing.stamp && standing.kind === 'send' ? <TrimList trimmed={standing.trimmed} /> : null}
        </>
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
