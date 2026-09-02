import { useEffect, useMemo, useRef, useState } from 'react'

import { PositionLabel } from './PositionLabel'
import { PlaceNeighbors } from './PlaceNeighbors'
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'
import { isEditableTarget } from './keys'
import type {
  BoxRecord,
  InventoryCard,
  PricingPayload,
  QueueEntryWire,
  QueueSnapshot,
  RemoveResult,
} from './types'
import type { Failure } from './server'
import {
  describeFailure,
  isDeparted,
  positionLabel,
  getBoxes,
  getQueues,
  getInventory,
  getPricing,
  photoUrl,
  removeCardInPlace,
  reshootPhoto,
  updateCard,
  newCaptureId,
} from './server'
import { BoxIdentity, BoxOps, ClaimEditor, type ClaimPatch } from './BoxOps'
import { reasonLabel } from './reasons'
import { collectorNumber } from './cardNumber'
import { SearchField } from './SearchField'
import { useSearch } from './useSearch'
import './BoxBrowse.css'

/* THE BROWSE — box, then section, then card. One of `#/inventory`'s two ways in (D31).
 *
 * THIS FILE WAS `PullPreview.tsx` AT `#/pull` AND IS THE SAME WALK, taken forward rather than
 * rewritten. The owner's words are in D31: three routes rendered the same 767 records and
 * "read as separate instances of one thing", and the one question a person actually arrives
 * with — what is in this box, and can I click it — was answerable on the screen named after a
 * fulfilment errand and nowhere else. So the route is gone and the walk is now what the
 * inventory's Browse mode renders. Everything the walk had been tuned into keeping — sticky
 * section headers, the segmented strip, one-line rows, the deep keys scoped to the list, the
 * detail panel with the photograph — is unchanged, because it was the best-tested navigation
 * in the app and rewriting it would have thrown that away to arrive back at it.
 *
 * WHAT ACTUALLY CHANGED, and it is one idea: THE STRIP SELECTS RATHER THAN JUMPS. It used to
 * scroll one continuous walk of every card in the store to the first row of a box; it now
 * chooses which box the walk is OF. The reason is the browse's own shape — D31 puts the box
 * operations on the box header, and a header that names one box cannot sit over a list holding
 * four. It is also the density answer: box 2 alone is 544 cards, so a walk of all 767 is a
 * scroller whose position tells you nothing, which is the complaint that started this work.
 * The section headers lost their `Box N ·` prefix in the same move — the box is named once,
 * above the list, by the panel that can also rename and seal it.
 *
 * THE RE-SHOOT CONTROL CAME WITH IT AND MAY NOT BE DROPPED. D26 put it on the pull preview
 * deliberately — "the screen whose whole job is looking at one stored photo beside its
 * position, so the moment a bad photo is discovered is the moment the remedy is already on
 * screen" — and D31 is explicit that the argument is about a detail panel showing one card's
 * photograph rather than about a URL, so it transfers intact and a merge that lost it would
 * have broken D26. It is below, unchanged, at `ReshootControl`.
 *
 * THE ONE WRITE THIS FILE MAKES ABOUT A CARD, AND ITS WHOLE EXTENT: replacing a photograph.
 * D26's re-shoot half — new bytes and a rebuilt sidecar at the same position, record
 * untouched, label unchanged, allocator never involved. Nothing else here writes a card;
 * mark-sold and retire belong to the search half of this screen. `BoxOps` writes the BOX,
 * which is a different object and says so.
 *
 * NO CONFIRM DIALOG, AND THE RE-SHOOT IS IRREVERSIBLE — both at once, deliberately, and the
 * reasoning is capture-undo's (docs/DESIGN.md) transposed: the old bytes are gone, not
 * archived, but the CARD is still in its slot, so the remedy for a wrong re-shoot is another
 * re-shoot. What bounds the loss on undo — the card still in your hand — is here the card
 * still in its box. A dialog would tax every correct replacement to soften a mistake that has
 * a two-tap repair.
 *
 * The photo comes from `GET /photo/<box>/<index>`, which is D6's route and the reason that
 * route exists at all: the review queue requires it and the pull modal reuses it.
 *
 * Owner-side, so density is fine and docs/DESIGN.md's Fulfillment floors do not bind.
 * They bind on 7b's pull modal, which is a different screen for a different person;
 * borrowing them here would make this screen look like his and set the expectation that
 * it is safe for him to use, which it is not — it lists every card in every state, speaks
 * the pipeline's vocabulary, and now carries a control that destroys a photograph.
 */

/* The position label is READ off the wire and never composed here, and the rule now lives in
 * `server.ts:positionLabel` — this file wrote it, the inventory view copied it verbatim, and
 * one rule about one field is one function. The whole argument went across with it, including
 * the part this screen learned the hard way: an earlier draft ported the arithmetic and D10's
 * then-current 25-cards-per-divider constant into TypeScript, which is one divider rule living
 * in two languages with nothing keeping them in step — and of the two answers, the one on
 * screen is the one a person walks to a box with. That constant was DELETED on 2026-08-29
 * (D10, amended: an undeclared box is one section, and dividers exist only where somebody put
 * one), and this screen needed no edit for it, which is the argument above collecting its
 * evidence.
 *
 * What stayed here is the fallback at the call sites below, which is this screen's decision
 * rather than the rule's: a row with no label shows its store key with `no label` in front of
 * it. Recomputing the label locally would trade a visible gap for an invisible disagreement,
 * and only one of those sends someone to the wrong slot.
 */

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and React,
 * and shown verbatim in the one case where a row carries no label — never parsed into a
 * position: a store key and a physical location are two different facts that agree until the
 * box's first divider and diverge behind it, where `3/26` in a box divided at 26 is Section 2,
 * Card 1. (They agree all the way through an undeclared box, which is not a reason to parse
 * one — that is a fact about that box's layout today, and a divider is one keypress away on
 * the capture screen.) */
export type Row = { key: string; card: InventoryCard }

/* Box-walk order — box, then index. The same order `store/queues.py:sort_key` falls back
 * to and the order the cards physically sit in, so reading down this list is walking the
 * box. Rejected: newest first, which is the order you want while capturing and the wrong
 * one while checking a run against the boxes on the desk. */
function rowsOf(cards: Record<string, InventoryCard>): Row[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)
}

/* The identity every control below preserves: `visible` is always a subsequence of
 * `rowsOf`'s answer. The search narrows it, the sections partition it, the box strip
 * indexes it, and every key walks it — one order, stated once, so no two controls on this
 * screen can disagree about what comes next. The constant is module-level so an empty
 * answer keeps one identity across renders and the effects hanging off `visible` do not
 * re-arm while the inventory is still loading. */
const NO_ROWS: Row[] = []

// ------------------------------------------------------------------ the walk, in sections

/* WHICH SHELF A ROW IS ON — the thing the strip selects, and the scope of one walk.
 *
 * A box number for an ordinary card; `pooled` for a card whose game says `located: false`
 * (D24 — a count, not a location, so its `box` is a store key and putting it under a box
 * number would make the strip promise a shelf); `unplaced` for the record whose box will not
 * coerce, which `do_inventory` leaves undecorated and `GET /status` reports. Three shelves and
 * not two, because a design fact and a fault must never share a cell.
 */
type Shelf = number | 'pooled' | 'unplaced'

function shelfOf(row: Row): Shelf {
  if (isPooled(row.card)) return 'pooled'
  const box = row.card.box
  if (typeof box !== 'number' || Number.isNaN(box)) return 'unplaced'
  return box
}

/** What a shelf's cell says on the strip, and what the box header says above the walk. */
function shelfLabel(shelf: Shelf): string {
  if (shelf === 'pooled') return 'pooled'
  if (shelf === 'unplaced') return 'no box'
  return String(shelf)
}

/* Every shelf the current walk touches, boxes first and in the walk's own order.
 *
 * BUILT FROM THE SEARCH-FILTERED ROWS rather than from the whole store, which is the rule the
 * jump strip already followed: under a query the strip offers only shelves that still hold a
 * match, so a cell can never lead to an empty list. The two non-numeric shelves go last and
 * only when something is actually on them — a cell for a condition nothing is in is chrome
 * that has stopped being true, the same rule the key chips follow.
 */
function shelvesOf(rows: Row[], registry: readonly number[] = []): Shelf[] {
  const boxes: number[] = []
  let pooled = false
  let unplaced = false
  for (const row of rows) {
    const shelf = shelfOf(row)
    if (shelf === 'pooled') pooled = true
    else if (shelf === 'unplaced') unplaced = true
    else if (!boxes.includes(shelf)) boxes.push(shelf)
  }
  /* AND EVERY BOX THE REGISTRY KNOWS, WHICH IS NOT THE SAME SET AND WAS TREATED AS THOUGH IT
   * WERE. A box with no cards in it produces no row, so it produced no shelf, so the strip
   * drew no cell for it — and the strip is the ONLY way to select a shelf. `BoxIdentity` and
   * `BoxOps` draw for the SELECTED shelf, so an empty box could not be renamed, re-sectioned,
   * sealed or DELETED from any screen in the product. Measured on the owner's own store: 12 of
   * 13 boxes were unreachable, including every one they had just created to test with.
   *
   * It is `CLAUDE.md`'s route-is-not-a-feature rule caught from the other end — `DELETE
   * /boxes/<box>` exists, is covered by T7, has a client function AND has a control on screen,
   * and none of that is worth anything for a box you cannot put the screen on. And it is a
   * REGRESSION with a commit: `13c397a`, D31's merge, is where both this function and the
   * strip were written, and it is where `#/boxes` — the route whose whole content was the
   * registry list — stopped existing. The merge carried over the cards and not the registry.
   *
   * Sorted numerically rather than left in row order. Row order was already ascending because
   * the walk is, so nothing moves for a store with no empty boxes; what it settles is where a
   * registry-only box lands, which row order cannot answer because it has no row. */
  for (const box of registry) if (!boxes.includes(box)) boxes.push(box)
  boxes.sort((a, b) => a - b)
  const out: Shelf[] = [...boxes]
  if (pooled) out.push('pooled')
  if (unplaced) out.push('unplaced')
  return out
}

/* Which stretch of one shelf's walk a row belongs to, worded as its sticky header will say it.
 *
 * NO `Box N ·` PREFIX ANY MORE, and that is the merge's doing rather than a trim: the walk is
 * scoped to one shelf now and the box is named once above it, by a panel that can also rename
 * and seal it. Repeating the box number down every header would spend most of a narrow
 * column's width restating the one fact that cannot change while you are reading.
 *
 * Composed from the server's own decorations — the label rule at the top of this file forbids
 * position ARITHMETIC here, and this does none: `section` is a number the server sent, and the
 * span is `Place.section_start`/`section_end`, which is the store's own answer to where this
 * section begins and ends. A section with no end is drawn as open rather than filled in with
 * the box total, exactly as the layout table draws it: the two mean different things, and the
 * second is a claim about where a divider is.
 *
 * A pooled row groups under the pooled fact and a bare record under the fault, so a header
 * never claims a location the rows beneath it do not have.
 */
function sectionTitleOf(row: Row): string {
  if (isPooled(row.card)) {
    return `Pooled · ${row.card.place?.game_display ?? row.card.game ?? 'cards'}`
  }
  if (row.card.section === undefined) return 'No position label'

  const start = row.card.place?.section_start
  const end = row.card.place?.section_end
  if (typeof start !== 'number') return `Section ${row.card.section}`
  return typeof end === 'number'
    ? `Section ${row.card.section} · #${start}–#${end}`
    : `Section ${row.card.section} · #${start} onward`
}

type Section = { key: string; title: string; first: Row; rows: Row[] }

/* Run-length over the walk, deliberately not a Map keyed on title: the list's order is
 * `rowsOf`'s and a grouper must not invent a second one. Whatever order the rows arrive in
 * survives exactly — a keyed Map would quietly merge two stretches that something (a
 * record whose box is a string, a future sort) had separated, and the merged header would
 * lie about what sits under it. Keyed by the title plus the first row's key, so React
 * identity holds even when two separated stretches share a title. */
function sectionsOf(rows: Row[]): Section[] {
  const out: Section[] = []
  for (const row of rows) {
    const open = out[out.length - 1]
    const title = sectionTitleOf(row)
    if (open !== undefined && open.title === title) open.rows.push(row)
    else out.push({ key: `${title} @ ${row.key}`, title, first: row, rows: [row] })
  }
  return out
}

/* What a row's left cell says. Under a section header the answer is the slot alone — `17`
 * beneath `BOX 1 · SECTION 2` — read off the server's `card` decoration, never parsed out
 * of the label string: the header and the slot are two server facts drawn at two sizes,
 * and D10's divider arithmetic keeps living in one language. The fallbacks are the old
 * two-line row's, unchanged: a pooled card gets its pooled words, a bare record its store
 * key with `no label` in front, and a row that somehow carries a label without a slot
 * shows the label whole rather than a guess. */
function rowSlot(row: Row): string {
  if (row.card.card !== undefined) return String(row.card.card)
  if (hasDeparted(row.card)) return `departed · ${departedKey(row.card)}`
  const label = positionLabel(row.card)
  if (label !== null) return label
  return isPooled(row.card) ? pooledText(row.card, row.key) : `no label · ${row.key}`
}

/** `join.departed_label`'s store key, composed client-side because this cell drops the rest of
 *  the label (see below) and a key is the part it cannot drop.
 *
 *  THE SPELLING IS THE SERVER'S AND MUST STAY SO — `B3 #96`, D68 as amended: the row above this
 *  one may be a live card whose panel is showing `114/166`, and `3/96` in that company was read
 *  as a printed number by the owner. It is composed here rather than sliced off `place.label`
 *  for `rowSlot`'s own stated reason: this file draws server facts and never parses the label
 *  string. The two spellings are checked against each other by `app/tests/inventory.spec.ts`,
 *  which renders the server's label in the panel and this cell in the walk for one sold card.
 *
 *  `row.key` IS NOT IT, and that is the change of 2026-08-31. The walk's map key is
 *  `${box}/${index}` — the same two numbers, in the shape that reads as a fraction — so the two
 *  looked interchangeable and were, right up until one of them became a thing a person reads. */
function departedKey(card: InventoryCard): string {
  return `B${card.box} #${card.index}`
}

/** A record that is still in this box's index space and in none of its slots — sold or retired.
 *
 *  `slot === null` AND A LABEL, WHICH IS TWO TESTS BECAUSE THE FIELD HAS TWO CAUSES. `types.ts`
 *  says so on `Place.slot`: it is null for a card that has left AND for one the server could not
 *  count. The second answers `label: null` as well — there is no honest label when the cards
 *  could not be counted — so the label is what tells the design fact from the fault, and the
 *  fault keeps the panel `BoxBrowse` already draws for it. `card` is null with it, which is why `rowSlot` above reaches this
 *  line at all — `_flat_place` omits the flat `card` key rather than sending it null.
 *
 *  THE FULL LABEL IS WHAT THIS REPLACES AND IT DID NOT FIT. `Box 3 · departed · 3/31` measures
 *  177px into a 169px cell, so the browser ellipsised it — and what an ellipsis takes off the end
 *  is exactly the store key that D68 put there to tell two departed copies apart. Four departed
 *  Moonfalls drew `Box 3 · departed · 3…` four times. `Box 3 · ` is the part worth spending:
 *  this walk is scoped to one shelf, named in the panel above and in every section header, which
 *  is the same argument that took the box out of those headers.
 *
 *  THE BOX IS BACK INSIDE THE KEY AND THE PREFIX IS STILL GONE, which is not a reversal: the
 *  prefix restated a shelf this walk cannot leave, and `B3` is part of an address the copies
 *  list carries across shelves. Measured at the shipped 11px: `departed · B3 #96` is 130.9px
 *  against the old form's 115.5px, in a cell whose `max-width: 22ch` is the 169.4px the full
 *  label overflowed. 38.5px spare, so the two characters cost nothing this cell has. */
function hasDeparted(card: InventoryCard): boolean {
  return isDeparted(card.place)
}


// -------------------------------------------------------------- stepping through the list

/* Left and Right move the selection one card, in the order `rowsOf` already put them in and
 * no other. The owner asked for this by name — "fast nav" — and what makes it fast is not the
 * binding but the two properties below: a held key repeats, and the ends stop.
 *
 * NOTHING HERE WRITES, and adding a key does not bend the look-only rule in this file's
 * header. A selection change is the same non-event a click on a row already was; the keys buy
 * a hand back, not a new power.
 *
 * ONE TABLE, TWO CONSUMERS: the handler reads `key` and `delta`, and the chips in the header
 * draw `label`. ReviewQueue.tsx pairs each key with its label constant for this reason, and
 * the reason is worth repeating — a screen that can advertise a key nothing listens for will
 * eventually do it, and that failure is invisible until someone presses the key.
 *
 * HOME AND END WERE DECLINED AT WINDOW SCOPE, AND ARE NOW BOUND WHERE THE DECLINE SAID
 * THEY BELONG. The paragraph this replaces refused them because at window scope those keys
 * are the page's own — End is how you reach the bottom of the facts panel — and then named
 * its own fix: "Home and End bound on the list with the chips moved onto it — never a
 * wrap". That is what is built, for all four deep keys: PageUp, PageDown, Home and End are
 * a React handler ON the list element, so holding focus IS the scope and there is no
 * listener to tear down, and the chips advertising them sit under the list saying the
 * condition out loud. The cost the old paragraph feared — one key doing two things
 * depending on where focus happens to be — is conceded rather than argued away: it is paid
 * where the browser itself set the precedent, since PageDown already scrolls whichever
 * pane holds focus, and a chip that names the scope is what keeps the rule visible rather
 * than diagnosed. Still never a wrap, and every end still stops.
 */
const STEPS = [
  { key: 'ArrowLeft', label: '←', delta: -1 },
  { key: 'ArrowRight', label: '→', delta: 1 },
] as const

/* The deep keys, list-scoped — the ruling above. Same table shape as STEPS and for the
 * same reason: the handler reads `key`, the chips under the list draw `label`, and a
 * screen that can advertise a key nothing listens for will eventually do it.
 *
 * PageUp goes to the top of the CURRENT section first and to the previous one only from
 * there. The pair moves by BOUNDARY — the same boundaries the sticky headers draw, so the
 * key does what the picture says — and from the middle of a section the nearest boundary
 * backwards is that section's own start; skipping it would overshoot the header on
 * screen. */
const SECTION_KEYS = [
  { key: 'PageUp', label: 'PgUp', delta: -1 },
  { key: 'PageDown', label: 'PgDn', delta: 1 },
] as const

/* First and last of the CURRENT filter, not of the whole store — Home under a query lands
 * on the first MATCH, which is what "the beginning" means while a filter is on. */
const EDGE_KEYS = [
  { key: 'Home', label: 'Home', last: false },
  { key: 'End', label: 'End', last: true },
] as const

/* Tick the current card, so the mass-select is reachable without leaving the keyboard the rest
 * of this list is driven from. List-scoped like the deep keys and advertised in the same
 * caption — a chip under the list, because that is where the binding lives.
 *
 * A LETTER RATHER THAN SPACE, which is the obvious choice and the wrong one: Space activates
 * whichever button has focus, and every row on this list is a button. */
const TICK_KEY = { key: 'x', label: 'X' } as const

/* Is the person typing?
 *
 * `keys.ts:isEditableTarget` answers for a world of text inputs and counts EVERY `<input>` as
 * one, which was exactly right until this list grew a checkbox on every row. A checkbox takes
 * no text, so a focused one must not silently kill the arrow keys the header advertises —
 * otherwise ticking a card with the mouse is the gesture that breaks the walk, with nothing on
 * screen saying why. Narrowed here rather than in `keys.ts`: four other screens depend on that
 * function meaning what it says, and this is the only list with a non-text input in it. */
function isTyping(target: EventTarget | null): boolean {
  if (target instanceof HTMLInputElement && target.type === 'checkbox') return false
  return isEditableTarget(target)
}

/** What the screen above hands down, and what it gets back.
 *
 *  THIS COMPONENT DRAWS THE WALK AND IS NOT A PAGE. `Inventory.tsx` owns the route, the title
 *  and the one flow that writes cards — the sale, the retirement, their receipts and their undo
 *  windows — so the two exchange exactly four things and nothing else. The alternative was
 *  moving that flow in here, which would have made this file the whole screen and left the
 *  other one a shell; the alternative to THAT was passing twenty pieces of sale state down as
 *  props, which is the same coupling written out longhand. */
type BoxBrowseProps = {
  /** The page title, rendered into this component's one header row. A slot rather than an
   *  `<h1>` of its own: the walk does not own a page title, and the row is where the title has
   *  to sit for the screen to be as short as it now is. */
  head?: ReactNode

  /** Rendered in `.browse-under`, the full-width row beneath the photograph-and-facts band, so
   *  it gets a measure neither of the band's two tracks is — the copies of the selected card, its
   *  receipts and its sale controls. Given as a node rather than as a render function because the
   *  caller already knows which card is selected: it is told below. */
  detail?: ReactNode

  /** Rendered beneath the box header, for the BOX being walked rather than for a card in it.
   *
   *  A SEPARATE SLOT FROM `detail` BECAUSE THE GUARD IS DIFFERENT, and that difference is the
   *  whole reason this prop exists. `detail` is drawn only when a card is selected, which is
   *  right for a panel about one card and wrong for anything about the box: the run panel went
   *  in there first and disappeared whenever the walk had nothing selected — so starting a run
   *  over a box required picking a card in it, for no reason a person could have guessed. */
  boxPanel?: ReactNode

  /** Which card the walk is pointing at, reported on every change and `null` when the filter
   *  leaves nothing to point at. The caller needs it to build `detail`. */
  onSelect?: (row: Row | null) => void

  /** The box registry, as this component's own `GET /boxes` answered it. Reported so the screen
   *  above can draw position bars from real divider layouts WITHOUT a second read of the same
   *  route — one fetch, one owner, one consumer. */
  onBoxes?: (records: readonly BoxRecord[]) => void

  /** Bumped by the caller after it writes a card, to force the same re-read the Reload does.
   *  A sale or a retirement changes a state this walk draws, and the walk holds no second copy
   *  of the inventory to patch. */
  reloadToken?: number

  /** WALK TO ONE CARD, BY STORE KEY — the inbound half of `onSelect`, and the only way anything
   *  outside this component moves the mark.
   *
   *  `Inventory.tsx` draws the selected card's copies (D7's SKU -> positions map) and one of
   *  them is in another box; pressing its position label asks for the walk to go there, so the
   *  photograph, the facts and the box operations all follow. The alternative shapes were an
   *  imperative ref handle and lifting `selected` into the caller: the first hides a state
   *  change inside a method call and the second hands a page the walk's own bookkeeping — the
   *  four effects that keep the mark inside the filter, the shelf and the fold.
   *
   *  `at` RATHER THAN THE KEY ALONE, because the same copy may be asked for twice. Walk to it,
   *  arrow away, press it again: the key has not changed and nothing would fire. The counter is
   *  the request, the key is its subject, and a request already answered is ignored — so a
   *  re-render of the caller cannot re-walk a jump the owner made a minute ago.
   *
   *  A JUMP THAT CANNOT LAND DOES NOTHING, and the two ways it cannot are handled where they
   *  are read below. */
  goTo?: { key: string; at: number } | null

  /** WHAT A RUN WOULD BE SCOPED TO: the box being walked, and the ticked cards inside it.
   *
   *  The third thing this component reports upwards, and it exists for the same reason the
   *  other two do — the walk owns the state and the screen above owns the write. `indices` is
   *  the same `pickedIndices` a bulk claim would reach, so a run and a claim correction can
   *  never disagree about what "the selection" means; `box` is null on a pooled or unplaced
   *  shelf, which has no box to identify. */
  onScope?: (scope: { box: number | null; indices: readonly number[] }) => void

  /** WHEN GIVEN, ArrowLeft/ArrowRight STEP THIS INSTEAD OF THE BOX — the order walk's queue.
   *
   *  The one window listener and the one `STEPS` table stay; what changes is who answers the
   *  key. A second listener in the caller would be a second copy of the four guards above the
   *  move, kept in step by hand. `says` replaces the header chip's sentence so the chips stay
   *  truthful about what the arrows do. The deep keys (PageUp/Down, Home/End, the tick) keep
   *  walking the box: they are about its sections, which is still true while an order drives. */
  arrows?: { says: string | null; onStep: (delta: -1 | 1) => void } | null

  /** Rendered after the header row and before the three-column body. A THIRD SLOT because the
   *  guard is different again: `detail` is drawn only with a selected card, `boxPanel` sits in
   *  the header row that may never become two rows (D39), and a banner about the ORDER driving
   *  the walk is about neither the card nor the box. */
  banner?: ReactNode
}


/* `describeFailure` and `Failure` LIVED HERE and moved to server.ts on 2026-08-13, beside
 * the `ServerError` they destructure. This file's copy was the original and the argument in
 * its docstring travelled with it whole — including the reason it does not offer `make
 * server`, which this screen learned by getting it wrong first. Two later screens had copied
 * it byte for byte, and both of those comments named server.ts as the destination; the third
 * copy is what made the move due. */

/* BRING A ROW INTO VIEW WITHOUT MOVING THE PAGE, and the page is the whole point.
 *
 * `Element.scrollIntoView` scrolls EVERY scrollable ancestor, and the last of them is the
 * document. That is exactly wrong on this screen, and it is wrong in a way `.browse-map`
 * makes worse rather than better: the walk's column is `position: sticky`, so scrolling the
 * document cannot move a row inside it — the browser computes a delta from the row's current
 * geometry, scrolls the page by it, and the row stays exactly where it was. The page moves
 * and nothing is revealed.
 *
 * MEASURED, and it is the owner's report of 2026-08-29 — "picking from a copy of a card moves
 * the screen down a little to where it hides the top bars". At 1280x720 over the two-box
 * fixture, with the page at rest: pressing a copy's walk-to took `window.scrollY` 0 -> 280,
 * which is the document's whole scroll range, putting the nav at y=-280 and the screen's own
 * header at y=-218. The landing row was already going to be visible; what the press bought was
 * losing every control above the fold.
 *
 * SO THE SCROLL IS DONE BY HAND, UP TO A BOUNDARY. Each scrollable ancestor from the row to
 * `boundary` inclusive gets its `scrollTop` adjusted; nothing above `boundary` is touched, so
 * the document scroller is out of reach by construction rather than by a flag that could be
 * dropped. `scroll-margin-top` on the row is honoured because `.browse-row` sets it (28px) to
 * clear its own sticky section header, and a hand-rolled scroll that ignored it would park the
 * landing underneath that header — the failure the stylesheet's declaration exists to prevent.
 *
 * THE INNERMOST SCROLLER TAKES `mode` AND EVERY OUTER ONE TAKES `nearest`. `start` is a
 * statement about where the row sits in the LIST, which is what a jump wants; asking the same
 * of the column outside it would drag the search field and the box strip off the top of a
 * column that is only ever scrolled to reach the box's editors.
 *
 * Rects are re-read per scroller, innermost first, because scrolling one moves the row. */
/** FOCUS MUST NOT MOVE THE PAGE EITHER, which is the second door into the same defect.
 *  `HTMLElement.focus()` scrolls the focused element into view by default — the document
 *  included — so the two presses that hand the keys to the walk (`selectShelf`, and the
 *  landing of a walk-to) could undo `scrollWithin` a line after it ran. Measured, neither
 *  fires today: `.browse-map` is sticky at the top of the viewport, so the list it holds is
 *  already on screen whenever these run. It is a latent second cause rather than a live one,
 *  and it costs one object to close: `scrollWithin` above owns where this component scrolls,
 *  and nothing else in it may. */
const FOCUS = { preventScroll: true } as const

type Bring = 'start' | 'nearest'

function scrollWithin(target: HTMLElement, boundary: HTMLElement | null, mode: Bring): void {
  let node: HTMLElement | null = target.parentElement
  let next: Bring = mode
  while (node !== null) {
    /* THE DOCUMENT IS THE THING THIS FUNCTION EXISTS TO NOT TOUCH, so it is checked FIRST and
       independently of `boundary`. A null ref — this running before the column has mounted —
       would otherwise walk straight past it to `<html>`, which is a scrolling element like any
       other, and the defect would be back with no null check anywhere near the symptom. The
       ceiling has to hold when the boundary is missing, or it is not a ceiling. */
    if (node === document.body || node === document.documentElement) return
    if (node.scrollHeight > node.clientHeight) {
      bringInto(target, node, next)
      next = 'nearest'
    }
    if (node === boundary) return
    node = node.parentElement
  }
}

/** One scroller, adjusted by the smallest amount that satisfies `mode`.
 *
 *  The scroller's CONTENT edge, not its border box: `.browse-list` carries a 1px border, and
 *  `clientTop`/`clientLeft` are what that border measures. Overscrolling is left to the
 *  browser, which clamps `scrollTop` to the scrollable range on assignment. */
function bringInto(target: HTMLElement, scroller: HTMLElement, mode: Bring): void {
  const style = window.getComputedStyle(target)
  const rect = target.getBoundingClientRect()
  const box = scroller.getBoundingClientRect()
  const top = rect.top - (parseFloat(style.scrollMarginTop) || 0)
  const bottom = rect.bottom + (parseFloat(style.scrollMarginBottom) || 0)
  const edge = box.top + scroller.clientTop
  const foot = edge + scroller.clientHeight

  if (mode === 'start' || top < edge) {
    scroller.scrollTop += top - edge
    return
  }
  if (bottom > foot) scroller.scrollTop += bottom - foot
}

/* A POOLED CARD — the owner's ruling that a code card is a count, not a location
 * (`pipeline/games.py`'s `located` flag; "Code cards are pooled inventory, not located" in
 * docs/DECISIONS.md). The server sends its row with no flat label and a `place` block
 * carrying `located: false` plus the game's display name, so this screen can tell the
 * design fact from the fault it already draws a panel for: a row whose box will not coerce
 * arrives with no `place` at all. `!== false` keeps an older server's rows — no flag
 * anywhere — reading as located, which they all are. */
function isPooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

/** The row line and the machine line for a pooled card, one composer for both call sites.
 *  The display name is the server's stamp off the registry; `pooled ·` in front of the
 *  store key so `5/2` cannot read as a position — the same trick the no-label fallback
 *  below plays with `no label ·`. */
function pooledText(card: InventoryCard, key: string): string {
  return `${card.place?.game_display ?? card.game ?? 'pooled'} · pooled · ${key}`
}

type Detail = { label: string; value: string; mono: boolean }

/* What is shown beside the photo, and the reason it is more than the position.
 *
 * §7 asks for the photo and the label. `state` earns its line anyway: it is the other
 * half of the Gate B question — the photo proves the capture landed, the state proves
 * whether anything downstream has touched it. The rest are the fields a run is debugged
 * with, and this is the screen open while it is being debugged.
 *
 * A card's name is a thing a human reads, so it takes the body face; everything else is a
 * value being compared against something, so it takes the utility face. That is
 * docs/DESIGN.md's mono-carries-all-metadata rule applied one field at a time rather than
 * one panel at a time.
 */
/** A SET-VALUED CLAIM, rendered — and it renders BOTH of the panel's two since 2026-08-25:
 *  D3 rung 1's finish and D23's rarity. One renderer rather than two, because a second
 *  hand-rolled `' · '` join is a second thing to keep in step with this one for no benefit.
 *
 *  THE UNION STAYS WIDER THAN `InventoryCard.rarity_claim`'s DECLARED `string[] | null`, and
 *  that is deliberate for the same reason it is wider than `metadata_finish`'s: the paragraph
 *  below applies to both fields.
 *
 *  D3 rung 1's finish claim, rendered. A SET since 2026-08-23 and a bare string before it
 *  — both shapes live on disk permanently, because a bare string reads as a one-member set
 *  and there is deliberately no migration.
 *
 *  `_card_row` ships `asdict(card)` straight to the browser, so this really does receive
 *  whichever shape the record holds. Rendering the value directly is what would print
 *  `normal,reverse_holo` from JavaScript's array coercion — no crash, no error, just a
 *  wrong screen; the union on `InventoryCard.metadata_finish` is what makes that a compile
 *  error instead, and this is the answer to it. " · " is the app's separator for metadata,
 *  which is what this row is. */
function claimText(claim: string | string[] | null): string {
  const members = (typeof claim === 'string' ? [claim] : (claim ?? [])).filter(
    (member) => typeof member === 'string' && member.trim() !== '',
  )
  return members.length === 0 ? 'none recorded' : members.join(' · ')
}

/* WHAT A RUN'S JOIN SAID A CARD IS WORTH, AND HOW LONG AGO IT SAID IT.
 *
 * THE STORE HAS NO PRICE IN IT, and that is D8 rather than a gap: every figure in this product
 * comes out of the TCGplayer Filtered Export, and `store/master.py` holds not one field
 * shaped like money. So the answer is not on the record the walk already has, and the question
 * "what is this card worth" could be answered on `#/pricing` and nowhere the operator is
 * actually standing when they ask it.
 *
 * THE EDGE IS D46'S, REUSED RATHER THAN REBUILT: card -> `run` -> that run's `pricing.json`.
 * `cli/cmd_join.py` writes that file on every join with each matched SKU's export row verbatim
 * AND every position holding a copy, so a position resolves to a SKU and a market price with no
 * new route, no new field on the wire and no schema change anywhere. `GET /pipeline/runs/<name>
 * /pricing` is free, read-only and creates nothing, which is what makes it safe to open from a
 * screen that is not about running anything.
 *
 * KEYED BY POSITION AND NOT BY `card.sku`. That field is written by `emit`, for SKUs that
 * reached an import file — so a sub-threshold card, a withheld one (D49) and every card in a run
 * that was joined but never emitted all carry `null` and would silently drop out. The position
 * is on both sides of this join and is written by neither.
 *
 * NOT ON THE WALK'S OWN READ. `GET /inventory` answers with the whole store and knows nothing
 * about runs; folding a price into it would put a per-run figure onto a record whose whole
 * contract is that the app READS state and never sets it. */
type MarketRead =
  /** The run's table, indexed. `at` is `written_at` — when `join` last read an export — or
   *  null against a server too old to send it. */
  | { kind: 'table'; at: number | null; rows: Record<string, string | null> }
  /** No table to read, and WHY, because the two reasons have different remedies: a run that
   *  predates `pricing.json` wants a re-join, and everything else wants a look at the server. */
  | { kind: 'absent'; why: string }

/** One payload, turned into the only two things this panel asks it: which positions the join
 *  matched, and what the export's Market cell said for each. Every other column stays on
 *  `#/pricing`, which is the screen for deciding a price rather than for reading one. */
function marketTable(payload: PricingPayload): MarketRead {
  const rows: Record<string, string | null> = {}
  for (const priced of payload.pricing?.skus ?? []) {
    for (const at of priced.positions ?? []) {
      rows[`${at.box}/${at.index}`] = priced.snap?.market ?? null
    }
  }
  return { kind: 'table', at: payload.written_at ?? null, rows }
}

/* THE MARKET ROW'S VALUE, INCLUDING EVERY WAY THERE IS NOT ONE.
 *
 * A PRICE IS NEVER DRAWN WITHOUT ITS AGE, which is the owner's ask and is also the only honest
 * way to draw it. `join` is free and re-runnable and is routinely pointed at a refreshed export,
 * so two cards on one shelf can carry prices read a week apart — and a bare `$5.47` claims a
 * currency the file cannot support.
 *
 * `read`, NEVER `as of`. The age is the age of the JOIN, not of the price: the export is a CSV
 * the operator downloaded from TCGplayer at some earlier moment nothing on this machine can see,
 * so the freshest thing this can truthfully say is when the pipeline last looked at it. The
 * `written_at` field on the server carries the same paragraph at the other end.
 *
 * `no_market_data` VERBATIM, UNDERSCORE AND ALL, and the underscore is the whole point. It is
 * `pipeline/routing.py`'s own constant — `NO_MARKET_DATA` — and D9 is emphatic that a blank
 * Market cell is an UNKNOWN price rather than a low one, which is the mistake that entry exists
 * to prevent: rendering it as `$0.00` is what hands a chase card away at the floor. Spelled
 * `no market data` it is neither the machine string nor a human label, which is the second
 * vocabulary D22 refuses and D16 exists to catch — and it would grep to nothing on the day
 * somebody holds this screen against `decisions.json`'s own `no_market_data` block, which is
 * where such a card is priced by hand.
 *
 * THE SPLIT IN THIS FUNCTION IS THEREFORE: plain English where THIS SCREEN has nothing (the
 * shape every other fallback in the list takes — `not identified yet`, `none recorded`), and the
 * pipeline's own word where the PIPELINE said something. `no row in this run` is the first
 * kind: a position absent from the table is not a classification the pipeline made, and the
 * queue block below these rows is what names the reason when there is one.
 *
 * EVERY SENTENCE HERE IS CUT TO THE 181px THE VALUE TRACK GIVES IT, and that is a constraint on
 * this function rather than a style. Three of them were over it: the priced form (see below),
 * `no row matched by this run` at 236.6px, and `no pricing table — join this run` at 291.2px,
 * which is drawn where the refusal is caught. The budget is 19 characters at 9.1px each, and a
 * sentence written past it does not fail loudly — it silently costs the row a second line and
 * pushes the panel down. */
function marketText(card: InventoryCard, read: MarketRead | undefined): string {
  if (card.run === null) return 'not joined yet'
  if (read === undefined) return 'reading…'
  if (read.kind === 'absent') return read.why

  const price = read.rows[`${card.box}/${card.index}`]
  /* A POSITION THE TABLE DOES NOT HOLD IS NOT A MISSING PRICE — it is a card the join matched
     no catalog row for, which is `no_catalog_row` and is the review queue's business. The block
     below these rows already says so when it is; this row says only that it has no figure. */
  if (price === undefined) return 'no row in this run'
  if (price === null) return 'no_market_data'

  /* `read 12d` AND NOT `read 12 days ago`, WHICH IS A MEASUREMENT AND NOT A HOUSE STYLE. The
     value track is 181px and this row is the only one on the panel carrying two facts, so the
     full wording wrapped every priced card: `$0.34 · read 9 hours ago` is 218.4px against a
     `Run` row at 163.8px that fits. See `sinceText` for the arithmetic and for why the queue
     age keeps its words.

     `read` SURVIVES AND `ago` DOES NOT, which is the trade rather than an abbreviation taken as
     far as it would go. `read` is what says the age is the JOIN's — the export is a CSV
     downloaded from TCGplayer at a moment nothing on this machine can see — and dropping it
     leaves `$0.34 · 12d`, which could as easily be read as twelve days on the market. `ago` is
     the redundant word: `read` is already past tense, and it is the wider of the two at 36.4px
     against 45.5px, so keeping the verb costs less than keeping the preposition.

     `no age` RATHER THAN `age unknown` FOR THE SAME 181px REASON. That branch is a server too
     old to send `written_at`; at 127.4px of suffix it fitted `$0.34` and wrapped `$149.99`,
     which is a wrap in the one state that cannot be reproduced by looking at a card. It joins
     `none` and `not recorded` further up this list, which is the register the panel already
     uses for a fact it does not have. */
  const age = read.at === null ? null : sinceText(read.at * 1000, 'compact')
  if (age === null) return `$${price} · no age`
  return `$${price} · ${age === 'today' ? 'read today' : `read ${age}`}`
}

function detailsOf(card: InventoryCard, market: MarketRead | undefined): Detail[] {
  return [
    { label: 'Card', value: card.name ?? 'not identified yet', mono: card.name === null },
    { label: 'Number', value: numberCell(card), mono: true },
    /* THE MODEL'S OWN HEDGE, DIRECTLY UNDER THE READ IT HEDGES. `confidence` qualifies the two
     * rows above it and nothing else, so it sits against them rather than at the bottom of the
     * panel — D35's failure mode is a name-and-number pair a human has to judge, and five rows
     * between the read and the hedge makes that two glances instead of one.
     *
     * THE ONLY PLACE A RESOLVED CARD'S CONFIDENCE IS READABLE. `ReviewQueue.tsx` renders this
     * field too, but only for a card that was QUEUED; box 2's five `medium` reads cleared
     * routing and are visible on no screen at all today.
     *
     * SHOWN FLAT, AND THAT IS DELIBERATE. T1's recorded misses and D35's nine Pokedex misreads
     * are all CONFIDENT and wrong, so `high` is not reassurance. That is an argument about what
     * the value MEANS, not about whether to print it, and docs/DESIGN.md's owner-screen rule is
     * the machine value verbatim. So: a plain mono row like every other — never a chip, never a
     * colour, never an accent.
     *
     * `none recorded` and not `none`, matching `ReviewQueue.tsx`'s rendering of the same field.
     * Two screens spelling one field's null two ways is the drift types.ts's header rails
     * against. */
    { label: 'Confidence', value: card.confidence ?? 'none recorded', mono: true },
    // The record's own game claim, verbatim. Null means written before the field existed
    // — the pipeline reads that as pokemon, and saying "not recorded" is the honest form
    // of the same fact. Earns its line the day boxes are mixed: it is what explains why
    // the panel above says pooled, or does not.
    { label: 'Game', value: card.game ?? 'not recorded', mono: true },
    { label: 'State', value: card.state, mono: true },
    { label: 'Captured', value: capturedText(card.captured_at), mono: true },
    { label: 'Set hint', value: card.set_hint ?? 'none', mono: true },
    { label: 'Finish', value: claimText(card.metadata_finish), mono: true },
    /* THE TWO CLAIMS THIS PANEL COULD ALREADY OVERWRITE AND NEVER SHOWED. `CardOps` ->
     * `ClaimEditor` writes FIVE claims — game, set hint, finish, rarity and note — and this list
     * drew three of them, so the button directly beneath these rows replaced two values that
     * appeared nowhere on the screen. Worse than silent: `ClaimEditor` opens with those fields
     * EMPTY and reads armed-and-empty as a clear, so the correction was a blind overwrite.
     *
     * `rarity_claim` is set on 543 of 543 records, so this was live rather than latent, and
     * `BoxOps.tsx` carries the scar from the other end of the same seam — a client function that
     * "silently omitted `rarity_claim`, which the route had always accepted".
     *
     * RARITY RENDERS VERBATIM, and abbreviating it to the box's own `C/UC` is the temptation to
     * refuse: D22 says "rarity strings render verbatim, the way reason codes do. A second
     * friendly vocabulary is a thing nothing audits." The box NAME is free text the operator
     * typed; this is the exact `Rarity` cell `pipeline/games.py` authors and the ladder compares
     * against, and the two being free to disagree on screen is the point.
     *
     * RARITY SITS BESIDE FINISH because they are read together — D23 job 2 makes the rarity
     * claim narrow the finish chips, so a finish offer that looks wrong is explained by the row
     * above it. NOTE GOES LAST because it is the one unbounded free-text value here: a note that
     * wraps grows the panel from the bottom rather than shifting aligned rows under it. That
     * tail is also `ClaimField`'s own order in the editor beneath, so correcting a claim is a
     * straight read-down from fact to field.
     *
     * NEITHER ROW IS CONDITIONAL, though `note` is null on all 543 today. A row that disappears
     * leaves "this card has no note" and "this screen does not show notes" indistinguishable,
     * which is the bug being fixed. D22 makes the note the whole identity of a `misc` card —
     * "a free-text operator note instead, so it is findable by search" — so the first misc
     * capture is a card whose only distinguishing field would otherwise be invisible on the
     * screen named after finding cards. */
    { label: 'Rarity', value: claimText(card.rarity_claim), mono: true },
    /* WHICH RUN READ THIS CARD — the join between this panel and the Runs panel one column to
     * the right, which lists run directories and cannot say which cards each one touched. The
     * operator's loop is walk the box, find the card, run the pipeline, come back and see what
     * changed, and until now the last step had nothing to land on. This list's own comment
     * already promised "the fields a run is debugged with" while omitting the field naming it.
     *
     * PER CARD AND NOT PER BOX, even though all 543 records currently carry one string:
     * `store/master.py` sets `card.run = run or card.run` inside `record_identification`, and
     * D33 scopes a run to a SELECTION inside a box, so two cards in one box can legitimately
     * carry different runs. */
    { label: 'Run', value: card.run ?? 'not identified yet', mono: true },
    /* WHAT THAT RUN'S JOIN SAID THIS CARD IS WORTH, DIRECTLY UNDER THE RUN THAT SAID IT — the
     * owner's ask of 2026-08-29, "if a join has happened on that set, can I get the TCG Market
     * Price as part of the data summary... with a note of how stale/fresh that data is".
     *
     * BENEATH `Run` FOR THE REASON `Confidence` SITS BENEATH THE READ IT HEDGES. The price is
     * not a property of the card, it is what one join found in one export, and the age drawn
     * beside it is that join's age — so provenance is a straight read-down rather than two
     * glances. Both would be inexplicable apart: `Run` names a directory and cannot say what it
     * found, and a price with no run named is a number from nowhere.
     *
     * ABOVE `Note`, WHICH KEEPS ITS PLACE AS THE LAST ROW for the reason stated there — it is
     * the one unbounded free-text value in this list, so it grows the panel from the bottom
     * rather than shifting aligned rows underneath it.
     *
     * NEVER CONDITIONAL, the same rule the two rows above it follow: a row that disappears
     * leaves "this card has no price" and "this screen does not show prices" indistinguishable,
     * and `marketText` has a sentence for every one of the five ways there is no figure. */
    { label: 'Market', value: marketText(card, market), mono: true },
    { label: 'Note', value: card.note ?? 'none', mono: card.note === null },
  ]
}

/* WHEN THIS CARD WAS PHOTOGRAPHED, AS A PERSON SAYS IT. The store keeps
 * `2026-08-23T18:35:05.621+00:00` and this panel printed it verbatim, where it was by some way
 * the longest value on the card — ~234px against the ~100px this draws, on a row grid whose
 * width every other value then had to live inside. The owner's instruction, 2026-08-25: "state
 * an actual understandable human time like 2pm 9/24".
 *
 * LOCAL TIME, NOT THE STORED ZONE. The stamp is UTC and the operator is not; a "human" time
 * eight hours out is worse than the machine one, because it reads as wrong rather than as
 * technical. `toLocaleString` asks the browser, which is the owner's own Mac (D13).
 *
 * THE PRECISION IS NOT LOST, IT IS ELSEWHERE. `docs/GATES.md`'s cadence measurements come off
 * `captured_at` at millisecond precision, and every one of them was taken by reading the store
 * — never by looking at this panel. A screen that answers "where is this card" wants the hour;
 * `curl /inventory` still has the rest of it.
 *
 * A STRING THAT WILL NOT PARSE IS RETURNED VERBATIM rather than rendered as `Invalid Date`. The
 * field is a free `Optional[str]` in `store/master.py` and nothing validates it, so the honest
 * failure is to show what is actually stored. */
function capturedText(stamp: string | null): string {
  if (stamp === null) return 'not recorded'
  const at = new Date(stamp)
  if (Number.isNaN(at.getTime())) return stamp

  const clock = at
    .toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    .replace(/\s?([AP])M/i, (_m, half: string) => half.toLowerCase() + 'm')
  const day = at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  /* The year only when it is not this one — it is the same for every card in the store today,
     so printing it on all 543 spends width to say nothing. */
  const year = at.getFullYear()
  const suffix = year === new Date().getFullYear() ? '' : ` ${year}`
  return `${clock} · ${day}${suffix}`
}

/* Shown as the model returned it, unpadded. `pipeline/join.py:join_key` zero-fills to
 * three digits to match the export's `Number` column, and doing that here would put a
 * string on screen that nothing in the run ever said — which is the wrong trade on the
 * screen someone opens to find out what the run actually said. */
/** The open question about one position, or null — the entry and which queue it is in.
 *
 *  BOTH QUEUES ARE SEARCHED AND THE ANSWER SAYS WHICH, because they mean different things to
 *  the person standing at the box. `review` is worked expensive-first behind a starvation tier;
 *  `parked` is sub-threshold and, in `server.ts`'s own words, "the low-value queue an
 *  unidentifiable card may never be worth a tap on". Knowing which one a card is in is most of
 *  knowing whether to go and answer it. */
function openQuestion(
  snapshot: QueueSnapshot | null,
  row: Row,
): { entry: QueueEntryWire; queue: 'review' | 'parked' } | null {
  if (snapshot === null) return null
  const mine = (entry: QueueEntryWire) =>
    entry.box === row.card.box && entry.index === row.card.index
  const inReview = snapshot.review.find(mine)
  if (inReview !== undefined) return { entry: inReview, queue: 'review' }
  const inParked = snapshot.parked.find(mine)
  return inParked === undefined ? null : { entry: inParked, queue: 'parked' }
}

/** How long ago a moment was, coarsely — `3 days`, `4 hours`, `today`, or the same fact
 *  compacted to `3d` / `4h`.
 *
 *  ONE VOCABULARY FOR THE TWO AGES THIS PANEL DRAWS, which is the whole reason it is a
 *  function rather than two. A card can carry both at once — how long its question has been
 *  waiting, and how long ago the join read its price — and two spellings of "two days" sixteen
 *  pixels apart is the drift `reasons.ts` was extracted to stop one screen further on.
 *
 *  THE COMPACT FORM IS A SECOND RENDERING AND NOT A SECOND VOCABULARY, which is the whole
 *  reason it is a parameter here rather than a helper beside `marketText`. The thresholds, the
 *  rounding and the `today` floor stay in one place, so the two ages can never come to disagree
 *  about which day a moment falls on — only about how many characters they spend saying it. A
 *  private `compactAge()` next to its one caller would have been the same rule written twice.
 *
 *  IT EXISTS BECAUSE OF A MEASUREMENT AND ONLY THE MARKET ROW TAKES IT. The facts list draws at
 *  `column-width: 260px`, which at the owner's 1440 gives two columns of 277px and a value
 *  track of 181px at 9.1px per character — 19 characters. `$0.34 · read 9 hours ago` is 218.4px
 *  and wrapped every priced card onto two lines. `$0.34 · read 9h` is 100.1px of suffix, which
 *  leaves eight characters for the figure. The queue age keeps the words: it is drawn in
 *  `.browse-queued` below the list, which is full-width and has never been short of room.
 *
 *  AND THE WORDS ARE UNBOUNDED WHERE THE COMPACT FORM IS NOT. `N days` grows with N — a
 *  year-old join renders `read 400 days ago` — so the wrap was the ordinary case rather than a
 *  bad one. `Nd` is four characters until 2036. */
function sinceText(at: number, form: 'words' | 'compact' = 'words'): string {
  const elapsed = Date.now() - at
  const days = Math.floor(elapsed / 86400000)
  if (days >= 1) return form === 'compact' ? `${days}d` : `${days} day${days === 1 ? '' : 's'}`
  const hours = Math.floor(elapsed / 3600000)
  if (hours < 1) return 'today'
  return form === 'compact' ? `${hours}h` : `${hours} hour${hours === 1 ? '' : 's'}`
}

/** How long an entry has been waiting, in the queue's own terms. */
function waitingFor(firstSeen: string): string {
  const at = Date.parse(firstSeen)
  return Number.isNaN(at) ? 'unknown age' : sinceText(at)
}

/* `none` IS THIS SCREEN'S WORD AND THE COMPOSITION IS `cardNumber.ts`'S (D67). What was here
 * tested `printed_total === null` one line below a test of `number` for the same, and the store
 * writes `""` on 174 of its 676 numbered records — so a quarter of the walk drew `198/219/`.
 * The fact row wants a word rather than a blank cell, which is the one thing this keeps. */
function numberCell(card: InventoryCard): string {
  return collectorNumber(card) ?? 'none'
}


export function BoxBrowse({
  head,
  detail,
  boxPanel,
  arrows = null,
  banner,
  onSelect,
  onBoxes,
  onScope,
  goTo,
  reloadToken = 0,
}: BoxBrowseProps) {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  /* WHICH SHELF THE WALK IS OF, or null before the first read has said which shelves exist.
   * The strip writes it and the effect below keeps it honest against the current filter.
   *
   * NOT PERSISTED, and worth one line because two neighbours in this app are. `useCamera.ts`
   * remembers a device and a rotation and D27 lets the capture screen remember its claims —
   * both because they describe THIS RIG and would be wrong shared. Which box you were last
   * looking at describes a minute of reading, not the rig, and a browse that reopened on box
   * 95 because that is where a different question ended would be a screen arguing with the
   * person who just opened it. */
  const [shelf, setShelf] = useState<Shelf | null>(null)

  /* THE MASS-SELECT, by store key rather than by index. `PUT /inventory/<box>` takes indices, so
   * a set of bare integers is what it ultimately wants — and a set of bare integers is also a
   * set that means something different in every box. Keyed by `"<box>/<index>"` the ambiguity
   * cannot be expressed, and `pickedIndices` below narrows to the shelf being walked at the one
   * moment the box number is known.
   *
   * NOT PERSISTED, AND THAT IS A SAFETY RULE RATHER THAN A PREFERENCE. A restored selection is
   * one a later bulk write acts on without anybody having chosen it in this sitting, which is
   * the shape of a real accident: eighty-five cards claimed for the wrong game because a tab
   * remembered a tick from yesterday. D27 permits `sessionStorage` for the capture screen's own
   * claims; this is the case that permission is not for.
   *
   * CLEARED WHEN THE BOX CHANGES, for the same reason it is keyed rather than indexed: the
   * write is box-scoped, so a selection that outlived a box change would be a set of ticks the
   * next apply silently ignores. */
  const [picked, setPicked] = useState<readonly string[]>([])

  /* Which sections the owner has explicitly opened, by section key. THE SET HOLDS THE OPEN ONES
   * RATHER THAN THE CLOSED ONES, which is what makes collapsed-by-default cost no bookkeeping:
   * a box that has never been touched has an empty set and folds itself, and a section that
   * arrives from a re-read is closed without anything having to notice it arrived.
   *
   * IT IS PER-BOX FOR FREE. A section key is its title plus its first row's store key, and a
   * store key names a box — so switching boxes shows the new box's own folds and coming back
   * finds the old ones. Not persisted, for the same reason the shelf is not: which sections
   * were open describes a minute of reading, not the rig. */
  const [opened, setOpened] = useState<readonly string[]>([])

  /* The box registry, for the panel above the walk — `GET /boxes`, the one route that renders
   * a box's own layout. Empty until it answers and empty forever if it never does: the walk
   * does not depend on it, so a dead `/boxes` costs the header and nothing else. Kept as the
   * raw list rather than a map because it is four rows today and thirty at worst, and a
   * `.find` over thirty is not a data structure worth having. */
  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])
  /* The key whose photo 404'd, not a boolean: an `onError` from the previously selected
   * card can land after the selection has moved, and a boolean would blame the wrong
   * card for a missing file. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)

  /* THE OPEN QUESTIONS, READ ONCE FOR THE WHOLE SCREEN. A card can be sitting in the review
   * queue with nothing this panel says about it — live right now, `2/95` is `no_catalog_row`
   * with zero candidates and two days old, and walking to it in the box list tells you nothing
   * is wrong with it. `State: identified` is not merely silent there, it is MISLEADING: `state`
   * describes how far capture and identify got, and the open question was raised by the JOIN.
   *
   * NOT A PER-CARD FETCH. `GET /queues` returns both queues whole — it is what `#/review` reads
   * on mount — so one read serves every card the walk can land on, and stepping through a box
   * with the arrow keys costs nothing. Re-read on the same counter every other write here uses.
   *
   * FAILS SILENT, DELIBERATELY. This is a decoration on a panel whose job is where the card is;
   * a queue read that 404s must not put a refusal over a position label. `null` and the block
   * simply does not draw — which is the same state as "no open question", and that is honest:
   * both mean this screen has nothing to add. */
  const [queued, setQueued] = useState<QueueSnapshot | null>(null)

  /* THE MARKET PRICES, ONE RUN'S TABLE AT A TIME AND CACHED BY RUN NAME. `pricing.json` is
   * per-run and every card in a box normally names the same run, so walking a whole box costs
   * ONE read — the same argument `queued` above makes for reading both queues whole rather than
   * per card, and it matters more here: a real table is ~80KB for 50 SKUs, which is cheap once
   * and silly per arrow key.
   *
   * KEYED BY RUN AND NOT BY BOX, because a run is what wrote the file. D33 scopes a run to a
   * SELECTION inside a box, so two cards on one shelf can legitimately carry different runs and
   * therefore two tables read at two different moments — which is exactly the staleness the row
   * exists to report.
   *
   * FAILS INTO A SENTENCE RATHER THAN SILENT, unlike `queued` beside it, and the difference is
   * the point. A missing queue entry and a card with no open question are the same fact, so
   * drawing nothing is honest there. A missing PRICE and a price of nothing are not: this row
   * is always drawn, so a read that refused has to say it refused rather than leave `Market`
   * looking like a card nobody has priced. */
  const [priced, setPriced] = useState<Record<string, MarketRead>>({})
  /* Every run a fetch has already been started for. A ref rather than reading `priced`, because
   * the state lands one render AFTER the request goes out — and the effect below re-runs
   * whenever any OTHER run's table arrives, which is a second request for a run already in
   * flight. Bookkeeping about requests, never a fact drawn: `askedAt` one screen up is the same
   * shape for the same reason. */
  const asked = useRef<Set<string>>(new Set())
  const [reloads, setReloads] = useState(0)
  /* Each re-shot card's NEW capture id, by row key — the cache nonce PhotoPanel appends
   * after a replacement, and nothing else. The id rather than a counter because it
   * already names the exact photograph the screen expects, so a `?reshot=<id>` in a
   * network log is self-explaining. Kept across reloads deliberately: the URL is the
   * same stable one, and the bytes behind it are still the ones this id names. */
  const [reshot, setReshot] = useState<Record<string, string>>({})
  /* The key of the replacement in flight, or null — one at a time, the same rule every
   * write in this app follows: `Store.write()` takes the file lock per call. */
  const [reshootBusy, setReshootBusy] = useState<string | null>(null)
  /* A refusal PAIRED WITH ITS CARD, not floated loose: stepping to the next card must
   * not carry the previous card's refusal under a photo it says nothing about. */
  const [reshootFailure, setReshootFailure] = useState<{ key: string; failure: Failure } | null>(
    null,
  )
  const listRef = useRef<HTMLUListElement | null>(null)
  /* THE COLUMN, AS THE CEILING ON EVERY SCROLL THIS COMPONENT PERFORMS. `scrollWithin` walks
   * scrollable ancestors up to this node and stops, so the document scroller cannot be reached
   * — which is the whole fix, stated as a boundary rather than as a flag. It is a ref and not a
   * `document.querySelector` for the reason `listRef` is: two of these screens on one page is
   * not a thing today and a global query would be the first thing to break if it ever were. */
  const mapRef = useRef<HTMLDivElement | null>(null)
  /* The key a box-chip jump wants scrolled to the TOP of the scroller, or null for every
   * ordinary selection change. One-shot; the scroll effect consumes it. `block: 'nearest'`
   * is right for a step and wrong for a jump — after two hundred rows it parks the landing
   * at the bottom edge, which shows the END of the box before the one just asked for. */
  const jumpRef = useRef<string | null>(null)

  /* THE JUMP THIS SCREEN HAS BEEN ASKED FOR AND HAS NOT LANDED YET, or null. State rather than
   * a ref because a jump can take two passes — see the landing effect — and the second pass has
   * to be a render this component actually performs.
   *
   * `askedAt` is the last request accepted, so a re-render of the caller holding the same object
   * cannot replay a jump. A ref because it is bookkeeping about requests and not a fact drawn. */
  const [jump, setJump] = useState<string | null>(null)
  const askedAt = useRef<number | null>(null)

  /* THE SEARCH IS THE SERVER'S MATCHER FILTERING THIS SCREEN'S OWN LIST — neither of the
   * two shapes already in the app, and argued against both. Inventory.tsx renders the
   * search RESPONSE, because `GET /search` carries facts `GET /inventory` does not; this
   * screen needs none of them — its rows are already here, labelled and ordered, and what
   * it lacks is only WHICH of them the owner means. So the answer is read for its copy
   * KEYS and nothing else, and the walk keeps its own order and its own rendering. The
   * other obvious shape — a client-side substring over `name` — was declined harder:
   * `do_search` matches six fields (name, number, the zfilled join key, SKU, set hint,
   * note), and the note is the only handle a card the pipeline never identified has. A
   * second, weaker matcher here would make `#/pull` and `#/inventory` answer the same
   * query differently, and nothing anywhere would say so.
   *
   * NO `autoFocus`, WHERE Inventory PASSES IT — a screen's judgement, exactly as
   * SearchField's prop says. That screen is opened to type; this one is opened to WALK,
   * and a field holding focus on arrival is a field eating the arrow keys the header
   * advertises (they guard on `isEditableTarget`). `/` reaches the field from anywhere. */
  const { query, setQuery, results, loading, failure: searchFailure } = useSearch()
  const searching = query.trim() !== ''

  /* Every key the answer names, flattened — membership is the one thing this screen reads
   * off it. Copies of sold and retired cards are in there too, which is right: the walk
   * lists every card in every state, and a search that could not find a sold card would
   * be a search that cannot answer "where was it". */
  const matched = useMemo(() => {
    if (results === null) return null
    const keys = new Set<string>()
    for (const group of results.groups) for (const copy of group.copies) keys.add(copy.key)
    return keys
  }, [results])

  /* Filtered only when there is an answer to filter BY. While the first answer is still
   * owed — debounce, flight — the walk stays whole rather than blanking on every
   * keystroke: Inventory.tsx's rule ("a list that blanks is worse to type against than
   * one that lags by 200ms and says so") applied to a list that exists before the query
   * does; the `Looking.` line is what says so. A FAILED search also leaves the whole walk
   * standing, under the failure panel: an empty list would claim "no card matches", which
   * is an answer, and a failure is precisely not one. */
  const inQuery = useMemo(() => {
    if (rows === null) return NO_ROWS
    if (!searching || matched === null) return rows
    return rows.filter((row) => matched.has(row.key))
  }, [rows, searching, matched])

  /* IS THE WALK BELOW ACTUALLY A SET OF MATCHES? `searching` alone does not answer that and
   * using it as though it did is a real defect rather than a nicety: it goes true on the first
   * keystroke, while the debounce and the request are still out and `inQuery` is still every
   * row in the box. The search-expands-its-matches effect keys on THIS instead, so box 2's 544
   * rows are never thrown open for the length of a debounce and then mostly thrown away again.
   *
   * A FAILED search reads false here, which is the same answer the walk itself gives: the rows
   * stay unfiltered under the failure panel, so there is nothing match-shaped to expand.
   *
   * HOISTED ABOVE `shelves`, which now reads it. */
  const filtered = searching && matched !== null

  /* The shelves the query still reaches, and then the one shelf being walked. TWO STAGES AND
   * NOT ONE, because they answer different questions: the strip has to offer every shelf the
   * query matches (or a match in another box would be invisible with nothing saying so), and
   * the list has to show one shelf's worth (or the header above it would name a box the rows
   * do not all belong to). `visible` stays the name every control below already walks.
   *
   * THE REGISTRY IS UNIONED IN ONLY WHEN NOTHING IS BEING SEARCHED FOR, and that boundary is
   * the whole of the change rather than a caveat on it. The rule this function was written to
   * — a cell may never lead to an empty list — is right about a QUERY and was wrong as a rule
   * about the store: under a query an empty cell is a dead end, so a box holding no match stays
   * out; with no query an empty box's list is empty because the box IS empty, which is not a
   * dead end but the truth, and it is the only state from which that box can be renamed,
   * sealed or deleted. */
  const shelves = useMemo(
    () => shelvesOf(inQuery, filtered ? [] : boxRecords.map((record) => record.box)),
    [inQuery, filtered, boxRecords],
  )

  const visible = useMemo(() => {
    if (shelf === null) return NO_ROWS
    return inQuery.filter((row) => shelfOf(row) === shelf)
  }, [inQuery, shelf])

  const sections = useMemo(() => sectionsOf(visible), [visible])

  /* The box row for the shelf being walked, or null — the header draws `BoxOps` only for a
   * NUMBERED shelf that the registry actually knows. A box a card names but `GET /boxes` has
   * not answered for gets no panel rather than an invented one: the operations it would offer
   * write to a record that is not there. */
  const shelfBox = useMemo(() => {
    if (typeof shelf !== 'number') return null
    return boxRecords.find((record) => record.box === shelf) ?? null
  }, [boxRecords, shelf])

  /* The re-shoot, from a picked file to the server. The base64 the wire wants is the
   * data-URL's payload — sliced at the first comma rather than split, and RAW, no
   * `data:` prefix, exactly as `capture()` documents: the server refuses the prefixed
   * shape loudly rather than letting two spellings spread.
   *
   * A FRESH CAPTURE ID PER PICK, and that is safe HERE in a way it is not on the capture
   * screen. There the id must survive a retry because a replay with a new id burns an
   * index; a re-shoot allocates nothing, so the lost-response worst case is the same
   * bytes written to the same position twice with one extra history line. Holding the id
   * across a retry would buy machinery, not safety.
   *
   * On success: remember the id as this card's cache nonce, then re-read the inventory —
   * the record's `photo` and `capture_id` changed server-side, the loader keeps the
   * selection, and it also resets `photoAbsent`, which is how a card whose photo file
   * was LOST comes back to life when a re-shoot gives the route bytes to serve again. */
  const beginReshoot = (row: Row, file: File) => {
    setReshootBusy(row.key)
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      const imageBase64 = url.slice(url.indexOf(',') + 1)
      const captureId = newCaptureId()
      reshootPhoto(row.card.box, row.card.index, imageBase64, captureId)
        .then(() => {
          setReshot((held) => ({ ...held, [row.key]: captureId }))
          setReshootBusy(null)
          setReshootFailure(null)
          setReloads((n) => n + 1)
        })
        .catch((err: unknown) => {
          setReshootBusy(null)
          /* Verbatim, owner screen: `card_sold` and `card_retired` should be unreachable
           * (the control is not drawn for either state), but a second device can move a
           * card between this screen's read and the press, and the server's message
           * names the way back better than anything composed here could. */
          setReshootFailure({ key: row.key, failure: describeFailure(err) })
        })
    }
    reader.onerror = () => {
      setReshootBusy(null)
      setReshootFailure({
        key: row.key,
        failure: describeFailure(reader.error ?? new Error('the picked file could not be read')),
      })
    }
    reader.readAsDataURL(file)
  }

  useEffect(() => {
    // StrictMode runs effects twice in dev, and a slow first response can land after the
    // second one. The flag makes the late arrival a no-op rather than a flicker.
    let live = true
    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`. The two-argument form does not cover
     * its own success handler, so anything thrown while walking the answer — `rowsOf` over a
     * body with no `cards`, which is what an older or wrong server returns — becomes an
     * unhandled rejection: no failure panel, no Reload to press, and the screen stuck on
     * "Reading the inventory." Fulfillment.tsx watched exactly that happen for a morning and
     * fixed itself; this file kept the shape for another ten days, which is the argument for
     * the eslint rule in `app/eslint.config.js` rather than for a fourth copy of this comment.
     * With `.catch` a body this screen cannot read fails the same way a dead server does. */
    getInventory()
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        setFailure(null)
        setPhotoAbsent(null)
        /* Keep the selection across a reload when the card is still there. An undo on the
         * capture screen deletes the newest card outright — D10, no tombstone — so a key
         * held blindly would render an empty panel that reads as a bug rather than as the
         * deletion it is. */
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (next[0]?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
    /* `reloadToken` beside `reloads`: the screen above writes cards this walk draws — a sale,
     * a retirement, their reversals — and it holds no copy of the inventory to patch, so the
     * only honest refresh is the one the Reload already does. */
  }, [reloads, reloadToken])

  /* THE BOX REGISTRY, on the same counter as the inventory read and allowed to fail without
   * anybody hearing about it — `Inventory.tsx` argues the shape at length for its own layout
   * read and every word of it holds here. The walk, the strip, the rows and the photograph all
   * come off `GET /inventory`; this read only decides whether the box header can be drawn. A
   * failure panel would trade a working walk for a message about a panel.
   *
   * ON `reloads` RATHER THAN ON THE SHELF, because a box edit is what changes these rows and
   * `BoxOps` bumps that counter when it makes one. It must: D10 as amended makes Section and
   * Card a VIEW of an index, so a divider edit changes every card decoration in the box as
   * well as the box row — which is why the inventory read is on the same counter and why they
   * are refreshed together rather than separately.
   *
   * `.then(ok).catch(fail)` AND NOT `.then(ok, fail)` — the rule `app/eslint.config.js`
   * enforces. It binds here even though the failure path does nothing: the success handler
   * walks a body off the wire, and the two-argument form would turn a throw in it into an
   * unhandled rejection rather than the silence this effect intends. */
  useEffect(() => {
    let live = true
    getBoxes()
      .then((summary) => {
        if (!live) return
        const records = Array.isArray(summary.boxes) ? summary.boxes : []
        setBoxRecords(records)
        /* Handed up in the same breath rather than read again by the caller. `Inventory.tsx`
         * needs these layouts for the position bars on the copy rows and it used to fetch this
         * route for itself — two reads of one registry on one screen, which was harmless and
         * was also two places for the same answer to arrive at different times. */
        onBoxes?.(records)
      })
      .catch(() => {
        // Deliberately nothing. See above: the walk is whole without this.
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken, onBoxes])

  useEffect(() => {
    let live = true
    getQueues()
      .then((snapshot) => {
        if (live) setQueued(snapshot)
      })
      .catch(() => {
        // Deliberately nothing — see the `queued` declaration. The panel is whole without it.
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken])

  /* A RELOAD DROPS EVERY CACHED TABLE, and it is declared BEFORE the read below so that the
   * clear and the re-read happen in one pass rather than leaving the panel a render showing
   * yesterday's price. The button beside the walk is pressed after a join precisely because
   * something downstream has changed, and a price is one of the things a join rewrites. */
  useEffect(() => {
    asked.current = new Set()
    setPriced({})
  }, [reloads, reloadToken])

  /* THE SHELF FOLLOWS THE FILTER, which is the selection rule one level up and it exists for
   * the same failure: a query matching only box 95 while box 1 is selected would draw an empty
   * list under a header naming a box that does have cards, and nothing on screen would say the
   * match was somewhere else. So an unreachable shelf falls to the first one the query does
   * reach. When NOTHING matches, the shelf is deliberately left alone — clearing the query
   * then puts the owner back exactly where they were, and one over-narrow keystroke does not
   * cost them their place. */
  useEffect(() => {
    if (shelves.length === 0) return
    setShelf((prev) =>
      prev !== null && shelves.includes(prev) ? prev : (shelves[0] ?? null),
    )
  }, [shelves])

  /* THE SELECTION FOLLOWS THE FILTER. A query that drops the selected card would otherwise
   * leave the detail panel showing a card the list no longer contains — a photo beside a
   * walk that cannot reach it. First match rather than nothing, because the filtered list
   * is an answer and its first row is the walk's own order speaking. When NOTHING matches,
   * the selection is deliberately left alone: the detail hides on its own (it renders off
   * `visible`), and clearing the query then restores exactly the card that was open —
   * nulling it would make one over-narrow keystroke cost the owner their place. */
  useEffect(() => {
    if (visible.length === 0) return
    setSelected((prev) =>
      prev !== null && visible.some((row) => row.key === prev) ? prev : (visible[0]?.key ?? null),
    )
  }, [visible])

  /* The ticks are the box's, so they go when the box does — the ruling at `picked`. It fires on
   * the first render too, when the shelf moves from null to the first box, which costs a
   * set-state over an already-empty list and buys the rule having exactly one statement. */
  useEffect(() => {
    setPicked([])
  }, [shelf])

  /* THE ARROW KEYS, armed on the window rather than on the list itself, so the owner does not
   * have to click a row before the keyboard does anything — a fast nav that needs a mouse
   * click to arm it is not one. `trigger.ts` and ReviewQueue.tsx both bind this way and both
   * arm it from an effect that exists only while their screen is mounted; this is that shape
   * a third time, teardown included, which is the half of it that keeps a second mount from
   * leaving two listeners walking the list two cards at a time. The deep keys are the
   * opposite ruling — list-scoped, a React handler on the element itself — and the split
   * is argued at SECTION_KEYS above.
   *
   * `selected` is deliberately NOT a dependency. The move is a functional update, so the
   * handler closes over `visible` alone and is registered once per change of the walk
   * instead of once per keystroke — at auto-repeat pace the second shape churns a window
   * listener thirty times a second, and the stale closure it would otherwise need is a real
   * bug rather than a style question. `visible` and not `rows`, which is how the arrows
   * compose with the search: a held Right walks the MATCHES, in walk order, and never steps
   * onto a card the filter removed.
   */
  useEffect(() => {
    /* The queue's arrows must survive a query matching nothing: an empty walk is not an empty
     * queue, and the order still wants stepping to its next stop. */
    if (visible.length === 0 && arrows === null) return

    const onKeyDown = (event: KeyboardEvent) => {
      /* Modifiers belong to the browser and the OS: Cmd-Left is Back and Alt-Left is a word
       * jump, and neither should quietly become a card. Shift is left out of that list for
       * the reason trigger.ts gives — it does not change which key was pressed — and a held
       * Shift silently killing the nav would be the worse of the two failures. */
      if (event.metaKey || event.ctrlKey || event.altKey) return

      const step = STEPS.find((candidate) => candidate.key === event.key)
      if (step === undefined) return
      if (isTyping(event.target)) return

      /* AUTO-REPEAT IS THE FEATURE HERE, which is why there is no `event.repeat` guard and
       * why its absence is written down rather than left looking like an omission. trigger.ts
       * refuses a repeat because a held key there is a stack of captures of one card sitting
       * in the lens; ReviewQueue.tsx refuses one because a held key there is a run of answers,
       * and every answer is a write. Here the action is a selection change on a screen that
       * writes nothing: holding Right walks the box, letting go stops it, and nothing has been
       * spent that has to be walked back.
       *
       * What it does cost is a photo request per card as the panel keeps up. The browser
       * abandons the ones it does not finish, and a debounce was declined: it would leave the
       * photo showing one card while the highlight and the position label showed another,
       * which is precisely the disagreement this screen exists to rule out.
       */

      /* Prevented before the move rather than after it, because a refusal at the end of the
       * list is still this handler answering for the key. The alternative lets a held Right
       * start scrolling the page sideways the moment it runs out of cards, which reads as the
       * list having thrown you somewhere. Every press that reached one of the returns above
       * keeps its normal behaviour, which is the whole reason this line sits here and not at
       * the top. */
      event.preventDefault()

      /* AN ORDER IS DRIVING: the key steps the queue and the caller lands the walk through
       * `goTo`. Every guard above still applies — the arrows are the same arrows. */
      if (arrows !== null) {
        arrows.onStep(step.delta)
        return
      }

      setSelected((prev) => {
        const at = visible.findIndex((row) => row.key === prev)

        /* Not in this list at all — hard to reach, since the loader plants the selection on
         * the first row and only drops it when there is nothing to select. Step in from the
         * end you are stepping from, so a first press does something rather than nothing. */
        if (at === -1) {
          const landing = step.delta === 1 ? visible[0] : visible[visible.length - 1]
          return landing?.key ?? prev
        }

        /* BOTH ENDS STOP, and the missing index is what stops them: one past either end,
         * `rows[...]` is undefined under noUncheckedIndexedAccess and the selection is left
         * exactly where it was. Wrapping was the alternative and it is the wrong one —
         * arriving back at card 1 after the last card of a two-hundred-card box loses your
         * place without saying so, and the list is then lying about where its end is. A list
         * that stops is telling the truth. */
        return visible[at + step.delta]?.key ?? prev
      })
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visible, arrows])

  /* Keep the selected row where it can be seen. The failure this prevents is specific, and it
   * is the one that makes a keyboard list feel broken: the detail panel updates, the marked
   * row is three screens up inside its own scroller, and the only thing that visibly moved is
   * on the other side of the page.
   *
   * `'nearest'` so it scrolls only when it has to, which is what keeps it from fighting the
   * mouse — a click on a row that was already visible moves nothing. A box-chip jump is the
   * argued exception and lands `'start'`, once, via jumpRef above: a jump is FOR seeing what
   * follows the landing, and 'nearest' shows what precedes it. The rows' scroll-margin in the
   * stylesheet is what keeps 'start' from parking the row under its own sticky section header.
   *
   * `scrollWithin` RATHER THAN `scrollIntoView`, AND THE BOUNDARY IS THE POINT. That API
   * scrolls the document too, which on a sticky column moves the page without moving the row —
   * the owner's hidden-top-bars report. The helper's own header carries the measurement.
   *
   * READ OFF `aria-current` rather than off a ref per row. That attribute is already this
   * screen's answer to "which row is current", so the row that scrolls is by construction the
   * row that is marked; a parallel map of refs is a second answer to the same question, and
   * the day the two disagree nothing says so. (The box cells carry the attribute too, but
   * they live outside `listRef`, so the query cannot land on one.) `visible` in the
   * dependencies for the handler's own reason: when the filter redraws the list around an
   * unchanged selection, the marked row should still be the one on screen. */
  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) {
      scrollWithin(current, mapRef.current, jumpRef.current === selected ? 'start' : 'nearest')
    }
    jumpRef.current = null
  }, [selected, visible])

  /* The deep keys. A React handler on the list rather than a window listener — focus
   * within the list IS the scoping the ruling at SECTION_KEYS asks for, there is nothing
   * to tear down, and a fresh closure per render means no dependency bookkeeping. The
   * guards are the window handler's, in the same order and for the same reasons. */
  const onListKeys = (event: ReactKeyboardEvent<HTMLUListElement>) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isTyping(event.target)) return

    /* Tick the current card. Before the movement keys because it is the only one of them that
       is a letter, and lower-cased so a held Shift does not make it stop working — the same
       reasoning `trigger.ts` gives for leaving Shift out of the modifier guard. */
    if (event.key.toLowerCase() === TICK_KEY.key) {
      event.preventDefault()
      if (selected !== null) toggleTick(selected)
      return
    }

    const edge = EDGE_KEYS.find((candidate) => candidate.key === event.key)
    const jump = SECTION_KEYS.find((candidate) => candidate.key === event.key)
    if (edge === undefined && jump === undefined) return

    /* Prevented even when the move refuses, exactly as the arrows argue: a refusal at the
     * end is still this handler answering for the key, and the default here — the scroller
     * paging the ROWS out from under an unmoved selection — is precisely the disagreement
     * between the mark and the viewport this screen exists to rule out. */
    event.preventDefault()

    if (edge !== undefined) {
      const landing = edge.last ? visible[visible.length - 1] : visible[0]
      if (landing !== undefined) setSelected(landing.key)
      return
    }
    if (jump === undefined) return

    setSelected((prev) => {
      const at = sections.findIndex((section) => section.rows.some((row) => row.key === prev))

      /* Not in any section — the same hard-to-reach case the arrows handle, answered the
       * same way: step in from the end being stepped from. */
      if (at === -1) return sections[0]?.first.key ?? prev

      if (jump.delta === 1) return sections[at + 1]?.first.key ?? prev

      /* Backwards: the nearest boundary first — this section's own start from its middle,
       * the previous section's from its start. Both ends stop, by the arrows' own
       * mechanism: one past either end is undefined under noUncheckedIndexedAccess and the
       * selection stays put. */
      const own = sections[at]
      if (own !== undefined && own.first.key !== prev) return own.first.key
      return sections[at - 1]?.first.key ?? prev
    })
  }

  /* A CELL PRESS CHANGES WHAT THE WALK IS OF, and then does the two things a click on a row
   * does not. It scrolls the landing to the top of the scroller — via jumpRef, argued at the
   * scroll effect — and it hands focus to the list, arming the deep keys: the gesture after
   * "show me box 7" is walking box 7, and a selection that left the keys dead until a click
   * would give back the mouse it just saved.
   *
   * The landing is computed off `inQuery` rather than `visible` for a reason that is easy to
   * get wrong: `visible` is the shelf you are LEAVING at the moment this runs, so it holds no
   * row of the shelf being asked for. `inQuery` is every row the current query reaches, on any
   * shelf, which is where the landing has to come from. */
  const selectShelf = (next: Shelf) => {
    setShelf(next)
    const landing = inQuery.find((row) => shelfOf(row) === next)
    if (landing !== undefined) {
      jumpRef.current = landing.key
      setSelected(landing.key)
    }
    listRef.current?.focus(FOCUS)
  }

  /* Off `visible`, not off `rows`: a selection the filter removed renders NO detail rather
   * than a card the list cannot reach — and comes back whole when the query clears.
   *
   * MEMOISED BECAUSE IT IS REPORTED UPWARDS. A fresh `.find` per render is a fresh object
   * identity per render, and the effect that hands this to `onSelect` would then fire on every
   * render — setting state in the parent, re-rendering this component, and firing again. The
   * memo is what makes that effect fire when the SELECTION changes rather than when React
   * happens to run. */
  const selectedRow = useMemo(
    () => visible.find((row) => row.key === selected) ?? null,
    [visible, selected],
  )

  /* WHAT A BULK WRITE WOULD REACH: the ticked rows that are in the box being walked, as the
   * indices `PUT /inventory/<box>` takes. Off `rows` and not off `visible`, deliberately — a
   * tick survives a search that hides its row, because a tick is about a card and a filter is
   * about the view, and the status line states the total so nothing is hidden. Narrowed to the
   * shelf because the route is per-box; a non-numeric shelf (pooled, unplaced) has no box to
   * write to and yields nothing. */
  const pickedIndices = useMemo(() => {
    if (rows === null || typeof shelf !== 'number') return []
    return rows
      .filter(
        (row) =>
          picked.includes(row.key) &&
          row.card.box === shelf &&
          typeof row.card.index === 'number' &&
          Number.isFinite(row.card.index),
      )
      .map((row) => row.card.index)
  }, [rows, picked, shelf])

  /* A SECTION IS OPEN WHEN IT IS IN THE OPEN SET. Nothing else. The invariant that no control
   * can put the mark on a row nobody can see is kept by the effect below, which OPENS the
   * landing section when the selection moves — at navigation time, not at render time.
   *
   * IT USED TO READ `opened.includes(key) || selection is inside it`, and that second clause
   * made an explicit fold of the section you are standing in do NOTHING: the click recorded
   * the close, the render overrode it, and the operator saw a control that moves nothing. The
   * owner reported it exactly that way — clickable, does not work — alongside an eleven-pixel
   * dead zone above it (BoxBrowse.css), and the two together are why it felt broken rather
   * than merely stubborn.
   *
   * The distinction is D19's, about arming: an explicit act and an automatic consequence are
   * not the same thing and must not be decided in the same expression. Navigation opens what
   * it lands in — that is the automatic half, and it still holds. Folding is an act, and an
   * act wins. */
  const isOpen = (section: Section) => opened.includes(section.key)

  /* THE ONE FOLD CONTROL READS *ANY* RATHER THAN *EVERY*, AND THAT IS THE SECOND HALF OF THE
   * CLICK-TWICE FIX. It used to say `collapse all` only when every section was open, so from
   * any PARTIAL state — one section opened by a step, one folded by hand — it offered to
   * expand, and reaching a collapsed list took two presses. That is the owner's report in one
   * sentence: "you gotta click it once or twice for it to be working right".
   *
   * With `any`, one press always produces the state the label names: nothing open offers
   * `expand all` and opens everything; anything open offers `collapse all` and shuts
   * everything. There is no state from which the control needs a warm-up press.
   *
   * WHICH DIRECTION A PARTIAL STATE OFFERS IS THE REAL CHOICE HERE, and collapse wins because
   * collapsed is this walk's resting state: the fold exists to turn box 2's 544 rows into 22
   * readable lines, so the way BACK to the table of contents is the gesture that has to be one
   * press from anywhere. Expanding 544 rows is the deliberate, rarer act and can afford the
   * second press. */
  const anyExpanded = sections.some((section) => opened.includes(section.key))

  const toggleAllSections = () =>
    setOpened(anyExpanded ? [] : sections.map((section) => section.key))

  const toggleSection = (section: Section) =>
    setOpened((held) =>
      held.includes(section.key)
        ? held.filter((key) => key !== section.key)
        : [...held, section.key],
    )

  const toggleTick = (key: string) =>
    setPicked((held) => (held.includes(key) ? held.filter((k) => k !== key) : [...held, key]))

  const tickSection = (section: Section, on: boolean) =>
    setPicked((held) => {
      const keys = section.rows.map((row) => row.key)
      const rest = held.filter((key) => !keys.includes(key))
      return on ? [...rest, ...keys] : rest
    })

  const shownAllTicked = visible.length > 0 && visible.every((row) => picked.includes(row.key))

  const tickAllShown = () =>
    setPicked((held) => {
      const keys = visible.map((row) => row.key)
      const rest = held.filter((key) => !keys.includes(key))
      return shownAllTicked ? rest : [...rest, ...keys]
    })

  /* THE INVARIANT THE RENDER-TIME OVERRIDE USED TO CARRY, moved to where it belongs. Every key
   * that moves the selection — arrows, PgUp/PgDn, Home/End, a box cell, a search landing —
   * ends here, so the section the mark lands in is opened as a CONSEQUENCE of the move rather
   * than as a condition of drawing. The mark can never sit on a row nobody can see, and a fold
   * the operator asked for is not undone on the next render.
   *
   * Adds only, and only when the section is shut, so it cannot fight a fold of some OTHER
   * section and cannot loop: a selection that does not move re-runs this to no effect.
   *
   * A MOVE IS A STEP FROM ONE CARD TO ANOTHER, AND THE LOADER'S OWN FIRST PICK IS NOT ONE.
   * Added 2026-08-23, and it is the whole of the click-twice bug the owner reported. This
   * effect fired for the AUTOMATIC selection every read plants on the first row (see the
   * loader, and the two follows-the-filter effects), so a freshly opened box arrived with one
   * section already open while the control beside it offered to `expand all` — the first press
   * expanded, and only the second reached the collapsed list the press was for. Measured on box
   * 1: load 25 rows, press 53, press 0.
   *
   * `cameFrom` is the previous selection and the test is `both are cards and they differ`. A
   * transition OUT OF null is by construction automatic — nothing on this screen navigates from
   * nothing, only the loader and the filter plant a selection where there was none — so
   * ignoring it is exactly the rule "the operator moved" written in the one term the component
   * actually holds. A ref rather than state because it is bookkeeping about renders and not a
   * fact the screen draws; storing it in state would re-render to record that nothing happened.
   *
   * It also buys a second thing worth having: a re-read (Reload, a write upstream, a box edit)
   * rebuilds `sections` with the selection unchanged, and this now leaves the folds exactly as
   * the operator left them instead of re-opening one. */
  const cameFrom = useRef<string | null>(null)
  useEffect(() => {
    const previous = cameFrom.current
    cameFrom.current = selected
    /* THE `previous === null` GUARD WAS REMOVED ON 2026-08-24 AND PUT BACK THE SAME HOUR.
     * Worth recording, because the argument for removing it is good and still wrong.
     *
     * A UI review made this its highest-leverage finding: the guard is what makes the spine
     * open showing ZERO card rows — N section headers in the quietest type in the product,
     * no `aria-current` for the scroll effect to find, no "you are here" on the map — and it
     * argued the click-twice bug had two independent causes with only one fix needed, since
     * `anyExpanded` reads `some` rather than `every` and therefore already reaches a
     * collapsed list in one press from any partial state.
     *
     * That reasoning is sound and it is not the whole test. D31 rules "collapsed is the
     * resting state" and "nothing opens on load, on a reload, or on an upstream write", and
     * `app/tests/inventory.spec.ts` encodes it by name — "the walk arrives fully collapsed,
     * the planted selection included". Removing the guard turned ten of that file's twenty-one
     * assertions red, eight of them by timing out on rows that should not have been there.
     *
     * So this is a decision to reopen with the owner, not a defect to fix in a stylesheet —
     * CLAUDE.md: name the entry, say why, and wait. The finding is real and is recorded in
     * docs/specs/ui-redesign-options.md; the guard stays until D31 is amended. */
    if (previous === null || selected === null || selected === previous) return
    const holding = sections.find((section) => section.rows.some((row) => row.key === selected))
    if (holding === undefined) return
    setOpened((held) => (held.includes(holding.key) ? held : [...held, holding.key]))
  }, [selected, sections])

  /* A SEARCH OPENS EVERY SECTION IT MATCHES INTO. The owner's ask, verbatim: "i want if i
   * search for a card, all results of that card in whatever/all section/box are expanded
   * (immediately findable)". Under a query `visible` is already only the matches, so every
   * section the walk still draws holds one — the effect is "open all of them", and it stays
   * true across boxes because pressing another cell on the strip rebuilds `sections` for that
   * box and re-runs this. The strip itself already offers only boxes a match survives in.
   *
   * AN EFFECT AND NOT A CLAUSE IN `isOpen`, which is the same ruling the nav effect above
   * carries and for the same reason: a `searching || …` override would make a fold under a
   * query record a close that the next paint discarded, which is the exact defect the owner
   * reported as clickable-and-not-working. Here the expansion is a write like any other, so a
   * section folded during a search stays folded — `opened` changes, `sections` does not, and
   * this effect does not re-run. */
  useEffect(() => {
    if (!filtered) return
    setOpened((held) => {
      const shut = sections.filter((section) => !held.includes(section.key))
      return shut.length === 0 ? held : [...held, ...shut.map((section) => section.key)]
    })
  }, [filtered, sections])

  /* AND GIVES IT ALL BACK WHEN THE QUERY GOES. Clearing the field returns the walk to the state
   * it opens in — fully collapsed — rather than leaving the shape a search built standing over
   * a list that is no longer an answer to anything. The expansion above was never asked for by
   * a hand on a fold; it belonged to the query, and it goes when the query does.
   *
   * The property that makes this the right default rather than merely a tidy one: a cleared
   * search and an arrival now render identically, so there is one resting state to learn and
   * not two. The mark can sit inside a shut section afterwards, exactly as it does on arrival —
   * the detail column, the photograph and the copies are all still drawn for it, and the first
   * arrow key opens its section by the effect above.
   *
   * DECLINED: snapshotting the folds standing when the query arrived and restoring them. It is
   * nicer in the one case where the operator had expanded something on purpose before typing,
   * and it costs a second remembered fold state that nothing on screen names — so what the
   * screen does after a clear would depend on a thing the operator cannot see. Collapsing is
   * predictable from the label in front of them.
   *
   * `filtered` ALONE IN THE DEPS, deliberately: `sections` changes on every re-read, box switch
   * and box edit, and a collapse keyed on that would throw away folds whenever anything
   * upstream wrote. This fires on the edge out of a search and nowhere else. */
  useEffect(() => {
    if (filtered) return
    setOpened((held) => (held.length === 0 ? held : []))
  }, [filtered])

  /* A JUMP IS ACCEPTED HERE AND LANDED BELOW, in two effects rather than one, because accepting
   * is about the REQUEST — has this `at` been answered — and landing is about the WALK, which
   * may not be able to take it on the pass the request arrives. */
  useEffect(() => {
    if (goTo === undefined || goTo === null) return
    if (askedAt.current === goTo.at) return
    askedAt.current = goTo.at
    setJump(goTo.key)
  }, [goTo])

  /* WALK TO THE CARD SOMETHING OUTSIDE ASKED FOR — the box, the fold, the mark and the scroll,
   * in one batch, so no intermediate state exists for another effect to correct.
   *
   * DECLARED AFTER THE TWO FOLD EFFECTS ABOVE AND THAT IS LOAD-BEARING. Effects run in
   * declaration order within a commit, and the pass that clears a query is the same pass the
   * collapse-on-clear effect fires in. Opening the landing's section first would have that
   * effect shut it again, and it would not re-run afterwards — its only dependency is
   * `filtered`. Last means the open is the final word.
   *
   * THE FILTER IS THE FAILURE THIS EXISTS TO PREVENT, and it is silent in the worst way. Under a
   * query the walk holds only matches, and the two follows-the-filter effects above move the
   * mark to `visible[0]` whenever the selection is not among them — so a jump to a card the
   * query does not reach would land on WHATEVER CARD IS FIRST, drawn under its own photograph,
   * with nothing on screen saying the wrong one was reached. Not hypothetical: `do_search`
   * builds a SKU's group WHOLE, so a copy of a matched SKU is always reachable, but the
   * `sku: null` group is the matched cards THEMSELVES — and a named, never-emitted card is most
   * of this store. Two copies of one name in two boxes, a query that reached only one of them,
   * and the other is a copy row that cannot be walked to.
   *
   * SO THE QUERY IS DROPPED RATHER THAN THE JUMP. The owner pressed a position; the filter was
   * a way of finding it, and it has been found. Clearing re-runs this effect with the whole walk
   * to land in — the pending `jump` is what carries the request across that second pass.
   *
   * A KEY THE WALK DOES NOT HOLD IS DROPPED, with nothing drawn. It means these rows and this
   * list disagree about the store: the copies come from `GET /search` on every selection and
   * the walk from `GET /inventory` at mount, so a card deleted from another device sits in one
   * and not the other until a Reload. Naming it would need a refusal channel out of a component
   * that reports three things upward and takes one back; the honest cheap answer is that the
   * press does nothing and the Reload beside the list is the remedy. */
  useEffect(() => {
    if (jump === null) return
    if (rows === null) return
    const row = rows.find((candidate) => candidate.key === jump)
    if (row === undefined) {
      setJump(null)
      return
    }
    if (!inQuery.some((candidate) => candidate.key === jump)) {
      /* Still filtered out with no query to clear — nothing else can widen the walk, so the
         request is dropped rather than left pending forever. Unreachable today: `inQuery` IS
         `rows` when nothing is being searched for, and the row was just found in `rows`. */
      if (!searching) setJump(null)
      else setQuery('')
      return
    }
    const landing = shelfOf(row)
    /* The landing's own sections, computed for the shelf being GONE TO rather than read off
       `sections` — that memo describes the shelf being left, and on a cross-box jump it holds
       no row of the box asked for. Opening it here rather than leaving it to the
       mark-is-never-hidden effect is what lets the scroll below find a rendered row: that
       effect runs a commit later, and the scroll's dependencies do not include the folds. */
    const holding = sectionsOf(inQuery.filter((candidate) => shelfOf(candidate) === landing)).find(
      (section) => section.rows.some((candidate) => candidate.key === jump),
    )
    if (holding !== undefined) {
      setOpened((held) => (held.includes(holding.key) ? held : [...held, holding.key]))
    }
    setShelf(landing)
    /* `block: 'start'` for the same reason a box-chip press takes it — see the scroll effect.
       A jump is for seeing what surrounds the landing, and 'nearest' after two hundred rows
       parks it against the bottom edge. */
    jumpRef.current = jump
    setSelected(jump)
    /* The keys, armed. The gesture after "take me to that copy" is walking from it, exactly as
       `selectShelf` argues.

       THIS COMMENT USED TO END "and the page scroll this brings with it is wanted here: the
       copies list is below the card band, and the photograph is what was asked for". The
       intention was right and what happened was the opposite: the scroll came from
       `scrollIntoView` on the landed ROW, so it moved the page DOWN — away from the card band —
       and on a sticky column it moved the page without moving the row at all. The owner
       reported it as the top bars disappearing. `scrollWithin` is the fix and `FOCUS` is what
       stops this line becoming the same defect by another door. */
    listRef.current?.focus(FOCUS)
    setJump(null)
  }, [jump, rows, inQuery, searching, setQuery])

  /* THE SELECTION, REPORTED UPWARDS. `Inventory.tsx` draws the copies of whatever card the walk
   * is pointing at, and it cannot know which one that is without being told. The memo above is
   * what keeps this from looping: a stable identity means this fires on a real change and not
   * on every render. */
  useEffect(() => {
    onSelect?.(selectedRow)
  }, [selectedRow, onSelect])

  /* THE SELECTED CARD'S RUN, READ ONCE AND THEN NOT AGAIN. The dependency is the run NAME and
   * not the row, so stepping through a box of one run fires this exactly once — and the guard is
   * `asked` rather than `priced` for the reason given at that ref.
   *
   * THE RELOAD COUNTERS ARE IN THE DEPENDENCIES AND LEAVING THEM OUT WAS A LIVE BUG, caught by
   * pressing Reload against the real store. The effect above empties the cache; this one was
   * keyed on the run NAME alone, which does not change when a box is re-read — so the cleared
   * entry was never re-fetched and the row sat on `reading…` permanently. A clear and its
   * re-read are one gesture and must be triggered by the same thing. Declared AFTER that effect
   * so the order within the commit is empty-then-ask rather than the reverse. */
  const pricedRun = selectedRow?.card.run ?? null
  useEffect(() => {
    if (pricedRun === null) return
    if (asked.current.has(pricedRun)) return
    asked.current.add(pricedRun)
    let live = true
    getPricing(pricedRun)
      .then((payload) => {
        if (live) setPriced((held) => ({ ...held, [pricedRun]: marketTable(payload) }))
      })
      .catch((error: unknown) => {
        /* THE REFUSAL IS KEPT AND SHOWN, and `pricing_not_written` is the one worth telling
           apart: it means this run predates `pricing.json` or has not been joined at all, and
           the remedy is a join rather than a look at the server. Every other failure — a run
           directory that has gone, a server that is down — is one sentence, because the row has
           one line and the console has the rest.

           THE REMEDY IS WHAT SURVIVED THE CUT. `no pricing table — join this run` is 291.2px in
           a 181px track, so it drew as two lines, and only one of its halves fits. The state is
           the half to drop: `MARKET: join this run` already says a table is what is missing, and
           the sentence this is being told apart FROM — `could not be read` — names no remedy at
           all, so the pair still reads as two different failures. */
        const why =
          describeFailure(error).code === 'pricing_not_written'
            ? 'join this run'
            : 'could not be read'
        if (live) setPriced((held) => ({ ...held, [pricedRun]: { kind: 'absent', why } }))
      })
    return () => {
      live = false
    }
  }, [pricedRun, reloads, reloadToken])

  /* THE SCOPE, REPORTED UPWARDS, on the same terms and for the same reason. `pickedIndices` is
   * already memoised on exactly the three things that can move it, so this fires on a real
   * change to the selection or the shelf and not on every render — the identical guard the
   * effect above relies on. */
  useEffect(() => {
    onScope?.({ box: typeof shelf === 'number' ? shelf : null, indices: pickedIndices })
  }, [shelf, pickedIndices, onScope])

  /* Read once for the selected card and passed down, rather than read again inside
   * PhotoPanel. Two reads of the same field cannot disagree today, but they are two places
   * to edit the day the field is renamed, and the failure mode of getting that half-right
   * is a photo captioned with a position beside a panel saying there is none. */
  const selectedLabel = selectedRow === null ? null : positionLabel(selectedRow.card)

  /* Read once beside the label it sits under, for the label's own reason: one read, one
   * value, and no way for the sentence's presence test and its rendering to disagree. */

  return (
    <section className="browse">
      {/* ONE HEADER ROW FOR THE WHOLE SCREEN, and the page title is a slot in it (D31's merge,
          tightened 2026-08-23). Measured before the change at 1440x900: the title block, its
          lede, the two-mode switch and this controls row cost 240px — 27% of the viewport —
          before the first card row, which sat at y=475. The switch is gone because there are no
          modes any more; the lede is gone because a screen made of a box strip, a walk and a
          photograph explains itself to the one person who uses it; and the title moved into
          this row rather than sitting on its own line above it. `head` is that slot: this
          component draws the walk and does not own a page title, so the screen above hands one
          down. */}
      <div className="browse-controls">
        {head}
        {/* A reload is a GET. The ban in §7 is on acting — writing a state, marking a
            sale, pulling a card — and re-reading the inventory is none of those. It
            earns its place because Gate B alternates between capturing on one screen and
            checking here, and the alternative is teaching the operator to reload the
            browser, which also throws away the selection. No accent fill: docs/DESIGN.md
            reserves the solid fill for a screen with exactly one thing to do, and this
            screen's one thing is to be looked at. */}
        <button className="browse-reload" type="button" onClick={() => setReloads((n) => n + 1)}>
          Reload
        </button>
        {rows === null ? null : (
          /* IT SAYS WHAT IT COUNTS. `rows.length` is a STORE-WIDE total — it never narrows by
             box and never narrows by search — and it was drawn as a bare `543 cards`,
             byte-identical to `.boxops-meta`'s `cards 543` two hundred pixels below it, which
             counts one box. They agreed only because every other box happened to be empty. */
          <span className="browse-count">
            {rows.length} {rows.length === 1 ? 'card' : 'cards'} in the store
          </span>
        )}
        {/* "Every choice shows its key" — docs/DESIGN.md, owner-side, where an hour spent
            checking a run against the boxes on the desk is a keyboard and not a mouse. A
            hotkey nobody can see is a hotkey nobody uses, and this screen had no chrome to
            discover it from at all.

            In the header rather than pinned to the list, because that is where the binding
            actually is: the keys are on the window and work wherever you are on this screen,
            so a chip attached to the list would claim a smaller thing than the truth. The
            deep keys are the same rule pointing the other way — bound on the list, so their
            chips sit under it.

            Drawn only with two cards to step between. A hint offering to move you through a
            list of one is chrome that has stopped being true, and the empty and failed
            states have no list under it at all. */}
        {/* THE RUN LINE, BETWEEN THE STORE COUNT AND THE KEY HINT (2026-08-29). `docs/DESIGN.md`
            authorises exactly this: "the page title ... shares a line with the screen's controls
            and counts", and a box's run state plus a link to `#/runs` is a count and a control.
            It was the one item on this screen missing that file's OWN first-content floor — "the
            first row of real content sits within 150px of the top of the viewport" — by
            1014-1422px.

            IT CANNOT BECOME TWO ROWS HERE, which is D39's standing rule about this component, and
            in a shared header line that stops being a promise in a comment and becomes structural.
            Measured with the real faces: the widest realistic pair is 487px against 905px of empty
            header, so it fits at 1440 with 418px spare and at 1280 with 246px.

            REJECTED: the left column, where D38's "the left column IS the box" would point. Its
            track is 285-360px and the content box is ~334px at the wide end; the ordinary ticked
            state measures 428px, so it would wrap to two lines the moment anything is ticked —
            the one thing D39 forbids. That is a measurement, not a preference. */}
        {boxPanel}
        {/* THE CHIP SAYS WHAT THE ARROWS DO, and while an order drives that is not the box.
            `arrows.says` may be null — a queue of one stop has nothing to step between, which is
            the same rule the plain walk applies to a list of one: a hint offering to move you
            through a list of one is chrome that has stopped being true. */}
        {(arrows ? arrows.says : rows === null || rows.length < 2 ? null : 'step one card') === null ? null : (
          /* THE WORDS FIRST, THEN THE CHIPS, and the span itself is pushed to the far edge of
             the row by `margin-left: auto`. Chips-then-words put two bordered arrow keys
             twelve pixels from a real bordered button, which is the prev/next affordance
             itself — see `.browse-keys` for the argument. Reading `step one card ← →` also
             puts the sentence where a sentence goes and the keys where the eye already
             expects a pager. */
          <span className="browse-keys">
            {arrows ? arrows.says : 'step one card'}
            {STEPS.map((step) => (
              <kbd className="browse-key" key={step.key}>
                {step.label}
              </kbd>
            ))}
          </span>
        )}
      </div>

      {/* THE BANNER SLOT — the order driving the walk, when one is. Between the header row
          and the body so it is about neither the card nor the box; see the prop. */}
      {banner === undefined || banner === null ? null : (
        <div className="browse-banner">{banner}</div>
      )}

      {failure === null ? null : (
        <div className="browse-note">
          <p className="browse-note-text">{failure.message}</p>
          {/* The CODE beneath the sentence, and never the sentence again.
              docs/DESIGN.md's rule is "human label large, machine string small beneath
              it", and the machine string it means is a greppable token — `store_busy`,
              `unreachable` — that says something the label above it does not. An earlier
              draft printed the server's one message in both slots, which is not that rule
              but a stutter, and it cost the small line the only job it has: getting from
              what is on screen to what the server said, with `git grep`. Owner-side only,
              and this screen is owner-side. */}
          <p className="browse-machine">{failure.code}</p>
        </div>
      )}

      {rows === null && failure === null ? (
        <p className="browse-note-text">Reading the inventory.</p>
      ) : null}

      {rows !== null && rows.length === 0 ? (
        <p className="browse-note-text">No cards captured yet.</p>
      ) : null}

      {rows !== null && rows.length > 0 ? (
        <div className="browse-body">
          {/* The map column: search, box strip, one status line, the list, then the keys that
              walk it. One column because they are one instrument — everything in it narrows
              or indexes the same walk, and the detail panel beside it is what the walk is
              pointing at. */}
          <div className="browse-map" ref={mapRef}>
            {/* The shared field: owner persona, `/` from anywhere, Esc handing focus back
                with the query intact — all SearchField's own rulings, not re-made here. The
                search-shape argument and the deliberate absence of autoFocus are at the
                useSearch call above. */}
            {/* NB: the box strip is below this, and `BoxIdentity` sits under it — see there. */}
            <SearchField value={query} onChange={setQuery} persona="owner" />

            {/* THE BOX STRIP — the capture screen's segmented-track idiom, not a row of
                buttons and not a <select>. Thirty boxes must fit over a 300-380px column,
                which rules out thirty padded chips by arithmetic; a native select fits any
                count by hiding the map behind a click, and a map you have to open is not a
                map. Hairline-divided 10px utility cells wrap to a second row past roughly a
                dozen boxes, which costs 20px and hides nothing.

                IT SELECTS RATHER THAN JUMPS NOW (D31) — the header at the top of this file
                argues the change. `aria-current` still marks where you are, so the strip still
                doubles as "you are here"; what moved is that the rail follows the SHELF rather
                than the selected card's box, and those were the same fact only while one walk
                held every box.

                DRAWN EVEN WITH ONE SHELF, which reverses the old rule and does not contradict
                it. A strip of one chip that jumps you to a row you can already see is chrome;
                a strip of one cell that NAMES the box the list below is of is the only place
                that fact appears when the box registry has not answered. */}
            {shelves.length === 0 ? null : (
              <div className="browse-boxline">
                <span className="browse-boxcap" aria-hidden="true">
                  Box
                </span>
                <div className="browse-boxes" role="group" aria-label="Choose a box to walk">
                  {shelves.map((cell) => (
                    <button
                      key={String(cell)}
                      className="browse-boxcell"
                      type="button"
                      aria-label={
                        cell === 'pooled'
                          ? 'Pooled cards, which have no box'
                          : cell === 'unplaced'
                            ? 'Records with no readable box'
                            : `Box ${cell}`
                      }
                      aria-current={cell === shelf ? 'true' : undefined}
                      onClick={() => selectShelf(cell)}
                    >
                      {shelfLabel(cell)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* WHAT THIS BOX IS, under the strip that just named it (owner, 2026-08-25) —
                its name, how full it is, whether it is sealed, and the shape of its sections.
                Drawn here rather than in a panel across the screen because this column IS the
                box: the strip above picks it, the walk below is its cards, and the operations
                at the bottom act on it. See `BoxIdentity`, which was split out of `BoxOps` for
                exactly this. Nothing for the pooled and no-box shelves, which are not boxes. */}
            {shelfBox === null ? null : (
              <BoxIdentity
                record={shelfBox}
                /* WHERE THE SELECTED CARD IS, ON THE BOX'S OWN BAR (owner, 2026-08-25). The
                   server's `fraction`, never `index / box_total` recomputed here — types.ts and
                   `PositionBar` both make that the rule, because the two disagree across a
                   sealed box's frozen capacity. Null for a card in another box, a pooled card,
                   or no selection at all, and the marker simply is not drawn. */
                at={
                  selectedRow !== null && selectedRow.card.box === shelfBox.box
                    ? (selectedRow.card.place?.fraction ?? null)
                    : null
                }
              />
            )}

            {/* The search's own failure, in the owner idiom: the sentence, then the
                greppable code. The walk below it is deliberately UNFILTERED while this
                stands — see the `visible` memo. */}
            {searchFailure === null ? null : (
              <div className="browse-note browse-mapnote">
                <p className="browse-note-text">{searchFailure.message}</p>
                <p className="browse-machine">{searchFailure.code}</p>
              </div>
            )}

            {/* ONE STATUS LINE FOR THREE FACTS ABOUT THE LIST, and it is one line because the
                map column's height is the list's height: everything above the rows is height
                the rows do not get. Before this it was a match line that existed only while
                searching; the fold state and the tick count both needed somewhere to live, and
                a line each would have cost 40px of walk permanently.

                THE TICK COUNT IS HERE RATHER THAN ONLY ON THE SECTIONS BECAUSE A FOLD CAN
                HIDE A TICK. Collapsing a section does not untick its rows — a tick is about a
                card and a fold is about the view — so how many cards a bulk write would reach
                has to be readable without opening anything. Each section header carries its
                own share of the same number for the same reason.

                `loading` is true through the debounce as well as the request — useSearch says
                why — so the match half is the honest answer to "is the list below an answer to
                the box above". */}
            <p className="browse-status">
              {sections.length < 2 ? null : (
                <>
                  <button className="browse-quiet" type="button" onClick={toggleAllSections}>
                    {anyExpanded ? 'collapse all' : 'expand all'}
                  </button>
                  <span className="browse-status-sep">·</span>
                  <span>
                    {sections.length} {sections.length === 1 ? 'section' : 'sections'}
                  </span>
                </>
              )}

              {searching && loading ? (
                <>
                  <span className="browse-status-sep">·</span>
                  <span>Looking.</span>
                </>
              ) : null}
              {searching && !loading && results !== null ? (
                <>
                  <span className="browse-status-sep">·</span>
                  <span>
                    {inQuery.length === 0
                      ? `nothing matches ${results.query}`
                      : `${visible.length} here · ${inQuery.length} of ${rows.length} match`}
                  </span>
                </>
              ) : null}

              {/* THE MASS-SELECT'S OWN SHARE OF THE LINE. `tick shown` operates on the rows the
                  current filter leaves standing IN THIS BOX, which is the only honest meaning
                  of "shown" — the indices a bulk write takes are box-scoped, so a control that
                  reached across boxes would be building a request the route cannot express. */}
              {visible.length === 0 ? null : (
                <>
                  <span className="browse-status-sep">·</span>
                  <button className="browse-quiet" type="button" onClick={tickAllShown}>
                    {shownAllTicked ? 'untick shown' : 'tick shown'}
                  </button>
                </>
              )}
              {picked.length === 0 ? null : (
                <>
                  <span className="browse-status-sep">·</span>
                  <span className="browse-status-picked">{picked.length} ticked</span>
                  <span className="browse-status-sep">·</span>
                  <button className="browse-quiet" type="button" onClick={() => setPicked([])}>
                    clear
                  </button>
                </>
              )}
            </p>

            {/* Focusable and labelled, so the interaction is reachable rather than
                folklore: a keyboard user gets a tab stop that announces itself as the list
                of cards and says which keys it answers to. `aria-keyshortcuts` is the
                machine-readable half of the chips — the same facts, said once to a person
                and once to a screen reader. The arrows are bound on the window and deliver
                MORE than the attribute claims; the deep keys and X are bound on this element
                and deliver exactly. Neither direction over-claims, which is the safe way for
                the attribute to be imprecise. */}
            {/* AN EMPTY BOX SAYS SO, because it is now a box you can actually be standing in.
                Until the strip learned the registry there was no way to select a shelf with no
                rows, so `visible.length === 0` below could only mean a search that matched
                nothing — which the status line above already reports — and rendering nothing
                was right. It can now also mean a real, registered, empty box, and rendering
                nothing for that is a blank column beside a box header, which reads as a screen
                that failed rather than a box that is empty.

                `filtered` is what keeps the two apart, and `shelfBox` is what keeps this off
                the pooled and no-box shelves, which have no registry row and cannot be empty in
                this sense. The second sentence points at the operations rather than repeating
                them: they are directly below this, and the reason the owner is here at all is
                usually to reach one. */}
            {visible.length === 0 && !filtered && shelfBox !== null ? (
              <p className="browse-empty">
                No cards in box {shelfBox.box} yet. Rename, re-section, seal or delete it below.
              </p>
            ) : null}

            {visible.length === 0 ? null : (
              <ul
                className="browse-list"
                ref={listRef}
                tabIndex={0}
                aria-label="Captured cards, in box-walk order"
                aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End X"
                onKeyDown={onListKeys}
              >
                {sections.map((section) => {
                  /* THE FOLD IS PRESENTATION AND NEVER A FILTER, which is the ruling that lets
                     every other control on this screen go on working. `visible` is untouched by
                     it, so the arrow keys, PgUp/PgDn, Home/End, the match counts and the box
                     strip all still walk the whole box — and a step into a collapsed section
                     OPENS it rather than selecting a row nobody can see. The alternative
                     (collapsing removes rows from the walk) would make a fold a second, silent
                     narrowing beside the search, and two narrowings that look different and
                     compound is how a screen starts lying about how many cards it holds.

                     FULLY COLLAPSED BY DEFAULT — zero rows, INCLUDING the section holding the
                     selection the loader planted. Box 2 holds 544 cards over five sections;
                     opened flat that is a scroller whose position tells you nothing, which is
                     the complaint this work started from. Opened collapsed it is a table of
                     contents readable at a glance.

                     THE ARRIVING SELECTION USED TO OPEN ITS SECTION AND NO LONGER DOES, which
                     is the owner's click-twice bug: a screen that arrives partly expanded while
                     the control beside it says `expand all` needs two presses to reach a
                     collapsed list. Nothing is lost by shutting it — the selected card's
                     photograph, its facts and its copies are all drawn in the detail column
                     beside this list; only its ROW is folded away, and any key that moves the
                     selection opens the section it lands in. See the nav effect above for the
                     line that draws that distinction. */
                  const open = isOpen(section)
                  const ticked = section.rows.filter((row) => picked.includes(row.key)).length
                  return (
                    /* One li per stretch of the walk, its header sticky WITHIN it: the header
                       holds the scroller's top edge while its own rows pass and is pushed off
                       by the next one — so "where am I" is always on screen, which is the
                       first thing a two-hundred-row scroller loses. */
                    <li className="browse-group" key={section.key}>
                      <div className="browse-secthead">
                        {/* THE SECTION IS THE NATURAL UNIT OF A MASS-SELECT, so the tick that
                            arms one sits on the section's own header — and it works whether the
                            section is open or shut, which is half of why a fold may hide rows
                            without hiding what a bulk write would reach. `indeterminate` is a
                            DOM property with no attribute behind it, so it is set through a
                            callback ref: React cannot express it as JSX. */}
                        <input
                          className="browse-secttick"
                          type="checkbox"
                          checked={ticked > 0 && ticked === section.rows.length}
                          ref={(node) => {
                            if (node !== null)
                              node.indeterminate = ticked > 0 && ticked < section.rows.length
                          }}
                          aria-label={`Tick every card in ${section.title}`}
                          onChange={(event) => tickSection(section, event.target.checked)}
                        />
                        <button
                          className="browse-sectfold"
                          type="button"
                          aria-expanded={open}
                          onClick={() => toggleSection(section)}
                        >
                          <span className="browse-sectmark" aria-hidden="true" />
                          <span className="browse-secttitle">{section.title}</span>
                          <span className="browse-sectcount">
                            {ticked === 0
                              ? section.rows.length
                              : `${ticked}/${section.rows.length}`}
                          </span>
                        </button>
                      </div>
                      {!open ? null : (
                        <ul className="browse-group-rows">
                          {section.rows.map((row) => (
                            <li className="browse-rowline" key={row.key}>
                              {/* THE TICK IS OUTSIDE THE ROW BUTTON, because a button inside a
                                  button is invalid markup and two overlapping targets is the
                                  overshoot hazard `CardLocations.tsx` records. Two gestures,
                                  two meanings: the row selects, which writes nothing; the tick
                                  arms a bulk write that has not happened yet. */}
                              <input
                                className="browse-rowtick"
                                type="checkbox"
                                checked={picked.includes(row.key)}
                                aria-label={`Tick ${rowSlot(row)}`}
                                onChange={() => toggleTick(row.key)}
                              />
                              {/* Plain buttons, and they stay plain buttons now that the arrow
                                  keys are bound. Tab reaches every one of them for free, the
                                  click path is untouched, and `aria-current` below is still the
                                  one mark of which row is current — a roving-focus listbox
                                  would trade all three for an activedescendant dance this
                                  screen does not need.

                                  FOCUS DELIBERATELY DOES NOT FOLLOW THE SELECTION. It is the
                                  obvious next step and it is the wrong one: a held Right would
                                  fire a focus move per card, dragging focus out of wherever the
                                  owner left it and scrolling on its own account, thirty times a
                                  second. The row is marked, not focused, and the scroll effect
                                  above is what keeps it on screen.

                                  One line per card — the slot under its section header, then
                                  the name. rowSlot above says what the left cell may claim,
                                  fallbacks included. */}
                              <button
                                className="browse-row"
                                type="button"
                                aria-current={row.key === selected ? 'true' : undefined}
                                onClick={() => setSelected(row.key)}
                              >
                                <span className="browse-row-position">{rowSlot(row)}</span>
                                <span className="browse-row-name">
                                  {row.card.name ?? row.card.state}
                                </span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            {/* THE LIST-KEYS CHIP ROW IS GONE (owner, 2026-08-25). It drew PgUp/PgDn/Home/End/X
                with their captions under the walk — 51px of permanent chrome in a sticky column
                capped at the viewport, which is 51px the walk did not get on every card of every
                box. The bindings are untouched: SECTION_KEYS, EDGE_KEYS and TICK_KEY still fire,
                and the header's own chip row still advertises the window keys. What went is the
                advertisement for the deep ones, which is a thing learned once and then read
                past for the rest of the day. */}

            {/* `RegisterBox` STOOD HERE AND IS DELETED (owner, 2026-08-26: "delete register a
                new box from inventory screen"). It offered a box number, a name and dividers,
                and made an empty box.

                THE CAPABILITY IS NOT LOST, WHICH IS THE ONLY THING THAT MADE THE DELETION SAFE.
                `CaptureScreen.tsx:createOfferedBox` calls the same `POST /boxes` from the Box
                field: an entry matching no box offers to create it, by name or by number, and
                the box it makes holds nothing until a photograph lands in it. That is D20's
                "the box that holds nothing is the point", served from the screen a person is
                standing at when they reach for a new drawer rather than from the one they use
                to look up where a card already is.

                WHAT WENT WITH IT is the argument for its placement — it sat UNDER the walk
                rather than over it, because this column is sticky and viewport-capped, so a
                44px control between the strip and the list was 44px of rows the walk never got.
                That reasoning is worth keeping as a rule about this column even though the
                control it was written for is gone: anything added above `.browse-list` is paid
                for out of the cards. */}
            {/* THE BOX'S OWN OPERATIONS, and now the last thing in the box's own column.
                Rename, re-divide, seal, set claims over the ticked cards, release a listing
                hold, delete the box — every one of them acts on a BOX, which is what makes this
                the wrong neighbour for a card panel.

                BELOW THE WALK RATHER THAN ABOVE IT, and that costs nothing because the walk
                scrolls inside this column: `.browse-list` is `flex: 0 1 auto` with its own
                `overflow-y`, so these stay on screen while 543 cards move past them. Above the
                walk they would push the cards down for every card, to be reached once a box.

                IT TAKES THE TICKED SELECTION, which is what turns a column of checkboxes into a
                feature: `PUT /inventory/<box>` applies retroactive capture claims over a box or
                over an explicit list of indices, and the list is the one these ticks build. The
                scope sentence is written onto the button there, so the widening from "the ticked
                cards" to "the whole box" is never silent.

                `onChanged` bumps the same counter Reload does, which re-reads the registry AND
                the inventory — a divider edit relabels every card in the box (D10 as amended),
                so the walk has to be re-read with the panel. */}
            {shelfBox === null ? null : (
              <BoxOps
                record={shelfBox}
                selection={pickedIndices}
                onChanged={() => setReloads((n) => n + 1)}
              />
            )}
          </div>

          <div className="browse-side">
            {/* THE SELECTED CARD IS THE WHOLE OF THIS COLUMN NOW, which is where two successive
                fixes to the same complaint arrived. The first, on 2026-08-24, moved the card
                ABOVE the box header inside one column: measured at 1440x900, the header (190px)
                and the two folds sat over it, so the photograph of the card just clicked opened
                at y=482 of a 900px viewport and ran to y=917, cut off. The second, on
                2026-08-25, moved the box header and the runs OUT — see `.browse-boxrun` below.
                Ordering them was the cheap fix; not sharing a column with them is the real one.

                MOVED IN THE DOM RATHER THAN WITH `order`, both times. A flex `order` would have
                produced the same picture and left the tab ring and a screen reader walking the
                old sequence. The two orders are kept the same on purpose. */}
            {/* THE RECEIPT SURVIVES AN EMPTY LIST, AND IT DID NOT UNTIL 2026-08-24.
                `detail` — the receipts, their undo, and the refusal panel — is rendered
                inside the `selectedRow` guard below, which is right while there IS a selected
                card. But `selectedRow` is `visible.find(...) ?? null`, so a query that matches
                nothing makes it null and unmounts the whole detail column: a receipt whose
                twenty-second undo is still running disappears, and so does a refusal the
                operator has not read yet.

                That is the exact invariant Inventory.tsx says it fixed — a receipt must not be
                hidden by moving to another card — arrived at from the other direction, because
                nothing there considered moving to NO card. Repro: mark a copy sold, then type a
                query matching nothing inside twenty seconds.

                Rendered here only when the guard below cannot: never twice, always once. */}

            {selectedRow === null ? null : (
              /* A BAND AND A ROW UNDER IT, AND THE MEASUREMENT IS THE ARGUMENT. This panel drew
                 everything in one 420px-wide stack inside an 824px column, so half the width of
                 the widest thing on screen sat empty beside a photograph while the facts under
                 it pushed everything else below the fold. Splitting it into two columns fixed
                 that and left a second version of it: the photograph then ran 587px against
                 204px of facts, so the column that held the facts had ~380px of nothing under
                 them and everything real was still below the fold.

                 So the split is no longer down the middle of the panel. The photograph and the
                 seven rows read ABOUT the card are one BAND, the same height because the
                 photograph now takes its height from the rows (D38); the headline spans both
                 above it, because a position label is what the whole panel is for; and
                 `.browse-under` spans both below it, because the copies list and the card's
                 own writes want a measure and neither of the band's two tracks is one. */
              <section
                className={
                  photoMissing(selectedRow, photoAbsent === selectedRow.key)
                    ? 'browse-detail is-absent'
                    : 'browse-detail'
                }
              >
                <div className="browse-headline">
                  {selectedLabel === null && isPooled(selectedRow.card) ? (
                    /* Pooled, not missing — the deliberate case, before the fault below can
                       claim it. The sentence says what the card IS so the absent label stops
                       looking like something to go and fix. */
                    <div className="browse-gap">
                      <p className="browse-note-text">
                        This card is pooled — a count, not a location. It has no box, section or
                        card position to show; the key below names its photo and sidecar on
                        disk, and nothing else.
                      </p>
                      <p className="browse-machine">
                        located: false · {pooledText(selectedRow.card, selectedRow.key)}
                      </p>
                    </div>
                  ) : selectedLabel === null ? (
                    /* The gap, drawn as a panel in the space the label would have filled.
                       Loud rather than blank: this screen's whole claim is that it says where
                       a card is, and a screen that has quietly stopped making that claim
                       should not look like one that is still making it. */
                    <div className="browse-gap">
                      {/* Both causes, because the sentence has to survive being read on the
                          wrong one: a restart fixes an old server and does nothing at all for a
                          record whose box will not coerce. Naming only the likelier one would
                          send the operator round a loop that cannot work. */}
                      <p className="browse-note-text">
                        The capture server sent no position label for this card, and this screen
                        does not work one out for itself. Either an older server is running —
                        restart it with `make server` and reload — or this record&rsquo;s box or
                        index is not a number, which `GET /status` reports.
                      </p>
                      {/* The field and its state, in the shape the missing-photo panel below
                          uses — `photo: null` there, `label: absent` here — plus the store key,
                          which is what a `curl /inventory | grep` needs to see it for itself. */}
                      <p className="browse-machine">label: absent · key {selectedRow.key}</p>
                    </div>
                  ) : (
                    /* The payload of the whole screen. Utility face because it is a position,
                       and sized up because it is the one thing being checked against a physical
                       box across the desk. */
                    <>
                      <p className="browse-position">
                        <PositionLabel label={selectedLabel} />
                      </p>
                      {/* D30's neighbours, RANKED rather than joined (D41's move one line
                          down — the connectives are the separators and the names are the
                          payload). `Card 19` is the nineteenth card in the box and these are
                          what let a hand count to it. `PlaceNeighbors` answers nothing —
                          never a guess — for a pooled card, an older server, a decoration the
                          server degraded, or the one card whose box holds nothing else.

                          THE GAP CLAUSE THAT USED TO TRAIL IT IS GONE (owner, 2026-08-30):
                          D58 closes the box up over a departed card, so the count no longer
                          comes out short and the clause had nothing left to explain. */}
                      <div className="browse-position-said">
                        <PlaceNeighbors place={selectedRow.card.place} />
                      </div>
                    </>
                  )}
                </div>

                {/* JUST THE PHOTOGRAPH. The re-shoot moved inside `Correct claims` (owner,
                    2026-08-25) — see CardOps, which is where the argument for that now lives. */}
                <div className="browse-shot">
                  <PhotoPanel
                    row={selectedRow}
                    label={selectedLabel}
                    absent={photoAbsent === selectedRow.key}
                    onAbsent={() => setPhotoAbsent(selectedRow.key)}
                    nonce={reshot[selectedRow.key] ?? null}
                  />
                </div>

                {/* WHAT THIS CARD IS — the eleven fact rows, and nothing else since 2026-08-26.
                    `CardOps` and the open-question block sat under them here, on the argument
                    that the band's two sides were different heights and the ~70px they filled was
                    air that would otherwise sit under the facts. That was true of a two-track
                    band and this one has three: the writes get a track, and the facts get a
                    measure cut to their own ink rather than a `1fr` that was 260px at 1440 and
                    100px at 1280. See `.browse-detail` in the stylesheet for both numbers. */}
                {/* THE FACTS ARE NOT DRAWN HERE ANY MORE — they cap the copies column, in
                    `.browse-under` below. Left as a marker rather than deleted silently, because
                    this is the second time in four days that something moved out of this band and
                    a reader arriving at `.browse-detail` should be told where it went rather than
                    inferring it from an absence. `BoxBrowse.css`'s `.browse-detail` comment carries
                    the measurement that decided it. */}

                {/* WHAT CAN BE DONE TO THIS CARD, in a track of its own (2026-08-26). These two
                    blocks were the tail of `.browse-about`, under the eleven fact rows, and the
                    move is what takes the band from 445px to 420px on its own — a card-level
                    write does not want the 300px measure a definition list wants.

                    THE ORDER IS UNCHANGED AND SO IS THE DOM SEQUENCE: what is waiting on this
                    card, then what can be done about it. Moved in the DOM rather than with
                    `order`, this file's standing rule, so the tab ring and a screen reader walk
                    what the eye walks. */}
                <div className="browse-ops">
                  {/* WHETHER THIS CARD HAS AN OPEN QUESTION, which is the fact that ties the
                      three things this screen is for together: the walk finds the card, this
                      says whether anything is waiting on it, and the run panel one column over
                      is what would answer it.

                      IT IS NOT DUPLICATION OF `#/review`, and the distinction matters because
                      D38 just deleted a duplication one column left. That screen answers "what
                      is left to do, in worked order"; it cannot be searched by card and has no
                      deep link, so the walk is the only path from a physical slot to a card.
                      This is the same fact reached from the other direction, not the same
                      rendering drawn twice.

                      OUTSIDE THE `<dl>` ON PURPOSE, and one of the three reasons has since
                      been spent. It read "`detailsOf` is a pure function of `InventoryCard` and
                      a queue entry is per-POSITION" — and the Market row added on 2026-08-29 is
                      per-position too, passed in as a second argument, so that clause no longer
                      separates the two. What still does: a `dt`/`dd` grid row cannot hold the
                      two-line reason DESIGN.md's reason-code rule requires, and it must not,
                      because a queue block is a SENTENCE about what to do next where every row
                      in that list is a value being compared against something.

                      The candidate count is load-bearing rather than decoration: zero candidates
                      is the difference between "go and answer it" and "it cannot be answered as
                      it stands", and it is what points at the re-shoot icon already on this
                      panel. `POST /review/<box>/<index>/answer` refuses a candidate-less entry
                      as `no_candidates`. */}
                  {(() => {
                    const open = openQuestion(queued, selectedRow)
                    if (open === null) return null
                    const { entry, queue } = open
                    const answerable = entry.candidates.length > 0
                    return (
                      <div className="browse-queued">
                        <p className="browse-note-text">
                          Waiting in the {queue === 'review' ? 'review' : 'parked'} queue —{' '}
                          {reasonLabel(entry.reason)}. {waitingFor(entry.first_seen)}.{' '}
                          {answerable
                            ? `${entry.candidates.length} candidate row${entry.candidates.length === 1 ? '' : 's'} to choose from on the review screen.`
                            : 'No candidate rows, so it cannot be answered as it stands — re-shoot it, or stand it down from the review screen.'}
                        </p>
                        {/* A token the sentence does not already say. Never the sentence again:
                            `.browse-machine`'s own comment records this file making exactly that
                            mistake — "reads as a stutter and greps to nothing". */}
                        <p className="browse-machine">
                          {entry.reason} · {queue} · candidates {entry.candidates.length}
                        </p>
                      </div>
                    )
                  })()}

                  {/* The card-level writes: two change a claim the pipeline reads and the third
                      deletes a record. See CardOps. */}
                  <CardOps
                    key={selectedRow.key}
                    row={selectedRow}
                    onChanged={() => setReloads((n) => n + 1)}
                    /* A SLOT RATHER THAN FOUR THREADED PROPS. The re-shoot's state — which card
                       is uploading, which refusal belongs to which card, and the cache-busting
                       nonce per key — already lives up here beside the photo it replaces, and
                       handing `CardOps` the rendered node keeps it there. */
                    reshoot={
                      <ReshootControl
                        row={selectedRow}
                        busy={reshootBusy === selectedRow.key}
                        failure={
                          reshootFailure !== null && reshootFailure.key === selectedRow.key
                            ? reshootFailure.failure
                            : null
                        }
                        onPick={(file) => beginReshoot(selectedRow, file)}
                      />
                    }
                  />
                </div>

              </section>
            )}
          </div>

          {/* THE COPIES OF THIS CARD, DIRECTLY UNDER IT — D7's SKU -> positions map, handed down
              by the screen that owns the write. This is where the merged Find mode went: you
              search, the walk narrows, you pick one, and every other copy is right here with its
              own position and its own controls. The node belongs to `Inventory.tsx` because the
              receipts, the undo windows and the two confirm panels are one flow with twenty
              pieces of state, and splitting a flow across two components is how half of it drifts.

              IT MOVED UP PAST THE CONSOLE ON 2026-08-26, and the reason is in `BoxBrowse.css`'s
              `.browse-body` comment: a grid row is as tall as its tallest cell, so while the card
              and the run panel shared row 1 these began at y=938 — or y=1599 with a run picked,
              1039px of white below the card on a 2214px page. The answer to "where is this card"
              was positioned by a panel about something else, at an unbounded height.

              IT KEEPS THE FULL MEASURE, which was never the problem and is not negotiable:
              `CardLocations.css`'s container query cuts the row 159px -> 83px as the container
              crosses ~940, so the copies get the content column's whole width exactly as they got
              columns 2+3 before. 1024px at 1440, and the same 864px at 1280 they have today.

              RENDERED ONCE, WHICH IS THE SECOND THING THIS BUYS. `detail` used to draw at two
              mutually exclusive sites so that a receipt whose twenty-second undo was still
              running would survive a query matching nothing. Out here it is not inside
              `selectedRow`'s guard at all, so that invariant is structural rather than a prose
              promise — and `.browse-body > .browse-under:empty` hides only a node with no
              children, so a standing receipt is never the thing collapsed.

              BEFORE `.browse-boxrun` IN THE DOM, NOT AFTER. This file rules twice that a reorder
              happens in the DOM rather than with `order`, so the tab ring and a screen reader
              walk what the eye walks. That rule is unchanged; what it now produces is card,
              copies, runs — the old comment here said "card, runs, copies is reading order at
              both breakpoints", and that sentence moved with the rows rather than being kept. */}
          {/* THE DESCRIPTION CAPS THIS COLUMN, ABOVE THE COPIES (2026-08-29, the owner's ask).
              It is guarded on `selectedRow` rather than living inside `.browse-side`'s guard,
              because this node must keep rendering when no card is selected — a standing
              mark-sold receipt with a live twenty-second undo lives in `{detail}` and the
              paragraph above is the whole reason it is out here. So the two children have
              DIFFERENT conditions on purpose: the facts follow the selection, the receipt does
              not, and `.browse-under`'s hide rule in the stylesheet asks about both. */}
          <div className="browse-under">
            {selectedRow === null ? null : (
              <div className="browse-about">
                <dl className="browse-facts">
                  {detailsOf(
                    selectedRow.card,
                    selectedRow.card.run === null ? undefined : priced[selectedRow.card.run],
                  ).map((fact) => (
                    <div className="browse-fact" key={fact.label}>
                      <dt>{fact.label}</dt>
                      <dd className={fact.mono ? 'is-util' : undefined}>{fact.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            {detail}
          </div>

          {/* THE RUNS, LAST IN THE CONTENT COLUMN — and until 2026-08-26 this was a third column
              beside the card. D31 put box operations "on the box header inside the browse", D38
              moved the box into the walk's column and left the runs a 370px track of their own,
              and this is the third move in that sequence: the track is gone and the panel is a
              full-width band under the copies.

              WHY, IN ONE SENTENCE: its height, not its width, was the defect. A grid row is as
              tall as its tallest cell, so a 799px console — 1461px with a run picked — decided
              where the card's own copies began. `BoxBrowse.css`'s `.browse-body` comment carries
              the measurements and the trade.

              NOTHING FOLDS, WHICH IS THE HALF D33 ACTUALLY SETTLED, and it is untouched: no
              disclosure, no cap, no internal scroller, every step head and note drawn in every
              state, the spend button still absent-until-preflight rather than disabled. What
              changed is where the panel sits in the reading order, not whether it is drawn — and
              it draws SHORTER here than it did in the column, because 1024px unwraps its head,
              its notes and its free steps: 799 -> 625 closed, 1461 -> 1143 open, with no code
              change at all.

              THE `selectedRow` GUARD STILL CANNOT REACH IN HERE. It is a `.browse-body` child in
              its own grid row, and the guard lives inside `.browse-side` — so a control about the
              SHELF cannot be slid inside a card's guard without first being moved between rows,
              which is the structural version of a promise this comment used to make in prose.
              `app/tests/inventory.spec.ts` asserts `.browse-side .run-panel` is never rendered. */}
          <div className="browse-boxrun">
            {/* WHY THERE IS NO BOX PANEL IN THE LEFT COLUMN, said in the column that has room
                for the sentence. The pooled and no-box shelves are not boxes and have nothing to
                rename, divide or seal. */}
            {shelf === 'pooled' ? (
              <div className="browse-gap">
                <p className="browse-note-text">
                  These cards are pooled — a count, not a location (D24). They have no box,
                  section or card position, so there is no box to name, divide or seal.
                </p>
                <p className="browse-machine">located: false</p>
              </div>
            ) : null}

            {shelf === 'unplaced' ? (
              <div className="browse-gap">
                <p className="browse-note-text">
                  These records reached the store with a box or an index that is not a number,
                  so the capture server sent them with no position at all. `GET /status`
                  reports them; nothing here can name a box for them.
                </p>
                <p className="browse-machine">place: absent</p>
              </div>
            ) : null}

            {/* THE RUN LINE IS IN THE HEADER NOW — see `.browse-controls` above. It is
                box-scope content and this node is in the content columns, so its y-position was
                being set by the copy count and by whether the claims editor happened to be open:
                measured, y=1164 on a six-copy card and y=1572 on an eleven-copy one, both below
                a 900px fold. Nothing about it varies with the selected card. */}
          </div>

        </div>
      ) : null}
    </section>
  )
}

/* WHETHER THERE IS A PHOTOGRAPH TO DRAW, asked in one place because two callers need the same
 * answer and a second copy is how they drift. `PhotoPanel` below branches on exactly these two
 * conditions to render `.browse-absent` instead of an image, and `BoxBrowse` needs the same fact
 * one level up to decide whether the shot/facts band can exist at all — a 150px track is right
 * for a card and wrong for a paragraph, so the band collapses to one column when the panel is a
 * sentence (see `.browse-detail.is-absent`).
 *
 * Written as a predicate rather than lifted state: both facts are already here. `photo === null`
 * is on the record, and `absent` is the 404 this screen learned about from the <img>'s own
 * onError. */
function photoMissing(row: Row, absent: boolean): boolean {
  return row.card.photo === null || row.card.photo_reclaimed_at !== null || absent
}

type PhotoPanelProps = {
  row: Row

  /** The server's own position label, or null when this row arrived without one. Handed
   *  down rather than derived here — see the note beside `selectedLabel`. */
  label: string | null

  absent: boolean
  onAbsent: () => void

  /** The capture id of a photo THIS SESSION replaced at this position, or null for the
   *  ordinary card. Non-null appends `?reshot=<id>` to the img src — see the comment at
   *  `base` below for why that is the one legitimate query parameter on this URL. */
  nonce: string | null
}

/* Three ways a photo can be missing, and they are different facts, so they get different
 * sentences rather than one broken image.
 *
 *   `photo` is null            — no photo was ever stored. `emit` can record a card that was
 *                                never photographed, and `store/master.py` keeps the field
 *                                null for it.
 *   `photo_reclaimed_at` set   — the photograph was deleted ON PURPOSE after the card sold
 *                                (D89), and the record kept its digest. Checked before the
 *                                404 branch because the route WILL 404 for this card, and the
 *                                404 sentence would call a deliberate reclaim a loss.
 *   the route 404s             — the record claims a photo and the file is not there. That
 *                                is a store that has lost something, and it is worth saying
 *                                so plainly.
 *
 * The last two print what was asked for, so the next move is a curl rather than a guess.
 */
function PhotoPanel({ row, label, absent, onAbsent, nonce }: PhotoPanelProps) {
  /* One phrasing, used by both the sentence beside a missing photo and the alt text on a
   * present one, so those two cannot end up disagreeing about where the card is. The
   * fallback says `store key` out loud rather than printing `3/30` bare: bare, it reads
   * like a position, and the whole point of the null case is that no position was sent. */
  const where = label ?? `store key ${row.key}`

  if (row.card.photo === null) {
    return (
      <div className="browse-absent">
        <p className="browse-note-text">No photo was stored for this card.</p>
        <p className="browse-machine">photo: null</p>
      </div>
    )
  }

  if (row.card.photo_reclaimed_at !== null) {
    return (
      <div className="browse-absent">
        <p className="browse-note-text">
          Photograph reclaimed after the sale — deleted on purpose, record kept (D89).
        </p>
        <p className="browse-machine">
          reclaimed {row.card.photo_reclaimed_at}
          {row.card.photo_sha256 ? ` · sha256 ${row.card.photo_sha256.slice(0, 16)}…` : ''}
        </p>
      </div>
    )
  }

  /* The URL as `server.ts` mints it — with nothing appended, EXCEPT after a re-shoot.
   *
   * There is a real hazard here and it is worth naming rather than inheriting silently:
   * undo deletes a photo and releases its index, so the next capture reuses this exact URL
   * for different bytes, and `GET /photo` sends no `Cache-Control`, no `ETag` and no
   * `Last-Modified`. A browser that held one of these would show a stale photo at a correct
   * position — precisely the failure this screen exists to catch, and invisible when it
   * happens.
   *
   * A LOAD-TIME cache-busting parameter minted here was written and then removed, and it
   * stays removed. `server.ts:photoUrl`'s comment rejects that fix by name — the general
   * repair belongs in a response header on the server, one line in
   * `server/capture_server.py:_send` — and a nonce on every render would defeat what
   * caching this screen benefits from while papering over the missing header.
   *
   * THE RE-SHOOT NONCE IS THE ONE EXCEPTION, ARGUED AGAINST THAT COMMENT RATHER THAN
   * AROUND IT. What that comment refuses is a guess: a parameter added on every load
   * because the bytes MIGHT have changed. After `reshootPhoto` succeeds there is no might
   * — THIS screen sent the new bytes to this exact URL, so rendering the src that a
   * moment ago showed the photograph it just destroyed is showing a picture the store no
   * longer holds, the stale-photo failure above realised by our own hand. One screen, at
   * the one moment it knows, appending the id of the photograph it expects: that is
   * cache-busting as a statement of fact, not as a workaround, and photoUrl's comment now
   * names it as the standing exception. */
  /* THE URL NAMES THE PHOTOGRAPH, NOT THE SLOT (D52), AND THAT IS THE WHOLE OF THE FIX HERE.
   * `photoUrl` answers `/photo/<box>/<index>`, which is an address that CHANGES ITS
   * MEANING: D10 ruling 1's mid-box delete slides a different card into the slot this
   * screen is still pointing at, and D10's undo releases an index the next capture reuses.
   *
   * TWO CHEAPER REPAIRS WERE BUILT AND MEASURED FIRST, AND NEITHER IS SUFFICIENT — which
   * is why this one is here and why the two below stay:
   *
   *   1. A validator on the server. `GET /photo` now sends a strong `ETag` and
   *      `Cache-Control: no-cache`, which is the repair `server.ts:photoUrl` has named in
   *      writing since it was written. It is necessary and it does not reach this case: a
   *      header is a rule about reusing a cached RESPONSE, and an `<img>` that React keeps
   *      in the document never asks for one.
   *   2. The occupant in this element's `key`, so React remounts it. It does remount —
   *      observed, `sameDomNode: false` across a delete — and the picture still did not
   *      change, because Chrome satisfies a second load of an IDENTICAL URL in one
   *      document from its in-memory resource cache, which consults neither the ETag nor
   *      `no-cache`. Measured: one resource-timing entry, `transferSize: 0`, before and
   *      after.
   *
   * SO THE STAMP IS NOT A CACHE-BUSTER AND `photoUrl`'s COMMENT DOES NOT FORBID IT. What
   * that comment refuses is a nonce minted per LOAD because the bytes might have changed —
   * a value that defeats caching by never repeating. `capture_id` is the opposite: it is
   * stable for the life of a photograph, so this card keeps one URL forever and caches
   * better than it did, and a URL only changes when the thing behind it does. The re-shoot
   * exception that comment already carries is now a special case of this rule rather than
   * a separate mechanism — `nonce` IS the new capture id, so it is the same stamp arriving
   * one re-read early, and it wins while it is set.
   *
   * A RECORD WRITTEN BEFORE CAPTURE IDS EXISTED CARRIES null and falls back to the bare
   * slot URL, exactly as before. That is the honest limit rather than a reason to invent a
   * value: `do_remove_card` aims by the same field and is blind in the same place, and the
   * server's ETag is what still makes a Reload right. */
  const base = photoUrl(row.card.box, row.card.index)
  const stamp = nonce ?? row.card.capture_id
  const src = stamp === null ? base : `${base}?card=${encodeURIComponent(stamp)}`

  if (absent) {
    return (
      <div className="browse-absent">
        <p className="browse-note-text">
          The record has a photo but the file is not on disk. The card is still at {where} —
          and a photo added below replaces nothing, it is the first one this position would
          have again.
        </p>
        <p className="browse-machine">{src}</p>
      </div>
    )
  }

  return (
    <img
      /* Remounted per card AND per replacement: `src` in the key means a re-shoot swaps
         the element rather than mutating it, so a failed load cannot leave the previous
         photograph's broken state attached to the new one.

         AND PER OCCUPANT, WHICH IS THE HALF A RENUMBER NEEDS. `row.key` is a POSITION and
         `src` is derived from one, so after D10 ruling 1's mid-box delete both are
         unchanged for the slot that is still selected — while the card in it is a
         different card. React then reuses this element, no load is initiated, and no
         response header can help: `Cache-Control` is a rule about reusing a cached
         response, not about an element that never asks for one. Measured on a copy of the
         owner's store: deleting box 2 card 180 left the deleted card's photograph on
         screen over its replacement's facts, at the same position label, which reads as
         the delete not having happened — and the next press deletes the card that slid in.

         `capture_id` IS THE OCCUPANT'S IDENTITY AND IS ALREADY ON THE ROW. It changes
         exactly when the physical card at this slot changes and never otherwise, so this
         costs no request on an ordinary re-render: a remount re-validates against the
         server's ETag and takes a 304 whenever the bytes really are the same.

         A RECORD WRITTEN BEFORE CAPTURE IDS EXISTED CARRIES null, and two of those in one
         box are indistinguishable here. That is the honest limit rather than a reason to
         mint something: `do_remove_card` aims by the same field and has the same blind
         spot, and a Reload is correct in both. */
      key={`${row.key}:${row.card.capture_id ?? 'no-id'}:${src}`}
      className="browse-photo"
      src={src}
      alt={`The card photographed at ${where}`}
      onError={onAbsent}
    />
  )
}

/* The re-shoot control — the pull preview's one write. The header at the top of this file
 * carries the ruling (D26's second half, placed here by the owner) and the no-dialog
 * argument; what this component decides is the MECHANISM, and the honest one on this
 * screen is a file.
 *
 * NOT A CAMERA, ON PURPOSE. This screen has none, and wiring one in would duplicate the
 * capture screen's whole device-picker apparatus (D13: no facingMode, UVC labels, a
 * rotation chip) for a control used once in a while. The rig capture screen is for live
 * shooting; this control replaces a bad STORED photo with a better frame from wherever
 * the owner has one — a re-shot rig frame saved to disk, a phone photo airdropped over.
 * `accept="image/jpeg"` because the server stores what it is given and never converts
 * (`image_not_jpeg` is its word on anything else, rendered verbatim below).
 *
 * NOT DRAWN AT ALL FOR A SOLD OR RETIRED CARD — the `restores_to` lesson, learned twice:
 * never offer a control whose only behaviour is a refusal. The server would refuse both
 * (`card_sold`: the stored photo is the dispute record; `card_retired`: a photo of a card
 * that left is a photo of nothing), and this screen reads the same state field the server
 * checks. Not-rendered rather than disabled, the same ruling the shell applies to nav.
 */
type ReshootControlProps = {
  row: Row
  busy: boolean

  /** This card's own refusal or null — the caller keys failures by row so another card's
   *  refusal cannot render under this card's photo. */
  failure: Failure | null

  onPick: (file: File) => void
}

function ReshootControl({ row, busy, failure, onPick }: ReshootControlProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  if (row.card.state === 'sold' || row.card.state === 'retired') return null

  /* One string, used as the accessible name, the tooltip, and the refusal panel's heading —
     so the three cannot drift into describing different controls. */
  const label = busy
    ? 'Replacing the photo…'
    : row.card.photo === null
      ? 'Add a photo'
      : 'Re-shoot this photo'

  return (
    <div className="browse-reshoot">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          /* Cleared before use, so picking the SAME file again fires onChange again —
           * which is exactly what a retry after a refusal is. */
          event.target.value = ''
          if (file !== undefined) onPick(file)
        }}
      />
      {/* THE WORDS ARE BACK, AND THE ICON WAS THE RIGHT ANSWER TO A QUESTION THAT NO LONGER
          EXISTS. It became a 24px glyph on 2026-08-25 when this sat under the photograph and the
          owner called the button "a text box taking up so much horizontal space" — true of a
          control living in a column whose width IS the photograph's. It now lives inside
          `Correct claims`, where there is a panel's width, and a glyph whose meaning has to be
          recovered from a tooltip is worse than the words when the words fit.

          The label changes with the fact — a card `emit` recorded without a photograph has
          nothing to re-shoot, and the route's own comment calls that case the first photograph
          the position has, so this says so rather than claiming a replacement.

          No accent fill: docs/DESIGN.md reserves the solid fill for a screen with exactly one
          thing to do, and this panel offers five corrections and a cancel. */}
      <button
        className="browse-reload"
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {label}
      </button>
      {failure === null ? null : (
        <div className="browse-note">
          <p className="browse-note-text">{failure.message}</p>
          <p className="browse-machine">{failure.code}</p>
        </div>
      )}
    </div>
  )
}

/* THE CARD-LEVEL OPERATIONS — correct what this card claims, and delete a junk capture out of
 * the middle of a box. Two routes that had no control on any screen until now.
 *
 * A ROUTE IS NOT A FEATURE (CLAUDE.md, 2026-08-23). `POST /inventory/<box>/<index>/remove` was
 * built with full T7 coverage and no client function; `PUT /inventory/<box>/<index>` had a
 * client function that silently omitted `rarity_claim`, which the route had always accepted —
 * so the one claim a correction is most likely to be about was the one no screen could correct.
 * The owner found both by looking for them and not finding them.
 *
 * ON THIS PANEL BECAUSE THIS IS THE SCREEN WHERE A BAD CAPTURE IS DISCOVERED. D26 put the
 * re-shoot here with exactly that argument — "the screen whose whole job is looking at one
 * stored photo beside its position, so the moment a bad photo is discovered is the moment the
 * remedy is already on screen" — and the same sentence is true of a photograph of the desk, of
 * a card captured under the wrong set hint, and of a stack toggled to the wrong finish. The
 * three remedies now sit together: replace the photo, correct the claim, or remove the record.
 *
 * THE DELETE GATES AND THE CORRECTION DOES NOT, and the split is docs/DESIGN.md's. A claim
 * correction is a write you can write again — the field is still on screen, the card is still
 * in its slot — so it takes no confirm, per the ban on dialogs over reversible actions. The
 * mid-box delete is D10's ONE sanctioned renumber: the record, the sidecar and the photograph
 * are gone and every card behind it in the box is relabelled. That is not reversible and the
 * card is not necessarily in your hand, so it says what it will do and asks a second time.
 *
 * NOT DRAWN FOR A SOLD OR RETIRED CARD — the `restores_to` lesson again: never offer a control
 * whose only behaviour is a refusal. `do_remove_card` refuses those two by their own names
 * (`card_sold`, `card_retired`) because deleting either would erase the record of a departure
 * D10 makes permanent. The claim correction stays, because a note or a set hint on a departed
 * card is still a record somebody may need to fix.
 */
function CardOps({
  row,
  onChanged,
  reshoot,
}: {
  row: Row
  onChanged: () => void

  /** The re-shoot control, rendered inside the claims editor. See where it is used. */
  reshoot?: ReactNode
}) {
  const [open, setOpen] = useState<'claims' | 'delete' | null>(null)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [removed, setRemoved] = useState<RemoveResult | null>(null)
  const [corrected, setCorrected] = useState<string | null>(null)

  const terminal = row.card.state === 'sold' || row.card.state === 'retired'
  /* The delete needs two real integers for its URL, and an unplaced record has neither — it is
     the row `do_inventory` leaves undecorated because its box or index will not coerce. A
     control that would build `/inventory/undefined/undefined/remove` is not drawn. */
  const addressable =
    typeof row.card.box === 'number' &&
    Number.isFinite(row.card.box) &&
    typeof row.card.index === 'number' &&
    Number.isFinite(row.card.index)

  const correct = async (patch: ClaimPatch) => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      await updateCard(row.card.box, row.card.index, patch)
      /* The receipt names the FIELDS, not the values: the values are already on screen in the
         facts list a moment after the re-read, and naming which claims moved is the part a
         later `git grep` of the history line needs. */
      setCorrected(Object.keys(patch).join(' · '))
      setOpen(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      /* THE CAPTURE ID IS THE AIM AND IT IS SENT EXACTLY AS THE RECORD HOLDS IT, null included.
         The operation is not idempotent — after the shift a different physical card sits at
         this index — so a replay or a press against a stale read must refuse
         (`capture_id_mismatch`) rather than delete the neighbour that slid in. A record written
         before capture ids existed carries null, and null is the honest aim for it. */
      const result = await removeCardInPlace(row.card.box, row.card.index, row.card.capture_id)
      setRemoved(result)
      setOpen(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="browse-cardops">
      {corrected === null ? null : (
        <div className="browse-receipt">
          <p className="browse-note-text">Claims written.</p>
          <p className="browse-machine">
            {row.key} · {corrected}
          </p>
        </div>
      )}

      {removed === null ? null : (
        /* THE SHIFT IS THE HEADLINE, not a footnote. `shifted > 0` means every card behind the
           deleted one has a new index and therefore a new label — the one operation in the
           product that renumbers — and a receipt that reported only "deleted" would leave the
           owner holding printed-out positions that silently stopped being true. */
        <div className="browse-receipt">
          <p className="browse-note-text">
            {removed.shifted === 0
              ? 'The capture is gone. It was the top of its box, so nothing moved.'
              : `The capture is gone and ${removed.shifted} ${
                  removed.shifted === 1 ? 'card' : 'cards'
                } behind it moved down one index — every one of those labels has changed.`}
          </p>
          <p className="browse-machine">
            {removed.deleted} · shifted {removed.shifted} · next index {removed.next_index} ·
            photo {String(removed.photo_deleted)} · sidecar {String(removed.sidecar_deleted)} ·
            review {String(removed.review_deleted)} · parked {String(removed.parked_deleted)} ·
            cache {String(removed.cache_deleted)}
          </p>
        </div>
      )}

      {open === 'claims' ? (
        <>
          {/* RE-SHOOT LIVES IN HERE NOW (owner, 2026-08-25): "remove the retake button and
              instead add it as something you can do if you click into correct claims".
              D26 put it "on the screen whose whole job is looking at one stored photo beside its
              position", and it still is — one press further in, on the panel that already exists
              for correcting what a card claims. That is the better home on its own terms: a
              re-shoot is a correction, it is the correction the other four cannot make, and the
              things it sits with are the ones an operator reaches for in the same moment.

              WHAT IT COST WHERE IT WAS. Drawn under the photograph it was a permanent control
              for an occasional act, in the column whose width is the photograph's — first a
              ~150px button, then a 24px icon after the owner called the button "a text box
              taking up so much horizontal space". Neither is free, and both were on screen for
              every card of every box.

              A LABELLED BUTTON AGAIN, not the icon. The icon existed because the photo column
              was 150px wide and a sentence did not fit; in here there is a panel's width, and a
              glyph whose meaning has to be recovered from a tooltip is worse than the words when
              the words fit. */}
          {reshoot}
          <ClaimEditor
            scope="this card"
            /* The card's OWN game drives the finish and rarity vocabularies (D22), which is the
               one place this editor can be exact — a box-wide apply has to guess because a box
               may be mixed (D21), and one card cannot be. */
            game={row.card.game}
            busy={busy}
            onApply={(patch) => void correct(patch)}
            onCancel={() => setOpen(null)}
          />
        </>
      ) : open === 'delete' ? (
        <div className="browse-danger">
          <p className="browse-note-text">
            This deletes the record, the photograph and the sidecar for this card, and{' '}
            <strong>slides every card behind it in box {row.card.box} down one index</strong> —
            so every stored position above it changes, and so does the photograph each one is
            named after. There is no undo, and unlike an undone capture this card is not
            necessarily still in your hand.
          </p>
          {/* THE SECOND HALF OF THIS SENTENCE USED TO SAY "shifting across a permanent gap
              would close a gap that means something", which was the refusal's own reason
              until D58. It is not any more: the box already closes up over a departed card
              on every screen, so there is no gap left to close. The refusal stands and is
              deliberately unchanged — relaxing it would let this route shift indices across
              records that are history and commitments, which is its own decision and not a
              consequence of this one — so what is corrected here is the explanation, not the
              rule. A refusal that recites a reason nobody can check any more teaches an
              operator to read past it. */}
          <p className="browse-note-text">
            It is refused if any card behind it has been sold, retired or listed. Those
            records are departures and commitments rather than clutter, and this route moves
            the stored index a photograph and an import file are named by &mdash; not the
            number on the screen, which already counts past a departed card.
          </p>
          <p className="browse-machine">
            aiming at capture id {row.card.capture_id ?? 'null (written before ids existed)'}
          </p>
          {trouble === null ? null : (
            <div className="browse-note">
              <p className="browse-note-text">{trouble.message}</p>
              <p className="browse-machine">{trouble.code}</p>
            </div>
          )}
          <div className="browse-cardops-actions">
            <button
              className="browse-reload browse-reload-danger"
              type="button"
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? 'Removing…' : 'Remove this card and slide the box down'}
            </button>
            <button className="browse-reload" type="button" onClick={() => setOpen(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="browse-cardops-actions">
          {/* No accent fill on either: docs/DESIGN.md reserves the solid fill for a screen with
              exactly one thing to do, and this panel offers three including the re-shoot. */}
          <button className="browse-reload" type="button" onClick={() => setOpen('claims')}>
            Correct claims
          </button>
          {/* THE ENTRY CARRIES THE WEIGHT. `browse-reload` is the page header's Reload button
              and the re-shoot's, byte for byte — so the control that deletes a record and
              SLIDES EVERY CARD BEHIND IT DOWN ONE INDEX looked exactly like the one that
              re-reads the page, with a trailing ellipsis as the only difference. The ink
              border is the one step of emphasis this palette allows and it was being spent
              only on the confirm inside the panel, where attention already is. */}
          {terminal || !addressable ? null : (
            <button
              className="browse-reload browse-reload-danger"
              type="button"
              onClick={() => setOpen('delete')}
            >
              Remove this card…
            </button>
          )}
        </div>
      )}

      {open === 'delete' || trouble === null ? null : (
        <div className="browse-note">
          <p className="browse-note-text">{trouble.message}</p>
          <p className="browse-machine">{trouble.code}</p>
        </div>
      )}

      {!terminal ? null : (
        <p className="browse-machine">
          state {row.card.state} — this card has left inventory, so it cannot be removed from
          its box: D10 and D26 make that gap permanent on purpose.
        </p>
      )}
    </div>
  )
}
