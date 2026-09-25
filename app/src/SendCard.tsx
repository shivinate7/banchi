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
 *    published, and a downloaded file is not uploaded. Drawn until the owner dismisses it, and
 *    on a phone folded to one line that opens (round 5);
 *  - a MIXED press (the owner's ruling, 2026-09-24: "Allow mixed"): new copies and price
 *    changes on cards already live, named apart, "Send 3 copies and 2 price changes".
 *
 * NO PIPELINE WORD REACHES THE SCREEN (D196): not emit, not staged, not reconcile. */

import { useEffect, useState } from 'react'
import { Button, Icon, Money, Notice, Refusal, Retry } from './kit'
import { clockTime } from './dates'
import { describeFailure, dismissSendWarning, sendCopies, sendFileUrl, takeBackSend } from './server'
import type { Failure } from './server'
import type { LiveMove, PriceChange, RefusedPrice, SendSummary, SendTrim } from './types'
import { current as liveState, refresh as refreshLive, useLiveCheck } from './liveCheck'
import './SendCard.css'

const plural = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`

/** What a press carries, in owner words: "3 copies", "2 price changes", or both joined. A price
 *  change is a card already live whose typed price moves; it adds no copy. */
function carried(copies: number, prices: number): string {
  const parts = [
    copies > 0 || prices === 0 ? plural(copies, 'copy', 'copies') : null,
    prices > 0 ? plural(prices, 'price change', 'price changes') : null,
  ].filter((part): part is string => part !== null)
  return parts.join(' and ')
}
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
    case 'send_rolled_back':
      return 'TCGplayer turned the send away, and Banchi rolled the upload back. Check the Staged list before you send again.'
    case 'price_refused':
      return 'A price change on this list is not the one to send, so nothing was sent.'
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

/** The live copies a press moves, as words and figures: "2 live copies move to $19.99", or "to
 *  new prices" where they move to more than one (the owner's ruling, round 7). */
function MovesPhrase({ moves }: { readonly moves: readonly { copies: number; price: string }[] }) {
  const copies = moves.reduce((total, move) => total + move.copies, 0)
  const prices = new Set(moves.map((move) => Number(move.price)))
  const head = `${plural(copies, 'live copy moves', 'live copies move')} to `
  return prices.size === 1 ? (
    <>
      {head}
      <Money value={Number(moves[0]?.price)} />
    </>
  ) : (
    <>{`${head}new prices`}</>
  )
}

/** The refused rows a press can send again, named (round 7, R6-1): a price whose live figure
 *  moved since the screen read it, and live copies the button did not say would move. Any other
 *  refused row is not offered: the press is refused whole. */
function confirmable(failure: Failure | null): RefusedPrice[] {
  if (failure === null || failure.code !== 'price_refused') return []
  const refused = ((failure.data as { refused?: RefusedPrice[] } | undefined)?.refused ?? []).filter(Boolean)
  /* A MOVE UNDER THE FLOOR, A PRICE NOT SAVED, A CARD NOT IN THE SEND: never offered (R7-1). */
  const offered = new Set<RefusedPrice['why']>(['live_moved', 'move_unnamed', 'move_count'])
  if (refused.length === 0 || refused.some((row) => !offered.has(row.why))) return []
  return refused
}

/** "TCGplayer shows $22.03 now. Send $30.00?" per refused row, and one press that sends again
 *  with the live price named. The server refuses again if TCGplayer moved again. */
function ResendPrices({
  rows,
  busy,
  onSend,
}: {
  readonly rows: readonly RefusedPrice[]
  readonly busy: boolean
  readonly onSend: () => void
}) {
  const one = rows.length === 1 ? rows[0] : undefined
  return (
    <Notice
      tone="warn"
      compact
      className="send-failure send-resend"
      title="TCGplayer's price is not the one this list showed."
      action={
        <Button size="sm" busy={busy} disabled={busy} onClick={onSend}>
          {one !== undefined && one.price !== null ? (
            <>
              Send <Money value={Number(one.price)} />
            </>
          ) : (
            'Send these prices'
          )}
        </Button>
      }
    >
      <ul className="send-names">
        {rows.map((row) => (
          <li key={`${row.sku}-${row.why}`}>
            <span className="send-name">{row.name || row.sku}</span>
            <span className="send-figure">
              {row.why === 'live_moved' ? 'TCGplayer shows ' : `${plural(row.copies, 'live copy', 'live copies')} at `}
              {row.live === null ? 'no price' : <Money value={Number(row.live)} />}
              {row.why === 'live_moved' ? ' now. Send ' : ' move to '}
              {row.price === null ? 'this price' : <Money value={Number(row.price)} />}
              {row.why === 'live_moved' ? '?' : '.'}
            </span>
          </li>
        ))}
      </ul>
    </Notice>
  )
}

/** EVERY LIVE COPY A PRESS MOVES, BEFORE THE PRESS, when they move to more than one price (the
 *  owner's ruling names the copies AND their price; round 8, R7-2). One price fits the button's
 *  own words; more than one is listed here, card by card, the way the guard's trims are listed
 *  after a press. */
function MovesList({ moves }: { readonly moves: readonly LiveMove[] }) {
  if (new Set(moves.map((move) => Number(move.price))).size < 2) return null
  return (
    <Notice tone="info" compact className="send-moves" title="Live copies this press moves to their new price.">
      <ul className="send-names">
        {moves.map((move) => (
          <li key={move.sku}>
            <span className="send-name">{move.name || move.sku}</span>
            <span className="send-figure">
              {`${plural(move.copies, 'live copy', 'live copies')}, `}
              {move.was === null ? 'no price' : <Money value={Number(move.was)} />}
              {' to '}
              <Money value={Number(move.price)} />
            </span>
          </li>
        ))}
      </ul>
    </Notice>
  )
}

/** Why a named price change stayed out of the file, in owner words (round 6). */
const LEFT_WHY: Record<string, string> = {
  already: 'TCGplayer already shows this price',
  not_live: 'no copy is live now',
  adds_copies: 'its new copies carry the price',
}

/** The price changes the button named that this press left out. Named once, right after the
 *  press, like the guard's trims. */
function PricesLeft({ send }: { readonly send: SendSummary }) {
  if (send.prices_left.length === 0) return null
  return (
    <Notice tone="info" compact className="send-prices-left" title={`${plural(send.prices_left.length, 'price change', 'price changes')} left out.`}>
      <ul className="send-names">
        {send.prices_left.slice(0, 6).map((note) => (
          <li key={note.sku}>
            <span className="send-name">{note.name || note.sku}</span>
            <span className="send-figure">{LEFT_WHY[note.why] ?? 'left out'}</span>
          </li>
        ))}
        {send.prices_left.length > 6 ? <li className="send-more">and {send.prices_left.length - 6} more</li> : null}
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

/** Price changes the check found TCGplayer not showing. Named, and never offered back: the way
 *  a live price changes again is another price change. */
function PriceMisses({ send }: { readonly send: SendSummary }) {
  const missing = send.price_check?.missing ?? []
  if (missing.length === 0) return null
  return (
    <ul className="send-names send-price-misses">
      {missing.slice(0, 6).map((row) => (
        <li key={row.sku}>
          <span className="send-name">{row.name || row.sku}</span>
          <span className="send-figure">{row.live === null ? 'no price live' : <>still <Money value={Number(row.live)} /></>}</span>
        </li>
      ))}
      {missing.length > 6 ? <li className="send-more">and {missing.length - 6} more</li> : null}
    </ul>
  )
}

/** What the check found, in one sentence: copies found, price changes live, or both. */
function foundLine(send: SendSummary): string {
  if (send.check !== null && send.prices === 0) return `${send.check.found} of ${send.check.expected} found`
  const parts: string[] = []
  if (send.check !== null && send.check.expected > 0) {
    parts.push(`${send.check.found} of ${plural(send.check.expected, 'copy', 'copies')} found`)
  }
  if (send.prices > 0 && send.price_check !== null) {
    parts.push(`${send.price_check.matched} of ${plural(send.price_check.expected, 'price change', 'price changes')} live`)
  }
  return parts.join(', ')
}

/** The upload TCGplayer never confirmed may still wait in its Staged list. SAID FOR AS LONG AS
 *  THE RECEIPT IS DRAWN, before the check and after it, beside Take back too (the round-2
 *  review, F3): nothing here can see that upload leave Staged, and publishing it by hand after
 *  a take-back would list the same copies twice. */
const STAGED_WARNING = 'The upload may still wait in TCGplayer’s Staged list. Do not publish it there.'

function StagedWarning({ send }: { readonly send: SendSummary }) {
  if (!send.staged) return null
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
  /* ON A PHONE IT FOLDS TO ONE LINE (round 5): two open warnings stood half the screen high in
     the sticky bar. The line is the warning itself, and it opens to the rest. It never folds
     away: only Dismiss takes it off the card, as round 4 ruled. */
  const [open, setOpen] = useState(false)
  if (send.warning === null) return null
  const line =
    send.warning === 'staged'
      ? 'Do not publish the upload.'
      : send.warning === 'rolled_back'
        ? 'Check the Staged list.'
        : 'Do not upload the old file.'
  const head =
    send.warning === 'rolled_back'
      ? `Upload rolled back at ${clockTime(send.taken_back_at)}.`
      : `Copies taken back at ${clockTime(send.taken_back_at)}.`
  return (
    <Notice
      tone="warn"
      compact
      className={open ? 'send-standing send-taken-back send-fold-open' : 'send-standing send-taken-back'}
      title={
        <>
          <span className="send-fold-wide">{head}</span>
          <button type="button" className="send-fold" aria-expanded={open} onClick={() => setOpen((was) => !was)}>
            <span className="send-fold-line">{line}</span>
            <Icon name={open ? 'chevronUp' : 'chevronDown'} size={16} />
          </button>
        </>
      }
      action={
        <Button size="sm" busy={dismissing} disabled={dismissing} onClick={() => dismiss(send.stamp)}>
          Dismiss
        </Button>
      }
    >
      {send.warning === 'staged'
        ? STAGED_WARNING
        : send.warning === 'rolled_back'
          ? /* A ROLLBACK'S ANSWER IS NOT PROOF (round 6, S4): TCGplayer said the upload is gone,
               and nothing here has seen that proved, so the upload MAY still wait there. */
            STAGED_WARNING
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
  const copies = carried(send.copies, send.prices)
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
          {send.staged
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
          {foundLine(send)} at TCGplayer.
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
          title={`${foundLine(send)} at TCGplayer at ${clockTime(send.checked_at)}.`}
          action={action}
        >
          <StagedWarning send={send} />
          <MissingList send={send} />
          <PriceMisses send={send} />
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
  priceChanges = [],
  liveMoves = [],
  settled,
  saveFailed,
  quantities,
  onSent,
}: {
  /** The runs whose copies this send carries: the worklist's own list. */
  readonly runs: readonly string[]
  /** Copies the worklist says are ready, for the button's words. Null when not known. */
  readonly copies: number | null
  /** Cards already live whose typed price this press changes (the mixed send). The server
   *  decides against a fresh read; this is the worklist's count, for the button's words. */
  readonly priceChanges?: readonly PriceChange[]
  /** Live copies this press's listing rows move to their stored price (the owner's ruling,
   *  round 7), off the same fresh read. The button names them, and the server refuses a move it
   *  was not told of. */
  readonly liveMoves?: readonly LiveMove[]
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
  /* WHAT THE OWNER CONFIRMED AFTER A REFUSAL (round 7, R6-1): the live price each named price
     is now measured against, and each move of live copies they agreed to. Spent by a send. */
  const [confirmed, setConfirmed] = useState<{ was: Record<string, string | null>; moves: Record<string, LiveMove> }>({
    was: {},
    moves: {},
  })

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
        const prices = priceChanges.map((change) =>
          change.sku in confirmed.was ? { ...change, was: confirmed.was[change.sku] ?? null } : change,
        )
        const moves = [
          ...liveMoves.filter((move) => !(move.sku in confirmed.moves)),
          ...Object.values(confirmed.moves),
        ]
        const answer = await sendCopies(runs, { download, splitThreshold: download && split, quantities: quantities(), prices, moves })
        setSent(answer.send)
        setFailure(null)
        setConfirmed({ was: {}, moves: {} })
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
  }, [phase, settled, saveFailed, intent, runs, split, quantities, priceChanges, liveMoves, confirmed, onSent])

  const press = (next: 'send' | 'download') => {
    setIntent(next)
    setFailure(null)
    setPhase('waiting')
  }

  /* ONE PRESS SENDS AGAIN WITH WHAT THE OWNER NOW SEES NAMED: each refused price against the
     live price shown, and each refused move of live copies as a move the button said. */
  const resend = (rows: readonly RefusedPrice[]) => {
    setConfirmed((held) => {
      const next = { was: { ...held.was }, moves: { ...held.moves } }
      for (const row of rows) {
        if (row.why === 'live_moved') next.was[row.sku] = row.live
        /* A MOVE THE BUTTON DID NOT NAME, OR NAMED AT ANOTHER COUNT: named now at TCGplayer's own
           count of live copies (round 8, R7-3). */
        else if (row.price !== null) next.moves[row.sku] = { sku: row.sku, name: row.name, copies: row.copies, price: row.price, was: row.live }
      }
      return next
    })
    press(intent)
  }
  const offered = confirmable(failure)

  /* THE NEWEST RECEIPT IS WHAT THE CARD STANDS ON, unless this visit's own press is one the
     status read has not caught up with yet. The server lists receipts newest PRESS first; a stamp
     is never compared here, because two presses in one second order by a random tail (round 5).
     A settled send older than a day says nothing here: a clock time with no date on it would
     read as today's. */
  const newest = live.status?.sends[0] ?? null
  const caughtUp = sent === null || (live.status?.sends ?? []).some((send) => send.stamp === sent.stamp)
  const latest = newest !== null && caughtUp ? newest : sent
  const settledAt = Date.parse(latest?.checked_at ?? latest?.published_at ?? '')
  const open = openReceipts(live.status?.sends ?? [])
  /* A TAKEN-BACK RECEIPT, OR A FAILED ONE WHOSE UPLOAD WAS ROLLED BACK (round 6, S4), keeps its
     warning until the owner dismisses it. */
  const warned = (live.status?.sends ?? []).filter(
    (send) => (send.state === 'taken_back' || send.state === 'failed') && send.warning !== null,
  )
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
  /* THE PRESS KEEPS ITS WORDS WHILE IT RUNS (round 9, D118: a press changes what is on the
     screen, never where the rest of it is). Its label named the live copies on two lines at a
     phone width and became one short line under the finger, so the sticky bar shrank and the
     press moved. `busy` draws the spinner on it; what the press is doing is said to a screen
     reader beside it, in a status that takes no room. */
  const doing = phase === 'waiting' ? 'Saving your prices…' : phase === 'sending' || running ? 'Checking TCGplayer, then sending…' : ''
  const label =
    liveMoves.length > 0
          ? /* THE LIVE COPIES THE PRESS MOVES ARE NAMED ON IT (the owner's ruling, round 7):
               "Send 1 copy, 2 live copies move to $19.99". */
            (
              <>
                {`Send ${carried(copies ?? 0, priceChanges.length)}, `}
                <MovesPhrase moves={liveMoves} />
              </>
            )
          : priceChanges.length > 0
            ? `Send ${carried(copies ?? 0, priceChanges.length)}`
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
        <span className="bn-sr" role="status">
          {doing}
        </span>
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

      <MovesList moves={liveMoves} />

      {offered.length > 0 ? (
        <ResendPrices rows={offered} busy={busy} onSend={() => resend(offered)} />
      ) : failure === null ? null : RETRYABLE.has(failure.code) ? (
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
          {sent !== null && sent.stamp === standing.stamp ? <PricesLeft send={standing} /> : null}
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
