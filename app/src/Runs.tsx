import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeFailure, getBoxes, type Failure } from './server'
import type { BoxRecord, RunSelection, RunSummary } from './types'
import { Button, Pill, ReloadButton } from './kit'
import { LiveReconcile } from './LiveReconcile'
import { RunPanel } from './RunPanel'
import {
  NO_DRAFT,
  RunsComposer,
  selectionLine,
  selectionOf,
  startAnswered,
  type SelectionDraft,
} from './RunsComposer'
import { SubmissionClaims } from './SubmissionClaims'
import { carriedScope, clearCarriedScope, parseKey, type CarriedScope } from './runHandoff'
import './Runs.css'

/* THE PIPELINE, ON A ROUTE OF ITS OWN (D39). Shoot a box, identify it, join it, answer what
 * the join could not — the loop of a session, between Capture and the review queue.
 *
 * THIS FILE OWNS THE SELECTION AND NOTHING ELSE: what the operator has pointed at, and the
 * ticked cards handed over from `#/inventory`'s one mass-select (`runHandoff.ts`). The composer
 * owns how they are read and the money gate; the panel owns the list and the run.
 *
 * IT USED TO OWN A CART OF BOXES. `cart: CartBox[]` was one row per drawer, each carrying the
 * cards ticked in it, and both the composer and the panel read it. There is one selection per
 * press now — `box` is a term in it rather than the unit of work — so what this file holds is a
 * DRAFT (the screen's vocabulary: which start, which drawers, which narrowings) and the wire's
 * `RunSelection` is derived from it by one function in the composer.
 *
 * THE HANDOFF IS VALIDATED PER KEY, NOT PER BOX. `runHandoff.ts:CarriedScope` carries a flat
 * list of `box/index` keys rather than one box and its indices, which is what lets a tick list
 * from `#/inventory` span drawers — so a key naming a drawer the registry no longer holds is
 * dropped alone, and the rest of the handoff survives it.
 *
 * `#/runs?state=captured` OPENS THE COMPOSER ON ITS DEFAULT SCOPE. `standing.ts`'s one ranked
 * sentence on `#/` — *"N cards are photographed and not identified"* — links here now rather
 * than to a bare `#/runs`, so the answer to the sentence the operator just read is one click
 * rather than a second question about drawers. The default draft (`NO_DRAFT`) is already
 * `state === 'captured'` under its `needed` start, so the address has nothing to compose — it
 * only has to open the dialog, the way a `run=` link opens a run's own detail. This is
 * read-once, like `run=`: there is no write-back of a narrowing into the address and no
 * `&box=` term, because nothing in this app links to one yet and building the two-way sync a
 * bookmarked narrowing would need is not this fix. */

function inOrder(records: readonly BoxRecord[]): BoxRecord[] {
  return [...records].sort((a, b) => a.box - b.box)
}

/** `?run=<name>` opens that run — Home links here that way, and so does the Review strip
 *  since the fold (D291). Read off the whole hash's
 *  query, so it works the same whether the path in front of it is `#/runs` or `#/review`. */
export function runInHash(): string | null {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).get('run')
}

/** `?state=captured` — `standing.ts`'s own link — asks for the composer to be open on
 *  arrival. The value is not otherwise read: `captured` is the only state this composer can
 *  act on and it is already the default draft's start. */
export function stateInHash(): boolean {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).get('state') === 'captured'
}

/** `?box=<n>` — Capture's "Identify <box> on Runs" (UX-030). THE PRESS ARRIVES WITH THE
 *  BOX IT NAMED AS ITS SCOPE, which is D39's own outcome: the selection is handed to the screen.
 *  Before this the button landed on the store-wide start, so the next press spent money across
 *  every box while the label named one. A value that is not a whole number is no box at all. */
export function boxInHash(): number | null {
  const query = window.location.hash.split('?')[1] ?? ''
  const raw = new URLSearchParams(query).get('box')
  if (raw === null || !/^[0-9]+$/.test(raw)) return null
  const box = Number(raw)
  return box >= 1 ? box : null
}

/** WHAT A CARD HAS COST TO IDENTIFY, ON THIS STORE'S OWN PAST RUNS: every recorded spend
 *  divided by every card those runs read. The "~$X" on Review's Identify strip (D291) is this
 *  times the waiting count. It is not a quote, and nothing is gated on it: the composer's free
 *  preflight is still the one figure the spend press is confirmed against. A store with no run
 *  that recorded a spend has no rate, and the strip then says no figure at all rather than a
 *  guess. Both figures are the server's (`usage.cost_usd`, `counts.cards_in`); this only
 *  divides them, and multiplies no token count by any rate. */
export function perCardRate(runs: readonly RunSummary[]): number | null {
  let usd = 0
  let cards = 0
  for (const run of runs) {
    const spent = run.usage.cost_usd
    const read = run.counts.cards_in
    if (typeof spent !== 'number' || spent <= 0 || typeof read !== 'number' || read <= 0) continue
    usd += spent
    cards += read
  }
  return cards === 0 ? null : usd / cards
}

/** THE RUNS CONTENT, folded into Review's own sheet (D291,
 *  the owner's ruling, RULINGS.md Q6). Unchanged from the screen this used to be on its own
 *  route — same state, same hooks, same hash reads — only the outer frame moved: `#/runs`'s
 *  own `<main className="runs bn-page">` and `<PageHeader>` are gone, because this now
 *  mounts inside `ReviewQueue.tsx`'s own Sheet, whose header already draws a title.
 *  `#/runs` itself is a redirect now (`RunsRedirect`, below) that keeps every deep link
 *  (`?run=`, `?state=captured`, `?box=`) working unread by this file — it is the SAME hash
 *  query reads, `runInHash`/`stateInHash`/`boxInHash` above, that already worked from either
 *  path. */
export function RunsContent({
  compose = false,
  run = null,
  onLeave,
}: {
  /** A run to open on arrival: the one Review's "Identify now" just started, so its progress
   *  shows the way a composer-started run's does. */
  readonly run?: string | null
  /** Open straight onto the composer: Review's Identify strip pressed through to the money
   *  gate (D291), rather than the past-runs link. */
  readonly compose?: boolean
  /** Called when a composer opened by `compose` closes with no run started, so the press
   *  leaves nothing behind it: the operator is back on Review, not in the run list. */
  readonly onLeave?: () => void
} = {}) {
  const [boxes, setBoxes] = useState<readonly BoxRecord[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /** WHAT THE OPERATOR HAS POINTED AT. No DRAWER is ever ticked for them — a drawer chosen on
   *  their behalf is one they did not read, and the press after it spends money. The default
   *  START is the store-wide one, which is the state `#/`'s own standing line already named. */
  const [draft, setDraft] = useState<SelectionDraft>(NO_DRAFT)

  /** The cards handed over from `#/inventory`'s mass-select, as position keys. */
  const [carried, setCarried] = useState<CarriedScope | null>(null)

  const [composerOpen, setComposerOpen] = useState(() => compose || stateInHash())
  const started = useRef(false)
  const [syncOpen, setSyncOpen] = useState(false)
  const [openRun, setOpenRun] = useState<string | null>(() => run ?? runInHash())

  useEffect(() => {
    const fromHash = () => {
      const named = runInHash()
      if (named !== null) setOpenRun(named)
      if (stateInHash()) setComposerOpen(true)
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  /** The handoff from `#/inventory` is applied ONCE, on the first successful read of the
   *  registry — never on a Reload and never when a run starts, both of which bump `reloads`.
   *  It stays in storage until the operator picks a scope, so re-applying it here would reopen
   *  the composer uninvited and silently put back a selection they had just replaced. */
  const handoffApplied = useRef(false)

  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const answer = await getBoxes()
        if (!live) return
        setBoxes(answer.boxes)
        setFailure(null)
        if (handoffApplied.current) return
        handoffApplied.current = true

        /* THE BOX CAPTURE NAMED, if the registry still holds it. It wins over a stale tick list:
           it is the press the operator just made. A box the registry no longer holds falls
           through to the ordinary start rather than to a guess. */
        const named = boxInHash()
        if (named !== null && answer.boxes.some((record) => record.box === named)) {
          setDraft({ ...NO_DRAFT, start: 'drawers', boxes: [named] })
          setComposerOpen(true)
          return
        }

        /* THE HANDOFF IS VALIDATED AGAINST THE REGISTRY BEFORE IT IS DRAWN, AND PER KEY RATHER
           THAN WHOLE. `CarriedScope` is a flat list of `box/index` keys, which is what lets a
           tick list from `#/inventory` span drawers — dropping the whole handoff because ONE of
           several drawers was deleted underneath it would be a narrowing the operator never
           asked for in the one direction that costs them work. Keys in a departed drawer go,
           the rest stay, and a handoff with nothing left goes the way it always did. */
        const handoff = carriedScope()
        if (handoff === null) return
        const known = new Set(answer.boxes.map((record) => record.box))
        const kept = handoff.keys.filter((key) => {
          const at = parseKey(key)
          return at !== null && known.has(at.box)
        })
        if (kept.length === 0) {
          clearCarriedScope()
          return
        }
        setCarried({ keys: kept })
        /* ARRIVING WITH A TICK LIST SELECTS IT, which is what the handoff is for — and it is
           the operator's own act one screen back, not a default this file invented. */
        setDraft((held) => ({ ...held, start: 'ticked' }))
        setComposerOpen(true)
      } catch (err) {
        if (!live) return
        setFailure(describeFailure(err))
      }
    })()
    return () => {
      live = false
    }
  }, [reloads])

  /* D39'S RE-CONSENT RULE, NARROWED AND NOT REPEALED. That entry drops the ticked selection
     whenever a scope is picked on `#/runs`, because a tick list surviving a deliberate choice is
     a filter the operator did not re-consent to, sitting over the control that spends. Under the
     cart the rule scoped to the carried BOX: un-ticking it dropped the handoff and toggling any
     other left it alone. A drawer is a term rather than the unit now, so the rule scopes to the
     START: choosing any start other than the ticked cards is the deliberate choice, and it drops
     them. Toggling a drawer while the drawers start is showing is not — it is the operator
     building the selection they already chose. */
  const toggleBox = useCallback((next: number) => {
    setDraft((held) => {
      const on = held.boxes.includes(next)
      return {
        ...held,
        boxes: on ? held.boxes.filter((box) => box !== next) : [...held.boxes, next].sort((a, b) => a - b),
        /* A SECTION BELONGS TO ONE DRAWER, so a pick that leaves the selection naming two drops
           it rather than letting a stale value reach a refusal the operator did not cause. */
        section: held.boxes.length === 1 && !on ? null : held.section,
      }
    })
  }, [])

  const dropCarried = useCallback(() => {
    setCarried(null)
    clearCarriedScope()
  }, [])

  const onDraft = useCallback(
    (patch: Partial<SelectionDraft>) => {
      setDraft((held) => ({ ...held, ...patch }))
      if (patch.start !== undefined && patch.start !== 'ticked') dropCarried()
    },
    [dropCarried],
  )

  const rows = useMemo(() => (boxes === null ? [] : inOrder(boxes)), [boxes])

  /** The draft as the wire reads it. ONE derivation, in the composer, so the pill on this page
   *  and the payload the money press sends cannot describe different cards. The box NAMES travel
   *  for the screen (D56) and are never sent. */
  const selection = useMemo<RunSelection>(() => selectionOf(draft, carried), [draft, carried])
  const answered = useMemo(() => startAnswered(draft, carried), [draft, carried])
  const scopeLine = useMemo(
    () => (answered ? selectionLine(draft, carried, boxes) : ''),
    [answered, draft, carried, boxes],
  )

  const onStarted = useCallback((run: string) => {
    started.current = true
    setOpenRun(run)
    setReloads((n) => n + 1)
  }, [])

  const closeComposer = useCallback(() => {
    setComposerOpen(false)
    if (compose && !started.current) onLeave?.()
  }, [compose, onLeave])
  const closeSync = useCallback(() => setSyncOpen(false), [])

  return (
    <div className="runs">
      {/* The sheet's own header carries the title and icon now (Review's Sheet, "Runs").
         This row is the one worded primary — "Identify cards" — plus icons for the rest
         (the header rule, owner 2026-09-24). */}
      <p className="runs-lede">Only Identify costs money.</p>
      <div className="runs-actions">
        {scopeLine === '' ? null : (
          <Pill tone="accent" icon="box" className="runs-scope">
            {scopeLine}
          </Pill>
        )}
        <ReloadButton onReload={() => setReloads((n) => n + 1)} busy={boxes === null && failure === null} label="Reload boxes and runs" hotkey={false} />
        {/* WORDS, NOT AN ICON (ICON-MAP's Runs row): its verb is not in the icon vocabulary, and a
            second refresh glyph beside the reload would read as the same control. Ghost, because
            Identify cards is this row's one primary. */}
        <Button variant="ghost" icon="refresh" onClick={() => setSyncOpen(true)}>
          Check what is live
        </Button>
        {/* ONE VERB, WHATEVER THE SELECTION IS OVER. It read `Identify a box` / `Identify N
            boxes`, which named the unit of work in the label of the button that opens the
            dialog where the unit is chosen — so the operator had to have decided before
            pressing. `Identify cards` is true of every selection this now composes. */}
        <Button variant="primary" icon="zap" onClick={() => setComposerOpen(true)}>
          Identify cards
        </Button>
      </div>

      {/* WHAT A LIVE SEND IS HOLDING, AND THE WAY OUT OF A STUCK CLAIM
          (D174). Above the run list rather than inside it, because it is a
          fact about the PRESS and not about any one run: a claim can outlive the run that made
          it, and the refusal an operator meets — "watch that run, or release its claim" —
          points at both halves of this screen. It draws NOTHING when nothing is claimed,
          which on a healthy store is always, so it costs the page no height at rest. */}
      <SubmissionClaims />

      {/* The one failure statement on the page is drawn in the run list's column by the panel,
          so the server being unreachable is said once rather than by every column. */}
      <RunPanel
        drawers={selection.box ?? []}
        pageFailure={failure}
        openRun={openRun}
        onOpenRun={setOpenRun}
        reloadTick={reloads}
        onIdentify={() => setComposerOpen(true)}
      />

      <RunsComposer
        open={composerOpen}
        onClose={closeComposer}
        selection={selection}
        draft={draft}
        onDraft={onDraft}
        boxes={rows}
        boxesFailure={failure}
        onToggleBox={toggleBox}
        carried={carried}
        onDropCarried={dropCarried}
        onStarted={onStarted}
      />

      <LiveReconcile open={syncOpen} onClose={closeSync} />
    </div>
  )
}

/** `#/runs` ITSELF IS A REDIRECT NOW (item 2, `D291.md`). Every deep link
 *  a person or another screen already holds — `#/runs`, `#/runs?run=<name>`,
 *  `#/runs?state=captured`, `#/runs?box=<n>` — keeps landing on the same content, because the
 *  whole query string carries over unread by this component: `RunsContent`'s own hash reads
 *  (`runInHash`, `stateInHash`, `boxInHash`) run again once the location is `#/review?...`
 *  and see the same values. `replace: true` so the redirect leaves no `#/runs` entry for the
 *  Back button to land back on. */
export function RunsRedirect() {
  useEffect(() => {
    const query = window.location.hash.split('?')[1] ?? ''
    /* A BARE `#/runs`, WITH NO QUERY, STILL HAS TO OPEN THE SHEET — every internal link this
       app already carries to `#/runs` (Pricing's "Start a run", ValueBands' own links, and
       others) means "take me to the runs screen," which now means "open the sheet." `runs=1`
       is that intent, read by `ReviewQueue.tsx` beside `run=`/`state=`/`box=`, which already
       carry their own intent and do not need it added.

       `window.location.hash =`, never `history.replaceState`: the shell's own router
       (`App.tsx:useHashPath`) reads the path on `hashchange` alone, and `replaceState` does
       not fire it — the route would keep drawing this redirect with a URL already changed
       under it. Every other navigation in this app sets `.hash` the same way. */
    window.location.hash = `#/review${query === '' ? '?runs=1' : `?${query}`}`
  }, [])
  return null
}
