import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
  BoxRecord,
  InventoryCard,
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
  markSold,
  photoUrl,
  retireCard,
  undoRetire,
  undoSale,
} from './server'
import { BoxBrowse, type Row } from './BoxBrowse'
import { BoxRuns } from './BoxRuns'
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { useSearch } from './useSearch'
import './Inventory.css'

/* THE INVENTORY — one owner-side view of stored cards, and there is only one way through it.
 *
 * THREE ROUTES BECAME THIS ONE ON 2026-08-23 (D31), AND THEN THE TWO MODES BECAME ONE SCREEN
 * THE SAME DAY. The first half is D31's: `#/boxes`, `#/pull` and this screen rendered the same
 * 767 records and "read as separate instances of one thing", so they merged. The second half is
 * the owner's correction on seeing what that merge shipped — a segmented switch offering
 * "Browse the boxes" or "Find a card":
 *
 *     "i imagined moreso in this merge that these wouldn't be two tabs, instead it's
 *      basically find a card in a box-based system if anything.."
 *
 * So the switch is gone. THE BOX-BASED STRUCTURE IS THE SPINE — box strip, then sections, then
 * cards — and finding a card is a SEARCH OVER THAT SPINE rather than a second place to stand.
 * Typing narrows the walk and the box strip together (`BoxBrowse.tsx` owns both), and what the
 * old Find mode uniquely had now lands where the walk points: select a card and its copies, its
 * listing quantities and its two writes are in the detail panel beside its photograph.
 *
 * WHAT THE SWITCH COST, AND WHY DELETING IT IS NOT A LOSS. The argument that stood here was
 * that the two halves key differently — one by SKU and fungible across copies (D7), one by
 * position and about one physical card — so "a single list would have to pick a key and lie
 * about the other". That was true of a single LIST and it is not true of this screen: the list
 * is keyed by position, and the SKU-keyed view is drawn for the ONE card the list is pointing
 * at, where there is no ambiguity about which key is which. Nothing was folded together; one
 * thing was made a view of the other.
 *
 * NOTHING FROM THE FIND HALF WAS DROPPED, and each piece is named so a later reader can check:
 * D7's SKU -> positions map is `CopiesPanel` below; the sale keeps its receipt and its
 * twenty-second undo — and lost its photo-confirm on 2026-08-30, see the ruling below; D26's
 * retirement keeps all three; `already_sold` is still
 * drawn as a receipt rather than as an error; a pooled copy (D24) still renders no position
 * label; and the per-SKU listing quantities the old group rows carried are now read off
 * `SearchGroup.listed`, which is the same three numbers from the route that also reports the
 * cap this screen used to refuse to compute.
 *
 * WHAT THIS FILE IS NOW: the route, the title, and the one flow that writes a card. The walk,
 * the box operations, the photograph, the re-shoot and the card-level corrections all belong to
 * `BoxBrowse.tsx`; it hands this file the selected card and the box registry, and this file
 * hands it back a node to draw beside the photo. Four things across the seam and nothing else.
 *
 * WHAT DID NOT MERGE: `#/fulfillment`. D31 is explicit — a different persona at a different
 * posture, and the one screen in the product whose whole design is a floor. Nothing here
 * reaches it and `app/tests/fulfillment.spec.ts` is unchanged by any of this.
 *
 * ---- the sale's own argument, unchanged, because the write did not move ----
 *
 * THIS SCREEN WRITES, AND THE PARAGRAPH THAT SAID IT NEVER WOULD IS KEPT BELOW RATHER THAN
 * DELETED. Overturning an argument by erasing it leaves the next session with a screen that
 * does the thing and no record that anybody thought about it — so the objection stands, quoted,
 * and each half is answered where it was made.
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
 *   carried both: a photo-confirm panel showing the copy's own stored photo (D6) at its
 *   position before anything was written, and a receipt with an undo window on every
 *   recorded sale — the shape Fulfillment.tsx already ships. `markSold` answers
 *   `restores_to` precisely so a caller knows whether an undo can be offered at all, and
 *   this screen reads it rather than offering one blind.
 *
 *   AND THE PHOTOGRAPH HALF WAS RULED REDUNDANT ON THIS SCREEN ON 2026-08-30 (D57). The
 *   owner: "for my side i literally have the inventory image in front of me already, it was
 *   redundant." The panel argued it was checking "is the card in your hand the card at this
 *   position", which only a photograph can answer — and since D38 the card band draws that
 *   photograph at 449x627 two inches from the row, so the panel was answering a question
 *   already answered. `Mark sold` writes on one press now and the undo half is DOUBLED
 *   rather than dropped: the row's own slot becomes `Undo` for the window, and the receipt
 *   below keeps its own. That is docs/DESIGN.md's headline rule — "No confirm dialog on a
 *   reversible action ... Undo covers the mistake" — honoured on this control for the first
 *   time, and its Fulfillment line has read "One-tap mark-sold" all along.
 *
 *   THE ANSWER ABOVE IS NOT WEAKENED BY THAT, and the distinction is the whole of D57. The
 *   guards still belong to the write rather than to a view; what moved is which guard this
 *   screen needs, on a screen that already draws the photograph. #/fulfillment is untouched:
 *   his two-step exists because a double-tap once sold a card whose photo he never saw, and
 *   app/tests/fulfillment.spec.ts measures the two rectangles.
 *
 *   OBJECTION 2, TWO PLACES FOR ONE ACTION — ANSWERED BY THE SERVER, WHICH ALREADY REFUSES
 *   THE RACE. The failure feared was two devices disagreeing about which copy went. They
 *   cannot: the second device's sale comes back `already_sold`, and Fulfillment.tsx has
 *   already worked out what that means — somebody else sold that copy, so it is a receipt
 *   for a card leaving your list rather than an error, and no undo may be offered because
 *   the undo would reverse the OTHER device's real sale. This screen reads the same code the
 *   same way, for the same reason, in `doSell` below.
 *
 * OWNER-SIDE, so this is the dense end of docs/DESIGN.md's one system, two densities, and the
 * Fulfillment floors do not bind. It speaks the pipeline's vocabulary — `sku`, `pushed`,
 * `staged` — which the Fulfillment banned-word list forbids outright; borrowing his floors here
 * would make it look like his screen and set the expectation that it is safe for him to read,
 * which it is not (D5).
 *
 * NOTHING IS KEPT. `BoxBrowse` reads `GET /inventory` and `GET /boxes` once each and throws
 * them away on the way out; the copies panel re-asks `GET /search` per card. D13 has exactly
 * one place inventory lives, and the failure a browser-side copy produces is two answers to
 * "where is this card" with one of them stale and neither labelled.
 *
 * TWO THINGS THIS SCREEN USED TO REFUSE TO COMPUTE, AND ONE OF THEM IS SETTLED. The live cap
 * (`pipeline/join.py:LIVE_QUANTITY_CAP`) was refused because writing `2 of 4 live` in TypeScript
 * is a copy of a configurable Python constant that nothing keeps in step — and `GET /search`
 * now reports it (`types.ts:SearchGroup.cap`), which is the exact condition that entry named,
 * so `CardLocations` draws the denominator off the wire. The price is still absent and still
 * for the same reason: D8 routes every price through the export and no inventory record carries
 * one, so there is no money on this screen at all.
 */

/** How long a receipt's undo stays. Twenty seconds, which is Fulfillment.tsx's number and not a
 *  second opinion about the same question.
 *
 *  docs/DESIGN.md's floor is ">= 10s" and it is written as a Fulfillment row, so nothing binds
 *  this screen to any particular length — which is precisely the argument for not inventing
 *  one. Two undo windows of different lengths in one product is a thing to learn for no gain,
 *  and the owner is not the person the shorter number would be for. If the length is ever
 *  measured it should move in both files together.
 *
 *  WHAT WOULD SETTLE IT: watching a sale get taken back. Nothing in this repo has yet. */
const UNDO_WINDOW_MS = 20_000

/* THE TWO REFUSAL CODES THIS SCREEN BRANCHES ON, and the rulings are Fulfillment.tsx's, adopted
 * here rather than re-derived. That file paid for them with a data-integrity bug and wrote up
 * why; a second reading of the same two codes on a second screen is exactly the drift a shared
 * vocabulary exists to stop.
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
 * than deriving new ones. `already_retired` on a retirement is the other device's retirement:
 * a receipt with no undo, because the undo would reverse a departure this device never
 * recorded. `not_retired` on a reversal is success. The CROSS-refusals (`card_retired` on a
 * sale, `already_sold` on a retirement) are deliberately not branched on: each is a real
 * refusal whose server message names the other route's undo as the way through, and the
 * trouble panel shows it verbatim. */
const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const ALREADY_RETIRED = 'already_retired'
const NOT_RETIRED = 'not_retired'

/** The four reasons a card leaves without a sale, in the store's own vocabulary
 *  (`store/master.py:RETIRE_REASONS`, D26). Human label beside the machine word, drawn at two
 *  sizes per docs/DESIGN.md's owner-side rule: the label is read, the word is what greps to the
 *  history line the choice lands in. The order is the enum's, not a ranking. */
const REASONS: readonly { reason: RetireReason; label: string }[] = [
  { reason: 'pulled', label: 'Pulled out' },
  { reason: 'damaged', label: 'Damaged' },
  { reason: 'lost', label: 'Lost' },
  { reason: 'given_away', label: 'Given away' },
]

/** No box layouts, as one shared empty map.
 *
 *  A CONSTANT RATHER THAN `new Map()` AT THE CALL SITE, so that "we have not been told" has
 *  exactly one identity and re-rendering cannot mint a second empty map for React to compare
 *  against. No null is needed: for every other read on this screen "not answered yet" and
 *  "answered with nothing" are different facts, but a position bar draws the same honest
 *  three-run picture either way — so a distinction nothing on screen can act on would be a
 *  state to explain and never to use. */
const NO_LAYOUTS: ReadonlyMap<number, readonly SectionDetail[]> = new Map()

/* Each box's divider layout, keyed by box number, out of the registry `BoxBrowse` already read.
 *
 * THE KEY IS THE POINT OF THE FUNCTION. `sections_detail` is `pipeline/join.py`'s own rendering
 * of one box's layout, and D10 as amended 2026-08-23 puts the dividers wherever the operator
 * physically put them — box 1 declares none and is drawn by the 25-rule, box 95 declares
 * `[1, 24, 74, 84]`, and neither tells you anything about the other. A search group is a SKU
 * and not a box (D7 keeps every copy at its own position), so one card can hold copies in three
 * boxes; flattening this to a single list would hand one box's dividers to another box's card.
 * Keyed by `box`, that mistake has nowhere to happen.
 *
 * GUARDED AT THE EDGES AND NOWHERE ELSE. `server.ts:request` casts rather than validates, so
 * the array and the box number are checked here — an older capture server can answer a shape
 * the type says is impossible. Every field INSIDE a `SectionDetail` is left alone on purpose:
 * `spansOf` reads them one at a time and clamps each into the box, and a second copy of that
 * reading here would be a second place to keep the same rule. */
function layoutsOf(records: readonly BoxRecord[]): ReadonlyMap<number, readonly SectionDetail[]> {
  const out = new Map<number, readonly SectionDetail[]>()
  for (const record of records) {
    if (record === null || typeof record !== 'object') continue
    if (typeof record.box !== 'number' || !Number.isFinite(record.box)) continue
    const detail: unknown = record.sections_detail
    if (!Array.isArray(detail) || detail.length === 0) continue
    out.set(record.box, detail as readonly SectionDetail[])
  }
  return out
}

/** The server's code for a thrown thing, or `''` for anything that is not a refusal — a dead
 *  network, a body that did not parse, a bug in this app. Empty rather than null so every
 *  comparison is a plain `===` against a code that cannot match. */
function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/** Whether the write just recorded can be taken back, out of the server's own answer.
 *
 *  ABSENT IS READ AS NULL and the direction is the safe one — the same guard Fulfillment.tsx
 *  keeps, for the same reason. `server.ts` casts rather than validates, so a capture server old
 *  enough to answer this route without the field hands back `undefined` under a type that says
 *  `string | null`. Suppressing an undo that would have worked costs a question; offering one
 *  that cannot work is the defect the field was added to remove. */
function canTakeBack(result: SaleResult | RetireResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

/** One physical copy, built out of an inventory row, for the one card the search cannot reach.
 *
 *  WHY THIS EXISTS AT ALL. The copies panel finds a card's group by asking `GET /search` for its
 *  SKU or its name — six fields, the server's own matcher, never a second one in the browser.
 *  A card the pipeline has never identified has neither: box 95 and box 99 are 170 records that
 *  are all `captured`, with no name and no SKU, and that is 22% of the store today. Without this
 *  they would be the cards on which D26's retirement — the remedy for a damaged card — is
 *  unreachable, which is precisely backwards.
 *
 *  IT IS NOT A `SearchGroup` AND MUST NOT BECOME ONE. A group carries `on_hand`, `listed` and
 *  `cap`, and there is no honest local value for any of them; inventing three would put numbers
 *  on screen that name nothing. So the fallback draws ONE copy with its two controls and no
 *  group header at all — the group facts are absent because there is no group.
 *
 *  Null when the record arrived with no `place` block: that is the row whose box or index will
 *  not coerce, which the server deliberately leaves undecorated, and a sale needs a position. */
function loneCopy(row: Row): SearchCopy | null {
  const place = row.card.place
  if (place === undefined) return null
  return {
    key: row.key,
    state: row.card.state,
    state_at: row.card.state_at,
    /* `has_photo` off the record's own `photo` field rather than off a second read: the confirm
       panel treats it as a hint and still handles the image failing to load, which is what
       makes this coercion safe. */
    has_photo: row.card.photo !== null,
    place,
  }
}

/** One write that has just been recorded — a sale, or since D26 a retirement — and what can
 *  still be done about it.
 *
 *  A LIST OF THESE AND NOT ONE SLOT. Fulfillment.tsx shipped the single-slot version and found
 *  what it costs: the second sale in a row silently discards the first card's undo and re-arms
 *  the clock for the new one, so "undo on every mark-sold" quietly becomes "on the most recent".
 *  An owner working through the copies of one card has exactly that shape — several copies sold
 *  one after another — so each sale carries its own deadline.
 *
 *  IT HOLDS ITS OWN COPY OF THE POSITION rather than a pointer into the results, because the
 *  results are allowed to move underneath it. Stepping to the next card in the walk replaces
 *  them, and the undo window has to outlive that: a receipt that vanished when the owner
 *  pressed Right would be a twenty-second promise kept for two.
 *
 *  ONE TYPE FOR BOTH WRITES, because a receipt is a receipt: the same panel, the same clock,
 *  the same rules about when Undo may be drawn. `kind` exists for exactly one branch — which
 *  route the Undo calls — and for nothing the render reads. */
type Receipt = {
  /** Which write this reverses: the sale route, or the retirement's. Read by `doUndo` alone. */
  kind: 'sale' | 'retirement'

  /** `SearchCopy.key`, the store's own `"<box>/<index>"`. Identity for React and for the
   *  optimistic overlays `soldKeys` and `retiredKeys` hand back to the rows. */
  key: string
  box: number
  index: number

  /** The server's own rendered label. Never composed here — types.ts states the rule on
   *  `Place.label`, and D10 is why it has teeth. */
  place: string

  /** The sentence at the top of the receipt. Two exist per write: this device's, and the other
   *  device's, which is a receipt for a card leaving the boxes rather than for anything the
   *  owner did. Both are receipts, so both are drawn the same way. */
  said: string

  /** False when there is nothing to offer — the server said the write cannot be reversed, or it
   *  was never this device's write. `note` then says why, because a control that quietly is not
   *  there is indistinguishable from one that was not found. */
  canUndo: boolean

  note: string | null

  /** Wall-clock deadline, fixed when the write is recorded and never touched again. A duration
   *  held here instead would have to be restarted on every re-render. */
  until: number
}

export function Inventory() {
  /* WHICH CARD THE WALK IS POINTING AT, reported up by `BoxBrowse`. This screen owns the writes
   * and therefore has to know which card they are about; the walk owns the selection because it
   * owns the list, the keys and the filter that decide it. One direction, one owner each. */
  const [selected, setSelected] = useState<Row | null>(null)

  /* The box registry, handed up by the same component out of the read it already makes. This
   * file used to fetch `GET /boxes` for itself, which was one route read twice on one screen —
   * harmless and still two places for the same answer to arrive at different times. */
  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])

  /* WHAT A RUN WOULD BE SCOPED TO — the box the walk is in, and the cards ticked inside it.
   * Reported by `BoxBrowse` on the same terms as the selection and the registry, and for the
   * same reason: the walk owns the state, this screen owns the write. It is the identical
   * `pickedIndices` a bulk claim correction reaches, so a run and a claim can never disagree
   * about what "the selection" means — which they could if this screen derived its own. */
  const [runScope, setRunScope] = useState<{ box: number | null; indices: readonly number[] }>({
    box: null,
    indices: [],
  })
  const layouts = useMemo(
    () => (boxRecords.length === 0 ? NO_LAYOUTS : layoutsOf(boxRecords)),
    [boxRecords],
  )

  /* WALK TO A COPY — the one thing this screen asks the walk to do, and the mirror of `selected`
   * coming back the other way.
   *
   * D7 keeps every copy of a card at its own position, so the copies list under the card is
   * routinely a list of other boxes. Pressing one of those positions is the shortest way to
   * "show me THAT one" — the walk switches box, marks the card, and the photograph, the facts,
   * the box operations and the queue block all follow, because every one of them is already
   * drawn for whatever the walk points at.
   *
   * A COUNTER BESIDE THE KEY because the same copy can be asked for twice: walk to it, arrow
   * away, press it again. `BoxBrowse` ignores a request it has already answered, so this may be
   * held in state without a re-render replaying yesterday's jump. */
  const [goTo, setGoTo] = useState<{ key: string; at: number } | null>(null)
  const walkTo = useCallback(
    (copy: SearchCopy) => setGoTo((asked) => ({ key: copy.key, at: (asked?.at ?? 0) + 1 })),
    [],
  )

  /* Bumped after every write, and read by the walk as a re-read trigger and by the copies panel
   * as a re-search trigger. The walk holds no copy of the inventory to patch and this file holds
   * no copy of anything, so a write's only honest follow-up is to ask again. */
  const [reloads, setReloads] = useState(0)

  /* The copy waiting on a retire panel, or null. THERE IS NO SALE EQUIVALENT SINCE D57 — this
   * sat beside a `pending` that held the copy waiting on a photo-confirm, and the sale writes on
   * one press now.
   *
   * THE SIBLING WRITE KEEPS ITS PANEL AND THE REASON IS NOT SYMMETRY (D26): a retirement without
   * a reason is refused (`retire_reason_invalid`), so the four reason buttons ARE the confirm and
   * there is no redundant press here to take away. D57 removed a press that asked "did you mean
   * it" about a photograph already on screen; this one asks a question with four answers. */
  const [retiring, setRetiring] = useState<SearchCopy | null>(null)

  /* One write in flight at a time, by copy key. `Store.write()` takes the file lock per call, so
   * several at once stack against a lock and return their failures out of order — the same
   * reason the review screen serialises. */
  const [busyKey, setBusyKey] = useState<string | null>(null)

  /* Receipts — sales and retirements — still inside their undo window, newest first. */
  const [receipts, setReceipts] = useState<Receipt[]>([])

  /* Copies this screen has sold and the wire has not caught up with yet. An optimistic overlay
   * and nothing more — `CardLocations.soldKeys` is documented as exactly that. It outlives the
   * receipt on purpose: the undo window closes after twenty seconds, and the row must not go
   * back to offering to sell a card that is already gone. */
  const [sold, setSold] = useState<string[]>([])

  /* The same overlay for the sibling write. Two lists rather than one because the row draws a
   * different word for each — `sold` and `retired` are two different doors out, and a combined
   * "gone" list would erase which one the copy left by until the next read. */
  const [retired, setRetired] = useState<string[]>([])

  /* A refusal from a write or an undo, as an owner-side screen draws it. Screen-wide rather than
   * per-write because it belongs to something that produced no receipt to hang it on; the `note`
   * field carries the per-write case, which is the split Fulfillment.tsx arrived at after a
   * failed-undo message outlived the button it told you to press. */
  const [trouble, setTrouble] = useState<Failure | null>(null)

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline rather than one per write.
   * Fulfillment.tsx's shape, and the slack at the end is its finding too: a timer that fired a
   * hair early would drop nothing, return an array of the same length, and React would bail out
   * on the identical reference — leaving the receipt up forever with nothing to re-arm it. */
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

  /* Escape closes the retire panel. It closed the photo-confirm too until D57 took that panel
   * away; one panel is left and the key still has to work, because a panel is a decision point
   * and not a destination.
   *
   * WHAT DOES NOT FOLLOW FROM THIS: that the sale wanted the same key. Escape is the way OUT of
   * an unanswered question, and the sale no longer asks one — its way back is `Undo`, in the row
   * and on the receipt, which is docs/DESIGN.md's own remedy for a reversible action. */
  useEffect(() => {
    if (retiring === null) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setRetiring(null)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [retiring])

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
      setRetiring(null)

      /* The label, or the pooled fact — `Place.label` is null for a pooled copy (types.ts, on
       * the field), and a receipt still needs a line the owner can grep. */
      const seat = {
        key: copy.key,
        box: copy.place.box,
        index: copy.place.index,
        place: copy.place.label ?? `pooled · ${copy.key}`,
      }
      try {
        const reversible = canTakeBack(await markSold(copy.place.box, copy.place.index))
        setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        // "Mark sold" produced "Marked sold." — docs/DESIGN.md's copy rule that an action keeps
        // its name through the whole flow.
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
        // Both the walk and the copies panel are now one copy stale. Re-read rather than patch:
        // D13 has one place inventory lives, and this screen's whole rule is that it holds no
        // second copy of it.
        setReloads((n) => n + 1)
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          /* Not this device's sale — see the ruling at ALREADY_SOLD. A receipt rather than a
           * failure, because that is what it is: a copy left the boxes and the owner did not do
           * it. No undo, deliberately; it would reverse the other device's real sale. */
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
      setRetiring(null)

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
        // "Retire" produced "Retired." — the same copy rule the sale follows. The machine word
        // for WHY sits in the note, greppable against the history line it landed in.
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
      } catch (err) {
        if (refusalCode(err) === ALREADY_RETIRED) {
          /* The other device's retirement — the sibling of ALREADY_SOLD's ruling, adopted whole:
           * a receipt with no undo, because the undo would reverse a departure this device
           * never recorded. */
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
        /* `not_sold` / `not_retired` is success — the copy is not in the state the press asked
         * to leave, which is what it asked for. Each is read only against its own route:
         * `not_retired` from the sale route would be a bug worth seeing, not a success to
         * swallow. Anything else keeps the receipt standing so the control is still there to
         * press. */
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
      setReloads((n) => n + 1)
      setBusyKey(null)
    },
    [busyKey],
  )

  const soldKeys = useMemo(() => new Set(sold), [sold])
  const retiredKeys = useMemo(() => new Set(retired), [retired])

  /** The sales a row may still take back, by copy key. D57's half of the undo, and the reason
   *  it is a MAP rather than a set beside `soldKeys`: the row's press calls `doUndo`, which
   *  needs the box, the index and the kind, and a key alone cannot rebuild them.
   *
   *  `kind === 'sale'` IS LOAD-BEARING AND NOT A TIDY-UP. `remember` dedupes by key across both
   *  writes, so one position holds one receipt — without the filter a RETIREMENT's receipt would
   *  put an Undo in the row's `retired` branch, which nobody ruled on. D26's write keeps its
   *  panel and keeps its undo on the receipt alone.
   *
   *  `canUndo` FALLS OUT HERE, which is what makes the two dead ends draw the plain word:
   *  `already_sold` is another device's sale and `sold_origin_unknown` has no state to put back,
   *  and in both cases the receipt below carries the sentence a row has no room for.
   *
   *  NOTHING CHECKS `until`. Dropping an expired receipt is the timer's job above, and a second
   *  clock read here would be a second opinion about when the window closed. */
  const undoableSales = useMemo(
    () =>
      new Map(
        receipts
          .filter((receipt) => receipt.kind === 'sale' && receipt.canUndo)
          .map((receipt) => [receipt.key, receipt] as const),
      ),
    [receipts],
  )

  /* THE PRESS IS THE SALE AS OF 2026-08-30 (D57). This was `openSell`, which set `pending` and
   * wrote nothing until a photo-confirm was answered. `doSell` already refuses a second write
   * while one is in flight and already clears `trouble`, so what is left of the old body is the
   * one thing the sale still has to do to its sibling: a retire panel standing over another copy
   * is a question about a different card, and leaving it up over a sale that has just landed
   * would leave two writes on screen at once. */
  const sell = useCallback(
    (copy: SearchCopy) => {
      setRetiring(null)
      void doSell(copy)
    },
    [doSell],
  )

  const undo = useCallback((receipt: Receipt) => void doUndo(receipt), [doUndo])

  const openRetire = useCallback((copy: SearchCopy) => {
    setTrouble(null)
    setRetiring(copy)
  }, [])

  /* THE RECEIPTS SIT ABOVE THE COPIES AND INSIDE THE SAME NODE, which is Fulfillment.tsx's
   * finding rather than a layout preference. They were rendered inside one branch there, so
   * walking away hid the Undo while its clock kept running — a twenty-second promise on screen
   * for two. Here the equivalent is stepping to the next card: the copy rows are replaced and
   * the window is still open. Held in this component's state and drawn above the rows, the
   * receipt survives the rows moving under it.
   *
   * ONE PANEL SHAPE FOR BOTH KINDS. A sale's receipt and a retirement's differ only in their
   * sentence and their note; `kind` is `doUndo`'s to branch on and nothing rendered here reads
   * it.
   *
   * IT IS NOW THE SECOND UNDO ON A SALE AND STILL THE ONLY ONE THAT SURVIVES (D57). The row's
   * own slot draws an `Undo` too, which is the one under the hand — but the rows are unmounted
   * by stepping the walk, by a query matching nothing, and by a failed re-read (`useSearch`
   * clears its results on a failure, deliberately), and the clock does not stop for any of the
   * three. So this is not redundancy: it is the control the paragraph above was written for,
   * and deleting it would make a twenty-second promise good for as long as you stand still.
   *
   * AND IT IS THE ONLY PLACE `already_sold` AND `sold_origin_unknown` CAN SPEAK. Both come back
   * `canUndo: false`, so the row correctly draws the plain word `sold`; the sentence saying WHY
   * there is no way back needs a line of prose, and a 32px slot in a copy row has none.
   *
   * NO FILL, AND AS OF D57 THERE IS NONE LEFT ANYWHERE ON THIS SCREEN. docs/DESIGN.md reserves
   * the solid accent for a screen with exactly one thing to do; the photo-confirm panel used to
   * be it and it is gone. That is the rule satisfied rather than broken — it says where a fill
   * MAY go, never that a screen must have one, and `#/runs` draws none either. */
  const receiptPanels = receipts.map((receipt) => (
    <div className="inventory-receipt" key={receipt.key}>
      <p className="inventory-receipt-said">{receipt.said}</p>
      <p className="inventory-receipt-place">{receipt.place}</p>
      {receipt.note === null ? null : <p className="inventory-machine">{receipt.note}</p>}
      {!receipt.canUndo ? null : (
        /* The position is in the accessible name and not on the button. Two receipts standing at
           once make two controls that both read "Undo" to anything that cannot see the panel
           they sit in; the visible word stays one word, which is what the copy rules ask of a
           control.

           AND SINCE D57 A THIRD CONTROL CAN BE LIVE FOR THE SAME SALE — the copy row's own
           `Undo`, which names itself `Undo the sale at <place>` for exactly the reason above.
           The two strings are deliberately different rather than deliberately the same: they
           reverse one write from two places, and a reader that cannot see the layout has no
           other way to tell them apart. `Action` carries the other half of this pair; change
           neither string without the other. */
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

  const detail = (
    <div className="inventory-detail">
      {trouble === null ? null : (
        <div className="inventory-note">
          <p className="inventory-note-text">{trouble.message}</p>
          {/* The code beneath the sentence, never the sentence again — docs/DESIGN.md's
              human-label-large, machine-string-small rule. What goes here is the greppable
              token, which is the only way from what is on screen to what the server said. */}
          <p className="inventory-machine">{trouble.code}</p>
        </div>
      )}

      {receiptPanels.length === 0 ? null : (
        <div className="inventory-receipts">{receiptPanels}</div>
      )}

      {selected === null ? null : (
        <CopiesPanel
          row={selected}
          layouts={layouts}
          reloadToken={reloads}
          busyKey={busyKey}
          soldKeys={soldKeys}
          retiredKeys={retiredKeys}
          undoableSales={undoableSales}
          onSell={sell}
          onUndo={undo}
          onRetire={openRetire}
          onGoTo={walkTo}
        />
      )}
    </div>
  )

  return (
    <main className="inventory">
      <BoxBrowse
        head={<h1 className="inventory-title">Inventory</h1>}
        detail={detail}
        onSelect={setSelected}
        onBoxes={setBoxRecords}
        onScope={setRunScope}
        goTo={goTo}
        reloadToken={reloads}
        /* THE PIPELINE IS NO LONGER HERE, AND THIS IS WHAT IT LEFT BEHIND (D39). Until 2026-08-29
           this slot held `RunPanel` whole, on D33's reasoning — a run is something you do to
           the box you are looking at, or to the cards you have just ticked in it, and a route
           of its own would have to re-implement the box strip, the search and the mass-select.
           The owner moved it anyway; `#/runs` answers the box half with a picker of its own and
           the SELECTION half by taking it from here, which is the one place in the product a
           selection can be made.

           SO WHAT STAYS IS THE HANDOFF AND THE ONE FACT WORTH A LINE — is anything running over
           this box. `BoxRuns.tsx` carries both arguments; what matters at this call site is that
           it is one row and can never become two.

           `boxPanel` AND NOT `detail`, and the difference is not cosmetic: `detail` is drawn
           only when a card is selected. The run panel went there first and vanished whenever
           the walk had nothing picked, which made starting a run require choosing a card in the
           box — a step with no reason behind it that a person could have worked out. The same
           trap is live for the handoff, which is about the BOX and the ticks, never about a
           card. */
        boxPanel={<BoxRuns box={runScope.box} indices={runScope.indices} />}
      />

      {retiring === null ? null : (
        <RetirePanel
          copy={retiring}
          sections={layouts.get(retiring.place.box)}
          busy={busyKey !== null}
          onRetire={(reason) => void doRetire(retiring, reason)}
          onCancel={() => setRetiring(null)}
        />
      )}
    </main>
  )
}

/* EVERY COPY OF THE SELECTED CARD, AND WHERE EACH ONE SITS — D7's SKU -> positions map, drawn
 * for the one card the walk is pointing at.
 *
 * THIS IS WHERE THE FIND MODE WENT, and the owner's sentence is the whole design brief: "it's
 * basically find a card in a box-based system if anything". You search, the walk narrows, you
 * pick a card, and its copies are right here — with the sale, the retirement, the listing
 * quantities and the live cap that used to live on a separate mode.
 *
 * `GET /search` STAYS THE MATCHER AND NOTHING HERE FILTERS THE INVENTORY LOCALLY. The handle
 * this panel asks with is the card's own SKU, or its name when it has no SKU — and the group it
 * keeps is the one whose copies CONTAIN this row's store key, which is an exact test rather than
 * a guess about which of several groups was meant. That matters: `do_search` matches on six
 * fields, so a SKU that happens to be a substring of another card's note comes back as a second
 * group, and picking by key cannot be fooled by it.
 *
 * WHY THE SEARCH ROUTE RATHER THAN THE INVENTORY THIS SCREEN ALREADY HAS. Three numbers, none of
 * which `GET /inventory` carries: `on_hand` (D7's count of unsold positions, which is not
 * `copies.length`), `listed` (per-SKU quantities since D7's amendment moved them off the card),
 * and `cap` — the live quantity cap, which `Inventory.tsx` refused for years to write in
 * TypeScript because it is a configurable Python constant. The search route reports all three,
 * which is exactly the condition that refusal named as settling it.
 *
 * IT DEBOUNCES, WHICH IS WHY HOLDING AN ARROW KEY DOES NOT SPAM THE STORE. `useSearch`'s timer
 * restarts on every query change, so walking a box at auto-repeat pace issues one request when
 * the hand stops. That is the same property the typed search relies on, reused rather than
 * re-derived.
 */
function CopiesPanel({
  row,
  layouts,
  reloadToken,
  busyKey,
  soldKeys,
  retiredKeys,
  undoableSales,
  onSell,
  onUndo,
  onRetire,
  onGoTo,
}: {
  row: Row
  layouts: ReadonlyMap<number, readonly SectionDetail[]>

  /** Bumped by the screen after a write. The panel's own query has not changed — it is still
   *  the same card — so nothing would re-ask without this, and the header's `on hand` and
   *  `listed N of 4` would sit one copy stale behind a row that had already updated. */
  reloadToken: number

  busyKey: string | null
  soldKeys: ReadonlySet<string>
  retiredKeys: ReadonlySet<string>

  /** The sales still inside their undo window, by copy key (D57). Passed through to `Action`
   *  and read nowhere else here — this panel decides nothing about which sale is reversible,
   *  it only hands the screen's answer to the slot that draws it. */
  undoableSales: ReadonlyMap<string, Receipt>

  onSell: (copy: SearchCopy) => void
  onUndo: (receipt: Receipt) => void
  onRetire: (copy: SearchCopy) => void

  /** Point the walk at one copy. Handed straight to `CardLocations`, which draws it on every
   *  row but the one already selected — the lone-copy fallback below deliberately gets nothing,
   *  because that copy IS the card the walk is standing on. */
  onGoTo: (copy: SearchCopy) => void
}) {
  const { query, setQuery, results, loading, failure, reload } = useSearch()

  /* The handle the server is asked with: the SKU if the card has one, else its name. Null for a
   * card the pipeline has never identified, which is the case `loneCopy` exists for. */
  const handle = skuOrName(row.card)

  useEffect(() => {
    setQuery(handle ?? '')
  }, [handle, setQuery])

  /* Re-ask on a write, and NEVER on the first render. A ref rather than a boolean state because
   * this is bookkeeping about renders and not a fact the screen draws — and because a state
   * would re-render to record that it had not needed to. */
  const seen = useRef(reloadToken)
  useEffect(() => {
    if (seen.current === reloadToken) return
    seen.current = reloadToken
    reload()
  }, [reloadToken, reload])

  /* MATCHED BY KEY, NOT BY SKU. This row's own store key is in exactly one group, whichever way
   * the query matched — so a name search that returns four cards, or a SKU that is a substring
   * of somebody's note, both resolve to the right group without a second rule. */
  const group =
    results === null
      ? null
      : (results.groups.find((candidate) =>
          candidate.copies.some((copy) => copy.key === row.key),
        ) ?? null)

  /* The answer is for the card being asked about only when the query the server echoed is the
     one this panel asked. Otherwise it is the previous card's answer still on screen, and the
     honest thing is to say we are looking rather than to draw somebody else's copies. */
  const settled = results !== null && results.query === (handle ?? '')

  if (handle === null) {
    /* No SKU and no name, so there is no card group to fetch and none is invented. 22% of the
       store is in this state today — box 95 and box 99 are 170 captured-and-never-identified
       records — and it is exactly the state in which D26's retirement matters most. */
    const lone = loneCopy(row)
    return (
      <section className="inventory-copies">
        <p className="inventory-note-text">
          This card has no name and no SKU yet, so there is no card group to show — it is one
          copy at one position. A SKU is written when <code className="inventory-inline">emit</code>{' '}
          writes the card&rsquo;s row into an import file, and never before.
        </p>
        {lone === null ? (
          <p className="inventory-machine">place: absent · key {row.key}</p>
        ) : (
          <div className="inventory-lone">
            <span className="inventory-lone-place">{lone.place.label ?? `pooled · ${row.key}`}</span>
            {/* THE TWO DEPTHS REACH THE 92% OF THE STORE THAT HAS NO GROUP. This is where they
                matter most and where they were nearly left out: 629 of the 682 records on this
                Mac are captured-and-never-identified, so `GET /search` cannot reach them and
                every one of them takes this branch. A feature that drew both bars only for the
                53 identified cards would have answered "how far into the section is this" for
                8% of the boxes the owner actually walks to.

                NEVER FOR A POOLED CARD (D24). It is a count and not a location, so there is no
                box to draw and no section to be inside — the same refusal `CardLocations` makes
                on its own rows, and `sectionDepthOf` refuses the second scale for it besides.
                The label slot above already says the pooled fact where the position would be. */}
            {lone.place.located === false ? null : (
              <PositionBar
                place={lone.place}
                persona="owner"
                sections={layouts.get(lone.place.box)}
                sectionDepth
              />
            )}
            <Action
              copy={lone}
              busyKey={busyKey}
              soldKeys={soldKeys}
              retiredKeys={retiredKeys}
              undoableSales={undoableSales}
              onSell={onSell}
              onUndo={onUndo}
              onRetire={onRetire}
            />
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="inventory-copies">
      {failure === null ? null : (
        <div className="inventory-note">
          <p className="inventory-note-text">{failure.message}</p>
          <p className="inventory-machine">{failure.code}</p>
        </div>
      )}

      {/* `loading` is true through the debounce as well as the request, so this is the honest
          answer to "are the copies below this card's copies". Drawn beside the previous answer
          rather than instead of it — a panel that blanked on every arrow keypress would flicker
          the length of a box walk. */}
      {loading || !settled ? <p className="inventory-note-text">Looking for the copies.</p> : null}

      {group === null && settled && !loading ? (
        <p className="inventory-note-text">
          The search did not return this card&rsquo;s own row, which should not happen — its key
          is <span className="inventory-inline">{row.key}</span> and the query was{' '}
          <span className="inventory-inline">{query}</span>.
        </p>
      ) : null}

      {group === null ? null : (
        /* `sections` IS THE WHOLE MAP AND NOT THIS BOX'S SLICE, because a group is a SKU and not
           a box. D7 keeps every copy at its own position, so the rows of one group can run
           across boxes that are divided differently — picking a layout out here would mean
           picking one for a set of copies that do not share one. `CardLocations` looks it up per
           copy off `place.box`, which is the only place the right answer is known. */
        <CardLocations
          group={group}
          persona="owner"
          sections={layouts}
          currentKey={row.key}
          onGoTo={onGoTo}
          onSell={onSell}
          busyKey={busyKey}
          soldKeys={soldKeys}
          renderAction={(copy) => (
            <Action
              copy={copy}
              busyKey={busyKey}
              soldKeys={soldKeys}
              retiredKeys={retiredKeys}
              undoableSales={undoableSales}
              onSell={onSell}
              onUndo={onUndo}
              onRetire={onRetire}
            />
          )}
        />
      )}
    </section>
  )
}

/** The handle the copies search asks with. SKU first because it is exact and a card has at most
 *  one; the name second because a card that has been identified but never emitted has no SKU and
 *  its name still finds every copy of it. Null when the record carries neither. */
function skuOrName(card: InventoryCard): string | null {
  const sku = card.sku
  if (sku !== null && sku.trim() !== '') return sku.trim()
  const name = card.name
  if (name !== null && name.trim() !== '') return name.trim()
  return null
}

/** What one copy row offers: the word for the door it left by, or the two writes.
 *
 *  ONE COMPONENT FOR BOTH CALL SITES — the group's rows and the lone copy above — so the rule
 *  about which copies may be sold is written once. D7 as amended: every copy that has not left
 *  is sellable, and `sold` and `retired` are the only two words there are to compare against,
 *  because `pushed`/`staged`/`live` stopped being card states.
 *
 *  THE OPTIMISTIC OVERLAYS ARE READ HERE and not only on the wire's `state`, so a row stops
 *  offering to sell a card in the seconds between the write returning and the re-read landing. */
function Action({
  copy,
  busyKey,
  soldKeys,
  retiredKeys,
  undoableSales,
  onSell,
  onUndo,
  onRetire,
}: {
  copy: SearchCopy
  busyKey: string | null
  soldKeys: ReadonlySet<string>
  retiredKeys: ReadonlySet<string>
  undoableSales: ReadonlyMap<string, Receipt>
  onSell: (copy: SearchCopy) => void
  onUndo: (receipt: Receipt) => void
  onRetire: (copy: SearchCopy) => void
}) {
  if (copy.state === 'sold' || soldKeys.has(copy.key)) {
    /* THE UNDO IS INSIDE THE SOLD BRANCH AND NOT AHEAD OF IT (D57), which is forced rather than
       stylistic: `doSell` sets the optimistic `soldKeys` overlay in the same continuation as the
       receipt, so the very next render is already down here. A branch above this one would be
       unreachable, and unreachable code that looks like the feature is worse than none.
       `undoableSales` has already filtered to sales that CAN be reversed, so `already_sold` and
       `sold_origin_unknown` fall through to the plain word with the receipt carrying their
       sentence.

       `Undo` ALONE, WITH NO `Retire` BESIDE IT, which is what this slot already did for a sold
       copy: the server refuses the retirement of a sold card (`already_sold` on that route), so
       drawing the second control would be drawing one that can only fail.

       ITS ACCESSIBLE NAME IS NOT THE RECEIPT'S. Two live controls reverse this one sale and a
       screen reader announces both; identical names would leave them indistinguishable, which is
       the failure the receipt's own label was written to avoid one register down. Composed from
       `receipt.place` and never from `copy.place.label`, because that is null for a pooled copy
       (D24) and the receipt's copy already carries the `pooled · key` fallback. */
    const standing = undoableSales.get(copy.key)
    return standing === undefined ? (
      <span className="card-locations-gone">sold</span>
    ) : (
      <button
        className="card-locations-sell"
        type="button"
        aria-label={`Undo the sale at ${standing.place}`}
        disabled={busyKey !== null}
        onClick={() => onUndo(standing)}
      >
        Undo
      </button>
    )
  }
  if (copy.state === 'retired' || retiredKeys.has(copy.key)) {
    return <span className="card-locations-gone">retired</span>
  }
  return (
    <span className="inventory-copy-actions">
      {/* No accent fill on either, and since D57 there is none on this screen at all.
          docs/DESIGN.md reserves the solid fill for a screen with exactly one thing to do, and a
          copy row with two doors out of inventory is not that.

          THE GUARD IS NOW ASYMMETRIC AND THAT IS THE RULING, NOT AN OVERSIGHT. `Retire` still
          opens a panel, because a retirement without a reason is refused and the four reasons ARE
          the confirm. `Mark sold` writes on this press: the photograph it used to confirm against
          is already on screen in the card band, and the way back is the `Undo` this slot draws
          for twenty seconds plus the receipt above.

          WHAT GUARDS THE OVERSHOOT IS `busyKey` AND NOTHING ELSE (the owner's choice, D57).
          Fulfillment.css records the opposite ruling for the same failure — it displaces the
          second control out of the first one's footprint, because a double-tap there once sold a
          card whose photo he never saw — and a reader will find that first, so: it was offered
          and declined for this screen. The honest caveat is that against a local server the gate
          reopens in milliseconds, so it does not span a human double-tap; what does cover it here
          is that the slot SHRINKS to one right-packed control, vacating the coordinate `Mark
          sold` was under, and that a receipt appearing above pushes the whole list down. If a
          real mis-sale ever happens, `.fulfillment-step`'s displacement is the fix to reach for
          — not the panel this replaced. */}
      <button
        className="card-locations-sell"
        type="button"
        disabled={busyKey !== null}
        onClick={() => onSell(copy)}
      >
        Mark sold
      </button>
      <button
        className="card-locations-sell"
        type="button"
        disabled={busyKey !== null}
        onClick={() => onRetire(copy)}
      >
        Retire
      </button>
    </span>
  )
}

/* The retire panel — the one panel left on this screen, and the last reader of `.inventory-scrim`
 * and `.inventory-confirm*`.
 *
 * IT HAD A SIBLING UNTIL 2026-08-30 (D57) and the rules below were written against the pair:
 * `Confirm` was the sale's photo-confirm and this shared its scrim, its photo and its bar so
 * what the owner confirmed against was the same picture on both writes. The sale writes on one
 * press now and that component is gone.
 *
 * WHY THIS ONE SURVIVED, WHICH IS THE PART A LATER SESSION WILL ASK. D57 removed a press that
 * asked "did you mean it" about a photograph the card band already draws — the confirm
 * docs/DESIGN.md bans on a reversible action. This panel asks something else: a retirement
 * without a reason is refused (`retire_reason_invalid`), so the four reason buttons are not an
 * acknowledgement, they are the write's only input. Take them away and there is nothing to send.
 *
 * FOUR ANSWERS, SO NO FILL. docs/DESIGN.md gives the solid accent to a screen with exactly one
 * thing to do, and this panel is a choice — filling one reason would teach the queue's "a screen
 * with two answers gets no fill" rule a counterexample on the next screen over. The reason
 * buttons are the confirm: pressing one writes the retirement, pressing nothing writes nothing,
 * and Escape or the scrim leaves. There is no separate "Retire" button to press after the
 * reason, because the reason IS the decision — a second press would be the acknowledgement
 * dialog the design bans.
 *
 * FOCUS LANDS ON CANCEL, not on a reason. Focusing any reason would make Enter answer a question
 * the owner has not read yet, and the four are not ranked. Cancel is the one control whose
 * accidental press costs nothing. */
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
            No photo is stored for this position, so there is nothing to check the card against.
            The copy is still recorded at the position below.
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

        {/* Both scales, as on the sale panel above and for its reason. */}
        <PositionBar place={copy.place} persona="owner" sections={sections} sectionDepth />

        {/* What the choice does, before the choices: the record stays, the gap stays. Kept to one
            sentence — the panel is a decision point, not documentation. */}
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
