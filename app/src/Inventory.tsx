import { useCallback, useEffect, useState } from 'react'
/* `Inventory` is aliased because this file's own component is called that. The alias names the
 * thing rather than dodging the clash — the type is one `GET /inventory` response, and the
 * component is a screen built out of many readings of it. */
import type {
  BoxSummary,
  InventoryCard,
  Inventory as InventoryResponse,
  RetireReason,
  RetireResult,
  SaleResult,
  SearchCopy,
  SectionDetail,
} from './types'
import type { Failure } from './server'
import {
  ServerError,
  describeFailure,
  positionLabel,
  getBoxes,
  getInventory,
  markSold,
  photoUrl,
  retireCard,
  undoRetire,
  undoSale,
} from './server'
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { PullConfirm } from './PullConfirm'
import { SearchField } from './SearchField'
import { useSearch } from './useSearch'
import './Inventory.css'

/* The inventory view — build-order step 7b. D7's SKU -> positions map, made visible.
 *
 * D7 collapses copies to ONE import row with a copy count and keeps EVERY copy as its own
 * position with its own photo, "because that is what makes an order pull addressable: the
 * app maps SKU -> all positions holding it, and the pull marks one of them sold". That
 * sentence names an app that did not exist when it was written. This is it: one row per
 * SKU carrying the count, expanding to the individual positions holding it.
 *
 * THIS SCREEN WRITES NOW, AND THE PARAGRAPH THAT SAID IT NEVER WOULD IS KEPT BELOW RATHER
 * THAN DELETED. Overturning an argument by erasing it leaves the next session with a screen
 * that does the thing and no record that anybody thought about it — so the objection stands,
 * quoted, and each half is answered where it was made.
 *
 *   WHAT IT SAID. "`POST /inventory/<box>/<index>/sold` shipped in the same commit as this
 *   file, and `server.ts:markSold` calls it — from Fulfillment.tsx, which is where D5 puts a
 *   pull. His view earns that write by carrying the guards docs/DESIGN.md asserts on it and
 *   only on it: photo-confirm before each pull, undo on every mark-sold with a ten-second
 *   window, no destructive action reachable at all. A sold button on a dense owner-side table
 *   would be the same irreversible-looking write with neither guard, and a second place to
 *   perform one action — which is how two devices end up disagreeing about which copy went."
 *
 *   OBJECTION 1, THE MISSING GUARDS — ANSWERED BY BRINGING THEM. The guards were never
 *   properties of the Fulfillment view; they are properties of a screen that records a sale,
 *   and docs/DESIGN.md asserts them THERE because that is the view its constraints table
 *   governs. Nothing in D5 says the owner may have the write without them. So this screen
 *   carries both: `Confirm` below is the photo-confirm — the sale goes through a panel
 *   showing the copy's own stored photo (D6) at its position before anything is written —
 *   and every recorded sale leaves a receipt with an undo window, the shape Fulfillment.tsx
 *   already ships. `markSold` answers `restores_to` precisely so a caller knows whether an
 *   undo can be offered at all, and this screen reads it rather than offering one blind.
 *
 *   OBJECTION 2, TWO PLACES FOR ONE ACTION — ANSWERED BY THE SERVER, WHICH ALREADY REFUSES
 *   THE RACE. The failure feared was two devices disagreeing about which copy went. They
 *   cannot: the second device's sale comes back `already_sold`, and Fulfillment.tsx has
 *   already worked out what that means — somebody else sold that copy, so it is a receipt
 *   for a card leaving your list rather than an error, and no undo may be offered because
 *   the undo would reverse the OTHER device's real sale. This screen reads the same code the
 *   same way, for the same reason, in `doSell` below.
 *
 *   WHY THE WRITE IS WORTH HAVING AT ALL. The flow it completes is the one D7 exists for: a
 *   card sells, somebody types its name, and every physical copy answers with where it is.
 *   Ending that flow at a lookup and sending the owner to the Fulfiller's screen to finish it
 *   is the other half of what the paragraph above rejected — "making these rows link into his
 *   view" — and it is rejected still. What is left, once both are declined, is finishing the
 *   job here.
 *
 * STILL TRUE, AND NOT WHAT THIS OVERTURNS: the Fulfillment view keeps its own constraints
 * table and this screen is not measured against it. The floors below are the owner's.
 *
 * OWNER-SIDE, so this is the dense end of docs/DESIGN.md's one system, two densities, and
 * the Fulfillment floors do not bind. It speaks the pipeline's vocabulary — `sku`, `pushed`,
 * `staged` — which the Fulfillment banned-word list forbids outright; borrowing his floors
 * here would make it look like his screen and set the expectation that it is safe for him
 * to read, which it is not (D5).
 *
 * ONE GET, GROUPED IN THE BROWSER, KEPT NOWHERE. `GET /inventory` answers with the whole
 * card map and the grouping below is a view of it — not a second store. There is no
 * module-level cache and no state above this component on purpose: leaving the screen
 * throws the response away and coming back re-reads it. D13 has exactly one place inventory
 * lives, and the failure a browser-side copy produces is the same one spec 5.5 rejected
 * queue-and-continue over — two answers to "where is this card", one of them stale and
 * neither of them labelled.
 *
 * A SECOND GET NOW, AND THE PARAGRAPH ABOVE STILL HOLDS — because what it forbids is a second
 * copy of the inventory, and a divider layout is not a card. `GET /boxes` is read once beside
 * the read above for one reason: the position bar on every copy row draws the box's real
 * dividers only if it is handed them. A `Place` states this card's own section and cannot say
 * where the OTHER dividers in its box are, and deriving them from one section's width is the
 * arithmetic types.ts forbids on `Place` and D10 makes wrong — dividers go where the operator
 * physically put them, so a uniform width is an assumption about a box nobody made. So the
 * layouts come off the one route that renders them, `sections_detail`, and are held here in
 * component state exactly as the groups are: thrown away on the way out of the screen,
 * re-read on the way back in.
 *
 * AND IT IS DECORATION, SO IT IS ALLOWED TO FAIL SILENTLY AND COMPLETELY. Nothing waits for
 * it, nothing reports it, and no sale is ever blocked on it. Without it every bar draws the
 * coarser three-run picture `PositionBar:spansOf` documents — the part of the box before this
 * card's section, the section, the part after — which is true and merely less detailed. A
 * failure panel would trade a working lookup for a message about an ornament, and the panels
 * on this screen belong to the two reads somebody actually opened it for.
 *
 * TWO NUMBERS ON THIS SCREEN, AND THEY ARE NOT IN THE SAME UNIT. That was true from the day
 * D7 was amended (2026-08-23) and this file did not say so for the ten days after it, which
 * is why it is the first thing in this header now.
 *
 *   a card's state    `captured`, `identified`, `sold` — or `retired`, D26's way out of
 *                     inventory without a sale. One physical card at one position.
 *                     Counted by `tally`.
 *   a SKU's listing   `pushed`, `staged` and `live`, as QUANTITIES on
 *                     `store/master.py:Listing`. Which physical copies back them is
 *                     deliberately not recorded, because copies are fungible — the owner's
 *                     ruling that marking three of fifteen live means any three. Read by
 *                     `listingsOf`.
 *
 * The three listing words used to be card states and were tallied as such by this file. They
 * stopped being states and the tally went on offering them: three counts that could only ever
 * read zero, drawn from a field that no longer holds them, beside no sign that the numbers
 * had moved. Nothing was wrong on screen — the rows simply stopped mentioning listings at
 * all. `STATE_ORDER` and `LISTED_ORDER` below are the two halves of the fix.
 *
 * TWO THINGS THIS SCREEN STILL DELIBERATELY DOES NOT COMPUTE, because the numbers they need
 * are not on this wire and approximating them is worse than omitting them:
 *
 *   the live cap      `pipeline/join.py:LIVE_QUANTITY_CAP` is 4 and D7 calls it
 *                     configurable. Writing `2 of 4 live` here would put a configurable
 *                     Python constant into TypeScript with nothing keeping the two in step
 *                     — the mistake PullPreview.tsx records having made with D10's divider
 *                     size and undone. `GET /search` HAS SINCE STARTED REPORTING IT
 *                     (`types.ts:SearchGroup.cap`), which is what this entry named as the
 *                     thing that would settle it; `GET /inventory` does not, and this screen
 *                     reads that one. Settled here the day `Listing` carries it, or the day
 *                     this screen has a reason to ask the search route instead.
 *   the price         D8 routes every price through the export and the inventory record
 *                     carries none, so there is no money on this screen at all. Settled by
 *                     a price reaching the wire.
 *
 * The refill maths was the third entry and it is not one any more. It read that
 * `Add to Quantity = min(cap - live, backstock)` takes `live` from the export's
 * `Total Quantity` while "the store's own `live` state is the nearest thing and it is what
 * the tally counts" — half of which was made false by the amendment and the other half by
 * where the number now comes from. `Listing.live` is the store's estimate of exactly that
 * quantity, drawn as itself in the listing cluster, so there is no approximation left to
 * decline. D7 is explicit that it is an estimate a join corrects and never a second source
 * of truth, and this screen shows it under a caption that says which side it came from.
 */

/** One physical card at one position, exactly as `GET /inventory` sent it. `key` is the
 *  store's own `"<box>/<index>"` — identity for React, and the string a `curl /inventory`
 *  is grepped with. Never parsed into a position: a store key and a physical location agree
 *  for the first 25 cards in a box and diverge from card 26 on. */
type Copy = { key: string; card: InventoryCard }

/** One card state and how many of a group's copies are in it. A count of PHYSICAL CARDS. */
type Tally = { state: string; count: number }

/** One SKU's three listing quantities — `store/master.py:Listing`, as `GET /inventory` sends
 *  it under `listings`.
 *
 *  A COUNT OF COPIES AT A TCGPLAYER STAGE, WHICH IS NOT THE SAME UNIT AS `Tally` ABOVE even
 *  though both are integers about the same group. A `Tally` counts records this app can point
 *  at a box for; these three count quantity against a SKU, and D7 says in as many words which
 *  physical copies back them is "deliberately not recorded". Two shapes rather than one so
 *  that nothing in this file can merge them by accident — they were one list until the store
 *  refactor, and merging them now would put a number on screen that names no card.
 *
 *  THIS TYPE BELONGS IN types.ts AND IS HERE BECAUSE OF FILE OWNERSHIP, NOT DESIGN. Precedent
 *  and precedent's own words: the queue types were written in ReviewQueue.tsx for exactly this
 *  reason and moved the moment both files were writable together. `types.ts:Inventory` today
 *  declares `{ version, cards }` and stops, while `store/master.py:Inventory.to_payload` has
 *  sent `boxes` and `listings` beside them since v2 — so this is a field the wire really
 *  carries and the type has not caught up with, never a field invented here. Move it, and
 *  delete `listedFor`'s cast with it. */
type Listed = { pushed: number; staged: number; live: number }

/** One SKU and every copy holding it — one row of D7's map.
 *
 *  `sku` is null for the one group that is not a SKU. Every other field is the DISTINCT set
 *  of what the copies say, in the order the copies say it, rather than one value lifted off
 *  the first copy — see `distinct` for why that matters.
 *
 *  `listed` IS NULL RATHER THAN THREE ZEROS when this SKU has no listing record, and the
 *  difference is the one this screen exists to show. Three zeros say a SKU that has been
 *  through `emit` and come back empty; null says nothing has ever written a row for it. The
 *  no-SKU group is always null, because a listing is keyed by SKU and that group has none. */
type Group = {
  sku: string | null
  copies: Copy[]
  names: string[]
  conditions: string[]
  numbers: string[]
  states: Tally[]
  listed: Listed | null
}

/* The lifecycle order the states are DISPLAYED in, and deliberately not an enumeration of
 * the enum. `store/master.py:STATES` owns that list, and types.ts already argues that an app
 * enumerating pipeline states needs editing every time one is added.
 *
 * So this is a display order with a guard: a state not named here still renders, after these
 * and in the order it was met. A new state in `store/master.py` therefore shows up unsorted
 * rather than disappearing, which is CLAUDE.md's never-silently-drop-a-card rule applied to
 * a tally instead of to a row.
 *
 * `pushed`, `staged` AND `live` WERE THE LAST THREE ENTRIES HERE AND ARE NOT STATES ANY MORE
 * (D7, amended 2026-08-23). They were never wrong to keep apart — the paragraph that stood
 * here argued that merging `staged` and `live` breaks D7's refill maths, and it still does —
 * but they were the wrong SHAPE: a stage was worn by a position, so `cli/cmd_join.py` had to
 * choose which four of seven identical copies were sellable. The owner's ruling is that
 * copies are fungible, so the three moved onto the SKU as counts, `master.STATES` is now
 * `captured | identified | sold | retired` (the last is D26's), and `check_state` refuses
 * the three listing words outright.
 *
 * THE GUARD ABOVE IS EXACTLY WHY THIS WAS SILENT. Three names that can no longer occur went
 * on being valid display order, tallied zero copies each, and rendered nothing at all — so
 * the screen looked correct while the whole listing half of it had gone dark. `LISTED_ORDER`
 * below is where those three live now, read from a different field, in a different unit, and
 * drawn as a separate cluster so the two can never be read as one number again. */
const STATE_ORDER: readonly string[] = ['captured', 'identified', 'sold', 'retired']

/* The three listing stages, in the order a SKU passes through them —
 * `store/master.py:LISTING_STAGES`, same strings, same order.
 *
 * FIXED RATHER THAN GUARDED, which is the opposite of `STATE_ORDER` above and is deliberate.
 * That one renders an unrecognised state because a card wearing one is a real card that must
 * not vanish from a count; this one reads three named fields off a record, so a fourth stage
 * added in `store/master.py` is a field this screen would not know how to fetch either way.
 * The failure is a missing column rather than a missing card, and it shows up the first time
 * anyone compares this screen against a run report. */
const LISTED_ORDER = ['pushed', 'staged', 'live'] as const

/* A record that reached the store with no state, said in a shape no state can be confused
 * with: lower case with a space, which no member of `STATES` contains. Same trick as the
 * capture screen's `no claim` and the pull preview's `no label · 3/30` — a stand-in for a
 * machine string must never be readable as one.
 *
 * The type says `state: string` and `store/master.py` defaults the field, so this should be
 * unreachable. It exists because the alternative is a copy that counts toward the group total
 * and appears in no tally, which is a card going quietly missing from a number the screen is
 * read for. */
const NO_STATE = 'no state'

/* This file's copy of `describeFailure` said "worth sharing when a third screen needs it, not
 * before". A third screen needed it in the same session, so it is in server.ts now, beside
 * the `ServerError` it destructures — which is where all three copies' comments pointed. */

/* The position label is READ off the wire and never composed here — `server.ts:positionLabel`
 * holds the rule and the argument for it, since this file and the pull preview carried
 * identical copies. What is still this screen's is the fallback at the call site: a row with
 * no label shows the store key with the words `no label` in front of it, because `3/30` bare
 * reads like a position and is not one. */

/* The collector number as the model returned it, unpadded, or null when there is none to
 * show. `pipeline/join.py:join_key` zero-fills to three digits to match the export's
 * `Number` column; doing that here would put a string on screen that nothing in the run ever
 * said. Same rule and the same shape as the pull preview's, which is the third small reader
 * of this record — a shared module is the fix if a fourth arrives. */
function collectorNumber(card: InventoryCard): string | null {
  if (card.number === null || card.number.trim() === '') return null
  return card.printed_total === null ? card.number : `${card.number}/${card.printed_total}`
}

/* Every distinct value the copies carry, in the order they carry it, blanks dropped.
 *
 * THE POINT IS THAT IT DOES NOT PICK. Two copies of one SKU that were read as `Rhyhorn` and
 * `Rhydhorn` are one identification that went wrong — a T1 recorded miss, name misread with
 * the number right — and taking the first copy's name would put the wrong one on screen half
 * the time and hide the disagreement the other half. Showing both is not a judgement about
 * which is correct, which is a thing this screen has no business making. */
function distinct(values: readonly (string | null)[]): string[] {
  const seen: string[] = []
  for (const value of values) {
    if (value === null) continue
    const trimmed = value.trim()
    if (trimmed !== '' && !seen.includes(trimmed)) seen.push(trimmed)
  }
  return seen
}

/* One stage's quantity, coerced, floored at zero — `Listing.set` and `Listing.bump` floor on
 * the store side and this is the same rule read back. Anything that is not a finite number
 * reads as zero rather than as `NaN` on screen: this comes off disk through a route that
 * coerces nothing, exactly like `InventoryCard.metadata_finish`, and a stage the store has
 * never written is absent rather than null. */
function quantity(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 0
}

/* Every SKU's listing quantities, out of the `listings` map `GET /inventory` answers with.
 *
 * THE CAST IS THE WHOLE OF THIS FUNCTION AND IT IS NOT A SHORTCUT. `types.ts:Inventory`
 * declares `{ version, cards }`; `store/master.py:Inventory.to_payload` has answered with
 * `boxes` and `listings` beside them since schema v2. The field is really on the wire — the
 * type is behind it — and that file belongs to another session today. Intersecting rather
 * than casting through `unknown` so the assertion stays legal to the compiler and legible to
 * a reader: this is `Inventory` PLUS a key the type has not declared, not a claim that some
 * unrelated shape is an `Inventory`.
 *
 * EVERY VALUE PAST THE CAST IS TREATED AS `unknown` AND COERCED, which is what makes the cast
 * safe rather than merely quiet. A cast the compiler is told to believe and the code then
 * trusts is how a missing field becomes `undefined` rendered as a quantity. Nothing here
 * believes anything: a missing map, a map of the wrong shape, and a record with no numbers on
 * it all produce no listing rather than a wrong one.
 *
 * DELETE THIS THE DAY `types.ts:Inventory` GAINS `listings`, and read the field directly. */
function listingsOf(inventory: InventoryResponse): Map<string, Listed> {
  const out = new Map<string, Listed>()
  const carried = (inventory as InventoryResponse & { listings?: unknown }).listings
  if (carried === null || typeof carried !== 'object') return out

  for (const [sku, record] of Object.entries(carried as Record<string, unknown>)) {
    if (record === null || typeof record !== 'object') continue
    const held = record as Record<string, unknown>
    out.set(sku, {
      pushed: quantity(held['pushed']),
      staged: quantity(held['staged']),
      live: quantity(held['live']),
    })
  }
  return out
}

/** No box layouts, as one shared empty map.
 *
 *  A CONSTANT RATHER THAN `useState(new Map())`, so that the "we have not been told" case has
 *  exactly one identity and re-rendering cannot mint a second empty map for React to compare
 *  against. It is also the reason no null is needed here: for every other read on this screen
 *  "not answered yet" and "answered with nothing" are different facts and the header insists
 *  on the difference, but a bar draws the same honest three-run picture either way — so a
 *  distinction nothing on screen can act on would be a state to explain and never to use. */
const NO_LAYOUTS: ReadonlyMap<number, readonly SectionDetail[]> = new Map()

/* Each box's divider layout, keyed by box number, out of one `GET /boxes`.
 *
 * THE KEY IS THE POINT OF THE FUNCTION. `sections_detail` is `pipeline/join.py`'s own
 * rendering of one box's layout, and D10 as amended 2026-08-23 puts the dividers wherever the
 * operator physically put them — box 1 declares none and is drawn by the 25-rule, box 95
 * declares `[1, 24, 74, 84]`, and neither tells you anything about the other. A search group
 * is a SKU and not a box (D7 keeps every copy at its own position), so one result can hold
 * copies in three boxes; flattening this to a single list would hand one box's dividers to
 * another box's card. Keyed by `box`, that mistake has nowhere to happen.
 *
 * GUARDED AT THE EDGES AND NOWHERE ELSE, which is a smaller job than `listingsOf` above and
 * deliberately so. `server.ts:request` casts rather than validates, so the array and the box
 * number are checked here — an older capture server can answer a shape this type says is
 * impossible. Every field INSIDE a `SectionDetail` is left alone on purpose: `spansOf` reads
 * them one at a time and clamps each into the box, and a second copy of that reading here
 * would be a second place to keep the same rule. A box that sends no detail is skipped rather
 * than stored empty, so `Map.get` answers undefined and the bar takes the fallback path.
 *
 * There is no coercion of `end` either, for the same reason: `spansOf` already treats a
 * section whose end did not arrive as one running to the end of the box, which is what an
 * open last section is. */
function layoutsOf(summary: BoxSummary): ReadonlyMap<number, readonly SectionDetail[]> {
  const out = new Map<number, readonly SectionDetail[]>()
  const carried: unknown = summary.boxes
  if (!Array.isArray(carried)) return out

  for (const record of carried as BoxSummary['boxes']) {
    if (record === null || typeof record !== 'object') continue
    if (typeof record.box !== 'number' || !Number.isFinite(record.box)) continue
    const detail: unknown = record.sections_detail
    if (!Array.isArray(detail) || detail.length === 0) continue
    out.set(record.box, detail as readonly SectionDetail[])
  }
  return out
}

function tally(copies: readonly Copy[]): Tally[] {
  const counts = new Map<string, number>()
  for (const copy of copies) {
    const state =
      typeof copy.card.state === 'string' && copy.card.state.trim() !== ''
        ? copy.card.state
        : NO_STATE
    counts.set(state, (counts.get(state) ?? 0) + 1)
  }
  const known = STATE_ORDER.filter((state) => counts.has(state))
  const rest = [...counts.keys()].filter((state) => !STATE_ORDER.includes(state))
  return [...known, ...rest].map((state) => ({ state, count: counts.get(state) ?? 0 }))
}

/* The whole card map, grouped into D7's rows.
 *
 * BOX-WALK ORDER THROUGHOUT — box, then index. Inside a group it is the order
 * `store/master.py:positions_for_sku` returns, which is the order a pull walks the boxes in;
 * between groups it orders by each group's earliest copy, because a `Map` keeps insertion
 * order and the copies are sorted before they are bucketed.
 *
 * Rejected for the group order: copy count descending, which puts D7's multi-copy cases —
 * the ones this screen exists for — at the top. It loses because the order would reshuffle
 * every time a copy sells, and a row you looked at yesterday would be somewhere else today;
 * the count is on every row anyway. ASSUMPTION, and the doc does not settle it: docs/DESIGN.md
 * argues a sort order for the review queue only, where price decides. Watching the owner look
 * something up here settles it.
 *
 * The arithmetic matches PullPreview.tsx's. A record whose box will not coerce to a number
 * sorts wherever `Object.entries` put it rather than being dropped — it is the same record
 * `do_inventory` leaves without a label and `GET /status` reports, and it stays on screen. */
function groupBySku(
  cards: Record<string, InventoryCard>,
  listings: Map<string, Listed>,
): Group[] {
  const copies: Copy[] = Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)

  /* Keyed by `string | null` with no sentinel string, because a sentinel would have to be a
   * value no TCGplayer Id can take and nothing here can promise that. `null` is a key a Map
   * holds natively. */
  const buckets = new Map<string | null, Copy[]>()
  for (const copy of copies) {
    // An empty string is not a SKU. Treated as none rather than as a group of its own, which
    // would be a row nothing can ever be listed under.
    const raw = copy.card.sku
    const sku = raw === null || raw.trim() === '' ? null : raw.trim()
    const held = buckets.get(sku)
    if (held === undefined) buckets.set(sku, [copy])
    else held.push(copy)
  }

  const groups = [...buckets.entries()].map(([sku, held]) => ({
    sku,
    copies: held,
    names: distinct(held.map((copy) => copy.card.name)),
    conditions: distinct(held.map((copy) => copy.card.condition)),
    numbers: distinct(held.map((copy) => collectorNumber(copy.card))),
    states: tally(held),
    /* Looked up, never derived. The copies cannot tell you what is listed any more — that is
     * the whole of D7's amendment — so a group whose SKU has no record answers null, and
     * `null ?? undefined` is not reached because `Map.get` already returns undefined. */
    listed: sku === null ? null : (listings.get(sku) ?? null),
  }))

  // The no-SKU group last, wherever its earliest copy landed. It is the one group that is not
  // a row of D7's map, and reading down a list of SKUs should not run through it.
  return [...groups.filter((g) => g.sku !== null), ...groups.filter((g) => g.sku === null)]
}

/** `1 copy`, `4 copies`. */
function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/* The date a copy entered its current state, without the time.
 *
 * A day is the granularity anything here is acted on — `store/master.py` measures a stale
 * staged import in days, and D7's refill is a decision made per import rather than per
 * minute. The full stamp is in `inventory.json` for anyone who needs the seconds.
 *
 * A stamp that does not split is shown whole rather than blanked: it is what the store
 * actually holds, and the screen's job is to say so. */
function sinceDay(stamp: string | null): string {
  if (stamp === null || stamp.trim() === '') return 'unknown'
  const day = stamp.split('T')[0]
  return day === undefined || day === '' ? stamp : day
}

// ------------------------------------------------------------------- search, and the sale

/* NO STATE CONSTANT LIVES IN THIS HALF OF THE FILE, and that is worth one line rather than
 * being noticed as an absence. Which copies may be sold is `CardLocations`'s test and not this
 * screen's: D7's 2026-08-23 amendment moved the three listing stages off the card and onto the
 * SKU, so every unsold copy is sellable and `sold` is the only word there is to compare
 * against. A second copy of that comparison here would be a second place to keep it in step
 * with the decision. What this file owns is the write, the guards around it, and the two
 * refusal codes below.
 */

/* THE TWO REFUSAL CODES THIS SCREEN BRANCHES ON, and the rulings are Fulfillment.tsx's,
 * adopted here rather than re-derived. That file paid for them with a data-integrity bug and
 * wrote up why; a second reading of the same two codes on a second screen is exactly the drift
 * a shared vocabulary exists to stop.
 *
 * `already_sold` ON A SALE IS NOT THIS DEVICE'S SALE. Somebody else sold that copy (D13: two
 * devices, one store). Answered as success it would print a receipt and offer an Undo, and
 * that Undo would reverse the other device's real sale — putting a card back on TCGplayer
 * that a buyer has paid for. Drawn as a receipt with NO undo and a sentence naming what
 * happened, because from where the owner sits a card did leave the boxes and he did not do it.
 *
 * `not_sold` ON A REVERSAL IS SUCCESS. The card is not sold, which is what the tap asked for.
 * Reported as a failure it is a dead end: pressing Undo again answers identically forever.
 *
 * The CODES and never the messages. Codes are a stable vocabulary worth branching on.
 *
 * THE RETIREMENT PAIR BELOW APPLIES THE SAME TWO RULINGS TO THE SIBLING WRITE (D26), rather
 * than deriving new ones. `already_retired` on a retirement is the other device's
 * retirement: a receipt with no undo, because the undo would reverse a departure this
 * device never recorded. `not_retired` on a reversal is success — the card is not retired,
 * which is what the tap asked for. The CROSS-refusals (`card_retired` on a sale,
 * `already_sold` on a retirement) are deliberately not branched on: each is a real refusal
 * whose server message names the other route's undo as the way through, and the trouble
 * panel shows it verbatim — which is this screen's ordinary treatment of a refusal it did
 * not expect. */
const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const ALREADY_RETIRED = 'already_retired'
const NOT_RETIRED = 'not_retired'

/* HOW LONG THE UNDO STAYS. Twenty seconds, which is Fulfillment.tsx's number and not a second
 * opinion about the same question.
 *
 * docs/DESIGN.md's floor is ">= 10s" and it is written as a Fulfillment row, so nothing binds
 * this screen to any particular length — which is precisely the argument for not inventing
 * one. Two undo windows of different lengths in one product is a thing to learn for no gain,
 * and the owner is not the person the shorter number would be for. If the length is ever
 * measured it should move in both files together.
 *
 * WHAT WOULD SETTLE IT: watching a sale get taken back. Nothing in this repo has yet. */
const UNDO_WINDOW_MS = 20_000

/** The server's code for a thrown thing, or `''` for anything that is not a refusal — a dead
 *  network, a body that did not parse, a bug in this app. Empty rather than null so every
 *  comparison is a plain `===` against a code that cannot match. */
function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/** Whether the sale just recorded can be taken back, out of the server's own answer.
 *
 *  ABSENT IS READ AS NULL and the direction is the safe one — the same guard Fulfillment.tsx
 *  keeps, for the same reason. `server.ts` casts rather than validates, so a capture server
 *  old enough to answer this route without the field hands back `undefined` under a type that
 *  says `string | null`. Suppressing an undo that would have worked costs a question;
 *  offering one that cannot work is the defect the field was added to remove. */
function canTakeBack(result: SaleResult | RetireResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

/** One write that has just been recorded — a sale, or since D26 a retirement — and what can
 *  still be done about it.
 *
 *  A LIST OF THESE AND NOT ONE SLOT. Fulfillment.tsx shipped the single-slot version and
 *  found what it costs: the second sale in a row silently discards the first card's undo and
 *  re-arms the clock for the new one, so "undo on every mark-sold" quietly becomes "on the
 *  most recent". An owner working a search result has exactly that shape — several copies of
 *  one card, sold one after another — so each sale carries its own deadline.
 *
 *  IT HOLDS ITS OWN COPY OF THE POSITION rather than a pointer into the search results,
 *  because the results are allowed to move underneath it. Typing a new query replaces them,
 *  and the undo window has to outlive that: a receipt that vanished when the owner searched
 *  for the next card would be a ten-second promise kept for two.
 *
 *  ONE TYPE FOR BOTH WRITES, because a receipt is a receipt: the same panel, the same clock,
 *  the same rules about when Undo may be drawn. `kind` exists for exactly one branch — which
 *  route the Undo calls — and for nothing the render reads. */
type Receipt = {
  /** Which write this reverses: the sale route, or the retirement's. Read by `doUndo` alone. */
  kind: 'sale' | 'retirement'

  /** `SearchCopy.key`, the store's own `"<box>/<index>"`. Identity for React and for the
   *  optimistic overlays `soldKeys` and `retiredKeys` hand back to the list. */
  key: string
  box: number
  index: number

  /** The server's own rendered label. Never composed here — types.ts states the rule on
   *  `Place.label`, and D10 is why it has teeth. */
  place: string

  /** The sentence at the top of the receipt. Two exist per write: this device's, and the
   *  other device's, which is a receipt for a card leaving the boxes rather than for
   *  anything the owner did. Both are receipts, so both are drawn the same way. */
  said: string

  /** False when there is nothing to offer — the server said the write cannot be reversed, or
   *  it was never this device's write. `note` then says why, because a control that quietly
   *  is not there is indistinguishable from one that was not found. */
  canUndo: boolean

  note: string | null

  /** Wall-clock deadline, fixed when the write is recorded and never touched again. A
   *  duration held here instead would have to be restarted on every re-render. */
  until: number
}

export function Inventory() {
  /* Null means "not read yet", which is a different thing from an empty array, and the two
   * render differently below — a store with no cards in it is a fact, and a store that has
   * not answered is not. */
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  /* Each box's divider layout, for the bars on the copy rows. Empty until `GET /boxes`
   * answers, and empty forever if it never does — see the effect below and the header. */
  const [layouts, setLayouts] = useState<ReadonlyMap<number, readonly SectionDetail[]>>(
    NO_LAYOUTS,
  )

  /* THE SEARCH IS A SECOND READ AND NOT A FILTER OVER THE FIRST. `GET /search` groups on the
   * server and hands back two numbers this app is forbidden from computing — D7's live cap and
   * each copy's place in its box (D10) — neither of which is on `GET /inventory`. Filtering the
   * browse groups in the browser would draw a list that looks the same and cannot answer the
   * question the screen was opened for. See `server.ts:search`. */
  const { query, setQuery, results, loading, failure: searchFailure, reload } = useSearch()

  /* The copy waiting on a photo-confirm, or null. THE PHOTO IS THE GUARD — see the header:
   * this is half of what the objection asked for, and it is why pressing Mark sold on a row
   * writes nothing on its own. */
  const [pending, setPending] = useState<SearchCopy | null>(null)

  /* The copy waiting on a retire panel, or null. The same guard for the sibling write
   * (D26): pressing Retire on a row writes nothing on its own — the panel shows the copy's
   * stored photo at its position, and the write happens only when a REASON is chosen, since
   * a retirement without one is refused (`retire_reason_invalid`) and the choice is the
   * confirm. At most one of `pending` and this is non-null: opening either closes the
   * other at the call sites, because two stacked scrims is two answers to "what am I about
   * to do". */
  const [retiring, setRetiring] = useState<SearchCopy | null>(null)

  /* One sale in flight at a time, by copy key. `Store.write()` takes the file lock per call,
   * so several at once stack against a lock and return their failures out of order — the same
   * reason the review screen serialises. */
  const [busyKey, setBusyKey] = useState<string | null>(null)

  /* Receipts — sales and retirements — still inside their undo window, newest first. */
  const [receipts, setReceipts] = useState<Receipt[]>([])

  /* Copies this screen has sold and the wire has not caught up with yet. An optimistic overlay
   * and nothing more — `CardLocations.soldKeys` is documented as exactly that. It outlives the
   * receipt on purpose: the undo window closes after twenty seconds, and the row must not go
   * back to offering to sell a card that is already gone.
   *
   * THE HEADER USED TO GO STALE AND NO LONGER DOES. `on hand` and `listed N of 4` come off the
   * SKU rather than off the copy rows, so nothing in the response this screen already holds
   * could be patched to show a sale — the overlay covered the ROW and the header sat one copy
   * behind until the query changed. `useSearch` now exposes `reload`, which re-asks the
   * CURRENT query and leaves the field alone; the sale handler calls it beside its browse
   * re-read. Nudging the query string to force the same refetch was the tempting workaround
   * and stays refused: it would put text in a box the owner did not type, while they are
   * mid-sentence in it. */
  const [sold, setSold] = useState<string[]>([])

  /* The same optimistic overlay for the sibling write: copies this screen has retired and
   * the wire has not caught up with yet. Two lists rather than one because the row draws a
   * different word for each — `sold` and `retired` are two different doors out, and a
   * combined "gone" list would erase which one the copy left by until the next read. */
  const [retired, setRetired] = useState<string[]>([])

  /* A refusal from a sale or an undo, as an owner-side screen draws it. Screen-wide rather
   * than per-sale because it belongs to a write that produced no receipt to hang it on; the
   * `note` field carries the per-sale case, which is the split Fulfillment.tsx arrived at
   * after a failed-undo message outlived the button it told you to press. */
  const [trouble, setTrouble] = useState<Failure | null>(null)

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first response can land after the
    // second one; the flag makes the late arrival a no-op rather than a flicker. Same shape
    // as the pull preview's.
    let live = true
    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`. The two-argument form does not cover
     * its own success handler: anything thrown while walking the answer lands as an unhandled
     * rejection instead of a failure panel, and the screen sits on "Reading the inventory."
     * forever with nothing to press. Fulfillment.tsx recorded that symptom in those words
     * after a morning of it, and this file kept the two-argument form for another ten days —
     * which is the argument for the eslint rule in `app/eslint.config.js` rather than for a
     * fourth comment saying the same thing. The walk below is `Object.entries` over two maps
     * off the wire, so it is exactly the shape that throws on a body this screen cannot read.
     */
    getInventory()
      .then((inventory) => {
        if (!live) return
        // Grouped once, here, rather than memoised at render: the response is the only input
        // and it changes exactly when this runs.
        setGroups(groupBySku(inventory.cards, listingsOf(inventory)))
        setFailure(null)
      })
      .catch((err: unknown) => {
        if (!live) return
        setGroups(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* THE BOX LAYOUTS. One read, on the same counter as the inventory read above, and allowed
   * to fail without anybody hearing about it.
   *
   * NOT ON THE SEARCH. A query does not move a divider — the layouts change when the owner
   * edits one on `#/boxes`, which is rare and is not something typing a card's name can do —
   * so hanging this off `query` would ask the server for the same records on every keystroke
   * to draw a picture that had not changed. `reloads` is the right counter because
   * it is the one the screen's own Reload bumps, and a control that plainly means "read it
   * all again" should cover the bars as well as the rows. A recorded sale bumps it too and so
   * re-reads a layout that has almost certainly not moved; that is one small GET after a write
   * that has already returned, which is cheaper than a second counter and a second Reload.
   *
   * THE `.catch` IS EMPTY ON PURPOSE AND THAT IS THE WHOLE DESIGN. No failure state, no
   * message, no clearing of what is already held — a `/boxes` that is dead, slow, or answering
   * nonsense leaves every bar drawing the honest three-run picture and leaves the search
   * results, the browse, and the sale button exactly as they were. A refresh that fails after
   * a good read keeps the good read rather than coarsening the bars mid-session, which would
   * look like a defect and would be one less true thing on screen for no gain.
   *
   * `.then(ok).catch(fail)` AND NOT `.then(ok, fail)` — the rule the inventory read above
   * argues at length and `app/eslint.config.js` enforces. It binds here even though the
   * failure path does nothing: `layoutsOf` walks a body off the wire, so it is exactly the
   * shape that throws inside the success handler, and the two-argument form would turn that
   * into an unhandled rejection instead of the silence this effect intends. */
  useEffect(() => {
    let live = true
    getBoxes()
      .then((summary) => {
        if (!live) return
        setLayouts(layoutsOf(summary))
      })
      .catch(() => {
        // Deliberately nothing. See above: the bars are honest without this.
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline rather than one per sale.
   * Fulfillment.tsx's shape, and the slack at the end is its finding too: a timer that fires a
   * hair early would drop nothing, return an array of the same length, and React would bail
   * out on the identical reference — leaving the receipt up forever with nothing to re-arm
   * the timer. */
  useEffect(() => {
    if (receipts.length === 0) return
    const soonest = Math.min(...receipts.map((receipt) => receipt.until))
    const timer = window.setTimeout(
      () =>
        setReceipts((held) => {
          const standing = held.filter((receipt) => receipt.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [receipts])

  /* Escape closes whichever panel is up — the photo-confirm, or the retire panel, which is
   * the same decision point for the sibling write. A panel is a decision point and not a
   * destination, so the key that means "I did not mean this" has to work — and
   * docs/DESIGN.md's no-dialog rule is about REVERSIBLE actions, which is what makes a
   * confirm legal here at all. */
  useEffect(() => {
    if (pending === null && retiring === null) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPending(null)
        setRetiring(null)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [pending, retiring])

  /** Newest first, and a second write against one position replaces its receipt rather than
   *  stacking another on it. These are events rather than places, so box-walk order does not
   *  apply. */
  const remember = useCallback((receipt: Omit<Receipt, 'until'>) => {
    setReceipts((held) => [
      { ...receipt, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.key !== receipt.key),
    ])
  }, [])

  const doSell = useCallback(
    async (copy: SearchCopy) => {
      if (busyKey !== null) return
      setBusyKey(copy.key)
      setTrouble(null)
      setPending(null)
      setRetiring(null)

      /* The label, or the pooled fact — `Place.label` is null for a pooled copy (types.ts,
       * on the field), and a receipt still needs a line the owner can grep. */
      const seat = {
        key: copy.key,
        box: copy.place.box,
        index: copy.place.index,
        place: copy.place.label ?? `pooled · ${copy.key}`,
      }
      try {
        const reversible = canTakeBack(await markSold(copy.place.box, copy.place.index))
        setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        // "Mark sold" produced "Marked sold." — docs/DESIGN.md's copy rule that an action
        // keeps its name through the whole flow.
        remember({
          ...seat,
          kind: 'sale',
          said: 'Marked sold.',
          canUndo: reversible,
          note: reversible
            ? null
            : 'The store cannot say what state this copy was in before the sale, so it ' +
              'cannot be put back from here (sold_origin_unknown).',
        })
        // Both views behind the sale are now one copy stale. Re-read rather than patch: D13
        // has one place inventory lives, and this screen's whole rule is that it holds no
        // second copy of it. `reload` re-asks the current query without touching the field.
        setReloads((n) => n + 1)
        reload()
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          /* Not this device's sale — see the ruling at ALREADY_SOLD. A receipt rather than a
           * failure, because that is what it is: a copy left the boxes and the owner did not
           * do it. No undo, deliberately; it would reverse the other device's real sale. */
          setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
          remember({
            ...seat,
            kind: 'sale',
            said: 'Already sold.',
            canUndo: false,
            note: 'Another device sold this copy first, so nothing was written here.',
          })
          setReloads((n) => n + 1)
          return
        }
        setTrouble(describeFailure(err))
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, remember],
  )

  /* The sibling write (D26), shaped move for move on `doSell` above so the two cannot drift:
   * same busy gate, same optimistic overlay, same receipt with the same clock, same re-read
   * after the write. The reason arrives already chosen — the retire panel's four buttons are
   * the confirm, so there is no reasonless press to guard against. */
  const doRetire = useCallback(
    async (copy: SearchCopy, reason: RetireReason) => {
      if (busyKey !== null) return
      setBusyKey(copy.key)
      setTrouble(null)
      setPending(null)
      setRetiring(null)

      /* As at `doSell`: the label, or the pooled fact, never null on a receipt. */
      const seat = {
        key: copy.key,
        box: copy.place.box,
        index: copy.place.index,
        place: copy.place.label ?? `pooled · ${copy.key}`,
      }
      try {
        const reversible = canTakeBack(
          await retireCard(copy.place.box, copy.place.index, reason),
        )
        setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        // "Retire" produced "Retired." — the same copy rule the sale follows. The machine
        // word for WHY sits in the note, greppable against the history line it landed in.
        remember({
          ...seat,
          kind: 'retirement',
          said: 'Retired.',
          canUndo: reversible,
          note: reversible
            ? `reason: ${reason}`
            : `reason: ${reason} — the store cannot say what state this copy was in ` +
              'before the retirement, so it cannot be put back from here ' +
              '(retired_origin_unknown).',
        })
        setReloads((n) => n + 1)
        reload()
      } catch (err) {
        if (refusalCode(err) === ALREADY_RETIRED) {
          /* The other device's retirement — the sibling of ALREADY_SOLD's ruling, adopted
           * whole: a receipt with no undo, because the undo would reverse a departure this
           * device never recorded. */
          setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
          remember({
            ...seat,
            kind: 'retirement',
            said: 'Already retired.',
            canUndo: false,
            note: 'Another device retired this copy first, so nothing was written here.',
          })
          setReloads((n) => n + 1)
          return
        }
        setTrouble(describeFailure(err))
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, remember],
  )

  const doUndo = useCallback(
    async (receipt: Receipt) => {
      if (busyKey !== null) return
      setBusyKey(receipt.key)
      setTrouble(null)
      try {
        if (receipt.kind === 'sale') await undoSale(receipt.box, receipt.index)
        else await undoRetire(receipt.box, receipt.index)
      } catch (err) {
        /* `not_sold` / `not_retired` is success — the copy is not in the state the press
         * asked to leave, which is what it asked for. Each is read only against its own
         * route: `not_retired` from the sale route would be a bug worth seeing, not a
         * success to swallow. Anything else keeps the receipt standing so the control is
         * still there to press. */
        const settled = receipt.kind === 'sale' ? NOT_SOLD : NOT_RETIRED
        if (refusalCode(err) !== settled) {
          setTrouble(describeFailure(err))
          setBusyKey(null)
          return
        }
      }
      setReceipts((held) => held.filter((standing) => standing.key !== receipt.key))
      if (receipt.kind === 'sale') setSold((held) => held.filter((key) => key !== receipt.key))
      else setRetired((held) => held.filter((key) => key !== receipt.key))
      // Both views behind the reversal are now one copy stale — the same sentence the
      // write handlers say, now true in the other direction. The search re-read was
      // missing here while the write path had it, so an undone copy's row went on wearing
      // `sold` until the next keystroke; observed on the retirement's first walk-through
      // and fixed for both kinds, since the gap was never about which door.
      setReloads((n) => n + 1)
      reload()
      setBusyKey(null)
    },
    [busyKey],
  )

  /* Three counts, and the third is the one worth publishing beside the other two: copies the
     pipeline has written no import row for. It is the gap between what is in the boxes and
     what is for sale, and a screen that reported only SKUs and copies would let that number
     grow without ever naming it. */
  const skus = groups === null ? 0 : groups.filter((group) => group.sku !== null).length
  const copies = groups === null ? 0 : groups.reduce((n, group) => n + group.copies.length, 0)
  const withoutSku =
    groups === null ? 0 : (groups.find((group) => group.sku === null)?.copies.length ?? 0)

  /* Trimmed, matching `useSearch`'s own rule: a field holding one space is empty, and the hook
   * asks the server nothing for it. One test rather than two so the screen and the hook cannot
   * disagree about which body is on show. */
  const searching = query.trim() !== ''
  const soldKeys = new Set(sold)
  const retiredKeys = new Set(retired)

  /* THE RECEIPTS SIT ABOVE BOTH BODIES, which is Fulfillment.tsx's finding rather than a
   * layout preference. They were rendered inside one branch there, so walking away hid the
   * Undo while its clock kept running — a twenty-second promise on screen for two. Here the
   * equivalent is typing the next card's name: the results are replaced, the row is gone, and
   * the window is still open. Above the branch, it survives.
   *
   * ONE PANEL SHAPE FOR BOTH KINDS. A sale's receipt and a retirement's differ only in their
   * sentence and their note; `kind` is `doUndo`'s to branch on and nothing rendered here
   * reads it.
   *
   * NO FILL. docs/DESIGN.md reserves the solid accent for a screen with exactly one thing to
   * do, and a receipt is the way back from something already done. The confirm panel below is
   * the one place on this screen that qualifies, and it keeps the only fill. */
  const receiptPanels = receipts.map((receipt) => (
    <div className="inventory-receipt" key={receipt.key}>
      <p className="inventory-receipt-said">{receipt.said}</p>
      <p className="inventory-receipt-place">{receipt.place}</p>
      {receipt.note === null ? null : <p className="inventory-machine">{receipt.note}</p>}
      {!receipt.canUndo ? null : (
        /* The position is in the accessible name and not on the button. Two receipts standing
           at once make two controls that both read "Undo" to anything that cannot see the
           panel they sit in; the visible word stays one word, which is what the copy rules ask
           of a control. */
        <button
          className="inventory-plain"
          type="button"
          aria-label={`Undo ${receipt.place}`}
          disabled={busyKey !== null}
          onClick={() => void doUndo(receipt)}
        >
          Undo
        </button>
      )}
    </div>
  ))

  return (
    <main className="inventory">
      <header className="inventory-head">
        <h1 className="inventory-title">Inventory</h1>
        <p className="inventory-lede">
          Every copy of every card, grouped by the SKU it was listed under. One SKU is one row
          in an import file; each copy beneath it is a physical card at its own position. Type a
          card&rsquo;s name to see every copy of it, how far into its box each one sits, and to
          record a sale against the copy your hand reached.
        </p>

        {/* THE SEARCH IS THE FIRST CONTROL ON THE SCREEN, above the browse it does not
            replace. `/` focuses it from anywhere — SearchField owns the hotkey and the chip,
            and both are owner-side by its own rule. `autoFocus` because this screen is opened
            for one reason: a card just sold and its copies need finding. */}
        <div className="inventory-search">
          <SearchField value={query} onChange={setQuery} persona="owner" autoFocus />
        </div>

        <div className="inventory-controls">
          {/* A reload is a GET, and re-reading the store is not acting on it. It earns its
              place for the reason the pull preview's does: the alternative is teaching the
              owner to reload the browser. No accent fill — docs/DESIGN.md reserves the solid
              fill for a screen with exactly one thing to do, and this screen's one thing is
              to be read. */}
          <button
            className="inventory-reload"
            type="button"
            onClick={() => setReloads((n) => n + 1)}
          >
            Reload
          </button>
          {groups === null ? null : (
            <span className="inventory-count">
              {count(skus, 'sku', 'skus')} · {count(copies, 'copy', 'copies')}
              {withoutSku === 0 ? null : ` · ${withoutSku} without a sku`}
            </span>
          )}
        </div>
      </header>

      {receiptPanels.length === 0 ? null : (
        <div className="inventory-receipts">{receiptPanels}</div>
      )}

      {trouble === null ? null : (
        <div className="inventory-note">
          <p className="inventory-note-text">{trouble.message}</p>
          <p className="inventory-machine">{trouble.code}</p>
        </div>
      )}

      {pending === null ? null : (
        <Confirm
          copy={pending}
          /* THE PANEL GETS ONE BOX'S LAYOUT AND THE ROWS GET THE MAP, because the panel holds
             exactly one copy and the box it is in is already known here. Looking it up at the
             call site rather than handing a whole map to a component with one place to draw is
             the same reason `CardLocations` takes the map: each is given the shape its own job
             needs, and neither has to pick. */
          sections={layouts.get(pending.place.box)}
          busy={busyKey !== null}
          onConfirm={() => void doSell(pending)}
          onCancel={() => setPending(null)}
        />
      )}

      {retiring === null ? null : (
        <RetirePanel
          copy={retiring}
          /* One box's layout, exactly as the sale's panel above takes it. */
          sections={layouts.get(retiring.place.box)}
          busy={busyKey !== null}
          onRetire={(reason) => void doRetire(retiring, reason)}
          onCancel={() => setRetiring(null)}
        />
      )}

      {searching ? (
        <>
          {searchFailure === null ? null : (
            <div className="inventory-note">
              <p className="inventory-note-text">{searchFailure.message}</p>
              <p className="inventory-machine">{searchFailure.code}</p>
            </div>
          )}

          {/* `loading` is true through the debounce as well as the request — `useSearch` says
              why — so this is the honest answer to "is what is on screen an answer to what is
              in the box". Drawn beside the previous results rather than instead of them: a
              list that blanks on every keystroke is worse to type against than one that lags
              by 200ms and says so. */}
          {loading ? <p className="inventory-note-text">Looking.</p> : null}

          {results !== null && !loading && results.groups.length === 0 ? (
            <p className="inventory-note-text">
              Nothing in the boxes matches <span className="inventory-inline">{results.query}</span>.
            </p>
          ) : null}

          {results === null ? null : (
            <div className="inventory-found">
              {results.groups.map((group) => (
                /* THE POSITION BAR DRAWS ON EVERY COPY ROW, and that is the owner's ruling
                   rather than a default. `CardLocations`'s owner skin puts one on each row for
                   the reason its own header gives: how far into the box a copy sits is what
                   the screen was opened to learn, and a fact you have to hover to see is a
                   fact you compare one at a time. Four copies in four boxes is exactly the
                   case that makes that impossible.

                   `renderAction` NOW, AND THE PARAGRAPH THAT DECLINED IT IS OVERTAKEN RATHER
                   THAN ERASED. It said the default slot was what this screen wants — "Mark
                   sold, or the word `sold`" — which was true while the screen had one write.
                   D26 gave it a second, and the default slot draws exactly one control, so
                   the slot is replaced with the same rules it applied plus the sibling: a
                   copy that left draws the word for WHICH door (`sold` or `retired`,
                   verbatim, the pipeline's own vocabulary), and a copy still here draws both
                   quiet buttons. What that paragraph defended still stands: the guard is not
                   in the slot — each press opens its panel over the copy's own photo, and
                   the receipt above carries the undo.

                   `sections` IS THE WHOLE MAP AND NOT THIS GROUP'S SLICE, because a group is a
                   SKU and not a box. D7 keeps every copy at its own position, so the rows of
                   one group can run across boxes that are divided differently — picking a
                   layout out here would mean picking one for a set of copies that do not share
                   one. `CardLocations` looks it up per copy off `place.box`, which is the only
                   place the right answer is known. */
                <CardLocations
                  key={group.sku ?? `without-a-sku-${group.names.join('/')}`}
                  group={group}
                  persona="owner"
                  sections={layouts}
                  onSell={(copy) => {
                    setTrouble(null)
                    setRetiring(null)
                    setPending(copy)
                  }}
                  busyKey={busyKey}
                  soldKeys={soldKeys}
                  renderAction={(copy) =>
                    copy.state === 'sold' || soldKeys.has(copy.key) ? (
                      <span className="card-locations-gone">sold</span>
                    ) : copy.state === 'retired' || retiredKeys.has(copy.key) ? (
                      <span className="card-locations-gone">retired</span>
                    ) : (
                      <span className="inventory-copy-actions">
                        <button
                          className="card-locations-sell"
                          type="button"
                          disabled={busyKey !== null}
                          onClick={() => {
                            setTrouble(null)
                            setRetiring(null)
                            setPending(copy)
                          }}
                        >
                          Mark sold
                        </button>
                        <button
                          className="card-locations-sell"
                          type="button"
                          disabled={busyKey !== null}
                          onClick={() => {
                            setTrouble(null)
                            setPending(null)
                            setRetiring(copy)
                          }}
                        >
                          Retire
                        </button>
                      </span>
                    )
                  }
                />
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {failure === null ? null : (
            <div className="inventory-note">
              <p className="inventory-note-text">{failure.message}</p>
              {/* The code beneath the sentence, never the sentence again — docs/DESIGN.md's
                  human-label-large, machine-string-small rule. What goes here is the greppable
                  token, which is the only way from what is on screen to what the server
                  said. */}
              <p className="inventory-machine">{failure.code}</p>
            </div>
          )}

          {groups === null && failure === null ? (
            <p className="inventory-note-text">Reading the inventory.</p>
          ) : null}

          {groups !== null && groups.length === 0 ? (
            <p className="inventory-note-text">No cards captured yet.</p>
          ) : null}

          {groups !== null && groups.length > 0 ? (
            <div className="inventory-groups">
              {groups.map((group) => (
                <GroupRow key={group.sku ?? 'without-a-sku'} group={group} />
              ))}
            </div>
          ) : null}
        </>
      )}
    </main>
  )
}

/* The photo-confirm, and the first half of the answer to this file's own objection.
 *
 * D6 PUTS THE PHOTO SERVICE HERE FOR EXACTLY THIS: "the review queue requires it; the pull
 * modal reuses it, showing the card's own capture photo beside its location before pulling."
 * The pull modal is the Fulfiller's; this is the owner's, and the entry describes the
 * operation rather than the persona. What is being confirmed is not "did you mean to press
 * that" — docs/DESIGN.md bans that dialog outright — but "is the card in your hand the card at
 * this position", which is a question only a photograph can answer.
 *
 * ONE THING TO DO, SO IT GETS THE FILL. The rule is docs/DESIGN.md's: solid accent where there
 * is exactly one action, outline where the system is unsure. A confirm panel is the one shape
 * on this screen that qualifies, which is why `PullConfirm` is reused here rather than copied
 * — the same component step 6 built and the same fill it was measured in. Cancel is not a
 * second action in that sense; it is the way out, and it is drawn as the quiet control every
 * other owner-side screen uses.
 *
 * A MISSING PHOTO DOES NOT BLOCK THE SALE. `has_photo` says the server had bytes when it
 * answered, and undo deletes a photo — so the load can still fail between the search and this
 * panel. A card with no photograph is still a real card at a real position, and refusing to
 * let the owner sell it would make a display failure into an inventory one. The panel says
 * plainly that there is nothing to confirm against and leaves the decision where it was.
 */
function Confirm({
  copy,
  sections,
  busy,
  onConfirm,
  onCancel,
}: {
  copy: SearchCopy

  /** THIS copy's box layout, or undefined. One box's spans and not the map, because this panel
   *  draws one copy — see the call site. Undefined is the ordinary case before `GET /boxes`
   *  answers and the permanent case if it never does, and the bar is honest either way. */
  sections?: readonly SectionDetail[]
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const [broken, setBroken] = useState(false)
  const [panel, setPanel] = useState<HTMLDivElement | null>(null)

  /* Focus lands on the confirm button. A callback ref rather than `useRef` + an effect on
   * mount, because the node is what the effect is waiting for and a callback ref already fires
   * when it arrives.
   *
   * NO KEY CHIP, and its absence is the honest half of "every choice shows its key". The
   * focused button already takes Enter and Escape already cancels — both true without a
   * listener of this file's own. A chip saying so would be a hint about the browser's
   * behaviour rather than about a binding this screen owns, and a second Enter handler beside
   * the focused button is how one press fires twice. */
  useEffect(() => {
    panel?.querySelector<HTMLButtonElement>('.pull-confirm')?.focus()
  }, [panel])

  const gone = !copy.has_photo || broken

  return (
    /* The scrim closes on a click that misses the panel, which is the same gesture Escape is.
       `role="presentation"` because it is not a control — the panel's own buttons are, and the
       keyboard route out is the key rather than this element. */
    <div className="inventory-scrim" role="presentation" onClick={onCancel}>
      <div
        className="inventory-confirm"
        ref={setPanel}
        role="dialog"
        aria-modal="true"
        aria-label={`Mark sold: ${copy.place.label}`}
        onClick={(event) => event.stopPropagation()}
      >
        <p className="inventory-confirm-head">Mark sold</p>

        {gone ? (
          <p className="inventory-note-text">
            No photo is stored for this position, so there is nothing to check the card
            against. The copy is still recorded at the position below.
          </p>
        ) : (
          <img
            className="inventory-confirm-photo"
            src={photoUrl(copy.place.box, copy.place.index)}
            alt={`The card stored at ${copy.place.label}`}
            onError={() => setBroken(true)}
          />
        )}

        <p className="inventory-confirm-place">{copy.place.label}</p>
        {copy.place.box_name === null ? null : (
          <p className="inventory-confirm-boxname">{copy.place.box_name}</p>
        )}

        {/* The same bar the row carries, so what the owner confirms against is what he chose
            the copy by. Nothing here is computed: `spansOf` draws the server's own numbers.

            THAT SENTENCE IS WHY `sections` IS PASSED HERE TOO. The rows draw the box's real
            dividers now; a panel left without the layout would draw the coarser three-run
            picture, and the bar in front of the owner at the moment he confirms would not be
            the bar he picked the copy by. Both true, differently shaped, one of them arriving
            only at the decision point — which is the one place on this screen where a changed
            picture could make somebody hesitate over the right card. */}
        <PositionBar place={copy.place} persona="owner" sections={sections} />

        <div className="inventory-confirm-actions">
          <PullConfirm label="Mark sold" onConfirm={onConfirm} disabled={busy} />
          <button className="inventory-plain" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

/* The four reasons a card leaves without a sale, in the store's own vocabulary
 * (`store/master.py:RETIRE_REASONS`, D26). Human label beside the machine word, drawn at
 * two sizes per docs/DESIGN.md's owner-side rule: the label is read, the word is what greps
 * to the history line the choice lands in. The order is the enum's, not a ranking. */
const REASONS: readonly { reason: RetireReason; label: string }[] = [
  { reason: 'pulled', label: 'Pulled out' },
  { reason: 'damaged', label: 'Damaged' },
  { reason: 'lost', label: 'Lost' },
  { reason: 'given_away', label: 'Given away' },
]

/* The retire panel — `Confirm`'s sibling for D26's write, sharing its scrim, its photo and
 * its bar so what the owner confirms against is the same picture on both writes.
 *
 * FOUR ANSWERS, SO NO FILL. docs/DESIGN.md gives the solid accent to a screen with exactly
 * one thing to do, and this panel is a choice — filling one reason would teach the queue's
 * "a screen with two answers gets no fill" rule a counterexample on the next screen over.
 * The reason buttons are the confirm: pressing one writes the retirement, pressing nothing
 * writes nothing, and Escape or the scrim leaves the way `Confirm` does. There is no
 * separate "Retire" button to press after the reason, because the reason IS the decision —
 * a second press would be the acknowledgement dialog the design bans.
 *
 * FOCUS LANDS ON CANCEL, not on a reason. `Confirm` focuses its one action because it has
 * one; focusing any reason here would make Enter answer a question the owner has not read
 * yet, and the four are not ranked. Cancel is the one control whose accidental press costs
 * nothing. */
function RetirePanel({
  copy,
  sections,
  busy,
  onRetire,
  onCancel,
}: {
  copy: SearchCopy
  sections?: readonly SectionDetail[]
  busy: boolean
  onRetire: (reason: RetireReason) => void
  onCancel: () => void
}) {
  const [broken, setBroken] = useState(false)
  const [panel, setPanel] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    panel?.querySelector<HTMLButtonElement>('.inventory-plain')?.focus()
  }, [panel])

  const gone = !copy.has_photo || broken

  return (
    <div className="inventory-scrim" role="presentation" onClick={onCancel}>
      <div
        className="inventory-confirm"
        ref={setPanel}
        role="dialog"
        aria-modal="true"
        aria-label={`Retire: ${copy.place.label}`}
        onClick={(event) => event.stopPropagation()}
      >
        <p className="inventory-confirm-head">Retire</p>

        {gone ? (
          <p className="inventory-note-text">
            No photo is stored for this position, so there is nothing to check the card
            against. The copy is still recorded at the position below.
          </p>
        ) : (
          <img
            className="inventory-confirm-photo"
            src={photoUrl(copy.place.box, copy.place.index)}
            alt={`The card stored at ${copy.place.label}`}
            onError={() => setBroken(true)}
          />
        )}

        <p className="inventory-confirm-place">{copy.place.label}</p>
        {copy.place.box_name === null ? null : (
          <p className="inventory-confirm-boxname">{copy.place.box_name}</p>
        )}

        <PositionBar place={copy.place} persona="owner" sections={sections} />

        {/* What the choice does, before the choices: the record stays, the gap stays. Kept
            to one sentence — the panel is a decision point, not documentation. */}
        <p className="inventory-note-text">
          The card leaves the inventory without a sale. Its record and photo stay, and the
          position is never reused.
        </p>

        <div className="inventory-retire-reasons">
          {REASONS.map(({ reason, label }) => (
            <button
              key={reason}
              className="inventory-retire-reason"
              type="button"
              disabled={busy}
              onClick={() => onRetire(reason)}
            >
              <span className="inventory-retire-label">{label}</span>
              <span className="inventory-machine">{reason}</span>
            </button>
          ))}
        </div>

        <div className="inventory-confirm-actions">
          <button className="inventory-plain" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

/* One group: the summary that is always visible, and the copies underneath it.
 *
 * `<details>` rather than a button and a `useState` set of open keys, for the reason App.tsx
 * gives for using plain anchors and no click handler: the browser already does this, and
 * reproducing it in React would be code to keep working — keyboard, focus and the open state
 * itself — in exchange for nothing this screen needs.
 *
 * COLLAPSED BY DEFAULT, and this one is an ASSUMPTION the doc does not settle. A Gate B run
 * may be two hundred cards (capture-app spec §10.1), and open by default is a two-hundred-row
 * wall on a screen whose first job is to say how many copies of what exist. The summary
 * carries the count and the state tally, which is most of what a lookup wants; the positions
 * are one click away. Watching a real run settles it — if every group gets opened, they
 * should start open. */
function GroupRow({ group }: { group: Group }) {
  const loose = group.sku === null

  /* The copy rows carry a card name only where the summary above cannot say it for them:
   * the no-SKU group, whose copies are DIFFERENT cards, and a SKU whose copies were read as
   * more than one name. A SKU group is by definition one card, and repeating its name down
   * forty rows is the dense-grey-table failure docs/DESIGN.md names by the front door. */
  const showNames = loose || group.names.length > 1

  /* The machine line under the name. `sku: null` rather than a friendlier phrase for the
   * group that has none — the field and its state, in the shape the pull preview's
   * `photo: null` panel established, so the screen and a `curl /inventory` use one vocabulary.
   *
   * Distinct values are joined rather than reduced to one. For `sku` there is only ever the
   * one; for condition and number there should be, and a group showing two is a run worth
   * looking at rather than a display to tidy. */
  const meta = loose
    ? ['sku: null']
    : [
        `sku ${group.sku ?? ''}`,
        ...(group.conditions.length > 0 ? [group.conditions.join(' / ')] : []),
        ...(group.numbers.length > 0 ? [group.numbers.join(' / ')] : []),
      ]

  return (
    <details className="inventory-group">
      <summary className="inventory-summary">
        {/* Drawn rather than left to the browser's own disclosure triangle. The native marker
            is sized and coloured by the browser and differs between the one the owner works
            in and the Chromium `make screenshot` renders — and comparing that render against
            the reference is the loop docs/DESIGN.md calls mandatory. A glyph in the utility
            face is one system in both. */}
        <span className="inventory-marker" aria-hidden="true" />

        {/* The copy count is the number D7 is about, so it is the utility face and the
            heaviest thing in the row. */}
        <span className="inventory-copies-count">{count(group.copies.length, 'copy', 'copies')}</span>

        <span className="inventory-main">
          <span className="inventory-name">
            {loose
              ? 'No SKU yet'
              : group.names.length === 0
                ? 'Not identified yet'
                : group.names.join(' / ')}
          </span>
          <span className="inventory-meta">{meta.join(' · ')}</span>
        </span>

        {/* TWO CLUSTERS IN ONE COLUMN, CAPTIONED, BECAUSE THEY ARE COUNTS OF DIFFERENT THINGS.
            The left one counts card records, each of which is a position somebody can walk to
            a box for. The right one is quantity against a SKU, and D7 says which physical
            copies back it is "deliberately not recorded" — so `live 3` names no card, and a
            reader who takes it for three positions has been told a thing that is not true.

            Before the store refactor all six words were one list, correctly: every one of them
            was a state a position wore. Rendering them that way now would be the old fiction
            redrawn — the exact reading that made `cli/cmd_join.py` pick which four of seven
            identical copies were sellable.

            `positions` and `listed` rather than a heavier separator, because the captions carry
            the one fact the words alone cannot: `pushed` and `identified` are both plainly
            pipeline vocabulary, and nothing in either word says which unit it is counted in.
            Muted with no number beside them, so they read as labels and not as data.

            The captions appear only when the second cluster does. A group with no listing
            record draws exactly what this row drew before, uncaptioned — there is nothing to
            disambiguate, and a lone caption over a lone cluster is chrome.

            Every state present, none of them merged, and the same on the listing side:
            `staged` and `live` are two facts about two different things. `store/master.py`
            says why in as many words — D7's refill maths reads the LIVE number, and an import
            that was staged and never moved live has no live quantity at all. A display that
            merged them would hide exactly the box that is not earning, which is why the zeros
            are drawn rather than dropped once a record exists at all. */}
        <span className="inventory-tally">
          {group.listed === null ? null : (
            <span className="inventory-tally-item">
              <span className="inventory-tally-state">positions</span>
            </span>
          )}
          {group.states.map((entry) => (
            <span className="inventory-tally-item" key={entry.state}>
              <span className="inventory-tally-state">{entry.state}</span>
              <span className="inventory-tally-count">{entry.count}</span>
            </span>
          ))}
          {group.listed === null ? null : (
            <>
              <span className="inventory-tally-item">
                <span className="inventory-tally-state">listed</span>
              </span>
              {LISTED_ORDER.map((stage) => (
                <span className="inventory-tally-item" key={stage}>
                  <span className="inventory-tally-state">{stage}</span>
                  <span className="inventory-tally-count">{group.listed?.[stage] ?? 0}</span>
                </span>
              ))}
            </>
          )}
        </span>
      </summary>

      <div className="inventory-body">
        {loose ? (
          <p className="inventory-note-text">
            A card is given a SKU when <code className="inventory-inline">emit</code> writes its
            row into an import file, and never before — so this group holds every copy the
            pipeline has not pushed yet. Cards still to be identified or joined are here, and so
            are the backstock copies past the live cap, which{' '}
            <code className="inventory-inline">emit</code> leaves unpushed by design (D7). None
            of them is lost: each one sits at a position in a box, and stays visible here until a
            run writes a row for it.
          </p>
        ) : null}

        {/* A table because this is one: four fields repeated per copy, read down a column.
            docs/DESIGN.md's warning about the cataloguing tools that became spreadsheets is
            about hierarchy and weight rather than about the element — and the hierarchy here
            is between the group above and its copies, which are deliberately quieter. */}
        <table className={showNames ? 'inventory-table inventory-table-named' : 'inventory-table'}>
          <thead>
            <tr>
              <th className="inventory-cell-position">Position</th>
              {showNames ? <th className="inventory-cell-name">Card</th> : null}
              <th className="inventory-cell-state">State</th>
              <th className="inventory-cell-since">Since</th>
            </tr>
          </thead>
          <tbody>
            {group.copies.map((copy) => (
              <tr key={copy.key}>
                <td className="inventory-cell-position">
                  {positionLabel(copy.card) ?? `no label · ${copy.key}`}
                </td>
                {showNames ? (
                  <td className="inventory-cell-name">
                    {copy.card.name ?? 'not identified yet'}
                  </td>
                ) : null}
                {/* The pipeline's own word, verbatim. A friendly label would be a second
                    vocabulary nothing audits, which is the drift docs/DESIGN.md shows reason
                    codes as machine strings to avoid. */}
                <td className="inventory-cell-state">{copy.card.state}</td>
                <td className="inventory-cell-since">{sinceDay(copy.card.state_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
