import { useCallback, useEffect, useRef, useState } from 'react'

import { describeFailure, getSubmissions, releaseSubmission, type Failure } from './server'
import type { SubmissionClaim } from './types'
import { Button, Notice, Pill } from './kit'
import { toast } from './kit/toast'
import './SubmissionClaims.css'

/* WHAT IS HELD RIGHT NOW, AND THE ONE WAY OUT OF A STUCK CLAIM (D174).
 *
 * WHY THIS IS A PANEL ON `#/runs` AND NOT A SCREEN. A claim exists only between a press and
 * the collection it paid for, so on a healthy store there is nothing here at all — this
 * component draws NOTHING when no claim is live, which is the state it is in almost always. A
 * route for that would be a nav item leading to an empty page. It belongs on `#/runs` because
 * that is where the press that makes a claim lives and where the run holding one is watched:
 * the refusal an operator meets says "watch that run, or release its claim", and both of those
 * are one screen.
 *
 * THE FREE COUNT COMES BEFORE THE CONTROL THAT FIRES, which is the box photo reclaim's shape
 * (D89) and the listing release's before it. `getSubmissions` is a read that holds nothing,
 * and the release button does not exist until it has answered — so the receipt, the run, the
 * card count and whether the holder is still alive are all on screen before anything can be
 * pressed.
 *
 * A LIVE HOLDER IS NOT OFFERED A RELEASE. Releasing a claim whose run is still submitting
 * re-opens those cards to a second press, and that press is the double invoice the claim
 * exists to prevent. So the button is only drawn for a claim whose holder is GONE, and a live
 * one says what to do instead: watch the run. That is not a disabled control with a tooltip —
 * the action genuinely does not apply, and D50's `not-allowed` cursor is for a control that
 * exists and cannot be used right now.
 */

/** How long between polls while a claim is live. The run list beside this polls at 4s; a
 *  claim changes at most twice in a run's life — once when it is made, once when the answers
 *  are banked — so this is deliberately slower and stops entirely when nothing is held. */
const POLL_MS = 8000

function started(stamp: string): string {
  const at = new Date(stamp)
  return Number.isNaN(at.getTime()) ? stamp : at.toLocaleTimeString()
}

function cardCount(n: number): string {
  return `${n} card${n === 1 ? '' : 's'}`
}

export function SubmissionClaims() {
  const [claims, setClaims] = useState<readonly SubmissionClaim[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [releasing, setReleasing] = useState<string | null>(null)
  /** Receipts this session has released, whose ROW IS STILL DRAWN (D118).
   *
   *  A PRESS CHANGES WHAT IS ON THE SCREEN AND NEVER WHERE THE REST OF IT IS. Adopting the
   *  server's post-release list straight away removes the row, the panel shrinks, and
   *  everything below it jumps — MEASURED at 156px over 25 elements, with the page 60px
   *  shorter, which is precisely the harm that floor was written for. So the row stays where
   *  it is and its action slot becomes its own receipt (D57's shape: the control becomes the
   *  way back), and the poll below drops it a beat later, away from the finger. */
  const [released, setReleased] = useState<ReadonlySet<string>>(() => new Set())

  /** Whether a read has EVER landed, in a ref rather than derived from `claims`.
   *
   *  IT IS A REF SO THAT `read` BELOW CAN DECLARE `[]` AND MEAN IT. Asking `claims === null`
   *  instead put `claims` in that callback's dependency list, which made `read` a new function
   *  on every answer, which made the mount effect need an `exhaustive-deps` disable to avoid
   *  refetching on every render. `app/eslint.config.js` argues that a guard disabled inline is
   *  one the next person disables without reading, so the dependency is removed rather than
   *  the warning. */
  const everLoaded = useRef(false)

  const read = useCallback(async () => {
    try {
      const answer = await getSubmissions()
      everLoaded.current = true
      setClaims(answer.claims)
      setFailure(null)
    } catch (err) {
      /* A claims read that fails is NOT drawn as a page failure. The run list next to this
         says the server is unreachable once, and a second statement of it here would be the
         same fault reported twice — `Runs.tsx` records that rule for the page. What this does
         instead is hold the last list it had, so a dropped poll cannot make a live claim
         vanish off the screen. Watched for real: the panel held both claims through a server
         restart while the run list reported unreachable. */
      if (!everLoaded.current) setFailure(describeFailure(err))
    }
  }, [])

  useEffect(() => {
    let live = true
    void (async () => {
      if (live) await read()
    })()
    return () => {
      live = false
    }
  }, [read])

  useEffect(() => {
    /* THE POLL STOPS WHEN NOTHING IS HELD, which is the ordinary state. A timer running
       forever against a route that answers an empty list on a healthy store is the kind of
       cost nobody notices and nobody needs. */
    if (claims === null || claims.length === 0) return
    const timer = window.setInterval(() => void read(), POLL_MS)
    return () => window.clearInterval(timer)
  }, [claims, read])

  useEffect(() => {
    /* A RECEIPT FOR A ROW THAT HAS GONE IS A LEAK. Once the poll's answer no longer carries a
       receipt, its mark has nothing to describe — and keeping it would mean a later claim
       reusing that receipt drew as released. Receipts are unique, so this is hygiene rather
       than a correctness fix; the set is pruned because an ever-growing one in a panel that
       lives as long as the screen does is how a leak starts. */
    if (claims === null) return
    setReleased((held) => {
      if (held.size === 0) return held
      const live = new Set(claims.map((claim) => claim.receipt))
      const kept = new Set([...held].filter((receipt) => live.has(receipt)))
      return kept.size === held.size ? held : kept
    })
  }, [claims])

  const release = useCallback(
    async (claim: SubmissionClaim) => {
      setReleasing(claim.receipt)
      try {
        const answer = await releaseSubmission(claim.receipt)
        /* `answer.claims` IS DELIBERATELY NOT ADOPTED HERE. It is the correct list and it is
           the list this row has left — adopting it is what moved the page 156px under the
           operator's finger. The row is marked instead, and the next poll takes the server's
           answer whole. */
        setReleased((held) => new Set(held).add(claim.receipt))
        /* A RECEIPT, BECAUSE A RELEASE IS A WRITE WITH A FIGURE ON IT. `released: false` is
           the already-released answer and is a status rather than a receipt — nothing
           happened, so there is nothing to account for. */
        toast(
          answer.released
            ? {
                kind: 'receipt',
                title: `Released ${cardCount(answer.cards)}`,
                body: `${answer.run ?? answer.receipt} no longer holds them. Another send may buy them now.`,
                icon: 'unlock',
              }
            : {
                kind: 'status',
                title: `${answer.run ?? answer.receipt} was already released`,
              },
        )
      } catch (err) {
        toast({ kind: 'refusal', title: 'That claim was not released', body: describeFailure(err).message })
        // A refused release leaves the list as it was, so re-read rather than guess: the most
        // likely cause is a stale screen, and the list is what says so.
        await read()
      } finally {
        setReleasing(null)
      }
    },
    [read],
  )

  if (failure !== null && claims === null) return null
  if (claims === null || claims.length === 0) return null

  /* THE FIGURES COUNT WHAT IS STILL HELD, never the rows on screen. A row kept for its
     receipt is not holding anything any more, and a headline that counted it would overstate
     what is locked at the one moment the operator is watching it fall. */
  const standing = claims.filter((claim) => !released.has(claim.receipt))
  const stale = standing.filter((claim) => !claim.holder_alive)
  const held = standing.reduce((sum, claim) => sum + claim.cards, 0)
  /* THE NOTICE IS DRAWN OFF THE ROWS ON SCREEN, NOT OFF THE FIGURES, and that is the same
     rule as the row's own receipt one register up (D118). Basing it on `stale` unmounted it
     the instant the press landed and moved everything below the panel 75px — the notice is
     about 75px tall. Its sentence stays TRUE of a just-released row, because that row's
     holder is still gone; what has changed is that its cards are no longer held, which is
     what the headline figure says. So the block leaves on the same poll that removes the row,
     away from the finger. */
  const staleDrawn = claims.filter((claim) => !claim.holder_alive)

  return (
    <section className="claims bn-panel" aria-labelledby="claims-heading">
      <header className="claims-head">
        <h2 className="claims-title" id="claims-heading">
          Cards claimed by a live send
        </h2>
        {/* THE WORK, ON THE SCREEN. The count of rows and the count of CARDS are different
            facts and both are worth seeing: one claim over four hundred cards and four claims
            over one card each are the same row count and completely different situations. */}
        <Pill tone={stale.length > 0 ? 'warn' : 'accent'} icon="lock">
          {cardCount(held)} held by {standing.length} send{standing.length === 1 ? '' : 's'}
        </Pill>
      </header>

      <p className="claims-lede">
        A send holds the cards it is paying to read until its answers are banked, so a second
        press over the same card is refused rather than billed twice. These clear themselves
        when the run finishes.
      </p>

      {staleDrawn.length > 0 ? (
        <Notice tone="warn">
          {staleDrawn.length === 1
            ? 'One of these sends is'
            : `${staleDrawn.length} of these sends are`}{' '}
          no longer running. Its cards stay held on purpose: a send that was killed after it
          submitted has already been billed, and the answers keep for 29 days. Watch that run
          first — releasing it lets another press buy those cards again.
        </Notice>
      ) : null}

      <ul className="claims-list bn-list">
        {claims.map((claim) => (
          <li className="claims-row" key={claim.receipt}>
            <div className="claims-what">
              <span className="claims-who">{claim.run ?? 'Starting up'}</span>
              <span className="claims-meta">
                {cardCount(claim.cards)} · started {started(claim.started_at)}
              </span>
              {/* Enough of the positions to recognise which selection this is — two or three
                  is what tells a double-click from a drawer you had forgotten about. */}
              <span className="claims-sample">
                {claim.sample.join(', ')}
                {claim.cards > claim.sample.length ? ` and ${claim.cards - claim.sample.length} more` : ''}
              </span>
            </div>
            <div className="claims-act">
              {released.has(claim.receipt) ? (
                /* THE CONTROL BECAME ITS OWN RESULT, in the slot it stood in (D57). The row
                   goes on the next poll, not under the finger. */
                <Pill tone="ok" icon="check">
                  Released {cardCount(claim.cards)}
                </Pill>
              ) : claim.holder_alive ? (
                <Pill tone="live" icon="zap">
                  Running
                </Pill>
              ) : (
                <>
                  <Pill tone="warn" icon="alert">
                    Holder gone
                  </Pill>
                  <Button
                    variant="danger"
                    icon="unlock"
                    onClick={() => void release(claim)}
                    disabled={releasing !== null}
                    busy={releasing === claim.receipt}
                  >
                    Release {cardCount(claim.cards)}
                  </Button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
      <p className="claims-receipt">
        {/* THE RECEIPT, ON SCREEN. It is what the release takes and what both refusals name,
            so it is the one string that joins this panel to the sentence an operator met. */}
        Receipts: {claims.map((claim) => claim.receipt).join(', ')}
      </p>
    </section>
  )
}
