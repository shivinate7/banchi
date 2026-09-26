import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type {
  BoxRecord,
  InventoryCard,
  Listing,
  RetireReason,
  RetireResult,
  SaleResult,
  SearchCopy,
  SearchGroup,
  SectionDetail,
} from './types'
import type { Failure } from './server'
import {
  ServerError,
  describeFailure,
  getOrders,
  isDeparted,
  markSold,
  moveCard,
  undoMove,
  photoUrl,
  retireCard,
  undoRetire,
  undoSale,
} from './server'
import { BoxBrowse, type Row } from './BoxBrowse'
import { BoxRuns } from './BoxRuns'
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { sayPlace } from './position'
import { RETIRE_REASONS, reasonWord } from './cardState'
import { useSearch } from './useSearch'
import {
  Button,
  Icon,
  IconButton,
  Loading,
  Notice,
  Page,
  Pill,
  Select,
  UNDO_KEY_LABEL,
  boxesMostRecentFirst,
  useUndoHotkey,
} from './kit'
import { UNNAMED_BOX } from './kit/data'
import { dismissToast, toast } from './kit/toast'
import { rememberHideSold, storedHideSold } from './deviceMemory'
import { RANK_IS_CURRENT, type FrozenRank } from './frozenRank'
import { Dialog as Overlay } from './kit/overlay'
import './Inventory.css'

/* THE INVENTORY — one owner-side view of stored cards: find a card by name or SKU, or walk a
 * box → section → card; see the photograph that proves what is in that slot; see every copy of
 * that card and where each one is; and record that a copy left — sold, retired, moved.
 *
 * `BoxBrowse` owns the walk, the box operations, the photograph and the card-level
 * corrections; this file owns the one flow that writes a card — the sale, the retirement, their
 * receipts and their undo — and draws the copies beside the photograph. Nothing
 * here holds a second copy of the inventory: every write is followed by a re-read.
 *
 * IT DREW A LOCATION CARD ABOVE THAT LIST UNTIL D119, and the copy the walk stands on is an
 * ordinary row of the list now. What that deletion moved here rather than losing is the
 * receipt: a sale is taken back where it was pressed.
 *
 * THE RECEIPT HAS NO CLOCK (`docs/specs/undo.md` §11.1, UN-5, D28 and D57 amended
 * 2026-09-25). Rank replaces it: the newest sale or retirement keeps its `Undo`, in the row
 * and on the page, until a newer one takes its place. `UNDO_WINDOW_MS` is only the toast's own
 * fade — a toast still fades; the undo does not fade with it. */

/** How long a receipt's TOAST stays on screen — the fade, never the undo. Fulfillment.tsx's
 *  number, kept in step. */
const UNDO_WINDOW_MS = 20_000

/* The refusal codes this screen branches on. `already_sold` on a sale is not this device's
 * sale: a receipt with NO undo. `not_sold` on a reversal is success. The retirement pair
 * applies the same two rulings. Codes, never messages. */
/* WHAT A RECEIPT SAYS WHEN THE STORE CANNOT PUT A COPY BACK (UX-207, D196): the stored reason
 * (`sold_origin_unknown`, `retired_origin_unknown`) stays off the screen. */
const NO_UNDO = 'No undo for this one.'

const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const ALREADY_RETIRED = 'already_retired'
const NOT_RETIRED = 'not_retired'
const NOT_MOVED = 'not_moved'

const NO_LAYOUTS: ReadonlyMap<number, readonly SectionDetail[]> = new Map()

/* Every SKU's listing record, keyed by SKU, as `GET /inventory` sends it. Read for ONE field —
 * `at`, the moment this store last wrote that SKU's pushed/staged/live figures — because a
 * live count with no age reads as a fact about TCGplayer when it is a fact about the last time
 * this store looked. `GET /search` carries the counts and no stamp, so the age is joined here
 * out of the same store record; see `CardLocations.tsx:ReadingAge`. */
const NO_LISTINGS: Readonly<Record<string, Listing>> = {}

/* Each box's divider layout, keyed by box number, out of the registry `BoxBrowse` already
 * read. Keyed by `box` so one box's dividers can never be handed to another box's card. */
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

function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/* Graveyard reads the one label table through here (UX review, 2026-09-20). */
export { reasonWord }

/** WHO TAKES THE NUMBER (UX-190). A card counts the cards in its section (D58, amended by
 *  D260), so when one leaves, the card in front of it (toward the
 *  owner, `neighbors.next`) takes its number, and every card after it steps down one. The rows
 *  hold still (FLT-22), so the receipt says it: `Tinkatink is now card 3.` Nothing when the card
 *  was the last of its section, when the store sent no neighbours, or for a pooled card. */
function renumberNote(place: SearchCopy['place']): string | null {
  const next = place.neighbors?.next ?? null
  if (next === null || place.card === null || place.slot === null) return null
  if (place.section_end !== null && place.slot >= place.section_end) return null
  const who = next.name ?? 'The unread card in front'
  return `${who} is now card ${place.card}.`
}

/** The receipt's second line, in sentences: who took the number, then any note. */
function receiptBody(place: string, ...lines: readonly (string | null)[]): string {
  const said = lines.filter((line): line is string => line !== null && line !== '')
  return said.length === 0 ? place : `${place}. ${said.join(' ')}`
}

/** An open order that names one copy, by the copy's store key (`3/103`). */
type Wanted = { order: string; key: string }
const NOBODY: ReadonlyMap<string, Wanted> = new Map()

/* The three states `store/master.py:TERMINAL_STATES` names — gone from the box, permanently.
   `moved` is one of them and is not a retire reason: the card is fully sellable at a new key.
   Written once because two readers here need it — which copies an open order can still be
   waiting on, and whether the lone card below is still on hand.

   TAKES A NULLABLE STATE because one of those readers has one: a resolver pick carries
   `state: string | null`, and an unknown state is not a departure. */
const GONE: ReadonlySet<string> = new Set(['sold', 'retired', 'moved'])
function gone(state: string | null): boolean {
  return state !== null && GONE.has(state)
}

/* Which on-hand copies an open order is waiting on, out of the resolver's own picks — so a copy
 * about to be pulled for an order says so before it is marked sold as a walk-in sale. A pulled
 * copy already reads `Sold`; only the ones still on hand are named. */
function wantedOf(payload: Awaited<ReturnType<typeof getOrders>>): ReadonlyMap<string, Wanted> {
  const out = new Map<string, Wanted>()
  for (const order of payload.resolution?.orders ?? []) {
    for (const line of order.lines) {
      for (const pick of line.picks) {
        if (pick.held_by !== null) continue
        if (gone(pick.state)) continue
        const at = `${pick.box}/${pick.index}`
        if (!out.has(at)) out.set(at, { order: line.order, key: line.order_key })
      }
    }
  }
  return out
}

/** Whether the write just recorded can be taken back, out of the server's own answer. Absent
 *  is read as null and the direction is the safe one. */
function canTakeBack(result: SaleResult | RetireResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

/** One physical copy, built out of an inventory row, for the one card the search cannot reach
 *  — a card the pipeline has never identified has neither a SKU nor a name. Not a group and
 *  never one: the group facts are absent because there is no group. */
function loneCopy(row: Row): SearchCopy | null {
  const place = row.card.place
  if (place === undefined) return null
  return {
    key: row.key,
    state: row.card.state,
    state_at: row.card.state_at,
    /* D90's aim key, carried here too. `GET /search` sends one per copy so a pull can be aimed
       without walking to the card first; a copy built locally from an inventory row has the same
       fact on its card and must pass it on, or this one copy is the only one in the product that
       cannot be aimed at. */
    capture_id: row.card.capture_id,
    has_photo: row.card.photo !== null,
    place,
  }
}

/** The one-copy group for the card the search cannot reach, and IT IS A LOCAL FICTION — the
 *  only `SearchGroup` in this app that no server sent.
 *
 *  SO IT IS SHAPED TO BE THE ANSWER THE SERVER WOULD HAVE GIVEN, field for field, rather than
 *  to whatever this panel finds convenient. `capture_server.py:do_search` already builds a
 *  SKU-less group — the loose bag, for cards that matched a query and carry no SKU — and every
 *  value below is that branch's own expression evaluated over a bag of exactly one card. This
 *  function exists only because that branch cannot be REACHED for these seven cards:
 *  `GET /search` refuses an empty query, a card with no SKU and no name has no query, and so
 *  the store cannot be asked a question whose answer it already knows how to compose.
 *
 *  NOTHING HERE IS COMPUTED THAT THE SERVER COMPUTES. `listable` is `on_hand`, which is what
 *  `do_search` sends now that there is no standing cap (D7, rewritten 2026-09-07; the `cap`
 *  field this fiction once carried left the wire with it) — NOT zero. Zero would be a truer-sounding sentence ("No copies
 *  can go live") arrived at by inventing a number the store would contradict; the header stops
 *  drawing that sentence instead (`CardLocations.tsx:OwnerRows`, keyed off `sku === null`),
 *  which fixes the SKU-less bag on the search path in the same move. */
function loneGroup(row: Row, copy: SearchCopy): SearchGroup {
  const held = gone(row.card.state) ? 0 : 1
  return {
    sku: null,
    /* `skuOrName` proved the name is null or blank, and `_distinct` over one blank is empty. */
    names: [],
    number: row.card.number,
    printed_total: row.card.printed_total,
    number_display: row.card.number_display ?? null,
    set_hint: row.card.set_hint,
    // NULL, NOT DERIVED: this group has no SKU (`skuOrName` proved it), and `set`/`rarity`
    // are written at identification time out of the row a SKU resolved to
    // (D213) — a card with none has
    // nothing to carry them from. `InventoryCard` does not put them on the wire at all;
    // only `do_search`'s own group does.
    set: null,
    rarity: null,
    condition: row.card.condition,
    listed: { pushed: 0, staged: 0, live: 0 },
    sold_here: 0,
    live_as_of: null,
    on_hand: held,
    listable: held,
    copies: [copy],
  }
}

/** One write that has just been recorded — a sale, or a retirement — and what can still be
 *  done about it. A list of these, holding its own copy of the position because the rows may
 *  move underneath it.
 *
 *  NO CLOCK (`docs/specs/undo.md` §11.1, UN-5): the newest reversible write on this screen
 *  keeps its Undo until a newer write replaces it — rank, never a deadline. `remember` already
 *  prepends and dedupes by `key`, so the array is newest-first by construction and `.find` /
 *  `[0]` reach the same answer a clock used to gate. A toast still fades (`kit/toast.tsx`'s own
 *  `ttlMs`); the row's and the page's Undo do not fade with it. */
type Receipt = {
  kind: 'sale' | 'retirement' | 'move'
  key: string
  box: number
  index: number
  place: string
  said: string
  canUndo: boolean
  note: string | null
  /** MOVE ONLY: where the transplant reads now, and its capture id. `undoMove` aims at the
   *  tombstone (`box`/`index` above) and refuses `move_built_on` once either box has changed
   *  again. The remedy then is an ordinary `moveCard`, aimed at THIS location, back to `box`
   *  (`server.ts:moveCard`'s own doc comment). */
  current?: { box: number; index: number; captureId: string | null }
}

const MOVE_BUILT_ON = 'move_built_on'

/* NO RAW CODE ON SCREEN (D196, D269 — the Opus review round's finding #7): a toast has no
 * disclosure to put a machine string behind, so it does not carry one. The server's own
 * sentence, already in `failure.message`, is what a person reads; `code` stays off-screen. */
function report(failure: Failure): void {
  toast({ kind: 'refusal', title: failure.message })
}

export function Inventory() {
  const [selected, setSelected] = useState<Row | null>(null)
  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])
  const [listings, setListings] = useState<Readonly<Record<string, Listing>>>(NO_LISTINGS)
  const [runScope, setRunScope] = useState<{ box: number | null; indices: readonly number[] }>({
    box: null,
    indices: [],
  })
  const layouts = useMemo(
    () => (boxRecords.length === 0 ? NO_LAYOUTS : layoutsOf(boxRecords)),
    [boxRecords],
  )

  /* Walk to a copy — the one thing this screen asks the walk to do. A counter beside the key
   * so the same copy can be asked for twice.
   *
   * `box` RIDES ALONG SINCE D192 (store-scaling item 2): `BoxBrowse`'s own `rows`
   * holds only the box already on screen, so it can no longer find an OTHER box's copy by
   * scanning `rows` for the key the way it used to when `rows` held the whole store. This
   * screen's own copies list already knows the target's box (`SearchCopy.place.box`, off
   * `CopiesFor`'s own `useSearch()`), so it is handed over rather than re-derived. */
  const [goTo, setGoTo] = useState<{ key: string; at: number; box: number | null } | null>(null)
  const walkTo = useCallback(
    (copy: SearchCopy) =>
      setGoTo((asked) => ({
        key: copy.key,
        at: (asked?.at ?? 0) + 1,
        box: copy.place.located === false ? null : copy.place.box,
      })),
    [],
  )

  /* Bumped after every write, and read by the walk and the copies panel as a re-read trigger. */
  const [reloads, setReloads] = useState(0)

  /* The copy waiting on a retire panel, or null. A retirement without a reason is refused, so
   * the four reason buttons ARE the confirm. */
  const [retiring, setRetiring] = useState<SearchCopy | null>(null)
  /* The copy waiting on the move panel, or null (UX-244). */
  const [moving, setMoving] = useState<SearchCopy | null>(null)

  /* One write in flight at a time, by copy key. */
  const [busyKey, setBusyKey] = useState<string | null>(null)

  /* Receipts — sales and retirements — still inside their undo window, newest first. */
  const [receipts, setReceipts] = useState<Receipt[]>([])

  /* Copies this screen has sold or retired and the wire has not caught up with yet. */
  const [sold, setSold] = useState<string[]>([])
  const [retired, setRetired] = useState<string[]>([])

  /* THE COPIES THAT HAVE LEFT SINCE THE ORDER ON SCREEN WAS TAKEN (`frozenRank.ts`).
   *
   * Not a second overlay on top of `sold`/`retired`: those two are OPTIMISM, cleared the moment
   * the re-read agrees with them, and they exist so a press shows its own result before the wire
   * catches up. This is MEMORY, and it outlives the re-read on purpose — it is what lets every
   * ranking under a query go on computing the order it was computing before the press.
   *
   * It is held here rather than in either list because ONE PRESS MAKES BOTH OF THEM STALE and
   * one press must clear both: the copies list and the box rail rank the same departure two
   * ways, and two freezes released by two controls is the owner pressing twice to stop one
   * list moving. */
  const [frozen, setFrozen] = useState<FrozenRank>(RANK_IS_CURRENT)
  const holdRank = useCallback((key: string) => {
    setFrozen((held) => (held.has(key) ? held : new Set(held).add(key)))
  }, [])
  const releaseRank = useCallback((key: string) => {
    setFrozen((held) => {
      if (!held.has(key)) return held
      const next = new Set(held)
      next.delete(key)
      return next
    })
  }, [])
  /* THE RE-RANK, and the only way the order ever moves under a standing query. Also what a new
     query gets: a fresh answer has not been worked down yet, so there is nothing to hold still —
     `BoxBrowse` calls this when the searchbox changes. Identity-stable when already current, so
     the walk's own effect cannot loop on it. */
  const rerank = useCallback(() => {
    setFrozen((held) => (held.size === 0 ? held : RANK_IS_CURRENT))
  }, [])

  /* The copy the walk is pointing at, as the search knows it — for the phone's action bar,
   * which is its one reader since D119 deleted the location card. */
  const [currentCopy, setCurrentCopy] = useState<SearchCopy | null>(null)

  /* The toast standing for each receipt, by copy key, so an undo from the row can take it down. */
  const toasts = useRef<Map<string, number>>(new Map())

  /* The open orders' claims on copies, re-read with every write and allowed to fail without
     anybody hearing: the walk is whole without the ledger. */
  const [wanted, setWanted] = useState<ReadonlyMap<string, Wanted>>(NOBODY)
  useEffect(() => {
    let live = true
    getOrders()
      .then((payload) => {
        if (live) setWanted(wantedOf(payload))
      })
      .catch(() => {
        // Deliberately nothing.
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* Escape closes the retire panel. */
  useEffect(() => {
    if (retiring === null) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setRetiring(null)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [retiring])

  const doUndoRef = useRef<(receipt: Receipt) => Promise<void>>(async () => {})

  /** Newest first, and a second write against one position replaces its receipt. Every
   *  receipt is also a toast — with its Undo where there is one, and its note where there is
   *  not. */
  const remember = useCallback((receipt: Receipt) => {
    setReceipts((held) => [receipt, ...held.filter((standing) => standing.key !== receipt.key)])
    const previous = toasts.current.get(receipt.key)
    if (previous !== undefined) dismissToast(previous)
    const id = toast({
      kind: receipt.canUndo ? 'receipt' : 'status',
      icon: receipt.kind === 'sale' ? 'check' : receipt.kind === 'move' ? 'package' : 'archive',
      title: receipt.said,
      body: receiptBody(receipt.place, receipt.note),
      ttlMs: UNDO_WINDOW_MS,
      action: receipt.canUndo ? { label: 'Undo', onPress: () => void doUndoRef.current(receipt) } : undefined,
    })
    toasts.current.set(receipt.key, id)
  }, [])

  const doSell = useCallback(
    async (copy: SearchCopy) => {
      if (busyKey !== null) return
      setBusyKey(copy.key)
      setRetiring(null)

      const seat = {
        key: copy.key,
        box: copy.place.box,
        index: copy.place.index,
        place: sayPlace(copy.place.label ?? `pooled, ${copy.key}`),
      }
      try {
        const reversible = canTakeBack(await markSold(copy.place.box, copy.place.index))
        setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        holdRank(copy.key)
        remember({
          ...seat,
          kind: 'sale',
          said: 'Marked sold',
          canUndo: reversible,
          note: [renumberNote(copy.place), reversible ? null : NO_UNDO].filter(Boolean).join(' ') || null,
        })
        setReloads((n) => n + 1)
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
          /* ANOTHER DEVICE SOLD IT, AND THE ROW STILL MAY NOT MOVE. The re-read is about to
             bring the departure back whatever this screen wrote, so the order has gone stale
             here exactly as it would have on a sale of its own. */
          holdRank(copy.key)
          remember({
            ...seat,
            kind: 'sale',
            said: 'Already sold',
            canUndo: false,
            note: 'Another device sold this copy first, so nothing was written here.',
          })
          setReloads((n) => n + 1)
          return
        }
        report(describeFailure(err))
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, remember, holdRank],
  )

  /* The sibling write (D26), shaped move for move on `doSell`. */
  const doRetire = useCallback(
    async (copy: SearchCopy, reason: RetireReason) => {
      if (busyKey !== null) return
      setBusyKey(copy.key)
      setRetiring(null)

      const seat = {
        key: copy.key,
        box: copy.place.box,
        index: copy.place.index,
        place: sayPlace(copy.place.label ?? `pooled, ${copy.key}`),
      }
      try {
        const reversible = canTakeBack(
          await retireCard(copy.place.box, copy.place.index, reason),
        )
        setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        holdRank(copy.key)
        remember({
          ...seat,
          kind: 'retirement',
          said: `Retired: ${reasonWord(reason)}`,
          canUndo: reversible,
          note: [renumberNote(copy.place), reversible ? null : NO_UNDO].filter(Boolean).join(' ') || null,
        })
        setReloads((n) => n + 1)
      } catch (err) {
        if (refusalCode(err) === ALREADY_RETIRED) {
          setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
          holdRank(copy.key)
          remember({
            ...seat,
            kind: 'retirement',
            said: 'Already retired',
            canUndo: false,
            note: 'Another device retired this copy first, so nothing was written here.',
          })
          setReloads((n) => n + 1)
          return
        }
        report(describeFailure(err))
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, remember, holdRank],
  )

  /* D83's third door, for one copy (UX-244). UN-14 (`docs/specs/undo.md` §11.1, D28/D57
   * amended 2026-09-25): the move gets the same fast path a sale does — `remember` folds it
   * into the SAME receipt list, so `U` and the toast's own Undo reach whichever write, sale,
   * retirement or move, was pressed last. `undoMove` is aimed at the TOMBSTONE (the source
   * `box`/`index` this call sent), never the new one — the card comes back to its own index,
   * and nothing else in either box moves. */
  const doMove = useCallback(
    async (copy: SearchCopy, toBox: number) => {
      if (busyKey !== null) return
      setBusyKey(copy.key)
      const seat = { key: copy.key, box: copy.place.box, index: copy.place.index }
      try {
        const result = await moveCard(copy.place.box, copy.place.index, copy.capture_id, toBox)
        setMoving(null)
        holdRank(copy.key)
        const where = boxRecords.find((record) => record.box === toBox)?.name ?? UNNAMED_BOX
        remember({
          ...seat,
          place: sayPlace(copy.place.label ?? copy.key),
          kind: 'move',
          said: `Moved to ${where}`,
          canUndo: true,
          note: renumberNote(copy.place),
          current: { box: result.new_box, index: result.new_index, captureId: result.card.capture_id },
        })
        setReloads((n) => n + 1)
      } catch (err) {
        report(describeFailure(err))
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, holdRank, boxRecords, remember],
  )

  const doUndo = useCallback(
    async (receipt: Receipt) => {
      if (busyKey !== null) return
      setBusyKey(receipt.key)
      let movedBack = false
      /* WHERE THE REMEDY ACTUALLY PUT IT (finding #5, the Opus review round): the remedy
       * lands at a FRESH index in the origin box, never the tombstoned one, so `receipt.place`
       * — the copy's place from BEFORE the original move — names the wrong shelf once this
       * runs. `result.card.label` is the server's own answer to the move-back itself. */
      let movedBackTo: string | null = null
      try {
        if (receipt.kind === 'sale') await undoSale(receipt.box, receipt.index)
        else if (receipt.kind === 'retirement') await undoRetire(receipt.box, receipt.index)
        else await undoMove(receipt.box, receipt.index)
      } catch (err) {
        /* `not_sold` / `not_retired` / `not_moved` is success — the copy is not in the state
         * the press asked to leave. Anything else keeps the receipt standing, EXCEPT
         * `move_built_on` (UN-14): the ordinary reversal aims at the tombstone and refuses
         * once either box has changed again since — same reason `undoSale` refuses
         * `sale_built_on`. There is no separate route for the fix-after here, unlike a sale's
         * `saleStillHere`: `server.ts:moveCard`'s own doc comment names the remedy as an
         * ORDINARY `moveCard` again, aimed at the transplant's CURRENT position, back to the
         * box the receipt started from. It lands at a fresh index there, never the
         * tombstoned one. */
        if (receipt.kind === 'move' && refusalCode(err) === MOVE_BUILT_ON && receipt.current !== undefined) {
          try {
            const result = await moveCard(receipt.current.box, receipt.current.index, receipt.current.captureId, receipt.box)
            movedBack = true
            movedBackTo = result.card.label === undefined ? null : sayPlace(result.card.label)
          } catch (remedyErr) {
            report(describeFailure(remedyErr))
            setBusyKey(null)
            return
          }
        } else {
          const settled = receipt.kind === 'sale' ? NOT_SOLD : receipt.kind === 'retirement' ? NOT_RETIRED : NOT_MOVED
          if (refusalCode(err) !== settled) {
            report(describeFailure(err))
            setBusyKey(null)
            return
          }
        }
      }
      setReceipts((held) => held.filter((standing) => standing.key !== receipt.key))
      const standing = toasts.current.get(receipt.key)
      if (standing !== undefined) {
        dismissToast(standing)
        toasts.current.delete(receipt.key)
      }
      if (receipt.kind === 'sale') setSold((held) => held.filter((key) => key !== receipt.key))
      else if (receipt.kind === 'retirement') setRetired((held) => held.filter((key) => key !== receipt.key))
      /* THE COPY IS BACK, SO THE ORDER IS NO LONGER STALE BY IT. Releasing rather than leaving
         it held is what keeps the staleness figure a count of what actually left: an undone sale
         that went on being counted would offer a re-rank for a store that never moved. */
      releaseRank(receipt.key)
      toast({
        kind: 'ok',
        icon: 'undo',
        /* ONE VOCABULARY (UN-5, finding #15, the Opus review round, `docs/specs/undo.md`
         * §11.9): every reversal reads "<what it undid> undone", whether the write went
         * through the ordinary reversal route or, for a move, back through `moveCard`
         * itself (`movedBack`) — a distinction the operator has no reason to see. */
        title:
          receipt.kind === 'sale'
            ? 'Sale undone'
            : receipt.kind === 'retirement'
              ? 'Retirement undone'
              : 'Move undone',
        body: movedBack ? (movedBackTo ?? receipt.place) : receipt.place,
        ttlMs: 4000,
      })
      setReloads((n) => n + 1)
      setBusyKey(null)
    },
    [busyKey, releaseRank],
  )
  doUndoRef.current = doUndo

  /* THE NEWEST RECEIPT STILL CARRYING AN UNDO — sale or retirement, whichever was pressed
   * last. `receipts` is already newest-first (`remember`), so the first one with `canUndo`
   * is the one `U` reaches. Read fresh every render; nothing about it needs a ref. */
  const receiptsRef = useRef(receipts)
  receiptsRef.current = receipts
  const newestUndoable = useMemo(() => receipts.find((receipt) => receipt.canUndo) ?? null, [receipts])

  /* THE SHARED HOOK (`docs/specs/undo.md` §11.3, UN-10) — one primitive for the newest
   * reversible write, in place of this screen's own listener. */
  useUndoHotkey(() => {
    const newest = receiptsRef.current.find((receipt) => receipt.canUndo)
    return newest === undefined ? null : () => void doUndoRef.current(newest)
  })

  const soldKeys = useMemo(() => new Set(sold), [sold])
  const retiredKeys = useMemo(() => new Set(retired), [retired])

  /* WHETHER SOLD ROWS ARE WORTH SCROLLING PAST (D132). One control on the walk's status bar,
     one answer for the walk AND the copies list, remembered by this browser. */
  const [hideSold, setHideSold] = useState<boolean>(() => storedHideSold())
  const toggleHideSold = useCallback(() => {
    setHideSold((held) => {
      rememberHideSold(!held)
      return !held
    })
  }, [])

  /** The one sale a row may still take back — the NEWEST reversible receipt, and only if it is
   *  a sale (`docs/specs/undo.md` §11.1, the Opus review round, finding #12): "only the newest
   *  sale is undoable by U or the toast." An older sold row keeps its own row (the freeze,
   *  D132) but its Undo leaves the instant a later write takes the newest rank, the same way
   *  Orders' `newestUndoKey` gates `RowAction`. Filtering every `canUndo` receipt here (the
   *  first build) kept EVERY sale of the session undoable at once, which is what the review
   *  caught: §11.1 asks for one. */
  const undoableSales = useMemo(
    () =>
      newestUndoable !== null && newestUndoable.kind === 'sale'
        ? new Map([[newestUndoable.key, newestUndoable] as const])
        : new Map<string, Receipt>(),
    [newestUndoable],
  )

  /* The press is the sale (D57). A retire panel standing over another copy is closed first. */
  const sell = useCallback(
    (copy: SearchCopy) => {
      setRetiring(null)
      void doSell(copy)
    },
    [doSell],
  )

  const undo = useCallback((receipt: Receipt) => void doUndo(receipt), [doUndo])

  const openRetire = useCallback((copy: SearchCopy) => {
    setRetiring(copy)
  }, [])

  const actionFor = (copy: SearchCopy, primary: boolean): ReactNode => (
    <Action
      copy={copy}
      primary={primary}
      busyKey={busyKey}
      soldKeys={soldKeys}
      retiredKeys={retiredKeys}
      undoableSales={undoableSales}
      undoKeyOn={newestUndoable?.key === copy.key}
      onSell={sell}
      onUndo={undo}
      onRetire={openRetire}
      onMove={setMoving}
    />
  )

  const detail =
    selected === null ? null : (
      <div className="inventory-detail">
        <CopiesPanel
          row={selected}
          layouts={layouts}
          listings={listings}
          wanted={wanted}
          reloadToken={reloads}
          busyKey={busyKey}
          soldKeys={soldKeys}
          onSell={sell}
          onGoTo={walkTo}
          onCurrent={setCurrentCopy}
          renderAction={actionFor}
          hideSold={hideSold}
          frozen={frozen}
          onRerank={rerank}
        />
      </div>
    )

  return (
    /* THE KIT'S PAGE (D275): the one h1 off the route, the one width and top gap. */
    <Page
      icon="box"
      /* SILENT WITH NO BOX: the empty state says "No boxes yet" once, not the lede too. */
      lede={boxRecords.length === 0 ? undefined : 'Sell, retire or move any card.'}
      className="inventory"
    >
      <BoxBrowse
        detail={detail}
        onSelect={setSelected}
        onBoxes={setBoxRecords}
        onListings={setListings}
        onScope={setRunScope}
        goTo={goTo}
        reloadToken={reloads}
        hideSold={hideSold}
        onHideSold={toggleHideSold}
        frozen={frozen}
        onQuery={rerank}
        boxPanel={<BoxRuns box={runScope.box} indices={runScope.indices} />}
        actionBar={currentCopy === null || selected === null || currentCopy.key !== selected.key ? null : actionFor(currentCopy, true)}
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
      {moving === null ? null : (
        <MovePanel
          copy={moving}
          boxes={boxRecords}
          busy={busyKey !== null}
          onMove={(toBox) => void doMove(moving, toBox)}
          onCancel={() => setMoving(null)}
        />
      )}
    </Page>
  )
}

/* EVERY COPY OF THE SELECTED CARD, AND WHERE EACH ONE SITS — D7's SKU -> positions map, drawn
 * for the one card the walk is pointing at. THE COPY IT IS POINTING AT IS ONE OF THE ROWS and
 * not a card above them (D119): it carries a `Viewing` marker and a neutral rail, and nothing
 * else separates it.
 *
 * `GET /search` stays the matcher and nothing here filters the inventory locally: the panel
 * asks with the card's own SKU, or its name when it has no SKU, and keeps the group whose
 * copies CONTAIN this row's store key. The search route carries three numbers the inventory
 * read does not — `on_hand`, `listed` and `cap`. It debounces, so holding an arrow key issues
 * one request when the hand stops.
 */
function CopiesPanel({
  row,
  layouts,
  listings,
  wanted,
  reloadToken,
  busyKey,
  soldKeys,
  onSell,
  onGoTo,
  onCurrent,
  renderAction,
  hideSold,
  frozen,
  onRerank,
}: {
  row: Row
  layouts: ReadonlyMap<number, readonly SectionDetail[]>
  listings: Readonly<Record<string, Listing>>
  wanted: ReadonlyMap<string, Wanted>
  reloadToken: number
  busyKey: string | null
  soldKeys: ReadonlySet<string>
  onSell: (copy: SearchCopy) => void
  onGoTo: (copy: SearchCopy) => void
  onCurrent: (copy: SearchCopy | null) => void
  renderAction: (copy: SearchCopy, primary: boolean) => ReactNode
  hideSold: boolean
  frozen: FrozenRank
  onRerank: () => void
}) {
  const { query, setQuery, results, loading, failure, reload } = useSearch()

  const handle = skuOrName(row.card)

  useEffect(() => {
    setQuery(handle ?? '')
  }, [handle, setQuery])

  /* Re-ask on a write, and never on the first render. */
  const seen = useRef(reloadToken)
  useEffect(() => {
    if (seen.current === reloadToken) return
    seen.current = reloadToken
    reload()
  }, [reloadToken, reload])

  /* Matched by key, not by SKU: this row's own store key is in exactly one group. */
  const group = useMemo(
    () =>
      results === null
        ? null
        : (results.groups.find((candidate) =>
            candidate.copies.some((copy) => copy.key === row.key),
          ) ?? null),
    [results, row.key],
  )

  const settled = results !== null && results.query === (handle ?? '')

  /* B1: THE LOADER MUST GIVE UP. `settled` above asks whether the answer ON HAND matches the
     query ON HAND — a strict check the D118 comment above needs to avoid flashing a stale
     group. It says nothing about whether a fetch is actually running, so a query the server
     never echoes back correctly (measured: the shared route-sweep fixture's `/search` stub
     always answers `query: ''`) leaves `settled` false forever even after `loading` has gone
     back to false — `group === null && (loading || !settled)` then never turns false, and the
     kit's `aria-busy` `<Loading>` spins for good. `askedFor` remembers the handle a fetch was
     actually LAUNCHED for; once `loading` returns to false for that same handle, the fetch is
     over — settled or not — and there is nothing left to wait for. */
  const askedFor = useRef<string | null>(null)
  useEffect(() => {
    if (loading) askedFor.current = handle
  }, [loading, handle])
  const gaveUp = !loading && askedFor.current === handle

  /* The copy the walk is pointing at, as the search knows it — or the lone copy when the
     search cannot reach it. */
  const lone = useMemo(() => (handle === null ? loneCopy(row) : null), [handle, row])
  const current = useMemo(
    () => (handle === null ? lone : settled && group !== null ? (group.copies.find((copy) => copy.key === row.key) ?? null) : null),
    [handle, lone, settled, group, row.key],
  )

  useEffect(() => {
    onCurrent(current)
  }, [current, onCurrent])

  /* The one-copy group, built only where the search cannot be asked. Null when the record
     carries no place at all, which is the one shape that has no copy to put in a group. */
  const solo = useMemo(() => (lone === null ? null : loneGroup(row, lone)), [row, lone])

  if (handle === null) {
    return (
      <section className="inventory-copies">
        {solo === null ? null : (
          <CardLocations
            group={solo}
            persona="owner"
            sections={layouts}
            currentKey={row.key}
            /* No SKU, so no listing record and nothing to be the age OF. */
            listedAt={null}
            claims={wanted}
            /* NO `onGoTo`, and that is D45 rather than an omission: the only copy in this group
               is the one the walk is standing on, and a walk-to on it goes nowhere. */
            onSell={onSell}
            busyKey={busyKey}
            soldKeys={soldKeys}
            renderAction={(copy) => renderAction(copy, false)}
          />
        )}
        {/* KEPT, AND UNDER THE GROUP RATHER THAN DELETED. The panel above answers "where is it
            and what can I do with it"; this answers "why is there only one row and no listing
            figures", which is context for the thing above it and reads wrong before it. */}
        <div className="inventory-lone">
          <Notice tone="info" title="No name and no SKU yet.">
            {lone === null ? 'The store sent no place for this card.' : 'This is the only copy.'} It gets a SKU
            when a run matches it.
          </Notice>
        </div>
      </section>
    )
  }

  return (
    <section className="inventory-copies">
      {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}

      {/* D118: a press changes what is on screen, never where the rest of it is. A re-read
          after `Mark sold` (`doSell`'s `setReloads`) keeps `group` standing from the old
          `results` while `useSearch` sets `loading` — measured at 1440 with `/search` delayed
          800ms: drawing this skeleton on every `loading`/`!settled` pushed `CardLocations` from
          y=79 to y=181 and back on an ~93ms answer. Draw it only when there is nothing to stand
          on — a fresh card on the walk (`group` is null because `row.key` is not in the still-
          old `results`) or the very first read. A re-read of the SAME card keeps its `group`
          (found by key in the stale `results`) and the list stays put while the fetch runs.
          `!gaveUp` rather than `loading || !settled` (B1): the fetch this handle asked for is
          over the moment `loading` goes back to false, whether or not it ever settled. */}
      {group === null && !gaveUp ? (
        <Loading rows={1} className="inventory-looking" label="Reading this card's copies" />
      ) : null}

      {group === null && gaveUp ? (
        <Notice tone="warn" title="The search did not return this card's own row." code={`key ${row.key}, query ${query}`}>
          That should not happen; a reload usually settles it.
        </Notice>
      ) : null}

      {group === null ? null : (
        <CardLocations
          group={group}
          persona="owner"
          sections={layouts}
          currentKey={row.key}
          listedAt={group.sku === null ? null : (listings[group.sku]?.live_as_of ?? null)}
          claims={wanted}
          onGoTo={onGoTo}
          onSell={onSell}
          busyKey={busyKey}
          soldKeys={soldKeys}
          /* EVERY row draws its own controls, the copy the walk is standing on included —
             and since D119 there is no second place they could be drawn. `false` is the row
             form: a quiet `Mark sold` and an icon-only `Retire`. The `true` form survives at
             one call site, the phone's sticky action bar, and is phone-only from here. */
          renderAction={(copy) => renderAction(copy, false)}
          hideSold={hideSold}
          frozen={frozen}
          onRerank={onRerank}
        />
      )}
    </section>
  )
}

/** The handle the copies search asks with. SKU first, the name second, null when neither. */
function skuOrName(card: InventoryCard): string | null {
  const sku = card.sku
  if (sku !== null && sku.trim() !== '') return sku.trim()
  const name = card.name
  if (name !== null && name.trim() !== '') return name.trim()
  return null
}

/** What one copy offers: the word for the door it left by, or the two writes.
 *
 *  `primary` IS A SIZE, NOT A SHAPE, AS OF D119. It used to mean "the location card's form —
 *  the one solid button on the screen"; that card is gone, and its last caller is the phone's
 *  sticky action bar (`actionBar` below → `BoxBrowse`, rendered only under `max-width: 639px`).
 *  So `primary` is phone-only from here, and what it decides is emphasis and control size —
 *  never whether a state is drawn at all. */
function Action({
  copy,
  primary,
  busyKey,
  soldKeys,
  retiredKeys,
  undoableSales,
  undoKeyOn,
  onSell,
  onUndo,
  onRetire,
  onMove,
}: {
  copy: SearchCopy
  primary: boolean
  busyKey: string | null
  soldKeys: ReadonlySet<string>
  retiredKeys: ReadonlySet<string>
  undoableSales: ReadonlyMap<string, Receipt>
  /** True on the one copy `U` reaches — the newest receipt still carrying an undo. */
  undoKeyOn: boolean
  onSell: (copy: SearchCopy) => void
  onUndo: (receipt: Receipt) => void
  onRetire: (copy: SearchCopy) => void
  onMove: (copy: SearchCopy) => void
}) {
  const busy = busyKey === copy.key
  if (copy.state === 'sold' || soldKeys.has(copy.key)) {
    const standing = undoableSales.get(copy.key)
    /* After the undo window the state is a pill, ONLY FOR AN OPTIMISTIC SALE STILL IN FLIGHT
       (S2): the struck number this row already draws is the confirmed-sold mark, and the hero
       chips above say `Sold` once for the copy the walk stands on. That covers the phone's
       sticky bar too — it used to draw its own `Sold` unconditionally once `primary` was true,
       which was a THIRD `Sold` on the one row a phone actually shows all three at once. */
    return standing === undefined ? (
      copy.state !== 'sold' ? (
        <Pill tone="ok" icon="check">
          Sold
        </Pill>
      ) : null
    ) : (
      /* THE ROW HAS NO CLOCK EITHER, SINCE UN-5 (D28 and D57 amended 2026-09-25) — which is
         D118 deciding the shape rather than taste. The location card drew the whole receipt
         and the row got a bare `Undo`; with that card gone the row is where a sale is taken
         back, and it stands until a newer sale replaces it rather than for a counted twenty
         seconds. What could NOT come with it is the panel: `.card-locations-action` reserves
         the button pair's own 137x28 so a press cannot resize the slot it lands in, and a
         `bn-receipt` pill is 268px wide and 36px tall — put in the cell it shoves the address,
         given a grid row of its own it grows the row 38px, and either one is the screen shake
         D118 was built to end. Measured both ways.
         SO THE ROW GETS ONLY THE BUTTON, inside the slot, at the slot's size — no drain, since
         a drain that finished and stayed empty is exactly the "it looks dead but it still
         works" shape UN-5 removes. The sentence is not lost: the state pill beside it already
         reads `Sold`, and the toast this sale posted carries `Marked sold.` with the same
         Undo. The phone's action bar is unchanged — it has no state pill beside it, and it is
         what `primary` now means. */
      <span className={primary ? 'bn-receipt inventory-receipt' : 'inventory-copy-actions inventory-receipt'}>
        {primary ? <span className="inventory-receipt-said">Marked sold.</span> : null}
        {/* ICON, U IN THE TOOLTIP (ICONOGRAPHY): Undo is reversed by pressing it again, so it
            keeps no words in either sector — the row and the phone bar both read it from the
            sentence beside it. */}
        <IconButton
          size={primary ? 'xl' : 'sm'}
          icon="undo"
          label="Undo"
          name={`Undo the sale at ${standing.place}`}
          busy={busy}
          disabled={busyKey !== null && !busy}
          kbd={undoKeyOn ? UNDO_KEY_LABEL : undefined}
          onClick={() => onUndo(standing)}
        />
      </span>
    )
  }
  if (copy.state === 'retired' || retiredKeys.has(copy.key)) {
    /* S2's own reasoning applies here too: an optimistic pill only, never once the state is
       confirmed — the struck number and the hero chip already say `Retired`. */
    return copy.state !== 'retired' ? (
      <Pill tone="warn" icon="archive">
        Retired
      </Pill>
    ) : null
  }
  return (
    <span className={primary ? 'inventory-copy-actions is-primary' : 'inventory-copy-actions'}>
      {/* MARK SOLD KEEPS ITS WORDS ONLY WHERE IT IS THE ONE PRIMARY IN ITS SECTOR, the phone's
          sticky action bar (ICONOGRAPHY). The row form is the icon vocabulary's own `sold`
          glyph — a round seal, never confused with Retire's box. */}
      {primary ? (
        <Button variant="primary" size="lg" icon="check" busy={busy} disabled={busyKey !== null && !busy} onClick={() => onSell(copy)}>
          Mark sold
        </Button>
      ) : (
        <IconButton size="sm" icon="sold" label="Mark sold" busy={busy} disabled={busyKey !== null && !busy} onClick={() => onSell(copy)} />
      )}
      {/* ICON IN BOTH SECTORS (ICONOGRAPHY): Retire is reversible (Undo), so it never spends
          words. `archive` — a lidded box — reads as "put away" rather than "delete". */}
      <IconButton
        size={primary ? 'xl' : 'sm'}
        icon="archive"
        label="Retire"
        disabled={busyKey !== null}
        onClick={() => onRetire(copy)}
      />
      {/* MOVE ONE COPY FROM THE CARD IN VIEW (UX-244): it was only in Manage, over ticked cards,
          and with nothing ticked it moved the whole box. A pooled copy has no box to leave.
          ICON IN BOTH SECTORS, the same vocabulary as Retire beside it. */}
      {copy.place.located === false ? null : (
        <IconButton
          size={primary ? 'xl' : 'sm'}
          icon="moveTo"
          label="Move to another box"
          disabled={busyKey !== null}
          onClick={() => onMove(copy)}
        />
      )}
    </span>
  )
}

/* THE MOVE PANEL (UX-244, D83): one copy, one destination, one press. The other boxes by name,
 * most recent first as everywhere (the owner's box-order ruling). */
function MovePanel({
  copy,
  boxes,
  busy,
  onMove,
  onCancel,
}: {
  copy: SearchCopy
  boxes: readonly BoxRecord[]
  busy: boolean
  onMove: (toBox: number) => void
  onCancel: () => void
}) {
  const [to, setTo] = useState<string | null>(null)
  /* S4: MOST RECENT FIRST, the same primitive the rail sorts by — `others` used to be the
     server's own `GET /boxes` order (box number), which said nothing about which box the hand
     was likeliest to reach for. */
  const others = boxesMostRecentFirst(
    boxes.filter((record) => record.box !== copy.place.box && record.state !== 'closed'),
  )
  return (
    <Overlay kind="dialog" label={`Move: ${sayPlace(copy.place.label ?? copy.key)}`} onClose={onCancel} className="inventory-confirm">
      <div className="inv-dialog-head">
        <span className="bn-eyebrow">Move</span>
        <h2 className="inv-dialog-title">Which box does this copy go to?</h2>
      </div>
      <div className="inv-dialog-body">
        <p className="bn-muted">It goes to the front of that box. No other card changes box.</p>
        {others.length === 0 ? (
          <Notice tone="info" title="There is no other open box." />
        ) : (
          <Select
            label="Box"
            value={to}
            placeholder="Choose a box"
            options={others.map((record) => ({ value: String(record.box), label: record.name ?? UNNAMED_BOX }))}
            onChange={setTo}
          />
        )}
      </div>
      <div className="inv-dialog-foot">
        <Button variant="ghost" onClick={onCancel} data-autofocus="">
          Cancel
        </Button>
        <Button variant="primary" icon="package" busy={busy} disabled={to === null} onClick={() => to !== null && onMove(Number(to))}>
          Move
        </Button>
      </div>
    </Overlay>
  )
}

/* The retire panel — a dialog whose four reasons are the write's only input. Focus lands on
 * Cancel, the one control whose accidental press costs nothing. */
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
  const gone = !copy.has_photo || broken


  return (
    <Overlay kind="dialog" label={`Retire: ${sayPlace(copy.place.label ?? copy.key)}`} onClose={onCancel} className="inventory-confirm">
      <div className="inv-dialog-head">
        <span className="bn-eyebrow">Retire</span>
        <h2 className="inv-dialog-title">Why is this copy leaving?</h2>
      </div>
      <div className="inv-dialog-body">
        <div className="inventory-retire-card">
          {gone ? (
            <div className="inventory-retire-nophoto">
              <Icon name="image" size={20} />
            </div>
          ) : (
            <img
              className="inventory-confirm-photo"
              /* BY NAME (D172): `_copy_row` puts the card's own `cid` on a `SearchCopy`,
                 already filtered to the two shapes that name a photograph — so the copy this
                 dialog is about to retire is the copy on screen, whatever has slid through
                 its slot since the search answered. */
              src={photoUrl(copy.place.box, copy.place.index, copy.cid)}
              alt={`The card stored at ${sayPlace(copy.place.label ?? copy.key)}`}
              onError={() => setBroken(true)}
            />
          )}
          <div className="inventory-retire-where">
            <div className="inventory-confirm-place">
              {copy.place.label === null ? <span className="bn-mono">{copy.key}</span> : <PositionLabel label={copy.place.label} />}
            </div>
            {copy.place.box_name === null ? null : (
              <span className="inventory-confirm-boxname">{copy.place.box_name}</span>
            )}
            {copy.place.located === false || isDeparted(copy.place) ? null : (
              <PositionBar place={copy.place} persona="owner" sections={sections} sectionDepth />
            )}
          </div>
        </div>

        <p className="bn-muted">Leaves the box without a sale. The record stays.</p>

        <div className="inventory-retire-reasons" role="group" aria-label="Reason">
          {RETIRE_REASONS.map(({ reason, label, said }) => (
            <button
              key={reason}
              className="inventory-retire-reason"
              type="button"
              disabled={busy}
              onClick={() => onRetire(reason)}
            >
              <span className="inventory-retire-text">
                <span className="inventory-retire-label">{label}</span>
                <span className="inventory-retire-said">{said}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="inv-dialog-foot">
        <Button variant="ghost" onClick={onCancel} data-autofocus="">
          Cancel
        </Button>
      </div>
    </Overlay>
  )
}
