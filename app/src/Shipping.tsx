import { useEffect, useRef, useState } from 'react'

import { readUpload } from './csvUpload'
import {
  describeFailure,
  forgetShippingExport,
  onServerBoot,
  readShippingExport,
  shippingFileUrl,
} from './server'
import type { Failure } from './server'
import type { ShippingBatch, ShippingLane, ShippingReason, ShippingRow } from './types'
import './Shipping.css'

/* THE SHIPPING SCREEN — TCGplayer's `Orders → Export Shipping`, read into three lanes.
 *
 * `pipeline/shipping.py` is the whole argument and this file draws its answer. There are three
 * lanes and not a $50 line: an order under $50 that is all cards goes in a stamped envelope, an
 * order at or over $50 goes in a tracked parcel whatever it weighs, an order carrying something
 * that is not a card goes in a parcel whatever it cost — and the router ABSTAINS rather than
 * guessing when it cannot tell. The abstention is a third answer (D61) and this screen's first
 * job is to draw it as one.
 *
 * WHAT THIS SCREEN IS NOT, AND EACH ABSENCE IS LOAD-BEARING:
 *
 *   NO BUYER PII. No name, no street, no city, no state, no postcode — none of it is read out
 *   of the batch and none of it is rendered. The export carries all five on every row and they
 *   cross the wire exactly ONCE, inside the CSV the anchor below downloads, which is a file the
 *   operator hands to Pirate Ship and nothing this screen has ever painted. A column of buyer
 *   names on an owner screen is a page that cannot be screenshotted, and this screen has no
 *   question that a name would answer.
 *
 *   NO SORT AND NO SEARCH. The list is in the export's own order, always. A filter REMOVES and
 *   never reorders, which is what lets the operator work down the list against the pile on the
 *   desk and press a chip without losing their place.
 *
 *   NO WEIGHT FIELD, AND NO AFFORDANCE OF ANY KIND THAT PUTS A NUMBER IN `Package Weight`. The
 *   catalog constant this project holds is a SUM of per-product constants and is not a measured
 *   parcel weight; understated postage is charged back weeks later at the far end, where nobody
 *   is looking. The column ships blank on purpose and there is no control here to fill it.
 *
 *   NO INSURANCE CONTROL. That is a per-order choice the owner makes inside Pirate Ship against
 *   a value only they can see the consequence of.
 *
 *   NOTHING THAT SPENDS. Every control here reads a file, forgets a file, or hides a row.
 *
 * NO SERVER READ ON MOUNT, and that is a decision rather than an omission. There is nothing to
 * read until the operator hands this screen a file: the server holds no list of shipping
 * batches, and a screen that fetched one on arrival would invent state the server does not
 * have. The pre-read empty state says where the file comes from, which is the only thing a
 * cold arrival needs.
 */

/** The lanes, in the order the strip draws them and the order `pipeline/shipping.py:LANES`
 *  declares them. Envelope first because it is the cheap lane and the one most orders land in;
 *  unjudged last because it is the pile that needs a person. */
const LANES: readonly ShippingLane[] = ['envelope', 'parcel', 'unjudged']

/** ANNOTATED AND NEVER INFERRED. `Record<ShippingLane, string>` is what makes a fourth lane a
 *  compile error here rather than a chip that silently renders `undefined`. */
const LANE_LABEL: Record<ShippingLane, string> = {
  envelope: 'Envelope',
  parcel: 'Parcel',
  unjudged: 'Unjudged',
}

/* THE REASON, IN A SENTENCE, AND THE THREE ABSTENTIONS DO NOT SHARE ONE.
 *
 * `no_weight_data`, `no_value_data` and `sub_single_weight` all produce `unjudged`, and a
 * single "could not judge" string over all three would be the screen throwing away the only
 * thing that tells the operator what to DO about it:
 *
 *   no_weight_data      the row has a value but no usable weight, so what is IN the order is
 *                       unknown — open the order and look at what was bought.
 *   no_value_data       the row has no value at all, so the published $50 threshold cannot even
 *                       be asked — this is a malformed row, not an ambiguous order.
 *   sub_single_weight   the per-item weight is under one card, so the weight model does not
 *                       describe this order at all — the export's own arithmetic is suspect.
 *
 * Three different next actions. One string would have hidden all three behind the same shrug.
 *
 * The judged three say what was READ rather than what was CONCLUDED — "worth $50 or more",
 * "heavier per item than cards run" — because the conclusion is the lane badge beside them and
 * a sentence restating it says nothing. `non_card_signal` in particular may never say "contains
 * a playmat": `pipeline/shipping.py` is explicit that even at an 18x separation it is an
 * inference, and the quality word below is what carries that.
 */
const REASON_SAYS: Record<ShippingReason, string> = {
  value_at_threshold: 'Worth $50 or more, so tracking is required.',
  non_card_signal: 'Heavier per item than cards run, so something in it is not a card.',
  cards_only: 'Cards only, and under $50.',
  no_weight_data: 'No usable weight on the row, so what is in it is unknown.',
  no_value_data: 'No value on the row, so the threshold cannot be asked.',
  sub_single_weight: 'Lighter per item than one card, so the weight model does not apply here.',
}

/**
 * The figures, as one line, with every ABSENT figure drawing nothing at all.
 *
 * A MISSING NUMBER IS NEVER RENDERED AS `0`, and this is the whole abstention arriving at the
 * last inch. `pipeline/shipping.py` abstains precisely because a figure is absent — it refuses
 * to let a missing weight mean a light one — and a screen that printed `0.0000 oz/item` under
 * `No usable weight on the row` would undo that in the one place the operator actually looks.
 * So each part is dropped rather than defaulted, and a row with nothing to show draws no line.
 *
 * `weight_per_item_oz` IS A RENDERING AND IS NEVER COMPARED. It is a decimal string because the
 * real comparison is server-side against exact `Fraction`s over the export's own decimals — the
 * spec records a float pass manufacturing "a phantom sub-0.07 row" on a distribution whose true
 * minimum is exactly 0.07, which is the one outcome the module treats as impossible. Nothing
 * here parses it.
 */
function figuresOf(row: ShippingRow): string | null {
  const parts: string[] = []
  if (row.value !== null) parts.push(`$${row.value}`)
  if (row.weight_per_item_oz !== null) parts.push(`${row.weight_per_item_oz} oz/item`)
  if (row.item_count !== null) parts.push(`${row.item_count} item${row.item_count === 1 ? '' : 's'}`)
  return parts.length === 0 ? null : parts.join(' · ')
}

/**
 * THE QUALITY WORD, ON JUDGED ROWS ONLY.
 *
 * `certain` is exactly `reason === 'value_at_threshold'` server-side, so on a judged row this is
 * a true two-way split: a published price read against a published threshold, or an inference
 * off an 18x weight ratio. That split is the reason the router returns a reason at all — two
 * orders both land in `parcel`, one because it is worth $600 and one because it probably holds a
 * playmat, and a screen that cannot tell them apart cannot show which of its answers is worth
 * checking.
 *
 * NULL ON AN UNJUDGED ROW, because there the same word would be a third meaning wearing one
 * label: an abstention is neither certain nor inferred, it is the absence of a claim. The
 * sentence and the machine reason already say what happened.
 */
function qualityOf(row: ShippingRow): string | null {
  if (row.lane === 'unjudged') return null
  return row.certain ? 'Certain' : 'Inferred'
}

export function Shipping() {
  const [batch, setBatch] = useState<ShippingBatch | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [lanes, setLanes] = useState<ReadonlySet<ShippingLane>>(() => new Set(LANES))
  const [gone, setGone] = useState<string | null>(null)
  const pick = useRef<HTMLInputElement>(null)

  /* THE BOOT NOTICE (D73). The batch lives in the capture server's memory and nowhere else, so
     a restart takes it with it — and the `<a download>` below would go on pointing at a batch
     that no longer exists, failing as a dead download rather than as a sentence. `onServerBoot`
     fires when the server's boot id changes, which is the one observation point in the app that
     can tell; it returns its own unsubscriber, so the effect returns it directly. */
  useEffect(
    () =>
      onServerBoot(() => {
        setBatch(null)
        setGone(
          'The capture server restarted, so the export it was holding is gone. Read the file ' +
            'again.',
        )
      }),
    [],
  )

  const onPick = () => {
    void (async () => {
      const chosen = pick.current?.files?.[0]
      if (chosen === undefined) return
      setBusy('read')
      setGone(null)
      setFailure(null)
      try {
        const answer = await readShippingExport(await readUpload(chosen))
        setBatch(answer)
        /* EVERY READ STARTS WITH ALL THREE LANES SHOWING. A filter is about the file on screen;
           carrying one across a new file would hide orders the operator has never seen. */
        setLanes(new Set(LANES))
      } catch (err) {
        setFailure(describeFailure(err))
        setBatch(null)
      } finally {
        setBusy(null)
        /* Cleared so the SAME file can be picked again — a native file input fires no `change`
           when the chosen file is the one already in it, and re-reading after a restart is
           exactly that press. */
        if (pick.current !== null) pick.current.value = ''
      }
    })()
  }

  const onForget = () => {
    void (async () => {
      if (batch === null) return
      setBusy('forget')
      setFailure(null)
      try {
        await forgetShippingExport(batch.batch)
        /* Back to the pre-read state, whose sentence already says what to do next. Nothing is
           invented to confirm it: the export is gone, and the screen showing no export IS the
           receipt. */
        setBatch(null)
        setGone(null)
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(null)
      }
    })()
  }

  const toggleLane = (lane: ShippingLane) => {
    setLanes((current) => {
      const next = new Set(current)
      if (next.has(lane)) next.delete(lane)
      else next.add(lane)
      return next
    })
  }

  /* THE FILTER REMOVES AND NEVER REORDERS. `filter` over the batch's own array preserves the
     export's order exactly, which is the order the orders were printed in and the order the
     operator is working the pile in. Nothing here sorts, and nothing here may. */
  const shown = batch === null ? [] : batch.rows.filter((row) => lanes.has(row.lane))
  const stamps = batch === null ? null : batch.stamps

  return (
    <main className="screen shipping">
      <header className="shipping-head">
        {/* The title shares its line with the scope and the controls — docs/DESIGN.md's
            page-chrome rule as written, and the shape `Runs.tsx` and `ReviewQueue.tsx` already
            draw. What is on that line is what the screen is pointed at. */}
        <div className="shipping-head-top">
          <h1 className="shipping-title">Shipping</h1>
          <div className="shipping-controls">
            <span className="shipping-scope">
              {batch === null ? 'No export read' : `${batch.name} · ${batch.shipments} shipments`}
            </span>
            <label className="shipping-plain">
              Read an export
              <input
                type="file"
                accept=".csv,text/csv"
                ref={pick}
                onChange={onPick}
                disabled={busy !== null}
              />
            </label>
            {batch === null ? null : (
              <button
                type="button"
                className="shipping-plain"
                onClick={onForget}
                disabled={busy !== null}
              >
                Forget this export
              </button>
            )}
          </div>
        </div>
        <p className="shipping-lede">
          TCGplayer&apos;s Orders → Export Shipping. Every order gets a lane, and the ones this
          cannot judge stay unjudged.
        </p>
      </header>

      {gone === null ? null : (
        <div className="shipping-note">
          <p className="shipping-note-text">{gone}</p>
        </div>
      )}

      {failure === null ? null : (
        /* NO ANSWER CONTROL BESIDE IT, and no disabled retry. Every refusal this route can send
           has the same remedy — read a different file — and the file input above IS that
           control. A second button that only ever repeats the same rejection is a control that
           teaches the operator its press means nothing. The greppable code sits small beneath
           the sentence, docs/DESIGN.md's human-label-large, machine-string-small rule. */
        <div className="shipping-note">
          <p className="shipping-note-text">{failure.message}</p>
          <p className="shipping-machine">{failure.code}</p>
        </div>
      )}

      {batch === null ? (
        failure === null ? (
          <p className="shipping-empty">
            No export read yet. Take TCGplayer&apos;s Orders → Export Shipping file and read it
            here.
          </p>
        ) : null
      ) : batch.shipments === 0 ? (
        /* ITS OWN SENTENCE, NOT THE PRE-READ ONE. Falling through to "No export read yet" would
           read as though the file had been refused, and the operator would go looking for a
           fault in a file that was accepted and is simply empty. */
        <p className="shipping-empty">That export has a header and no orders in it.</p>
      ) : (
        <>
          {/* ------------------------------------------------- the tally, and the filter it is */}
          {/* ALL THREE LANES ALWAYS, INCLUDING A ZERO. A lane that vanished when it held nothing
              would make "no unjudged orders today" indistinguishable from "this build stopped
              drawing them", and the zero is the reassuring number here rather than the empty
              one. */}
          <div className="shipping-lanes" role="group" aria-label="Which lanes to show">
            {LANES.map((lane) => (
              <button
                key={lane}
                type="button"
                className={`shipping-chip shipping-chip-${lane}${
                  lanes.has(lane) ? ' shipping-chip-on' : ''
                }`}
                aria-pressed={lanes.has(lane)}
                onClick={() => toggleLane(lane)}
              >
                <span className="shipping-chip-label">{LANE_LABEL[lane]}</span>
                <span className="shipping-chip-count">{batch.lane_counts[lane]}</span>
              </button>
            ))}
          </div>

          {/* --------------------------------------------------- the file Pirate Ship imports */}
          {batch.parcel_count === 0 ? null : (
            <section className="shipping-ship">
              <p className="shipping-ship-head">The Pirate Ship import</p>
              {/* THE ANCHOR FROM `RunFiles.tsx`, AND NOT THE COMPONENT. `RunFiles` filters
                  `manifest.json` and splits on `is_import`, neither of which means anything to a
                  batch that is one file held in memory; teaching it a third mode is the drift
                  its own comment argues against. What is shared is the shape — name left, size
                  right, bordered like `.run-file` — and that is a stylesheet's job. */}
              <a
                className="shipping-file"
                href={shippingFileUrl(batch.batch, batch.file.name)}
                download={batch.file.name}
              >
                <span className="shipping-file-name">{batch.file.name}</span>
                <span className="shipping-file-size">{(batch.file.bytes / 1000).toFixed(1)} kB</span>
              </a>
              <p className="shipping-ship-note">
                {batch.parcel_count} order{batch.parcel_count === 1 ? '' : 's'} in the parcel lane,
                and only those, are in this file. Nothing else here is downloadable.
              </p>
              <p className="shipping-ship-note">
                Package Weight is blank on every row, because nothing here derives a weight from
                the catalog constant and under-stated postage is charged back weeks later at the
                far end. No insurance column is written either, because that is your per-order
                choice inside Pirate Ship. This file buys nothing and books nothing.
              </p>
              <p className="shipping-ship-note">
                {stamps === null
                  ? 'The three Rubber Stamp columns are blank: a pick location comes from the ' +
                    'order ledger, and no order has been read into it yet.'
                  : `${stamps.stamped} of ${batch.parcel_count} orders carry a pick location.`}
              </p>
              <p className="shipping-ship-note">
                Held in the capture server&apos;s memory for about{' '}
                {Math.round(batch.expires_in / 60)} minutes and nowhere else. Forget this export
                ends it now.
              </p>
            </section>
          )}

          {/* --------------------------------------------------------------------- the orders */}
          {shown.length === 0 ? (
            <p className="shipping-empty">No orders in the lanes you are showing.</p>
          ) : (
            <ol className="shipping-list">
              {shown.map((row) => {
                const quality = qualityOf(row)
                const figures = figuresOf(row)
                return (
                  <li key={row.order} className={`shipping-row shipping-row-${row.lane}`}>
                    <div className="shipping-row-top">
                      <span className="shipping-order">{row.order}</span>
                      <span className={`shipping-lane shipping-lane-${row.lane}`}>
                        {LANE_LABEL[row.lane]}
                      </span>
                      {quality === null ? null : (
                        <span className="shipping-quality">{quality}</span>
                      )}
                    </div>
                    <p className="shipping-says">{REASON_SAYS[row.reason]}</p>
                    {/* The machine string beneath the sentence, so what was on screen greps
                        against `pipeline/shipping.py`'s own constant. */}
                    <p className="shipping-reason">{row.reason}</p>
                    {figures === null ? null : <p className="shipping-figures">{figures}</p>}
                    {row.stamp === null ? null : <p className="shipping-stamp">{row.stamp}</p>}
                  </li>
                )
              })}
            </ol>
          )}
        </>
      )}
    </main>
  )
}
