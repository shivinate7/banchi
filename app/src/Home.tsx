import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  getBoxes,
  getOrders,
  getPricingWorklist,
  getRecentCards,
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
import { useCardCrop } from './cardCrop'
import { Button, cropStyle, Icon, Kbd, Loading, Page, type IconName } from './kit'
import { dayMonth, weekdayDate } from './dates'
import { runsOwingPrice, standing, type Standing } from './standing'
import { DEMO_HISTORY_SCALE, inflate, photographed, ribbon, sittings, type Ribbon } from './storeHistory'
import { StagePill, stageOf, whenLabel } from './RunsStage'
import { placeWordsOf } from './position'
import { runBoxLabel } from './runScope'
import { hubState } from './OrdersHubStore'
import { useLiveCheck } from './liveCheck'
import { matchWaiting } from './autoMatch'
import { storedBoxRecency } from './deviceMemory'
import './Home.css'

/* BANCHI HOME — the one page where the product is drawn as a picture: the five-stage spine
   with live counts under each stage, the boxes, the recent runs, and one primary action.
   FIVE, NOT SIX (2026-09-24): Runs folded into Review, so the spine no longer gives Runs its
   own tile — Review's own figure carries the identify backlog too, once the review queue
   itself is empty.

   Every figure here is the SAME figure the stage's own screen draws — a run's stage comes from
   `RunsStage.stageOf`, the pull backlog from the ledger's own `wanted − recorded`, the pricing
   count from the worklist's roster — so Home can never be a step ahead of the screen it links. */

type Loaded<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed' }

function useLoad<T>(load: () => Promise<T>, again = 0): Loaded<T> {
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
    // `again` is the one reason to read twice: a write this screen made (the automatic match).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [again])
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
    /* THE SLOT ROUTE, BECAUSE THIS PASS HAS NO CARD TO GET A NAME FROM (D172). The index is
       arithmetic off the registry's `next_index` — there is no record here at all, which is
       the whole point of the first pass — so there is nothing carrying a `cid` to address
       the photograph by. The second pass below has the records and uses the name. */
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
      /* BY NAME (D172): an inventory row carries the card's own `cid`, so the hero addresses
         the photograph rather than the slot it happens to sit in. */
      photo: photoUrl(card.box, card.index, card.cid),
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

/** A BOX IS SHOWN BY ITS NAME, EVERYWHERE (the owner's ruling, 2026-09-23) — never a bare
 *  number standing for the drawer. `Box ${box.box}` is the one exception the ruling itself
 *  names: the owner's own default for a box nobody has named yet ("it can default to count+1
 *  Box as a default name"), so this is what the STORE will hand back once the backfill lands
 *  and never a second, different-looking guess drawn here in the meantime. */
function boxDisplayName(box: { readonly name: string | null; readonly box: number }): string {
  return box.name ?? `Box ${box.box}`
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

/** The ranked sentence. Renders what `standing.ts` decided and judges nothing itself. */
function StandingLine({ standing: say }: { readonly standing: Standing | null }) {
  if (say === null) return <Loading rows={1} shape="rows" className="home-standing-skel" />
  /* A row that cannot be pressed is PROSE, not a control: it drops the surface, the ring and
     the shadow, so the shape says whether there is work before the colour or the words do. */
  const body = (
    <>
      <span className="home-standing-rule" />
      {say.icon === null ? null : (
        <span className={`home-standing-ic${say.running ? ' home-standing-ic-live' : ''}`}>
          <Icon name={say.icon} size={17} />
        </span>
      )}
      <span className="home-standing-say">
        <span className="home-standing-lead">{say.lead}</span>
        {say.say.map((part, i) =>
          part.em ? (
            <strong key={i}>{part.text}</strong>
          ) : (
            <span key={i}>{part.text}</span>
          ),
        )}
      </span>
      {say.href === null ? null : (
        <span className="home-standing-go" aria-label="Go to it">
          {/* The shortcut chip is a hint, not the label. This span is decoration — a kbd
              chip and an arrow, nothing a sighted reader reads as words — so `aria-label`
              names the AFFORDANCE directly rather than parking a phrase in the reading order
              for content that has no textual reading order of its own. It replaces this
              span's own contribution to the row's accessible name (an ancestor's
              name-from-content computation reads a labelled descendant's `aria-label` in
              place of its subtree text), so a screen reader hears "go to it" once, appended
              to the row's sentence, instead of the raw shortcut string. `Kbd` still carries
              its own `aria-hidden`, matching every other kbd chip in the app; redundant
              under this label, kept for consistency. */}
          {say.kbd === null ? null : <Kbd>{say.kbd}</Kbd>}
          <Icon name="chevronRight" size={16} />
        </span>
      )}
    </>
  )
  return (
    <div className="home-standing" data-tone={say.tone}>
      {say.href === null ? (
        <div className="home-standing-row" data-press="no">
          {body}
        </div>
      ) : (
        <a className="home-standing-row" href={say.href}>
          {body}
        </a>
      )}
      {/* THE "BEHIND THAT" LINE NEVER REPEATS A SPINE FIGURE (the owner's ruling, 2026-09-24).
          `standing.ts` hands over plain sentences only — there is no figure left to draw here,
          so this is a supplementary line, never a second copy of a number 24px below. */}
      {say.behind.length === 0 && say.problem === null ? null : (
        <p className="home-standing-behind">
          {say.behind.map((label, i) => (
            <span key={i} className="home-standing-behind-lab">
              {label}
            </span>
          ))}
        </p>
      )}
      {/* The server's own words, verbatim. Never paraphrased and never swallowed. */}
      {say.problem === null ? null : (
        <p className="home-standing-problem">
          <Icon name="alert" size={13} /> <span className="bn-mono">{say.problem}</span>
        </p>
      )}
    </div>
  )
}

/** The library, and how it was made. Achromatic but for the pace ramp — see `storeHistory.ts`
 *  for why width is minutes and height is cards an hour. */
function HistoryFoot({
  status,
  boxes,
  sold,
  shelf,
  live,
}: {
  readonly status: ServerStatus | null
  readonly boxes: number | null
  readonly sold: number | null
  readonly shelf: Record<string, InventoryCard> | null
  readonly live: boolean
}) {
  const plot: Ribbon | null = useMemo(() => ribbon(inflate(sittings(shelf))), [shelf])
  if (status === null) return <div className="home-foot" />
  const realTotal = photographed(status)
  if (realTotal === 0) {
    return (
      <div className="home-foot">
        <p className="home-foot-sum home-foot-quiet">No cards yet. The library starts with the first box.</p>
      </div>
    )
  }
  /* ON HAND, from `states` alone. Not `Σ boxes[].on_hand`, whose nullable member is null
     exactly when a box could not be counted — a sum with a null in it is not a sum, and the
     fallback this replaced (`cards - sold - retired - moved` per box) invented a figure in
     precisely the case where the server had refused to give one. And not `states.identified`
     either: a card photographed and not yet identified is still on the shelf. */
  const retired = status.states.retired ?? 0
  const onHand = realTotal - (status.states.sold ?? 0) - retired

  /* THE DEMO INFLATES ITS OWN HISTORY, AND ONLY ITS HISTORY — `storeHistory.ts`'s
     `DEMO_HISTORY_SCALE` carries the whole argument and the trade the owner took. Cards ever
     photographed and cards ever sold move with the sittings so this sentence stays true to
     ITSELF; `onHand` and the box count are deliberately left real, because the boxes panel a
     few inches below draws those same two figures from the same store and they may not
     disagree on one screen. The cards that have left are then whatever the sentence needs to
     balance — derived rather than scaled, so `photographed − on hand − retired − sold` is
     still zero at any multiplier. Folded away entirely in every non-demo build. */
  let total = realTotal
  let everSold = sold
  if (__BN_DEMO__) {
    total = realTotal * DEMO_HISTORY_SCALE
    everSold = total - onHand - retired * DEMO_HISTORY_SCALE
  }
  const since = plot?.from ? dayMonth(plot.from) : null
  const newest = plot?.blocks[plot.blocks.length - 1]?.sitting ?? null
  return (
    <div className="home-foot">
      <p className="home-foot-sum">
        <b>{total.toLocaleString()}</b> photographed
        {plot === null ? null : (
          <>
            {' over '}
            <b>{plot.blocks.length + (plot.plinth?.sittings ?? 0)}</b>
            {plot.blocks.length + (plot.plinth?.sittings ?? 0) === 1 ? ' sitting' : ' sittings'}
            {since === null ? null : ` since ${since}`}
          </>
        )}
        <i aria-hidden="true" />
        {/* `on_hand` is nullable BECAUSE a box could not be counted. A sum with a null in it is
            not a sum, so the clause degrades and the sentence does not. */}
        <b>{onHand.toLocaleString()}</b> on hand
        {boxes === null ? null : <> in <b>{boxes}</b> {boxes === 1 ? 'box' : 'boxes'}</>}
        {everSold === null || everSold === 0 ? null : (
          <>
            <i aria-hidden="true" />
            {/* THIS STORE'S OWN COUNT, NOT SALES' (UX-019): Sales totals the order ledger,
                this totals every card this store has ever marked sold, and the two are
                different universes on purpose — the link is the way to the one that reasons
                about money. Also Home's one link into the loop's last stage (UX-032). */}
            <a className="home-foot-sold" href="#/revenue">
              <b>{everSold.toLocaleString()}</b> sold
            </a>
          </>
        )}
      </p>
      {plot === null ? null : <Ribbon plot={plot} live={live} />}
      {newest === null ? null : (
        <p className="home-foot-last">
          <b>{dayMonth(newest.from)}</b>
          {' — '}
          <b>{newest.cards.toLocaleString()}</b> {newest.cards === 1 ? 'card' : 'cards'}
          {newest.box === null ? null : <> into Box {newest.box}</>}
          {newest.rate === null ? '.' : (
            <>
              {' in '}
              <b>{newest.minutes < 2 ? `${Math.round(newest.minutes * 60)} seconds` : `${Math.round(newest.minutes)} minutes`}</b>
              {'. '}
              <em>{Math.round(newest.rate).toLocaleString()} an hour.</em>
            </>
          )}
        </p>
      )}
    </div>
  )
}

/** The drawing itself. Every number in it comes from `storeHistory.ribbon`. */
function Ribbon({ plot, live }: { readonly plot: Ribbon; readonly live: boolean }) {
  return (
    <svg
      className="home-ribbon"
      viewBox="0 0 620 56"
      preserveAspectRatio="none"
      role="img"
      aria-label={`${plot.blocks.length} sittings. Each block is as wide as the minutes it took and as tall as the cards an hour it ran at, so its area is its card count. Below the rule, a tick a sitting on the real calendar.`}
    >
      <line className="home-ribbon-ceil" x1="0" y1="0.5" x2="620" y2="0.5" />
      <g className="home-ribbon-blocks">
        {plot.blocks.map((b, i) =>
          b.durationless || b.w <= 0 ? null : (
            <rect
              key={b.key}
              className={b.newest && live ? 'home-ribbon-blk home-ribbon-blk-live' : 'home-ribbon-blk'}
              style={{ '--n': i, '--pace': Math.round(b.pace * 100) } as CSSProperties}
              x={b.x}
              y={b.y}
              width={b.w}
              height={b.h}
              rx={1}
            >
              <title>{`${b.sitting.cards} cards, ${Math.round(b.sitting.minutes)} min`}</title>
            </rect>
          ),
        )}
      </g>
      <line className="home-ribbon-axis" x1="0" y1="40.5" x2="620" y2="40.5" />
      <g>
        {plot.ticks.map((t) => (
          <rect
            key={t.key}
            className={t.newest ? 'home-ribbon-tick home-ribbon-tick-now' : 'home-ribbon-tick'}
            x={t.x}
            y={44}
            width={t.newest ? 2.5 : 2}
            height={8}
            rx={1}
          />
        ))}
      </g>
    </svg>
  )
}

export function Home() {
  const status = useLoad<ServerStatus>(getStatus)
  const boxes = useLoad<BoxRecord[]>(async () => (await getBoxes()).boxes)
  /* BOXES LIST MOST RECENT FIRST (the owner's ruling, 2026-09-23), off the SAME store
     `BoxBrowse`'s own rail sorts by (D142): the box this browser last reached for, then the
     box holding the most cards, then the number — read once on mount, the way that screen
     reads it, since this panel is a summary and never the place a pick gets recorded. */
  const [recency] = useState<ReadonlyMap<number, string>>(() => storedBoxRecency())
  /* A NAME FOR A BOX NUMBER THIS SCREEN DID NOT ALREADY HAVE ONE FOR — the hero's card-based
     pass (`deckFromCards`) can front a card from a DIFFERENT box than `deckFromBoxes`'s own
     "newest box", so its fallback needs a lookup rather than `deckBox`'s own record. */
  const boxNameByNumber = useMemo(
    () => new Map(boxes.state === 'ready' ? boxes.value.map((b) => [b.box, b.name] as const) : []),
    [boxes],
  )
  const orderedBoxes = useMemo(() => {
    if (boxes.state !== 'ready') return []
    return [...boxes.value].sort((a, b) => {
      const ra = recency.get(a.box) ?? ''
      const rb = recency.get(b.box) ?? ''
      if (ra !== rb) return ra > rb ? -1 : 1
      const ha = a.on_hand ?? a.cards - a.sold - a.retired - a.moved
      const hb = b.on_hand ?? b.cards - b.sold - b.retired - b.moved
      if (ha !== hb) return hb - ha
      return a.box - b.box
    })
  }, [boxes, recency])
  const [runsRead, setRunsRead] = useState(0)
  const runs = useLoad<RunSummary[]>(getRuns, runsRead)
  const orders = useLoad<OrdersPayload>(getOrders)
  const pricing = useLoad<PricingWorklist>(() => getPricingWorklist())
  /* A VISIT TO HOME RUNS A DUE LIVE CHECK (the owner's Q3 ruling): a send whose wait ended
     while the app was closed is checked here, by itself. */
  const liveCheck = useLiveCheck()
  /* AND A VISIT TO HOME MATCHES A FINISHED READING (the owner's Q4 ruling, on Q3's two halves):
     a run whose reading ended while the app was closed is matched here, by itself. */
  useEffect(() => {
    if (runs.state !== 'ready') return
    void matchWaiting(runs.value).then((asked) => {
      /* THE RUN MOVED ON (or stopped on a problem), so the spine reads the runs again. */
      if (asked) setRunsRead((n) => n + 1)
    })
  }, [runs])
  /* The hero's own newest-captured cards, off a lean top-K route rather than the whole card
     map (D192, item 2) — on its own load so no panel above waits on it, and `deckFromCards`
     below applies exactly the same filter/sort/slice it always has over the smaller result. */
  const shelf = useLoad<Record<string, InventoryCard>>(async () => (await getRecentCards(DECK_DEPTH)).cards)
  const fromBoxes = deckFromBoxes(boxes.state === 'ready' ? boxes.value : null)
  const fromCards = deckFromCards(shelf.state === 'ready' ? shelf.value : null)
  /* The box-derived pass is a placeholder for the moment before the card map lands, so it
     yields to the named cards the instant they arrive. */
  const deck = fromCards.length > 0 ? fromCards : fromBoxes.cards
  const deckBox = fromBoxes.box
  const front = deck[0]
  const frontCard = front?.card ?? null
  /* THE HERO'S READING COMES OFF THE SHARED MACHINE NOW (D125, `cardCrop.ts`). It was written
     here first, as one fetch for one card, and the policy around it — serial, cached, a refusal
     remembered, a failure not — was written a second time on `#/pricing` and then wanted by three
     more screens. The behaviour here is unchanged except that the cache is the app's: a hero
     answered on this screen is already answered when the box walk reaches that card. */
  const crop = useCardCrop(front === undefined ? null : { box: front.box, index: front.index })

  const boxCount = boxes.state === 'ready' ? boxes.value.length : null
  const sold = boxes.state === 'ready' ? boxes.value.reduce((n, b) => n + b.sold, 0) : null
  const review = status.state === 'ready' ? status.value.queues.review : null
  const parked = status.state === 'ready' ? status.value.queues.parked : null
  /* The tile's headline is #/review's own headline: `review + parked`, the same total
     `ReviewQueue.tsx`'s `total = everyone.length + done` reaches in steady state, where
     `apply_run` (`store/queues.py`) keeps a position out of both files at once. The transient
     overlap `oneCardPerPosition` guards against is not observable from `/status` alone and is
     not worth a second `/queues` fetch here just to dedupe a state that is already rare —
     a named, accepted imprecision rather than a silent mismatch. */
  const reviewTotal = review === null || parked === null ? null : review + parked
  const lastBox = boxes.state === 'ready' ? [...boxes.value].sort((a, b) => b.box - a.box)[0] : undefined
  /* CARDS PHOTOGRAPHED AND NEVER SENT TO A RUN — `standing.ts`'s own branch 6 reads the same
     `states.captured`. Runs folded into Review (the owner's ruling, 2026-09-24): the spine no
     longer gives Runs its own tile, so the Review tile surfaces this the moment its own queue
     is empty, which is the one case a missing Runs tile would otherwise hide. */
  const captured = status.state === 'ready' ? (status.value.states.captured ?? 0) : null

  /* Orders: the figure is open orders; the note is the PULL BACKLOG the Orders screen itself
     draws as "N of M pulled" — `wanted − recorded` over the ledger's open rows. The resolver's
     `outstanding` is a different fact (copies the store cannot FIND) and is named as such. */
  const openRows = orders.state === 'ready' ? orders.value.orders.filter((o) => o.open) : null
  const openOrders = openRows === null ? null : openRows.length
  const toPull = openRows === null ? null : openRows.reduce((n, o) => n + Math.max(0, o.wanted - o.recorded), 0)
  /* Same join `standing.ts` makes, for the same reason: `resolution.orders` is already a
     subset of the open orders (`do_orders`'s own `open_keys`, D63 amended), and this counts
     a resolved line only where ITS order reads `open: true` here too, rather than trusting
     that upstream shape blind. See `## D202`. */
  const openKeys = openRows === null ? null : new Set(openRows.map((o) => o.key))
  const unfindable =
    orders.state === 'ready' && openKeys !== null
      ? orders.value.resolution.orders.reduce((n, o) => n + (openKeys.has(o.key) ? (o.outstanding ?? 0) : 0), 0)
      : 0
  /* Pricing: the runs the worklist says still owe an answer — `owes` is emit's own reason. */
  const runsToPrice = pricing.state === 'ready' ? runsOwingPrice(pricing.value.roster) : null
  /* And the copies every joined run still holds that TCGplayer does not (D156)
     — the same `unsent` the picker draws per run, summed, so this note and that chip agree. */
  const unsentCopies = pricing.state === 'ready' ? pricing.value.roster.reduce((n, r) => n + (r.unsent ?? 0), 0) : null

  /* THE STANDING LINE. The policy is `standing.ts`; this only hands it the readings and
     keeps the three non-values apart, which is the whole of what that module needs to obey
     its null invariant. */
  const say = standing({
    status: status.state === 'ready' ? status.value : null,
    statusFailed: status.state === 'failed',
    orders: orders.state === 'ready' ? orders.value : null,
    ordersFailed: orders.state === 'failed',
    pricing: pricing.state === 'ready' ? pricing.value : null,
    pricingFailed: pricing.state === 'failed',
    runs: runs.state === 'ready' ? runs.value : null,
    runsFailed: runs.state === 'failed',
    unconfirmed: liveCheck.status?.unconfirmed.copies ?? null,
  })

  /* Shipping: the export the hub last read, if one is in hand. */
  const batch = hubState().batch

  const stages: Stage[] = [
    {
      path: '/capture',
      icon: 'camera',
      label: 'Capture',
      /* THE NEWEST BOX, RELABELLED TO SAY SO (the owner's D142 ruling): this tile never claimed
         to be the box the operator is capturing INTO right now, only the newest one holding
         cards — the figure is that box's own card count, matching every other tile's numeral,
         and the note names it BY NAME (never a number — the owner's box-numbers ruling,
         2026-09-23). */
      figure: boxes.state === 'ready' ? (lastBox ? String(lastBox.cards) : '0') : '—',
      note: lastBox
        ? `newest: ${boxDisplayName(lastBox)}`
        : boxes.state === 'loading'
          ? 'reading…'
          : boxes.state === 'failed'
            ? 'boxes not read'
            : 'no boxes yet',
    },
    {
      /* REVIEW CARRIES THE IDENTIFY BACKLOG TOO (Runs folded into Review, the owner's ruling,
         2026-09-24): once the review queue itself is answered, this tile falls back to the
         count of cards photographed and never sent to a run — exactly what the removed Runs
         tile used to show, so that backlog is never invisible for want of its own tile. */
      path: '/review',
      icon: 'inbox',
      label: 'Review',
      figure:
        reviewTotal !== null && reviewTotal > 0
          ? String(reviewTotal)
          : captured !== null && captured > 0
            ? String(captured)
            : reviewTotal === null
              ? '—'
              : '0',
      note:
        reviewTotal !== null && reviewTotal > 0
          ? parked !== null && parked > 0
            ? `${review} waiting, ${parked} parked`
            : 'waiting'
          : captured !== null && captured > 0
            ? `${plural(captured, 'card')} to identify`
            : reviewTotal === 0
              ? 'nothing waiting'
              : '',
      tone:
        (reviewTotal !== null && reviewTotal > 0) || (captured !== null && captured > 0)
          ? 'warn'
          : reviewTotal === 0
            ? 'ok'
            : undefined,
    },
    {
      path: '/pricing',
      icon: 'tag',
      label: 'Pricing',
      figure: runsToPrice === null ? '—' : String(runsToPrice),
      note:
        runsToPrice === null
          ? pricing.state === 'failed'
            ? 'worklist not read'
            : 'reading the worklist…'
          : runsToPrice === 0
            ? unsentCopies !== null && unsentCopies > 0
              ? `${plural(unsentCopies, 'copy', 'copies')} ready to send`
              : 'nothing to price'
            : runsToPrice === 1
              ? 'run'
              : 'runs',
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
              ? `${toPull} to pull${unfindable ? `, ${unfindable} missing` : ''}`
              : `every copy pulled${unfindable ? `, ${unfindable} missing` : ''}`,
      tone: toPull ? 'warn' : openOrders === 0 ? 'ok' : undefined,
    },
    {
      path: '/shipping',
      icon: 'truck',
      label: 'Shipping',
      figure: batch ? String(batch.shipments) : '—',
      quiet: !batch,
      note: batch ? `${batch.name}: ${batch.shipments} ${batch.shipments === 1 ? 'shipment' : 'shipments'} in lanes` : 'no export yet',
    },
  ]

  const deckArt = (
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
                  ? `The last cards photographed into ${boxDisplayName(deckBox)}. Open the box on Inventory.`
                  : `${frontCard.name ?? 'The last card you photographed'}, ${
                      frontCard.place?.label ??
                      boxDisplayName({ box: frontCard.box, name: boxNameByNumber.get(frontCard.box) ?? null })
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
                              .map((part, at) => (
                                <span key={at}>{part}</span>
                              ))}
                          </div>
                        </>
                      ) : null}
                    </div>
                  )
                })}
              <div className="home-deck-address" aria-hidden="true">
                <Icon name="pin" size={14} />
                {frontCard?.place?.label != null ? (
                  // D218: found beyond the reader's own list — this badge draws
                  // `Position.label` raw, off a variable rather than a literal, so the count
                  // above never saw it. Same server string, same aria-hidden badge; the seam
                  // between its parts is CSS now (`.home-deck-card-no > span::before`).
                  <span className="home-deck-card-no">
                    {placeWordsOf(frontCard.place.label).map((part, at) => (
                      <span key={at}>{part}</span>
                    ))}
                  </span>
                ) : (
                  <span className="home-deck-card-no">{boxDisplayName(deckBox)}</span>
                )}
              </div>
            </a>
          )}
        </div>
  )

  return (
    <Page
      className="home"
      title={<>{greeting()}.</>}
      lede={<span className="bn-eyebrow">{weekdayDate(new Date())}</span>}
      actions={deckArt}
    >
      <div className="home-hero-body">
        <StandingLine standing={say} />
        <div className="home-actions">
          <Button
            variant="primary"
            size="lg"
            icon="camera"
            kbd=",C"
            onClick={() => (window.location.hash = '#/capture')}
          >
            {status.state === 'ready' && status.value.cards === 0 ? 'Photograph the first box' : 'Start capturing'}
          </Button>
        </div>
        <HistoryFoot status={status.state === 'ready' ? status.value : null} boxes={boxCount} sold={sold} shelf={shelf.state === 'ready' ? shelf.value : null} live={say?.running ?? false} />
      </div>

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
              <Loading rows={4} shape="rows" className="home-skel-rows" />
            ) : boxes.state === 'failed' ? (
              <p className="home-empty">The server did not answer.</p>
            ) : boxes.value.length === 0 ? (
              <p className="home-empty">No boxes yet. Capture a card to make the first one.</p>
            ) : (
              orderedBoxes.map((box) => {
                const held = box.on_hand ?? box.cards - box.sold - box.retired - box.moved
                const pct = box.cards > 0 ? Math.round((held / box.cards) * 100) : 0
                const name = boxDisplayName(box)
                return (
                  <a key={box.box} className="home-box" href={`#/inventory?box=${box.box}`}>
                    {/* AN ICON, NEVER THE BOX'S NUMBER (the owner's ruling, 2026-09-23): the
                        number is an arbitrary internal index, not a fact worth a badge. */}
                    <span className="home-box-num" aria-hidden="true">
                      <Icon name="box" size={16} />
                    </span>
                    <span className="home-box-text">
                      <span className="home-box-name" title={name}>
                        {name}
                      </span>
                      <span className="home-box-meta">
                        <span>{held.toLocaleString()} on hand</span>
                        <span>{box.sold} sold</span>
                      </span>
                    </span>
                    <span className="home-box-bar" title={`${pct}% on hand`}>
                      <span style={{ width: `${pct}%` }} />
                    </span>
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
              <Loading rows={4} shape="rows" className="home-skel-rows" />
            ) : runs.state === 'failed' ? (
              <p className="home-empty">The server did not answer.</p>
            ) : runs.value.length === 0 ? (
              <p className="home-empty">No runs yet. Identify a box from the Runs screen.</p>
            ) : (
              runs.value.slice(0, 6).map((run) => {
                // `runBoxLabel` AND NOT A SECOND SPELLING OF IT (D145). This line
                // composed the label itself, so `Box 1 (deleted)` reached `#/runs` and `#/pricing`
                // and this panel went on drawing `Box 1` for a drawer that is not on the shelf —
                // which is `runScope.ts`'s own founding defect (D56), repeated one screen over.
                const boxLabel = runBoxLabel(run) ?? 'Run'
                return (
                  <a key={run.run} className="home-run" href={`#/runs?run=${encodeURIComponent(run.run)}`}>
                    <span className="home-run-text">
                      {/* D218: found beyond the reader's own list — `runScope.ts:boxLabel`
                          composes `Box N · Name` off a template literal, so the reader's
                          plain-string scan never saw it. That composer is shared and stays
                          untouched (same rule as `Position.label`); only the render splits it.
                          `title` cannot hold elements, so it gets the comma-joined form. */}
                      <span className="home-run-box" title={boxLabel.replace(/ · /g, ', ')}>
                        {boxLabel.split(' · ').map((part, at) => (
                          <span key={at}>{part}</span>
                        ))}
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
    </Page>
  )
}
