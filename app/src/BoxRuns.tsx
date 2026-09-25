import { useState } from 'react'

import { getRuns } from './server'
import type { RunSummary } from './types'
import { runningFor } from './RunPanel'
import { boxOf } from './runScope'
import { cardKey, carryScope, clearCarriedScope } from './runHandoff'
import { usePoll } from './usePoll'
import { Icon } from './kit'
import './BoxRuns.css'

/* What is left of the run panel on `#/inventory` — one status line and one way over to it.
 * The selection is handed over from here (`runHandoff.ts` carries the pair, `#/runs` draws it),
 * and whether the box in front of you has a run going is worth a line on the screen you are
 * standing on. Deliberately not a second run panel: no step, no console, no control that spends. */

/** Live runs are re-read on this cadence, idle ones on the slower one — the same pair
 *  `RunPanel` uses, and now the same HOOK (D207) rather than a copy of its constants
 *  kept in step by comment alone. */
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

  /* No failure panel: a pipeline route being down says nothing about the walk. A failed read
     leaves the line reading `nothing running`; `#/runs` draws the refusal in full — so this
     poll has no `onError` at all, exactly as it never reported one before the hook existed. */
  usePoll<RunSummary[]>({
    fn: getRuns,
    onData: setRuns,
    isLive: (rows) => rows.some((row) => row.live),
    liveMs: LIVE_MS,
    idleMs: IDLE_MS,
  })

  /* Runs over this box, by the one derivation (`runScope.ts:boxOf`). */
  const here = box === null ? [] : runs.filter((row) => row.live && boxOf(row) === box)

  const said =
    box === null
      ? 'Pick a box.'
      : here.length === 0
        ? 'Nothing running'
        : here.map((row) => runningFor(row)).join(', ')

  return (
    <div className="boxruns" data-live={here.length > 0 ? 'true' : undefined}>
      <span className={here.length > 0 ? 'bn-dot bn-dot-live' : 'bn-dot'} aria-hidden="true" />
      <p className="boxruns-said">{said}</p>

      {/* An anchor and not a button, because it navigates. The handoff is written in the click
          and the default navigation is left alone. It clears the handoff when nothing is
          ticked, so every press through this control states the whole scope. */}
      <a
        className="boxruns-go"
        href="#/runs"
        aria-disabled={box === null}
        onClick={() => {
          if (box === null) return
          /* KEYS, NOT A BOX AND ITS INDICES. `CarriedScope` moved to `box/index` strings so a
             selection can span drawers; this control only ever produces one drawer's worth —
             it is drawn inside one box's walk — so it composes the keys rather than gaining a
             second shape. `cardKey` is the one spelling. */
          if (indices.length > 0) carryScope({ keys: indices.map((index) => cardKey(box, index)) })
          else clearCarriedScope()
        }}
      >
        <Icon name="play" size={13} />
        {box === null
          ? 'Runs'
          : indices.length > 0
            ? `Run ${indices.length} ticked`
            : 'Run this box'}
        <Icon name="arrowRight" size={13} />
      </a>
    </div>
  )
}
