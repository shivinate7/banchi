import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'

import { readUpload } from './csvUpload'
import { Button, EmptyState, Icon, Money, Notice, OrderLink, type IconName } from './kit'
import { toast } from './kit/toast'
import { SHIP_LANES, setHub, useHub } from './OrdersHubStore'
import { describeFailure, fillShippingStamps, forgetShippingExport, readShippingExport, shippingFileUrl } from './server'
import type { Failure } from './server'
import type { OrderRow, OrdersPayload, ShippingLane, ShippingReason, ShippingRow } from './types'
import './Shipping.css'

/* MUST BE MODULE-LOCAL, AND THAT IS THE WHOLE REASON IT IS DECLARED HERE RATHER THAN
 * IMPORTED. Vite substitutes `import.meta.env.VITE_DEMO` with a literal at build time, so
 * this folds to `false` in an ordinary build and Rollup then eliminates the branch and the
 * dynamic `import()` inside it. An IMPORTED constant does not fold: it stays a live binding
 * across the module boundary, the branch survives, and the chunk is emitted. Measured — a
 * first version exported `IS_DEMO` from `server.ts`, and a normal build shipped
 * `demoCamera-*.js` plus three references to `demoStream` in the main bundle. Three
 * declarations of one expression is the price of the guard actually working. */
const IS_DEMO = __BN_DEMO__


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

/* Not exported. Nothing outside this file has ever read it — `Orders.tsx` carries its own
 * `ORDER_LANE_LABEL` — and the export was enough on its own to stop React Refresh updating
 * this module in place, so every edit to the Ship stage reloaded the whole page. */
const LANE_LABEL: Record<ShippingLane, string> = {
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

/** The two reasons that ARE a lane's own rule, restated: `LANE_HEAD` already says "cards only,
 *  under $50" and "$50 or more". A card whose reason is one of these carries no fact its lane
 *  header did not already give it (TXT-01). Every other reason is a card that reached its lane
 *  on different ground, or an abstention the header cannot explain by itself, and keeps its own
 *  sentence. */
const LANE_OWN_REASON: Partial<Record<ShippingReason, ShippingLane>> = {
  cards_only: 'envelope',
  value_at_threshold: 'parcel',
}

/** The reason sentence, or null where the lane header already said it. Always shown on the
 *  Needs-a-look lane: its header names no single ground, so each abstention still has to say
 *  which one it is. */
function reasonSentenceOf(row: ShippingRow): string | null {
  if (LANE_OWN_REASON[row.reason] === row.lane) return null
  return REASON_SAYS[row.reason]
}

/** The weight and item-count figures, with every ABSENT figure drawing nothing at all. A
 *  missing number is never rendered as `0`: the router abstains precisely because a figure is
 *  absent, and `0.0000 oz/item` under "no usable weight" would undo that in the one place the
 *  operator looks. `row.value` is drawn separately, through the kit's `Money` (D221/R2-money),
 *  because it is money and this array is plain strings.
 *
 *  THE WEIGHT DRAWS ONLY WHERE IT IS EVIDENCE (TXT-04). `cards_only` and `value_at_threshold`
 *  are the two reasons a lane's own rule already explains (see `LANE_OWN_REASON`); the ratio
 *  that put the row there is, on those two reasons, the plain per-card constant on nearly
 *  every row — the same figure repeated with nothing to say. `non_card_signal` and
 *  `sub_single_weight` are the two reasons the ratio itself is the finding, so the number
 *  stays, rounded to what a person reads rather than the module's four decimal places. */
function figuresOf(row: ShippingRow): string[] {
  const parts: string[] = []
  if (row.weight_per_item_oz !== null && (row.reason === 'non_card_signal' || row.reason === 'sub_single_weight')) {
    parts.push(`${Number(row.weight_per_item_oz).toFixed(2)} oz each`)
  }
  if (row.item_count !== null) parts.push(`${row.item_count} item${row.item_count === 1 ? '' : 's'}`)
  return parts
}

/** Certain or inferred, on judged rows only. An abstention is neither — it is the absence of
 *  a claim — so an unjudged row draws no word. */
function qualityOf(row: ShippingRow): 'Certain' | 'Inferred' | null {
  if (row.lane === 'unjudged') return null
  return row.certain ? 'Certain' : 'Inferred'
}

/** The full sentence behind the quality icon (TXT-03): the word first, then what it means, so
 *  the tooltip and the accessible name carry what the visible face no longer does. */
function qualityTitleOf(row: ShippingRow): string {
  return row.certain
    ? 'Certain — the export said so outright'
    : 'Inferred — read from the weight and value on the row'
}

function keptOf(seconds: number): string {
  return `kept ${Math.round(seconds / 60)} min`
}

/** Whether the viewport is a phone, for the one thing that changes shape there: a freshly
 *  loaded batch's lanes start folded (UX-016/D-ship-lanes-collapse) rather than all three open,
 *  because the Needs-a-look lane — the one that needs a person — could sit 32,000 px down a
 *  37,000 px page. The same convention `ReviewQueue.tsx`, `Pricing.tsx`, `Orders.tsx` and
 *  `BoxBrowse.tsx` already use. */
function usePhone(): boolean {
  const query = '(max-width: 767px)'
  const [phone, setPhone] = useState(() => (typeof window === 'undefined' ? false : window.matchMedia(query).matches))
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setPhone(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return phone
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
  const phone = usePhone()

  const readFile = async (chosen: File) => {
    setBusy('read')
    setHub({ gone: null })
    setFailure(null)
    try {
      const answer = await readShippingExport(await readUpload(chosen))
      /* EVERY READ STARTS WITH EVERY LANE SHOWING ITS OWN CONTENT — except on a phone, where D61
         (amended: D-ship-lanes-collapse) folds all three shut so the operator sees three counts,
         not a 37,000 px scroll, before choosing which to open. A collapsed lane is about the
         file on screen; carrying it across a new file would hide orders the operator has never
         seen, so a fresh read still resets to the width's own default rather than to whatever
         was open before. */
      setHub({ batch: answer, lanes: phone ? new Set() : new Set(SHIP_LANES) })
      toast({
        kind: 'ok',
        icon: 'truck',
        title: 'Export read',
        // D218: `toast.body` is a plain string, so this is a sentence rather than two elements
        // joined by a typed dot.
        body: `Read ${answer.shipments} order${answer.shipments === 1 ? '' : 's'} from ${answer.name}.`,
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

  /* THE PUBLISHED DEMO HAS NOBODY TO HAND IT A FILE, so it hands itself one.
   *
   * This stage reads nothing on mount by design — the note at the top of this file says why,
   * and that is right at the desk, where the operator arrives holding an export. A viewer
   * clicking a shared link is not holding anything, and every other screen in the demo fills
   * itself, so this one would be the single blank stage of six for a reason that is about
   * hardware rather than about the product.
   *
   * The content is ignored in demo mode: `demoServer.ts` answers this POST with the batch
   * that was recorded from `fixtures/orders-shipping.csv` — anonymised at rest, every row
   * reading `Buyer001 Placeholder`. Runs once, and only when nothing has been read yet, so
   * a viewer who then drops their own file keeps it. */
  const demoLoaded = useRef(false)
  useEffect(() => {
    if (!IS_DEMO || demoLoaded.current || batch !== null) return
    demoLoaded.current = true
    void (async () => {
      try {
        /* The name is what the screen shows above the lanes, so it says where this came
           from rather than pretending a file was chosen. The content is ignored. */
        const frozen = { name: 'orders-shipping.csv (demo)', content: '' }
        /* Bound, then folded — the same shape `readFile` above uses, and what
           `make screen-freshness` looks for: a write whose answer goes back into the screen
           rather than one that leaves it guessing. */
        const answer = await readShippingExport(frozen)
        setHub({ batch: answer, lanes: phone ? new Set() : new Set(SHIP_LANES) })
      } catch {
        /* Left to the empty state, which is the honest thing to draw and already exists. */
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch])

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

  /* THE PRESS THAT FILLS THE LABEL'S THREE CORNERS (T2b). Free, re-runnable and idempotent —
     the server re-asks the store every time and SETS the stamps rather than adding to them —
     so this needs no confirmation and no money gate, and pressing it twice is a no-op rather
     than a refusal.

     IT REPLACES THE BATCH WHOLESALE. The route answers the same object `readShippingExport`
     does, counts and rows together, so merging fields into the batch already held would be a
     second assembly of a payload the server has already assembled. */
  const onStamps = () => {
    void (async () => {
      if (batch === null) return
      setBusy('stamps')
      setFailure(null)
      try {
        const filled = await fillShippingStamps(batch.batch)
        setHub({ batch: filled, gone: null })
        const counts = filled.stamps
        toast({
          kind: 'status',
          icon: 'check',
          title: 'Pick locations filled',
          /* THE UNSTAMPED COUNT IS SAID OUT LOUD RATHER THAN INFERRED FROM THE DIFFERENCE. An
             order gets all three corners or none, so "8 of 20" leaves the operator to work out
             both how many were missed and why — and the why is the part that matters, because
             an order over three copies is a different problem from an order the ledger has
             never seen. */
          body:
            counts === null
              ? batch.name
              : `${counts.stamped} of ${filled.parcel_count} rows carry one; ${counts.unstamped} do not.`,
        })
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
            Never written to disk, held 30 minutes. No buyer info shown here — only in the file you
            download.
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
            title="Export has no orders"
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
              <span>
                {batch.shipments} order{batch.shipments === 1 ? '' : 's'}
              </span>
              <span>{keptOf(batch.expires_in)}</span>
            </span>
          </div>
          <div className="shipping-file-actions">
            {picker('Read another file', 'upload')}
            <Button variant="danger" icon="trash" onClick={onForget} busy={busy === 'forget'} disabled={busy !== null}>
              Forget this file
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
              <span className="shipping-file-meta">No orders in the parcel lane.</span>
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
              {/* THE COUNT IS SAID ONCE, ON THE DOWNLOAD BUTTON BELOW (TXT-05): a second count
                  here duplicated it in the same breath as the lede above and the tab beside it.
                  This line keeps only what the button cannot say — the stamp state. */}
              <p className="shipping-ship-note">
                {stamps === null
                  ? 'Rubber Stamp columns are blank until filled below.'
                  : `${stamps.stamped} of ${batch.parcel_count} carry a pick location, ${stamps.unstamped} do not — all three corners or none.`}
              </p>
              <details className="shipping-caveats">
                <summary>
                  <Icon name="info" size={14} /> What this file does not carry
                </summary>
                <p>
                  Package Weight is blank on every row. No insurance column either — that&apos;s your call in Pirate
                  Ship. This file buys and books nothing.
                </p>
              </details>
            </div>
            <div className="shipping-file-actions">
              {/* BEFORE THE DOWNLOAD, BECAUSE IT CHANGES WHAT THE DOWNLOAD CONTAINS. The file is
                  re-rendered server-side on this press, so an operator who grabs the CSV first
                  gets blank corners — reading order is the only thing that says so here. */}
              <Button
                variant="default"
                icon="pin"
                onClick={onStamps}
                busy={busy === 'stamps'}
                disabled={busy !== null}
              >
                {stamps === null ? 'Fill pick locations' : 'Refill pick locations'}
              </Button>
              <a
                className="bn-btn bn-btn-primary shipping-file shipping-download"
                href={shippingFileUrl(batch.batch, batch.file.name)}
                download={batch.file.name}
              >
                <Icon name="download" size={16} />
                <span>Download</span>
                <span className="shipping-download-count">
                  {batch.parcel_count} order{batch.parcel_count === 1 ? '' : 's'}
                </span>
              </a>
            </div>
          </section>
        )}
      </div>

      {/* THE WORD, SAID ONCE (TXT-03), rather than on up to 292 cards. The icon on each row
          still carries it, in its tooltip and its accessible name. */}
      <p className="shipping-quality-legend">
        <Icon name="check" size={11} /> Certain reads the export&apos;s own numbers.{' '}
        <Icon name="circle" size={11} /> Inferred is read from the weight.
      </p>

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

              {/* THE ID IS ALWAYS HERE, so `aria-controls` above always resolves — only its
                  content is conditional. A FOLDED LANE DRAWS NO SENTENCE (fixed alongside
                  D-ship-lanes-collapse): the chip's own count already says how many, and on a
                  phone, where every lane opens folded, three lanes repeating "N orders folded
                  away" was the exact repeated-sentence shape TXT-01 exists to catch — restating
                  a figure the chip already shows, three times over. */}
              <div id={`shipping-lane-${lane}`}>
                {!on ? null : rows.length === 0 ? (
                  <p className="shipping-lane-empty">No orders in this lane.</p>
                ) : (
                  <ol className="shipping-list">
                    {rows.map((row, at) => {
                    const quality = qualityOf(row)
                    const figures = figuresOf(row)
                    const known = ledger.get(row.order) ?? null
                    const sentence = reasonSentenceOf(row)
                    return (
                      <li
                        key={row.order}
                        className={`shipping-row shipping-row-${row.lane}`}
                        style={{ animationDelay: `${Math.min(at, 12) * 30}ms` }}
                      >
                        <div className="shipping-row-top">
                          <span className="shipping-order">
                            {known === null ? row.order : <OrderLink orderKey={known.key}>{row.order}</OrderLink>}
                          </span>
                          {quality === null ? null : (
                            <span
                              className={`shipping-quality shipping-quality-${row.certain ? 'certain' : 'inferred'}`}
                              title={qualityTitleOf(row)}
                              aria-label={qualityTitleOf(row)}
                            >
                              <Icon name={row.certain ? 'check' : 'circle'} size={11} aria-hidden="true" />
                            </span>
                          )}
                        </div>
                        {sentence === null ? null : <p className="shipping-says">{sentence}</p>}
                        {row.value === null && figures.length === 0 ? null : (
                          <div className="shipping-row-meta">
                            <span className="shipping-figures">
                              {/* D221/R2-money: a dollar figure is drawn only through the kit's
                                  `Money`, never a hand-rolled `$${...}` template. */}
                              {row.value === null ? null : (
                                <span className="shipping-figure">
                                  <Money value={Number(row.value)} />
                                </span>
                              )}
                              {figures.map((figure) => (
                                <span key={figure} className="shipping-figure">
                                  {figure}
                                </span>
                              ))}
                            </span>
                          </div>
                        )}
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
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
