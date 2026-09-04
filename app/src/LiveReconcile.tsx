import { useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { describeFailure, reconcileLive, type Failure } from './server'
import { readUpload } from './csvUpload'
import { Button, Icon, Notice } from './kit'
import { toast } from './kit/toast'
import { DropZone } from './RunsDrop'
import { whenLabel } from './RunsStage'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import './LiveReconcile.css'

/* THE FOURTH COMMAND, OVER THE WHOLE STORE (D87), as a sheet off the Runs header.
 *
 * Not run-scoped, and drawn apart from the runs because of it: it settles the live
 * quantities `pipeline/join.py`'s cap arithmetic reads, over every SKU at once, against one
 * live export — TCGplayer's My Pricing. Two presses, and the first writes nothing: the
 * preview is read, then the store is reconciled. The picked file is held so the second press
 * sends the same bytes the preview described. */
export function LiveReconcile({ open, onClose }: { readonly open: boolean; readonly onClose: () => void }) {
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<string | null>(null)
  const [wrote, setWrote] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)

  /* HOW OLD THE STORE'S `live` READING IS. A live figure drawn with no age reads as a fact
     about the marketplace when it is a fact about the last time the store looked, and this
     sheet is where that look happens — so it is where the age is said.
     THE STORE'S OWN READING TIME IS NOT ON THE WIRE on this branch: the field will be
     `live_read_at` on `POST /pipeline/reconcile-live`'s answer. Until it lands, the only
     reading this screen can date honestly is one it just took. */
  const [readAt, setReadAt] = useState<string | null>(null)
  const held = useRef<Awaited<ReturnType<typeof readUpload>> | null>(null)
  const sheet = useRef<HTMLElement | null>(null)

  const send = useCallback(async (write: boolean) => {
    const file = held.current
    if (file === null) return
    setBusy(true)
    setFailure(null)
    try {
      const answer = await reconcileLive(file, { write })
      setReport(answer.console)
      setWrote(answer.wrote)
      if (answer.wrote) {
        setReadAt(new Date().toISOString())
        toast({ kind: 'ok', title: 'Store reconciled', body: 'Live quantities written for every SKU in the store.' })
      }
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [])

  const take = useCallback(
    (files: File[]) => {
      const file = files[0]
      if (file === undefined) return
      setReport(null)
      setWrote(false)
      setFailure(null)
      setFileName(file.name)
      void readUpload(file)
        .then((upload) => {
          held.current = upload
          return send(false)
        })
        .catch((err) => setFailure(describeFailure(err)))
    },
    [send],
  )

  /* Focus lands inside on open, stays inside under Tab, and returns to the opener on close;
     Escape closes. */
  useOverlayFocus(sheet, open, onClose)

  /* Portalled to <body> for the same reason the composer is: `main.bn-page` keeps a filled
     transform after its enter animation, and a fixed sheet inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet livecheck"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="livecheck-head"
        tabIndex={-1}
      >
        <header className="livecheck-top">
          <div className="livecheck-heading">
            <span className="bn-eyebrow">Store-wide · free</span>
            <h2 className="livecheck-head" id="livecheck-head">
              Reconcile the whole store
            </h2>
          </div>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="livecheck-body">
          <p className="livecheck-says">
            One live export — TCGplayer&rsquo;s <strong>My Pricing</strong>, all printings — against every
            SKU in the store, whatever run or box it came from. It reports both directions: copies this
            pipeline sent that TCGplayer no longer holds, and SKUs it holds that were never sent from
            here. It moves quantities and marks no card sold.
          </p>

          <p className="livecheck-age">
            <Icon name="clock" size={14} />
            <span>
              Every <strong>live</strong> figure in the store is only as current as the last time this ran
              {readAt === null ? '.' : ` — read ${whenLabel(readAt)}.`}
            </span>
          </p>

          <div className="livecheck-pick">
            <DropZone
              title="Drop the My Pricing export here"
              hint="or click to choose the .csv"
              fileName={fileName}
              disabled={busy}
              onFiles={take}
            />
          </div>

          {busy && report === null ? (
            <p className="livecheck-status" role="status">
              <span className="bn-dot bn-dot-accent" /> Comparing the export with the store…
            </p>
          ) : null}

          {failure === null ? null : (
            <Notice tone="danger" code={failure.code}>
              {failure.message}
            </Notice>
          )}

          {report === null ? null : (
            <>
              {wrote ? (
                <Notice tone="ok" title="Reconciled">
                  The live quantities are written, and every one of them is now a reading taken just now.
                  Nothing was marked sold.
                </Notice>
              ) : (
                <Notice tone="info" title="Preview — nothing written yet">
                  Read what would move, then reconcile the store below.
                </Notice>
              )}
              <LogWell
                text={report}
                label={wrote ? 'What the reconcile printed' : 'What the preview printed'}
                className="livecheck-console"
                maxHeight={420}
              />
            </>
          )}
        </div>

        {report === null || wrote ? null : (
          /* Absent until the preview has answered: the control that settles does not exist
             before there is anything to read. */
          <footer className="livecheck-foot">
            <Button variant="ghost" onClick={onClose}>
              Not now
            </Button>
            <Button variant="primary" icon="check" busy={busy} disabled={busy} onClick={() => void send(true)}>
              Reconcile the store
            </Button>
          </footer>
        )}
      </aside>
    </>,
    document.body,
  )
}
