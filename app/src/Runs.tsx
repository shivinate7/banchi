import { useCallback, useEffect, useMemo, useState } from 'react'

import { describeFailure, getBoxes, type Failure } from './server'
import { boxLabel } from './runScope'
import type { BoxRecord } from './types'
import { LiveReconcile } from './LiveReconcile'
import { RunPanel, type CartBox } from './RunPanel'
import { carriedScope, clearCarriedScope } from './runHandoff'
import './Runs.css'

/* THE PIPELINE, ON A ROUTE OF ITS OWN — the owner's ruling of 2026-08-29 (D39), and it reverses
 * the placement D33 argued for and D38 moved three times.
 *
 * WHAT D33 SAID AND WHY IT LOST. It put the panel on `#/inventory` on the reasoning that "a run
 * is something you do TO a box, or to the cards you have just ticked inside it", so the scope a
 * run needs is the scope the walk is already showing. That is still true, and it is why this
 * file exists rather than a bare `<RunPanel />`: what a route of its own costs is exactly the
 * box strip and the mass-select, and both are answered here rather than wished away. The box is
 * re-answered by a picker of its own. The SELECTION is handed over from the one mass-select in
 * the product — see `runHandoff.ts`, which carries the whole argument.
 *
 * WHAT THE MOVE BUYS, and it is the half D33 could not give. The four commands are the loop of a
 * session — shoot a box, identify it, join it, answer what the join could not — and they were
 * housed on the screen `App.tsx`'s own route table calls `look`: "reached when asked, not on a
 * rhythm". The panel is also the tallest thing this product draws, at 625px closed and 1143px
 * with a run picked, and on `#/inventory` it was the last row of the content column, which put
 * `Check cost` a page-scroll below the card. Neither of those is a layout complaint that a
 * fourth relocation inside one screen was going to answer.
 *
 * IT SITS BETWEEN CAPTURE AND THE REVIEW QUEUE, which is the order the work happens in and the
 * order the nav now draws: shoot the box, run the pipeline over it, answer what the run could
 * not. `,R` reaches it and the review queue moved to `,Q` to make room — the chord is a route
 * initial and `r` is this screen's.
 *
 * THIS FILE OWNS THE SCOPE AND NOTHING ELSE. Every figure, every console, every poll and the
 * whole money gate stay in `RunPanel.tsx`, which is unchanged in all of that: it is given a
 * scope and reads the run directory for the rest. The split is the same one `BoxBrowse` and
 * `Inventory.tsx` already keep — the picker owns what is selected, the panel owns what is done
 * with it — so there is one answer to "which box" on this screen and one place it comes from.
 *
 * THE PICKER TAKES SEVERAL BOXES AS OF 2026-08-29, AND EACH IS STILL ITS OWN RUN. The owner
 * asked for boxes to be "individualized" and sent together, and the split that answers it is
 * this: one press, one request, one `confirm`, one total — and N run directories, because a
 * run over several boxes would force one reading across drawers that deserve their own. What
 * is a cart is the REQUEST; a run is unchanged.
 *
 * WHICH BOXES IS THIS FILE'S; HOW EACH IS READ IS THE PANEL'S. The reading moves the estimate,
 * so it belongs beside the estimate and under the same confirm — see `RunPanel.tsx`'s cart
 * block. This file hands over the boxes and the cards ticked in one of them, and nothing else.
 */

/** One frozen empty array, so `scope` is referentially stable across renders where nothing was
 *  handed over. `RunPanel` builds a `scopeKey` out of this and voids its cost estimate when the
 *  key moves (D32); a fresh `[]` every render would void a paid-for quote on every poll. */
const NONE: readonly number[] = []

/** Boxes ascending, which is the order they sit on a shelf and the order the strip on
 *  `#/inventory` already draws. `GET /boxes` answers in registry order, which is neither. */
function inOrder(records: readonly BoxRecord[]): BoxRecord[] {
  return [...records].sort((a, b) => a.box - b.box)
}

export function Runs() {
  const [boxes, setBoxes] = useState<readonly BoxRecord[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /** Which boxes the send is over. Empty before anything is picked, and nothing here defaults
   *  it: a box chosen for the operator is a box they did not read, and the next press after it
   *  spends money. The panel's preflight is disabled while this is empty and its spend button
   *  does not exist until the preflight has answered.
   *
   *  A SET, ORDERED ASCENDING WHEN IT IS DRAWN. Selection order would make the cart, the quote
   *  and the strip disagree about which box comes first for no reason anybody chose; ascending
   *  is the order the strip already offers and the order a shelf is in. */
  const [picked, setPicked] = useState<ReadonlySet<number>>(() => new Set())

  /** The cards handed over from `#/inventory`'s mass-select, and the box they were ticked in.
   *  Held as the whole carried record rather than as a bare array so that a selection can never
   *  be drawn against a box it was not ticked in — the pair is written together and is read
   *  together or not at all. */
  const [carried, setCarried] = useState<{ box: number; indices: readonly number[] } | null>(null)

  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const answer = await getBoxes()
        if (!live) return
        setBoxes(answer.boxes)
        setFailure(null)

        /* THE HANDOFF IS VALIDATED AGAINST THE REGISTRY BEFORE IT IS DRAWN, and this is the
           only place that can do it — `runHandoff.ts` can check a shape and cannot know which
           boxes exist. A carried box that has since been deleted (D10 ruling 3) is dropped
           whole rather than drawn as a box number with nothing behind it. Falls through to the
           picker, which is the state the operator would have been in had nothing been handed
           over at all. */
        const handoff = carriedScope()
        if (handoff === null) return
        if (!answer.boxes.some((record) => record.box === handoff.box)) {
          clearCarriedScope()
          return
        }
        setCarried(handoff)
        setPicked(new Set([handoff.box]))
      } catch (err) {
        if (!live) return
        setFailure(describeFailure(err))
      }
    })()
    return () => {
      live = false
    }
  }, [reloads])

  /* TOGGLING THE HANDOFF'S OWN BOX DROPS THE HANDOFF; TOGGLING ANY OTHER LEAVES IT ALONE.
     D39's rule was that picking a box always dropped the tick list, on the grounds that "a
     tick list that survived the operator deliberately choosing a box is a filter they did not
     re-consent to, sitting over the control that spends". That reason is preserved rather than
     weakened by scoping it to the carried box: under a single-select, choosing a box REPLACED
     the scope, so every press was a re-consent question. Adding box 7 to a cart does not touch
     what box 3 means, and dropping box 3's selection because box 7 was ticked would be the
     surprise the rule exists to prevent, wearing the rule's own clothes.

     Un-ticking the carried box drops it, because the selection has left the send. Re-ticking
     that box brings back the WHOLE box, which is the safe direction: it costs more and
     identifies nothing that is not there. */
  const toggleBox = useCallback(
    (next: number) => {
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
    },
    [],
  )

  const dropCarried = useCallback(() => {
    setCarried(null)
    clearCarriedScope()
  }, [])

  const rows = useMemo(() => (boxes === null ? [] : inOrder(boxes)), [boxes])

  /** The cart, ascending, each box carrying the cards ticked in it — which is at most one box,
   *  because `#/inventory`'s mass-select is box-scoped and there is deliberately only one of
   *  them in the product. */
  const cart = useMemo<CartBox[]>(
    () =>
      [...picked]
        .sort((a, b) => a - b)
        .map((box) => ({
          box,
          /* THE NAME TRAVELS WITH THE BOX INTO THE PANEL (D56), from the same `GET /boxes` the
             picker above draws. The panel names the drawer on every leg head and in the
             per-box cost breakdown, and a cart row is the one place the name can come from —
             a box that has never been run has no run summary to carry it. It is drawn and
             never sent: `RunPanel`'s `legs` projects a row to what the route reads, so a
             rename cannot reach `scopeKey` and cannot void a live estimate. */
          name: boxes?.find((record) => record.box === box)?.name ?? null,
          indices: carried !== null && carried.box === box ? carried.indices : NONE,
        })),
    [picked, carried, boxes],
  )

  /** The one box, where there is exactly one. Bound rather than indexed twice, because
   *  `cart[0]` is `CartBox | undefined` under this project's index checking and a `!` here
   *  would be a claim about a length the compiler can already see. */
  const only = cart.length === 1 ? cart[0] : undefined

  /* THE ONE-BOX CASE NAMES THE DRAWER AND THE CART CASE DOES NOT (D56). With one box this is
     the only line above the money gate saying what is about to be read, and `Box 3` alone was
     the complaint that produced D56. With several, the names would run this header to two and
     three lines while the picker directly below it draws every one of them named — so the
     header counts the boxes and the chips say which. */
  const scopeLine =
    only !== undefined
      ? `${boxLabel(only.box, only.name)} · ` +
        (only.indices.length > 0
          ? `${only.indices.length} ticked card${only.indices.length === 1 ? '' : 's'}`
          : 'the whole box')
      : cart.length === 0
        ? 'Pick a box. You can pick several.'
        : `${cart.length} boxes · ` +
          cart
            .map((row) =>
              row.indices.length > 0 ? `${row.box} (${row.indices.length} ticked)` : `${row.box}`,
            )
            .join(', ')

  return (
    <main className="runs">
      <header className="runs-head">
        {/* THE TITLE SHARES ITS LINE WITH THE SCOPE AND THE RELOAD — docs/DESIGN.md's page-chrome
            rule as written, and the same shape `ReviewQueue.tsx` draws. What is on that line is
            what the screen is currently pointed at, which is the one fact worth carrying above
            everything else here: every control below it spends or re-runs against that scope. */}
        <div className="runs-head-top">
          <h1 className="runs-title">Runs</h1>
          <div className="runs-controls">
            <span className="runs-scope">{scopeLine}</span>
            {carried === null ? null : (
              /* THE WAY BACK OUT OF A HANDOFF, and it names what it does rather than saying
                 Clear. The operator arrived here from a tick list; the question they will ask
                 of this control is "how do I run the rest of the box", and that is the sentence
                 on it. It names the box now, because with a cart there can be others beside it
                 and "the whole box" would not say which. */
              <button className="runs-plain" type="button" onClick={dropCarried}>
                Run all of box {carried.box} instead
              </button>
            )}
            <button
              className="runs-plain"
              type="button"
              onClick={() => setReloads((n) => n + 1)}
              disabled={boxes === null && failure === null}
            >
              Reload boxes
            </button>
          </div>
        </div>
        <p className="runs-lede">
          identify · join · emit · reconcile. One of the four spends money; the other three are
          free and re-runnable.
        </p>
      </header>

      {failure === null ? null : (
        <div className="runs-note">
          <p className="runs-note-text">{failure.message}</p>
          {/* The greppable token beneath the sentence — docs/DESIGN.md's human-label-large,
              machine-string-small rule, the same shape every owner screen draws a refusal in. */}
          <p className="runs-machine">{failure.code}</p>
        </div>
      )}

      {/* ------------------------------------------------------------------- the box picker */}
      <div className="runs-boxes" role="group" aria-label="Which boxes to run">
        {boxes === null && failure === null ? (
          <p className="runs-empty">Reading the boxes…</p>
        ) : rows.length === 0 ? (
          <p className="runs-empty">No boxes yet. Shoot one on the capture screen.</p>
        ) : (
          rows.map((record) => (
            <button
              key={record.box}
              type="button"
              className={`runs-box${picked.has(record.box) ? ' runs-box-on' : ''}`}
              aria-pressed={picked.has(record.box)}
              onClick={() => toggleBox(record.box)}
            >
              <span className="runs-box-name">
                Box {record.box}
                {record.name === null ? '' : ` · ${record.name}`}
              </span>
              {/* CARDS, NOT THE HIGH-WATER MARK. `next_index` is what the capture screen draws
                  because it is about to consume one; what a run is about to read is the
                  photographs that exist, and those two disagree the moment a record is removed
                  (D10). An empty box is drawn rather than hidden or disabled — the free
                  preflight is what answers whether there is anything to send, and a picker that
                  refuses on the client is a second copy of that rule. */}
              <span className="runs-box-cards">
                {record.cards} card{record.cards === 1 ? '' : 's'}
              </span>
            </button>
          ))
        )}
      </div>

      <RunPanel cart={cart} />

      {/* THE FOURTH COMMAND, UNSCOPED (D87). Below the run panel because everything
          above it is about a run and this deliberately is not. */}
      <LiveReconcile />
    </main>
  )
}
