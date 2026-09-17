import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { describeFailure, rescueRun, type Failure } from './server'
import type { RescueResult } from './types'
import { Button, Notice, Stat } from './kit'
import { toast } from './kit/toast'
import { useOverlayFocus } from './runsOverlay'
import './RunRescue.css'

/* D165's repair, offered from the run it strands (D210). A rescue re-addresses
 * a stranded run's cards to the drawer they are actually in now, and writes that as a NEW run
 * — the source is never edited, so this sheet's own way back is always a link to it.
 *
 * NO RAW MACHINE TEXT ANYWHERE IN THIS FILE, on the owner's ruling of 2026-09-13. Every other
 * free step's sheet (`QueueRefresh`, `LiveReconcile`) shows the command's own stdout in a
 * `LogWell`; `rescueRun`'s answer carries no `console` at all, and every sentence below is
 * composed from `RescueResult`'s typed fields — the reason CODES translated by `REASON_COPY`,
 * never the CLI's own words. The raw report is on disk, named by `RescueResult.log`, and
 * nothing here reads it. */

const REASON_COPY: Record<NonNullable<RescueResult['reason']>, string> = {
  not_stranded: 'This run’s drawer is live again — there is nothing here to rebind.',
  no_identifications: 'This run has no card readings to rebind.',
  none_on_shelf: 'None of this run’s cards are still on a shelf — they have already left the store.',
  spread_across_boxes: 'This run’s cards are now spread across more than one drawer, so nothing was rebound.',
  digest_ambiguous_on_disk: 'Two photographs on the shelf could match the same card, so nothing was rebound.',
  digest_twice_in_run: 'Two records in this run point at the same photograph, so nothing was rebound.',
}

function reasonSentence(reason: RescueResult['reason']): string {
  return reason === null ? 'The rebind did not run.' : REASON_COPY[reason]
}

function destinationLabel(destination: RescueResult['destination']): string {
  if (destination === null) return 'another drawer'
  const named = destination.box_name?.trim()
  return named ? `Box ${destination.box} · ${named}` : `Box ${destination.box}`
}

export function RunRescue({
  open,
  onClose,
  run,
  onOpenRun,
}: {
  readonly open: boolean
  readonly onClose: () => void
  /** The stranded run's own name — never edited by any press in here. */
  readonly run: string
  /** Jumps the panel to a run by name, with no route change (D118). */
  readonly onOpenRun: (name: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<RescueResult | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const sheet = useRef<HTMLElement | null>(null)

  const send = useCallback(
    async (write: boolean) => {
      setBusy(true)
      setFailure(null)
      try {
        const answer = await rescueRun(run, { write })
        setResult(answer)
        if (answer.wrote) {
          toast({
            kind: 'ok',
            title: 'The cards were rebound',
            body: `${answer.counts.rebound} card${answer.counts.rebound === 1 ? '' : 's'} now in ${destinationLabel(answer.destination)}.`,
          })
        }
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [run],
  )

  /* The preview, on opening, once — the same ref-guarded shape `QueueRefresh` uses so
     StrictMode's second mount does not send it twice. Reopening takes a fresh reading: the
     shelf may have changed since the sheet was last open. */
  const asked = useRef(false)
  useEffect(() => {
    if (!open) {
      asked.current = false
      return
    }
    if (asked.current) return
    asked.current = true
    setResult(null)
    setFailure(null)
    void send(false)
  }, [open, send])

  useOverlayFocus(sheet, open, onClose, busy)

  const applyable = result !== null && result.ok && !result.wrote && result.already_rescued === null && result.counts.rebound > 0

  return createPortal(
    <>
      {open ? <div className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet rescue-sheet"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="rescue-sheet-head"
        tabIndex={-1}
      >
        <header className="rescue-sheet-top">
          <div className="rescue-sheet-heading">
            <span className="bn-eyebrow">This run · free</span>
            <h2 className="rescue-sheet-head" id="rescue-sheet-head">
              Rebind this run
            </h2>
          </div>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="rescue-sheet-body">
          <p className="rescue-sheet-says">
            The drawer this run was over has since been deleted and its number given to another
            drawer. If this run’s cards are sitting somewhere else on a shelf, they can be
            re-addressed there — as a new run. <strong>This run is never changed.</strong>
          </p>

          {!busy ? null : (
            <p className="rescue-sheet-status" role="status">
              <span className="bn-dot bn-dot-accent" />
              {result === null ? 'Looking for these cards on a shelf…' : 'Rebinding…'}
            </p>
          )}

          {failure === null ? null : (
            <Notice tone="danger" title="The rebind did not run, and nothing was written" code={failure.code}>
              {failure.message}
            </Notice>
          )}

          {result === null || failure !== null ? null : !result.ok ? (
            <Notice tone="danger" title="Nothing to rebind">
              {reasonSentence(result.reason)}
            </Notice>
          ) : result.already_rescued !== null ? (
            <div className="bn-receipt rescue-receipt">
              <span className="rescue-receipt-said">
                Already rebound — {result.counts.rebound} card{result.counts.rebound === 1 ? '' : 's'} in{' '}
                {destinationLabel(result.destination)}.
              </span>
              <Button size="sm" onClick={() => onOpenRun(result.already_rescued as string)}>
                Open that run
              </Button>
            </div>
          ) : result.wrote ? (
            <div className="bn-receipt rescue-receipt">
              <span className="rescue-receipt-said">
                {result.counts.rebound} card{result.counts.rebound === 1 ? '' : 's'} rebound into{' '}
                {destinationLabel(result.destination)}.
              </span>
              <Button size="sm" onClick={() => onOpenRun(result.new_run as string)}>
                Open the new run
              </Button>
            </div>
          ) : (
            <>
              <div className="rescue-sheet-figures">
                <Stat value={result.counts.rebound} label="Found on a shelf" />
                <Stat value={result.counts.not_on_shelf} label="Left the store" />
                {result.counts.ambiguous > 0 ? <Stat value={result.counts.ambiguous} label="Could not be told apart" /> : null}
              </div>
              <p className="rescue-sheet-says">
                {result.counts.rebound > 0 ? (
                  <>
                    All in <strong>{destinationLabel(result.destination)}</strong>.
                  </>
                ) : (
                  'Nothing here can be rebound.'
                )}
              </p>
            </>
          )}
        </div>

        <footer className="rescue-sheet-foot">
          {applyable ? (
            <Button variant="primary" icon="check" busy={busy} onClick={() => void send(true)}>
              Rebind these cards
            </Button>
          ) : null}
        </footer>
      </aside>
    </>,
    document.body,
  )
}
