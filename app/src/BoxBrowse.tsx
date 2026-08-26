import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'
import { isEditableTarget } from './keys'
import type {
  BoxRecord,
  InventoryCard,
  QueueEntryWire,
  QueueSnapshot,
  RemoveResult,
} from './types'
import type { Failure } from './server'
import {
  describeFailure,
  positionLabel,
  placeSentence,
  getBoxes,
  getQueues,
  getInventory,
  photoUrl,
  removeCardInPlace,
  reshootPhoto,
  updateCard,
  newCaptureId,
} from './server'
import { BoxIdentity, BoxOps, ClaimEditor, RegisterBox, type ClaimPatch } from './BoxOps'
import { reasonLabel } from './reasons'
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
 * 25-cards-per-divider constant into TypeScript, which is one divider size living in two
 * languages with nothing keeping them in step — and of the two answers, the one on screen is
 * the one a person walks to a box with.
 *
 * What stayed here is the fallback at the call sites below, which is this screen's decision
 * rather than the rule's: a row with no label shows its store key with `no label` in front of
 * it. Recomputing the label locally would trade a visible gap for an invisible disagreement,
 * and only one of those sends someone to the wrong slot.
 */

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and React,
 * and shown verbatim in the one case where a row carries no label — never parsed into a
 * position: a store key and a physical location are two different facts that agree for the
 * first 25 cards in a box and diverge from card 26 on, where `3/26` is Section 2, Card 1. */
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
function shelvesOf(rows: Row[]): Shelf[] {
  const out: Shelf[] = []
  let pooled = false
  let unplaced = false
  for (const row of rows) {
    const shelf = shelfOf(row)
    if (shelf === 'pooled') pooled = true
    else if (shelf === 'unplaced') unplaced = true
    else if (!out.includes(shelf)) out.push(shelf)
  }
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
  const label = positionLabel(row.card)
  if (label !== null) return label
  return isPooled(row.card) ? pooledText(row.card, row.key) : `no label · ${row.key}`
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

  /** WHAT A RUN WOULD BE SCOPED TO: the box being walked, and the ticked cards inside it.
   *
   *  The third thing this component reports upwards, and it exists for the same reason the
   *  other two do — the walk owns the state and the screen above owns the write. `indices` is
   *  the same `pickedIndices` a bulk claim would reach, so a run and a claim correction can
   *  never disagree about what "the selection" means; `box` is null on a pooled or unplaced
   *  shelf, which has no box to identify. */
  onScope?: (scope: { box: number | null; indices: readonly number[] }) => void
}


/* `describeFailure` and `Failure` LIVED HERE and moved to server.ts on 2026-08-13, beside
 * the `ServerError` they destructure. This file's copy was the original and the argument in
 * its docstring travelled with it whole — including the reason it does not offer `make
 * server`, which this screen learned by getting it wrong first. Two later screens had copied
 * it byte for byte, and both of those comments named server.ts as the destination; the third
 * copy is what made the move due. */

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

function detailsOf(card: InventoryCard): Detail[] {
  return [
    { label: 'Card', value: card.name ?? 'not identified yet', mono: card.name === null },
    { label: 'Number', value: collectorNumber(card), mono: true },
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

/** How long an entry has been waiting, in the queue's own terms. */
function waitingFor(firstSeen: string): string {
  const at = Date.parse(firstSeen)
  if (Number.isNaN(at)) return 'unknown age'
  const days = Math.floor((Date.now() - at) / 86400000)
  if (days >= 1) return `${days} day${days === 1 ? '' : 's'}`
  const hours = Math.floor((Date.now() - at) / 3600000)
  return hours >= 1 ? `${hours} hour${hours === 1 ? '' : 's'}` : 'today'
}

function collectorNumber(card: InventoryCard): string {
  if (card.number === null) return 'none'
  return card.printed_total === null ? card.number : `${card.number}/${card.printed_total}`
}

export function BoxBrowse({
  head,
  detail,
  boxPanel,
  onSelect,
  onBoxes,
  onScope,
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
  /* The key a box-chip jump wants scrolled to the TOP of the scroller, or null for every
   * ordinary selection change. One-shot; the scroll effect consumes it. `block: 'nearest'`
   * is right for a step and wrong for a jump — after two hundred rows it parks the landing
   * at the bottom edge, which shows the END of the box before the one just asked for. */
  const jumpRef = useRef<string | null>(null)

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

  /* The shelves the query still reaches, and then the one shelf being walked. TWO STAGES AND
   * NOT ONE, because they answer different questions: the strip has to offer every shelf the
   * query matches (or a match in another box would be invisible with nothing saying so), and
   * the list has to show one shelf's worth (or the header above it would name a box the rows
   * do not all belong to). `visible` stays the name every control below already walks. */
  const shelves = useMemo(() => shelvesOf(inQuery), [inQuery])

  const visible = useMemo(() => {
    if (shelf === null) return NO_ROWS
    return inQuery.filter((row) => shelfOf(row) === shelf)
  }, [inQuery, shelf])

  const sections = useMemo(() => sectionsOf(visible), [visible])

  /* IS THE WALK BELOW ACTUALLY A SET OF MATCHES? `searching` alone does not answer that and
   * using it as though it did is a real defect rather than a nicety: it goes true on the first
   * keystroke, while the debounce and the request are still out and `inQuery` is still every
   * row in the box. The search-expands-its-matches effect keys on THIS instead, so box 2's 544
   * rows are never thrown open for the length of a debounce and then mostly thrown away again.
   *
   * A FAILED search reads false here, which is the same answer the walk itself gives: the rows
   * stay unfiltered under the failure panel, so there is nothing match-shaped to expand. */
  const filtered = searching && matched !== null

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
    if (visible.length === 0) return

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
  }, [visible])

  /* Keep the selected row where it can be seen. The failure this prevents is specific, and it
   * is the one that makes a keyboard list feel broken: the detail panel updates, the marked
   * row is three screens up inside its own scroller, and the only thing that visibly moved is
   * on the other side of the page.
   *
   * `block: 'nearest'` so it scrolls only when it has to, which is what keeps it from
   * fighting the mouse — a click on a row that was already visible moves nothing. A
   * box-chip jump is the argued exception and lands `block: 'start'`, once, via jumpRef
   * above: a jump is FOR seeing what follows the landing, and 'nearest' shows what
   * precedes it. The rows' scroll-margin in the stylesheet is what keeps 'start' from
   * parking the row under its own sticky section header.
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
      current.scrollIntoView({ block: jumpRef.current === selected ? 'start' : 'nearest' })
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
    listRef.current?.focus()
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

  /* THE SELECTION, REPORTED UPWARDS. `Inventory.tsx` draws the copies of whatever card the walk
   * is pointing at, and it cannot know which one that is without being told. The memo above is
   * what keeps this from looping: a stable identity means this fires on a real change and not
   * on every render. */
  useEffect(() => {
    onSelect?.(selectedRow)
  }, [selectedRow, onSelect])

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
  const selectedSentence = selectedRow === null ? null : placeSentence(selectedRow.card.place)

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
          <span className="browse-count">
            {rows.length} {rows.length === 1 ? 'card' : 'cards'}
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
        {rows === null || rows.length < 2 ? null : (
          <span className="browse-keys">
            {STEPS.map((step) => (
              <kbd className="browse-key" key={step.key}>
                {step.label}
              </kbd>
            ))}
            step one card
          </span>
        )}
      </div>

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
          <div className="browse-map">
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

            {/* Register a box before a card goes into it — D20's control, in the column that
                lists every box it would join, at the bottom of it.

                UNDER THE WALK RATHER THAN OVER IT, and the reason is measured. This column is
                sticky and its height is the viewport, so everything above the list is height
                the list does not get: drawn between the strip and the walk this control cost
                44px of rows, permanently, to offer an action taken a handful of times a year.
                Below, it costs nothing until the list is short enough to leave room. It is
                still beside the strip in the sense D20's own argument needs — every existing
                box is listed in the same column, which is what makes a mistyped number
                visible. */}
            {/* THE BOX'S OWN OPERATIONS, at the bottom of the box's own column and directly
                above the control that creates one. Rename, re-divide, seal, set claims over the
                ticked cards, release a listing hold, delete the box — every one of them acts on
                a BOX, which is what makes this the right neighbour for `RegisterBox` and the
                wrong one for a card panel.

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

            <RegisterBox onChanged={() => setReloads((n) => n + 1)} />
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
                      <p className="browse-position">{selectedLabel}</p>
                      {/* D30's sentence, quiet, directly under the label it makes countable:
                          "between Mantine and Thievul · 2 slots in this section are empty".
                          `Card 17` is the seventeenth SLOT, and once the section has permanent
                          gaps that is no longer the seventeenth card a hand can count to —
                          the neighbours restore the count and the gap tally says why it came
                          out short. Composed by `server.ts:placeSentence`, the one composer,
                          which answers null — and this renders nothing, never a guess — for a
                          pooled card, an older server, or a decoration the server degraded. */}
                      {selectedSentence === null ? null : (
                        <p className="browse-between">{selectedSentence}</p>
                      )}
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

                {/* WHAT THIS CARD IS, THEN WHAT CAN BE DONE TO IT — one column beside the
                    photograph. `CardOps` is here rather than below the band because the band's
                    two sides are now different heights, and the ~70px it fills is the air that
                    would otherwise sit under the facts. Its writes are card-level, like every
                    row above it, so the column reads as one subject. */}
                <div className="browse-about">
                  <dl className="browse-facts">
                    {detailsOf(selectedRow.card).map((fact) => (
                      <div className="browse-fact" key={fact.label}>
                        <dt>{fact.label}</dt>
                        <dd className={fact.mono ? 'is-util' : undefined}>{fact.value}</dd>
                      </div>
                    ))}
                  </dl>

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

                      OUTSIDE THE `<dl>` ON PURPOSE. `detailsOf` is a pure function of
                      `InventoryCard` and a queue entry is per-POSITION; a `dt`/`dd` grid row
                      cannot hold the two-line reason DESIGN.md's reason-code rule requires; and
                      `app/tests/inventory.spec.ts` measures `.browse-facts` specifically, so
                      keeping this out of that list leaves D38's assertion honest.

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

          {/* THE THIRD COLUMN IS THE RUNS, and it used to be the box and the runs. D31 put box
              operations "on the box header inside the browse, beside the box they operate on",
              and on 2026-08-25 the owner pointed out that the box's header is now the left
              column: the strip names it, the walk is its cards, and this panel was re-listing
              those same sections as inert text a thousand pixels away. So the box went there and
              the runs came up into the space.

              WHAT THE PAIR BOUGHT IS STILL BOUGHT. D33 removed two disclosures on the grounds
              that a `1fr 1fr` row cost one panel's height rather than two; a column beside the
              card cost the card nothing at all; and this costs it nothing while giving the box
              back to the box. Nothing folds, which is the half D33 actually settled.

              THE `selectedRow` GUARD CANNOT REACH IN HERE, and that is worth having structurally
              rather than by care. The old comment on `{boxPanel}` had to say in prose that it sat
              outside the guard deliberately — a control about the SHELF that vanished when no
              card was selected would be one the operator found by accident. It is in a different
              top-level column from the guard, so no later edit can slide it inside without
              moving it between columns first. */}
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

            {/* THE RUN PANEL — under the box header, and about the same box. */}
            {boxPanel}
          </div>

          {/* THE COPIES OF THIS CARD, ACROSS COLUMNS 2 AND 3 — D7's SKU -> positions map, handed
              down by the screen that owns the write. This is where the merged Find mode went:
              you search, the walk narrows, you pick one, and every other copy is right here with
              its own position and its own controls. The node belongs to `Inventory.tsx` because
              the receipts, the undo windows and the two confirm panels are one flow with twenty
              pieces of state, and splitting a flow across two components is how half of it drifts.

              IT GETS THE PAGE'S SPARE MEASURE RATHER THAN THE CARD COLUMN'S, and the measurement
              is the argument. In the middle column it was 976px of a 1450px page on the default
              card and 1713px of 2187px on an eleven-copy one — while the right column ended at
              y=451 and 778px of viewport sat empty beside a 630px stack of rows. Rebuilt wide
              and measured: the row goes 144px to 82px and eleven copies go 1598px to 902px, a
              43% cut with nothing removed. That is `CardLocations.css`'s own recorded complaint
              answered rather than worked around — that file records these rows being re-cut from
              a grid to a wrapping flex because a ~460px column shredded the position label.

              RENDERED ONCE, WHICH IS THE SECOND THING THIS BUYS. `detail` used to draw at two
              mutually exclusive sites so that a receipt whose twenty-second undo was still
              running would survive a query matching nothing. Out here it is not inside
              `selectedRow`'s guard at all, so that invariant stops being a prose promise and
              becomes structural — and the duplication risk `app/tests/inventory.spec.ts` names
              in its own comment stops existing.

              AFTER `.browse-boxrun` IN THE DOM, NOT BEFORE. This file rules twice that a reorder
              happens in the DOM rather than with `order`, so the tab ring and a screen reader
              walk what the eye walks: card, runs, copies is reading order at both breakpoints. */}
          <div className="browse-under">{detail}</div>
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
  return row.card.photo === null || absent
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

/* Two ways a photo can be missing, and they are different facts, so they get different
 * sentences rather than one broken image.
 *
 *   `photo` is null   — no photo was ever stored. `emit` can record a card that was never
 *                       photographed, and `store/master.py` keeps the field null for it.
 *   the route 404s    — the record claims a photo and the file is not there. That is a
 *                       store that has lost something, and it is worth saying so plainly.
 *
 * Both print the URL that was asked for, so the next move is a curl rather than a guess.
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
  const base = photoUrl(row.card.box, row.card.index)
  const src = nonce === null ? base : `${base}?reshot=${nonce}`

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
         photograph's broken state attached to the new one. */
      key={`${row.key}:${src}`}
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
            so every label above it changes. There is no undo, and unlike an undone capture this
            card is not necessarily still in your hand.
          </p>
          <p className="browse-note-text">
            It is refused if any card behind it has been sold, retired or listed: shifting
            across a permanent gap would close a gap that means something, and a listed
            card&rsquo;s position is already written into a file somebody will read.
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
