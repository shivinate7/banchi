import { useCallback, useRef, useState } from 'react'

import { describeFailure, markdownFileUrl, runMarkdown, type Failure } from './server'
import { readUpload } from './csvUpload'
import type { CsvUpload } from './types'
import './StaleListings.css'

/* MARK DOWN THE LISTINGS THAT ARE NOT SELLING (D94). Drives `pkmnscan markdown`.
 *
 * WHY IT IS ON `#/runs` AND NOT ON `#/pricing`. It reads the same document as the reconcile
 * above it — TCGplayer's My Pricing export — and answers the other question a person holding
 * that file has: not *what does TCGplayer hold*, but *what has it held too long*. One file in
 * Downloads, two things to do with it, one shelf.
 *
 * AND `#/pricing` IS DISQUALIFIED BY A RACE RATHER THAN BY TASTE. That screen holds the whole
 * corpus in component state from a mount-time snapshot and autosaves it WHOLESALE. A markdown
 * writes `inventory/prices.json` for every stale SKU at once, so a panel there would mean the
 * next keystroke on any row PUTs the stale document and silently reverts the entire sweep.
 * `server.ts:putPricingCorpus` now carries the revision guard that refuses such a write; this
 * panel being one screen away is what makes the guard something the operator meets at a
 * reload rather than mid-edit.
 *
 * IT OFFERS NO RULE AND NO BASIS CONTROL, WHICH IS D49's SEAM. `CLAUDE.md` records that those
 * two are deliberately absent from this screen because `#/pricing` is the one press that sets
 * a standing pricing policy. The window and the percentage are this operation's own
 * parameters, not that policy — and the report names the rule it applied, so the policy is on
 * screen before the control that applies it exists.
 *
 * TWO PRESSES, AND THE FIRST WRITES NOTHING. `docs/DECISIONS.md` deferred this feature naming
 * that exact shape, and the reason: an unattended loop that moves live marketplace prices is
 * the one thing in this product that could lose money while nobody is looking.
 */

/* HOW LONG A LISTING SITS BEFORE IT IS STALE, AND HOW FAR DOWN IT GOES. Declared HERE and
   nowhere else: the command requires both and defaults neither, on the grounds that no number
   in this repo derives a staleness window the way D9 derives the floor. So this is the one
   declaration of where they start, and there is no Python default for it to drift against. */
const WINDOWS = [7, 14, 30, 60, 90] as const
const PERCENTS = [5, 10, 15, 20, 25, 33, 50] as const
const WINDOW_DEFAULT = 30
const PERCENT_DEFAULT = 10

export function StaleListings() {
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<string | null>(null)
  /* THE STAMP, NOT A BOOLEAN, because it does two jobs at once: non-null takes the write
     control away, and it names the directory the download points at. One value, so there is
     no second flag that can disagree with it. */
  const [wrote, setWrote] = useState<string | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [days, setDays] = useState<number>(WINDOW_DEFAULT)
  const [percent, setPercent] = useState<number>(PERCENT_DEFAULT)
  /* THE BYTES AND THE SETTINGS TOGETHER, IN ONE REF. The write must send the same document
     AND the same window and percentage the preview read; two refs would let them drift apart,
     and reading `days` off state at send time would let a control moved after the preview
     reach the write. */
  const held = useRef<{ file: CsvUpload; days: number; percent: number } | null>(null)

  const send = useCallback(async (write: boolean) => {
    const carried = held.current
    if (carried === null) return
    setBusy(true)
    setFailure(null)
    try {
      const answer = await runMarkdown(carried.file, {
        write,
        days: carried.days,
        percent: carried.percent,
      })
      setReport(answer.console)
      setWrote(answer.stamp)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [])

  /* CHANGING EITHER SETTING RE-PREVIEWS AND TAKES THE WRITE CONTROL AWAY. The invariant the
     controls force, and the one LiveReconcile never needed: a write must never be aimed at a
     report the operator has replaced. Clearing `report` first is what removes the button. */
  const retune = useCallback(
    (next: { days?: number; percent?: number }) => {
      if (next.days !== undefined) setDays(next.days)
      if (next.percent !== undefined) setPercent(next.percent)
      const carried = held.current
      if (carried === null) return
      held.current = {
        file: carried.file,
        days: next.days ?? carried.days,
        percent: next.percent ?? carried.percent,
      }
      setReport(null)
      setWrote(null)
      void send(false)
    },
    [send],
  )

  return (
    <section className="stale" aria-labelledby="stale-head">
      <h2 className="stale-head" id="stale-head">
        Mark down what is not selling
      </h2>
      <p className="stale-says">
        The same live export — TCGplayer&rsquo;s <strong>My Pricing</strong>, all printings —
        read for the listings that are live, have not sold, and have been held longer than the
        window. Writes an import CSV that lowers their price and <strong>adds no copies</strong>,
        so nothing is delisted and the live cap cannot be breached. Cards you have held back on{' '}
        <a className="stale-link" href="#/pricing">
          Pricing
        </a>{' '}
        are left alone and named in the report.
      </p>

      <div className="stale-row">
        <label className="stale-field">
          <span className="stale-label">Not sold in</span>
          <select
            className="stale-select"
            value={days}
            disabled={busy}
            onChange={(event) => retune({ days: Number(event.currentTarget.value) })}
          >
            {WINDOWS.map((window) => (
              <option key={window} value={window}>
                {window} days
              </option>
            ))}
          </select>
        </label>
        <label className="stale-field">
          <span className="stale-label">Take off</span>
          <select
            className="stale-select"
            value={percent}
            disabled={busy}
            onChange={(event) => retune({ percent: Number(event.currentTarget.value) })}
          >
            {PERCENTS.map((step) => (
              <option key={step} value={step}>
                {step}%
              </option>
            ))}
          </select>
        </label>
        <label className="stale-pick">
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={busy}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0]
              if (file === undefined) return
              setReport(null)
              setWrote(null)
              setFailure(null)
              void readUpload(file)
                .then((upload) => {
                  held.current = { file: upload, days, percent }
                  return send(false)
                })
                .catch((err) => setFailure(describeFailure(err)))
            }}
          />
        </label>
        {report === null || wrote !== null ? null : (
          /* ABSENT UNTIL THE PREVIEW HAS ANSWERED, and absent again once it has written —
             LiveReconcile's rule, which is D33's rule for the control that spends: a button
             that exists before there is anything to read is a button pressed before anything
             was read. */
          <button
            type="button"
            className="stale-write"
            disabled={busy}
            onClick={() => void send(true)}
          >
            {busy ? 'Writing…' : 'Write the import CSV'}
          </button>
        )}
      </div>

      {failure === null ? null : (
        <div className="stale-note">
          <p className="stale-note-text">{failure.message}</p>
          <p className="stale-machine">{failure.code}</p>
        </div>
      )}

      {wrote === null ? null : (
        /* A URL THE BROWSER DOWNLOADS, NEVER BYTES THROUGH THE JSON BODY. This is the file
           that goes into TCGplayer's importer, and a string in a text area is not that. */
        <p className="stale-done">
          <a className="stale-file" href={markdownFileUrl(wrote)} download="markdown.csv">
            markdown.csv
          </a>
          <span className="stale-where">{wrote}</span>
          <span className="stale-next">
            Upload it to TCGplayer yourself — nothing here has told them anything.
          </span>
        </p>
      )}

      {report === null ? null : (
        /* THE COMMAND'S OWN STDOUT, VERBATIM (D33). Summarising it here would be a second
           opinion about which rows mattered, taken on the operator's behalf at the one moment
           a price moves — and every useful extra column is arithmetic on money, which
           `Pricing.tsx` forbids the client for reasons that apply here twice over. The command
           sorts by what each markdown gives up, so the first screenful is the one that
           decides whether to press. */
        <pre className="stale-console">{report}</pre>
      )}
    </section>
  )
}
