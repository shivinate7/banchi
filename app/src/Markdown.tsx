import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import {
  applyMarkdown,
  describeFailure,
  getMarkdowns,
  fetchLiveExport,
  markdownFileUrl,
  markdownListings,
  publishMarkdown,
  sendMarkdown,
  rollbackMarkdown,
  type Failure,
} from './server'
import { readUpload } from './csvUpload'
import type {
  CsvUpload,
  LiveExportFetched,
  MarkdownAnswer,
  MarkdownPush,
  MarkdownSummary,
} from './types'
import { Button, Icon, Notice } from './kit'
import { clockTime } from './dates'
import { toast } from './kit/toast'
import { DropZone, FileButton } from './RunsDrop'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import './Markdown.css'

/* THE STALE-LISTING MARKDOWN (D100), as a sheet mounted inside `#/pricing` (D105).
 *
 * A SHEET AND NOT A ROUTE, WHICH IS A JUDGEMENT RATHER THAN A CAPACITY REFUSAL. D100 was
 * argued against a shell that drew its nav as one horizontal strip and could not hold an
 * eleventh link at 1,440px; D95 replaced that with a sidebar, and `App.tsx`'s ROUTES table
 * carries the re-measurement of what a tenth link would cost there. It would fit. What keeps
 * this a sheet is that the lens already has an address — `#/pricing?markdown=<stamp>` — so a
 * second pricing route would be two screens for one job.
 *
 * FOUR STEPS, AND EACH PRESS IS ABSENT UNTIL THE ONE BEFORE IT HAS ANSWERED. D33's rule for
 * the control that spends, applied twice more: a button that exists before there is anything
 * to read is a button pressed before anything was read.
 *
 *   1. Read the My Pricing export — fetched, or dropped. Free, writes nothing, reports what
 *      would move.
 *   2. Write the worklist. A file, on this machine, uploaded nowhere.
 *   3. Hand the worklist back — edited in a spreadsheet, or untouched — and write the import
 *      CSV, then send it to TCGplayer's STAGED inventory, which no buyer can see.
 *   4. Move that staged upload LIVE. **The only press in this product a buyer can see.**
 *
 * STEPS 3 AND 4 ARE TWO PRESSES AND MUST STAY TWO. On 2026-09-06 a session drove TCGplayer's
 * own importer as a dry run with a guard that failed open, and pushed 100 real rows by
 * accident; the only reason that cost nothing is that staging is not publishing. Collapsing
 * these into one button would spend that margin.
 *
 * THE STDOUT IS THE RECEIPT (D33), and it is in a `LogWell` rather than a bare `<pre>` so it
 * folds, counts its lines and copies. Summarising the command's report here would be a second
 * opinion about which of its answers mattered, and the report's own header carries the one
 * sentence the operator must not be allowed to miss — that the age it measures is how long
 * the card has been OWNED and not how long it has been listed.
 */

const WORKLIST = 'worklist.csv'
const IMPORT = 'import.csv'
/** `cli/cmd_reprice.py:SURVEY` — every live row the export carried, and the lens's whole input. */
const SURVEY = 'survey.json'
/** `cli/cmd_reprice.py:REPORT` — the survey's own stdout, including the sentence about the
 *  proxy the window ranks on. Written since D100 and offered by nothing until D103. */
const REPORT = 'report.txt'

/** What a past markdown asked for, in a phrase — `7 days · 10% · top 40`.
 *
 *  READ OFF `asked`, WHICH IS `Plan.asked` VERBATIM. Every figure here was recorded by the
 *  command that ran; nothing is re-derived, so a row cannot describe a survey it did not run.
 *  Absent keys are simply left out rather than defaulted — a markdown written before a flag
 *  existed did not ask for that flag's default, it asked for nothing.
 */
function askedWords(entry: MarkdownSummary): ReactNode {
  const asked = entry.asked ?? {}
  const parts: string[] = []
  const days = asked.days
  if (typeof days === 'number') parts.push(`${days} day${days === 1 ? '' : 's'}`)
  const rule = asked.rule
  const basis = asked.basis
  /* THE BASIS IS PART OF THE CUT AND NOT A SEPARATE FACT: "10% off" means nothing until you know
     10% off WHAT. `asking` is the default and is left silent — naming it on every row would be
     noise on the ordinary case — so the line says the basis exactly when it is not the one the
     operator would assume. */
  const off =
    basis === 'market' ? ' of market' : basis === 'low' ? ' of TCG Low' : ''
  if (typeof rule === 'string' && rule !== '') {
    const pct = /^undercut:(.+)$/.exec(rule)
    parts.push(
      rule === 'match'
        ? `at${off === '' ? ' the asking price' : off.replace(' of', '')}`
        : pct === null
          ? `${rule}${off}`
          : `${pct[1]}% off${off}`,
    )
  }
  const above = asked.above_market
  if (above !== null && above !== undefined && `${above}` !== '') parts.push(`>${above}% over market`)
  const limit = asked.limit
  if (typeof limit === 'number') parts.push(`top ${limit}`)
  const when = entry.at === null ? null : new Date(entry.at)
  const day =
    when === null || Number.isNaN(when.getTime())
      ? null
      : when.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const partsLine =
    parts.length === 0 ? null : (
      <span className="bn-dotline">
        {parts.map((part, i) => (
          <span key={i}>{part}</span>
        ))}
      </span>
    )
  if (day === null) return partsLine
  if (partsLine === null) return day
  return (
    <>
      {day} — {partsLine}
    </>
  )
}

export function Markdown({
  open,
  onClose,
  revision,
  onCorpusWritten,
  autoFetch = false,
}: {
  readonly open: boolean
  readonly onClose: () => void
  /** Fetch the live export the moment the sheet opens, rather than waiting for the press.
   *
   *  THE ONE-CLICK DOOR. `#/pricing` on a store with live listings and no joined runs used to
   *  offer only "Go to Runs" — the screen where prices are decided sending the operator away
   *  from 387 live listings because none of them came out of a camera. The marketplace band on
   *  that deck opens this sheet with the fetch already running, so the whole distance from
   *  "price my live inventory" to a priced worklist is one press. Fires ONCE per opening: the
   *  guard is a ref rather than the `open` prop, because a re-render with `open` still true
   *  must not ask TCGplayer for a second copy of the same file. */
  readonly autoFetch?: boolean
  /** The corpus digest the screen this sheet is mounted on last read (D105).
   *
   *  IT TRAVELS BECAUSE THE SHEET NOW SHARES A TAB WITH A SCREEN THAT WRITES THE SAME FILE.
   *  Step 3 runs `reprice apply --write`, which writes `inventory/prices.json` from a
   *  subprocess — the hazard D103 built the guard for, and while this sheet lived on `#/runs`
   *  there was no pricing screen mounted beside it to be clobbered. There is now. Undefined
   *  means "the host read no revision", which the route allows and the terminal user relies on. */
  readonly revision?: string
  /** Hand the digest back after a write, so the host adopts it rather than being refused
   *  `corpus_moved` on its next keystroke for a write this sheet made on its behalf. */
  readonly onCorpusWritten?: (next: string) => void
}) {
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

  /** What TCGplayer is holding staged for THIS markdown, or null for nothing yet.
   *
   *  IT CARRIES `published_at` RATHER THAN A SECOND BOOLEAN, because the receipt on the server
   *  is the same shape and a screen that kept its own flag could disagree with it after a
   *  reload. Null / staged / published is one value with three readings. */
  const [pushed, setPushed] = useState<MarkdownPush['pushed'] | null>(null)
  /** Which of the two outbound presses is in flight. NOT a boolean: both buttons can be on
   *  screen at once and only the one that was pressed may spin. */
  const [sending, setSending] = useState<'push' | 'publish' | 'rollback' | null>(null)

  /* WHAT WAS PICKED, IN STATE RATHER THAN OFF THE REF BELOW. The drop zone draws the file's
     name and the re-read control only exists once there is a file to re-read; a ref answers
     neither question, because writing one renders nothing. */
  /** WHAT THE CUT COMES OFF (D103). `asking` is the operator's own live price and is the
   *  default for D100's reason: `TCG Marketplace Price` is populated on 441 of 441 live rows of
   *  a My Pricing export and blank on 7,787 of 7,802 of the wide Filtered Export, which is why
   *  `reprice.BASES` is local to that module rather than added to `pricing.BASES`. The other
   *  two are the same columns `#/pricing`'s rule strip prices against, so a person who has used
   *  that screen already knows what they mean. */
  const [basis, setBasis] = useState<'asking' | 'market' | 'low'>('asking')
  /** CUT BY A PERCENTAGE, OR PRICE AT THE BASIS EXACTLY. These are the CLI's own mutually
   *  exclusive pair — `cli/__main__.py`'s `markdown_size` group — and the screen mirrors the
   *  exclusion rather than inventing a third state: `_markdown_flags` reads `rule` first and
   *  `percent` only `elif`, so sending both would silently drop one.
   *
   *  `markup` IS DELIBERATELY NOT OFFERED. It is a real `pricing.Rule`, and on this path it is
   *  a trap: a price above the live one is `RAISED`, which refuses THE WHOLE FILE (D100). A
   *  control whose every use is refused is worse than no control. `match` is the one that means
   *  something here — price at the basis exactly, which is how an operator says "put everything
   *  back to market" — and against `asking` it means "leave it", which the `unchanged` refusal
   *  already names honestly. */
  const [cut, setCut] = useState<'percent' | 'match'>('percent')
  /** The live export this server fetched, if one was. Separate from `busy` because the fetch is
   *  its own wait — it opens a socket to TCGplayer and can take seconds — and the survey that
   *  follows it is a second one the operator should see start. */
  const [fetching, setFetching] = useState(false)
  const [fetched, setFetched] = useState<LiveExportFetched | null>(null)
  const [exportName, setExportName] = useState<string | null>(null)
  const [worklistName, setWorklistName] = useState<string | null>(null)

  /* THE EXPORT IS HELD SO THE SECOND PRESS SENDS THE SAME BYTES, which is `LiveReconcile`'s
     rule and matters more here: the preview the operator read and the worklist the write
     produces have to describe one file, or the numbers on the screen were about something
     else. */
  const held = useRef<CsvUpload | null>(null)
  /** The live export the SERVER holds, by name — the fetched counterpart to `held`'s bytes. */
  const fetchedName = useRef<string | null>(null)
  const edited = useRef<CsvUpload | null>(null)
  const sheet = useRef<HTMLElement | null>(null)
  const scrim = useRef<HTMLDivElement | null>(null)

  const refresh = useCallback(() => {
    void getMarkdowns()
      .then((answer) => setHistory(answer.markdowns))
      .catch(() => setHistory([]))
  }, [])

  /* WHAT TCGPLAYER IS HOLDING, RESTORED FROM THE SERVER'S OWN RECEIPT.
   *
   * A PUSH IS A SERVER WRITE AND THIS IS ITS WAY BACK. Without it, an operator who pushed and
   * then reloaded — or reopened the sheet — would have rows staged at TCGplayer and no control
   * here able to publish them, which is precisely the state `make screen-freshness` exists to
   * refuse. The list is the source and this screen never keeps its own copy: `published_at` is
   * what the publish route latches on, so a local flag that disagreed would offer a second
   * move of rows already moved. */
  useEffect(() => {
    if (stamp === null) return
    const row = history.find((entry) => entry.stamp === stamp)
    if (row !== undefined) setPushed(row.pushed ?? null)
  }, [history, stamp])

  /* GATED ON `open`, BECAUSE THIS SHEET IS ALWAYS MOUNTED. `Runs.tsx` renders it
     unconditionally and hides it with `hidden={!open}`, so an ungated effect fired
     `GET /pipeline/markdowns` on EVERY visit to `#/runs` — for a sheet most visits never open.
     `LiveReconcile`, the sheet this file declares itself a clone of, makes no request until it
     is asked to. Re-running when `open` flips is also what the history NEEDS: a worklist written
     in this session has to appear in the list the next opening draws. */
  useEffect(() => {
    if (!open) return
    refresh()
  }, [open, refresh])

  const ask = useCallback(() => {
    const options: Record<string, unknown> = {}
    if (days.trim() !== '') options.days = Number(days)
    if (cut === 'match') options.rule = 'match'
    else if (percent.trim() !== '') options.percent = percent.trim()
    /* SENT ALWAYS AND NOT ONLY WHEN CHANGED, because the command's own default is `asking` and
       a survey that did not say so would be indistinguishable in `asked` from one that could
       not. The history line reads `asked` verbatim. */
    options.basis = basis
    if (aboveMarket.trim() !== '') options.above_market = aboveMarket.trim()
    if (limit.trim() !== '') options.limit = Number(limit)
    if (again) options.again = true
    return options
  }, [days, percent, aboveMarket, limit, again, basis, cut])

  const read = useCallback(
    async (write: boolean) => {
      const file = held.current
      const named = fetchedName.current
      /* ONE DOCUMENT, FROM WHICHEVER DOOR. Bytes the operator dropped are held so the second
         press sends the same ones; a fetched file is the SERVER's and is named, so re-reading
         it with different numbers costs no second socket to TCGplayer. */
      if (file === null && named === null) return
      setBusy(true)
      setFailure(null)
      try {
        const answer = await markdownListings(file, {
          ...ask(),
          ...(named === null ? {} : { fetched: named }),
          write,
        })
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

  /** Fetch the live export, then survey it in the same press.
   *
   *  ONE PRESS AND NOT TWO, because the fetch is not a thing the operator wants for its own
   *  sake — it is how step 1 stops being a trip to another website. The survey that follows is
   *  the answer they came for, and it is the same `read` the drop zone calls, so the two
   *  entrances converge immediately rather than running parallel flows.
   *
   *  THE NAME IS HELD, NOT THE BYTES. `held` is bytes this screen must re-send; `fetchedName`
   *  is a file the server keeps, so `Read it again with these numbers` re-surveys the identical
   *  document without asking TCGplayer twice. Picking an export clears it, and fetching clears
   *  the bytes — one document at a time, which is the rule the route enforces anyway. */
  const fetchLive = useCallback(async () => {
    setFetching(true)
    setFailure(null)
    try {
      const answer = await fetchLiveExport()
      setFetched(answer)
      setExportName(answer.fetched)
      held.current = null
      fetchedName.current = answer.fetched
      await read(false)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setFetching(false)
    }
  }, [read])

  /* THE AUTOMATIC FETCH, ONCE PER OPENING. `armed` is cleared when the sheet closes so the
     next opening fetches again, and set before the await so a re-render mid-flight cannot
     start a second one. A failure leaves it armed-and-spent deliberately: the operator gets
     the sheet's own error and the ordinary button, rather than a retry loop against a remote
     service. */
  const armed = useRef(false)
  useEffect(() => {
    if (!open) {
      armed.current = false
      return
    }
    if (!autoFetch || armed.current) return
    armed.current = true
    void fetchLive()
  }, [open, autoFetch, fetchLive])

  const apply = useCallback(
    async (write: boolean) => {
      if (stamp === null) return
      setBusy(true)
      setFailure(null)
      try {
        const answer = await applyMarkdown(stamp, {
          worklist: edited.current ?? undefined,
          revision,
          write,
        })
        setApplied(answer)
        /* THE HOST ADOPTS THE NEW DIGEST WHETHER OR NOT A FILE WAS WRITTEN, because `apply`
           writes the corpus for every accepted row and `wrote` is only about `import.csv`. */
        if (answer.revision && onCorpusWritten) onCorpusWritten(answer.revision)
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
    [refresh, stamp, revision, onCorpusWritten],
  )

  /** Send `import.csv` to TCGplayer's staged inventory.
   *
   *  NO OPTIMISM. `pushed` is set from what the server reports and never from what was asked
   *  for: TCGplayer answers with its OWN count of rows it took, and a screen that assumed the
   *  file's row count would say "12 staged" over an upload it had accepted 9 of.
   */
  const push = useCallback(async () => {
    if (stamp === null) return
    setSending('push')
    setFailure(null)
    try {
      /* ONE PRESS (`D273`, Q7): the server reads what is live,
         pushes this file and makes it live. A failed publish is rolled back server-side, so
         the only states this screen can land in are "live" and "nothing changed". */
      const answer = await sendMarkdown(stamp)
      setPushed(answer.published)
      refresh()
    } catch (caught) {
      setFailure(describeFailure(caught))
    } finally {
      setSending(null)
    }
  }, [refresh, stamp])

  /** Discard the staged upload — the undo for a push, and only before it is published.
   *
   *  IT CLEARS `pushed` ON THE WAY BACK, because the server deletes the receipt: leaving it
   *  would leave step 4 offering to publish rows TCGplayer has been told to forget.
   */
  const discard = useCallback(async () => {
    if (stamp === null) return
    setSending('rollback')
    setFailure(null)
    try {
      await rollbackMarkdown(stamp)
      setPushed(null)
      refresh()
    } catch (caught) {
      setFailure(describeFailure(caught))
    } finally {
      setSending(null)
    }
  }, [refresh, stamp])

  /** Move that staged upload live. THE ONE PRESS IN THIS APP A BUYER CAN SEE.
   *
   *  IT SENDS NO UPLOAD ID — the server reads it off its own receipt, so what publishes is
   *  what this markdown staged and cannot be steered from here.
   */
  const publish = useCallback(async () => {
    if (stamp === null) return
    setSending('publish')
    setFailure(null)
    try {
      const answer = await publishMarkdown(stamp)
      setPushed(answer.published)
      refresh()
    } catch (caught) {
      setFailure(describeFailure(caught))
    } finally {
      setSending(null)
    }
  }, [refresh, stamp])

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
      /* AND WHAT WAS STAGED, because `pushed` is about ONE markdown's upload and picking a new
         export starts a different one. Left standing, step 4 would offer to publish the
         previous markdown's rows under this one's heading. */
      setPushed(null)
      setFailure(null)
      setExportName(file.name)
      /* ONE DOCUMENT AT A TIME. The route refuses a request carrying both, so the screen must
         not be able to build one — and the operator who drops a file after fetching plainly
         means the file. */
      fetchedName.current = null
      setFetched(null)
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

  /** Pick up a markdown written on an earlier day, at step 3 — the hand-back.
   *
   *  THE SHEET'S OWN DOCUMENTED FLOW LEAVES THE MACHINE IN THE MIDDLE OF IT: download the
   *  worklist, edit it in a spreadsheet, hand it back. A spreadsheet is not a thing anybody
   *  finishes in one sitting, and until this the ONLY way back in was to re-pick the export and
   *  re-survey — which mints a NEW stamp, so the file the operator had spent an evening editing
   *  was judged against a manifest that was not its own, or refused outright. The history list
   *  drew the worklist as a download beside a sheet that could not accept it back.
   *
   *  IT CLEARS EVERY ANSWER AND NOT THE STAMP. `survey`, `applied`, `wroteImport` and the two
   *  file names all describe the sitting that just ended; carrying one over would show a
   *  console about another markdown above the rows of this one. `nextPress` then reads
   *  `stamp !== null && applied === null` and lands on `check`, which is exactly step 3.
   *
   *  THE EXPORT IS NOT RE-READ AND MUST NOT BE. `apply` takes the stamp and the handed-back
   *  bytes; the manifest on disk is what judges them, and that is the whole point of the
   *  markdown directory being durable state. */
  const resume = useCallback((at: string) => {
    setStamp(at)
    setSurvey(null)
    setApplied(null)
    setWroteImport(false)
    setWorklistName(null)
    setExportName(null)
    setFailure(null)
    held.current = null
    edited.current = null
  }, [])

  /* Focus lands inside on open, stays inside under Tab, and returns to the opener on close;
     Escape closes. The same hook the composer and the store-wide reconcile use. */
  /* `busy` is the hold: Escape does nothing while a survey, a worklist write, a check or an
     import is in flight. Everything else in here survives a close — the sheet stays mounted. */
  useOverlayFocus(sheet, open, onClose, busy, scrim)

  /* WHICH PRESS IS NEXT — the footer's whole content, and three absences rather than three
     disabled buttons (D33). Each is unreachable until the read before it has answered. */
  const nextPress =
    survey !== null && stamp === null
      ? 'worklist'
      : /* A REFUSED CHECK HAS NOT ANSWERED, so the next press is still the check. This read
           `applied === null`, which is true of a check that has not run AND false of one that
           came back refused — so a refusal moved the footer on to `import`, drew that button
           DISABLED (`!applied.ok`), and left no way back. The only escape was re-picking the
           export, and `takeExport` clears `stamp`: it would have thrown away the worklist the
           refused check was about. Three absences rather than three disabled buttons is this
           footer's whole rule (D33), and a disabled forward button with nothing beside it was
           the one state it is meant not to have. */
        stamp !== null && (applied === null || !applied.ok)
        ? 'check'
        : applied !== null && !wroteImport
          ? 'import'
          : null

  /* Portalled to <body> for the same reason the composer and the reconcile sheet are:
     `main.bn-page` keeps a filled transform after its enter animation, and a fixed sheet
     inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div ref={scrim} className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet markdown"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="markdown-head"
        tabIndex={-1}
      >
        <header className="markdown-top">
          <div className="markdown-heading">
            <span className="bn-eyebrow bn-dotline">
              <span>Store-wide</span>
              <span>free</span>
            </span>
            <h2 className="markdown-head" id="markdown-head">
              Mark down what is not selling
            </h2>
          </div>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="markdown-body">
          <p className="markdown-says">Edits live listings. Deletes nothing.</p>

          {/* THE SUBSTITUTION, NAMED WHERE THE OPERATOR READS IT — and it is a substitution
              only where the store has no sighting for the row. `reconcile --live --write`
              records the first export seen holding a SKU, which IS the listing's own age, and
              the report the run prints counts both clocks and says which it used. Claiming the
              proxy unconditionally became a lie of its own the moment some rows had a real
              one, which is D100's rule pointed the other way. */}
          <details className="markdown-caveat">
            <summary>
              <Icon name="clock" size={14} /> How a listing's age is dated
            </summary>
            <span>
              From the first time TCGplayer showed the listing live. Where that is not known yet,
              from when the card was photographed. <a href="#/runs">Check what is live</a> dates
              more of them.
            </span>
          </details>

          <section className="markdown-step" aria-labelledby="markdown-ask">
            <h3 className="bn-section-title bn-dotline" id="markdown-ask">
              <span>1</span>
              <span>What counts as stale</span>
            </h3>
            <div className="markdown-fields">
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
                <span className="bn-field-label">New price is</span>
                <select
                  className="bn-input"
                  value={cut}
                  onChange={(event) => setCut(event.currentTarget.value as typeof cut)}
                >
                  <option value="percent">A percentage under</option>
                  <option value="match">Exactly</option>
                </select>
              </label>
              {cut !== 'percent' ? null : (
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
              )}
              <label className="bn-field">
                <span className="bn-field-label">Cut comes off</span>
                {/* A `select` AND NOT A `Segmented`, which the rule strip on `#/pricing` uses
                    for its four presets. This is one of four fields in a grid row and has to be
                    the height and shape of the three number inputs beside it; a segmented
                    control here would be a fifth kind of thing in a row of four. The kit has no
                    select primitive and `bn-input` is what the field row already speaks. */}
                <select
                  className="bn-input"
                  value={basis}
                  onChange={(event) => setBasis(event.currentTarget.value as typeof basis)}
                >
                  <option value="asking">Your asking price</option>
                  <option value="market">Market</option>
                  <option value="low">TCG Low</option>
                </select>
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

            {/* THE FILE, FETCHED (D104). Step 1 used to happen entirely off this machine and
                the screen could only point at it. `POST /pipeline/live-export` brings the
                operator's own live listings at `MyInventory: True` — the opposite document from
                the run path's catalogue fetch, behind its own guarded constant.

                THE DROP ZONE STAYS AND IS NOT A FALLBACK. An operator with a download already in
                hand should not have to fetch again, and a dead cookie must not be a dead end:
                every refusal here is a sentence, and the zone below is what it leaves them. */}
            <div className="markdown-row">
            </div>
            {fetched === null ? null : (
              <Notice
                tone="ok"
                title={
                  <span className="bn-dotline">
                    <span>{fetched.live_rows} listings live</span>{' '}
                    <span>{fetched.live_copies} copies</span>
                  </span>
                }
              >
                Read just now, across every product line.
                {/* NO CAVEAT, AND THAT IS A PROPERTY OF THE REQUEST RATHER THAN AN OMISSION.
                    `Export From Live` takes no scope at all, so there is nothing it could have
                    left out — and an answer with no rows is refused by the server rather than
                    reported here as an empty inventory. */}
              </Notice>
            )}

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
            <p className="markdown-status" role="status">
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
              {/* `markdown-console` IS A TEST SELECTOR AND NOT A STYLE HOOK, and the difference cost
                  a session once. `LogWell` puts `className` on the inner `<pre>` rather than on the
                  `.runslog` root, so a layout rule written against this class sets `flex` on
                  something that is not a flex item of this column and changes nothing at all. The
                  rule that keeps both consoles from being squeezed flat is `.markdown-body
                  .runslog` in `Markdown.css`, and says so there. */}
              <LogWell
                text={survey.console}
                label={stamp === null ? 'What the survey printed' : 'What the worklist write printed'}
                className="markdown-console"
                maxHeight={420}
              />

              <section className="markdown-step" aria-labelledby="markdown-worklist">
                <h3 className="bn-section-title" id="markdown-worklist">
                  <span className="bn-dotline">
                    <span>2</span>
                    <span>The worklist</span>
                  </span>
                </h3>
                {stamp === null ? (
                  <p className="markdown-says">
                    Writes a CSV on this machine — nothing uploads until you press.
                  </p>
                ) : (
                  <>
                    <Notice tone="ok" title="Written, and uploaded nowhere">
                      Price it on the pricing screen, or edit the spreadsheet's{' '}
                      <code className="bn-code">TCG Marketplace Price</code> column and hand it back.
                    </Notice>
                    {/* THE DOOR TO THE LENS, AND IT IS THE PRIMARY PRESS (D103). The screen it
                        opens is the thing the owner actually asked for — *"the same pricing sorta
                        setup I get when I'm first listing prices ... instead it gives me an excel"*
                        — and it shipped for a day reachable ONLY by typing the URL, which is
                        CLAUDE.md's hard rule broken exactly as `docs/GATES.md` step 7 records it:
                        every mechanical check green over a screen no human could open.

                        IT LEAVES THE SHEET, so it closes it on the way out rather than leaving a
                        modal standing over the screen the operator has just been sent to. */}
                    <div className="markdown-row">
                      <Button
                        variant="primary"
                        icon="tag"
                        onClick={() => {
                          onClose()
                          window.location.hash = `#/pricing?markdown=${stamp}`
                        }}
                      >
                        Price these on the pricing screen
                      </Button>
                      <a className="bn-btn" href={markdownFileUrl(stamp, WORKLIST)} download={WORKLIST}>
                        <Icon name="download" size={16} />
                        {WORKLIST}
                      </a>
                      <span className="bn-mono markdown-stamp">{stamp}</span>
                    </div>
                  </>
                )}
              </section>
            </>
          )}

          {stamp === null ? null : (
            <section className="markdown-step" aria-labelledby="markdown-apply">
              <h3 className="bn-section-title bn-dotline" id="markdown-apply">
                <span>3</span>
                <span>The upload</span>
              </h3>
              <div className="markdown-row">
                <FileButton
                  label={worklistName ?? 'Hand the worklist back'}
                  icon="upload"
                  disabled={busy}
                  onFiles={takeWorklist}
                />
                <span className="markdown-hint">
                  {survey === null
                    ? 'Leaving it means the worklist already in this markdown, unedited.'
                    : 'Optional — leaving it means \u201cthe one you wrote\u201d.'}
                </span>
              </div>

              {applied === null ? null : (
                <>
                  <LogWell
                    text={applied.console}
                    label={wroteImport ? 'What the write printed' : 'What the check printed'}
                    className="markdown-console"
                    maxHeight={420}
                  />
                  {wroteImport ? (
                    <>
                      {/* THE DOWNLOAD STAYS, AND IT IS NOT A FALLBACK. The file is the evidence
                          for what the push sent, and an operator who would rather upload it by
                          hand through My Pricing should not have to undo a button to do it —
                          the same argument D104 makes for keeping the upload door open beside
                          the fetch. */}
                      <Notice tone="ok" title="Ready to send">
                        Price changes only. No copies move.
                      </Notice>
                      <div className="markdown-row">
                        <a className="bn-btn" href={markdownFileUrl(stamp, IMPORT)} download={IMPORT}>
                          <Icon name="download" size={16} />
                          {IMPORT}
                        </a>
                        <span className="bn-sr" role="status">
                          {sending === 'push' ? 'Checking TCGplayer, then sending…' : ''}
                        </span>
                        {pushed === null ? (
                          <Button
                            variant="primary"
                            icon="send"
                            busy={sending === 'push'}
                            disabled={busy}
                            onClick={push}
                          >
                            {/* THE PRESS KEEPS ITS WORDS WHILE IT RUNS (round 9, D118): `busy`
                                draws the spinner, and what it is doing is said beside it. */}
                            Send these prices to TCGplayer
                          </Button>
                        ) : null}
                      </div>
                    </>
                  ) : null}

                </>
              )}
            </section>
          )}

          {/* STEP 4 EXISTS ONLY ONCE SOMETHING IS STAGED, which is D33's gate applied a third
              time: a press that changes what buyers pay must not be on screen before the thing
              it would publish exists.

              AND IT SITS OUTSIDE STEP 3's `applied` GUARD, because the receipt outlives this
              screen. An operator who pushed and then reloaded has run no check this session, so
              gating step 4 on one would strand rows at TCGplayer with nothing here able to
              publish or discard them — which is the very hole the receipt on the summary was
              added to close. It was written inside that guard first, and the reload path is
              what caught it. */}
              {pushed === null ? null : (
                <div className="markdown-publish">
                  <h3 className="bn-section-title bn-dotline">
                    <span>4</span>
                    <span>Go live</span>
                  </h3>
                  {pushed.published_at ? (
                    <Notice tone="ok" title="Live at TCGplayer">
                      {pushed.accepted} price{pushed.accepted === 1 ? '' : 's'} moved live at{' '}
                      {clockTime(pushed.published_at)}. Banchi checks TCGplayer again after the wait.
                    </Notice>
                  ) : (
                    <>
                      <Notice tone="warn" title="This changes what buyers pay">
                        TCGplayer holds {pushed.accepted} price
                        {pushed.accepted === 1 ? '' : 's'} in Staged
                        {pushed.accepted === pushed.rows ? '' : ` of ${pushed.rows} sent`}. Publishing
                        moves those — the only press here a buyer can see.
                      </Notice>
                      {pushed.messages.length === 0 ? null : (
                        <LogWell
                          text={pushed.messages.join('\n')}
                          label="What TCGplayer said about these rows"
                          className="markdown-console"
                          maxHeight={200}
                        />
                      )}
                      <div className="markdown-row">
                        <Button
                          variant="danger"
                          icon="zap"
                          busy={sending === 'publish'}
                          disabled={busy}
                          onClick={publish}
                        >
                          Move {pushed.accepted} live
                        </Button>
                        <Button
                          icon="undo"
                          busy={sending === 'rollback'}
                          disabled={busy}
                          onClick={discard}
                        >
                          Discard staged
                        </Button>
                        <span className="markdown-hint">
                          Discard removes them from TCGplayer. Publishing can't be undone — a
                          new markdown is the only way back.
                        </span>
                      </div>
                    </>
                  )}
            </div>
          )}

          {history.length === 0 ? null : (
            <section className="markdown-step" aria-labelledby="markdown-history">
              <h3 className="bn-section-title" id="markdown-history">
                Earlier markdowns
              </h3>
              {/* WHAT THE DIRECTORY HOLDS, not a flag: whether the upload was ever written is
                  answered by `import.csv` being listed rather than by a boolean that could be
                  true of a file somebody deleted. */}
              <ul className="bn-list markdown-history">
                {history.map((entry) => (
                  <li
                    className="bn-list-row markdown-history-row"
                    key={entry.stamp}
                    /* WHICH EXPORT IT WAS READ FROM, on hover rather than on the row. It is the
                       fact that settles "is this the same download I am holding" and it is a
                       long absolute path — drawn inline it would push the four controls off a
                       narrow sheet to answer a question nobody asks twice. */
                    title={entry.source === null ? undefined : `read from ${entry.source}`}
                  >
                    <span className="bn-mono markdown-stamp">{entry.stamp}</span>
                    <span className="bn-muted bn-tnum">
                      {entry.skus} SKU{entry.skus === 1 ? '' : 's'}
                    </span>
                    {/* WHAT THIS ONE ASKED FOR, so two markdowns can be told apart. Both fields
                        were already on the wire and drawn nowhere, which made a list of stamps
                        a list of identical rows: the operator could see THAT they had run four
                        surveys and nothing about which was which. */}
                    <span className="bn-muted markdown-history-asked">{askedWords(entry)}</span>
                    <span className="markdown-history-files">
                      {/* A MARKDOWN IS DURABLE STATE, NOT A ONE-SHOT — `inventory/markdowns/<stamp>/`
                          keeps its survey, and `reprice apply` will judge a worklist against it
                          weeks later. So yesterday's markdown reopens in the lens on the same terms
                          as the one just written; without this the history was a download shelf and
                          the only way back into a past survey was to type its URL.

                          GATED ON THE SURVEY BEING THERE. Every markdown written before D103 has no
                          `survey.json`, and the lens would refuse it with `survey_not_written` — an
                          offer that leads to a refusal is worse than no offer, so those rows keep
                          their downloads and nothing else. */}
                      {!entry.files.includes(SURVEY) ? null : (
                        <Button
                          size="sm"
                          variant="ghost"
                          icon="tag"
                          onClick={() => {
                            onClose()
                            window.location.hash = `#/pricing?markdown=${entry.stamp}`
                          }}
                        >
                          Price these
                        </Button>
                      )}
                      {/* THE WAY BACK INTO A SITTING THAT LEFT THE MACHINE. A worklist is
                          downloaded to be edited in a spreadsheet, and nothing says that
                          finishes today — see `resume` for what re-surveying instead would
                          have cost. Offered only where there IS a worklist to hand back. */}
                      {!entry.files.includes(WORKLIST) ? null : (
                        <Button
                          size="sm"
                          variant="ghost"
                          icon="upload"
                          onClick={() => resume(entry.stamp)}
                        >
                          Hand it back
                        </Button>
                      )}
                      {entry.files
                        /* THE REPORT JOINS THE TWO CSVs. It was written by every `--write`
                           since D100, matched `_DOWNLOADABLE`, and was listed by `_artefacts`
                           — and this filter dropped it, so the one artefact that says WHY a
                           row is in the worklist, and states the ownership-age substitution
                           the whole window rests on, was unreachable from the screen that
                           made it. D100 names the missing reason column as a cost of the
                           CSV's shape and points at this file for it. */
                        .filter((name) => name === WORKLIST || name === IMPORT || name === REPORT)
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

        <footer className="markdown-foot">
          <Button variant="ghost" onClick={onClose}>
            {wroteImport ? 'Done' : 'Not now'}
          </Button>
          {survey === null ? (
            <Button
              variant="primary"
              icon="download"
              busy={fetching}
              disabled={busy || fetching}
              onClick={() => void fetchLive()}
            >
              {fetching ? 'Asking TCGplayer…' : 'Fetch my live listings'}
            </Button>
          ) : null}
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
