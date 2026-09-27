import { useCallback, useEffect, useRef, useState } from 'react'

import { describeFailure, rescueRun, type Failure } from './server'
import type { RescueResult } from './types'
import { Button, Notice, Sheet, Stat } from './kit'
import { toast } from './kit/toast'
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
  not_stranded: 'This run’s box is back, so there is nothing to rebind.',
  no_identifications: 'This run has no card readings to rebind.',
  none_on_shelf: 'None of this run’s cards are in a box now. They have left the store.',
  spread_across_boxes: 'This run’s cards are now in more than one box, so nothing was rebound.',
  digest_ambiguous_on_disk: 'Two photographs could match the same card, so nothing was rebound.',
  digest_twice_in_run: 'Two records in this run point at the same photograph, so nothing was rebound.',
}

function reasonSentence(reason: RescueResult['reason']): string {
  return reason === null ? 'The rebind did not run.' : REASON_COPY[reason]
}

function destinationLabel(destination: RescueResult['destination']): string {
  if (destination === null) return 'another box'
  const named = destination.box_name?.trim()
  return named ? `${named} (Box ${destination.box})` : `Box ${destination.box}`
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

  const applyable = result !== null && result.ok && !result.wrote && result.already_rescued === null && result.counts.rebound > 0

  /* THE KIT'S OWN SHEET (D275). Nothing closes it while the preview or the rebind is in
     flight, so a write is never hidden. */
  return (
    <Sheet
      open={open}
      onClose={onClose}
      dismissible={!busy}
      title="Rebind this run"
      icon="moveTo"
      className="rescue-sheet"
      footer={
        applyable ? (
          <Button variant="primary" icon="check" busy={busy} onClick={() => void send(true)}>
            Rebind these cards
          </Button>
        ) : null
      }
    >
        <div className="rescue-sheet-body">
          <p className="rescue-sheet-says">
            This run’s box was deleted. If its cards are now in another box, they can be found
            there as a new run. This check is free. <strong>This run is never changed.</strong>
          </p>

          {!busy ? null : (
            <p className="rescue-sheet-status" role="status">
              <span className="bn-dot bn-dot-accent" />
              {result === null ? 'Looking for these cards in your boxes…' : 'Rebinding…'}
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
                <Stat value={result.counts.rebound} label="Found in a box" />
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
    </Sheet>
  )
}
