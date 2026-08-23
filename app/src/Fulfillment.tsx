import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import type { InventoryCard, SaleResult, SearchCopy, SearchGroup } from './types'
import { ServerError, getInventory, markSold, photoUrl, positionLabel, undoSale } from './server'
import { PullConfirm } from './PullConfirm'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import { useSearch } from './useSearch'
import './Fulfillment.css'

/* The Fulfillment view — docs/DESIGN.md, "Fulfillment view — hard constraints".
 *
 * D5's second persona: a retired, non-technical family member who fills orders from his own
 * device. This screen is the entire product for him. He never sees the capture screen, the
 * pull preview, the review queue or a terminal, so anything this file fails to say is not
 * said anywhere — and there is nobody in the room to ask.
 *
 * BUILT BEFORE GATE B, at the owner's explicit instruction on this branch — and both halves
 * of the sentence that stood here have since been overtaken, each in a different way.
 *
 * "No card has been photographed, no identification has been paid for" was true until
 * 2026-08-22, when Gate B put 53 real cards through capture, identification, the join and an
 * import. The store this screen reads has met cards. "No card has ever reached the `live`
 * state this screen selects on" is dead in the harder way: there is no `live` state any more,
 * and this file went on filtering for one for long enough to serve him an empty list. See
 * WHICH CARDS HE SEES below.
 *
 * WHAT IS STILL TRUE, and is the part of that paragraph worth keeping: no order has ever been
 * pulled on this screen. docs/DESIGN.md says so in the same words about its own instrument —
 * the explaining-twice requirement "has no instrument but the Fulfiller filling a real order,
 * and no order has been pulled". It is built to that document and validated against its
 * numbers and against hand-built fixtures — see `app/tests/fulfillment.spec.ts`, which is
 * where the constraints table lives as assertions rather than as prose in this comment.
 *
 * THE REGISTER IS THE HALF OF THIS FILE THAT IS EASIEST TO BREAK BY BEING HELPFUL.
 * docs/DESIGN.md's copy rules bind hardest here: active voice, the button says exactly what
 * happens, an action keeps its name through the flow, and things are named by what the
 * Fulfiller controls — he has orders and cards, not the things this pipeline is built out of.
 * Three consequences worth stating rather than leaving to be re-derived:
 *
 *   - NO MACHINE STRING APPEARS ON THIS SCREEN. The owner-side habit of printing the
 *     pipeline's own reason string small beneath a friendly label is forbidden here by name
 *     ("Owner-side only: the Fulfillment banned-word list forbids this register entirely").
 *     `PullPreview.tsx` does the opposite and is right to — that is his screen, this is not.
 *     `SaleResult.restores_to` is the newest thing this rule reaches: it is a pipeline state
 *     word, it is read for whether it is null, and it is never drawn. `Failure.code` off the
 *     search is the second, and is read the same way for the same reason.
 *   - THE SERVER'S OWN MESSAGES ARE NOT SHOWN EITHER, and this is the one place this app
 *     deliberately departs from `docs/specs/capture-app.md` section 4. Those strings are
 *     written for the person who can act on them: they name store locks, `make server` and
 *     routes. Every one of them is correct and none of them is his. So failures here say what
 *     happened and what to do next in his vocabulary, and the detail stays where it is
 *     actionable — the owner reads the same failure with the message intact on his screens.
 *     `server.ts:describeFailure` exists for those screens and says in its own comment that
 *     this one does not use it; the search below honours that rather than "finishing the job".
 *   - THE SOLID ACCENT FILL IS THE POINT OF THIS SCREEN. docs/DESIGN.md reserves it for a
 *     screen with exactly one thing to do, and calls his pull-confirm "the loudest thing he
 *     ever sees". So the flow below is shaped so that there IS exactly one thing to do at
 *     each step: the list offers many cards and carries no fill, and the card panel offers
 *     one action and carries it. The receipts above both — see `Sale` — carry no fill either,
 *     which is what lets them sit over the card panel without making the fill mean "press
 *     something". The search results are the newest test of that rule and are held to it —
 *     see `pulledKey`, which is what keeps at most one fill on screen however many copies the
 *     search found.
 *
 * FIVE THINGS THIS FILE DECIDES THAT docs/DESIGN.md DOES NOT SETTLE. Each is marked at the
 * code that makes it, and each names what would settle it. They are gathered here because a
 * reader deciding whether to trust this screen should be able to see all five at once: what
 * "a card to pull" means with no orders in the system, how long undo stays, when the list is
 * read again, the hash route this is mounted at (which only `App.tsx` can make true), and the
 * nav that must not render over it (in the stylesheet, and only until the shell stops drawing
 * one here).
 */

/* WHICH CARDS HE SEES — the first assumption, and the largest.
 *
 * D7 describes the real input: "Order pulls select specific positions and mark them sold
 * individually." There are no orders in this system. Nothing reads a TCGplayer order, no
 * route serves one, and `store/master.py` has no order record — so "the cards in this order"
 * cannot be answered today and this screen answers the nearest question it can: every card
 * that is for sale, in box-walk order, for him to find the one the order names.
 *
 * EVERY COPY THAT IS NOT SOLD. This line read `const FOR_SALE = 'live'` until D7 was amended
 * on 2026-08-23, and the paragraph under it argued for that filter at length: `pushed` meant
 * a row had been written into an import file, `staged` meant TCGplayer had confirmed it, and
 * only `live` meant a later export showed quantity against it — so only a `live` card was one
 * a buyer could have ordered.
 *
 * THAT ARGUMENT IS NOT WRONG. IT IS ABOUT A SKU, AND IT WAS BEING ASKED OF A POSITION. The
 * owner's ruling is that copies of one SKU are fungible: "if i have 15 of one copy and mark 3
 * as live, it's any 3 are live, not 3 specific locations are live and 12 are backstock." So
 * the three stages moved off the card and onto the SKU as counts — `store/master.py:Listing`
 * — and `master.STATES` is now `captured | identified | sold`, with `check_state` refusing
 * the other three outright. D7 states the consequence for this screen in one sentence: "Every
 * unsold copy is sellable. The pull marks whichever copy the hand reached."
 *
 * There is no per-position listing flag left to read, and this file must not grow a stand-in
 * for one. Filtering to `identified` would be exactly that — a proxy for "has a SKU" wearing
 * a state name, which is the fiction D7's amendment deleted. `store/master.py:copies_on_hand`
 * is the same rule on the other side of the wire and says it in the same words: "a copy is
 * sellable because it exists".
 *
 * THE FILTER CHANGED POLARITY, AND SO DID THE DIRECTION IT FAILS IN. Under `=== 'live'` a
 * record whose state was missing or garbled dropped off his list; under `!== 'sold'` it stays
 * on it. That is the right way round — CLAUDE.md forbids silently dropping a card, and this
 * is the one screen with nobody in the room to notice an absence. The cost is bounded and
 * already handled: the worst case is being offered a copy somebody else has sold, which the
 * route refuses as `already_sold` and which this file draws as its own receipt.
 *
 * WHAT IT COSTS HIM, stated rather than discovered: a card photographed ten minutes ago and
 * not yet identified is on his list, under the no-name sentence in `sellable` below. That is
 * D7's answer and not an oversight — nothing distinguishes it physically from the copy beside
 * it — but it is the first thing to watch when a real order is pulled, because it is the one
 * way this list is longer than the old one.
 *
 * IT IS ALSO WHY THE LIST STOPPED BEING ENOUGH ON ITS OWN. This paragraph used to end "until
 * an order feed exists this list is a haystack he searches by name", with the first real
 * order named as what would say whether that is acceptable. The store answered first: 229
 * cards, 176 of them with no name recorded, in box-walk order, with no photo on the row.
 * There is nothing to search by eye. So the haystack got a search field over it — see THE
 * SEARCH below — and the list beneath it is untouched, because a screen that has never been
 * tested on the person who uses it may gain a way in and must not lose one.
 *
 * WHAT WOULD STILL SETTLE IT: an order feed. Item 6 of the Gate B measurements in
 * `docs/specs/capture-app.md` section 10.2 is unchanged by any of this.
 */
/* A copy that has LEFT, whatever the door. `sold` left by a sale; `retired` (D26) was pulled
 * out, damaged, lost or given away. His screen must offer neither: the server would refuse a
 * sale of a retired copy with `card_retired`, and that refusal's message never reaches this
 * screen (D5 — it writes its own sentences), so the honest fix is upstream, in the filter.
 * A Set rather than two comparisons so the next terminal state has one place to land. */
const GONE = new Set(['sold', 'retired'])

/** Whether this copy is one he can be asked to pull. D7 amended: every unsold copy is.
 *
 *  A function rather than an inlined `!==` so that the paragraph above has something to be
 *  attached to. The old constant was findable by grepping for the word it held; a bare
 *  comparison inside the loader would not have been. */
function forSale(card: InventoryCard): boolean {
  return !GONE.has(card.state)
}

/* A POOLED CARD NEVER ENTERS THIS VIEW, and the filter is HERE — the view's — not the
 * server's. The owner's ruling ("Code cards are pooled inventory, not located",
 * docs/DECISIONS.md; `pipeline/games.py`'s `located` flag) is that such a card is a count
 * with no box, section or card position, so there is nothing for this screen to send him
 * to: its whole job is to say where a card is. Server-side omission was considered and is
 * the wrong half of the split — this device downloads the same map the owner's screens
 * read, and a server that hid pooled rows from `GET /inventory` and `GET /search` would
 * blind the OWNER's counts and search to cards he really holds. So the data flows whole,
 * and which cards HIS view offers is this file's ruling, exactly as `forSale` above is.
 *
 * NOT COUNTED INTO `unplaced`, and that is the second half of the decision. That count is
 * a FAULT count — its sentence ends "Ask for help", and help would find nothing to fix
 * here, because a pooled card with no place is a card working as designed. It is not
 * silently dropped either: the record stands in the store, the owner's screens count it
 * and search it, and `app/tests/fulfillment.spec.ts` asserts this exclusion by name —
 * which is where the ruling said the assertion belongs.
 *
 * `!== false` rather than a truthiness test, because absent must read as located: an older
 * server sends no `located` at all, and every block such a server sends carries a real
 * label. */
function pooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

/** The same fact off a search copy, whose place block always arrives. */
function pooledCopy(copy: SearchCopy): boolean {
  return copy.place.located === false
}

/* THE SEARCH — the second way into the same cards, and the smaller of the two decisions in it.
 *
 * THE SHAPE IS THE OWNER'S RULING AND NOT A DEFAULT: a field above, the list kept beneath.
 * Typing narrows; clearing the field gives him back the box-walk list he already had. The
 * alternative — a search screen he navigates to and back from — was declined for the reason
 * this whole file is careful: nothing he can do today may stop working, because nobody has
 * ever watched him do any of it. A flow with no instrument is a flow you add to rather than
 * replace.
 *
 * THE SERVER GROUPS, THIS SCREEN DOES NOT. `GET /search` answers with one group per SKU,
 * each carrying every copy and each copy carrying its own `Place` — which is the whole
 * question he has, since D7 keeps a copy per position precisely so a sale can be recorded
 * against one of them. `Inventory.tsx` answers the same question by pulling the entire store
 * and grouping in the browser; that is right for a screen whose job is to show everything and
 * wrong for this one.
 *
 * EVERY COPY IS ITS OWN CARD, which is the owner's second explicit ruling here and lives in
 * `CardLocations.tsx`'s Fulfiller skin rather than in this file. A card with copies in four
 * places gives him four cards to scroll, each with its own photo, position label, position
 * bar and action, so he walks to whichever slot is nearest. Copies are fungible (D7), so that
 * choice is his and every option has to carry the same information.
 *
 * WHAT THIS FILE OWNS OF THAT COMPONENT IS THE ACTION SLOT, through `renderAction` — see
 * `actionFor`. That prop exists for exactly this: the component's own control is one press,
 * and one press is not what this screen may offer.
 */

/** The sentence a card with no name gets, on both ways in. One constant because it is one
 *  sentence: the browse row builds it from `InventoryCard.name` and a search copy builds it
 *  from `SearchGroup.names`, and two spellings of it is two things to proofread. */
const NO_NAME = 'This card has no name recorded'

/* HOW LONG UNDO STAYS — the second assumption.
 *
 * docs/DESIGN.md's floor is ">= 10s window" and this is double it. The floor is a floor
 * rather than a target, and the two directions cost differently: a window that is too long
 * costs a line of text on a screen he is not looking at, while a window that is too short
 * costs a sale recorded against the wrong card with no way back. He is retired and not
 * hurried; twenty seconds is the reading speed this is drawn for, not the clicking speed.
 *
 * IT IS PER SALE, NOT PER SCREEN, and that is the fix rather than a refinement. This was one
 * slot — a single `Sale | null` that the next mark-sold overwrote — so the ordinary flow voided
 * the guarantee: a real order pull is two or three cards in a row, the second sale silently
 * discarded the first card's undo, and it re-armed the clock for the new card only. The
 * design row reads "present on every mark-sold", and every is the word that was not honoured.
 *
 * IT IS ALSO PER SALE RATHER THAN PER SCREEN IN THE OTHER SENSE: a sale made from a search
 * result and a sale made from the browse list are one code path, one window and one receipt.
 * A second sale path would be a second twenty seconds to keep in step and a second set of
 * refusal rulings — and the receipts already sit above every screen this view has, so the
 * control survives clearing the search exactly as it survives walking into a card.
 *
 * WHAT WOULD SETTLE THE LENGTH: watching him undo one. Gate B item 6 again.
 */
const UNDO_WINDOW_MS = 20_000

/* THE SALE GOES THROUGH `server.ts` LIKE EVERY OTHER CALL IN THIS APP.
 *
 * It did not until 2026-08-13: this file built its own `fetch` against
 * `POST /inventory/<box>/<index>/sold`, and its own base URL out of `photoUrl`, because that
 * module belonged to another group on the day the route landed. It said in as many words that
 * the whole block should be deleted the moment `server.ts` exported a mark-sold call. It has,
 * so it was — `markSold` and `undoSale`, one route in both directions, and the reasoning about
 * the empty body and the missing server-side expiry moved across with them.
 *
 * What stayed here is the only part of it that was ever this screen's: which refusals he is
 * told about, and how. `UNDO_WINDOW_MS` above is the other half of the same split — the route
 * is what makes the sale reversible, and this file decides how long the control stays up.
 */

/* THE THREE REFUSAL CODES THIS SCREEN BRANCHES ON, each with a different ruling. They were one
 * list called ALREADY_THERE, both members answered as success, and that list was wrong about
 * one of its two members in a way that lost data.
 *
 * `not_sold` on a REVERSAL is success. The card is not sold, which is what the tap asked for —
 * the other device reversed it first, which D13 permits by design and neither device is told
 * about. Reported as a failure it is a dead end: the message would say press it again, pressing
 * it again would answer the same way, and the only person who could act on that is not in the
 * room.
 *
 * `already_sold` on a SALE IS NOT THIS DEVICE'S SALE, and reading it as one is a data-integrity
 * bug rather than a cosmetic one. It means somebody else already sold that copy. Answered as
 * success it printed "Marked sold." and offered an Undo — and that Undo would have reached the
 * server and reversed the OTHER device's real sale, putting a card back on TCGplayer that a
 * buyer has paid for. The stale list this device was holding is what made the tap possible at
 * all, so the answer is to say plainly what happened and read the cards again.
 *
 * `sold_origin_unknown` is a refusal with no remedy he owns. `history.jsonl` cannot say what
 * state the card was in before the sale, so the route will not guess, and pressing Undo again
 * answers identically forever. The control comes down and the sentence names the one action
 * that is actually available to him: ask.
 *
 * The CODES and never the messages. The codes are a stable vocabulary worth branching on; the
 * messages are written for the owner and none of them may reach this screen. */
const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const NO_ORIGIN = 'sold_origin_unknown'

/** The server's code for a thrown thing, or `''` for anything that is not a refusal — a dead
 *  network, a body that did not parse, a bug in this app. Empty rather than null so every
 *  comparison below is a plain `===` against a code that cannot match. */
function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/** Reverse one sale, with `not_sold` read as success for the reason above. Selling has no
 *  such wrapper on purpose: after the `already_sold` bug there is no refusal on that side
 *  this screen may quietly swallow. */
async function unsell(box: number, index: number): Promise<void> {
  try {
    await undoSale(box, index)
  } catch (err) {
    if (refusalCode(err) === NOT_SOLD) return
    throw err
  }
}

/** Whether the sale just recorded can be taken back, out of the server's own answer.
 *
 *  ABSENT IS READ AS NULL, deliberately, and the direction is the safe one. A server old
 *  enough to answer this route without the field would otherwise arrive as `undefined` and
 *  typecheck as a string, and this module casts rather than validates — the same gap
 *  `server.ts:positionLabel` guards on the position label. Suppressing an undo that would
 *  have worked costs him a tap and a question; offering one that cannot work is the defect
 *  this whole path exists to remove. */
function canTakeBack(result: SaleResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

/** One card he can be asked to pull: where it is, and what it is called.
 *
 *  `place` is the server's own rendered label — `pipeline/join.py:Position.label`, decorated
 *  onto every inventory row by `do_inventory`. It is never composed here, for the reason
 *  `types.ts` states on the field: a second renderer is a second copy of D10's divider size,
 *  and of the two answers the one on screen is the one somebody walks to a box with. */
type Sellable = {
  key: string
  box: number
  index: number
  place: string
  name: string
}

/** One card that has just left his list, and what he can still do about it.
 *
 *  A LIST OF THESE AND NOT ONE, which is the whole of finding 1's fix. See `UNDO_WINDOW_MS`
 *  for what the single slot cost. Each carries its own `until`, so a second sale cannot
 *  extend or shorten the first card's window, and each renders its own panel — so the count
 *  on screen is the count of sales still standing rather than the most recent one. */
type Sale = {
  card: Sellable

  /** Wall-clock deadline, fixed when the sale is recorded and never touched again. A
   *  duration held here instead would have to be restarted on every re-render. */
  until: number

  /** The sentence at the top of the panel. Two of them exist: his own sale, and the other
   *  device's, which is a receipt for a card leaving his list rather than for anything he
   *  did. Both are receipts, so both are drawn the same way. */
  said: string

  /** False when there is nothing to offer — the server said the sale cannot be reversed, the
   *  reversal was refused with no remedy, or this was never this device's sale. `note` then
   *  says why, because a control that quietly is not there is indistinguishable from one he
   *  failed to find. */
  canUndo: boolean

  /** The second sentence, under the position. Why there is no Undo, or what went wrong with
   *  one. IT LIVES ON THE SALE AND NOT IN `trouble` BY CONSTRUCTION: a failed-undo message
   *  held in screen-wide state outlived the Undo button it told him to press, so the screen
   *  ended up carrying an instruction pointing at a control that was no longer there. Held
   *  here, the sentence and the button expire together because they are the same object. */
  note: string | null
}

/* A card with no rendered position is LEFT OUT of his list, and counted where he can see the
 * count.
 *
 * `do_inventory` leaves a row undecorated when its box or index will not coerce to an integer,
 * on the grounds that a placeholder label would name a position that does not exist. That is
 * the right call and it lands here as a card this screen cannot use for its only purpose: the
 * whole of what it does is say where a card is. `PullPreview.tsx` shows such a row with its
 * store key beside it, which is exactly right on the owner's screen and is the machine
 * register this one may not use.
 *
 * So it is dropped from the walk and reported as a number instead. Never dropped silently —
 * CLAUDE.md's hard rule is that no card leaves the pipeline unrecorded, and a row he cannot
 * see and cannot be told about is the shape that rule forbids.
 */
function sellable(key: string, card: InventoryCard): Sellable | null {
  /* The same one-line rule the owner's two screens read that field with, and the same
   * function — `server.ts:positionLabel`. What differs is what each screen does with a null,
   * and that difference is the argument below rather than a second reader of the field. */
  const place = positionLabel(card)
  if (place === null) return null
  return {
    key,
    box: card.box,
    index: card.index,
    place,
    /* THIS FALLBACK IS NOW AN EXPECTED CASE RATHER THAN A DEFENSIVE ONE, and that changed
     * with the filter above. It read "a live card has been identified, so a null name is not
     * expected" — true while only `live` copies reached here, and false the moment every
     * unsold copy did: a card captured an hour ago and not yet identified has no name to
     * print, and D7 says it is sellable all the same. The store says 176 of 229 today.
     *
     * A sentence rather than a placeholder token, and that was the right call before it had
     * to carry any weight. Everything else in this column is a card's name, and he has no way
     * to know that `null` or `—` is not one. This one says what is true and stops there: the
     * position beside it is what he actually walks to a box with, and it is never missing —
     * a row without one does not reach this function at all. */
    name: card.name ?? NO_NAME,
  }
}

/** The same physical card, in the shape the sale path already knows.
 *
 *  ONE `Sale`, ONE `doSell`, ONE UNDO WINDOW, whichever way in he found the card. The
 *  alternative is a second sale path for the search results, which would be a second twenty
 *  seconds to keep at twenty, a second set of rulings on `already_sold` and
 *  `sold_origin_unknown`, and a second place for the next one of those to be got wrong. This
 *  function is the whole of what the two paths do not share.
 *
 *  `place` is the server's own rendered label again, taken off `SearchCopy.place.label` and
 *  never composed — the same rule `sellable` above reads `InventoryCard.label` under, and the
 *  same one types.ts states on `Place.label`. */
function asSellable(group: SearchGroup, copy: SearchCopy): Sellable {
  return {
    key: copy.key,
    box: copy.place.box,
    index: copy.place.index,
    /* The coalesce is for the type, not for a case this screen can reach: `Place.label`
     * learned to be null for a pooled copy, and `stillHere` drops every pooled copy
     * before one can be pulled — a card with no place must never produce a receipt
     * naming one. An empty string here would mean that filter broke, which is the
     * spec's to catch, not this line's to paper over. */
    place: copy.place.label ?? '',
    name: group.names.length === 0 ? NO_NAME : group.names.join(' / '),
  }
}

/** One search group with the copies he can no longer pull taken out of it, or null when that
 *  leaves nothing.
 *
 *  TWO KINDS OF GONE, AND THEY ARE DROPPED FOR THE SAME REASON. A copy the store already calls
 *  `sold` is not his to sell, and the browse list has never shown one — `forSale` above. A
 *  copy THIS device has just sold is the same card one answer earlier: the sale is recorded,
 *  the receipt is standing above with its Undo, and the search results in hand were fetched
 *  before any of that happened. Leaving it on screen offers him a card that is in an envelope.
 *
 *  WHY THE ROW LEAVES RATHER THAN GOING QUIET IN PLACE. `CardLocations` draws each copy's own
 *  state as a sentence — "In the boxes." — from the wire, and the wire still says unsold until
 *  the next search. A card reading "In the boxes." beside a receipt reading "Marked sold." is
 *  a screen contradicting itself in front of the one person who cannot ask anybody which half
 *  is true. The browse list already answers this the same way: the sold card leaves, and the
 *  receipt above is where the sale is reported and taken back.
 *
 *  `on_hand` COMES DOWN WITH IT AND `listed` DOES NOT, and the difference is not fussiness.
 *  D7 defines `on_hand` as a count of unsold positions, so a sale makes it one smaller and
 *  saying otherwise puts "2 copies here" over one card. `listed` is a per-SKU listing
 *  quantity that `join`, `emit` and `reconcile` own between them — the app reads state and
 *  never sets it (capture-app spec 2.1) — so this leaves it exactly as the server said. */
function stillHere(group: SearchGroup, gone: ReadonlySet<string>): SearchGroup | null {
  const here = group.copies.filter(
    (copy) => !GONE.has(copy.state) && !gone.has(copy.key) && !pooledCopy(copy),
  )
  if (here.length === 0) return null
  const justSold = group.copies.filter((copy) => !GONE.has(copy.state) && gone.has(copy.key)).length
  /* THE THIRD KIND OF GONE, dropped beside the other two: a pooled copy (see `pooled`
   * above) is not his to walk to, so it leaves the group here exactly as a sold one does —
   * and it comes off `on_hand` for the same reason the sale does, because "3 copies here"
   * over two cards is the screen contradicting itself. The server's own `on_hand` is
   * untouched and still counts it, which is where the ruling says the count must survive:
   * the owner's screens. */
  const pooledHere = group.copies.filter(
    (copy) => !GONE.has(copy.state) && !gone.has(copy.key) && pooledCopy(copy),
  ).length
  return {
    ...group,
    copies: here,
    on_hand: Math.max(0, group.on_hand - justSold - pooledHere),
  }
}

/** Box-walk order: box, then index. The order the cards physically sit in, which is the
 *  order docs/DESIGN.md requires of this view and the same order `store/queues.py:sort_key`
 *  falls back to. Reading down the list is walking the boxes. */
function inWalkOrder(cards: Sellable[]): Sellable[] {
  return [...cards].sort((a, b) => a.box - b.box || a.index - b.index)
}

export function Fulfillment() {
  const [cards, setCards] = useState<Sellable[] | null>(null)
  const [unplaced, setUnplaced] = useState(0)
  const [loadFailed, setLoadFailed] = useState(false)
  const [reads, setReads] = useState(0)

  /* WHAT HE TYPED, AND WHAT CAME BACK. The three rules about when a query becomes a request —
   * an empty one asks nothing, a query waits out the debounce, a late answer to an old query
   * is discarded — are all `useSearch`'s, in one place, deliberately. This screen decides only
   * what to draw with the answer.
   *
   * `failure` IS READ FOR WHETHER IT IS NULL AND NEVER DRAWN. It carries the server's own
   * sentence and its own code, both correct and neither his — the same ruling this file makes
   * about `restores_to` and about every refusal on the sale path. */
  const { query, setQuery, results, loading, failure } = useSearch()

  /* The card he is holding, if any, and whether he has confirmed it against its photo.
   * Two pieces of state rather than one enum, because they answer two questions that stay
   * separate: which card, and how far through its two steps. */
  const [chosenKey, setChosenKey] = useState<string | null>(null)

  /** The one copy he has said he is holding, anywhere on this view — the browse list's card
   *  panel and the search results are the same question asked twice.
   *
   *  A KEY RATHER THAN THE BOOLEAN THIS WAS, and the change is what keeps the fill honest.
   *  docs/DESIGN.md gives the solid accent to a screen with exactly one thing to do; the
   *  search can put four copies of one card on screen, and a per-copy boolean would have let
   *  four "Mark sold" fills stand at once. One key means at most one card is past its first
   *  step, so there is at most one fill however long the list is. */
  const [pulledKey, setPulledKey] = useState<string | null>(null)

  /** The position a sale or a reversal is in flight for, or null.
   *
   *  ONE AT A TIME, deliberately: `Store.write()` takes the file lock per call, so several at
   *  once stack against a lock and return their failures out of order. A key rather than the
   *  boolean this was, because `CardLocations` asks for the key and answering it truthfully is
   *  cheaper than explaining why this screen would not. */
  const [busyKey, setBusyKey] = useState<string | null>(null)

  /** Written by this file, never by the server. See the register note at the top. Screen-wide
   *  and short-lived: it belongs to the mark-sold he just attempted, and it is cleared at the
   *  start of the next attempt and on every navigation. Anything that has to outlive a
   *  navigation belongs on a `Sale`, where it expires with the control it refers to. */
  const [trouble, setTrouble] = useState<string | null>(null)

  /** The sales he can still take back, newest first. */
  const [sales, setSales] = useState<Sale[]>([])

  /** Copies this device has sold, for as long as this screen is open.
   *
   *  NOT THE SAME LIST AS `sales`, AND THE DIFFERENCE IS THE BUG IT PREVENTS. A sale leaves
   *  `sales` when its undo window closes, which is twenty seconds and has nothing to do with
   *  whether the card is still sold. Keyed off `sales` a copy would reappear in the search
   *  results a third of a minute after he sold it, offering to sell it again.
   *
   *  An optimistic overlay and nothing more: the wire still says unsold until the next search,
   *  and a reversal takes the key straight back out. `CardLocations` names the same shape on
   *  its own `soldKeys` prop. */
  const [soldHere, setSoldHere] = useState<string[]>([])

  /** The key whose photo did not load, not a boolean: an `onError` for the previous card can
   *  land after he has moved on, and a boolean would blame the card he is looking at. */
  const [photoMissing, setPhotoMissing] = useState<string | null>(null)

  /** READ THE CARDS AGAIN. The list was read once at mount and never again, which is what let
   *  him tap Mark sold on a card the other device had already sold — the stale row was still
   *  on screen an hour later. D13 puts two devices on one store with no session between them,
   *  so the only defence a client has is to re-read at the moments the list can have moved
   *  under it: coming back to it, and finishing a sale. Not a poll — a timer that re-reads
   *  while he is reading is a list that reorders under his thumb. */
  const reread = useCallback(() => setReads((count) => count + 1), [])

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first answer can land after the
    // second. The flag makes the late arrival a no-op rather than a flicker.
    let livePage = true
    getInventory()
      /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, which is the whole of finding 6's
       * fix and reads like a style choice. The two-argument form does not cover its own
       * success handler: anything thrown while walking the answer — `Object.entries` on a
       * body with no `cards`, which is what an older or wrong server returns — became an
       * unhandled rejection, and the screen sat on "Getting the cards." for the rest of the
       * morning with no failure shown and no control to press. This form catches both, so a
       * body this screen cannot read fails the same way a dead server does. */
      .then((inventory) => {
        if (!livePage) return
        /* Pooled cards leave BEFORE the placed/unplaced split, so they land in neither —
         * not a row (nothing to walk to) and not the fault count (nothing is wrong).
         * The argument is at `pooled` above. */
        const offered = Object.entries(inventory.cards).filter(
          ([, card]) => forSale(card) && !pooled(card),
        )
        const placed: Sellable[] = []
        for (const [key, card] of offered) {
          const row = sellable(key, card)
          if (row !== null) placed.push(row)
        }
        setCards(inWalkOrder(placed))
        setUnplaced(offered.length - placed.length)
        setLoadFailed(false)
      })
      .catch(() => {
        if (!livePage) return
        /* THE LIST HE ALREADY HAS IS NOT THROWN AWAY. This used to `setCards(null)`, which
         * was right when the only read was the first one and is wrong now that a re-read can
         * fail: taking a working list off the screen because a refresh did not answer leaves
         * him with less than he had. The full-screen failure below is reached only when
         * there is nothing to show; otherwise the notice sits above the list he is using. */
        setLoadFailed(true)
      })
    return () => {
      livePage = false
    }
  }, [reads])

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline rather than one per sale.
   *
   * Each sale carries its own `until`, so this cannot re-arm anybody's window: it fires at
   * the front of the queue, drops whatever has actually expired, and the state change arms it
   * again for the next one. The slack is what stops a timer that fires a hair early from
   * dropping nothing, returning the same array, and leaving the panel up forever — React
   * bails out on an identical reference, so nothing would re-arm it. */
  useEffect(() => {
    if (sales.length === 0) return
    const soonest = Math.min(...sales.map((sale) => sale.until))
    const timer = window.setTimeout(
      () =>
        setSales((held) => {
          const standing = held.filter((sale) => sale.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [sales])

  const chosen = cards?.find((card) => card.key === chosenKey) ?? null

  /** A set, because `CardLocations` asks for one and because every read of it below is a
   *  membership test. Memoised so the component is not handed a new object on every render. */
  const soldSet = useMemo(() => new Set(soldHere), [soldHere])

  /** What the search found, minus what he can no longer pull.
   *
   *  `total` IS KEPT ALONGSIDE, because "no card has that name" and "every copy of that card
   *  is sold" are two different sentences and the filtered list cannot tell them apart. */
  const found = useMemo(() => {
    if (results === null) return null
    const groups: SearchGroup[] = []
    /* Whether anything the filter took out was POOLED rather than sold. The two empty
     * results need different sentences below — "every copy is sold" is a lie about a card
     * that was never in the boxes — and once the copies are filtered the list alone cannot
     * tell the two apart. */
    let pooledAway = false
    for (const group of results.groups) {
      if (group.copies.some((copy) => pooledCopy(copy) && !GONE.has(copy.state))) {
        pooledAway = true
      }
      const here = stillHere(group, soldSet)
      if (here !== null) groups.push(here)
    }
    return { total: results.groups.length, groups, pooledAway }
  }, [results, soldSet])

  /** Newest first. The sale he is most likely to want back is the one he just made, and the
   *  list everywhere else on this screen is box-walk order for a reason that does not apply
   *  here: these are events, not places. A second sale of the same position replaces its
   *  receipt rather than stacking one on it. */
  const remember = useCallback((sale: Omit<Sale, 'until'>) => {
    setSales((held) => [
      { ...sale, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.card.key !== sale.card.key),
    ])
  }, [])

  const drop = useCallback((card: Sellable) => {
    setCards((prev) => (prev === null ? prev : prev.filter((row) => row.key !== card.key)))
    // And out of the search results, which were fetched before the sale and cannot know.
    setSoldHere((held) => (held.includes(card.key) ? held : [...held, card.key]))
    setChosenKey(null)
    setPulledKey(null)
  }, [])

  const doSell = useCallback(
    async (card: Sellable) => {
      /* Guarded rather than disabled. docs/DESIGN.md gives this view no disabled state at all
       * — `PullConfirm`'s `disabled` prop is documented as owner-side only — and a control
       * that greys out under his finger is a control he presses again harder. A second press
       * while the first is in flight does nothing instead. */
      if (busyKey !== null) return
      setBusyKey(card.key)
      setTrouble(null)
      try {
        const reversible = canTakeBack(await markSold(card.box, card.index))
        drop(card)
        // "Mark sold" produced "Marked sold" — the copy rule that an action keeps its name
        // through the flow, and the reason this state is what the confirmation reads from.
        remember({
          card,
          said: 'Marked sold.',
          canUndo: reversible,
          note: reversible
            ? null
            : 'You cannot take this one back here. Ask for help if it is wrong.',
        })
        reread()
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          /* Not this device's sale, so no Undo — see the ruling at ALREADY_SOLD. Drawn as a
           * receipt rather than as an error because that is what it is from where he sits: a
           * card left his list, and he did not do it. */
          drop(card)
          remember({
            card,
            said: 'Already sold.',
            canUndo: false,
            note: 'Somebody else sold this card, so it has come off your list.',
          })
          reread()
          return
        }
        setTrouble('Nothing was saved. Press Mark sold again.')
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, drop, remember, reread],
  )

  const doUndo = useCallback(
    async (card: Sellable) => {
      if (busyKey !== null) return
      setBusyKey(card.key)
      setTrouble(null)
      try {
        await unsell(card.box, card.index)
        setCards((prev) =>
          prev === null ? prev : inWalkOrder([...prev.filter((row) => row.key !== card.key), card]),
        )
        // And back into the search results, for the same reason it left them.
        setSoldHere((held) => held.filter((key) => key !== card.key))
        setSales((held) => held.filter((standing) => standing.card.key !== card.key))
        reread()
      } catch (err) {
        const dead = refusalCode(err) === NO_ORIGIN
        /* The message goes ON THE SALE, so it cannot outlive the button it names. Says what he
         * can see rather than what the request did: "the sale is still saved" was the first
         * draft and is not always true — the reversal can fail after the other device has
         * already made it — while "the card is not back" is true in every case that reaches
         * this line, which is the test a sentence on this screen has to pass. */
        setSales((held) =>
          held.map((standing) =>
            standing.card.key !== card.key
              ? standing
              : {
                  ...standing,
                  canUndo: dead ? false : standing.canUndo,
                  note: dead
                    ? 'This card stays sold. Ask for help to put it back.'
                    : 'The card did not come back. Press Undo again.',
                },
          ),
        )
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, reread],
  )

  const doSellCopy = useCallback(
    (group: SearchGroup, copy: SearchCopy) => {
      void doSell(asSellable(group, copy))
    },
    [doSell],
  )

  /* THE TWO STEPS, ON A SEARCH RESULT — and this is the whole reason `renderAction` is passed.
   *
   * `CardLocations`'s Fulfiller skin gives every copy a single one-press "Mark sold", and says
   * in its own header comment that the overshoot is the thing it does not cover and that this
   * file's two-step is the fix to reach for. It is: "Pull" and "Mark sold" were one control in
   * one place on the card panel, one state apart, and a double-tap — the ordinary way a person
   * presses a button that did not seem to respond — recorded a sale of a card whose photo he
   * never looked at. One tap of overshoot between a photograph and a sale.
   *
   * So the same fix, in the same shape, in the slot the component hands over: "Pulled." takes
   * the footprint the "Pull" button was in, at the same box model, and "Mark sold" begins
   * below where "Pull" ended. The second tap of a double-tap lands on a sentence. The
   * stylesheet is what makes the box models match — see `.fulfillment-step` — and
   * `app/tests/fulfillment.spec.ts` measures the two rectangles rather than trusting either.
   *
   * A SEARCH RESULT IS NOT A SHORTCUT PAST THE PHOTO. The card panel's first step exists to
   * put a photograph in front of him before anything is recorded; here the photo is already on
   * the copy's own card, above this slot, so the confirm is structural and the step that
   * remains is the one that guards the overshoot.
   *
   * ONLY THE SECOND STEP CARRIES THE FILL. "Pull" is drawn as one of this view's quiet
   * controls, because a list of four copies each with a solid accent button is the drift
   * docs/DESIGN.md's two-jobs rule exists to stop — the fill would stop meaning "there is
   * exactly one thing to do" and start meaning "press something". `pulledKey` holds one key,
   * so exactly one fill can be on screen.
   *
   * THE PLACE IS IN THE ACCESSIBLE NAME AND NOT ON THE BUTTON, the same ruling the receipts
   * make: four copies make four buttons that all read "Pull" to anything that cannot see the
   * card they sit on, and the visible word stays one word because that is what the copy rules
   * ask of a control.
   */
  const actionFor = useCallback(
    (group: SearchGroup, copy: SearchCopy): ReactNode => {
      if (pulledKey !== copy.key) {
        return (
          <button
            className="fulfillment-plain fulfillment-step"
            type="button"
            aria-label={`Pull ${copy.place.label}`}
            onClick={() => {
              setPulledKey(copy.key)
              setTrouble(null)
            }}
          >
            Pull
          </button>
        )
      }
      return (
        <>
          {/* "Pull" produces "Pulled." — the copy rule, and the reason this reads as one flow
              rather than as two controls. */}
          <p className="fulfillment-pulled">Pulled.</p>
          {/* Beside the control it names rather than at the top of a list he has scrolled
              past. `trouble` belongs to the mark-sold he just attempted, and on this screen
              the attempt is always the copy that is past its first step. */}
          {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}
          <PullConfirm label="Mark sold" onConfirm={() => doSellCopy(group, copy)} />
        </>
      )
    },
    [pulledKey, trouble, doSellCopy],
  )

  /* THE RECEIPTS SIT ABOVE EVERY SCREEN THIS VIEW HAS, and that placement is the second half
   * of finding 1. They were rendered inside the list branch only, so walking into a card
   * hid the Undo while its clock kept running: a ten-second promise that could be on screen
   * for two of them. Above the branch, the control survives navigation — and now also
   * survives typing a search and clearing it — and the window means what it says.
   *
   * They carry no fill. docs/DESIGN.md reserves the solid accent for a screen with exactly
   * one thing to do, and a receipt is the way back from the thing he has already done — so
   * the card panel underneath keeps the only fill on screen and the rule is not bent to make
   * this work. */
  const receipts = sales.map((sale) => (
    <div className="fulfillment-panel" key={sale.card.key}>
      <p className="fulfillment-say">{sale.said}</p>
      <p className="fulfillment-place">{sale.card.place}</p>
      {sale.note === null ? null : <p className="fulfillment-say">{sale.note}</p>}
      {!sale.canUndo ? null : (
        /* The place is in the accessible name and not on the button. Two receipts standing at
           once make three buttons that all read "Undo" to anything that cannot see the panel
           they sit in; the visible word stays one word, which is what the copy rules ask of a
           control, and the name says which card it belongs to. */
        <button
          className="fulfillment-plain"
          type="button"
          aria-label={`Undo ${sale.card.place}`}
          onClick={() => void doUndo(sale.card)}
        >
          Undo
        </button>
      )}
    </div>
  ))

  /* A re-read that failed while he already had a list. Says what happened and what to do, and
   * keeps the list — see the loader's catch for why it is not a full-screen failure. */
  const stale =
    loadFailed && cards !== null ? (
      <div className="fulfillment-panel">
        <p className="fulfillment-say">
          These cards may have changed since they were last checked. Try again.
        </p>
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setLoadFailed(false)
            reread()
          }}
        >
          Try again
        </button>
      </div>
    ) : null

  let body: ReactNode

  if (cards === null && loadFailed) {
    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">The cards did not load. Try again.</p>
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setLoadFailed(false)
            reread()
          }}
        >
          Try again
        </button>
      </>
    )
  } else if (cards === null) {
    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">Getting the cards.</p>
      </>
    )
  } else if (chosen !== null) {
    /* THE CARD PANEL — one card, one action, and the fill that says so.
     *
     * Photo-confirm before each pull, which is D6's whole reason for `GET /photo/<box>/<index>`
     * existing: he sees the card's own capture photo beside its location before he pulls it.
     * The list is replaced rather than sat beside, so there is one thing on screen and one
     * thing to do — which is what lets this screen carry the solid fill at all.
     */
    body = (
      <>
        {/* Leaving, not answering, so it is drawn quiet and sits above the card rather than
            beside the action. A second filled control here would make the fill mean "press
            something", which is the drift docs/DESIGN.md's two-jobs rule exists to stop.
            Going back re-reads the cards: the list he is returning to is the one thing on
            this screen that another device can change while he is not looking at it. */}
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setChosenKey(null)
            setPulledKey(null)
            setTrouble(null)
            reread()
          }}
        >
          Back to the cards
        </button>

        <p className="fulfillment-place fulfillment-place-large">{chosen.place}</p>

        {photoMissing === chosen.key ? (
          /* The photo is gone and the card is not. Says where it still is, because that is
             the only part of this screen he needs to finish the job. */
          <p className="fulfillment-say">
            The photo is missing. The card is still in the place above.
          </p>
        ) : (
          <img
            // Remounted per card so a failed load cannot leave the previous card's broken
            // state attached to the next one's element.
            key={chosen.key}
            className="fulfillment-photo"
            src={photoUrl(chosen.box, chosen.index)}
            alt={`The card in ${chosen.place}`}
            onError={() => setPhotoMissing(chosen.key)}
          />
        )}

        <p className="fulfillment-name">{chosen.name}</p>

        {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

        {/* THE TWO STEPS DO NOT SHARE A SPOT, and that is a hazard fixed rather than a layout
            preference. "Pull" and "Mark sold" were the same control in the same place, one
            state apart, so a double-tap on Pull sold the card — one tap of overshoot between
            looking at a photo and recording a sale. The confirmation now takes the slot the
            button was in, at the same box model, so the second tap of a double-tap lands on a
            sentence and "Mark sold" starts below where "Pull" ended.

            The alternative was arming the second button on a timer. Rejected: a control that
            ignores a press is a control he presses harder, and it would have made the fix
            invisible to the thing that has to check it. This one is measurable — the spec
            takes both boxes and asserts they do not overlap.

            The same fix runs on a search result, through `actionFor`. */}
        <div className="fulfillment-action">
          {pulledKey === chosen.key ? (
            <>
              {/* "Pull" produces "Pulled." — the copy rule, and the reason this reads as one
                  flow rather than as two screens. */}
              <p className="fulfillment-pulled">Pulled.</p>
              <PullConfirm label="Mark sold" onConfirm={() => void doSell(chosen)} />
            </>
          ) : (
            <PullConfirm label="Pull" onConfirm={() => setPulledKey(chosen.key)} />
          )}
        </div>
      </>
    )
  } else {
    /* THE LIST SCREEN — a way to find a card by name, over the walk he already had.
     *
     * The field is above and the list is beneath it, which is the owner's ruling. Typing
     * narrows to the copies of what he typed; clearing the field gives the box-walk list back
     * untouched. Nothing he could do before this session costs him anything now.
     */
    const hunting = query.trim() !== ''

    /* What the search has to show, in the order the states actually occur. Assembled before
     * the markup rather than as nested ternaries inside it: five outcomes in one expression is
     * where a screen quietly loses one of them. */
    let hits: ReactNode
    if (loading) {
      // True through the debounce as well as the request — `useSearch` says why — so this is
      // "what is on screen is not an answer to what is in the box yet", which is the honest
      // thing to say while the previous card's copies are still in hand.
      hits = <p className="fulfillment-say">Looking for that card.</p>
    } else if (failure !== null) {
      // What happened, and what to do next, in his words. None of the server's: `failure`
      // carries a sentence naming routes and a code, and neither may reach this screen.
      hits = <p className="fulfillment-say">The search did not finish. Type the name again.</p>
    } else if (found === null) {
      hits = null
    } else if (found.total === 0) {
      hits = <p className="fulfillment-say">No card here has that name. Check the spelling.</p>
    } else if (found.groups.length === 0 && found.pooledAway) {
      // The name matched and what it matched is pooled — never in the boxes, nothing wrong,
      // nothing for him to do. "Sold" would be a lie about it, and the fault sentence
      // ("Ask for help") would send someone to fix a thing working as designed.
      hits = (
        <p className="fulfillment-say">
          That card is not kept in the boxes, so there is nothing to pull.
        </p>
      )
    } else if (found.groups.length === 0) {
      // The name matched and every copy of it has gone. A different fact from the line above
      // and a different thing to do about it, so a different sentence.
      hits = (
        <p className="fulfillment-say">Every copy of that card is sold. There is nothing to pull.</p>
      )
    } else {
      hits = found.groups.map((group, at) => (
        <CardLocations
          /* The SKU when there is one, and the names when there is not — a card the pipeline
             has not put a SKU against yet still has to have a stable identity across renders,
             and `at` alone would re-key every group when one drops out. */
          key={`${at}:${group.sku ?? group.names.join('/')}`}
          group={group}
          persona="fulfiller"
          onSell={(copy) => doSellCopy(group, copy)}
          busyKey={busyKey}
          soldKeys={soldSet}
          renderAction={(copy) => actionFor(group, copy)}
        />
      ))
    }

    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>

        {/* No `autoFocus`: focusing this on his device pops a software keyboard over the first
            thing he was going to read. No key hint either — that is the component's own rule
            for this persona, and docs/DESIGN.md's: his screens are touch and show no keys.
            The debounce stays in `useSearch`, which is why none is passed here. */}
        <SearchField value={query} onChange={setQuery} persona="fulfiller" />

        {hunting ? (
          <div className="fulfillment-results">
            {/* The way back, at the top rather than under a list he would have to scroll. Says
                exactly what happens, which is the copy rule and also the honest description:
                it does not "clear a search", it shows him every card again. */}
            <button
              className="fulfillment-plain"
              type="button"
              onClick={() => {
                setQuery('')
                setPulledKey(null)
                setTrouble(null)
              }}
            >
              Show every card
            </button>
            {hits}
          </div>
        ) : (
          <>
            <p className="fulfillment-say">
              Tap the card the order asks for. You will see its photo and where to find it.
            </p>

            {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

            {cards.length === 0 ? (
              <p className="fulfillment-say">
                No cards are for sale right now. There is nothing to pull.
              </p>
            ) : (
              <ul className="fulfillment-list">
                {cards.map((card) => (
                  <li key={card.key}>
                    {/* The whole row is the target. A row with a button on it has two things to
                        hit and one of them is smaller than the other; this way the smallest
                        target on the screen is the size of the row. */}
                    <button
                      className="fulfillment-row"
                      type="button"
                      onClick={() => {
                        setChosenKey(card.key)
                        setPulledKey(null)
                        setTrouble(null)
                      }}
                    >
                      <span className="fulfillment-name">{card.name}</span>
                      <span className="fulfillment-place">{card.place}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {/* Counted, never silently dropped — see `sellable`. Reads as a sentence rather
                than as a number in a chip, because the only thing he can do about it is tell
                someone. */}
            {unplaced === 0 ? null : (
              <p className="fulfillment-say">
                {unplaced === 1
                  ? '1 card for sale is not shown here, because its place is missing. Ask for help with that one.'
                  : `${unplaced} cards for sale are not shown here, because their places are missing. Ask for help with those.`}
              </p>
            )}
          </>
        )}
      </>
    )
  }

  return (
    <main className="fulfillment">
      {receipts}
      {stale}
      {body}
    </main>
  )
}
