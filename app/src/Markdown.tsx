import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import {
  applyMarkdown,
  describeFailure,
  getMarkdowns,
  markdownFileUrl,
  markdownListings,
  type Failure,
} from './server'
import { readUpload } from './csvUpload'
import type { CsvUpload, MarkdownAnswer, MarkdownSummary } from './types'
import { Button, Icon, Notice } from './kit'
import { toast } from './kit/toast'
import { DropZone, FileButton } from './RunsDrop'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import './Runs.css'

/* THE STALE-LISTING MARKDOWN (D100), as a sheet off the Runs header — the second one, beside
 * the store-wide reconcile it is a sibling of.
 *
 * A SHEET AND NOT A ROUTE, WHICH IS NOW A JUDGEMENT RATHER THAN A CAPACITY REFUSAL. D100 was
 * argued against a shell that drew its nav as one horizontal strip and could not hold an
 * eleventh link at 1,440px; D95 replaced that with a sidebar, and `App.tsx`'s ROUTES table
 * carries this session's own re-measurement of what a tenth link would cost there. The reason
 * it stays here is the one that was always the better half of D100's argument: this and the
 * store-wide reconcile read the SAME FILE — TCGplayer's My Pricing export — and the order is
 * the order of the work. Settle what TCGplayer holds, then decide about the part of it that
 * is not moving.
 *
 * THREE STEPS, AND EACH PRESS IS ABSENT UNTIL THE ONE BEFORE IT HAS ANSWERED. D33's rule for
 * the control that spends, applied to the one that publishes prices: a button that exists
 * before there is anything to read is a button pressed before anything was read. The footer
 * carries whichever of the three is next, which is `LiveReconcile`'s footer generalised — it
 * has one step and this has three.
 *
 *   1. Upload the My Pricing export. Free, writes nothing, reports what would move.
 *   2. Write the worklist. A file, on this machine, uploaded nowhere.
 *   3. Hand the worklist back — edited in a spreadsheet, or untouched — and write the import
 *      CSV. That is the file the operator uploads to TCGplayer.
 *
 * THE STDOUT IS THE RECEIPT (D33), and it is in a `LogWell` rather than a bare `<pre>` so it
 * folds, counts its lines and copies. Summarising the command's report here would be a second
 * opinion about which of its answers mattered, and the report's own header carries the one
 * sentence the operator must not be allowed to miss — that the age it measures is how long
 * the card has been OWNED and not how long it has been listed.
 */

const WORKLIST = 'worklist.csv'
const IMPORT = 'import.csv'

export function Markdown({ open, onClose }: { readonly open: boolean; readonly onClose: () => void }) {
  const [days, setDays] = useState('7')
  const [percent, setPercent] = useState('10')
  const [aboveMarket, setAboveMarket] = useState('')
  const [limit, setLimit] = useState('')
  const [again, setAgain] = useState(false)

  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [survey, setSurvey] = useState<MarkdownAnswer | null>(null)
  const [applied, setApplied] = useState<MarkdownAnswer | null>(null)
  const [stamp, setStamp] = useState<string | null>(null)
  const [wroteImport, setWroteImport] = useState(false)
  const [history, setHistory] = useState<MarkdownSummary[]>([])

  /* WHAT WAS PICKED, IN STATE RATHER THAN OFF THE REF BELOW. The drop zone draws the file's
     name and the re-read control only exists once there is a file to re-read; a ref answers
     neither question, because writing one renders nothing. */
  const [exportName, setExportName] = useState<string | null>(null)
  const [worklistName, setWorklistName] = useState<string | null>(null)

  /* THE EXPORT IS HELD SO THE SECOND PRESS SENDS THE SAME BYTES, which is `LiveReconcile`'s
     rule and matters more here: the preview the operator read and the worklist the write
     produces have to describe one file, or the numbers on the screen were about something
     else. */
  const held = useRef<CsvUpload | null>(null)
  const edited = useRef<CsvUpload | null>(null)
  const sheet = useRef<HTMLElement | null>(null)

  const refresh = useCallback(() => {
    void getMarkdowns()
      .then((answer) => setHistory(answer.markdowns))
      .catch(() => setHistory([]))
  }, [])

  useEffect(refresh, [refresh])

  const ask = useCallback(() => {
    const options: Record<string, unknown> = {}
    if (days.trim() !== '') options.days = Number(days)
    if (percent.trim() !== '') options.percent = percent.trim()
    if (aboveMarket.trim() !== '') options.above_market = aboveMarket.trim()
    if (limit.trim() !== '') options.limit = Number(limit)
    if (again) options.again = true
    return options
  }, [days, percent, aboveMarket, limit, again])

  const read = useCallback(
    async (write: boolean) => {
      const file = held.current
      if (file === null) return
      setBusy(true)
      setFailure(null)
      try {
        const answer = await markdownListings(file, { ...ask(), write })
        setSurvey(answer)
        if (answer.wrote && answer.stamp !== null) {
          setStamp(answer.stamp)
          setApplied(null)
          setWroteImport(false)
          setWorklistName(null)
          edited.current = null
          refresh()
          toast({
            kind: 'ok',
            title: 'Worklist written',
            body: 'On this machine only. Nothing has been uploaded and no price has moved.',
          })
        }
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [ask, refresh],
  )

  const apply = useCallback(
    async (write: boolean) => {
      if (stamp === null) return
      setBusy(true)
      setFailure(null)
      try {
        const answer = await applyMarkdown(stamp, {
          worklist: edited.current ?? undefined,
          write,
        })
        setApplied(answer)
        if (answer.wrote) {
          setWroteImport(true)
          refresh()
          toast({
            kind: 'ok',
            title: 'Import CSV written',
            body: 'Price only — every row carries Add to Quantity 0, so uploading it twice changes nothing.',
          })
        }
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [refresh, stamp],
  )

  /* Picking an export starts over: a survey about one file and a worklist written from
     another is the straddle this whole sheet is arranged to prevent. */
  const takeExport = useCallback(
    (files: File[]) => {
      const file = files[0]
      if (file === undefined) return
      setSurvey(null)
      setApplied(null)
      setStamp(null)
      setWroteImport(false)
      setFailure(null)
      setExportName(file.name)
      setWorklistName(null)
      edited.current = null
      void readUpload(file)
        .then((upload) => {
          held.current = upload
          return read(false)
        })
        .catch((err) => setFailure(describeFailure(err)))
    },
    [read],
  )

  const takeWorklist = useCallback(
    (files: File[]) => {
      const file = files[0]
      if (file === undefined) return
      setApplied(null)
      setWroteImport(false)
      setFailure(null)
      setWorklistName(file.name)
      void readUpload(file)
        .then((upload) => {
          edited.current = upload
          return apply(false)
        })
        .catch((err) => setFailure(describeFailure(err)))
    },
    [apply],
  )

  /* Focus lands inside on open, stays inside under Tab, and returns to the opener on close;
     Escape closes. The same hook the composer and the store-wide reconcile use. */
  useOverlayFocus(sheet, open, onClose)

  /* WHICH PRESS IS NEXT — the footer's whole content, and three absences rather than three
     disabled buttons (D33). Each is unreachable until the read before it has answered. */
  const nextPress =
    survey !== null && stamp === null
      ? 'worklist'
      : stamp !== null && applied === null
        ? 'check'
        : applied !== null && !wroteImport
          ? 'import'
          : null

  /* Portalled to <body> for the same reason the composer and the reconcile sheet are:
     `main.bn-page` keeps a filled transform after its enter animation, and a fixed sheet
     inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet runs-md"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="runs-md-head"
        tabIndex={-1}
      >
        <header className="runs-md-top">
          <div className="runs-md-heading">
            <span className="bn-eyebrow">Store-wide · free</span>
            <h2 className="runs-md-head" id="runs-md-head">
              Mark down what is not selling
            </h2>
          </div>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="runs-md-body">
          <p className="runs-md-says">
            One live export — TCGplayer&rsquo;s <strong>My Pricing</strong> — read for the listings
            TCGplayer says are live, that no copy has sold from here inside the window, and that this
            store has held for longer than the window. It reports what each would be re-priced to,
            writes a worklist you can edit, and turns that back into an import CSV you upload.
          </p>
          <p className="runs-md-says">
            <strong>Nothing is ever deleted at TCGplayer to lower a price.</strong> The upload edits
            the live listing in place, and every row of every file written here carries{' '}
            <code className="bn-code">Add to Quantity</code> of 0 — so uploading one of them twice
            changes nothing the second time, which is not true of an import from{' '}
            <code className="bn-code">emit</code>.
          </p>

          <p className="runs-md-caveat">
            <Icon name="clock" size={14} />
            <span>
              The age this ranks on is how long the card has been <strong>owned</strong>, not how long
              the listing has been live. The store cannot measure the second one. Read it as a floor.
            </span>
          </p>

          <section className="runs-md-step" aria-labelledby="runs-md-ask">
            <h3 className="bn-section-title" id="runs-md-ask">
              1 · What counts as stale
            </h3>
            <div className="runs-md-fields">
              <label className="bn-field">
                <span className="bn-field-label">Window, days</span>
                <input
                  className="bn-input"
                  type="number"
                  min="0"
                  value={days}
                  onChange={(event) => setDays(event.currentTarget.value)}
                />
              </label>
              <label className="bn-field">
                <span className="bn-field-label">Cut, percent</span>
                <input
                  className="bn-input"
                  type="number"
                  min="0"
                  max="99"
                  value={percent}
                  onChange={(event) => setPercent(event.currentTarget.value)}
                />
              </label>
              <label className="bn-field">
                <span className="bn-field-label">Only above market by</span>
                <input
                  className="bn-input"
                  type="number"
                  min="0"
                  placeholder="any"
                  value={aboveMarket}
                  onChange={(event) => setAboveMarket(event.currentTarget.value)}
                />
              </label>
              <label className="bn-field">
                <span className="bn-field-label">Take at most</span>
                <input
                  className="bn-input"
                  type="number"
                  min="0"
                  placeholder="all"
                  value={limit}
                  onChange={(event) => setLimit(event.currentTarget.value)}
                />
              </label>
            </div>
            <label className="bn-check">
              <input
                type="checkbox"
                checked={again}
                onChange={(event) => setAgain(event.currentTarget.checked)}
              />
              <span>Mark down again inside the window</span>
            </label>

            <DropZone
              title="Drop the My Pricing export here"
              hint="or click to choose the .csv"
              fileName={exportName}
              disabled={busy}
              onFiles={takeExport}
            />
            {exportName === null ? null : (
              /* NOT A FILE PICKER: the bytes are already held, and this re-asks the same file
                 with whatever the four fields above now say. Re-picking would let the answer
                 and the numbers that produced it come from two different reads. */
              <Button
                variant="ghost"
                icon="refresh"
                busy={busy}
                disabled={busy}
                onClick={() => void read(false)}
              >
                Read it again with these numbers
              </Button>
            )}
          </section>

          {busy && survey === null ? (
            <p className="runs-md-status" role="status">
              <span className="bn-dot bn-dot-accent" /> Reading the export against the store…
            </p>
          ) : null}

          {failure === null ? null : (
            <Notice tone="danger" code={failure.code}>
              {failure.message}
            </Notice>
          )}

          {survey === null ? null : (
            <>
              <LogWell
                text={survey.console}
                label={stamp === null ? 'What the survey printed' : 'What the worklist write printed'}
                className="runs-md-console"
                maxHeight={420}
              />

              <section className="runs-md-step" aria-labelledby="runs-md-worklist">
                <h3 className="bn-section-title" id="runs-md-worklist">
                  2 · The worklist
                </h3>
                {stamp === null ? (
                  <p className="runs-md-says">
                    The press below writes the rows above into a CSV on this machine. It is uploaded
                    nowhere and it changes no price anywhere until you say so.
                  </p>
                ) : (
                  <>
                    <Notice tone="ok" title="Written, and uploaded nowhere">
                      Edit its <code className="bn-code">TCG Marketplace Price</code> column, or hand it
                      straight back — a price is already proposed on every row. Only the SKU and the
                      price are read back; every other byte comes from the export.
                    </Notice>
                    <div className="runs-md-row">
                      <a className="bn-btn" href={markdownFileUrl(stamp, WORKLIST)} download={WORKLIST}>
                        <Icon name="download" size={16} />
                        {WORKLIST}
                      </a>
                      <span className="bn-mono runs-md-stamp">{stamp}</span>
                    </div>
                  </>
                )}
              </section>
            </>
          )}

          {stamp === null ? null : (
            <section className="runs-md-step" aria-labelledby="runs-md-apply">
              <h3 className="bn-section-title" id="runs-md-apply">
                3 · The upload
              </h3>
              <div className="runs-md-row">
                <FileButton
                  label={worklistName ?? 'Hand the worklist back'}
                  icon="upload"
                  disabled={busy}
                  onFiles={takeWorklist}
                />
                <span className="runs-md-hint">
                  Optional — leaving it means &ldquo;the one you wrote&rdquo;.
                </span>
              </div>

              {applied === null ? null : (
                <>
                  <LogWell
                    text={applied.console}
                    label={wroteImport ? 'What the write printed' : 'What the check printed'}
                    className="runs-md-console"
                    maxHeight={420}
                  />
                  {wroteImport ? (
                    <>
                      <Notice tone="ok" title="Ready to upload">
                        Upload this through TCGplayer&rsquo;s My Pricing. It carries{' '}
                        <code className="bn-code">Add to Quantity</code> of 0 on every row.
                      </Notice>
                      <div className="runs-md-row">
                        <a className="bn-btn" href={markdownFileUrl(stamp, IMPORT)} download={IMPORT}>
                          <Icon name="download" size={16} />
                          {IMPORT}
                        </a>
                      </div>
                    </>
                  ) : null}
                </>
              )}
            </section>
          )}

          {history.length === 0 ? null : (
            <section className="runs-md-step" aria-labelledby="runs-md-history">
              <h3 className="bn-section-title" id="runs-md-history">
                Earlier markdowns
              </h3>
              {/* WHAT THE DIRECTORY HOLDS, not a flag: whether the upload was ever written is
                  answered by `import.csv` being listed rather than by a boolean that could be
                  true of a file somebody deleted. */}
              <ul className="bn-list runs-md-history">
                {history.map((entry) => (
                  <li className="bn-list-row runs-md-history-row" key={entry.stamp}>
                    <span className="bn-mono runs-md-stamp">{entry.stamp}</span>
                    <span className="bn-muted bn-tnum">
                      {entry.skus} SKU{entry.skus === 1 ? '' : 's'}
                    </span>
                    <span className="runs-md-history-files">
                      {entry.files
                        .filter((name) => name === WORKLIST || name === IMPORT)
                        .map((name) => (
                          <a
                            className="bn-btn bn-btn-sm bn-btn-ghost"
                            download={name}
                            href={markdownFileUrl(entry.stamp, name)}
                            key={name}
                          >
                            <Icon name="download" size={14} />
                            {name}
                          </a>
                        ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <footer className="runs-md-foot">
          <Button variant="ghost" onClick={onClose}>
            {wroteImport ? 'Done' : 'Not now'}
          </Button>
          {nextPress === 'worklist' ? (
            <Button
              variant="primary"
              icon="download"
              busy={busy}
              disabled={busy || survey === null || !survey.ok}
              onClick={() => void read(true)}
            >
              Write the worklist
            </Button>
          ) : null}
          {nextPress === 'check' ? (
            <Button icon="eye" busy={busy} disabled={busy} onClick={() => void apply(false)}>
              Check it
            </Button>
          ) : null}
          {nextPress === 'import' ? (
            <Button
              variant="primary"
              icon="check"
              busy={busy}
              disabled={busy || applied === null || !applied.ok}
              onClick={() => void apply(true)}
            >
              Write the import CSV
            </Button>
          ) : null}
        </footer>
      </aside>
    </>,
    document.body,
  )
}
