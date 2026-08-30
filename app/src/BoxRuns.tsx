import { useEffect, useState } from 'react'

import { getRuns } from './server'
import type { RunSummary } from './types'
import { runningFor } from './RunPanel'
import { boxOf } from './runScope'
import { carryScope, clearCarriedScope } from './runHandoff'
import './BoxRuns.css'

/* WHAT IS LEFT OF THE RUN PANEL ON `#/inventory` — one status line and one way over to it.
 *
 * THE PANEL LEFT THIS SCREEN ON 2026-08-29 (D39, the owner's ruling; `Runs.tsx` is where it went),
 * and something had to stay here for two separate reasons that happen to have one answer.
 *
 * THE FIRST IS THE SELECTION. `BoxBrowse`'s mass-select is the only one in the product, and
 * `RunPanel` can run over a ticked subset — a capability with a server route, a symlink
 * directory and a test. Moving the panel to a screen with no walk would have left that
 * reachable from nowhere, which is `CLAUDE.md`'s route-is-not-a-feature rule pointing at the
 * thing that caused the move. So the selection is handed over from here: `runHandoff.ts`
 * carries the pair, `#/runs` draws it and says where it came from.
 *
 * THE SECOND IS THE ONE FACT WHOSE LATENCY MATTERS. An identify run takes minutes to hours and
 * `identify/batch.py` logs only when the batch's status CHANGES, so a console written forty
 * minutes ago is indistinguishable from a hang — which is why the run rows say how long they
 * have been running rather than estimating a progress bar. Whether the box in front of you has
 * one going is worth a line on the screen you are standing on; everything else about a run is a
 * page away and should be.
 *
 * IT IS DELIBERATELY NOT A SECOND RUN PANEL. No step, no console, no figures, and above all no
 * control that spends: `POST /pipeline/identify`'s money gate is two steps that must both
 * happen where the estimate is on screen (D33), and a spend reachable from a screen that never
 * showed a preflight is exactly what that gate exists to prevent. What is here is a sentence
 * and a link.
 *
 * IT SITS WHERE THE PANEL SAT, which is the cheapest possible signpost: the operator who used
 * to find the pipeline under the box header finds a line about the pipeline under the box
 * header, and it names where the rest of it is.
 */

/** Live runs are re-read on this cadence, idle ones on the slower one — the same pair
 *  `RunPanel` uses, and the same reason: a run started in a TERMINAL begins live, so a poll
 *  gated on "something is live" could never discover the one case this line exists to show.
 *
 *  TWO POLLERS OF `GET /pipeline/runs` NOW EXIST IN THE APP AND NEVER RUN AT ONCE, because they
 *  are on two routes and the shell renders one view at a time. Worth stating rather than
 *  leaving to be noticed: if a future shell ever keeps a route mounted in the background, this
 *  is the comment that says the doubling was not intended. */
const LIVE_MS = 4000
const IDLE_MS = 20000

type BoxRunsProps = {
  /** The box the walk is pointing at, or null before a shelf is picked. */
  box: number | null
  /** The cards ticked in it. Empty means the whole box, which is what `#/runs` defaults to. */
  indices: readonly number[]
}

export function BoxRuns({ box, indices }: BoxRunsProps) {
  const [runs, setRuns] = useState<readonly RunSummary[]>([])

  /* NO FAILURE PANEL, AND THAT IS A CHOICE. This is a status line beside the answer to "where
     is this card"; a pipeline route being down says nothing about the walk, and a red box under
     the box header would report it as though it did. A failed read leaves the line reading
     `no runs`, and the screen that actually cares — `#/runs` — draws the refusal in full. */
  useEffect(() => {
    let live = true
    let timer: number | undefined
    const tick = async () => {
      try {
        const rows = await getRuns()
        if (!live) return
        setRuns(rows)
        timer = window.setTimeout(() => void tick(), rows.some((row) => row.live) ? LIVE_MS : IDLE_MS)
      } catch {
        if (!live) return
        timer = window.setTimeout(() => void tick(), IDLE_MS)
      }
    }
    void tick()
    return () => {
      live = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [])

  /* RUNS OVER THIS BOX, BY THE ONE DERIVATION. `boxOf` is imported from `runScope.ts` rather
     than re-derived: the box comes off the server now (D56) and falls back to parsing the
     capture directory for a run that predates the field, and two copies of that fallback are
     two answers to which box a run was over. */
  const here = box === null ? [] : runs.filter((row) => row.live && boxOf(row) === box)

  const said =
    box === null
      ? 'Pick a box.'
      : here.length === 0
        ? `Box ${box} · nothing running`
        : `Box ${box} · ${here.map((row) => runningFor(row)).join(' · ')}`

  return (
    <div className="boxruns">
      <p className="boxruns-said">{said}</p>

      {/* AN ANCHOR AND NOT A BUTTON, because it navigates: middle-click, Cmd-click and the
          keyboard all do what a link does, and a `<button>` that assigns `location.hash` throws
          all three away. The handoff is written in the click and the default navigation is left
          alone — nothing here calls `preventDefault`.

          IT CLEARS THE HANDOFF WHEN NOTHING IS TICKED, which is the half that is easy to miss.
          Without it, ticking 36 cards, going over, coming back and pressing this again would
          arrive at `#/runs` with yesterday's selection restored from `sessionStorage` — a
          narrower scope than the operator just asked for, on the screen whose next press spends
          money. Every press through this control states the whole scope. */}
      <a
        className="boxruns-go"
        href="#/runs"
        aria-disabled={box === null}
        onClick={() => {
          if (box === null) return
          if (indices.length > 0) carryScope({ box, indices })
          else clearCarriedScope()
        }}
      >
        {box === null
          ? 'Runs'
          : indices.length > 0
            ? `Run these ${indices.length} ticked card${indices.length === 1 ? '' : 's'} →`
            : `Run box ${box} →`}
      </a>
    </div>
  )
}
