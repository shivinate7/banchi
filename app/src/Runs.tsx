import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { describeFailure, getBoxes, getGames, getInventory, type Failure } from './server'
import { boxesLabel } from './runScope'
import type { BoxRecord, GameRegistry, InventoryCard } from './types'
import { Button, PageHeader, Pill } from './kit'
import { LiveReconcile } from './LiveReconcile'
import { RunPanel } from './RunPanel'
import { RunsComposer, type CartBox } from './RunsComposer'
import { SubmissionClaims } from './SubmissionClaims'
import { carriedByBox, carriedScope, clearCarriedScope, parseKey, type CarriedScope } from './runHandoff'
import {
  census,
  EVERYTHING,
  gameChips,
  hashFor,
  legsFor,
  narrowed,
  newestSitting,
  pending,
  queryFor,
  selected,
  selectionFromHash,
  toggleBox,
  toggleGame,
  toggleSitting,
  type RunSelection,
} from './runSelection'
import './Runs.css'

/* THE PIPELINE, ON A ROUTE OF ITS OWN (D39). Shoot a box, identify it, join it, answer what
 * the join could not — the loop of a session, between Capture and the review queue.
 *
 * THIS FILE OWNS THE SCOPE AND NOTHING ELSE: which cards the next send is over, and the ticked
 * selection handed over from `#/inventory`'s one mass-select (`runHandoff.ts`). The composer
 * owns how each box is read and the money gate; the panel owns the list and the run.
 *
 * THE SCOPE IS A STATE AND ITS NARROWINGS, NOT A LIST OF DRAWERS. `runSelection.ts` carries the
 * whole argument; what this file does with it is hold one `RunSelection`, keep it in the
 * address so it is bookmarkable, and turn it into the cart the composer draws.
 *
 * "NOTHING IS SCOPED ON ARRIVAL" IS RETIRED, AND THE SENTENCE IT REPLACED SAID THE OPPOSITE.
 * This file used to refuse to default the scope, on the ground that "a box chosen for the
 * operator is a box they did not read, and the next press after it spends money". The first
 * half of that is still true and is why no DRAWER is ever ticked for them; the default is the
 * STATE — every card photographed and not identified — which is the fact the front door already
 * put on screen and sent them here to act on. What actually protects the dollar is untouched:
 * the free preflight still has to answer before the confirm exists, and the confirm still
 * carries the figure in its own label (D33). */

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

  /** The card map and the game registry, which together are where every figure on the first
   *  stage comes from — `runSelection.ts` says why they have no narrower source on this wire.
   *  Neither failure takes the screen down: the drawers still draw from the registry, and a
   *  count nobody could read is drawn as absent rather than as zero. */
  const [cards, setCards] = useState<Record<string, InventoryCard> | null>(null)
  const [registry, setRegistry] = useState<GameRegistry | null>(null)

  /** What the next send is over. The state by default, narrowed by nothing. */
  const [selection, setSelection] = useState<RunSelection>(() => selectionFromHash(window.location.hash) ?? EVERYTHING)

  /** The cards handed over from `#/inventory`'s mass-select, as position keys. */
  const [carried, setCarried] = useState<CarriedScope | null>(null)

  const [composerOpen, setComposerOpen] = useState(() => selectionFromHash(window.location.hash) !== null)
  const [syncOpen, setSyncOpen] = useState(false)
  const [openRun, setOpenRun] = useState<string | null>(() => runInHash())

  useEffect(() => {
    const fromHash = () => {
      const named = runInHash()
      if (named !== null) setOpenRun(named)
      /* THE FILTER IS READ BACK OUT OF THE ADDRESS, so a bookmark, a Home link and the back
         button all land on the same scope. A hash that names no state leaves the selection
         alone rather than resetting it — the dialog writes `#/runs` on close and that must not
         read back as "clear what the operator ticked". */
      const asked = selectionFromHash(window.location.hash)
      if (asked !== null) {
        /* ADOPTED ONLY WHEN IT DIFFERS, compared on the one spelling `queryFor` gives a
           selection. This screen writes the hash itself, so every write comes back through
           here; assigning the fresh object unconditionally would be a new identity on every
           press and a render that changes nothing. */
        setSelection((held) => (queryFor(held) === queryFor(asked) ? held : asked))
        setComposerOpen(true)
      }
    }
    window.addEventListener('hashchange', fromHash)
    return () => window.removeEventListener('hashchange', fromHash)
  }, [])

  /* THE ADDRESS FOLLOWS THE SCOPE, IN ONE PLACE. Written from an effect rather than from each
     control, because a React updater must be pure — `setSelection` runs twice under StrictMode
     and a `window.location.hash =` inside one is a side effect run twice. The guard is what
     stops the round trip: this writes, `hashchange` reads it back, and the comparison above
     finds the same selection and stops. */
  useEffect(() => {
    const want = hashFor(window.location.hash, composerOpen ? selection : null)
    if (want !== window.location.hash) window.location.hash = want
  }, [selection, composerOpen])

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

        /* THE HANDOFF IS VALIDATED AGAINST THE REGISTRY BEFORE IT IS DRAWN, AND PER DRAWER
           RATHER THAN WHOLE. It used to be one box, so a box the registry no longer held
           dropped the handoff entirely; keys can span drawers, and dropping forty cards in box
           4 because box 1 was deleted underneath them would be a narrowing the operator never
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

  /* The card map and the registry, read once on arrival. Neither is polled: a sitting's cards
     land through `#/capture`, and the Reload control is what re-reads them here. */
  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const answer = await getInventory()
        if (live) setCards(answer.cards)
      } catch {
        /* A count this screen cannot read is drawn as absent. `RunPanel` draws the one failure
           statement on the page and a second one for the chips would say the same thing twice. */
      }
    })()
    void (async () => {
      try {
        const answer = await getGames()
        if (live) setRegistry(answer)
      } catch {
        /* Without the registry no game can be NAMED, so no game chip is offered — see
           `gameChips`. Nothing is dropped from the scope. */
      }
    })()
    return () => {
      live = false
    }
  }, [reloads])

  /* ------------------------------------------------------------------- the scope, derived */
  const rows = useMemo(() => (boxes === null ? [] : inOrder(boxes)), [boxes])
  const nameOf = useCallback(
    (box: number) => boxes?.find((record) => record.box === box)?.name ?? null,
    [boxes],
  )

  const pendingRows = useMemo(() => pending(cards, registry), [cards, registry])
  const sittingWindow = useMemo(() => newestSitting(cards), [cards])
  const state = useMemo(() => census(pendingRows, sittingWindow), [pendingRows, sittingWindow])
  const games = useMemo(() => gameChips(registry, state.byGame), [registry, state.byGame])

  /** PICKING A SCOPE DROPS THE HANDOFF (D39). A filter that survived a deliberate choice is one
   *  the operator did not re-consent to, so every one of the three chip presses goes through
   *  this: the tick list is let go and the selection re-scopes to the chips. */
  const pick = useCallback((next: (held: RunSelection) => RunSelection) => {
    setCarried((held) => {
      if (held !== null) clearCarriedScope()
      return null
    })
    setSelection(next)
  }, [])

  const onToggleBox = useCallback((box: number) => pick((held) => toggleBox(held, box)), [pick])
  const onToggleGame = useCallback((game: string) => pick((held) => toggleGame(held, game)), [pick])
  const onToggleSitting = useCallback(() => pick((held) => toggleSitting(held)), [pick])
  const onEverything = useCallback(() => pick(() => EVERYTHING), [pick])

  /** The cart, ascending, each drawer carrying the cards ticked in it. The name travels with
   *  the box for the screen (D56) and is never sent.
   *
   *  A HANDOFF WINS OVER THE FILTER WHILE IT LASTS, which is the same precedence it always had
   *  — it is the operator's own explicit tick list, and the chips are a default until they
   *  press one. */
  const cart = useMemo<CartBox[]>(() => {
    const legs = carried !== null ? carriedByBox(carried) : legsFor(selection, pendingRows, sittingWindow)
    return legs.map((leg) => ({ box: leg.box, name: nameOf(leg.box), indices: leg.indices }))
  }, [carried, selection, pendingRows, sittingWindow, nameOf])

  /** How many cards the scope holds, or null where nothing could be counted. A handoff counts
   *  its own keys; a filter counts what it matched. */
  const scopeCards = useMemo(() => {
    if (carried !== null) return carried.keys.length
    if (cards === null) return null
    return selected(selection, pendingRows, sittingWindow).length
  }, [carried, cards, selection, pendingRows, sittingWindow])

  const scopeLine = useMemo(() => {
    const drawers = boxesLabel(cart)
    if (drawers === null) return ''
    const tail =
      carried !== null
        ? `${carried.keys.length} ticked card${carried.keys.length === 1 ? '' : 's'}`
        : narrowed(selection) || scopeCards === null
          ? scopeCards === null
            ? null
            : `${scopeCards} card${scopeCards === 1 ? '' : 's'}`
          : 'everything not yet identified'
    return tail === null ? drawers : `${drawers} · ${tail}`
  }, [cart, carried, selection, scopeCards])

  const onStarted = useCallback((run: string) => {
    setOpenRun(run)
    setReloads((n) => n + 1)
  }, [])

  const openComposer = useCallback(() => setComposerOpen(true), [])

  /* CLOSING CLEARS THE FILTER OUT OF THE ADDRESS rather than leaving one that reopens the
     dialog on the next reload — the effect above does the clearing. The selection itself is
     kept in state: closing is not unticking. */
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
            <Button variant="primary" icon="zap" onClick={openComposer}>
              {cart.length > 1 ? `Identify ${cart.length} boxes` : 'Identify a box'}
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
        cart={cart}
        pageFailure={failure}
        openRun={openRun}
        onOpenRun={setOpenRun}
        reloadTick={reloads}
        onIdentify={openComposer}
      />

      <RunsComposer
        open={composerOpen}
        onClose={closeComposer}
        cart={cart}
        boxes={rows}
        boxesFailure={failure}
        selection={selection}
        state={state}
        games={games}
        counted={cards !== null}
        scopeCards={scopeCards}
        onToggleBox={onToggleBox}
        onToggleGame={onToggleGame}
        onToggleSitting={onToggleSitting}
        onEverything={onEverything}
        carried={carried}
        onDropCarried={onEverything}
        onStarted={onStarted}
      />

      <LiveReconcile open={syncOpen} onClose={closeSync} />
    </main>
  )
}
