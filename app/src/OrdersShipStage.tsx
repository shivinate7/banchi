import { useMemo, useRef, useState, type DragEvent } from 'react'

import { readUpload } from './csvUpload'
import { Button, EmptyState, Icon, Notice, type IconName } from './kit'
import { toast } from './kit/toast'
import { SHIP_LANES, setHub, useHub } from './OrdersHubStore'
import { describeFailure, forgetShippingExport, readShippingExport, shippingFileUrl } from './server'
import type { Failure } from './server'
import type { OrderRow, OrdersPayload, ShippingLane, ShippingReason, ShippingRow } from './types'
import './Shipping.css'

/* THE SHIP STAGE — TCGplayer's `Orders → Export Shipping`, read into three lanes.
 *
 * `pipeline/shipping.py` is the whole argument and this file draws its answer: an order under
 * $50 that is all cards goes in a stamped envelope, an order at or over $50 goes in a tracked
 * parcel whatever it weighs, an order carrying something that is not a card goes in a parcel
 * whatever it cost — and the router ABSTAINS rather than guessing when it cannot tell. The
 * abstention is a third answer (D61) and this stage draws it as the lane that needs a person.
 *
 * NO BUYER PII. No name, no street, no city, no postcode — none of it is read out of the batch
 * and none of it is rendered. It crosses the wire exactly once, inside the CSV the download
 * carries to Pirate Ship.
 *
 * NO SORT AND NO SEARCH. Each lane lists its orders in the export's own order, always. A lane
 * can be collapsed, which removes and never reorders.
 *
 * NO WEIGHT FIELD AND NO INSURANCE CONTROL. `Package Weight` ships blank on purpose (understated
 * postage is charged back weeks later) and insurance is the owner's per-order choice inside
 * Pirate Ship. Nothing here spends.
 *
 * NO SERVER READ ON MOUNT. The server holds no list of batches; there is nothing to read until
 * the operator hands this stage a file. The batch itself lives in the hub store so a switch to
 * the Pull stage and back does not lose it — and the D73 boot notice is raised THERE, by a
 * listener that outlives this stage: a restart is observed by whichever request first sees the
 * new boot id, and that request is usually another screen's (see `OrdersHubStore.ts`). */

export const LANE_LABEL: Record<ShippingLane, string> = {
  envelope: 'Envelope',
  parcel: 'Parcel',
  unjudged: 'Needs a look',
}

const LANE_ICON: Record<ShippingLane, IconName> = {
  envelope: 'mail',
  parcel: 'package',
  unjudged: 'alert',
}

const LANE_SAYS: Record<ShippingLane, string> = {
  envelope: 'Cards only and under $50. A stamped envelope.',
  parcel: '$50 or more, or something that is not a card. Tracked.',
  unjudged: 'The export could not say. Open each order and decide.',
}

/* The column head's helper line: short enough to stay whole beside the count at every width the
   three columns get. The long form above is for the guide tiles, where there is room for it. */
const LANE_HEAD: Record<ShippingLane, string> = {
  envelope: 'Cards only, under $50',
  parcel: '$50 or more, or not all cards',
  unjudged: 'Could not judge — decide by hand',
}

/* The reason, in a sentence, and the three abstentions do not share one — each names a
   different next action. The judged three say what was READ rather than what was concluded,
   because the conclusion is the lane the row sits in. */
const REASON_SAYS: Record<ShippingReason, string> = {
  value_at_threshold: 'Worth $50 or more, so tracking is required.',
  non_card_signal: 'Heavier per item than cards run, so something in it is not a card.',
  cards_only: 'Cards only, and under $50.',
  no_weight_data: 'No usable weight on the row, so what is in it is unknown.',
  no_value_data: 'No value on the row, so the threshold cannot be asked.',
  sub_single_weight: 'Lighter per item than one card, so the weight model does not apply here.',
}

/** The figures, with every ABSENT figure drawing nothing at all. A missing number is never
 *  rendered as `0`: the router abstains precisely because a figure is absent, and `0.0000
 *  oz/item` under "no usable weight" would undo that in the one place the operator looks. */
function figuresOf(row: ShippingRow): string[] {
  const parts: string[] = []
  if (row.value !== null) parts.push(`$${row.value}`)
  if (row.weight_per_item_oz !== null) parts.push(`${row.weight_per_item_oz} oz/item`)
  if (row.item_count !== null) parts.push(`${row.item_count} item${row.item_count === 1 ? '' : 's'}`)
  return parts
}

/** Certain or inferred, on judged rows only. An abstention is neither — it is the absence of
 *  a claim — so an unjudged row draws no word. */
function qualityOf(row: ShippingRow): 'Certain' | 'Inferred' | null {
  if (row.lane === 'unjudged') return null
  return row.certain ? 'Certain' : 'Inferred'
}

function minutesOf(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  return `${minutes} minute${minutes === 1 ? '' : 's'}`
}

export function ShipStage({ payload }: { readonly payload: OrdersPayload | null }) {
  const hub = useHub()
  const batch = hub.batch
  const lanes = hub.lanes
  const gone = hub.gone
  const [failure, setFailure] = useState<Failure | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [over, setOver] = useState(false)
  const pick = useRef<HTMLInputElement>(null)

  const readFile = async (chosen: File) => {
    setBusy('read')
    setHub({ gone: null })
    setFailure(null)
    try {
      const answer = await readShippingExport(await readUpload(chosen))
      /* EVERY READ STARTS WITH ALL THREE LANES SHOWING. A collapsed lane is about the file on
         screen; carrying it across a new file would hide orders the operator has never seen. */
      setHub({ batch: answer, lanes: new Set(SHIP_LANES) })
      toast({
        kind: 'ok',
        icon: 'truck',
        title: 'Export read',
        body: `${answer.shipments} order${answer.shipments === 1 ? '' : 's'} · ${answer.name}`,
      })
    } catch (err) {
      setFailure(describeFailure(err))
      setHub({ batch: null })
    } finally {
      setBusy(null)
      /* Cleared so the SAME file can be picked again — a native file input fires no `change`
         when the chosen file is the one already in it. */
      if (pick.current !== null) pick.current.value = ''
    }
  }

  const onPick = () => {
    const chosen = pick.current?.files?.[0]
    if (chosen === undefined) return
    void readFile(chosen)
  }

  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setOver(false)
    if (busy !== null) return
    const chosen = event.dataTransfer.files[0]
    if (chosen === undefined) return
    void readFile(chosen)
  }

  const onForget = () => {
    void (async () => {
      if (batch === null) return
      setBusy('forget')
      setFailure(null)
      try {
        await forgetShippingExport(batch.batch)
        setHub({ batch: null, gone: null })
        toast({ kind: 'status', icon: 'trash', title: 'Export forgotten', body: batch.name })
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(null)
      }
    })()
  }

  const toggleLane = (lane: ShippingLane) => {
    setHub((current) => {
      const next = new Set(current.lanes)
      if (next.has(lane)) next.delete(lane)
      else next.add(lane)
      return { lanes: next }
    })
  }

  /* THE LEDGER'S HALF, JOINED BY ORDER NUMBER AND VIEW-ONLY. The export says which envelope; the
     ledger says how many copies have been pulled for it. Neither side is written by this. */
  const ledger = useMemo(() => {
    const out = new Map<string, OrderRow>()
    for (const order of payload?.orders ?? []) out.set(order.number, order)
    return out
  }, [payload])

  const picker = (label: string, icon: IconName, variant: 'primary' | 'default' = 'default') => (
    <label className={`bn-btn shipping-pick${variant === 'primary' ? ' bn-btn-primary' : ''}`}>
      <Icon name={icon} size={16} />
      {label}
      <input
        type="file"
        accept=".csv,text/csv"
        ref={pick}
        onChange={onPick}
        disabled={busy !== null}
        className="bn-sr"
      />
    </label>
  )

  /* THE KIT'S NOTICE, NOT THIS SCREEN'S. Tone, title and the reason code in its own slot: a
     refusal here is drawn exactly as a refusal on Runs or Pricing is.
     NO ANSWER CONTROL BESIDE IT. Every refusal this route sends has the same remedy — read a
     different file — and the file control on this stage already is that control. */
  const notices = (
    <>
      {gone === null ? null : <Notice tone="warn" className="shipping-note" title={gone} />}
      {failure === null ? null : <Notice tone="danger" className="shipping-note" title={failure.message} code={failure.code} />}
    </>
  )

  /* ------------------------------------------------------------------------- before a file */

  if (batch === null) {
    return (
      <div className="shipping-stage">
        {/* Inside the centred column, not above it: the hero is the only content on this branch
            and a banner left-aligned beside it read as belonging to another screen. */}
        <div className="shipping-empty">
          {notices}
          <label
            className={`shipping-drop${over ? ' shipping-drop-over' : ''}`}
            data-busy={busy === 'read' ? 'true' : undefined}
            onDragOver={(event) => {
              event.preventDefault()
              if (!over) setOver(true)
            }}
            onDragEnter={(event) => {
              event.preventDefault()
              setOver(true)
            }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            <input
              type="file"
              accept=".csv,text/csv"
              ref={pick}
              onChange={onPick}
              disabled={busy !== null}
              aria-label="Read an export"
            />
            <span className="shipping-drop-art" aria-hidden="true">
              <Icon name="upload" size={24} />
            </span>
            <span className="shipping-drop-title">
              {busy === 'read' ? 'Reading the export…' : 'Drop the Export Shipping file here'}
            </span>
            <span className="shipping-drop-body">
              or <span className="shipping-drop-link">choose it</span>. It comes from TCGplayer&apos;s Orders → Export
              Shipping.
            </span>
            {busy === 'read' ? (
              <span className="bn-progress shipping-drop-progress" aria-hidden="true">
                <span />
              </span>
            ) : null}
          </label>
          <p className="shipping-empty-note">
            The file is held in the capture server&apos;s memory for half an hour and never written to disk. No
            buyer&apos;s name or address is drawn on this screen; they cross the wire once, inside the Pirate Ship file
            you download.
          </p>
          <div className="shipping-lane-guide" aria-label="The three lanes">
            {SHIP_LANES.map((lane) => (
              <div key={lane} className={`shipping-guide shipping-guide-${lane}`}>
                <span className="shipping-guide-icon">
                  <Icon name={LANE_ICON[lane]} size={16} />
                </span>
                <span className="shipping-guide-label">{LANE_LABEL[lane]}</span>
                <span className="shipping-guide-says">{LANE_SAYS[lane]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  /* ------------------------------------------------------------------- a file with no rows */

  if (batch.shipments === 0) {
    return (
      <div className="shipping-stage">
        {notices}
        <div className="bn-panel">
          <EmptyState
            icon="inbox"
            title="That export has a header and no orders in it"
            body={`${batch.name} was read and accepted. It is simply empty — read the file for a day that has orders.`}
            actions={
              <>
                {picker('Read another file', 'upload', 'primary')}
                <Button variant="danger" icon="trash" onClick={onForget} busy={busy === 'forget'} disabled={busy !== null}>
                  Forget this export
                </Button>
              </>
            }
          />
        </div>
      </div>
    )
  }

  /* ------------------------------------------------------------------------------ the lanes */

  const stamps = batch.stamps

  return (
    <div className="shipping-stage">
      {notices}

      <div className="shipping-files">
        <section className="bn-panel shipping-file-card" aria-label="The export that was read">
          <span className="shipping-file-icon" aria-hidden="true">
            <Icon name="list" size={18} />
          </span>
          <div className="shipping-file-text">
            <span className="bn-label">Export loaded</span>
            <span className="shipping-file-title" title={batch.name}>
              {batch.name}
            </span>
            <span className="shipping-file-meta">
              {batch.shipments} order{batch.shipments === 1 ? '' : 's'} · held in memory for about {minutesOf(batch.expires_in)} · nothing
              written to disk
            </span>
          </div>
          <div className="shipping-file-actions">
            {picker('Read another file', 'upload')}
            <Button variant="danger" icon="trash" onClick={onForget} busy={busy === 'forget'} disabled={busy !== null}>
              Forget
            </Button>
          </div>
        </section>

        {batch.parcel_count === 0 ? (
          <section className="bn-panel shipping-ship shipping-ship-none" aria-label="The Pirate Ship import">
            <span className="shipping-file-icon" aria-hidden="true">
              <Icon name="download" size={18} />
            </span>
            <div className="shipping-file-text">
              <span className="bn-label">Pirate Ship import</span>
              <span className="shipping-file-title">Nothing to download</span>
              <span className="shipping-file-meta">No order landed in the parcel lane, so there is no file to hand to Pirate Ship.</span>
            </div>
          </section>
        ) : (
          <section className="bn-panel shipping-ship" aria-label="The Pirate Ship import">
            <span className="shipping-file-icon shipping-file-icon-accent" aria-hidden="true">
              <Icon name="download" size={18} />
            </span>
            <div className="shipping-file-text">
              <span className="bn-label">Pirate Ship import</span>
              <span className="shipping-file-row">
                <span className="shipping-file-name" title={batch.file.name}>
                  {batch.file.name}
                </span>
                <span className="shipping-file-size">{(batch.file.bytes / 1000).toFixed(1)} kB</span>
              </span>
              <p className="shipping-ship-note">
                {batch.parcel_count} order{batch.parcel_count === 1 ? '' : 's'} in the parcel lane, and only those, are in this
                file.{' '}
                {stamps === null
                  ? 'The three Rubber Stamp columns are blank: a pick location comes from the order ledger, and no order has been read into it yet.'
                  : `${stamps.stamped} of ${batch.parcel_count} carry a pick location.`}
              </p>
              <details className="shipping-caveats">
                <summary>
                  <Icon name="info" size={14} /> What this file does not carry
                </summary>
                <p>
                  Package Weight is blank on every row, because nothing here derives a weight from the catalog constant and
                  under-stated postage is charged back weeks later at the far end. No insurance column is written either,
                  because that is your per-order choice inside Pirate Ship. This file buys nothing and books nothing.
                </p>
              </details>
            </div>
            <div className="shipping-file-actions">
              <a
                className="bn-btn bn-btn-primary shipping-file shipping-download"
                href={shippingFileUrl(batch.batch, batch.file.name)}
                download={batch.file.name}
              >
                <Icon name="download" size={16} />
                Download · {batch.parcel_count} order{batch.parcel_count === 1 ? '' : 's'}
              </a>
            </div>
          </section>
        )}
      </div>

      <div className="shipping-lanes" role="group" aria-label="The three lanes">
        {SHIP_LANES.map((lane) => {
          /* `filter` over the batch's own array preserves the export's order exactly. Nothing
             here sorts, and nothing here may. */
          const rows = batch.rows.filter((row) => row.lane === lane)
          const on = lanes.has(lane)
          return (
            <section key={lane} className={`shipping-lane-col shipping-lane-col-${lane}`} data-on={on ? 'true' : 'false'}>
              <button
                type="button"
                className={`shipping-chip shipping-chip-${lane}${on ? ' shipping-chip-on' : ''}`}
                aria-pressed={on}
                aria-controls={`shipping-lane-${lane}`}
                onClick={() => toggleLane(lane)}
              >
                <span className="shipping-chip-icon" aria-hidden="true">
                  <Icon name={LANE_ICON[lane]} size={16} />
                </span>
                <span className="shipping-chip-text">
                  <span className="shipping-chip-label">{LANE_LABEL[lane]}</span>
                  <span className="shipping-chip-says">{LANE_HEAD[lane]}</span>
                </span>
                <span className="shipping-chip-count">{batch.lane_counts[lane]}</span>
                <Icon name={on ? 'chevronUp' : 'chevronDown'} size={14} className="shipping-chip-chev" />
              </button>

              {!on ? (
                <p className="shipping-lane-hidden" id={`shipping-lane-${lane}`}>
                  {rows.length} order{rows.length === 1 ? '' : 's'} folded away
                </p>
              ) : rows.length === 0 ? (
                <p className="shipping-lane-empty" id={`shipping-lane-${lane}`}>
                  No orders in this lane.
                </p>
              ) : (
                <ol className="shipping-list" id={`shipping-lane-${lane}`}>
                  {rows.map((row, at) => {
                    const quality = qualityOf(row)
                    const figures = figuresOf(row)
                    const known = ledger.get(row.order) ?? null
                    return (
                      <li
                        key={row.order}
                        className={`shipping-row shipping-row-${row.lane}`}
                        style={{ animationDelay: `${Math.min(at, 12) * 30}ms` }}
                      >
                        <div className="shipping-row-top">
                          <span className="shipping-order">{row.order}</span>
                          {quality === null ? null : (
                            <span
                              className={`shipping-quality shipping-quality-${row.certain ? 'certain' : 'inferred'}`}
                              title={row.certain ? 'The export said so outright' : 'Read from the weight and value on the row'}
                            >
                              <Icon name={row.certain ? 'check' : 'circle'} size={11} />
                              {quality}
                            </span>
                          )}
                        </div>
                        <p className="shipping-says">{REASON_SAYS[row.reason]}</p>
                        <div className="shipping-row-meta">
                          {figures.length === 0 ? null : (
                            <span className="shipping-figures">
                              {figures.map((figure) => (
                                <span key={figure} className="shipping-figure">
                                  {figure}
                                </span>
                              ))}
                            </span>
                          )}
                          <code className="shipping-reason">{row.reason}</code>
                        </div>
                        {row.stamp === null && known === null ? null : (
                          <div className="shipping-row-foot">
                            {row.stamp === null ? null : (
                              <span className="shipping-stamp">
                                <Icon name="pin" size={13} />
                                {row.stamp}
                              </span>
                            )}
                            {known === null ? null : (
                              <span className={`shipping-pull${known.open ? '' : ' shipping-pull-done'}`}>
                                <Icon name={known.open ? 'hand' : 'check'} size={12} />
                                {known.open ? `${known.recorded} of ${known.wanted} pulled` : 'every copy pulled'}
                              </span>
                            )}
                          </div>
                        )}
                      </li>
                    )
                  })}
                </ol>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
