/**
 * CLEAR TYPED PRICES — the mass-clear, off `#/pricing`'s header
 * (D168).
 *
 * THE OPERATOR ASKED FOR THIS AND FOR NOTHING AROUND IT: *"I also need a clear claims on
 * pricing (after several emits a lot of pricing is pre typed but stale and there's no way to
 * mass clear)"*. Offered the alternative — a typed price going stale by itself after N days —
 * they refused it: *"Just give me a mass-clear button."* So there is no expiry anywhere in this
 * file. The age control is a filter the operator points, spent by one press, and an answer
 * nobody clears stands forever.
 *
 * WHY IT IS A SHEET AND NOT A BUTTON. `inventory/prices.json` is ONE file for the whole store
 * (D86), so a clear is not scoped to what the operator is looking at unless it is scoped
 * deliberately — and an operator looking at one run's rows who presses `Clear` and loses 407
 * answers across twelve runs has been ambushed. The blast radius is therefore a CONTROL with
 * two positions, the narrower one is the default, and the figure that will go is in the
 * button's own label rather than in a tooltip. That is the only reason this is not one press.
 *
 * THE SCOPE IS THE WORKLIST AND NOT THE VISIBLE ROWS, which is the one place this screen could
 * have been more literal and should not be. `#/pricing` has filter chips and a cut-off that
 * re-partitions live, so "the rows on screen" is a set that moves as the operator toggles a
 * lens they may have set ten minutes ago — a destructive press whose meaning depends on a chip
 * is a press nobody can predict. The worklist is a thing with a name (*"Box 3, Box 4"*), it is
 * what the screen loaded, and the sheet says which runs it means.
 *
 * WHAT IT MAY REMOVE IS THE SERVER'S ANSWER, NOT THIS FILE'S. `GET /pricing` ships the
 * clearable SKUs and their ages in its envelope; everything here is set arithmetic over that
 * list. Deciding *which answers are clearable* in TypeScript would be `pipeline/corpus.py:
 * clearable` written a second time against the one file in this product that holds money —
 * D49 refused that across two languages and D103 found it happening across two Python modules.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { Button, Icon, Notice, Segmented } from './kit'
import { clearPricingAnswers, describeFailure, type Failure } from './server'
import type { PricingClearResult, PricingClearable } from './types'

import './ClearPrices.css'

/** The age windows offered, in days.
 *
 *  EVERY ONE OF THEM DRAWS ITS OWN COUNT, WHICH IS D103'S FINDING APPLIED. That entry measured
 *  a staleness GATE selecting *"177 SKUs at one day, 109 at three and at seven, and 0 at ten
 *  and at fourteen"* and ruled the zero was the argument: a window can be empty for a reason
 *  that is about the store's age rather than about the answers. The same is true here — on the
 *  owner's store today a 7-day window selects nothing at all — and the remedy is that the
 *  count sits ON the option, before the press, so an empty window is visible rather than
 *  discovered by pressing a button that then does nothing.
 *
 *  `null` IS "ANY AGE" AND IS THE DEFAULT, because a default window would be the expiry rule
 *  the owner turned down, chosen by this file instead of by them. */
const WINDOWS: readonly (number | null)[] = [null, 1, 3, 7, 14]

function windowLabel(days: number | null): string {
  return days === null ? 'Any age' : `${days}+ days`
}

export type ClearPricesProps = {
  readonly open: boolean
  readonly onClose: () => void
  /** What the server says may be cleared, and how old each one is. Absent for a server that
   *  predates this — in which case the control is not offered at all rather than offered
   *  over a guess. */
  readonly clearable: PricingClearable | null
  /** The SKUs this screen's worklist holds — the narrow scope, and the default. */
  readonly worklist: readonly string[]
  /** What to call that scope on the button and in the sheet: `Box 3, Box 4`, or the lens. */
  readonly worklistName: string
  /** The corpus digest this screen read, for the stale-write guard. */
  readonly revision?: string
  /** THE PRESS IS REFUSED WHILE THE SCREEN HAS UNSAVED WORK, and this is why the sheet has to
   *  be told. `#/pricing` autosaves the whole document; a clear landing under an unsaved
   *  keystroke would be undone by the next save, silently, which is D86's two-writer defect
   *  reached from inside one tab. */
  readonly unsaved: boolean
  readonly onCleared: (result: PricingClearResult) => void
}

export function ClearPrices({
  open,
  onClose,
  clearable,
  worklist,
  worklistName,
  revision,
  unsaved,
  onCleared,
}: ClearPricesProps) {
  const [scope, setScope] = useState<'worklist' | 'store'>('worklist')
  const [days, setDays] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const sheet = useRef<HTMLElement | null>(null)

  /* THE SHEET OPENS IN ITS SAFEST STATE EVERY TIME. A scope or a window remembered from the
     last press is a destructive default the operator did not choose this time — and this is
     one of the few controls in the product where the previous answer being restored could
     cost real work. `banchi.*` deliberately holds none of this (D27). */
  useEffect(() => {
    if (!open) return
    setScope('worklist')
    setDays(null)
    setFailure(null)
    sheet.current?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  /* THE AGES IN SCOPE. An intersection of the server's list with this screen's rows — set
     arithmetic over an answer Python already gave, never a second opinion about it. */
  const inScope = useMemo(() => {
    const all = clearable?.days ?? {}
    if (scope === 'store') return Object.entries(all)
    const rows = new Set(worklist)
    return Object.entries(all).filter(([sku]) => rows.has(sku))
  }, [clearable, scope, worklist])

  /** How many this window would take, and how many carry no date for it to read.
   *
   *  AN UNDATED ANSWER IS LEFT ALONE BY AN AGE FILTER AND NAMED. 20 of the owner's 407 carry
   *  no `at`: they predate the stamp, or the migration folded them in and D103 rules that
   *  inventing a date for one of those is refused. They are almost certainly the oldest
   *  answers in the file, and "almost certainly" is not something this repo clears money on.
   *  `Any age` takes them like any other typed price, which is what that option means. */
  const count = (window: number | null): number =>
    inScope.filter(([, age]) => (window === null ? true : age !== null && age >= window)).length

  const going = count(days)
  const undated = days === null ? 0 : inScope.filter(([, age]) => age === null).length
  const storeTotal = Object.keys(clearable?.days ?? {}).length
  const worklistTotal = useMemo(() => {
    const rows = new Set(worklist)
    return Object.keys(clearable?.days ?? {}).filter((sku) => rows.has(sku)).length
  }, [clearable, worklist])

  const press = async () => {
    if (busy || going === 0) return
    setBusy(true)
    setFailure(null)
    try {
      const result = await clearPricingAnswers({
        revision,
        /* THE SCOPE TRAVELS AS SKUS AND THE SERVER RE-DERIVES WHAT MAY GO. Sending the list
           the sheet counted would make this screen the authority on what is clearable; sending
           it as a SCOPE means a list that went stale between the read and the press removes
           fewer answers than the label said, never a different set. */
        ...(scope === 'store' ? {} : { skus: worklist }),
        ...(days === null ? {} : { olderThanDays: days }),
      })
      onCleared(result)
      onClose()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  const holds = clearable?.holds ?? 0
  const unpriced = clearable?.unknown ?? 0

  /* Portalled to <body> for the reason the markdown sheet is: `main.bn-page` keeps a filled
     transform after its enter animation, and a fixed sheet inside it would hang off the column. */
  return createPortal(
    <>
      {open ? <div className="bn-scrim" onClick={onClose} /> : null}
      <aside
        ref={sheet}
        className="bn-sheet clearprices"
        hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="clearprices-head"
        tabIndex={-1}
      >
        <header className="clearprices-top">
          <div className="clearprices-heading">
            <span className="bn-eyebrow">Removes pricing answers</span>
            <h2 className="clearprices-head" id="clearprices-head">
              Clear typed prices
            </h2>
          </div>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="clearprices-body">
          <p className="clearprices-says">
            Removes the <strong>answer</strong>, not the card — a cleared row shows the
            standing rule again. <strong>Nothing at TCGplayer changes.</strong>
          </p>

          <section className="clearprices-step" aria-labelledby="clearprices-scope">
            <h3 className="bn-section-title bn-dotline" id="clearprices-scope">
              <span>1</span>
              <span>Which answers</span>
            </h3>
            {/* THE BLAST RADIUS IS THE FIRST THING ASKED AND THE NARROW ONE IS SELECTED.
                `inventory/prices.json` is one file for the whole store (D86), so "everywhere"
                is the shape this act naturally has and is exactly why it may not be the
                default. */}
            <Segmented
              label="Which answers to clear"
              value={scope}
              options={[
                {
                  value: 'worklist',
                  label: (
                    <span className="bn-dotline">
                      <span>On this worklist</span>
                      <span>{worklistTotal}</span>
                    </span>
                  ),
                  icon: 'layers',
                },
                {
                  value: 'store',
                  label: (
                    <span className="bn-dotline">
                      <span>Everywhere</span>
                      <span>{storeTotal}</span>
                    </span>
                  ),
                  icon: 'grid',
                },
              ]}
              onChange={(next) => setScope(next)}
            />
            <p className="clearprices-scope-says">
              {scope === 'worklist' ? (
                <>
                  Only answers in <strong>{worklistName}</strong>.
                </>
              ) : (
                <>
                  <strong>Every run at once.</strong> Includes runs and boxes not on this screen.
                </>
              )}
            </p>
          </section>

          <section className="clearprices-step" aria-labelledby="clearprices-age">
            <h3 className="bn-section-title bn-dotline" id="clearprices-age">
              <span>2</span>
              <span>How old</span>
            </h3>
            <div className="clearprices-ages" role="group" aria-label="How old an answer must be">
              {WINDOWS.map((window) => {
                const n = count(window)
                return (
                  <button
                    key={String(window)}
                    type="button"
                    className="clearprices-age"
                    aria-pressed={window === days}
                    onClick={() => setDays(window)}
                  >
                    <span className="clearprices-age-label">{windowLabel(window)}</span>
                    <span className="clearprices-age-count">{n}</span>
                  </button>
                )
              })}
            </div>
            {/* ITS OWN CLASS AND NOT THE SCOPE'S. Two sentences in one sheet sharing a
                selector is a spec that cannot address either — and, read as CSS, a claim that
                these are the same kind of line when one describes a blast radius and the other
                describes a policy this feature deliberately does not have. */}
            <p className="clearprices-age-says">
              Nothing expires on its own — an answer stands until you clear it.
            </p>
          </section>

          {/* WHAT IS LEFT ALONE, SAID RATHER THAN LEFT TO BE DISCOVERED. Both of these are
              permanent: no control in this sheet reaches them, because neither is a typed
              price. */}
          <Notice tone="info" title="What this never touches" className="clearprices-spares">
            <ul className="clearprices-spare-list">
              <li>
                <strong>{holds}</strong> held back on purpose. Lift one on its own row.
              </li>
              {unpriced === 0 ? null : (
                <li>
                  <strong>{unpriced}</strong> with no catalogue price.
                </li>
              )}
              {undated === 0 ? null : (
                <li>
                  <strong>{undated}</strong> carry no date. Choose <em>Any age</em> to include them.
                </li>
              )}
            </ul>
          </Notice>

          {unsaved ? (
            <Notice tone="warn" title="Save first">
              Clearing now would be undone by the next autosave.
            </Notice>
          ) : null}

          {failure === null ? null : (
            <Notice tone="danger" title={failure.message} code={failure.code} />
          )}
        </div>

        <footer className="clearprices-foot">
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          {/* THE FIGURE IS IN THE LABEL, WHICH IS THIS REPO'S RULE FOR A PRESS THAT COSTS
              SOMETHING. A button reading "Clear" over 407 answers is the ambush this sheet
              exists to prevent, and a count in a tooltip is a count nobody reads. */}
          <Button
            variant="danger-solid"
            icon="trash"
            busy={busy}
            disabled={busy || going === 0 || unsaved}
            onClick={() => void press()}
          >
            {going === 0
              ? 'Nothing to clear'
              : `Clear ${going} typed price${going === 1 ? '' : 's'}${
                  scope === 'store' ? ' everywhere' : ''
                }`}
          </Button>
        </footer>
        <p className="clearprices-undo">
          <Icon name="undo" size={13} />
          <span>
            Undo is offered on the receipt, and it puts every answer back with the date it was
            typed on.
          </span>
        </p>
      </aside>
    </>,
    document.body,
  )
}
