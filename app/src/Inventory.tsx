import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type {
  BoxRecord,
  InventoryCard,
  Listing,
  Place,
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
  getOrders,
  isDeparted,
  markSold,
  photoUrl,
  positionLabel,
  retireCard,
  undoRetire,
  undoSale,
} from './server'
import { BoxBrowse, type Row } from './BoxBrowse'
import { BoxRuns } from './BoxRuns'
import { CardLocations } from './CardLocations'
import { PlaceNeighbors } from './PlaceNeighbors'
import { PositionBar } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { useSearch } from './useSearch'
import { Button, Icon, Notice, Pill } from './kit'
import { dismissToast, toast } from './kit/toast'
import { rememberHideSold, storedHideSold } from './deviceMemory'
import { Overlay } from './InventoryOverlay'
import './Inventory.css'

/* THE INVENTORY — one owner-side view of stored cards: find a card by name or SKU, or walk a
 * box → section → card; see the photograph that proves what is in that slot; see every copy of
 * that card and where each one is; and record that a copy left — sold, retired, moved.
 *
 * `BoxBrowse` owns the walk, the box operations, the photograph and the card-level
 * corrections; this file owns the one flow that writes a card — the sale, the retirement, their
 * receipts and their twenty-second undo — and draws the location card and the copies beside
 * the photograph. Nothing here holds a second copy of the inventory: every write is followed by
 * a re-read.
 */

/** How long a receipt's undo stays. Fulfillment.tsx's number, kept in step. */
const UNDO_WINDOW_MS = 20_000

/* The refusal codes this screen branches on. `already_sold` on a sale is not this device's
 * sale: a receipt with NO undo. `not_sold` on a reversal is success. The retirement pair
 * applies the same two rulings. Codes, never messages. */
const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const ALREADY_RETIRED = 'already_retired'
const NOT_RETIRED = 'not_retired'

/** The four reasons a card leaves without a sale, in the store's own vocabulary (D26). */
const REASONS: readonly { reason: RetireReason; label: string; said: string }[] = [
  { reason: 'pulled', label: 'Pulled out', said: 'Taken out of the box for something else.' },
  { reason: 'damaged', label: 'Damaged', said: 'Not in a condition to sell.' },
  { reason: 'lost', label: 'Lost', said: 'The slot is empty and nobody knows where it went.' },
  { reason: 'given_away', label: 'Given away', said: 'Left the store as a gift or a trade.' },
]

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

/** The retire reason as the panel labels it — `given_away` is `Given away` in a sentence. */
function reasonWord(reason: RetireReason): string {
  return REASONS.find((candidate) => candidate.reason === reason)?.label ?? reason
}

/** An open order that names one copy, by the copy's store key (`3/103`). */
type Wanted = { order: string; key: string }
const NOBODY: ReadonlyMap<string, Wanted> = new Map()

/* Which on-hand copies an open order is waiting on, out of the resolver's own picks — so a copy
 * about to be pulled for an order says so before it is marked sold as a walk-in sale. A pulled
 * copy already reads `Sold`; only the ones still on hand are named. */
function wantedOf(payload: Awaited<ReturnType<typeof getOrders>>): ReadonlyMap<string, Wanted> {
  const out = new Map<string, Wanted>()
  for (const order of payload.resolution?.orders ?? []) {
    for (const line of order.lines) {
      for (const pick of line.picks) {
        if (pick.held_by !== null) continue
        if (pick.state === 'sold' || pick.state === 'retired' || pick.state === 'moved') continue
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

/** One write that has just been recorded — a sale, or a retirement — and what can still be
 *  done about it. A list of these, each with its own deadline, holding its own copy of the
 *  position because the rows may move underneath it. */
type Receipt = {
  kind: 'sale' | 'retirement'
  key: string
  box: number
  index: number
  place: string
  said: string
  canUndo: boolean
  note: string | null
  until: number
}

function report(failure: Failure): void {
  toast({ kind: 'refusal', title: failure.message, body: failure.code })
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
   * so the same copy can be asked for twice. */
  const [goTo, setGoTo] = useState<{ key: string; at: number } | null>(null)
  const walkTo = useCallback(
    (copy: SearchCopy) => setGoTo((asked) => ({ key: copy.key, at: (asked?.at ?? 0) + 1 })),
    [],
  )

  /* Bumped after every write, and read by the walk and the copies panel as a re-read trigger. */
  const [reloads, setReloads] = useState(0)

  /* The copy waiting on a retire panel, or null. A retirement without a reason is refused, so
   * the four reason buttons ARE the confirm. */
  const [retiring, setRetiring] = useState<SearchCopy | null>(null)

  /* One write in flight at a time, by copy key. */
  const [busyKey, setBusyKey] = useState<string | null>(null)

  /* Receipts — sales and retirements — still inside their undo window, newest first. */
  const [receipts, setReceipts] = useState<Receipt[]>([])

  /* Copies this screen has sold or retired and the wire has not caught up with yet. */
  const [sold, setSold] = useState<string[]>([])
  const [retired, setRetired] = useState<string[]>([])

  /* The copy the walk is pointing at, as the search knows it — for the location card's own
   * action and the phone's action bar. */
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

  /* One timer for the whole list, armed at the soonest deadline. */
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
  const remember = useCallback((receipt: Omit<Receipt, 'until'>) => {
    const full: Receipt = { ...receipt, until: Date.now() + UNDO_WINDOW_MS }
    setReceipts((held) => [full, ...held.filter((standing) => standing.key !== receipt.key)])
    const previous = toasts.current.get(receipt.key)
    if (previous !== undefined) dismissToast(previous)
    const id = toast({
      kind: full.canUndo ? 'receipt' : 'status',
      icon: full.kind === 'sale' ? 'check' : 'minus',
      title: full.said,
      body: full.note === null ? full.place : `${full.place} — ${full.note}`,
      ttlMs: UNDO_WINDOW_MS,
      action: full.canUndo ? { label: 'Undo', onPress: () => void doUndoRef.current(full) } : undefined,
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
        place: copy.place.label ?? `pooled · ${copy.key}`,
      }
      try {
        const reversible = canTakeBack(await markSold(copy.place.box, copy.place.index))
        setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        remember({
          ...seat,
          kind: 'sale',
          said: 'Marked sold',
          canUndo: reversible,
          note: reversible
            ? null
            : 'The store cannot say what state this copy was in before the sale, so it ' +
              'cannot be put back from here (sold_origin_unknown).',
        })
        setReloads((n) => n + 1)
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          setSold((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
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
    [busyKey, remember],
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
        place: copy.place.label ?? `pooled · ${copy.key}`,
      }
      try {
        const reversible = canTakeBack(
          await retireCard(copy.place.box, copy.place.index, reason),
        )
        setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
        remember({
          ...seat,
          kind: 'retirement',
          said: 'Retired',
          canUndo: reversible,
          note: reversible
            ? reasonWord(reason)
            : `${reasonWord(reason)} — the store cannot say what state this copy was in ` +
              'before the retirement, so it cannot be put back from here ' +
              '(retired_origin_unknown).',
        })
        setReloads((n) => n + 1)
      } catch (err) {
        if (refusalCode(err) === ALREADY_RETIRED) {
          setRetired((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
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
    [busyKey, remember],
  )

  const doUndo = useCallback(
    async (receipt: Receipt) => {
      if (busyKey !== null) return
      setBusyKey(receipt.key)
      try {
        if (receipt.kind === 'sale') await undoSale(receipt.box, receipt.index)
        else await undoRetire(receipt.box, receipt.index)
      } catch (err) {
        /* `not_sold` / `not_retired` is success — the copy is not in the state the press asked
         * to leave. Anything else keeps the receipt standing. */
        const settled = receipt.kind === 'sale' ? NOT_SOLD : NOT_RETIRED
        if (refusalCode(err) !== settled) {
          report(describeFailure(err))
          setBusyKey(null)
          return
        }
      }
      setReceipts((held) => held.filter((standing) => standing.key !== receipt.key))
      const standing = toasts.current.get(receipt.key)
      if (standing !== undefined) {
        dismissToast(standing)
        toasts.current.delete(receipt.key)
      }
      if (receipt.kind === 'sale') setSold((held) => held.filter((key) => key !== receipt.key))
      else setRetired((held) => held.filter((key) => key !== receipt.key))
      toast({ kind: 'ok', icon: 'undo', title: receipt.kind === 'sale' ? 'Sale undone' : 'Retirement undone', body: receipt.place, ttlMs: 4000 })
      setReloads((n) => n + 1)
      setBusyKey(null)
    },
    [busyKey],
  )
  doUndoRef.current = doUndo

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

  /** The sales a row may still take back, by copy key. Only sales, only reversible ones. */
  const undoableSales = useMemo(
    () =>
      new Map(
        receipts
          .filter((receipt) => receipt.kind === 'sale' && receipt.canUndo)
          .map((receipt) => [receipt.key, receipt] as const),
      ),
    [receipts],
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
      onSell={sell}
      onUndo={undo}
      onRetire={openRetire}
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
        />
      </div>
    )

  return (
    <main className="inventory bn-page">
      <BoxBrowse
        head="Inventory"
        detail={detail}
        onSelect={setSelected}
        onBoxes={setBoxRecords}
        onListings={setListings}
        onScope={setRunScope}
        goTo={goTo}
        reloadToken={reloads}
        hideSold={hideSold}
        onHideSold={toggleHideSold}
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
    </main>
  )
}

/* EVERY COPY OF THE SELECTED CARD, AND WHERE EACH ONE SITS — D7's SKU -> positions map, drawn
 * for the one card the walk is pointing at, beneath the location card for that card itself.
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

  const location = (
    <LocationCard
      row={row}
      layouts={layouts}
      wantedBy={wanted.get(row.key) ?? null}
      action={current === null ? null : renderAction(current, true)}
    />
  )

  if (handle === null) {
    return (
      <section className="inventory-copies">
        {location}
        <div className="inventory-lone">
          <Notice tone="info" title="No name and no SKU yet, so there is no card group to show.">
            This is one copy at one position. A SKU is written when <code className="inventory-inline">emit</code>{' '}
            writes the card&rsquo;s row into an import file, and never before.
            {lone === null ? <span className="inventory-machine">place: absent · key {row.key}</span> : null}
          </Notice>
        </div>
      </section>
    )
  }

  return (
    <section className="inventory-copies">
      {location}

      {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}

      {loading || !settled ? (
        <div className="inventory-looking">
          <span className="bn-skeleton" style={{ width: 140, height: 14 }} />
          <span className="bn-skeleton" style={{ width: '100%', height: 64 }} />
        </div>
      ) : null}

      {group === null && settled && !loading ? (
        <Notice tone="warn" title="The search did not return this card's own row." code={`key ${row.key} · query ${query}`}>
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
          /* EVERY row draws its own controls, the copy the walk is standing on included. That
             copy's controls appear twice — once at hero size in the location card above, once
             at row size here — and that is the trade: a list where one row alone is inert is a
             list that has quietly picked for you. */
          renderAction={(copy) => renderAction(copy, false)}
          hideSold={hideSold}
        />
      )}
    </section>
  )
}

/* WHERE THIS CARD IS — the location card beside the photograph: the address, the neighbours a
 * hand counts by, the lens, and the one primary action for this copy. */
function LocationCard({
  row,
  layouts,
  wantedBy,
  action,
}: {
  row: Row
  layouts: ReadonlyMap<number, readonly SectionDetail[]>
  wantedBy: Wanted | null
  action: ReactNode
}) {
  const place: Place | undefined = row.card.place
  const label = positionLabel(row.card)
  const pooled = place?.located === false

  return (
    <section className="inventory-location">
      <div className="inventory-location-head">
        <span className="bn-label">
          <Icon name="pin" size={12} /> Location
        </span>
        {/* THE CORNER SAYS THE INDEX AND THE ADDRESS SAYS THE NAME (D132). `Box 3` is what the
            store keys the drawer by and `WB1 R1` is what the owner knows it as, so the name
            leads the address below and the index sits where the name used to. Drawn only when
            there IS a name; an unnamed box already reads `BOX 3` in the address. */}
        {place?.box_name ? <span className="inventory-location-boxname">Box {place.box}</span> : null}
      </div>

      {pooled ? (
        <p className="inventory-location-note">
          Pooled — a count, not a location. This card has no box, section or card position; the key{' '}
          <code className="inventory-inline">{row.key}</code> names its photo and sidecar on disk.
        </p>
      ) : label === null ? (
        <Notice tone="warn" title="The capture server sent no position label for this card." code={`label: absent · key ${row.key}`}>
          Either an older server is running — restart it and reload — or this record&rsquo;s box
          or index is not a number, which <code className="inventory-inline">GET /status</code> reports.
        </Notice>
      ) : (
        <>
          <div className="inventory-location-label">
            <PositionLabel label={label} boxName={place?.box_name ?? null} sectionName={place?.section_name ?? null} indexNote={false} />
          </div>
          <PlaceNeighbors place={place} />
          {/* THE LENS IS DRAWN FOR A DEPARTED COPY TOO (D118), and `departed` no longer gates it.
              The picture is of the BOX and the box is still there; what stops being true is that
              this copy is at a number in it, which the bar says by letting its mark fall out and
              muting the section it left. Skipping the block cost 85px of this card's height on
              the press that sold it — the panel collapsed 98px, 131 elements moved, and the same
              85px came back the moment the walk stepped onto a placed card. */}
          {place === undefined ? null : (
            <PositionBar place={place} persona="owner" sections={layouts.get(place.box)} sectionDepth />
          )}
        </>
      )}

      {/* An open order is waiting on this copy: the pull belongs on the order screen, and a
          walk-in sale here would take the card out from under it. */}
      {wantedBy === null ? null : (
        <a className="inventory-wanted" href="#/orders" title={`Order ${wantedBy.order} names this copy`}>
          <Icon name="cart" size={14} />
          <span className="inventory-wanted-text">
            Wanted by order <span className="inventory-wanted-number">{wantedBy.order}</span>
          </span>
          <Icon name="arrowRight" size={13} className="inventory-wanted-go" />
        </a>
      )}

      {action === null ? null : <div className="inventory-location-actions">{action}</div>}
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

/** What one copy offers: the word for the door it left by, or the two writes. `primary` is the
 *  location card's form — the one solid button on the screen; the rows draw the quiet one. */
function Action({
  copy,
  primary,
  busyKey,
  soldKeys,
  retiredKeys,
  undoableSales,
  onSell,
  onUndo,
  onRetire,
}: {
  copy: SearchCopy
  primary: boolean
  busyKey: string | null
  soldKeys: ReadonlySet<string>
  retiredKeys: ReadonlySet<string>
  undoableSales: ReadonlyMap<string, Receipt>
  onSell: (copy: SearchCopy) => void
  onUndo: (receipt: Receipt) => void
  onRetire: (copy: SearchCopy) => void
}) {
  const busy = busyKey === copy.key
  if (copy.state === 'sold' || soldKeys.has(copy.key)) {
    const standing = undoableSales.get(copy.key)
    /* After the undo window the state is a pill, in the register of every other state on the
       screen. A copy row's own state pill already says `sold` once the re-read lands, so only
       the location card and an optimistic sale still in flight draw one here. */
    return standing === undefined ? (
      primary || copy.state !== 'sold' ? (
        <Pill tone="ok" icon="check">
          Sold
        </Pill>
      ) : null
    ) : (
      <span
        className={primary ? 'bn-receipt inventory-receipt' : 'inventory-copy-actions'}
        style={primary ? { ['--receipt-ms' as string]: `${UNDO_WINDOW_MS}ms` } : undefined}
      >
        {primary ? <span className="inventory-receipt-said">Marked sold.</span> : null}
        {/* The undo window draining, the same clock the toast for this sale shows. */}
        {primary ? <span className="bn-receipt-bar" aria-hidden="true" /> : null}
        <Button
          size={primary ? 'md' : 'sm'}
          icon="undo"
          aria-label={`Undo the sale at ${standing.place}`}
          busy={busy}
          disabled={busyKey !== null && !busy}
          onClick={() => onUndo(standing)}
        >
          Undo
        </Button>
      </span>
    )
  }
  if (copy.state === 'retired' || retiredKeys.has(copy.key)) {
    return primary || copy.state !== 'retired' ? (
      <Pill tone="warn" icon="minus">
        Retired
      </Pill>
    ) : null
  }
  return (
    <span className={primary ? 'inventory-copy-actions is-primary' : 'inventory-copy-actions'}>
      <Button
        variant={primary ? 'primary' : 'default'}
        size={primary ? 'lg' : 'sm'}
        icon="check"
        busy={busy}
        disabled={busyKey !== null && !busy}
        onClick={() => onSell(copy)}
      >
        Mark sold
      </Button>
      <Button
        variant="ghost"
        size={primary ? 'md' : 'sm'}
        icon="minus"
        iconOnly={!primary}
        title={primary ? undefined : 'Retire'}
        disabled={busyKey !== null}
        onClick={() => onRetire(copy)}
      >
        Retire
      </Button>
    </span>
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
    <Overlay kind="dialog" label={`Retire: ${copy.place.label ?? copy.key}`} onClose={onCancel} className="inventory-confirm">
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
              src={photoUrl(copy.place.box, copy.place.index)}
              alt={`The card stored at ${copy.place.label ?? copy.key}`}
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

        <p className="bn-muted">
          The card leaves the inventory without a sale. Its record and photo stay, and the
          position is never reused.
        </p>

        <div className="inventory-retire-reasons" role="group" aria-label="Reason">
          {REASONS.map(({ reason, label, said }) => (
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
              <span className="inventory-machine">{reason}</span>
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
