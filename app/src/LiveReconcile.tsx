import { useCallback, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { describeFailure, fetchLiveExport, reconcileLive, type Failure } from './server'
import { readUpload } from './csvUpload'
import { Button, Icon, IconButton, Notice } from './kit'
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
  const scrim = useRef<HTMLDivElement | null>(null)
  /** The live export the SERVER holds, by name — the fetched counterpart to `held`'s bytes. */
  const fetchedName = useRef<string | null>(null)
  const [fetching, setFetching] = useState(false)

  const send = useCallback(async (write: boolean) => {
    const file = held.current
    const named = fetchedName.current
    /* ONE DOCUMENT, FROM WHICHEVER DOOR (D104) — the markdown sheet's rule, and the same
       reason: the preview the operator read and the write that follows must describe one
       reading, and a fetched file is the server's rather than this screen's. */
    if (file === null && named === null) return
    setBusy(true)
    setFailure(null)
    try {
      const answer = await reconcileLive(file, {
        write,
        ...(named === null ? {} : { fetched: named }),
      })
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
      fetchedName.current = null
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
     Escape closes, unless a read or a write is in flight — `busy` is the hold, and it covers
     both presses of the two-step gate. */
  useOverlayFocus(sheet, open, onClose, busy, scrim)

  /* Portalled to <body> for the same reason the composer is: `main.bn-page` keeps a filled
     transform after its enter animation, and a fixed sheet inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div ref={scrim} className="bn-scrim" onClick={onClose} /> : null}
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
            <span className="bn-eyebrow">
              <span>Store-wide</span>
              <span>free</span>
            </span>
            <h2 className="livecheck-head" id="livecheck-head">
              Check what is live
            </h2>
          </div>
          <IconButton icon="x" label="Close" onClick={onClose} />
        </header>

        <div className="livecheck-body">
          <p className="livecheck-says">
            Compares what TCGplayer holds with every card in the store. It marks no card sold.
          </p>

          <p className="livecheck-age">
            <Icon name="clock" size={14} />
            <span>{readAt === null ? 'Not checked yet.' : `Last checked ${whenLabel(readAt)}.`}</span>
          </p>

          {/* THE SAME DOCUMENT THE MARKDOWN SHEET FETCHES, AND THE SAME FILE (D104). An
              operator who marks down and then reconciles is acting on ONE reading rather than
              two downloads taken minutes apart — which matters here more than there, because
              this is the press that writes `live` for every SKU in the store. */}
          <div className="livecheck-fetch">
            <Button
              variant="primary"
              icon="download"
              busy={fetching}
              disabled={busy || fetching}
              onClick={() => {
                void (async () => {
                  setFetching(true)
                  setFailure(null)
                  try {
                    const answer = await fetchLiveExport()
                    held.current = null
                    fetchedName.current = answer.fetched
                    setFileName(answer.fetched)
                    await send(false)
                  } catch (err) {
                    setFailure(describeFailure(err))
                  } finally {
                    setFetching(false)
                  }
                })()
              }}
            >
              {fetching ? 'Asking TCGplayer…' : 'Fetch my live listings'}
            </Button>
          </div>

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
                <Notice tone="ok" title="The store now matches TCGplayer">
                  Nothing was marked sold.
                </Notice>
              ) : (
                <Notice tone="info" title="Preview — nothing written yet">
                  Read what would change, then press Match the store below.
                </Notice>
              )}
              <LogWell
                text={report}
                label={wrote ? 'What changed' : 'What would change'}
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
              Match the store
            </Button>
          </footer>
        )}
      </aside>
    </>,
    document.body,
  )
}
