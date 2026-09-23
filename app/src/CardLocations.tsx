import { useState, type CSSProperties, type ReactNode } from 'react'

import type { SearchCopy, SearchGroup, SectionDetail } from './types'
import { isDeparted, photoUrl, placeSentence } from './server'
import { PlaceNeighbors } from './PlaceNeighbors'
import { PullConfirm } from './PullConfirm'
import { PositionBar } from './PositionBar'
import { sayPlace, type Persona } from './position'
import { PositionLabel } from './PositionLabel'
import { collectorNumber } from './cardNumber'
import { Button, Chip, Icon, Pill } from './kit'
import { RANK_IS_CURRENT, ranksAsLive, ranksAsShown, stalenessSentence, type FrozenRank } from './frozenRank'
import './CardLocations.css'
import { forSale, readingAgo, readingExact, RETIRED, SOLD, stateLabel, stateTone } from './cardState'

/* One card, every copy of it, and where each copy physically is.
 *
 * ONE CORE, TWO SKINS, and `persona` is the whole of the difference: same data, same order,
 * same actions, same tokens. The owner's rows are dense and speak the pipeline's vocabulary;
 * the Fulfiller's cards are big, plain, and carry no machine string at all — his words only
 * ever come out of the `fulfiller` branch, so there is no path by which a SKU reaches him.
 *
 * Copies are fungible (D7): `live` is a quantity held against the SKU, not a flag on four
 * particular cards, so every unsold copy is sellable and the count of what is for sale comes
 * off `group.listed`, never off the copies.
 */

/* ------------------------------------------------- how old a LIVE reading is (D-rulings) ---
 *
 * A LIVE COUNT IS A FACT ABOUT WHEN THIS STORE LAST LOOKED, NOT A FACT ABOUT THE MARKETPLACE.
 * `store/master.py:Listing` says so in as many words — "an optimistic local estimate between
 * runs" — so no screen in this group draws the figure without saying how old it is.
 *
 * The stamp is `Listing.at` off `GET /inventory`. Every `set`/`bump` re-stamps it, so after a
 * `join` or a `reconcile --live` it is the moment TCGplayer's own figures were read in.
 *
 * IT IS JOINED CLIENT-SIDE BECAUSE `/search` DOES NOT CARRY IT: `SearchGroup.listed` is three
 * counts and no time at all on this branch. Both come off the same store record, so the join
 * is exact rather than a guess — but the day `listed` grows an `at` of its own, read that and
 * delete the join.
 */

/** `read 3 days ago`, drawn beside a live count and never louder than it. */
export function ReadingAge({ at, className }: { readonly at?: string | null; readonly className?: string }) {
  const ago = readingAgo(at)
  return (
    <span
      className={['inv-readage', ago === null ? 'is-unread' : '', className ?? ''].filter(Boolean).join(' ')}
      title={
        ago === null
          ? 'Nothing has written a listing figure for this yet.'
          : `This store last wrote these listing figures ${readingExact(at)}.`
      }
    >
      {ago === null ? 'not read yet' : `read ${ago}`}
    </span>
  )
}

/** An open order that has named one copy, keyed by the copy's store key. Structural, so the
 *  screen's own richer `Wanted` fits without a second import of it. `key` is the order's
 *  `source:number` composite (`ResolvedLine.order_key`) — what `Orders.tsx`'s
 *  `groupForOrderKey` actually matches on, and not the same string as `order`, which is the
 *  buyer-facing number alone. The pill links with `key` for exactly that reason.
 *
 *  REQUIRED, NOT OPTIONAL. `wantedOf` already sets it from `line.order_key` on every path, so
 *  no real producer is missing it — an optional field here would only ever be reached by a
 *  fallback the compiler could not see was dead. A bare `order` number resolves to nothing on
 *  `Orders.tsx` (`groupForOrderKey` matches on the store key), so a caller with no `key` has
 *  not got what the link needs and must not compile rather than silently linking nowhere. */
export type CopyClaim = { readonly order: string; readonly key: string }

/** What the Fulfiller is told about a copy — two sentences, never the raw state word. */
function saidState(state: string): string {
  if (state === SOLD) return 'Sold.'
  if (state === RETIRED) return 'No longer in the boxes.'
  return 'In the boxes.'
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/* HOW MUCH ROOM IS LEFT UNDER THE CEILING — said as headroom, never as a second live count.
 *
 * `group.listable` is D7's `min(cap, on hand)` computed by the server: what the rule permits
 * for THIS SKU. Drawn as `up to 3 may be live` it used the same numeral as the live figure two
 * lines above it, and the two sentences could not be told apart — is three live, or may three
 * be? Headroom is the same fact in terms nothing else on the panel is measured in. */
function headroom(group: SearchGroup): string {
  // THE ESTIMATE, NOT THE READING (D115). Headroom is what may still GO live, so it has to
  // count against what is live NOW — a SKU read at 4 with 2 sold here has room for 2, and
  // computing off the raw reading would say `At the ceiling of 4` and refuse a relist the
  // shelf can support. It would also put a third number on a panel that now draws two.
  const room = group.listable - forSale(group.listed.live, group.sold_here)
  if (group.listable === 0) return 'No copies can go live'
  if (room > 0) return `Room for ${room} more live`
  if (room === 0) return `At the ceiling of ${group.listable}`
  return `${-room} over the ceiling of ${group.listable}`
}

export type CardLocationsProps = {
  group: SearchGroup

  /** Required, not defaulted: a skin you get by forgetting is a skin nobody chose. */
  persona: Persona

  /** Record a sale of ONE copy — the position is the whole of the selection. The caller owns
   *  the request, its refusals and its undo window. */
  onSell: (copy: SearchCopy) => void

  /** The `SearchCopy.key` of a sale in flight, or null. One at a time. */
  busyKey: string | null

  /** Copies the caller has already sold and is holding a receipt for. An optimistic overlay. */
  soldKeys: ReadonlySet<string>

  /** Each box's own divider layout, keyed by `Place.box` — handed to every `PositionBar`.
   *  A map per box and never one array, because a search group is not a box. Optional; the
   *  bar is honest without it. */
  sections?: ReadonlyMap<number, readonly SectionDetail[]>

  /** Which copy the caller is currently pointing at, or undefined. Owner skin only.
   *
   *  A STATEMENT OF WHERE THE WALK STANDS, NEVER A RECOMMENDATION. The row it names is drawn
   *  in full like every other and keeps its own controls; all it gets extra is a quiet
   *  `Viewing` marker and a neutral rail, because the owner picks which physical copy to
   *  reach for and the UI does not get a vote. */
  currentKey?: string

  /** When this store last wrote this SKU's listing figures — `Listing.at` off `GET
   *  /inventory`. Optional; absent draws `not read yet` rather than a bare live count. */
  listedAt?: string | null

  /** Which copies an open order has already named, by copy key. A claimed copy is DRAWN AND
   *  MARKED, never hidden and never un-pressable: this screen is also where a walk-in sale is
   *  recorded, and the owner ruled that `Mark sold` stays. */
  claims?: ReadonlyMap<string, CopyClaim>

  /** Walk to this copy. Owner skin only, optional; never drawn on the current copy or a pooled
   *  one. */
  onGoTo?: (copy: SearchCopy) => void

  /** Replaces the action slot for EVERY copy, sold ones included — this is how a screen draws
   *  its own undo. */
  renderAction?: (copy: SearchCopy) => ReactNode

  /** FOLD THE DEPARTED COPIES AWAY (D132, the owner's default). Hidden, a sold or retired copy
   *  is not drawn — except the copy the walk stands on and a copy sold from THIS screen whose
   *  receipt is still standing, both of which are the row the person is looking at. Shown, the
   *  departed copies sort after every live one. Owner skin only; the Fulfiller's list is his
   *  order and this never reaches it. */
  hideSold?: boolean

  /** THE COPIES THAT LEFT SINCE THIS ORDER WAS TAKEN (`frozenRank.ts`). Each one goes on
   *  counting for its section and goes on being drawn where it is, `hideSold` included, so a
   *  sale moves no row. Omitted is `RANK_IS_CURRENT` — rank by what the store says now, which
   *  is what `#/gallery` and the lone-copy fallback want. Owner skin only. */
  frozen?: FrozenRank

  /** Take a new order. Drawn as a control only while `frozen` holds something, and it is the
   *  only thing on this screen that reshuffles the list (D28's shape: the operator says when).
   *  Omitted draws no control, which is the kit sheet's case. */
  onRerank?: () => void

  /** Where a copy's photograph comes from. Omitted by every screen in the product, which is
   *  how they all get D6's `GET /photo/<box>/<index>` and stay the single caller shape.
   *
   *  IT EXISTS FOR `#/gallery` AND FOR NOTHING ELSE, and the reason is not convenience. The
   *  kit sheet is what `make screenshot` renders and what a person compares against a
   *  reference, so its contents must not depend on which capture server is up or on what is
   *  in box 3 today — and a pooled capture's photograph is a live code card, which
   *  `scripts/views.txt` is not allowed to write into `captures/ui/` (D24). Setting
   *  `has_photo: false` on the fixtures would buy that by deleting the photo-bearing shell
   *  from the one page whose job is drawing every shell, which `app/tests/gallery.spec.ts`
   *  refuses. So the shell stays and the sheet brings its own image.
   *
   *  A SEAM, NOT A POLICY: it may not become the way a screen points at a second photo
   *  service. The default below is the product's answer. */
  photoSrc?: (copy: SearchCopy) => string

  /** DRAW `group.copies` IN EXACTLY THE ORDER GIVEN — no fullest-section rank, no sold-copy
   *  fold or sink. `hideSold`/`frozen`/`onRerank` are irrelevant under it and nothing is
   *  hidden. For a caller whose own order is already load-bearing and answers a question this
   *  ranking would only re-ask — the walk's solver order, "this stop's copies first, then
   *  ascending (box, index)" (`docs/specs/order-walk-plan.md` §8's 2026-09-19 ruling,
   *  `OrdersWalk.tsx`). Omitted, every existing caller ranks exactly as it always has. */
  preserveOrder?: boolean

  /** An extra class on the outer `<section>` — a CSS seam so a caller's own stylesheet can
   *  scope a rule to its usage (the walk's row `min-height`, D118) without it reaching
   *  `#/inventory` or `#/fulfillment`. Omitted, the section carries its usual two classes only. */
  className?: string
}

export function CardLocations(props: CardLocationsProps) {
  const { persona } = props

  /* Photos that failed to load, by copy key. */
  const [missing, setMissing] = useState<string[]>([])

  return persona === 'fulfiller' ? (
    <FulfillerCard {...props} missing={missing} setMissing={setMissing} />
  ) : (
    <OwnerRows {...props} />
  )
}

/* Sold is the only thing that stops a sale — D7's "every unsold copy is sellable" as code. */
function isSold(copy: SearchCopy, soldKeys: ReadonlySet<string>): boolean {
  return copy.state === SOLD || copy.state === RETIRED || soldKeys.has(copy.key)
}

/* A pooled copy — a count, not a location (D24). `!== false` so an older server's blocks keep
   reading as located. */
function isPooled(copy: SearchCopy): boolean {
  return copy.place.located === false
}

// ------------------------------------------------------------------------- the owner's skin

/* EVERY COPY OF THIS CARD, AND WHERE EACH ONE PHYSICALLY IS — the panel the owner picks a copy
 * out of, so three rules bind it:
 *
 *   1. Every LIVE copy is drawn, in full. No copy is folded away for being the one the walk
 *      happens to be standing on, and none is dropped for being far away or spoken for. SOLD
 *      is the one exception, and it is the owner's (D132, 2026-09-10): with `hideSold` the
 *      departed copies are folded away and a line says how many, and without it they sink
 *      under the live ones. Either way the copy the walk stands on is drawn.
 *   2. Nothing is preselected and nothing is recommended. The row the walk stands on carries a
 *      quiet `Viewing` marker and a neutral rail — a statement of where you are, not a nudge —
 *      and it keeps its own controls like every other row.
 *   3. A copy an open order has already named is MARKED, never hidden and never disabled: this
 *      is also where a walk-in sale is recorded, and `Mark sold` stays on every live row.
 *
 * The position lens is on every row: "how far into the box" is the thing the owner opened the
 * screen to learn, and every bar on screen at once is the feature.
 */
function OwnerRows({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  currentKey,
  listedAt,
  claims,
  onGoTo,
  renderAction,
  hideSold = false,
  frozen = RANK_IS_CURRENT,
  onRerank,
  preserveOrder = false,
  className,
}: Omit<CardLocationsProps, 'persona'>) {
  const number = collectorNumber(group)

  /* WHICH COPIES ARE DRAWN, AND IN WHAT ORDER (D132). Rule 1 below used to say no copy is
     dropped for being sold; the owner amended that on 2026-09-10 — a sold copy is not a place
     a hand can go, and scrolling past them to find the live ones was the whole complaint. What
     survives of the rule: the copy the walk stands on and a copy just sold here stay, so the
     press that sold it is still on screen with its receipt (D119); and nothing is preselected.
     A stable partition, so within each half the server's `(box, index)` order is untouched. */
  const gone = group.copies.filter((copy) => isSold(copy, soldKeys))
  /* Stays where it is: the copy the walk stands on, a copy sold from this screen while its
     receipt stands, and — since the order is frozen — every copy that left after this order was
     taken, whose receipt is long gone. The press may not move the rows beneath it (D118), and
     neither may the twenty seconds afterwards. */
  /* `ranksAsShown` is asked with `departed: true` because both callers below have already
     established that — `gone.filter(stays)` and `sinks`, which tests `isSold` first. Spelled
     through the shared predicate rather than as a bare `frozen.has`, so this list and the walk
     cannot answer the fold question two different ways. */
  const stays = (copy: SearchCopy) =>
    copy.key === currentKey || soldKeys.has(copy.key) || ranksAsShown(copy.key, true, frozen)
  const kept = hideSold ? gone.filter(stays) : gone
  /* A FROZEN DEPARTURE NEVER SINKS EITHER, which is the half that is easy to miss: D132 offers
     a fold OR a sink, and a sink is a movement too — every row under the sinking one comes up
     by its height. Frozen, the row keeps its place and is struck. */
  const sinks = (copy: SearchCopy) => isSold(copy, soldKeys) && !stays(copy)
  /* THE FULLEST SECTION LEADS (D132, amended on the owner's rule of 2026-09-11): the copies
     are grouped by box and section and the section holding the most of them is drawn first,
     because that is the place a hand can pull the most from. Within a section the server's
     card order holds. A copy sold from THIS screen still counts for its section while its
     receipt stands, so the press that sold it moves no row (D118); the store's own sold copies
     count for nothing and, when shown, sink under everything.

     AND A COPY THAT LEFT SINCE THIS ORDER WAS TAKEN GOES ON COUNTING FOR ITS SECTION, which is
     what makes the order survive the press outliving its receipt (`frozenRank.ts`). The
     arithmetic is unchanged; what changed is the state it is computed against. */
  const counts = new Map<string, number>()
  const sectionOf = (copy: SearchCopy) => `${copy.place.box}/${copy.place.section ?? '?'}`
  for (const copy of group.copies) {
    if (!ranksAsLive(copy.key, copy.state === SOLD || copy.state === RETIRED, frozen)) continue
    counts.set(sectionOf(copy), (counts.get(sectionOf(copy)) ?? 0) + 1)
  }
  const byFullest = (a: SearchCopy, b: SearchCopy) =>
    (counts.get(sectionOf(b)) ?? 0) - (counts.get(sectionOf(a)) ?? 0)
  const standing = group.copies.filter((copy) => !sinks(copy) && (!hideSold || !isSold(copy, soldKeys) || kept.includes(copy)))
  /* `preserveOrder` BYPASSES ALL OF THE ABOVE, RATHER THAN FEEDING IT `frozen`. The panel's own
     re-rank is a question about which section to reach into first, and a caller whose copies
     already arrive in a load-bearing order (the walk's solver order) is not asking that
     question at all — freezing the SORT'S INPUTS still runs the sort, and the sort still leads
     with the fullest section rather than with the caller's own first entry. Bypassing it is
     the smaller and the more honest fix. Nothing is hidden or sunk under it either: `hideSold`
     is a fold this caller never asked for. */
  const drawn = preserveOrder
    ? group.copies
    : [...[...standing].sort(byFullest), ...(hideSold ? [] : group.copies.filter(sinks))]
  const hidden = preserveOrder ? 0 : gone.length - kept.length
  /* HOW STALE THE ORDER IS, counted over the copies THIS LIST draws. `frozen` is the screen's —
     one press makes the box rail stale too — and a sentence saying `3 copies stale` over a list
     that holds one of them would be counting somebody else's cards. */
  const staleHere = group.copies.filter((copy) => frozen.has(copy.key)).length
  const stale = stalenessSentence(staleHere)

  /* A GROUP WITH NO SKU HAS NO LISTING TO REPORT, AND THE HEADER MUST NOT INVENT ONE (D119).
     `capture_server.py:do_search` sends the SKU-less bag `listed: {0,0,0}`, `sold_here: 0` and
     `live_as_of: null` — structurally, not because nothing has happened yet: `emit` is what
     creates a listing record and it cannot run for a card the pipeline has not identified.
     Drawn anyway that reads `0 live on TCGplayer · not read yet` and `Pushed 0 · Staged 0 ·
     Room for 1 more live` — a promise of headroom on a card that cannot be listed at all.

     WHAT GOES IS THE SENTENCE, NEVER THE FIGURE. `group.listable` stays exactly what the server
     sent; rewriting it to 0 here would make this the one thing in the product that answers a
     question differently from the store.

     DERIVED FROM `sku` AND NOT TAKEN AS A PROP: a prop is a second place the same fact can be
     told, and one caller forgetting it is a header that lies. Derived, it also reaches the
     search path — the 65 cards this store holds with a name and no SKU already land in the
     loose bag and already draw this. */
  const listing = group.sku !== null

  /* HOW MANY DIGITS THIS LIST'S SLOT COLUMN HAS TO HOLD, which is the one term of that column
     that is DATA rather than typography (`CardLocations.css`'s `--pos-slot-key` is the other).
     A row cannot compute it — it cannot see what its siblings drew — so the list does, over the
     copies it is about to render, and every row reserves the same width from it.

     `place.card` AND NOT THE LABEL. It is the same field `pipeline/join.py:Position.label`
     composes its last part from, it is already on the wire, and it is null exactly for the rows
     that draw no figure (D58, D71) — so reading it needs no second copy of `PositionLabel`'s
     seam here, which is the duplication D67 and D92 both record.

     Floored at three so no list renders narrower than every store, fixture and screenshot did
     before this existed. */
  const slotDigits = Math.max(
    3,
    ...drawn.map((copy) =>
      copy.place.card === null ? 0 : String(copy.place.card).length,
    ),
  )
  /* The machine strings — SKU, set code, number — in mono; the condition is a phrase and is
     drawn beside them in the UI face. */
  const meta =
    group.sku === null
      ? ['no SKU yet']
      : [
          `SKU ${group.sku}`,
          ...(group.set_hint === null ? [] : [group.set_hint]),
          ...(number === null ? [] : [number]),
        ]

  return (
    <section className={['card-locations', 'card-locations-owner', className ?? ''].filter(Boolean).join(' ')}>
      <header className="card-locations-head">
        <h3 className="bn-section-title card-locations-title">Every copy of this card</h3>
        {/* THE ONE THING THAT RESHUFFLES THIS LIST, and it is a press rather than a consequence.
            Drawn only once the order has actually gone stale — a control offering to recompute
            an order that is already current is a button that does nothing, and a permanent one
            would read as a setting to get right rather than as the state of this list. It sits
            in the header because the press that made it stale is in the rows beneath it; a
            re-rank on the walk's own status bar would be across the screen from the hand.

            THE SLOT AROUND IT IS ALWAYS RENDERED AND IS D118's RULE, not tidiness. A control
            that appears on a press is a row of the header's grid that did not exist a frame
            ago, and this list sits inside `.browse-band`'s fixed height — so every copy row
            would go down by the chip's height at the moment of the sale, which is the movement
            this whole entry exists to stop. The slot holds `--bn-control-h-sm` whether or not
            there is anything in it. */}
        <div className="card-locations-rerank-slot">
          {stale === null || onRerank === undefined ? null : (
            <Chip
              icon="refresh"
              className="card-locations-rerank"
              title="Ranked before these copies left."
              onClick={onRerank}
            >
              <span>{stale}</span>
              <span className="card-locations-rerank-go">re-rank</span>
            </Chip>
          )}
        </div>
        <div className="card-locations-stats">
          <div className="bn-stat card-locations-stat">
            <span className="bn-stat-value">{group.copies.length}</span>
            <span className="bn-stat-label">{group.copies.length === 1 ? 'copy' : 'copies'}</span>
          </div>
          <div className="bn-stat card-locations-stat">
            <span className="bn-stat-value">{group.on_hand}</span>
            <span className="bn-stat-label">in the boxes</span>
          </div>
          {/* THE LIVE FIGURE NEVER STANDS ALONE. It is what this store last believed, so its
              reading age sits under it, quieter than the count itself.
              AND SINCE D115 IT IS TWO NUMBERS. The big one is the ESTIMATE — the reading less
              what has sold here since — because that is the figure that must agree with the
              shelf the operator is standing at (D7). The split under it is drawn only when
              there is a difference: `4 when read · 2 sold here since` on 3 of 443 SKUs is
              information, and `· 0 sold here since` on the other 440 is noise that trains the
              eye to skip the line. */}
          {listing ? (
            <div className="bn-stat card-locations-stat card-locations-live">
              <span className="bn-stat-value">
                <span className="bn-dot bn-dot-live" aria-hidden="true" />
                {forSale(group.listed.live, group.sold_here)}
              </span>
              <span className="bn-stat-label">live on TCGplayer</span>
              <ReadingAge at={listedAt} />
              {group.sold_here > 0 ? (
                <span className="card-locations-since">
                  <span>{group.listed.live} when read</span>
                  <span>{group.sold_here} sold here since</span>
                </span>
              ) : null}
            </div>
          ) : null}
        </div>

        <p className="card-locations-meta">
          <span className="card-locations-meta-mono">
            {meta.map((part, at) => (
              <span key={at}>{part}</span>
            ))}
          </span>
          {group.condition === null ? null : (
            <span className="card-locations-cond">{group.condition}</span>
          )}
        </p>
        {/* THE CEILING, SAID SO IT CANNOT BE READ AS A SECOND READING. `up to 3 may be live`
            sat two lines under `3 live on TCGplayer` and used the same figure to mean the
            other thing, so a reader could not tell whether three ARE live or three MAY be.
            Headroom is the honest form of the same fact. */}
        {listing ? (
          <p className="card-locations-counts">
            <span>Pushed {group.listed.pushed}</span>
            <span>Staged {group.listed.staged}</span>
            <span>{headroom(group)}</span>
          </p>
        ) : null}
      </header>

      <ul
        className="card-locations-rows bn-stagger"
        style={{ ['--pos-slot-digits']: slotDigits } as CSSProperties}
      >
        {drawn.map((copy, i) => {
          const sold = isSold(copy, soldKeys)
          const pooled = isPooled(copy)
          const departed = isDeparted(copy.place)
          const current = copy.key === currentKey
          const label = copy.place.label
          const claim = claims?.get(copy.key) ?? null

          /* The walk-to for THIS copy, or null when there is nowhere to send anyone. */
          const goesTo = onGoTo === undefined || pooled || current ? null : () => onGoTo(copy)
          /* No bar for a pooled copy, and for nothing else — BOTH of the other terms that
             stood here were removed on 2026-09-07, by two branches, for two unrelated reasons,
             and this is the merge of them.

             THE COPY THE WALK IS STANDING ON (D119). Its lens used to be drawn full size in the
             location card ~150px above this list with the same `#N of M` caption, and two
             identical bars a screen apart read as a rendering fault rather than as hero-and-list.
             That card is deleted, so the duplication is gone and the exception with it.

             A DEPARTED COPY (D118). It was excluded on the reasoning that a bar cannot draw a
             card that is in no place — true of the MARK and not of the lens, which draws the BOX.
             Dropping the row cost this list a line's height at the moment a sale landed, so every
             row beneath the sold one moved under a pointer that had just pressed. The bar stays
             and the mark falls out of it instead.

             What is left is the one copy that has no coordinate at all: a pool is a count. */
          const noBar = pooled

          return (
            <li
              className={[
                'card-locations-row',
                noBar ? 'is-nobar' : '',
                sold || departed ? 'is-gone' : '',
                current ? 'is-current' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              key={copy.key}
              style={{ ['--i' as string]: i }}
              aria-current={current ? 'true' : undefined}
            >
              <span className="card-locations-place">
                {pooled ? (
                  <>
                    <span className="card-locations-label">
                      {copy.place.game_display ?? 'Pooled'}
                    </span>
                    <span className="card-locations-boxname">
                      <span>pooled</span>
                      <span>{copy.key}</span>
                    </span>
                  </>
                ) : (
                  <>
                    {/* The server's own label, displayed and never composed. Slot-first here
                        because this is a list: the figures land in a hard column. Where the
                        caller offers a walk-to, the same rendering sits inside a button. */}
                    <span className="card-locations-label">
                      {label === null ? null : goesTo === null ? (
                        <PositionLabel label={label} lead="slot" boxName={copy.place.box_name} sectionName={copy.place.section_name ?? null} />
                      ) : (
                        <button
                          className="card-locations-goto"
                          type="button"
                          aria-label={`Walk to ${sayPlace(label)}`}
                          onClick={goesTo}
                        >
                          <PositionLabel label={label} lead="slot" boxName={copy.place.box_name} sectionName={copy.place.section_name ?? null} />
                          <Icon name="arrowUpRight" size={14} className="card-locations-goto-icon" />
                        </button>
                      )}
                    </span>
                    <PlaceNeighbors place={copy.place} />
                  </>
                )}
              </span>

              {noBar ? null : (
                <PositionBar
                  place={copy.place}
                  persona="owner"
                  sections={sections?.get(copy.place.box)}
                  sectionDepth
                />
              )}

              <span className="card-locations-state">
                {current ? (
                  <Pill icon="eye" outline className="card-locations-viewing">
                    {/* NARROW, THE WORD IS SPOKEN AND NOT DRAWN — the kit's own `.bn-sr`
                        technique, `Button`'s `iconOnly` reuses the same way:
                        the current row is the only one that carries this second pill beside
                        its own state, and sharing the narrow row with `.card-locations-action`'s
                        137px reservation (D118) left `Identified` too little room — measured,
                        it wrapped onto its own line under 335px. Growing the row instead
                        (a line of its own for `state`) fixed the wrap and broke a stricter
                        floor: `toBeInViewport({ ratio: 1 })` on the pipeline-console case,
                        because the taller row no longer fit. The eye icon alone still says
                        "you are looking at this one"; the word rides `.bn-sr` so a screen
                        reader still gets it, and the row's height never moves. */}
                    <span className="card-locations-viewing-text">Viewing</span>
                  </Pill>
                ) : null}
                {claim === null ? null : (
                  <a
                    className="bn-pill bn-pill-warn card-locations-claim"
                    href={`#/orders?order=${encodeURIComponent(claim.key)}`}
                    aria-label={`Order ${claim.order} is waiting on this copy`}
                    title="Still yours to sell from here."
                  >
                    <Icon name="cart" size={12} />
                    Wanted
                    {/* The order number itself is 21 characters. It is drawn where the panel is
                        wide enough to hold it, and the mark alone where it is not — the number
                        is in the title and one press away. It used to be on the location card
                        above as well, which D119 deleted. */}
                    <span className="card-locations-claim-id">{claim.order}</span>
                  </a>
                )}
                <Pill tone={stateTone(copy.state)}>{stateLabel(copy.state)}</Pill>
              </span>

              {/* The action, or what stands where one would. A sold copy's own state pill
                  already says so; an optimistic sale whose re-read is still in flight needs a
                  word, and a sale whose undo window is still running draws its draining clock
                  and an `Undo` here since D119 — inside this cell, at the size the cell already
                  reserves (D118), because a press may not resize the slot it lands in. */}
              <span className="card-locations-action">
                {renderAction !== undefined ? (
                  renderAction(copy)
                ) : sold ? (
                  copy.state === SOLD || copy.state === RETIRED ? null : <Pill tone="ok">Sold</Pill>
                ) : (
                  <Button
                    size="sm"
                    busy={busyKey === copy.key}
                    disabled={busyKey !== null && busyKey !== copy.key}
                    onClick={() => onSell(copy)}
                  >
                    Mark sold
                  </Button>
                )}
              </span>
            </li>
          )
        })}
      </ul>
      {hidden === 0 ? null : (
        <p className="card-locations-hidden">
          {hidden === 1 ? '1 sold copy hidden' : `${hidden} sold copies hidden`}
        </p>
      )}
    </section>
  )
}

// --------------------------------------------------------------------- the Fulfiller's skin

/* Every copy is its own card: a photo to confirm against, a position label he can read at
 * arm's length, a bar saying how far in, and its own control. Unchanged by the owner-side
 * rebuild; every floor in docs/DESIGN.md's constraints table binds here. */
function FulfillerCard({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  listedAt,
  renderAction,
  photoSrc,
  missing,
  setMissing,
}: Omit<CardLocationsProps, 'persona'> & {
  missing: string[]
  setMissing: (next: (held: string[]) => string[]) => void
}) {
  const number = collectorNumber(group)

  /* His header carries no SKU, no set code and no state words. */
  const about = [
    ...(group.condition === null ? [] : [group.condition]),
    ...(number === null ? [] : [number]),
  ]

  return (
    <section className="card-locations card-locations-fulfiller">
      <header className="card-locations-head">
        <h2 className="card-locations-name">
          {group.names.length === 0 ? 'This card has no name yet' : group.names.join(' / ')}
        </h2>
        {about.length === 0 ? null : (
          <p className="card-locations-say">
            {about.map((part, at) => (
              <span key={at}>{part}</span>
            ))}
          </p>
        )}
        {/* HIS LIVE COUNT CARRIES ITS AGE TOO, in his words rather than in the pipeline's —
            "for sale" reads as a fact about the shop when it is a fact about the last time
            this store looked. Drawn only when the caller hands over the stamp, because
            "not read yet" is a sentence about plumbing and he is owed none of those.
            `Fulfillment.tsx` has to pass `listedAt` for this half to appear. */}
        <p className="card-locations-say">
          <span>{count(group.on_hand, 'copy here', 'copies here')}</span>
          <span>
            {forSale(group.listed.live, group.sold_here)} for sale
            {readingAgo(listedAt) === null ? '' : `, counted ${readingAgo(listedAt)}`}
          </span>
        </p>
        {/* AND WHY IT MOVED, IN HIS WORDS (D115, and the owner's ruling that BOTH figures are
            drawn everywhere — I argued for the estimate alone here and was overruled). The
            count above is the estimate, so it drops the moment he pulls a card; without this
            line the number simply changes under him with no reason given, which is the one
            thing `docs/DESIGN.md`'s constraints table will not have on this view.
            "sold", "counted" and "since" are all clear of the banned-word list
            (`app/tests/fulfillment.spec.ts`), and it is ONE sentence, so D5's "nothing is
            explained twice" holds. Drawn only when there is something to explain. */}
        {group.sold_here > 0 ? (
          <p className="card-locations-say">
            {count(group.sold_here, 'copy', 'copies')} sold here since we last counted.
          </p>
        ) : null}
      </header>

      <ul className="card-locations-copies">
        {group.copies.map((copy) => {
          const sold = isSold(copy, soldKeys)
          const noPhoto = !copy.has_photo || missing.includes(copy.key)
          const where = copy.place.label
          /* D218: the alt text is a sentence built AROUND the label ("The card in X"), where
             `where` below is drawn whole as its own line — `PositionLabel.tsx`'s own header
             names this exact firewall and it stays untouched (the Fulfiller's screen has hard
             floors, docs/DESIGN.md). Only the composed sentence gets the safe form. */
          const whereSpoken = where === null ? null : sayPlace(where)
          const between = placeSentence(copy.place)

          return (
            <li key={copy.key}>
              <article className="card-locations-copy">
                {noPhoto ? (
                  <p className="card-locations-say">
                    The photo is missing. The card is still in the place below.
                  </p>
                ) : (
                  <img
                    key={copy.key}
                    className="card-locations-photo"
                    src={
                      photoSrc === undefined
                        ? /* BY NAME (D172): `_copy_row` puts the card's own `cid` on every
                             `SearchCopy`, already filtered to a name that really is a
                             photograph's — so this thumbnail is THIS copy, not whatever
                             occupies its slot by the time the picture loads. */
                          photoUrl(copy.place.box, copy.place.index, copy.cid)
                        : photoSrc(copy)
                    }
                    alt={whereSpoken === null ? 'The card' : `The card in ${whereSpoken}`}
                    onError={() =>
                      setMissing((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
                    }
                  />
                )}

                {where === null ? null : <p className="card-locations-place-large">{where}</p>}
                {copy.place.box_name === null ? null : (
                  <p className="card-locations-say">{copy.place.box_name}</p>
                )}
                {between === null ? null : <p className="card-locations-say">{between}</p>}

                {isPooled(copy) ? null : (
                  <PositionBar
                    place={copy.place}
                    persona="fulfiller"
                    sections={sections?.get(copy.place.box)}
                  />
                )}

                <p className="card-locations-say">{saidState(copy.state)}</p>

                <div className="card-locations-action">
                  {renderAction !== undefined ? (
                    renderAction(copy)
                  ) : sold ? null : (
                    <PullConfirm
                      label="Mark sold"
                      onConfirm={() => {
                        if (busyKey !== null) return
                        onSell(copy)
                      }}
                    />
                  )}
                </div>
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
