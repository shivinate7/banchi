/* The stale-listing markdown, a section on `#/runs` (D100).
 *
 * IT WANTED A ROUTE AND DOES NOT FIT IN THE NAV, WHICH IS A MEASUREMENT AND NOT A PREFERENCE.
 * D49's precedent says a worklist the operator sits in earns a route, and this is one: three
 * presses, with a file leaving the machine in the middle of it and coming back. But the strip
 * needs 1,484.9px to draw eleven links on one row against the owner's 1,440 — the aside group
 * wraps, the nav doubles from 45.5px to 90px, and `app/tests/review.spec.ts`'s between-cards
 * floor goes red as the web font swaps in and tips the wrap mid-screen. No label rescues it:
 * the eleventh link would have to be 68px and `Runs` is 72.6. So the choice was this screen's
 * route or the shell's layout, and the shell is being rewritten on another branch.
 *
 * IT SITS BELOW THE STORE-WIDE RECONCILE, which is the right neighbour anyway: both read the
 * same file, and the order is the order of the work — settle what TCGplayer holds, then decide
 * about the part of it that is not moving.
 *
 * THREE STEPS, AND EACH CONTROL IS ABSENT UNTIL THE ONE BEFORE IT HAS ANSWERED. D33's rule
 * for the control that spends, applied to the one that publishes prices: a button that exists
 * before there is anything to read is a button pressed before anything was read.
 *
 *   1. Upload the My Pricing export. Free, writes nothing, reports what would move.
 *   2. Write the worklist. A file, on this machine, uploaded nowhere.
 *   3. Hand the worklist back — edited in a spreadsheet, or untouched — and write the
 *      import CSV. That is the file the operator uploads to TCGplayer.
 *
 * WRITTEN PLAINLY ON PURPOSE. A separate branch is rewriting every screen in this app into a
 * new design system; this is laid out to be legible and to be restyled, not to be admired.
 *
 * THE STDOUT IS THE RECEIPT (D33). Summarising the command's report here would be a second
 * opinion about which of its answers mattered, and the report's own header carries the one
 * sentence the operator must not be allowed to miss — that the age it measures is how long
 * the card has been OWNED and not how long it has been listed.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { readUpload } from './csvUpload'
import {
  applyMarkdown,
  describeFailure,
  getMarkdowns,
  markdownFileUrl,
  markdownListings,
} from './server'
import type { Failure } from './server'
import type { CsvUpload, MarkdownAnswer, MarkdownSummary } from './types'
import './Markdown.css'

const WORKLIST = 'worklist.csv'
const IMPORT = 'import.csv'

export function Markdown() {
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

  /* THE EXPORT IS HELD SO THE SECOND PRESS SENDS THE SAME BYTES, which is `LiveReconcile`'s
     rule and matters more here: the preview the operator read and the worklist the write
     produces have to describe one file, or the numbers on the screen were about something
     else. */
  const held = useRef<CsvUpload | null>(null)
  const edited = useRef<CsvUpload | null>(null)

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

  const survey_ = useCallback(
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
          edited.current = null
          refresh()
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
        }
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [refresh, stamp],
  )

  return (
    <section className="markdown" aria-labelledby="markdown-head">
      <h2 className="markdown-head" id="markdown-head">
        Mark down what is not selling
      </h2>
      <p className="markdown-says">
        Upload TCGplayer&rsquo;s <strong>My Pricing</strong> export. This reports which
        listings TCGplayer says are live, that no copy has sold from here inside the window,
        and that this store has held for longer than the window &mdash; and what each would be
        re-priced to. Then it writes a worklist you can edit, and turns that into an import CSV
        you upload back.
      </p>
      <p className="markdown-says">
        <strong>Nothing is ever deleted at TCGplayer to lower a price.</strong> The upload
        edits the live listing in place, and every row of every file written here carries{' '}
        <code>Add to Quantity</code> of 0 &mdash; so uploading one of them twice changes
        nothing the second time, which is not true of an import from <code>emit</code>.
      </p>
      <p className="markdown-caveat">
        The age this uses is how long the card has been <em>owned</em>, not how long the
        listing has been live. The store cannot measure the second one. Read it as a floor.
      </p>

      <section className="markdown-step" aria-labelledby="markdown-ask">
        <h3 className="markdown-step-head" id="markdown-ask">
          1 &middot; What counts as stale
        </h3>
        <div className="markdown-fields">
          <label className="markdown-field">
            <span className="markdown-label">Window, days</span>
            <input
              type="number"
              min="0"
              value={days}
              onChange={(event) => setDays(event.currentTarget.value)}
            />
          </label>
          <label className="markdown-field">
            <span className="markdown-label">Cut, percent</span>
            <input
              type="number"
              min="0"
              max="99"
              value={percent}
              onChange={(event) => setPercent(event.currentTarget.value)}
            />
          </label>
          <label className="markdown-field">
            <span className="markdown-label">Only above market by</span>
            <input
              type="number"
              min="0"
              placeholder="any"
              value={aboveMarket}
              onChange={(event) => setAboveMarket(event.currentTarget.value)}
            />
          </label>
          <label className="markdown-field">
            <span className="markdown-label">Take at most</span>
            <input
              type="number"
              min="0"
              placeholder="all"
              value={limit}
              onChange={(event) => setLimit(event.currentTarget.value)}
            />
          </label>
          <label className="markdown-check">
            <input
              type="checkbox"
              checked={again}
              onChange={(event) => setAgain(event.currentTarget.checked)}
            />
            <span>Mark down again inside the window</span>
          </label>
        </div>

        <div className="markdown-row">
          <label className="markdown-pick">
            <span className="markdown-label">My Pricing export</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0]
                if (file === undefined) return
                setSurvey(null)
                setApplied(null)
                setStamp(null)
                setWroteImport(false)
                setFailure(null)
                void readUpload(file)
                  .then((upload) => {
                    held.current = upload
                    return survey_(false)
                  })
                  .catch((err) => setFailure(describeFailure(err)))
              }}
            />
          </label>
          {held.current === null ? null : (
            <button
              type="button"
              className="markdown-again"
              disabled={busy}
              onClick={() => void survey_(false)}
            >
              {busy ? 'Reading…' : 'Read it again'}
            </button>
          )}
        </div>
      </section>

      {failure === null ? null : (
        <div className="markdown-note">
          <p className="markdown-note-text">{failure.message}</p>
          <p className="markdown-machine">{failure.code}</p>
        </div>
      )}

      {survey === null ? null : (
        <>
          <pre className="markdown-console">{survey.console}</pre>

          <section className="markdown-step" aria-labelledby="markdown-worklist">
            <h3 className="markdown-step-head" id="markdown-worklist">
              2 &middot; The worklist
            </h3>
            {stamp === null ? (
              <div className="markdown-row">
                <p className="markdown-says">
                  Writes the rows above into a CSV on this machine. It is uploaded nowhere and
                  it changes no price anywhere until you say so.
                </p>
                <button
                  type="button"
                  className="markdown-write"
                  disabled={busy || !survey.ok}
                  onClick={() => void survey_(true)}
                >
                  {busy ? 'Writing…' : 'Write the worklist'}
                </button>
              </div>
            ) : (
              <div className="markdown-row">
                <p className="markdown-says">
                  Written as <code>{stamp}</code>. Edit its{' '}
                  <code>TCG Marketplace Price</code> column, or hand it straight back &mdash; a
                  price is already proposed on every row. Only the SKU and the price are read
                  back; every other byte comes from the export.
                </p>
                <a
                  className="markdown-file"
                  href={markdownFileUrl(stamp, WORKLIST)}
                  download={WORKLIST}
                >
                  {WORKLIST}
                </a>
              </div>
            )}
          </section>
        </>
      )}

      {stamp === null ? null : (
        <section className="markdown-step" aria-labelledby="markdown-apply">
          <h3 className="markdown-step-head" id="markdown-apply">
            3 &middot; The upload
          </h3>
          <div className="markdown-row">
            <label className="markdown-pick">
              <span className="markdown-label">The worklist back (optional)</span>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0]
                  if (file === undefined) return
                  setApplied(null)
                  setWroteImport(false)
                  setFailure(null)
                  void readUpload(file)
                    .then((upload) => {
                      edited.current = upload
                      return apply(false)
                    })
                    .catch((err) => setFailure(describeFailure(err)))
                }}
              />
            </label>
            <button
              type="button"
              className="markdown-check-button"
              disabled={busy}
              onClick={() => void apply(false)}
            >
              {busy ? 'Checking…' : 'Check it'}
            </button>
          </div>

          {applied === null ? null : (
            <>
              <pre className="markdown-console">{applied.console}</pre>
              {wroteImport ? (
                <div className="markdown-row">
                  <p className="markdown-says">
                    Upload this through TCGplayer&rsquo;s My Pricing. It carries{' '}
                    <code>Add to Quantity</code> of 0 on every row.
                  </p>
                  <a
                    className="markdown-file"
                    href={markdownFileUrl(stamp, IMPORT)}
                    download={IMPORT}
                  >
                    {IMPORT}
                  </a>
                </div>
              ) : (
                <button
                  type="button"
                  className="markdown-write"
                  disabled={busy || !applied.ok}
                  onClick={() => void apply(true)}
                >
                  {busy ? 'Writing…' : 'Write the import CSV'}
                </button>
              )}
            </>
          )}
        </section>
      )}

      {history.length === 0 ? null : (
        <section className="markdown-step" aria-labelledby="markdown-history">
          <h3 className="markdown-step-head" id="markdown-history">
            Earlier markdowns
          </h3>
          <ul className="markdown-history">
            {history.map((entry) => (
              <li className="markdown-history-row" key={entry.stamp}>
                <span className="markdown-history-stamp">{entry.stamp}</span>
                <span className="markdown-history-count">{entry.skus} SKU(s)</span>
                <span className="markdown-history-files">
                  {entry.files
                    .filter((name) => name === WORKLIST || name === IMPORT)
                    .map((name) => (
                      <a
                        className="markdown-file"
                        download={name}
                        href={markdownFileUrl(entry.stamp, name)}
                        key={name}
                      >
                        {name}
                      </a>
                    ))}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}
