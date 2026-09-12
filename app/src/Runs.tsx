import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeFailure, getBoxes, type Failure } from './server'
import type { BoxRecord, RunSelection } from './types'
import { Button, PageHeader, Pill } from './kit'
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

/** `#/runs?run=<name>` opens that run — Home links here that way. */
function runInHash(): string | null {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).get('run')
}

/** `#/runs?state=captured` — `standing.ts`'s own link — asks for the composer to be open on
 *  arrival. The value is not otherwise read: `captured` is the only state this composer can
 *  act on and it is already the default draft's start. */
function stateInHash(): boolean {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).get('state') === 'captured'
}

export function Runs() {
  const [boxes, setBoxes] = useState<readonly BoxRecord[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /** WHAT THE OPERATOR HAS POINTED AT. No DRAWER is ever ticked for them — a drawer chosen on
   *  their behalf is one they did not read, and the press after it spends money. The default
   *  START is the store-wide one, which is the state `#/`'s own standing line already named. */
  const [draft, setDraft] = useState<SelectionDraft>(NO_DRAFT)

  /** The cards handed over from `#/inventory`'s mass-select, as position keys. */
  const [carried, setCarried] = useState<CarriedScope | null>(null)

  const [composerOpen, setComposerOpen] = useState(() => stateInHash())
  const [syncOpen, setSyncOpen] = useState(false)
  const [openRun, setOpenRun] = useState<string | null>(() => runInHash())

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
    setOpenRun(run)
    setReloads((n) => n + 1)
  }, [])

  const closeComposer = useCallback(() => setComposerOpen(false), [])
  const closeSync = useCallback(() => setSyncOpen(false), [])

  return (
    <main className="runs bn-page">
      <PageHeader
        eyebrow="Workflow"
        icon="play"
        title="Runs"
        lede="Identify, join, emit and reconcile a box. Identify is the one step that spends money; the other three are free and can be run again."

        actions={
          <>
            {scopeLine === '' ? null : (
              <Pill tone="accent" icon="box" className="runs-scope">
                {scopeLine}
              </Pill>
            )}
            <Button
              variant="ghost"
              icon="refresh"
              iconOnly
              onClick={() => setReloads((n) => n + 1)}
              disabled={boxes === null && failure === null}
            >
              Reload boxes and runs
            </Button>
            <Button icon="upload" onClick={() => setSyncOpen(true)} aria-label="Reconcile the whole store">
              <span className="runs-hide-sm">Reconcile the store</span>
              <span className="runs-only-sm">Reconcile</span>
            </Button>
            {/* ONE VERB, WHATEVER THE SELECTION IS OVER. It read `Identify a box` / `Identify N
                boxes`, which named the unit of work in the label of the button that opens the
                dialog where the unit is chosen — so the operator had to have decided before
                pressing. `Identify cards` is true of every selection this now composes. */}
            <Button variant="primary" icon="zap" onClick={() => setComposerOpen(true)}>
              Identify cards
            </Button>
          </>
        }
      />

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
    </main>
  )
}
