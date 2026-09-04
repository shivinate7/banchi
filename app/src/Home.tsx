import { useEffect, useState, type CSSProperties } from 'react'
import {
  cropPreview,
  getBoxes,
  getInventory,
  getOrders,
  getPricingWorklist,
  getRuns,
  getStatus,
  photoUrl,
} from './server'
import type {
  BoxRecord,
  InventoryCard,
  OrdersPayload,
  PricingWorklist,
  RunSummary,
  ServerStatus,
} from './types'
import { Button, cropStyle, Icon, type Crop, type IconName } from './kit'
import { StagePill, stageOf, whenLabel } from './RunsStage'
import { hubState } from './OrdersHubStore'
import './Home.css'

/* BANCHI HOME — the one page where the product is drawn as a picture: the six-stage spine
   with live counts under each stage, the boxes, the recent runs, and one primary action.

   Every figure here is the SAME figure the stage's own screen draws — a run's stage comes from
   `RunsStage.stageOf`, the pull backlog from the ledger's own `wanted − recorded`, the pricing
   count from the worklist's roster — so Home can never be a step ahead of the screen it links. */

type Loaded<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed' }

function useLoad<T>(load: () => Promise<T>): Loaded<T> {
  const [result, setResult] = useState<Loaded<T>>({ state: 'loading' })
  useEffect(() => {
    let alive = true
    load()
      .then((value) => {
        if (alive) setResult({ state: 'ready', value })
      })
      .catch(() => {
        if (alive) setResult({ state: 'failed' })
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return result
}

/* ---- the hero deck ----------------------------------------------------------------------
 *
 * IT DRAWS REAL CARDS, and it used to draw a fixture: a painted gradient under the name
 * "Headless Resurrection" at a location that card has never occupied. A picture of the product
 * on the product's own front page has to be the product, or the first thing this screen teaches
 * is that it is a mock-up.
 *
 * IT IS BUILT TWICE, AND THAT IS THE POINT. `GET /boxes` is already on this screen's critical
 * path, and a box's `next_index` high-water mark plus `GET /photo/<box>/<index>` is enough to
 * put the last three photographs on screen with NO extra request and no waiting. That is the
 * first pass. The second arrives when `GET /inventory` lands (160 ms warm, measured on a
 * healthy server) and upgrades the same three frames to the cards themselves: the name, the
 * number, the finish, and the exact place the front one sits in.
 *
 * So the hero is never empty while something loads, and never poorer than the data allows.
 *
 * WHAT IT WILL NOT DO IS INVENT A NAME. Until the card map lands there is no name to draw, and
 * the fixture's whole sin was drawing one anyway; the first pass says the box, by its real
 * name, and nothing more. An index whose photograph was undone or reclaimed (D89) simply does
 * not draw and the frame stays. */

const DECK_DEPTH = 3

type DeckCard = {
  readonly key: string
  readonly box: number
  readonly index: number
  readonly photo: string
  /** Present once the card map has landed; absent on the first pass. */
  readonly card: InventoryCard | null
}

/** The finish claim, as a word rather than an enum member. */
function finishOf(card: InventoryCard): string | null {
  const raw = card.metadata_finish
  const one = Array.isArray(raw) ? raw[0] : raw
  if (typeof one !== 'string' || one.trim() === '') return null
  return one.charAt(0).toUpperCase() + one.slice(1).replace(/_/g, ' ')
}

/* THE HERO IS CROPPED TO THE CARD, by the same reading the pipeline uses.
 *
 * A rig photograph is mostly stand: the card sits at [126, 741, 1770, 3038] inside a
 * 2160x3840 frame on this box, so nearly a fifth of the height above it is bracket and desk.
 * Drawn `cover`, the hero showed that. `POST /pipeline/crop-preview` is the SAME detector the
 * batch reading uses (`geometry/detect.py`), it is free, it calls no model, and it already
 * returns the rectangle — so the front card is framed on what the pipeline itself thinks the
 * card is, rather than on a second guess written here.
 *
 * The arithmetic is `cropStyle` in the kit, beside `.bn-crop`: the worklist's thumbnails want
 * exactly the same sum over a much smaller window, and it is the half that goes subtly wrong in
 * silence. What stays here is the POLICY — one card, one request.
 *
 * FRONT CARD ONLY: one request, and it is the only photograph not mostly occluded by the one
 * in front of it. A refusal (`crop_refused`, no rect, an unreadable frame, a server that is
 * not there) simply leaves `cover` in place — the deck was already correct before this. */

/* Where the hero's window sits on the card: it is roughly square and a card is not, so only
   about two-fifths of the height can show. Centred, that lands on the rules text and cuts the
   art off; this is where the art and the name are. */
const FOCUS = 0.34

/** First pass: the last few indices of the newest box that holds cards. No extra request. */
function deckFromBoxes(boxes: BoxRecord[] | null): { cards: DeckCard[]; box: BoxRecord | null } {
  if (boxes === null) return { cards: [], box: null }
  const holding = boxes.filter((b) => b.next_index > 1 && b.cards > 0)
  if (holding.length === 0) return { cards: [], box: null }
  const box = holding.reduce((newest, one) => (one.box > newest.box ? one : newest), holding[0]!)
  const cards: DeckCard[] = []
  for (let back = 0; back < DECK_DEPTH; back += 1) {
    const index = box.next_index - 1 - back
    if (index < 1) break
    cards.push({ key: `${box.box}/${index}`, box: box.box, index, photo: photoUrl(box.box, index), card: null })
  }
  return { cards, box }
}

/* Second pass: the newest IDENTIFIED cards in the store, as the cards they are.
 *
 * IDENTIFIED, NOT MERELY CAPTURED, on the owner's ruling. Sorting by `captured_at` alone puts
 * whatever came off the rig last at the front — which, in the window between a feeder session
 * and its run, is a card with no name, no number and no finish, and the hero becomes a blank
 * frame on the product's own front page. (Measured on this store: 1,520 identified on hand and
 * 7 photographed but unnamed, so the case is real rather than theoretical.) A card the pipeline
 * has resolved always has something to say, so the deck waits for one. */
function deckFromCards(cards: Record<string, InventoryCard> | null): DeckCard[] {
  if (cards === null) return []
  const gone = new Set(['sold', 'retired', 'moved'])
  return Object.entries(cards)
    .filter(
      ([, card]) =>
        card.photo !== null &&
        card.captured_at !== null &&
        !gone.has(card.state) &&
        card.name !== null &&
        card.name !== '',
    )
    .sort((a, b) => String(b[1].captured_at).localeCompare(String(a[1].captured_at)))
    .slice(0, DECK_DEPTH)
    .map(([key, card]) => ({
      key,
      box: card.box,
      index: card.index,
      photo: photoUrl(card.box, card.index),
      card,
    }))
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 5) return 'Still up'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

type Stage = {
  readonly path: string
  readonly icon: IconName
  readonly label: string
  readonly figure: string
  /** A figure that is a placeholder rather than a count draws quieter. */
  readonly quiet?: boolean
  readonly note: string
  readonly tone?: 'accent' | 'warn' | 'ok'
}

export function Home() {
  const status = useLoad<ServerStatus>(getStatus)
  const boxes = useLoad<BoxRecord[]>(async () => (await getBoxes()).boxes)
  const runs = useLoad<RunSummary[]>(getRuns)
  const orders = useLoad<OrdersPayload>(getOrders)
  const pricing = useLoad<PricingWorklist>(() => getPricingWorklist())
  /* The card map, for the hero only, on its own load so no panel above waits on it. 160 ms
     warm; the deck is already on screen from `boxes` before it lands. */
  const shelf = useLoad<Record<string, InventoryCard>>(async () => (await getInventory()).cards)
  const fromBoxes = deckFromBoxes(boxes.state === 'ready' ? boxes.value : null)
  const fromCards = deckFromCards(shelf.state === 'ready' ? shelf.value : null)
  /* The box-derived pass is a placeholder for the moment before the card map lands, so it
     yields to the named cards the instant they arrive. */
  const deck = fromCards.length > 0 ? fromCards : fromBoxes.cards
  const deckBox = fromBoxes.box
  const front = deck[0]
  const frontCard = front?.card ?? null
  const [crop, setCrop] = useState<Crop | null>(null)
  const frontKey = front === undefined ? null : `${front.box}/${front.index}`
  useEffect(() => {
    setCrop(null)
    if (front === undefined) return
    let alive = true
    cropPreview({ box: front.box, indices: [front.index], crop: true })
      .then((preview) => {
        const sample = preview.sample
        if (!alive || sample.rect == null || sample.frame == null) return
        if (sample.crop_refused != null) return
        setCrop({ frame: sample.frame, rect: sample.rect })
      })
      .catch(() => {
        /* No crop is not a failure: the deck already draws correctly without one, and a
           response this walk cannot read has to fail the same way a dead server does. */
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frontKey])

  const boxCount = boxes.state === 'ready' ? boxes.value.length : null
  const onHand = boxes.state === 'ready' ? boxes.value.reduce((n, b) => n + (b.on_hand ?? b.cards - b.sold - b.retired - b.moved), 0) : null
  const sold = boxes.state === 'ready' ? boxes.value.reduce((n, b) => n + b.sold, 0) : null
  const review = status.state === 'ready' ? status.value.queues.review : null
  const parked = status.state === 'ready' ? status.value.queues.parked : null
  const lastBox = boxes.state === 'ready' ? [...boxes.value].sort((a, b) => b.box - a.box)[0] : undefined
  const liveRuns = runs.state === 'ready' ? runs.value.filter((r) => r.live).length : null

  /* Orders: the figure is open orders; the note is the PULL BACKLOG the Orders screen itself
     draws as "N of M pulled" — `wanted − recorded` over the ledger's open rows. The resolver's
     `outstanding` is a different fact (copies the store cannot FIND) and is named as such. */
  const openRows = orders.state === 'ready' ? orders.value.orders.filter((o) => o.open) : null
  const openOrders = openRows === null ? null : openRows.length
  const toPull = openRows === null ? null : openRows.reduce((n, o) => n + Math.max(0, o.wanted - o.recorded), 0)
  const unfindable = orders.state === 'ready' ? orders.value.resolution.orders.reduce((n, o) => n + (o.outstanding ?? 0), 0) : 0

  /* Pricing: the runs the worklist says still owe an answer — `owes` is emit's own reason. */
  const runsToPrice = pricing.state === 'ready' ? pricing.value.roster.filter((r) => r.open && r.owes.length > 0).length : null

  /* Shipping: the export the hub last read, if one is in hand. */
  const batch = hubState().batch

  const stages: Stage[] = [
    {
      path: '/capture',
      icon: 'camera',
      label: 'Capture',
      figure: lastBox ? `Box ${lastBox.box}` : '—',
      note: lastBox ? `${plural(lastBox.cards, 'card')}${lastBox.name ? ` · ${lastBox.name}` : ''}` : 'no boxes yet',
    },
    {
      path: '/runs',
      icon: 'play',
      label: 'Runs',
      figure: liveRuns === null ? '—' : liveRuns > 0 ? String(liveRuns) : runs.state === 'ready' ? String(runs.value.length) : '—',
      note: liveRuns !== null && liveRuns > 0 ? 'running now' : 'runs on file',
      tone: liveRuns !== null && liveRuns > 0 ? 'accent' : undefined,
    },
    {
      path: '/review',
      icon: 'inbox',
      label: 'Review',
      figure: review === null ? '—' : String(review),
      note: review === 0 ? 'nothing waiting' : parked ? `to answer · ${parked} parked` : 'to answer',
      tone: review ? 'warn' : review === 0 ? 'ok' : undefined,
    },
    {
      path: '/pricing',
      icon: 'tag',
      label: 'Pricing',
      figure: runsToPrice === null ? '—' : String(runsToPrice),
      note: runsToPrice === null ? (pricing.state === 'failed' ? 'worklist not read' : 'reading the worklist…') : runsToPrice === 0 ? 'nothing to price' : `${runsToPrice === 1 ? 'run' : 'runs'} to price`,
      tone: runsToPrice ? 'warn' : runsToPrice === 0 ? 'ok' : undefined,
    },
    {
      path: '/orders',
      icon: 'cart',
      label: 'Orders',
      figure: openOrders === null ? '—' : String(openOrders),
      note:
        openOrders === null
          ? orders.state === 'failed'
            ? 'ledger not read'
            : 'reading the ledger…'
          : openOrders === 0
            ? 'no open orders'
            : toPull
              ? `${plural(toPull, 'copy', 'copies')} to pull${unfindable ? ` · ${unfindable} not found` : ''}`
              : `open · every copy pulled${unfindable ? ` · ${unfindable} not found` : ''}`,
      tone: toPull ? 'warn' : openOrders === 0 ? 'ok' : undefined,
    },
    {
      path: '/shipping',
      icon: 'truck',
      label: 'Shipping',
      figure: batch ? String(batch.shipments) : '—',
      quiet: !batch,
      note: batch ? `${batch.shipments === 1 ? 'shipment' : 'shipments'} in lanes · ${batch.name}` : 'no export read yet',
    },
  ]

  return (
    <main className="home bn-page">
      <section className="home-hero">
        <div className="home-hero-text">
          <span className="bn-eyebrow">{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</span>
          <h1 className="home-title">{greeting()}.</h1>
          <p className="home-lede">
            {onHand === null || boxCount === null || sold === null ? (
              <span className="bn-skeleton" style={{ display: 'inline-block', width: 260, height: 18 }} />
            ) : (
              <>
                <strong>{onHand.toLocaleString()}</strong> cards on hand in <strong>{boxCount}</strong> {boxCount === 1 ? 'box' : 'boxes'}
                {sold > 0 ? (
                  <>
                    {' '}
                    · <strong>{sold.toLocaleString()}</strong> sold
                  </>
                ) : null}
                . Every one has an address.
              </>
            )}
          </p>
          <div className="home-actions">
            <Button variant="primary" size="lg" icon="camera" kbd=",C" onClick={() => (window.location.hash = '#/capture')}>
              Start capturing
            </Button>
            <Button size="lg" icon="search" onClick={() => (window.location.hash = '#/inventory')}>
              Find a card
            </Button>
          </div>
        </div>
        <div className="home-hero-art">
          {front === undefined || deckBox === null ? (
            /* Nothing photographed yet: the frames alone, and no name. A deck that invents a
               card is the defect this replaced. */
            <div className="home-deck" aria-hidden="true" data-empty="true">
              {Array.from({ length: DECK_DEPTH }, (_, at) => (
                <div key={at} className={`home-deck-card home-deck-card-${DECK_DEPTH - at}`} />
              ))}
            </div>
          ) : (
            <a
              className="home-deck"
              href={`#/inventory?box=${frontCard?.box ?? deckBox.box}`}
              aria-label={
                frontCard === null
                  ? `The last cards photographed into box ${deckBox.box}${
                      deckBox.name === null ? '' : `, ${deckBox.name}`
                    }. Open the box on Inventory.`
                  : `${frontCard.name ?? 'The last card you photographed'}, ${
                      frontCard.place?.label ?? `box ${frontCard.box}`
                    }. Open it on Inventory.`
              }
            >
              {deck
                .slice()
                .reverse()
                .map((one, at) => {
                  const depth = deck.length - at
                  return (
                    <div key={one.key} className={`home-deck-card home-deck-card-${depth}`}>
                      <span className="home-deck-frame">
                        <img
                          className="home-deck-photo bn-crop"
                          src={one.photo}
                          alt=""
                          loading="lazy"
                          decoding="async"
                          data-cropped={depth === 1 && crop !== null ? 'true' : undefined}
                          style={depth === 1 ? cropStyle(crop, FOCUS) : undefined}
                          /* Undone, re-shot or reclaimed (D89): leave the frame, never a broken
                             image glyph. */
                          onError={(event) => {
                            event.currentTarget.style.visibility = 'hidden'
                          }}
                        />
                      </span>
                      {depth === 1 && one.card !== null ? (
                        <>
                          <div className="home-deck-name">{one.card.name ?? 'Not identified yet'}</div>
                          <div className="home-deck-meta">
                            {[one.card.number_display ?? one.card.number, finishOf(one.card)]
                              .filter((part): part is string => typeof part === 'string' && part !== '')
                              .join(' · ')}
                          </div>
                        </>
                      ) : null}
                    </div>
                  )
                })}
              <div className="home-deck-address" aria-hidden="true">
                <Icon name="pin" size={14} />
                {frontCard?.place?.label != null ? (
                  <span className="home-deck-card-no">{frontCard.place.label}</span>
                ) : (
                  <>
                    <span>Box {deckBox.box}</span>
                    {deckBox.name === null ? null : (
                      <>
                        <span className="home-deck-sep">·</span>
                        <span className="home-deck-card-no">{deckBox.name}</span>
                      </>
                    )}
                  </>
                )}
              </div>
            </a>
          )}
        </div>
      </section>

      <section className="home-spine bn-stagger" aria-label="The workflow">
        {stages.map((stage, i) => (
          <a
            key={stage.path}
            className={`home-stage ${stage.tone ? `home-stage-${stage.tone}` : ''}`}
            href={`#${stage.path}`}
            style={{ '--i': i + 2 } as CSSProperties}
          >
            <span className="home-stage-icon">
              <Icon name={stage.icon} size={18} />
            </span>
            <span className="home-stage-label">{stage.label}</span>
            <span className={`home-stage-figure${stage.quiet ? ' home-stage-figure-quiet' : ''}`}>{stage.figure}</span>
            <span className="home-stage-note" title={stage.note}>
              {stage.note}
            </span>
            {i < stages.length - 1 ? <Icon name="chevronRight" size={14} className="home-stage-arrow" /> : null}
          </a>
        ))}
      </section>

      <section className="home-grid2">
        <div className="bn-panel home-panel">
          <div className="bn-panel-head">
            <span className="bn-section-title">
              <Icon name="box" size={16} /> Boxes
            </span>
            <a className="home-more" href="#/inventory">
              Browse <Icon name="arrowRight" size={14} />
            </a>
          </div>
          <div className="home-boxes">
            {boxes.state === 'loading' ? (
              Array.from({ length: 4 }, (_, i) => <div key={i} className="bn-skeleton home-skel-row" />)
            ) : boxes.state === 'failed' ? (
              <p className="home-empty">The server did not answer.</p>
            ) : boxes.value.length === 0 ? (
              <p className="home-empty">No boxes yet. Capture a card to make the first one.</p>
            ) : (
              boxes.value.map((box) => {
                const held = box.on_hand ?? box.cards - box.sold - box.retired - box.moved
                const pct = box.cards > 0 ? Math.round((held / box.cards) * 100) : 0
                const name = box.name ?? `Box ${box.box}`
                return (
                  <a key={box.box} className="home-box" href={`#/inventory?box=${box.box}`}>
                    <span className="home-box-num">{box.box}</span>
                    <span className="home-box-text">
                      <span className="home-box-name" title={name}>
                        {name}
                      </span>
                      <span className="home-box-meta">
                        {held.toLocaleString()} on hand · {box.sold} sold{box.state === 'closed' ? ' · sealed' : ''}
                      </span>
                    </span>
                    <span className="home-box-bar" title={`${pct}% on hand`}>
                      <span style={{ width: `${pct}%` }} />
                    </span>
                    <span className="home-box-count">{box.cards}</span>
                  </a>
                )
              })
            )}
          </div>
        </div>

        <div className="bn-panel home-panel">
          <div className="bn-panel-head">
            <span className="bn-section-title">
              <Icon name="history" size={16} /> Recent runs
            </span>
            <a className="home-more" href="#/runs">
              All runs <Icon name="arrowRight" size={14} />
            </a>
          </div>
          <div className="home-runs">
            {runs.state === 'loading' ? (
              Array.from({ length: 4 }, (_, i) => <div key={i} className="bn-skeleton home-skel-row" />)
            ) : runs.state === 'failed' ? (
              <p className="home-empty">The server did not answer.</p>
            ) : runs.value.length === 0 ? (
              <p className="home-empty">No runs yet. Identify a box from the Runs screen.</p>
            ) : (
              runs.value.slice(0, 6).map((run) => {
                const boxLabel = `${run.box ? `Box ${run.box}` : 'Run'}${run.box_name ? ` · ${run.box_name}` : ''}`
                return (
                  <a key={run.run} className="home-run" href={`#/runs?run=${encodeURIComponent(run.run)}`}>
                    <span className="home-run-text">
                      <span className="home-run-box" title={boxLabel}>
                        {boxLabel}
                      </span>
                      <span className="home-run-name bn-mono">{run.run}</span>
                    </span>
                    <span className="home-run-when">{whenLabel(run.updated_at ?? run.created_at)}</span>
                    <StagePill stage={stageOf(run)} />
                  </a>
                )
              })
            )}
          </div>
        </div>
      </section>
    </main>
  )
}
