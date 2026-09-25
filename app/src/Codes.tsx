import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import {
  applyBoxClaims,
  buildLot,
  describeFailure,
  exportCodes,
  getBoxes,
  getCodes,
  getLots,
  photoUrl,
  scanCodes,
  type Failure,
} from './server'
import type {
  BoxRecord,
  CodeEntry,
  CodeExportResult,
  CodeLedger,
  CodeScanResult,
  LotReceipt,
  LotResult,
} from './types'
import { Button, EmptyState, Icon, IconButton, Loading, Notice, Page, Pill, ReloadButton, Segmented, Select, Sheet, Stat, type IconName } from './kit'
import { toast } from './kit/toast'
import { absoluteDate } from './dates'
import { SearchField } from './SearchField'
import './Codes.css'

/* CODES — the code-card track on a route of its own (D14, D70).
 *
 * Nothing on this screen spends: the QR is the code, so reading a box is free. What is
 * irreversible is handing codes over — an export and a lot both reserve permanently — so each
 * of those is a preview first and a named, red confirm second, inside its own sheet.
 *
 * Opsec: a held code is a bearer instrument. Codes are masked on screen until revealed, are
 * never drawn larger than body size, and the photograph (which IS the QR) is a link rather
 * than an inline image. This route stays out of `scripts/views.txt` on purpose.
 */

type Lane = 'bulk' | 'premium'
type Venue = 'ebay' | 'tcgplayer'
type Delivery = 'physical' | 'digital'
type SheetName = 'scan' | 'hand' | 'lot'
type StateFilter = 'all' | 'held' | 'reserved' | 'delivered' | 'dead'
type LaneFilter = 'all' | 'premium' | 'bulk' | 'unclaimed'
type LedgerTab = 'codes' | 'lots'
type LotTab = 'listing' | 'packing' | 'manifest'
type Tone = 'default' | 'accent' | 'ok' | 'warn' | 'danger'

const VENUES: readonly { value: Venue; label: string }[] = [
  { value: 'ebay', label: 'eBay' },
  { value: 'tcgplayer', label: 'TCGplayer' },
]
const STATES: readonly { value: StateFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'held', label: 'Held' },
  { value: 'reserved', label: 'Reserved' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'dead', label: 'Dead' },
]
const LANES: readonly { value: LaneFilter; label: string }[] = [
  { value: 'premium', label: 'Premium' },
  { value: 'bulk', label: 'Bulk' },
  { value: 'unclaimed', label: 'Unclaimed' },
]
const ROW_CAP = 200
/** By-product rows drawn when the list folds. Measured at 1440: four rows plus the disclosure
 *  stand level with the pile's figures and lane bar, and five rows without one fit under them —
 *  so a sixth kind folds the list to four and the disclosure takes the fifth row's slot. */
const PRODUCT_FOLD = 4

function venueLabel(venue: string): string {
  return VENUES.find((v) => v.value === venue)?.label ?? venue
}

function stateLabel(state: string): string {
  return STATES.find((s) => s.value === state)?.label ?? state
}

function deliveryLabel(delivery: string): string {
  if (delivery === 'physical') return 'Physical'
  if (delivery === 'digital') return 'Digital'
  return delivery
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

/** The code with every letter and digit replaced, its 3-4-3-3 shape kept. */
function mask(code: string): string {
  return code.replace(/[A-Za-z0-9]/g, '•')
}

function stateTone(state: string): Tone {
  switch (state) {
    case 'held':
      return 'ok'
    case 'reserved':
      return 'accent'
    case 'dead':
      return 'danger'
    default:
      return 'default'
  }
}

function laneTone(lane: string): Tone {
  if (lane === 'premium') return 'accent'
  if (lane === 'none' || lane === 'unclaimed') return 'warn'
  return 'default'
}

function laneLabel(lane: string): string {
  if (lane === 'premium') return 'Premium'
  if (lane === 'bulk') return 'Bulk'
  return 'No lane'
}

function laneOf(entry: CodeEntry): LaneFilter {
  if (entry.product === null || entry.product === '') return 'unclaimed'
  return entry.premium ? 'premium' : 'bulk'
}

/** The box's name only (`D259`). A registry row that is absent or
 *  stale falls back to the number — the honest answer where there is genuinely no name to
 *  read, never a placeholder drawn over a fault that is not there. */
function boxName(box: number, boxes: BoxRecord[] | null): string {
  const name = boxes?.find((b) => b.box === box)?.name
  return typeof name === 'string' && name.trim() !== '' ? name : `Box ${box}`
}

/* D218: this renders inside a native `<option>`, which is plain text only — no element can
   carry the seam, so this is a real sentence (a comma list) rather than a typed dot. */
function boxLabel(box: BoxRecord): string {
  const held = box.on_hand ?? box.cards
  const name = typeof box.name === 'string' && box.name.trim() !== '' ? box.name : `Box ${box.box}`
  return `${name}, ${plural(held, 'card')}`
}

/* ---- sheet -----------------------------------------------------------------------------------
 * The kit's `Sheet` (`app/src/kit/overlay.tsx`) was seeded from this screen's own local one —
 * the portal, the focus return, the Escape handling and the scroll lock all moved there, plus
 * the overlay stack (D272's sibling, UX-057/UX-090/UX-091) this local copy never
 * had. Each of the three sheets below stays mounted and toggles `open`, so the kit's own exit
 * animation runs instead of the panel disappearing the instant `sheet` changes. */

/* ---- a code string, masked until asked ----------------------------------------------------------- */

function Code({ code, shown, odd }: { readonly code: string; readonly shown: boolean; readonly odd?: boolean }) {
  return (
    <span key={shown ? 'shown' : 'masked'} className={`codes-code${shown ? ' is-shown' : ''}${odd ? ' is-odd' : ''}`}>
      {shown ? code : mask(code)}
    </span>
  )
}

/** Clipboard state drawn on the control itself — a 'Copied' beat on success, an inline refusal on
 *  failure — and never a toast: inside a sheet on a phone the stack sits over the sheet's head, and
 *  the reserve receipt is already the one toast there. */
function useClipboard(): { readonly copied: boolean; readonly failed: boolean; readonly copy: (text: string) => Promise<void> } {
  const [copied, setCopied] = useState(false)
  const [failed, setFailed] = useState(false)
  const timer = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )
  const copy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setFailed(false)
      setCopied(true)
      if (timer.current !== null) window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
      setFailed(true)
    }
  }, [])
  return { copied, failed, copy }
}

/** The reserved codes, handed over: masked, revealable, copyable, downloadable. */
function CodeBlock({ codes, name }: { readonly codes: readonly string[]; readonly name: string }) {
  const [shown, setShown] = useState(false)
  const clip = useClipboard()
  const download = useCallback(() => {
    const blob = new Blob([`${codes.join('\n')}\n`], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name || 'codes'}.txt`
    a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, [codes, name])
  return (
    <div className="codes-block">
      <div className="codes-block-bar">
        <span className="bn-label">{plural(codes.length, 'code')}</span>
        <span className="bn-spacer" />
        <IconButton
          size="sm"
          icon={shown ? 'eyeOff' : 'eye'}
          label={shown ? 'Hide' : 'Reveal'}
          pressed={shown}
          onClick={() => setShown((s) => !s)}
        />
        <IconButton
          size="sm"
          icon={clip.copied ? 'check' : 'copy'}
          label={clip.copied ? 'Copied' : 'Copy all'}
          onClick={() => void clip.copy(codes.join('\n'))}
        />
        <IconButton size="sm" icon="download" label="Download the codes" onClick={download} />
      </div>
      {clip.failed ? (
        <div className="codes-block-notice">
          <Notice tone="danger" title="The clipboard refused">
            Reveal the codes and copy them by hand.
          </Notice>
        </div>
      ) : null}
      <ol className="codes-block-list">
        {codes.map((code) => (
          <li key={code}>
            <Code code={code} shown={shown} />
          </li>
        ))}
      </ol>
    </div>
  )
}

/** The manifest's path on the capture server, with a copy control that reports on itself. */
function ManifestPath({ path }: { readonly path: string }) {
  const clip = useClipboard()
  return (
    <>
      <div className="codes-path">
        <code>{path}</code>
        <IconButton
          size="sm"
          icon={clip.copied ? 'check' : 'copy'}
          label={clip.copied ? 'Copied' : 'Copy path'}
          onClick={() => void clip.copy(path)}
        />
      </div>
      {clip.failed ? (
        <Notice tone="danger" title="The clipboard refused">
          Select the path and copy it by hand.
        </Notice>
      ) : null}
    </>
  )
}

/* ---- a number the operator just caused ------------------------------------------------------------- */

function Figure({ n, of, label }: { readonly n: number; readonly of?: number; readonly label: ReactNode }) {
  return (
    <div className="codes-figure">
      <span className="codes-figure-n">
        {n.toLocaleString()}
        {of === undefined ? null : <small> of {of.toLocaleString()}</small>}
      </span>
      <span className="codes-figure-label">{label}</span>
    </div>
  )
}

function ProductTable({ rows }: { readonly rows: readonly { product: string; display: string; premium: boolean; count: number }[] }) {
  return (
    <table className="bn-table codes-mini-table">
      <thead>
        <tr>
          <th>Product</th>
          <th>Lane</th>
          <th className="num">Codes</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.product}>
            <td>{row.display}</td>
            <td>
              <Pill tone={row.premium ? 'accent' : 'default'}>{row.premium ? 'Premium' : 'Bulk'}</Pill>
            </td>
            <td className="num">{row.count.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* ==================================================================================================== */

export function Codes() {
  const [ledger, setLedger] = useState<CodeLedger | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  /* A failure to READ the ledger is the page's, not a sheet's: it is drawn as an empty state
     with the way back in it, and never inside a task sheet. */
  const [loadFailure, setLoadFailure] = useState<Failure | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [boxes, setBoxes] = useState<BoxRecord[] | null>(null)

  const [sheet, setSheet] = useState<SheetName | null>(null)

  const [box, setBox] = useState('')
  const [scan, setScan] = useState<CodeScanResult | null>(null)

  const [lane, setLane] = useState<Lane>('premium')
  const [preview, setPreview] = useState<CodeExportResult | null>(null)
  const [orderId, setOrderId] = useState('')
  const [committed, setCommitted] = useState<CodeExportResult | null>(null)

  const [filter, setFilter] = useState('')
  const [stateFilter, setStateFilter] = useState<StateFilter>('all')
  const [laneFilter, setLaneFilter] = useState<LaneFilter>('all')
  const [tab, setTab] = useState<LedgerTab>('codes')
  const [revealAll, setRevealAll] = useState(false)
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(() => new Set())
  const [showAll, setShowAll] = useState(false)
  const [dupOpen, setDupOpen] = useState(false)
  const [allProducts, setAllProducts] = useState(false)

  /* D70's product claim, corrected where the problem is stated. `fixPick` is per box because
     the panel offers one apply per box and each is a separate press; nothing here is kept
     across a reload, and nothing about a card goes near `localStorage`. */
  const [fixOpen, setFixOpen] = useState(false)
  const [fixPick, setFixPick] = useState<Record<number, string>>({})

  /* THE LOT BUILDER. Box-scoped and physical by default, which is the shape the owner
     settled on 2026-08-30: 1,000-card lots, shipped, eBay or TCGplayer only. */
  const [lotBox, setLotBox] = useState('')
  const [lotVenue, setLotVenue] = useState<Venue>('ebay')
  const [lotDelivery, setLotDelivery] = useState<Delivery>('physical')
  const [lotPlan, setLotPlan] = useState<LotResult | null>(null)
  const [lotId, setLotId] = useState('')
  const [lotBuilt, setLotBuilt] = useState<LotResult | null>(null)
  const [lotTab, setLotTab] = useState<LotTab>('listing')
  const [lots, setLots] = useState<LotReceipt[]>([])

  const load = useCallback(async () => {
    /* THE BOXES TRAVEL WITH THE LEDGER NOW, and until 2026-09-05 they were read once at mount
       and never again — the shape `Fulfillment.tsx` records as its own stale-row defect, and
       one this screen had a live stake in the moment the product fix started naming the box it
       is about to write to (a rename, or a box created on the other device, was drawn wrong
       here until a reload). Deliberately NOT inside the `Promise.all`: an unreadable box list
       costs the box FIELD its names and nothing else, and folding it in would let that take the
       whole ledger down with it. A failed re-read keeps the list it had rather than emptying
       one that was good a second ago. */
    const boxesRead = getBoxes()
      .then((summary) => setBoxes([...summary.boxes].sort((a, b) => b.box - a.box)))
      .catch(() => setBoxes((held) => held ?? []))
    try {
      const [ledgerNext, lotsNext] = await Promise.all([getCodes(), getLots()])
      setLedger(ledgerNext)
      setLots(lotsNext.lots)
      setLoadFailure(null)
    } catch (err) {
      setLoadFailure(describeFailure(err))
    }
    await boxesRead
  }, [])

  const retry = useCallback(async () => {
    setRetrying(true)
    try {
      await load()
    } finally {
      setRetrying(false)
    }
  }, [load])

  useEffect(() => {
    void load()
  }, [load])

  const closeSheet = useCallback(() => setSheet(null), [])

  /* The kit's Sheet owns focus, Escape and the scroll lock now — this is the one thing it does
     not do for a screen it does not know about: step the toast stack aside so a receipt never
     covers the open sheet (Codes.css's `body[data-codes-sheet] .bn-toasts` rule). */
  useEffect(() => {
    if (sheet === null) return
    document.body.setAttribute('data-codes-sheet', '')
    return () => document.body.removeAttribute('data-codes-sheet')
  }, [sheet])

  const runScan = useCallback(
    async (dryRun: boolean) => {
      const n = Number(box)
      if (!Number.isSafeInteger(n) || n < 1) {
        setFailure({ code: 'box_required', message: 'Choose the box whose photographs should be scanned.' })
        return
      }
      setBusy(true)
      setPending(dryRun ? 'scan-preview' : 'scan')
      try {
        setScan(await scanCodes({ box: n, preview: dryRun }))
        setFailure(null)
        if (!dryRun) await load()
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
        setPending(null)
      }
    },
    [box, load],
  )

  /* THE SECOND DOOR ONTO D70's PRODUCT CLAIM, and it is two writes rather than one.
   *
   * The claim lives on the CARD — `codes/scan.py` reads `capture.product` off the sidecar and
   * stamps it onto the ledger line — so correcting a code means writing the cards and then
   * reading their photographs again. `applyBoxClaims` rewrites the sidecar of every card it
   * changes and `scanCodes` merges the fresh read over the ledger, refreshing `product` on the
   * lines whose code and position are unchanged. Skip the second call and the store is right
   * while this screen, both lanes and every lot still say unclaimed.
   *
   * ONLY THE UNCLAIMED CODES' OWN POSITIONS ARE SENT, never the whole box: a box may hold two
   * stacks, and a sweep over all of it would overwrite a claim somebody made deliberately.
   * The server refuses the whole call if any of those positions has gone (`card_not_found`)
   * and steps over sold and retired records, naming them — both land in the receipt below.
   */
  const fixProduct = useCallback(
    async (box: number, indices: readonly number[], product: string, named: string) => {
      if (product === '') return
      setBusy(true)
      setPending(`fix-${box}`)
      try {
        const claimed = await applyBoxClaims(box, { product }, [...indices])
        const reread = await scanCodes({ box, preview: false })
        setFailure(null)
        const stepped =
          claimed.skipped_terminal === 0
            ? ''
            : ` ${plural(claimed.skipped_terminal, 'sold or retired record')} left alone.`
        toast(
          claimed.applied === 0
            ? {
                kind: 'status',
                title: 'Nothing moved',
                body: `Every card reached in ${boxName(box, boxes)} already said ${named}.${stepped}`,
              }
            : {
                kind: 'ok',
                title: `${plural(claimed.applied, 'card')} now ${named}`,
                body: `${boxName(box, boxes)} read again — ${plural(reread.decoded, 'code')} decoded.${stepped}`,
              },
        )
        await load()
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
        setPending(null)
      }
    },
    [load, boxes],
  )

  const runPreview = useCallback(async () => {
    setBusy(true)
    setPending('hand-preview')
    setCommitted(null)
    try {
      setPreview(await exportCodes({ lane }))
      setFailure(null)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }, [lane])

  const runCommit = useCallback(async () => {
    if (!orderId.trim()) {
      setFailure({
        code: 'order_id_required',
        message: 'A confirmed export assigns codes to an order, so it needs a name.',
      })
      return
    }
    setBusy(true)
    setPending('hand-commit')
    try {
      const done = await exportCodes({ lane, confirm: true, orderId: orderId.trim() })
      setCommitted(done)
      setPreview(null)
      setOrderId('')
      setFailure(null)
      toast({
        kind: 'ok',
        title: `${plural(done.count, 'code')} reserved to ${done.order_id ?? 'the order'}`,
        body: 'Copy them to the buyer from the sheet. They will never be offered again.',
      })
      await load()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }, [lane, orderId, load])

  const planLot = useCallback(async () => {
    const n = Number(lotBox)
    if (lotDelivery === 'physical' && (!Number.isSafeInteger(n) || n < 1)) {
      setFailure({
        code: 'box_required',
        message: 'A physical lot is scoped to a box — choose the box.',
      })
      return
    }
    setBusy(true)
    setPending('lot-plan')
    setLotBuilt(null)
    try {
      setLotPlan(
        await buildLot({
          scope: lotDelivery === 'physical' ? 'box' : 'count',
          delivery: lotDelivery,
          venue: lotVenue,
          box: Number.isSafeInteger(n) && n > 0 ? n : null,
          count: lotDelivery === 'digital' ? Number(lotBox) || null : null,
        }),
      )
      setFailure(null)
    } catch (err) {
      setLotPlan(null)
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }, [lotBox, lotVenue, lotDelivery])

  const commitLot = useCallback(async () => {
    const n = Number(lotBox)
    setBusy(true)
    setPending('lot-commit')
    try {
      const done = await buildLot({
        scope: lotDelivery === 'physical' ? 'box' : 'count',
        delivery: lotDelivery,
        venue: lotVenue,
        box: Number.isSafeInteger(n) && n > 0 ? n : null,
        count: lotDelivery === 'digital' ? Number(lotBox) || null : null,
        confirm: true,
        lotId: lotId.trim() || undefined,
      })
      setLotBuilt(done)
      setLotTab(done.listing !== undefined ? 'listing' : done.packing !== undefined ? 'packing' : 'manifest')
      setLotPlan(null)
      setLotId('')
      setFailure(null)
      toast({
        kind: 'ok',
        title: `Lot ${done.lot_id ?? ''} built`.replace(/\s+/g, ' ').trim(),
        body: `${plural(done.count, 'code')} reserved. The listing, packing slip and manifest are in the sheet.`,
      })
      await load()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }, [lotBox, lotVenue, lotDelivery, lotId, load])

  /* ---- the ledger, filtered ------------------------------------------------------------- */

  const rows = useMemo(() => {
    if (ledger === null) return []
    const needle = filter.trim().toLowerCase()
    return ledger.entries.filter((e) => {
      if (stateFilter !== 'all' && e.state !== stateFilter) return false
      if (laneFilter !== 'all' && laneOf(e) !== laneFilter) return false
      if (!needle) return true
      return (
        e.code.toLowerCase().includes(needle) ||
        (e.product_display ?? '').toLowerCase().includes(needle) ||
        (e.set_hint ?? '').toLowerCase().includes(needle) ||
        (e.order_id ?? '').toLowerCase().includes(needle) ||
        (e.buyer ?? '').toLowerCase().includes(needle) ||
        e.state.includes(needle)
      )
    })
  }, [ledger, filter, stateFilter, laneFilter])

  const laneCounts = useMemo(() => {
    const counts: Record<LaneFilter, number> = { all: 0, premium: 0, bulk: 0, unclaimed: 0 }
    if (ledger === null) return counts
    for (const e of ledger.entries) {
      if (stateFilter !== 'all' && e.state !== stateFilter) continue
      counts.all += 1
      counts[laneOf(e)] += 1
    }
    return counts
  }, [ledger, stateFilter])

  /* WHICH BOXES HOLD THE UNCLAIMED CODES, and what the rest of each box already says.
   *
   * `lanes.unclaimed` is the figure the banner draws and it is a count of HELD codes with no
   * product — the same three-way answer `codes_routes._pool` reaches — so this walks the same
   * population rather than a wider one, and a reserved or delivered code is nobody's business
   * here: it has left.
   *
   * `company` IS EVIDENCE AND NEVER A DEFAULT. The commonest claim among the box's OTHER held
   * codes is drawn beside the picker, and nothing is preselected: a stack came out of one
   * sealed product, so the neighbours are usually right — but D70 chose an unclaimed code
   * refused by both lanes over a plausible wrong one, and a pre-filled picker is exactly the
   * thoughtless press that ruling exists to prevent. */
  const unclaimedFix = useMemo(() => {
    const byBox = new Map<number, number[]>()
    const claimedIn = new Map<number, Map<string, number>>()
    let adrift = 0
    for (const e of ledger?.entries ?? []) {
      if (e.state !== 'held') continue
      if (e.product !== null && e.product !== '') {
        if (e.box === null) continue
        const seen = claimedIn.get(e.box) ?? new Map<string, number>()
        seen.set(e.product, (seen.get(e.product) ?? 0) + 1)
        claimedIn.set(e.box, seen)
        continue
      }
      if (e.box === null || e.index === null) {
        adrift += 1
        continue
      }
      const held = byBox.get(e.box)
      if (held === undefined) byBox.set(e.box, [e.index])
      else held.push(e.index)
    }
    const boxes = [...byBox.entries()]
      .map(([box, indices]) => {
        const ranked = [...(claimedIn.get(box) ?? new Map<string, number>()).entries()].sort(
          (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
        )
        const top = ranked[0]
        const display = top === undefined ? null : ledger?.products.find((p) => p.key === top[0])?.display
        return {
          box,
          indices: [...new Set(indices)].sort((a, b) => a - b),
          company: top === undefined || !display ? null : { display, count: top[1] },
        }
      })
      /* Biggest first: one press clears the most codes. Ties by box number, so the order is
         stable across a reload rather than the map's insertion order. */
      .sort((a, b) => b.indices.length - a.indices.length || a.box - b.box)
    return { boxes, adrift }
  }, [ledger])

  /* The route button aims at the box when there is exactly one to aim at — `#/inventory?box=`
     is the deep link the home screen and the review queue already use. Bare `#/inventory`
     otherwise, because picking one of several boxes for the operator would be a guess. */
  const lone = unclaimedFix.boxes.length === 1 ? unclaimedFix.boxes[0] : undefined
  const fixHash = lone === undefined ? '#/inventory' : `#/inventory?box=${lone.box}`

  const filterKey = `${stateFilter}|${laneFilter}|${filter.trim().toLowerCase()}`
  const visible = showAll ? rows : rows.slice(0, ROW_CAP)
  const filtered = stateFilter !== 'all' || laneFilter !== 'all' || filter.trim() !== ''

  const toggleRow = useCallback((code: string) => {
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }, [])

  const clearFilters = useCallback(() => {
    setFilter('')
    setStateFilter('all')
    setLaneFilter('all')
  }, [])

  /* ---- pieces -------------------------------------------------------------------------- */

  const failureNode =
    failure === null ? null : (
      <div className="codes-failure bn-anim-pop">
        <Notice tone="danger" title={failure.message} code={failure.code || undefined} />
        <IconButton size="sm" icon="x" label="Dismiss" onClick={() => setFailure(null)} />
      </div>
    )

  const boxField = (value: string, onChange: (next: string) => void, autoFocus?: boolean) =>
    boxes !== null && boxes.length > 0 ? (
      <Select
        label="Box"
        value={value === '' ? null : value}
        onChange={onChange}
        placeholder="Choose a box…"
        options={boxes.map((b) => ({ value: String(b.box), label: boxLabel(b) }))}
      />
    ) : (
      <label className="bn-field codes-field">
        <span className="bn-field-label">Box</span>
        <input
          className="bn-input"
          inputMode="numeric"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ''))}
          placeholder="Box number"
          autoFocus={autoFocus}
        />
      </label>
    )

  const held = ledger === null ? 0 : ledger.lanes.premium + ledger.lanes.bulk + ledger.lanes.unclaimed
  const segments =
    ledger === null
      ? []
      : [
          { key: 'premium', label: 'Premium', n: ledger.lanes.premium },
          { key: 'bulk', label: 'Bulk', n: ledger.lanes.bulk },
          { key: 'unclaimed', label: 'Unclaimed', n: ledger.lanes.unclaimed },
        ]
  const maxProduct = ledger === null ? 0 : Math.max(0, ...ledger.by_product.map((r) => r.count))
  /* folding five kinds to four behind a one-row disclosure would hide one row to show one control */
  const productsFold = ledger !== null && ledger.by_product.length > PRODUCT_FOLD + 1

  const openSheet = (name: SheetName) => {
    setFailure(null)
    setSheet(name)
  }

  /* ---- render -------------------------------------------------------------------------- */

  return (
    // TXT-39: the lede restated D70 ("the QR is the code") to the owner. Deleted.
    <Page
      title="Codes"
      icon="qr"
      className="codes"
      actions={
        <>
          <ReloadButton onReload={() => void load()} busy={busy} />
          {/* UX-159: ONE first step. With nothing on file yet, the empty state's own "Go to
              capture" is that step; this button would open a scan with nothing captured to
              read. Once the ledger holds anything, this is the one persistent action again. */}
          {ledger === null || ledger.total > 0 ? (
            <Button variant="primary" icon="qr" onClick={() => openSheet('scan')}>
              Read a box
            </Button>
          ) : null}
        </>
      }
    >
      {sheet === null ? failureNode : null}
      {loadFailure !== null && ledger !== null ? (
        <div className="codes-failure bn-anim-pop">
          <Notice tone="danger" title={loadFailure.message} code={loadFailure.code || undefined}>
            The screen is showing codes as they were last read.
          </Notice>
          <Button variant="ghost" size="sm" icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
            Try again
          </Button>
        </div>
      ) : null}

      {ledger === null ? (
        loadFailure === null ? (
          // R2-class: the pile/products/tasks regions stay (the real content below shares
          // their layout), but every shimmer box now comes from the kit's own `Loading`
          // rather than a hand-typed `bn-skeleton` div.
          <div className="codes-loading" aria-busy="true" aria-label="Reading codes">
            <div className="bn-panel codes-pile">
              <div className="codes-pile-main">
                <Loading shape="summary" label="Reading the pile" />
              </div>
              <aside className="codes-products" aria-hidden="true">
                <Loading shape="cards" rows={4} label="Reading products" />
              </aside>
            </div>
            <div className="codes-tasks" aria-hidden="true">
              <Loading shape="cards" rows={3} label="Reading tasks" />
            </div>
          </div>
        ) : (
          <div className="bn-panel codes-empty codes-unreadable">
            <EmptyState
              icon="alert"
              title="Codes could not be read"
              body={
                <>
                  <span className="codes-failure-msg">{loadFailure.message}</span>
                  Codes did not answer — nothing on this screen can be shown yet.
                  {loadFailure.code ? <code className="codes-failure-code">{loadFailure.code}</code> : null}
                </>
              }
              actions={
                <Button icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
                  Try again
                </Button>
              }
            />
          </div>
        )
      ) : ledger.total === 0 ? (
        <>
          <div className="bn-panel codes-empty">
            <EmptyState
              icon="qr"
              title="No codes on file yet"
              /* UX-159: ONE first step. With the ledger empty, the header hides its own
                 "Read a box" (above) — there is nothing captured yet for it to read — so
                 this is the only button on screen. Once a box is captured and read, the
                 header's button takes over as the one persistent action instead. */
              body="Set Game to Pokémon code cards on Capture, then come back and read the box."
              actions={
                <Button icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                  Go to capture
                </Button>
              }
            />
          </div>
          {lots.length === 0 ? null : (
            <section className="bn-panel codes-ledger">
              <div className="bn-panel-head">
                <span className="bn-section-title">
                  <Icon name="package" size={16} /> Lots
                </span>
              </div>
              <LotsTable lots={lots} boxes={boxes} />
            </section>
          )}
        </>
      ) : (
        <>
          {/* -------------------------------------------------------------- alerts */}
          {ledger.duplicates.length === 0 && ledger.lanes.unclaimed === 0 ? null : (
            <div className="codes-banners">
              {ledger.duplicates.length === 0 ? null : (
                <div className="codes-banner is-danger" role="status">
                  <Icon name="alert" size={18} />
                  <div className="codes-banner-text">
                    <strong>{plural(ledger.duplicates.length, 'duplicate code')}</strong> — one code read at two positions. Either one
                    card was photographed twice, or two cards bear one code and one of them is worth nothing. Look at both photographs
                    before selling either.
                  </div>
                  <Button
                    size="sm"
                    variant="danger"
                    iconRight={dupOpen ? 'chevronUp' : 'chevronDown'}
                    aria-expanded={dupOpen}
                    onClick={() => setDupOpen((o) => !o)}
                  >
                    Review duplicates
                  </Button>
                </div>
              )}
              {dupOpen && ledger.duplicates.length > 0 ? (
                <ul className="codes-dups bn-anim-in">
                  {ledger.duplicates.map((e) => {
                    const shown = revealAll || revealed.has(e.code)
                    const positions = [{ box: e.box, index: e.index }, ...e.duplicate_positions]
                    return (
                      <li key={e.code} className="codes-dup">
                        <button
                          type="button"
                          className="codes-code-btn"
                          onClick={() => toggleRow(e.code)}
                          aria-pressed={shown}
                          aria-label={shown ? 'Hide this code' : 'Reveal this code'}
                        >
                          <Code code={e.code} shown={shown} odd={!e.well_formed} />
                          <Icon name={shown ? 'eyeOff' : 'eye'} size={13} />
                        </button>
                        <span className="codes-dup-where">
                          {positions.map((p, i) =>
                            p.box === null || p.index === null ? (
                              <span key={i} className="bn-muted">
                                No position
                              </span>
                            ) : (
                              <a
                                key={i}
                                /* THE SLOT ROUTE: a code-card ledger line carries no `cid`
                                   (D172). `codes/ledger.py:Entry` is its own record — the
                                   code, its state, `box`, `index`, `photo` and
                                   `photo_sha256` — and it has never held the card record's
                                   name. NOR IS ITS `photo_sha256` ONE: that is the digest of
                                   the file as it stands, which a re-shoot moves, where a
                                   `cid` is frozen at issue and does not. */
                                href={photoUrl(p.box, p.index)}
                                target="_blank"
                                rel="noreferrer"
                                className="codes-dup-link"
                                aria-label={`Open the photograph at ${boxName(p.box, boxes)}, slot ${p.index}`}
                              >
                                <Icon name="image" size={13} />
                                <span>{boxName(p.box, boxes)}</span>
                                <span>
                                  slot <span className="codes-index">{p.index}</span>
                                </span>
                              </a>
                            ),
                          )}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              ) : null}
              {ledger.lanes.unclaimed === 0 ? null : (
                <div className="codes-banner is-warn" role="status">
                  <Icon name="alert" size={18} />
                  <div className="codes-banner-text">
                    <strong>{plural(ledger.lanes.unclaimed, 'held code')}</strong>{' '}
                    {ledger.lanes.unclaimed === 1 ? 'carries' : 'carry'} no product claim, so neither lane will take{' '}
                    {ledger.lanes.unclaimed === 1 ? 'it' : 'them'}. Treating one as a booster would be right most of the time — and
                    the time it is wrong, a premium code leaves in a penny lot.
                  </div>
                  <div className="codes-banner-acts">
                    {/* Solid on a tinted banner, as the duplicates banner beside it already is:
                        a `default` button here is surface-on-tint and reads as disabled. The
                        icon is the chevron alone — this is a disclosure, and a second glyph on
                        a 32px control is noise. */}
                    <Button
                      size="sm"
                      variant="primary"
                      iconRight={fixOpen ? 'chevronUp' : 'chevronDown'}
                      aria-expanded={fixOpen}
                      onClick={() => setFixOpen((o) => !o)}
                    >
                      Set the product
                    </Button>
                    <Button size="sm" variant="ghost" iconRight="arrowRight" onClick={() => (window.location.hash = fixHash)}>
                      Fix on Inventory
                    </Button>
                  </div>
                </div>
              )}
              {fixOpen && ledger.lanes.unclaimed > 0 ? (
                <div className="codes-fix bn-anim-in">
                  <p className="codes-fix-lede">
                    A stack came out of one sealed product, so the box is the unit. Applying writes the claim onto those
                    cards and reads the box again — nothing changes lane until it has.
                  </p>
                  {unclaimedFix.boxes.length === 0 ? null : (
                    <ul className="codes-fix-list">
                      {unclaimedFix.boxes.map((row) => {
                        const chosen = fixPick[row.box] ?? ''
                        const entry = ledger.products.find((p) => p.key === chosen)
                        const working = pending === `fix-${row.box}`
                        return (
                          <li key={row.box} className="codes-fix-row">
                            <div className="codes-fix-where">
                              <span className="codes-fix-box">{boxName(row.box, boxes)}</span>
                              <span className="codes-fix-n">{plural(row.indices.length, 'unclaimed code')}</span>
                              {row.company === null ? null : (
                                <span className="codes-fix-company">
                                  the other {plural(row.company.count, 'code')} in this box say {row.company.display}
                                </span>
                              )}
                            </div>
                            {/* The picker, the lane it lands in and the press are ONE group: at
                                820 the row wraps, and a button that wrapped on its own sat
                                under the box name rather than under the picker it answers. */}
                            <div className="codes-fix-do">
                              <Select
                                label="Product"
                                value={chosen === '' ? null : chosen}
                                onChange={(next) => setFixPick((held) => ({ ...held, [row.box]: next }))}
                                placeholder="Choose a product…"
                                options={ledger.products.map((p) => ({ value: p.key, label: p.display }))}
                                disabled={busy}
                              />
                              {/* OUTLINED WHEN IT IS NOT PREMIUM. A default pill's fill is
                                  `--bn-surface-2`, which is this row's own ground, so Bulk
                                  drew as bare text beside a filled Premium chip and the two
                                  lanes stopped looking like one control's two answers. */}
                              <span className="codes-fix-lane">
                                {entry === undefined ? null : (
                                  <Pill tone={entry.premium ? 'accent' : 'default'} outline={!entry.premium}>
                                    {entry.premium ? 'Premium' : 'Bulk'}
                                  </Pill>
                                )}
                              </span>
                              <Button
                                size="sm"
                                variant="primary"
                                icon="check"
                                busy={working}
                                disabled={busy || chosen === ''}
                                onClick={() => void fixProduct(row.box, row.indices, chosen, entry?.display ?? chosen)}
                              >
                                Apply to {plural(row.indices.length, 'code')}
                              </Button>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                  {unclaimedFix.adrift === 0 ? null : (
                    <p className="codes-fix-adrift">
                      {plural(unclaimedFix.adrift, 'code')} {unclaimedFix.adrift === 1 ? 'carries' : 'carry'} no position, so there is
                      no card record to write a claim onto. Read {unclaimedFix.adrift === 1 ? 'its' : 'their'}{' '}
                      box again, or hand {unclaimedFix.adrift === 1 ? 'it' : 'them'} over by product below.
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {/* ---------------------------------------------------------------- hero */}
          <section className="bn-panel codes-pile" aria-label="The pile">
            <div className="codes-pile-main">
              <div className="codes-pile-head">
                <span className="bn-section-title">
                  <Icon name="layers" size={16} /> The pile
                </span>
                <span className="codes-pile-sum">
                  <span>
                    <strong>{plural(held, 'code')}</strong> on hand
                  </span>
                  <span>{ledger.total.toLocaleString()} on file</span>
                </span>
              </div>
              <div className="codes-stats">
                <Stat className="codes-stat is-premium" value={ledger.lanes.premium.toLocaleString()} label={<><span>Premium</span><span className="codes-stat-sub">sold singly</span></>} />
                <Stat className="codes-stat" value={ledger.lanes.bulk.toLocaleString()} label={<><span>Bulk</span><span className="codes-stat-sub">sold by lot</span></>} />
                <Stat
                  className={`codes-stat${ledger.lanes.unclaimed > 0 ? ' is-warn' : ''}`}
                  value={ledger.lanes.unclaimed.toLocaleString()}
                  label={<><span>Unclaimed</span><span className="codes-stat-sub">no lane</span></>}
                />
                <Stat className="codes-stat is-gone is-first-gone" value={(ledger.counts.reserved ?? 0).toLocaleString()} label={<><span>Reserved</span><span className="codes-stat-sub">to an order</span></>} />
                <Stat className="codes-stat is-gone" value={(ledger.counts.delivered ?? 0).toLocaleString()} label={<><span>Delivered</span><span className="codes-stat-sub">handed over</span></>} />
                <Stat className={`codes-stat is-gone${(ledger.counts.dead ?? 0) > 0 ? ' is-danger' : ''}`} value={(ledger.counts.dead ?? 0).toLocaleString()} label={<><span>Dead</span><span className="codes-stat-sub">worth nothing</span></>} />
              </div>
              <div className="codes-pile-bar">
                <div className="codes-lanebar" role="img" aria-label={segments.map((s) => `${s.label} ${s.n}`).join(', ')}>
                  {held === 0 ? (
                    <span className="codes-lanebar-empty" />
                  ) : (
                    segments
                      .filter((s) => s.n > 0)
                      .map((s, i) => (
                        <span
                          key={s.key}
                          className={`codes-lanebar-seg is-${s.key}`}
                          style={{ flexGrow: s.n, animationDelay: `${120 + i * 90}ms` }}
                          // D218: a `title=` attribute cannot hold elements, so this is a
                          // sentence — count then label — rather than a typed separator.
                          title={`${s.n.toLocaleString()} ${s.label.toLowerCase()}`}
                        />
                      ))
                  )}
                </div>
                <div className="codes-legend">
                  {segments.map((s) => (
                    <span key={s.key} className={`codes-legend-item is-${s.key}`}>
                      <i className="codes-legend-dot" />
                      {s.label}
                      <span className="codes-legend-n">{held === 0 ? '0%' : `${Math.round((s.n / held) * 100)}%`}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <aside className="codes-products" aria-label="By product">
              <div className="codes-products-head">
                <span className="bn-section-title">
                  <Icon name="tag" size={16} /> By product
                </span>
                <span className="bn-muted">{plural(ledger.by_product.length, 'kind')}</span>
              </div>
              {ledger.by_product.length === 0 ? (
                <p className="codes-products-empty">No product claims yet.</p>
              ) : (
                <ul className="codes-product-list">
                  {(allProducts || !productsFold ? ledger.by_product : ledger.by_product.slice(0, PRODUCT_FOLD)).map((row, i) => (
                    <li key={row.product} className="codes-product" style={{ '--delay': `${80 + i * 30}ms` } as CSSProperties}>
                      <span className="codes-product-name">{row.display}</span>
                      <Pill tone={laneTone(row.lane)}>{laneLabel(row.lane)}</Pill>
                      <span className="codes-product-n">{row.count.toLocaleString()}</span>
                      <span className={`codes-product-bar is-${row.lane}`}>
                        <span style={{ width: `${maxProduct === 0 ? 0 : Math.max(2, (row.count / maxProduct) * 100)}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {productsFold ? (
                <div className="codes-products-foot">
                  <Button
                    size="sm"
                    variant="ghost"
                    iconRight={allProducts ? 'chevronUp' : 'chevronDown'}
                    aria-expanded={allProducts}
                    onClick={() => setAllProducts((a) => !a)}
                  >
                    {allProducts ? 'Show fewer' : `Show all ${plural(ledger.by_product.length, 'kind')}`}
                  </Button>
                </div>
              ) : null}
            </aside>
          </section>

          {/* --------------------------------------------------------------- tasks */}
          <section className="codes-tasks" aria-label="Tasks">
            <TaskCard
              icon="qr"
              title="Read a box"
              body="Decode a box's code-card photographs."
              meta="Free"
              tone="accent"
              delay={0}
              onOpen={() => openSheet('scan')}
            />
            <TaskCard
              icon="hand"
              title="Hand codes to a buyer"
              body="Reserve a lane's codes to an order."
              meta={
                <>
                  <span>{`Premium\u00a0${ledger.lanes.premium.toLocaleString()}`}</span>
                  <span>{`Bulk\u00a0${ledger.lanes.bulk.toLocaleString()}`}</span>
                </>
              }
              tone="warn"
              delay={50}
              onOpen={() => openSheet('hand')}
            />
            <TaskCard
              icon="package"
              title="Build a lot"
              body="A whole box, shipped, with its listing, packing slip and manifest."
              meta={lots.length === 0 ? 'No lots built yet' : `${plural(lots.length, 'lot')} built`}
              tone="ok"
              delay={100}
              onOpen={() => openSheet('lot')}
            />
          </section>

          {/* -------------------------------------------------------------- ledger */}
          <section className="bn-panel codes-ledger">
            <div className="codes-ledger-head">
              <div className="bn-tabs codes-tabs" role="tablist" aria-label="Ledger">
                <button type="button" role="tab" className="bn-tab" aria-selected={tab === 'codes'} onClick={() => setTab('codes')}>
                  Codes <Pill>{ledger.total.toLocaleString()}</Pill>
                </button>
                <button type="button" role="tab" className="bn-tab" aria-selected={tab === 'lots'} onClick={() => setTab('lots')}>
                  Lots <Pill>{lots.length.toLocaleString()}</Pill>
                </button>
              </div>
              {tab === 'codes' ? (
                <SearchField
                  value={filter}
                  onChange={setFilter}
                  persona="owner"
                  label="Find a code"
                  placeholder="Find a code, product, set or order"
                  controlHeight="bar"
                />
              ) : null}
            </div>

            {tab === 'lots' ? (
              lots.length === 0 ? (
                <EmptyState
                  icon="package"
                  title="No lots built yet"
                  body="A whole box, shipped, with its listing, packing slip and manifest."
                  actions={
                    <Button icon="package" onClick={() => openSheet('lot')}>
                      Build a lot
                    </Button>
                  }
                />
              ) : (
                <LotsTable lots={lots} boxes={boxes} />
              )
            ) : (
              <>
                <div className="codes-toolbar">
                  <div className="codes-chips" role="group" aria-label="State">
                    {STATES.map((s) => {
                      const n = s.value === 'all' ? ledger.total : (ledger.counts[s.value] ?? 0)
                      return (
                        <button
                          key={s.value}
                          type="button"
                          className="codes-chip"
                          aria-pressed={stateFilter === s.value}
                          onClick={() => setStateFilter(s.value)}
                        >
                          {s.label}
                          <span className="codes-chip-n">{n.toLocaleString()}</span>
                        </button>
                      )
                    })}
                  </div>
                  <span className="codes-toolbar-sep" aria-hidden="true" />
                  <div className="codes-chips" role="group" aria-label="Lane">
                    {LANES.map((l) => (
                      <button
                        key={l.value}
                        type="button"
                        className={`codes-chip is-${l.value}`}
                        aria-pressed={laneFilter === l.value}
                        onClick={() => setLaneFilter((cur) => (cur === l.value ? 'all' : l.value))}
                      >
                        <i className="codes-chip-dot" />
                        {l.label}
                        <span className="codes-chip-n">{laneCounts[l.value].toLocaleString()}</span>
                      </button>
                    ))}
                  </div>
                  <span className="bn-spacer" />
                  <IconButton
                    size="sm"
                    icon={revealAll ? 'eyeOff' : 'eye'}
                    label={revealAll ? 'Hide codes' : 'Reveal codes'}
                    pressed={revealAll}
                    onClick={() => setRevealAll((r) => !r)}
                  />
                </div>

                {rows.length === 0 ? (
                  <EmptyState
                    icon="search"
                    title="Nothing matches"
                    body="No code matches those filters."
                    actions={
                      <Button icon="x" onClick={clearFilters}>
                        Clear filters
                      </Button>
                    }
                  />
                ) : (
                  <>
                    <div className="codes-table-wrap">
                      <table className="bn-table codes-table codes-entries">
                        <thead>
                          <tr>
                            <th>Code</th>
                            <th>State</th>
                            <th>Product</th>
                            <th>Set</th>
                            <th>Position</th>
                            <th>Order</th>
                            <th className="codes-th-photo">
                              <span className="bn-sr">Photograph</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody key={filterKey}>
                          {visible.map((e: CodeEntry, i) => {
                            const shown = revealAll || revealed.has(e.code)
                            const lane = laneOf(e)
                            return (
                              <tr key={e.code} className={`codes-row is-${e.state}`} style={{ animationDelay: `${Math.min(i, 24) * 16}ms` }}>
                                <td data-th="Code">
                                  <button
                                    type="button"
                                    className="codes-code-btn"
                                    onClick={() => toggleRow(e.code)}
                                    aria-pressed={shown}
                                    aria-label={shown ? 'Hide this code' : 'Reveal this code'}
                                  >
                                    <Code code={e.code} shown={shown} odd={!e.well_formed} />
                                    <Icon name={shown ? 'eyeOff' : 'eye'} size={13} />
                                  </button>
                                </td>
                                <td data-th="State">
                                  <Pill tone={stateTone(e.state)}>{stateLabel(e.state)}</Pill>
                                </td>
                                <td data-th="Product">
                                  <span className="codes-product-cell">
                                    {e.product_display ?? <span className="codes-unclaimed">No claim</span>}
                                    {lane === 'premium' ? <Pill tone="accent">{laneLabel('premium')}</Pill> : null}
                                  </span>
                                </td>
                                <td data-th="Set" className="codes-mono" data-empty={e.set_hint ? undefined : ''}>
                                  {e.set_hint ?? <span className="bn-faint">—</span>}
                                </td>
                                <td data-th="Position">
                                  {e.box === null || e.index === null ? (
                                    <span className="bn-faint">—</span>
                                  ) : (
                                    <span className="codes-where">
                                      <span className="codes-where-parts">
                                        <span>{boxName(e.box, boxes)}</span>
                                        <span>
                                          slot <span className="codes-index">{e.index}</span>
                                        </span>
                                      </span>
                                      {e.duplicate_positions.length > 0 ? <Pill tone="danger">Read twice</Pill> : null}
                                    </span>
                                  )}
                                </td>
                                <td data-th="Order" className="codes-mono" data-empty={e.order_id ? undefined : ''}>
                                  {e.order_id ?? <span className="bn-faint">—</span>}
                                </td>
                                <td data-th="Photo" className="codes-td-photo">
                                  {e.box === null || e.index === null ? null : (
                                    <a
                                      /* The slot route, for the duplicate list's reason
                                         above: the ledger carries no `cid`. */
                                      href={photoUrl(e.box, e.index)}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="codes-photo-link"
                                      aria-label={`Open the photograph at ${boxName(e.box, boxes)}, slot ${e.index}`}
                                    >
                                      <Icon name="image" size={15} />
                                      <span className="codes-photo-word">Photograph</span>
                                    </a>
                                  )}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="codes-ledger-foot">
                      <span className="bn-muted">
                        {rows.length > visible.length
                          ? `Showing ${visible.length.toLocaleString()} of ${rows.length.toLocaleString()}`
                          : filtered
                            ? `${plural(rows.length, 'code')} match`
                            : `${plural(rows.length, 'code')} on file`}
                      </span>
                      {rows.length > visible.length ? (
                        <Button size="sm" variant="ghost" onClick={() => setShowAll(true)}>
                          Show all {rows.length.toLocaleString()}
                        </Button>
                      ) : filtered ? (
                        <Button size="sm" variant="ghost" icon="x" onClick={clearFilters}>
                          Clear filters
                        </Button>
                      ) : null}
                    </div>
                  </>
                )}
              </>
            )}
          </section>
        </>
      )}

      {/* ================================================================ sheets */}
      <Sheet open={sheet === 'scan'} title="Read a box" icon="qr" onClose={closeSheet} className="codes-sheet">
          {failureNode}
          <p className="codes-sheet-lede">Free.</p>
          <form
            className="codes-form"
            onSubmit={(e) => {
              e.preventDefault()
              void runScan(false)
            }}
          >
            {boxField(box, setBox, true)}
            <div className="codes-form-actions">
              <Button type="button" icon="eye" busy={pending === 'scan-preview'} disabled={busy} onClick={() => void runScan(true)}>
                Preview
              </Button>
              <Button type="submit" variant="primary" icon="qr" busy={pending === 'scan'} disabled={busy}>
                Read the box
              </Button>
            </div>
          </form>

          {scan === null ? null : (
            <div className="codes-result bn-anim-in" key={`${scan.box}-${scan.preview ? 'p' : 'w'}-${scan.decoded}`}>
              <div className="codes-result-head">
                <Figure n={scan.decoded} of={scan.code_cards} label={<>code cards decoded in {boxName(scan.box, boxes)}</>} />
                {scan.preview ? (
                  <Pill tone="accent" icon="eye">
                    Preview — nothing written
                  </Pill>
                ) : (
                  <Pill tone="ok" icon="check">
                    Written
                  </Pill>
                )}
              </div>
              {scan.photographs !== scan.code_cards ? (
                <p className="codes-result-note">
                  {plural(scan.photographs - scan.code_cards, 'photograph')} of other games left alone.
                </p>
              ) : null}
              {scan.unread.length === 0 ? null : (
                <Notice tone="warn" title={`${plural(scan.unread.length, 'card')} did not read`}>
                  None is lost — each keeps its photograph and its position. The next reader is the paid vision transcription, then a
                  human.
                  <ul className="codes-mono-list">
                    {scan.unread.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </Notice>
              )}
              {scan.malformed.length === 0 ? null : (
                <Notice tone="info" title={`${plural(scan.malformed.length, 'code')} decoded but not in the printed 3-4-3-3 shape`}>
                  Kept and marked, never refused: a payload that survived the QR's own error correction is likelier to be an
                  unfamiliar print run than a misread.
                  <ul className="codes-mono-list">
                    {scan.malformed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </Notice>
              )}
            </div>
          )}
      </Sheet>

      {ledger !== null ? (
        <Sheet open={sheet === 'hand'} title="Hand codes to a buyer" icon="hand" onClose={closeSheet} className="codes-sheet">
          {failureNode}
          <p className="codes-sheet-lede">
            Confirming reserves every code it returns, permanently. A reserved code is never offered again — that is what stands
            between this pile and selling one code twice.
          </p>
          <div className="bn-field">
            <span className="bn-field-label">Lane</span>
            <Segmented<Lane>
              className="codes-seg"
              label="Lane"
              value={lane}
              options={[
                {
                  value: 'premium',
                  label: (
                    <>
                      <span>Premium</span>
                      <span className="codes-seg-n">{ledger.lanes.premium.toLocaleString()}</span>
                    </>
                  ),
                },
                {
                  value: 'bulk',
                  label: (
                    <>
                      <span>Bulk</span>
                      <span className="codes-seg-n">{ledger.lanes.bulk.toLocaleString()}</span>
                    </>
                  ),
                },
              ]}
              onChange={(next) => {
                setLane(next)
                setPreview(null)
                setCommitted(null)
              }}
            />
          </div>
          <div className="codes-form-actions">
            <Button icon="eye" busy={pending === 'hand-preview'} disabled={busy} onClick={() => void runPreview()}>
              Preview the {lane} lane
            </Button>
          </div>

          {preview === null ? null : (
            <div className="codes-result bn-anim-in">
              <div className="codes-result-head">
                <Figure n={preview.available} label={<>{preview.available === 1 ? 'code' : 'codes'} available in the {preview.lane} lane</>} />
              </div>
              <p className="codes-result-note">{preview.note}</p>
              {preview.sample && preview.sample.length > 0 ? (
                <div className="codes-sample">
                  <span className="bn-label">Sample</span>
                  {preview.sample.map((code) => (
                    <Code key={code} code={code} shown={false} />
                  ))}
                </div>
              ) : null}
              {preview.available === 0 ? null : (
                <div className="codes-confirm">
                  <label className="bn-field codes-field">
                    <span className="bn-field-label">Order name</span>
                    <input
                      className="bn-input"
                      value={orderId}
                      onChange={(e) => setOrderId(e.target.value)}
                      placeholder="wholesale-2026-09-02"
                      autoFocus
                    />
                    <span className="bn-field-hint">For matching to a settlement statement later.</span>
                  </label>
                  <Button
                    variant="danger-solid"
                    size="lg"
                    icon="lock"
                    block
                    busy={pending === 'hand-commit'}
                    disabled={busy || !orderId.trim()}
                    onClick={() => void runCommit()}
                  >
                    Reserve {plural(preview.available, 'code')} — cannot be undone
                  </Button>
                </div>
              )}
            </div>
          )}

          {committed === null ? null : (
            <div className="codes-result is-done bn-anim-in">
              <Notice tone="ok" title={`${plural(committed.count, 'code')} reserved${committed.order_id ? ` to ${committed.order_id}` : ''}`}>
                {committed.note}
              </Notice>
              <CodeBlock codes={committed.codes ?? []} name={committed.order_id ?? 'codes'} />
              <p className="codes-result-note">
                Copy these to the buyer. Nothing here sends anything anywhere — there is no channel integration, on purpose.
              </p>
            </div>
          )}
        </Sheet>
      ) : null}

      <Sheet open={sheet === 'lot'} title="Build a lot" icon="package" onClose={closeSheet} className="codes-sheet">
          {failureNode}
          <p className="codes-sheet-lede">
            A physical lot is <strong>the whole box, or nothing</strong> — anything left in the box would go in the parcel anyway.
            Move the strays out first; the refusal names where they sit.
          </p>
          <form
            className="codes-form"
            onSubmit={(e) => {
              e.preventDefault()
              void planLot()
            }}
          >
            <div className="codes-form-row">
              <div className="bn-field">
                <span className="bn-field-label">Delivery</span>
                <Segmented<Delivery>
                  className="codes-seg"
                  label="Delivery"
                  value={lotDelivery}
                  options={[
                    { value: 'physical', label: 'Physical', icon: 'package' },
                    { value: 'digital', label: 'Digital', icon: 'send' },
                  ]}
                  onChange={(next) => {
                    setLotDelivery(next)
                    setLotPlan(null)
                    setLotBuilt(null)
                  }}
                />
              </div>
              <div className="bn-field">
                <span className="bn-field-label">Venue</span>
                <Segmented<Venue> className="codes-seg" label="Venue" value={lotVenue} options={VENUES} onChange={setLotVenue} />
              </div>
            </div>
            {lotDelivery === 'physical' ? (
              boxField(lotBox, setLotBox, true)
            ) : (
              <label className="bn-field codes-field">
                <span className="bn-field-label">How many codes</span>
                <input
                  className="bn-input"
                  inputMode="numeric"
                  value={lotBox}
                  onChange={(e) => setLotBox(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="1000"
                  autoFocus
                />
              </label>
            )}
            <div className="codes-form-actions">
              <Button type="submit" variant="primary" icon="ruler" busy={pending === 'lot-plan'} disabled={busy}>
                Plan the lot
              </Button>
            </div>
          </form>

          {lotPlan === null ? null : (
            <div className="codes-result bn-anim-in">
              <div className="codes-result-head">
                <Figure
                  n={lotPlan.count}
                  label={
                    <>
                      <span>
                        {lotPlan.count === 1 ? 'code' : 'codes'}
                        {lotPlan.box === null ? '' : ` in ${boxName(lotPlan.box, boxes)}`}
                      </span>
                      <span>{venueLabel(lotPlan.venue)}</span>
                      <span>{deliveryLabel(lotPlan.delivery)}</span>
                    </>
                  }
                />
              </div>
              <p className="codes-result-note">{lotPlan.note}</p>
              {lotPlan.premium_in_lot > 0 ? (
                <Notice tone="danger" title={`${plural(lotPlan.premium_in_lot, 'premium code')} in this lot`}>
                  A premium code lists at roughly 46× a booster. Selling one inside a bulk lot is the most expensive mistake on this
                  track — make sure this is deliberate.
                </Notice>
              ) : null}
              {lotPlan.by_product.length === 0 ? null : <ProductTable rows={lotPlan.by_product} />}
              {lotPlan.sets.length === 0 ? null : (
                <div className="codes-sets">
                  {lotPlan.sets.map((s) => (
                    <Pill key={s.set} mono>
                      <span>{s.set}</span>
                      <span className="codes-set-count">{s.count}</span>
                    </Pill>
                  ))}
                </div>
              )}
              <div className="codes-confirm">
                <label className="bn-field codes-field">
                  <span className="bn-field-label">Lot name</span>
                  <input
                    className="bn-input"
                    value={lotId}
                    onChange={(e) => setLotId(e.target.value)}
                    placeholder={`${lotVenue}-${new Date().toISOString().slice(0, 10)}${lotPlan.box === null ? '' : `-box${lotPlan.box}`}`}
                  />
                  <span className="bn-field-hint">
                    For matching to a settlement statement later. Blank generates one.
                  </span>
                </label>
                <Button
                  variant="danger-solid"
                  size="lg"
                  icon="lock"
                  block
                  busy={pending === 'lot-commit'}
                  disabled={busy}
                  onClick={() => void commitLot()}
                >
                  Reserve {plural(lotPlan.count, 'code')} — cannot be undone
                </Button>
              </div>
            </div>
          )}

          {lotBuilt === null ? null : (
            <div className="codes-result is-done bn-anim-in">
              <Notice tone="ok" title={`Lot ${lotBuilt.lot_id ?? ''} built — ${plural(lotBuilt.count, 'code')} reserved`}>
                {lotBuilt.note}
              </Notice>
              <div className="bn-tabs codes-tabs" role="tablist" aria-label="Lot files">
                {lotBuilt.listing === undefined ? null : (
                  <button type="button" role="tab" className="bn-tab" aria-selected={lotTab === 'listing'} onClick={() => setLotTab('listing')}>
                    Listing
                  </button>
                )}
                {lotBuilt.packing === undefined ? null : (
                  <button type="button" role="tab" className="bn-tab" aria-selected={lotTab === 'packing'} onClick={() => setLotTab('packing')}>
                    Packing slip
                  </button>
                )}
                <button type="button" role="tab" className="bn-tab" aria-selected={lotTab === 'manifest'} onClick={() => setLotTab('manifest')}>
                  Manifest
                </button>
              </div>
              {lotTab === 'listing' && lotBuilt.listing !== undefined ? (
                <pre className="codes-pre is-prose">{lotBuilt.listing}</pre>
              ) : lotTab === 'packing' && lotBuilt.packing !== undefined ? (
                <pre className="codes-pre">{lotBuilt.packing}</pre>
              ) : (
                <div className="codes-manifest">
                  <p className="codes-result-note">
                    The buyer&rsquo;s manifest is a file on the capture server, kept out of this page on purpose — a thousand live
                    codes drawn here would land in every screenshot that ever caught it.
                  </p>
                  {lotBuilt.files?.['manifest.txt'] ? (
                    <ManifestPath path={lotBuilt.files['manifest.txt']} />
                  ) : (
                    <p className="bn-muted">No manifest path came back.</p>
                  )}
                </div>
              )}
            </div>
          )}
      </Sheet>
    </Page>
  )
}

/* ---- task card ---------------------------------------------------------------------------------- */

function TaskCard({
  icon,
  title,
  body,
  meta,
  tone,
  delay,
  onOpen,
}: {
  readonly icon: IconName
  readonly title: string
  readonly body: string
  readonly meta: ReactNode
  readonly tone: 'accent' | 'warn' | 'ok'
  readonly delay: number
  readonly onOpen: () => void
}) {
  return (
    <button type="button" className={`codes-task is-${tone}`} onClick={onOpen} style={{ animationDelay: `${delay}ms` }}>
      <span className="codes-task-icon">
        <Icon name={icon} size={20} />
      </span>
      <span className="codes-task-text">
        <span className="codes-task-title">{title}</span>
        <span className="codes-task-body">{body}</span>
      </span>
      <span className="codes-task-foot">
        <span className="codes-task-meta">{meta}</span>
        <span className="codes-task-go">
          Open <Icon name="arrowRight" size={14} />
        </span>
      </span>
    </button>
  )
}

/* ---- lots table --------------------------------------------------------------------------------- */

function LotsTable({ lots, boxes }: { readonly lots: readonly LotReceipt[]; readonly boxes: BoxRecord[] | null }) {
  return (
    <div className="codes-table-wrap">
      <table className="bn-table codes-table codes-lots">
        <thead>
          <tr>
            <th>Lot</th>
            <th className="num">Codes</th>
            <th>Box</th>
            <th>Delivery</th>
            <th>Venue</th>
            <th>Products</th>
            <th>Built</th>
          </tr>
        </thead>
        <tbody>
          {lots.map((l, i) => (
            <tr key={l.lot_id} className="codes-row" style={{ animationDelay: `${Math.min(i, 24) * 16}ms` }}>
              <td data-th="Lot" className="codes-mono">
                {l.lot_id}
              </td>
              <td data-th="Codes" className="num">
                {l.count.toLocaleString()}
              </td>
              <td data-th="Box">{l.box === null ? <span className="bn-faint">—</span> : boxName(l.box, boxes)}</td>
              <td data-th="Delivery">
                <Pill icon={l.delivery === 'physical' ? 'package' : 'send'}>{deliveryLabel(l.delivery)}</Pill>
              </td>
              <td data-th="Venue">{venueLabel(l.venue)}</td>
              <td data-th="Products">
                <span className="codes-lot-products">
                  {l.by_product.map((p) => (
                    <span key={p.product} className={`codes-lot-product${p.premium ? ' is-premium' : ''}`}>
                      {p.display} <span className="codes-lot-product-n">{p.count}</span>
                    </span>
                  ))}
                </span>
              </td>
              <td data-th="Built">{absoluteDate(l.built_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
