import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeFailure, getBoxes, type Failure } from './server'
import { boxLabel } from './runScope'
import type { BoxRecord } from './types'
import { Button, PageHeader, Pill } from './kit'
import { LiveReconcile } from './LiveReconcile'
import { Markdown } from './Markdown'
import { RunPanel } from './RunPanel'
import { RunsComposer, type CartBox } from './RunsComposer'
import { carriedScope, clearCarriedScope } from './runHandoff'
import './Runs.css'

/* THE PIPELINE, ON A ROUTE OF ITS OWN (D39). Shoot a box, identify it, join it, answer what
 * the join could not — the loop of a session, between Capture and the review queue.
 *
 * THIS FILE OWNS THE SCOPE AND NOTHING ELSE: which boxes are in the cart, and the ticked
 * selection handed over from `#/inventory`'s one mass-select (`runHandoff.ts`). The composer
 * owns how each box is read and the money gate; the panel owns the list and the run. */

/** One frozen empty array, so `scope` is referentially stable across renders where nothing was
 *  handed over — a fresh `[]` every render would void a paid-for quote on every poll. */
const NONE: readonly number[] = []

function inOrder(records: readonly BoxRecord[]): BoxRecord[] {
  return [...records].sort((a, b) => a.box - b.box)
}

/** `#/runs?run=<name>` opens that run — Home links here that way. */
function runInHash(): string | null {
  const query = window.location.hash.split('?')[1] ?? ''
  return new URLSearchParams(query).get('run')
}

export function Runs() {
  const [boxes, setBoxes] = useState<readonly BoxRecord[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /** Which boxes the send is over. Empty until picked: a box chosen for the operator is a box
   *  they did not read, and the press after it spends money. */
  const [picked, setPicked] = useState<ReadonlySet<number>>(() => new Set())

  /** The cards handed over from `#/inventory`'s mass-select, and the box they were ticked in. */
  const [carried, setCarried] = useState<{ box: number; indices: readonly number[] } | null>(null)

  const [composerOpen, setComposerOpen] = useState(false)
  const [syncOpen, setSyncOpen] = useState(false)
  const [markdownOpen, setMarkdownOpen] = useState(false)
  const [openRun, setOpenRun] = useState<string | null>(() => runInHash())

  useEffect(() => {
    const fromHash = () => {
      const named = runInHash()
      if (named !== null) setOpenRun(named)
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  /** The handoff from `#/inventory` is applied ONCE, on the first successful read of the
   *  registry — never on a Reload and never when a run starts, both of which bump `reloads`.
   *  It stays in storage until its box is unticked, so re-applying it here would reopen the
   *  composer uninvited and silently drop every other box in the cart. */
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

        /* The handoff is validated against the registry before it is drawn: a carried box that
           has since been deleted is dropped whole rather than drawn as a number with nothing
           behind it. A valid one opens the composer on the box it was ticked in. */
        const handoff = carriedScope()
        if (handoff === null) return
        if (!answer.boxes.some((record) => record.box === handoff.box)) {
          clearCarriedScope()
          return
        }
        setCarried(handoff)
        setPicked(new Set([handoff.box]))
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

  /* Toggling the handoff's own box drops the handoff; toggling any other leaves it alone. */
  const toggleBox = useCallback((next: number) => {
    setPicked((held) => {
      const now = new Set(held)
      if (now.has(next)) now.delete(next)
      else now.add(next)
      return now
    })
    setCarried((held) => {
      if (held === null || held.box !== next) return held
      clearCarriedScope()
      return null
    })
  }, [])

  const dropCarried = useCallback(() => {
    setCarried(null)
    clearCarriedScope()
  }, [])

  const rows = useMemo(() => (boxes === null ? [] : inOrder(boxes)), [boxes])

  /** The cart, ascending, each box carrying the cards ticked in it. The name travels with the
   *  box for the screen (D56) and is never sent. */
  const cart = useMemo<CartBox[]>(
    () =>
      [...picked]
        .sort((a, b) => a - b)
        .map((box) => ({
          box,
          name: boxes?.find((record) => record.box === box)?.name ?? null,
          indices: carried !== null && carried.box === box ? carried.indices : NONE,
        })),
    [picked, carried, boxes],
  )

  const only = cart.length === 1 ? cart[0] : undefined
  const scopeLine =
    only !== undefined
      ? `${boxLabel(only.box, only.name)} · ` +
        (only.indices.length > 0
          ? `${only.indices.length} ticked card${only.indices.length === 1 ? '' : 's'}`
          : 'the whole box')
      : cart.length === 0
        ? ''
        : `${cart.length} boxes · ` +
          cart.map((row) => (row.indices.length > 0 ? `${row.box} (${row.indices.length} ticked)` : `${row.box}`)).join(', ')

  const onStarted = useCallback((run: string) => {
    setOpenRun(run)
    setReloads((n) => n + 1)
  }, [])

  const closeComposer = useCallback(() => setComposerOpen(false), [])
  const closeSync = useCallback(() => setSyncOpen(false), [])
  const closeMarkdown = useCallback(() => setMarkdownOpen(false), [])

  return (
    <main className="runs bn-page">
      <PageHeader
        eyebrow="Workflow"
        icon="play"
        title="Runs"
        lede="Identify, join, emit and reconcile a box. Identify is the one step that spends money; the other three are free and can be run again."

        actions={
          <>
            {cart.length === 0 ? null : (
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
            {/* BESIDE THE RECONCILE AND AFTER IT (D100), because they read the SAME FILE —
                TCGplayer's My Pricing export — and the order of the two buttons is the order
                of the work: settle what TCGplayer holds, then decide about the part of it
                that is not moving. */}
            <Button icon="trendDown" onClick={() => setMarkdownOpen(true)} aria-label="Mark down stale listings">
              <span className="runs-hide-sm">Mark down stale</span>
              <span className="runs-only-sm">Mark down</span>
            </Button>
            <Button variant="primary" icon="zap" onClick={() => setComposerOpen(true)}>
              {cart.length > 1 ? `Identify ${cart.length} boxes` : 'Identify a box'}
            </Button>
          </>
        }
      />

      {/* The one failure statement on the page is drawn in the run list's column by the panel,
          so the server being unreachable is said once rather than by every column. */}
      <RunPanel
        cart={cart}
        pageFailure={failure}
        openRun={openRun}
        onOpenRun={setOpenRun}
        reloadTick={reloads}
        onIdentify={() => setComposerOpen(true)}
      />

      <RunsComposer
        open={composerOpen}
        onClose={closeComposer}
        cart={cart}
        boxes={rows}
        boxesFailure={failure}
        picked={picked}
        onToggleBox={toggleBox}
        carried={carried}
        onDropCarried={dropCarried}
        onStarted={onStarted}
      />

      <LiveReconcile open={syncOpen} onClose={closeSync} />
      <Markdown open={markdownOpen} onClose={closeMarkdown} />
    </main>
  )
}
