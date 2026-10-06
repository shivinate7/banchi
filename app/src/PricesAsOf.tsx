/**
 * "Prices as of 5:18 AM" and the one press that brings everything current.
 *
 * THE TIME IS THE CATALOG STEP'S FINISH, never the sales history's: history has its own "through"
 * date and never claims the page's time (`docs/specs/stale-listings.md`, 7b). A failed try keeps
 * the last good time and says why. THE PRESS IS A PRESS: a visit reads the state and posts
 * nothing, and "Try again" is the only press that sends `force`.
 *
 * TWO LINES ARE ALWAYS DRAWN, and a thin bar has its own place, so a refresh moves nothing under
 * it (D313). `--bn-*` tokens only.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Button, Icon } from './kit'
import { absoluteDate, clockTime } from './dates'
import { describeFailure, getPricesRefresh, startPricesRefresh } from './server'
import type { PricesRefreshState } from './types'
import './PricesAsOf.css'

/** How often a running refresh is asked where it is. */
const POLL_MS = 1500

const STEPS = [
  { key: 'listings', label: 'Listings' },
  { key: 'catalog', label: 'Catalog prices' },
  { key: 'history', label: 'Sales history' },
] as const

/** The second the page's prices were read: the catalog step's finish, or its last good one. */
export function asOfOf(state: PricesRefreshState | null): number | null {
  const step = state?.note?.steps?.['catalog']
  if (step === undefined) return null
  const at = step.ok ? step.at : step.last_ok_at
  return typeof at === 'number' && at > 0 ? at : null
}

/** Where "Refresh now" is, polled only while one runs. `onEnded` fires once when a run finishes.
 *  `enabled` is false where the header is not drawn (the Live tab), so nothing is read there. */
export function usePricesRefresh(onEnded: () => void, enabled: boolean) {
  const [state, setState] = useState<PricesRefreshState | null>(null)
  const [refused, setRefused] = useState<string | null>(null)
  const last = useRef<string | null>(null)
  const ended = useRef(onEnded)
  ended.current = onEnded

  const read = useCallback(() => {
    getPricesRefresh()
      .then((next) => setState(next))
      .catch(() => undefined /* No state is not a failure of this screen: the line says nothing. */)
  }, [])
  useEffect(() => {
    if (enabled) read()
  }, [enabled, read])

  const running = enabled && state?.state === 'running'
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(read, POLL_MS)
    return () => window.clearInterval(timer)
  }, [running, read])

  useEffect(() => {
    if (last.current === 'running' && state !== null && state.state !== 'running') ended.current()
    last.current = state?.state ?? null
  }, [state])

  const press = useCallback((force: boolean) => {
    setRefused(null)
    startPricesRefresh(force)
      .then(() => setState((now) => ({ note: null, done: 0, total: 0, ...now, state: 'running', step: 'listings' })))
      .catch((error) => setRefused(describeFailure(error).message))
  }, [])

  return { state, refused, press }
}

function stepIndex(state: PricesRefreshState): number {
  return Math.max(STEPS.findIndex((step) => step.key === (state.step === 'join' ? 'catalog' : state.step)), 0)
}

/** The steps so far, the live one with its count: "Listings, Catalog prices, Sales history 118 of 366". */
function stepsLine(state: PricesRefreshState): string {
  const at = stepIndex(state)
  return STEPS.slice(0, at + 1)
    .map((step, index) =>
      index === at && state.step === 'history' && state.total > 0 ? `${step.label} ${state.done} of ${state.total}` : step.label,
    )
    .join(', ')
}

function percent(state: PricesRefreshState): number {
  const within = state.step === 'history' && state.total > 0 ? state.done / state.total : 0
  return Math.round(((stepIndex(state) + within) / STEPS.length) * 100)
}

/** The sentence of the failed step, or the note's own. */
function failureOf(state: PricesRefreshState): string {
  const note = state.note
  if (note?.ok === false && note.message) return note.message
  for (const step of Object.values(note?.steps ?? {})) if (step !== undefined && !step.ok && step.message) return step.message
  return 'The refresh did not finish.'
}

export function PricesAsOf({
  state,
  refused,
  onPress,
  children,
}: {
  readonly children?: ReactNode
  readonly state: PricesRefreshState | null
  readonly refused: string | null
  readonly onPress: (force: boolean) => void
}) {
  const running = state?.state === 'running'
  const failed = refused !== null || state?.state === 'failed'
  const at = asOfOf(state)
  const today = at !== null && new Date(at * 1000).toDateString() === new Date().toDateString()
  /* THE OLD PANEL'S FACTS (price moves, the daily read, the trends read) ARE THE CHILDREN, so this is the one block that says how fresh things are. */
  const rest = '\u00a0'
  const line = failed ? (refused ?? (state === null ? '' : failureOf(state))) : running && state !== null ? stepsLine(state) : rest
  return (
    <section className="pricesasof" aria-label="Prices as of" data-state={failed ? 'failed' : running ? 'running' : 'rest'}>
      <div className="pricesasof-head">
        <p className="pricesasof-says">
          {at === null ? 'Prices have not been refreshed yet' : `Prices as of ${clockTime(at * 1000)}${today ? '' : `, ${absoluteDate(at * 1000)}`}`}
        </p>
        {failed ? (
          <Button size="sm" icon="refresh" onClick={() => onPress(true)}>
            Try again
          </Button>
        ) : null}
        <Button size="sm" icon="refresh" variant={failed ? 'quiet' : 'default'} busy={running} onClick={() => onPress(false)}>
          Refresh now
        </Button>
      </div>
      <p className="pricesasof-read" data-failed={failed ? 'true' : undefined} aria-live="polite">
        {failed ? <Icon name="alert" size={14} /> : null}
        <span className="pricesasof-read-text">{line}</span>
      </p>
      <div className="pricesasof-bar">
        {running && state !== null ? (
          <div className="bn-progress bn-progress-sm" role="progressbar" aria-label="Refreshing prices" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent(state)}>
            <span style={{ width: `${percent(state)}%` }} />
          </div>
        ) : null}
      </div>
      {children}
    </section>
  )
}
