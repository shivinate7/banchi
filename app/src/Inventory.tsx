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
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { PullConfirm } from './PullConfirm'
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
 * D7's SKU -> positions map is `CopiesPanel` below; the sale keeps its photo-confirm, its
 * receipt and its twenty-second undo; D26's retirement keeps all three; `already_sold` is still
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
  const layouts = useMemo(
    () => (boxRecords.length === 0 ? NO_LAYOUTS : layoutsOf(boxRecords)),
    [boxRecords],
  )

  /* Bumped after every write, and read by the walk as a re-read trigger and by the copies panel
   * as a re-search trigger. The walk holds no copy of the inventory to patch and this file holds
   * no copy of anything, so a write's only honest follow-up is to ask again. */
  const [reloads, setReloads] = useState(0)

  /* The copy waiting on a photo-confirm, or null. THE PHOTO IS THE GUARD — see the header: this
   * is half of what the objection asked for, and it is why pressing Mark sold on a row writes
   * nothing on its own. */
  const [pending, setPending] = useState<SearchCopy | null>(null)

  /* The copy waiting on a retire panel, or null. The same guard for the sibling write (D26):
   * pressing Retire writes nothing on its own — the panel shows the copy's stored photo at its
   * position, and the write happens only when a REASON is chosen, since a retirement without
   * one is refused (`retire_reason_invalid`) and the choice is the confirm. At most one of
   * `pending` and this is non-null: opening either closes the other at the call sites, because
   * two stacked scrims is two answers to "what am I about to do". */
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

  /* Escape closes whichever panel is up — the photo-confirm, or the retire panel, which is the
   * same decision point for the sibling write. A panel is a decision point and not a
   * destination, so the key that means "I did not mean this" has to work — and docs/DESIGN.md's
   * no-dialog rule is about REVERSIBLE actions, which is what makes a confirm legal here. */
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
      setPending(null)
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

  const openSell = useCallback((copy: SearchCopy) => {
    setTrouble(null)
    setRetiring(null)
    setPending(copy)
  }, [])

  const openRetire = useCallback((copy: SearchCopy) => {
    setTrouble(null)
    setPending(null)
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
   * NO FILL. docs/DESIGN.md reserves the solid accent for a screen with exactly one thing to
   * do, and a receipt is the way back from something already done. The confirm panel is the one
   * place on this screen that qualifies, and it keeps the only fill. */
  const receiptPanels = receipts.map((receipt) => (
    <div className="inventory-receipt" key={receipt.key}>
      <p className="inventory-receipt-said">{receipt.said}</p>
      <p className="inventory-receipt-place">{receipt.place}</p>
      {receipt.note === null ? null : <p className="inventory-machine">{receipt.note}</p>}
      {!receipt.canUndo ? null : (
        /* The position is in the accessible name and not on the button. Two receipts standing at
           once make two controls that both read "Undo" to anything that cannot see the panel
           they sit in; the visible word stays one word, which is what the copy rules ask of a
           control. */
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
          onSell={openSell}
          onRetire={openRetire}
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
        reloadToken={reloads}
      />

      {pending === null ? null : (
        <Confirm
          copy={pending}
          /* THE PANEL GETS ONE BOX'S LAYOUT, because the panel holds exactly one copy and the
             box it is in is already known here. Looking it up at the call site rather than
             handing a whole map to a component with one place to draw is the same reason
             `CardLocations` takes the map: each is given the shape its own job needs. */
          sections={layouts.get(pending.place.box)}
          busy={busyKey !== null}
          onConfirm={() => void doSell(pending)}
          onCancel={() => setPending(null)}
        />
      )}

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
  onSell,
  onRetire,
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
  onSell: (copy: SearchCopy) => void
  onRetire: (copy: SearchCopy) => void
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
            <Action
              copy={lone}
              busyKey={busyKey}
              soldKeys={soldKeys}
              retiredKeys={retiredKeys}
              onSell={onSell}
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
          onSell={onSell}
          busyKey={busyKey}
          soldKeys={soldKeys}
          renderAction={(copy) => (
            <Action
              copy={copy}
              busyKey={busyKey}
              soldKeys={soldKeys}
              retiredKeys={retiredKeys}
              onSell={onSell}
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
  onSell,
  onRetire,
}: {
  copy: SearchCopy
  busyKey: string | null
  soldKeys: ReadonlySet<string>
  retiredKeys: ReadonlySet<string>
  onSell: (copy: SearchCopy) => void
  onRetire: (copy: SearchCopy) => void
}) {
  if (copy.state === 'sold' || soldKeys.has(copy.key)) {
    return <span className="card-locations-gone">sold</span>
  }
  if (copy.state === 'retired' || retiredKeys.has(copy.key)) {
    return <span className="card-locations-gone">retired</span>
  }
  return (
    <span className="inventory-copy-actions">
      {/* No accent fill on either. docs/DESIGN.md reserves the solid fill for a screen with
          exactly one thing to do, and a copy row with two doors out of inventory is not that —
          the confirm panel each of them opens is. The guard is not in the slot: each press opens
          a panel over the copy's own photograph, and the receipt above carries the undo. */}
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

/* The photo-confirm, and the first half of the answer to this file's own objection.
 *
 * D6 PUTS THE PHOTO SERVICE HERE FOR EXACTLY THIS: "the review queue requires it; the pull
 * modal reuses it, showing the card's own capture photo beside its location before pulling."
 * The pull modal is the Fulfiller's; this is the owner's, and the entry describes the operation
 * rather than the persona. What is being confirmed is not "did you mean to press that" —
 * docs/DESIGN.md bans that dialog outright — but "is the card in your hand the card at this
 * position", which is a question only a photograph can answer.
 *
 * ONE THING TO DO, SO IT GETS THE FILL. The rule is docs/DESIGN.md's: solid accent where there
 * is exactly one action, outline where the system is unsure. A confirm panel is the one shape on
 * this screen that qualifies, which is why `PullConfirm` is reused here rather than copied — the
 * same component step 6 built and the same fill it was measured in. Cancel is not a second
 * action in that sense; it is the way out, and it is drawn as the quiet control every other
 * owner-side screen uses.
 *
 * A MISSING PHOTO DOES NOT BLOCK THE SALE. `has_photo` says the server had bytes when it
 * answered, and undo deletes a photo — so the load can still fail between the search and this
 * panel. A card with no photograph is still a real card at a real position, and refusing to let
 * the owner sell it would make a display failure into an inventory one. The panel says plainly
 * that there is nothing to confirm against and leaves the decision where it was.
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

  /* Focus lands on the confirm button. A callback ref rather than `useRef` + an effect on mount,
   * because the node is what the effect is waiting for and a callback ref already fires when it
   * arrives.
   *
   * NO KEY CHIP, and its absence is the honest half of "every choice shows its key". The focused
   * button already takes Enter and Escape already cancels — both true without a listener of this
   * file's own. A chip saying so would be a hint about the browser's behaviour rather than about
   * a binding this screen owns, and a second Enter handler beside the focused button is how one
   * press fires twice. */
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

        {/* The same bar the row carries, so what the owner confirms against is what he chose the
            copy by. Nothing here is computed: `spansOf` draws the server's own numbers. */}
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

/* The retire panel — `Confirm`'s sibling for D26's write, sharing its scrim, its photo and its
 * bar so what the owner confirms against is the same picture on both writes.
 *
 * FOUR ANSWERS, SO NO FILL. docs/DESIGN.md gives the solid accent to a screen with exactly one
 * thing to do, and this panel is a choice — filling one reason would teach the queue's "a screen
 * with two answers gets no fill" rule a counterexample on the next screen over. The reason
 * buttons are the confirm: pressing one writes the retirement, pressing nothing writes nothing,
 * and Escape or the scrim leaves the way `Confirm` does. There is no separate "Retire" button to
 * press after the reason, because the reason IS the decision — a second press would be the
 * acknowledgement dialog the design bans.
 *
 * FOCUS LANDS ON CANCEL, not on a reason. `Confirm` focuses its one action because it has one;
 * focusing any reason here would make Enter answer a question the owner has not read yet, and
 * the four are not ranked. Cancel is the one control whose accidental press costs nothing. */
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

        <PositionBar place={copy.place} persona="owner" sections={sections} />

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
