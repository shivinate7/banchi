import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent, ReactNode } from 'react'
import { Button, FailureNotice, Icon, IconButton, Segmented, useUndoHotkey } from './kit'
import { UNNAMED_BOX } from './kit/data'
import { Page } from './kit/Page'
import { describeFailure, getBoxes, getInventoryBox, moveSectionsBatch, undoSectionMove } from './server'
import type { Failure } from './server'
import { isEditableTarget } from './keys'
import type {
  BoxRecord,
  InventoryCard,
  RangeMoveBatchStep,
  SectionDetail,
  SectionMoveBatchResult,
  SectionMoveBatchStep,
} from './types'
import './BoxShelf.css'

/* THE SHELF: every box, sections running back to front, left to right (D264, the owner's
 * horizontal ruling, 2026-09-26: "using horizontal rather than vertical it seems more
 * intuitive" as boxes grow).
 *
 * READ-ONLY UNTIL EDIT LAYOUT. The owner's words: "i enter an edit mode, in this edit mode i
 * can drag and drop freely, and then i have to hit confirm once im happy with the layout." So
 * a drag in edit mode queues a move into a DRAFT — nothing is written — and every queued move
 * applies together, in the ORDER queued, on Confirm: one store transaction, or none of it
 * (D88, `do_move_sections_batch`). Cancel throws the draft away. Confirm's receipt carries one
 * Undo that reverses the whole layout, the same primitive a single move already used.
 *
 * THE CONFIRM GATE SEES CARDS, NOT ONLY DIVIDERS (the strict review's finding, 2026-09-27).
 * Edit layout reads the boxes AGAIN, with `content_digest` (`_box_digest`, over every card,
 * not `layout_token` alone) — a card captured or sold between the draft and Confirm changes
 * no divider, so a token-only check would miss it. Every digest is checked before a single
 * write happens, and a mismatch refuses the WHOLE draft.
 *
 * CARD RANGES ARE BACK IN EDIT MODE (owner's ruling, 2026-09-27): a range drafts exactly like
 * a section, in the same draft, the same Confirm, the same undo. A range can only be picked
 * up from a box the draft has not touched yet (`dirtied`) — its real card list, fetched live,
 * would otherwise disagree with what a queued section move already did to it in this draft. */

type Scope = 'one' | 'after' | 'all' | 'cards'

type Lifted = {
  readonly box: number
  readonly section: number
  readonly scope: Scope
}

type Dest = number | 'new'

/** A gap's id on the page: `s:<n>` in front of a section, `c:<index>` in front of a card,
 *  `e:<n>` at a section's end, `end` at the box's near end. */
type GapId = string

/** One view of Inventory: the walk, the shelf or the sets. The switch lives in the header. */
export type InventoryView = 'walk' | 'shelf' | 'sets'

export function ShelfSwitch({ view, onView }: { readonly view: InventoryView; readonly onView: (next: InventoryView) => void }) {
  return (
    <Segmented
      value={view}
      label="View"
      size="sm"
      options={[
        { value: 'walk', label: 'List' },
        { value: 'shelf', label: 'Map' },
        { value: 'sets', label: 'Sets' },
      ]}
      onChange={onView}
    />
  )
}

function sectionName(detail: SectionDetail): string {
  return detail.name ?? `Section ${detail.section}`
}

function cards(n: number): string {
  return n === 1 ? '1 card' : `${n} cards`
}

function cardName(card: InventoryCard): string {
  return card.name ?? 'An unread card'
}

const onHand = (card: InventoryCard) => card.state !== 'sold' && card.state !== 'retired' && card.state !== 'moved'

/** A box's on-hand cards by section, in the order they stand (the card's order key, D294). */
function bySection(cardsOf: readonly InventoryCard[]): Map<number, InventoryCard[]> {
  const out = new Map<number, InventoryCard[]>()
  const sorted = [...cardsOf].filter(onHand).sort((a, b) => (a.place?.order ?? a.index) - (b.place?.order ?? b.index))
  for (const card of sorted) {
    const section = card.place?.section ?? 1
    const list = out.get(section) ?? []
    list.push(card)
    out.set(section, list)
  }
  return out
}

function boxName(record: WorkingBox): string {
  if (record.name) return record.name
  return record.box < 0 ? 'New box' : UNNAMED_BOX
}

/** The sections a lift takes, first and last ordinal. */
function rangeOf(record: WorkingBox, lifted: Lifted): { first: number; last: number } {
  const count = record.sections_detail.length
  if (lifted.scope === 'all') return { first: 1, last: count }
  if (lifted.scope === 'after') return { first: lifted.section, last: count }
  return { first: lifted.section, last: lifted.section }
}

function movingCount(record: WorkingBox, first: number, last: number): number {
  return record.sections_detail
    .filter((d) => d.section >= first && d.section <= last)
    .reduce((sum, d) => sum + d.count, 0)
}

/** A block's height: its count against the fullest section on the shelf, floored at 44px. */
function blockStyle(count: number, fullest: number): CSSProperties {
  const share = fullest > 0 ? count / fullest : 0
  return { '--shelf-share': share.toFixed(3) } as CSSProperties
}

/** One box's cards, read when a lift or a destination needs them — only ever a box the draft
 *  has not touched yet (`dirtied`), so the live list agrees with what the shelf shows. */
function useBoxCards(box: number | null, reload: number): readonly InventoryCard[] | null {
  const [read, setRead] = useState<{ box: number; cards: InventoryCard[] } | null>(null)
  useEffect(() => {
    if (box === null) return
    let live = true
    getInventoryBox(box)
      .then((inv) => {
        if (live) setRead({ box, cards: Object.values(inv.cards) })
      })
      .catch(() => {
        if (live) setRead({ box, cards: [] })
      })
    return () => {
      live = false
    }
  }, [box, reload])
  return read !== null && read.box === box ? read.cards : null
}

/** A queued range move keeps the section it left and the section it landed in, resolved once
 *  at queue time (the source and destination boxes are both `undirtied`, so their sections
 *  still match the server's own) — client-only render metadata, never sent (`server.ts`
 *  rebuilds the wire body per `kind` from the typed fields alone). */
type QueuedRangeStep = RangeMoveBatchStep & { readonly srcSection: number; readonly dstSection: number }
type QueuedMove = SectionMoveBatchStep | QueuedRangeStep

/** A working box: the shape the shelf renders, real or a not-yet-real split (D264, negative
 *  `box`). Rebuilt from the server's own boxes plus every move the draft has queued so far —
 *  never fetched, never written until Confirm. */
type WorkingBox = {
  readonly box: number
  readonly name: string | null
  readonly sections_detail: SectionDetail[]
  readonly on_hand: number
}

function baseWorking(records: readonly BoxRecord[]): WorkingBox[] {
  return records.map((r) => ({
    box: r.box,
    name: r.name ?? null,
    sections_detail: r.sections_detail.map((d) => ({ section: d.section, start: 0, end: 0, count: d.count, name: d.name })),
    on_hand: r.on_hand ?? 0,
  }))
}

/** How many of a chosen range [first, last] fall before `before` — what the server's own
 *  same-box reorder subtracts, so before-and-after read the same gap (mirrors
 *  `server/capture_server.py:do_move_sections`'s `gap` line). */
function countChosenBefore(first: number, last: number, before: number): number {
  let n = 0
  for (let j = first; j <= last; j += 1) if (j < before) n += 1
  return n
}

function withSections(box: WorkingBox, sections: SectionDetail[]): WorkingBox {
  return { ...box, sections_detail: sections.map((d, i) => ({ ...d, section: i + 1 })), on_hand: sections.reduce((s, d) => s + d.count, 0) }
}

/** The draft, replayed onto the server's own boxes, in the order it was queued — the same
 *  replay `do_move_sections_batch` performs server-side, so what the owner sees while
 *  dragging is what Confirm will produce. A range move never adds or removes a section (no
 *  divider moves, D264's card-range rule) — only the two counts it touches change. */
function applyDraft(base: readonly WorkingBox[], moves: readonly QueuedMove[]): WorkingBox[] {
  let boxes = base.slice()
  let seq = 0
  for (const move of moves) {
    if (move.kind === 'range') {
      const srcIdx = boxes.findIndex((b) => b.box === move.box)
      const dstIdx = boxes.findIndex((b) => b.box === move.toBox)
      if (srcIdx === -1 || dstIdx === -1) continue
      const count = move.indices.length
      boxes = boxes.map((b, i) => {
        if (i === srcIdx && i === dstIdx) {
          const secs = b.sections_detail.map((d, idx) => {
            if (idx === move.srcSection - 1) return { ...d, count: Math.max(0, d.count - count) }
            if (idx === move.dstSection - 1) return { ...d, count: d.count + count }
            return d
          })
          return withSections(b, secs)
        }
        if (i === srcIdx) {
          const secs = b.sections_detail.map((d, idx) => (idx === move.srcSection - 1 ? { ...d, count: Math.max(0, d.count - count) } : d))
          return withSections(b, secs)
        }
        if (i === dstIdx) {
          const secs = b.sections_detail.map((d, idx) => (idx === move.dstSection - 1 ? { ...d, count: d.count + count } : d))
          return withSections(b, secs)
        }
        return b
      })
      continue
    }
    const srcIdx = boxes.findIndex((b) => b.box === move.box)
    if (srcIdx === -1) continue
    const src = boxes[srcIdx] as WorkingBox
    const taken = src.sections_detail.slice(move.first - 1, move.last)
    const rest = [...src.sections_detail.slice(0, move.first - 1), ...src.sections_detail.slice(move.last)]
    boxes = boxes.map((b, i) => (i === srcIdx ? withSections(b, rest) : b))
    if (move.toBox === 'new') {
      seq -= 1
      boxes = [...boxes, withSections({ box: seq, name: null, sections_detail: [], on_hand: 0 }, taken)]
      continue
    }
    const same = move.toBox === move.box
    const dstIdx = boxes.findIndex((b) => b.box === move.toBox)
    if (dstIdx === -1) continue
    const dst = boxes[dstIdx] as WorkingBox
    const adjusted = move.before === null ? null : same ? move.before - countChosenBefore(move.first, move.last, move.before) : move.before
    const at = adjusted === null ? dst.sections_detail.length : adjusted - 1
    const merged = [...dst.sections_detail.slice(0, at), ...taken, ...dst.sections_detail.slice(at)]
    boxes = boxes.map((b, i) => (i === dstIdx ? withSections(b, merged) : b))
  }
  return boxes
}

export function BoxShelf({ onView }: { readonly onView: (next: InventoryView) => void }) {
  const [records, setRecords] = useState<readonly BoxRecord[] | null>(null)
  const [readFailure, setReadFailure] = useState<Failure | null>(null)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [entering, setEntering] = useState(false)
  const [digests, setDigests] = useState<Record<string, string> | null>(null)
  const [moves, setMoves] = useState<readonly QueuedMove[]>([])
  /* BOXES THE DRAFT HAS ALREADY TOUCHED, as a source or a destination: a card range cannot be
     picked up from — or dropped into — one of these, because its real card list (fetched
     live) would disagree with what an earlier queued move in this same draft already did. */
  const [dirtied, setDirtied] = useState<ReadonlySet<number>>(new Set())
  const [lifted, setLifted] = useState<Lifted | null>(null)
  const [picked, setPicked] = useState<{ from: number; to: number } | null>(null)
  const [dest, setDest] = useState<Dest | null>(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  /* Undo's own refusal, shown by the Undo it answers (inside the receipt), not up in the toolbar. */
  const [undoFailure, setUndoFailure] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<SectionMoveBatchResult | null>(null)
  const [undone, setUndone] = useState(false)
  const [over, setOver] = useState<GapId | null>(null)
  const [cardsReload, setCardsReload] = useState(0)

  const load = useCallback(() => {
    getBoxes()
      .then((summary) => {
        setRecords(summary.boxes)
        setReadFailure(null)
      })
      .catch((err: unknown) => setReadFailure(describeFailure(err)))
  }, [])
  useEffect(load, [load])

  const working = useMemo(() => (records === null ? [] : applyDraft(baseWorking(records), moves)), [records, moves])
  const byBox = useMemo(() => new Map(working.map((r) => [r.box, r])), [working])
  const fullest = useMemo(() => Math.max(1, ...working.flatMap((r) => r.sections_detail.map((d) => d.count))), [working])
  const source = lifted === null ? null : (byBox.get(lifted.box) ?? null)
  const range = source !== null && lifted !== null ? rangeOf(source, lifted) : null
  const liftedDetail = source !== null && lifted !== null ? source.sections_detail[lifted.section - 1] : undefined
  const liftedName = liftedDetail === undefined ? '' : sectionName(liftedDetail)
  const cardMode = lifted?.scope === 'cards'

  const sourceCards = useBoxCards(cardMode && lifted !== null ? lifted.box : null, cardsReload)
  const destCards = useBoxCards(cardMode && typeof dest === 'number' ? dest : null, cardsReload)
  const sectionCards = useMemo(
    () => (sourceCards === null || lifted === null ? [] : (bySection(sourceCards).get(lifted.section) ?? [])),
    [sourceCards, lifted],
  )
  const chosen = useMemo(() => {
    if (picked === null) return []
    const lo = Math.min(picked.from, picked.to)
    const hi = Math.max(picked.from, picked.to)
    return sectionCards.slice(lo, hi + 1)
  }, [picked, sectionCards])
  const chosenName =
    chosen.length === 0 ? '' : chosen.length === 1 ? cardName(chosen[0] as InventoryCard) : `${chosen.length} cards`

  const putDown = useCallback(() => {
    setLifted(null)
    setDest(null)
    setOver(null)
    setPicked(null)
  }, [])

  const enterEdit = useCallback(() => {
    setEntering(true)
    setFailure(null)
    getBoxes(undefined, { withDigest: true })
      .then((summary) => {
        setRecords(summary.boxes)
        setDigests(Object.fromEntries(summary.boxes.map((r) => [String(r.box), r.content_digest ?? ''])))
        setMoves([])
        setDirtied(new Set())
        setReceipt(null)
        setUndone(false)
        setCardsReload((n) => n + 1)
        setMode('edit')
      })
      .catch((err: unknown) => setFailure(describeFailure(err)))
      .finally(() => setEntering(false))
  }, [])

  const cancelEdit = useCallback(() => {
    setMode('view')
    setDigests(null)
    setMoves([])
    setDirtied(new Set())
    putDown()
    setFailure(null)
  }, [putDown])

  const queue = useCallback(
    (step: QueuedMove) => {
      setMoves((was) => [...was, step])
      setDirtied((was) => {
        const next = new Set(was)
        next.add(step.box)
        if (step.toBox !== 'new') next.add(step.toBox)
        return next
      })
      setCardsReload((n) => n + 1)
      putDown()
    },
    [putDown],
  )

  const confirm = useCallback(async () => {
    if (busy) return
    if (moves.length === 0 || digests === null) {
      cancelEdit()
      return
    }
    setBusy(true)
    setFailure(null)
    try {
      setReceipt(await moveSectionsBatch({ digests, moves }))
      setUndoFailure(null)
      setUndone(false)
      setMode('view')
      setDigests(null)
      setMoves([])
      setDirtied(new Set())
      putDown()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      load()
    }
  }, [busy, moves, digests, cancelEdit, putDown, load])

  const undo = useCallback(async () => {
    if (receipt === null || undone || busy) return
    setBusy(true)
    setUndoFailure(null)
    try {
      await undoSectionMove(receipt.move)
      setUndone(true)
    } catch (err) {
      setUndoFailure(describeFailure(err))
    } finally {
      setBusy(false)
      load()
    }
  }, [receipt, undone, busy, load])

  /* One drop, whichever input made it. A section lands in front of a section or at the end;
     a card range lands in front of a card of the destination, or at a section's end. */
  const dropAt = useCallback(
    (gap: GapId) => {
      if (source === null || range === null || dest === null) return
      if (cardMode) {
        /* DEFENSE IN DEPTH: the disabled destination buttons are the real gate (the
           re-review's finding); this refuses even a stray call the UI never offered. */
        if (chosen.length === 0 || dest === 'new' || dirtied.has(dest) || dirtied.has(source.box)) return
        const beforeCard = gap.startsWith('c:') ? Number(gap.slice(2)) : null
        const sectionEnd = gap.startsWith('e:') ? Number(gap.slice(2)) : null
        const dstSection = sectionEnd ?? (destCards ?? []).find((c) => c.index === beforeCard)?.place?.section ?? 1
        queue({
          kind: 'range',
          box: source.box,
          indices: chosen.map((c) => c.index),
          toBox: dest,
          beforeCard,
          sectionEnd,
          srcSection: lifted?.section ?? 1,
          dstSection,
        })
        return
      }
      const before = gap === 'end' ? null : Number(gap.slice(2))
      queue({ kind: 'section', box: source.box, first: range.first, last: range.last, toBox: dest, before })
    },
    [source, range, dest, cardMode, chosen, destCards, lifted, dirtied, queue],
  )

  /* Esc puts the section down, and yields to typing. */
  const keys = useRef({ putDown, lifted })
  keys.current = { putDown, lifted }
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || isEditableTarget(event.target)) return
      if (event.key === 'Escape' && keys.current.lifted !== null) {
        event.preventDefault()
        keys.current.putDown()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  /* U undoes the batch the receipt shows, the one `U` primitive (`kit/undo.ts`). */
  useUndoHotkey(() => (receipt === null ? null : () => void undo()))

  /* THE POINTER DRAG. The lifted block follows nothing on screen (D118); the gap under the
     pointer opens instead, and the release drops there. */
  const drag = useRef<{ id: number } | null>(null)
  const gapAt = (x: number, y: number): HTMLElement | null => {
    const hit = document.elementFromPoint(x, y)
    return hit instanceof Element ? (hit.closest('[data-shelf-gap]') as HTMLElement | null) : null
  }
  const dragHandlers = {
    onDragStart: (event: ReactPointerEvent<HTMLElement>) => {
      if (dest === null || busy) return
      drag.current = { id: event.pointerId }
      event.currentTarget.setPointerCapture(event.pointerId)
    },
    onDragMove: (event: ReactPointerEvent<HTMLElement>) => {
      if (drag.current?.id !== event.pointerId) return
      setOver(gapAt(event.clientX, event.clientY)?.dataset.shelfGap ?? null)
    },
    onDragEnd: (event: ReactPointerEvent<HTMLElement>) => {
      if (drag.current?.id !== event.pointerId) return
      drag.current = null
      const gap = gapAt(event.clientX, event.clientY)?.dataset.shelfGap
      setOver(null)
      if (gap) dropAt(gap)
    },
  }

  const moving = cardMode ? chosenName : lifted?.scope === 'all' && source !== null ? boxName(source) : liftedName
  const gaps: Gaps = { over, name: moving, onPut: dropAt, busy }
  const destRecord = dest === null || dest === 'new' ? null : (byBox.get(dest) ?? null)
  const pairReady = dest !== null && source !== null && range !== null && (!cardMode || chosen.length > 0)
  /* A NOT-YET-REAL SPLIT (a negative `box`) IS NOT A DESTINATION FOR ANOTHER MOVE this same
     draft: `new_box` always allocates a fresh box, so a second drop into "the same" pending
     split has nothing real to land in until Confirm. Pick it up again, or Confirm first. */
  const destinations = working.filter((r) => r.box > 0)

  const editing = mode === 'edit'
  const dirty = moves.length > 0

  return (
    <Page
      className="shelf"
      icon="box"
      verdict={
        records === null ? null : editing ? `Editing the layout. ${dirty ? `${moves.length} ${moves.length === 1 ? 'change' : 'changes'} queued.` : 'Drag a section to move it.'}` : null
      }
      /* R2 (kit-adoption): the header's actions slot holds at most one worded press. The
         mode switch (Cancel/Confirm, or Edit layout) is a second row of the page instead,
         never squeezed in beside the h1 (D275, R2). */
      actions={editing ? null : <ShelfSwitch view="shelf" onView={onView} />}
      loading={records === null && readFailure === null}
      empty={readFailure === null ? null : <FailureNotice failure={readFailure} title="The boxes could not be read." onRetry={load} />}
    >
      <div className="shelf-mode-bar">
        {editing ? (
          <>
            <Button variant="quiet" onClick={cancelEdit} disabled={busy}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => void confirm()} disabled={busy || !dirty} busy={busy}>
              Confirm
            </Button>
          </>
        ) : (
          <Button variant="primary" icon="grip" onClick={enterEdit} disabled={records === null || entering} busy={entering}>
            Layout
          </Button>
        )}
        {failure === null ? null : <Answer><FailureNotice failure={failure} title={failureTitle(failure.code)} compact /></Answer>}
      </div>

      {records !== null && working.length > 0 ? (
        <div className="shelf-edges" aria-hidden="true">
          <span>Back</span>
          <span>Front</span>
        </div>
      ) : null}

      {editing && lifted !== null && source !== null && range !== null ? (
        <LiftBar
          name={liftedName}
          source={source}
          lifted={lifted}
          range={range}
          destinations={destinations}
          dest={dest}
          chosenName={cardMode ? chosenName : null}
          canPickCards={!dirtied.has(source.box)}
          dirtied={dirtied}
          onScope={(scope) => {
            setLifted({ ...lifted, scope })
            setPicked(null)
            if (scope === 'cards' && dest === 'new') setDest(null)
          }}
          onDest={setDest}
          onCancel={putDown}
        />
      ) : null}

      {editing && cardMode && dest === null ? (
        <CardPicker
          cards={sectionCards}
          loading={sourceCards === null}
          picked={picked}
          onPick={(at) =>
            setPicked((was) => (was === null || was.from !== was.to ? { from: at, to: at } : { from: was.from, to: at }))
          }
        />
      ) : null}

      {records === null ? null : pairReady && source !== null && range !== null ? (
        <div className="shelf-pair" aria-label="The two boxes, side by side">
          <BoxRow
            record={source}
            fullest={fullest}
            range={range}
            lifted={lifted}
            dragHandlers={dragHandlers}
            busy={busy}
            gaps={dest === source.box ? gaps : undefined}
            reorder={dest === source.box}
            editing={editing}
            cardGaps={dest === source.box && cardMode ? sourceCards : null}
            skip={chosen.map((c) => c.index)}
          />
          {dest === source.box ? null : (
            <BoxRow record={destRecord} fullest={fullest} gaps={gaps} editing={editing} cardGaps={cardMode ? destCards : null} />
          )}
        </div>
      ) : (
        <div className="shelf-boxes">
          {working.map((record) => (
            <BoxRow
              key={record.box}
              record={record}
              fullest={fullest}
              range={lifted !== null && lifted.box === record.box ? range : null}
              lifted={lifted}
              busy={busy}
              editing={editing}
              onLift={
                editing
                  ? (section) => {
                      setPicked(null)
                      setLifted({ box: record.box, section, scope: 'one' })
                      setDest(null)
                    }
                  : undefined
              }
            />
          ))}
        </div>
      )}

      {receipt === null ? null : (
        <MoveReceipt result={receipt} undone={undone} busy={busy} failure={undoFailure} onUndo={() => void undo()} onDone={() => setReceipt(null)} />
      )}
    </Page>
  )
}

/** The one sentence the owner reads when a drop is refused. `draft_stale`: a box the draft
 *  saw changed since Edit layout was pressed (a capture, a sale, an S on the rig, another
 *  device's edit), so nothing in the draft was applied, and the map has read the boxes
 *  again. Every other refusal keeps the plain title, with the server's words behind it. */
function failureTitle(code: string): string {
  return code === 'draft_stale' || code === 'section_gone'
    ? "A box's cards changed since Edit layout was pressed, so nothing in the draft was applied. The map shows it as it is now."
    : 'That layout did not save.'
}

function LiftBar({
  name,
  source,
  lifted,
  range,
  destinations,
  dest,
  chosenName,
  canPickCards,
  dirtied,
  onScope,
  onDest,
  onCancel,
}: {
  readonly name: string
  readonly source: WorkingBox
  readonly lifted: Lifted
  readonly range: { first: number; last: number }
  readonly destinations: readonly WorkingBox[]
  readonly dest: Dest | null
  readonly chosenName: string | null
  readonly canPickCards: boolean
  /** Boxes the draft has already touched (D264, the re-review's finding, 2026-09-28): in
   *  card mode a range cannot aim at one of these either, not only pick up FROM one — its
   *  card list is fetched live, and an earlier queued move already made that live shape
   *  wrong. */
  readonly dirtied: ReadonlySet<number>
  readonly onScope: (scope: Scope) => void
  readonly onDest: (dest: Dest) => void
  readonly onCancel: () => void
}) {
  const total = source.sections_detail.length
  const after = total - lifted.section
  const count = movingCount(source, range.first, range.last)
  const cardMode = lifted.scope === 'cards'
  const scopes: { value: Scope; label: string }[] = [{ value: 'one', label: 'This section' }]
  if (after > 0) scopes.push({ value: 'after', label: after === 1 ? 'This and the next' : `This and the ${after} after it` })
  if (total > 1) scopes.push({ value: 'all', label: 'The whole box' })
  if (canPickCards) scopes.push({ value: 'cards', label: 'Some cards' })
  const others = destinations.filter((r) => r.box !== source.box)
  const what = cardMode ? chosenName || 'No card picked' : lifted.scope === 'all' ? boxName(source) : name
  const sourceChanged = cardMode && dirtied.has(source.box)
  return (
    <section className="shelf-lift" aria-label="Move sections">
      <p className="shelf-lift-line" aria-live="polite">
        {cardMode && !chosenName ? (
          <>
            <strong>{name}</strong>. Pick a card, or a first and a last card.
          </>
        ) : dest === null ? (
          <>
            <strong>{what}</strong>{cardMode ? '' : `, ${cards(count)}`}. Which box does it go to?
          </>
        ) : (
          <>
            <strong>{what}</strong>{cardMode ? '' : `, ${cards(count)}`}. Drag it to a gap, or press a gap.
          </>
        )}
      </p>
      {dest === null ? <Segmented value={lifted.scope} label="What moves" options={scopes} onChange={onScope} /> : null}
      <div className="shelf-dests" role="group" aria-label="Which box">
        {others.map((r) => {
          /* A CARD RANGE CANNOT AIM AT A BOX THIS DRAFT ALREADY CHANGED: its gaps come from
             a live fetch that does not know about an earlier queued move. */
          const changed = cardMode && dirtied.has(r.box)
          return (
            <Button
              key={r.box}
              variant={dest === r.box ? 'primary' : 'default'}
              aria-pressed={dest === r.box}
              disabled={changed || (cardMode && !chosenName)}
              title={changed ? 'Already changed in this draft' : undefined}
              onClick={() => onDest(r.box)}
            >
              {boxName(r)}
              {changed ? ' (already changed)' : ''}
            </Button>
          )
        })}
        {(total > 1 && lifted.scope !== 'all') || cardMode ? (
          <Button
            variant={dest === source.box ? 'primary' : 'default'}
            aria-pressed={dest === source.box}
            disabled={sourceChanged || (cardMode && !chosenName)}
            title={sourceChanged ? 'Already changed in this draft' : undefined}
            onClick={() => onDest(source.box)}
          >
            Another place in {boxName(source)}
            {sourceChanged ? ' (already changed)' : ''}
          </Button>
        ) : null}
        {cardMode ? null : (
          <Button variant={dest === 'new' ? 'primary' : 'default'} aria-pressed={dest === 'new'} icon="plus" onClick={() => onDest('new')}>
            New box
          </Button>
        )}
        <Button variant="quiet" onClick={onCancel} kbd="Esc">
          Cancel
        </Button>
      </div>
    </section>
  )
}

/* THE LIFTED SECTION'S CARDS. One press picks a card; a second press picks the last card of
 * a range; a third starts again. */
function CardPicker({
  cards: list,
  loading,
  picked,
  onPick,
}: {
  readonly cards: readonly InventoryCard[]
  readonly loading: boolean
  readonly picked: { from: number; to: number } | null
  readonly onPick: (at: number) => void
}) {
  const lo = picked === null ? -1 : Math.min(picked.from, picked.to)
  const hi = picked === null ? -1 : Math.max(picked.from, picked.to)
  if (loading) return <p className="shelf-cards-empty">Reading the cards…</p>
  if (list.length === 0) return <p className="shelf-cards-empty">This section holds no cards.</p>
  return (
    <ol className="shelf-cards" aria-label="The cards in this section">
      {list.map((card, at) => (
        <li key={card.index}>
          <Button
            variant={at >= lo && at <= hi ? 'primary' : 'default'}
            aria-pressed={at >= lo && at <= hi}
            className="shelf-card"
            onClick={() => onPick(at)}
          >
            <span className="shelf-card-number">{card.place?.card ?? at + 1}</span>
            <span className="shelf-card-name">{cardName(card)}</span>
          </Button>
        </li>
      ))}
    </ol>
  )
}

type Gaps = {
  readonly over: GapId | null
  readonly name: string
  readonly onPut: (gap: GapId) => void
  readonly busy: boolean
}

function Gap({ gaps, id, where }: { readonly gaps: Gaps; readonly id: GapId; readonly where: string }) {
  return (
    <Button
      variant="ghost"
      className="shelf-gap"
      data-shelf-gap={id}
      data-over={gaps.over === id ? 'true' : undefined}
      disabled={gaps.busy}
      aria-label={`Put ${gaps.name} ${where}`}
      onClick={() => gaps.onPut(id)}
    >
      <Icon name="plus" size={14} />
      <span className="shelf-gap-text">Put here</span>
    </Button>
  )
}

/** One box, drawn horizontally: sections run left (the far back, card 1) to right (the near
 *  end, nearest the owner) (D264, D260). `editing` gates the grip and the gaps: the map is
 *  read-only outside edit mode. `cardGaps`, given, means a card range's own gaps replace the
 *  section blocks: a gap in front of every on-hand card, and one at each section's end. */
function BoxRow({
  record,
  fullest,
  range,
  lifted,
  onLift,
  gaps,
  reorder,
  dragHandlers,
  busy,
  editing,
  cardGaps,
  skip,
}: {
  readonly record: WorkingBox | null
  readonly fullest: number
  readonly range?: { first: number; last: number } | null
  readonly lifted?: Lifted | null
  readonly onLift?: (section: number) => void
  readonly gaps?: Gaps
  readonly reorder?: boolean
  readonly dragHandlers?: {
    onDragStart: (e: ReactPointerEvent<HTMLElement>) => void
    onDragMove: (e: ReactPointerEvent<HTMLElement>) => void
    onDragEnd: (e: ReactPointerEvent<HTMLElement>) => void
  }
  readonly busy?: boolean
  readonly editing: boolean
  /** Card mode: this box's cards, so a gap sits in front of each one. */
  readonly cardGaps?: readonly InventoryCard[] | null
  readonly skip?: readonly number[]
}) {
  if (record === null) {
    return (
      <section className="shelf-box" aria-label="New box">
        <header className="shelf-box-head">
          <h2 className="shelf-box-name">New box</h2>
          <span className="shelf-box-count">Empty</span>
        </header>
        <div className="shelf-box-body">{gaps ? <Gap gaps={gaps} id="end" where="into a new box" /> : null}</div>
      </section>
    )
  }
  const sections = record.sections_detail
  const cardMode = cardGaps !== undefined && cardGaps !== null
  const perSection = cardMode ? bySection(cardGaps) : null
  const inRange = (s: number) => range != null && s >= range.first && s <= range.last && !(cardMode && reorder)
  /* In a section reorder, no gap is offered inside or right after the moved sections: it
     would put them where they already are. */
  const offered = (before: number | null) => {
    if (!reorder || range == null || cardMode) return true
    if (before === null) return range.last < sections.length
    return before < range.first || before > range.last + 1
  }
  const where = (d: SectionDetail) => `just on the far side of ${sectionName(d)}, in ${boxName(record)}`
  const block = (d: SectionDetail) => (
    <div
      className="shelf-block"
      data-lifted={inRange(d.section) ? 'true' : undefined}
      data-empty={d.count === 0 ? 'true' : undefined}
      style={blockStyle(d.count, fullest)}
      onPointerDown={editing && inRange(d.section) && dragHandlers ? dragHandlers.onDragStart : undefined}
      onPointerMove={editing && inRange(d.section) && dragHandlers ? dragHandlers.onDragMove : undefined}
      onPointerUp={editing && inRange(d.section) && dragHandlers ? dragHandlers.onDragEnd : undefined}
      onPointerCancel={editing && inRange(d.section) && dragHandlers ? dragHandlers.onDragEnd : undefined}
    >
      <span className="shelf-block-text">
        <span className="shelf-block-name">{sectionName(d)}</span>
        <span className="shelf-block-count">{cards(d.count)}</span>
      </span>
      {editing && onLift && !gaps && d.count > 0 ? (
        <IconButton
          icon="grip"
          label="Move section"
          name={`Move section ${sectionName(d)} of ${boxName(record)}`}
          pressed={lifted != null && lifted.box === record.box && lifted.section === d.section}
          disabled={busy}
          onClick={() => onLift(d.section)}
        />
      ) : null}
    </div>
  )
  return (
    <section className="shelf-box" aria-label={boxName(record)}>
      <header className="shelf-box-head">
        <h2 className="shelf-box-name">{boxName(record)}</h2>
        <span className="shelf-box-count">{cards(record.on_hand)}</span>
      </header>
      <ol className="shelf-box-body">
        {sections.map((d) => (
          <li key={d.section} className="shelf-slot">
            {gaps && !cardMode && offered(d.section) ? <Gap gaps={gaps} id={`s:${d.section}`} where={where(d)} /> : null}
            {cardMode && gaps ? (
              <div className="shelf-card-gaps" aria-label={sectionName(d)}>
                <span className="shelf-block-name">{sectionName(d)}</span>
                {(perSection?.get(d.section) ?? [])
                  .filter((card) => !(skip ?? []).includes(card.index))
                  .map((card) => (
                    <div key={card.index} className="shelf-card-row">
                      <Gap gaps={gaps} id={`c:${card.index}`} where={`just on the far side of ${cardName(card)}, in ${boxName(record)}`} />
                      <span className="shelf-card-line">{cardName(card)}</span>
                    </div>
                  ))}
                <Gap gaps={gaps} id={`e:${d.section}`} where={`at the end of ${sectionName(d)}, in ${boxName(record)}`} />
              </div>
            ) : (
              block(d)
            )}
          </li>
        ))}
        {gaps && cardMode && sections.length === 0 ? (
          <li className="shelf-slot">
            <Gap gaps={gaps} id="end" where={`into ${boxName(record)}`} />
          </li>
        ) : null}
        {gaps && !cardMode && offered(null) ? (
          <li className="shelf-slot">
            <Gap gaps={gaps} id="end" where={`at the end of ${boxName(record)} nearest you`} />
          </li>
        ) : null}
      </ol>
    </section>
  )
}

/** A REFUSAL ANSWERS THE PRESS WHERE IT WAS MADE, OVER THE PAGE, MOVING NOTHING (D313, D118). It
 *  is positioned against the controls that were pressed, so it never takes a row of its own, and
 *  it scrolls itself into view so it cannot land off screen. */
function Answer({ children, above }: { readonly children: ReactNode; readonly above?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => ref.current?.scrollIntoView({ block: 'nearest' }), [])
  return (
    <div className="shelf-answer" data-above={above ? 'true' : undefined} ref={ref} role="alert">
      {children}
    </div>
  )
}

function MoveReceipt({
  result,
  undone,
  busy,
  failure,
  onUndo,
  onDone,
}: {
  readonly result: SectionMoveBatchResult
  readonly undone: boolean
  readonly busy: boolean
  readonly failure: Failure | null
  readonly onUndo: () => void
  readonly onDone: () => void
}) {
  return (
    <section className="shelf-receipt" aria-label="What to do with your hands">
      <h2 className="shelf-receipt-head">{undone ? 'Put back. Nothing needs to move.' : result.receipt.heading}</h2>
      {undone ? null : (
        <>
          <ol className="shelf-receipt-steps">
            {result.receipt.steps.map((step, i) => (
              <li key={`${i}-${step}`}>{step}</li>
            ))}
          </ol>
          {result.receipt.renumbered.length === 0 ? null : (
            <ul className="shelf-receipt-renumbered">
              {result.receipt.renumbered.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {[result.receipt.owed ?? '', ...result.receipt.next_capture]
            .filter((line) => line !== '')
            .map((line) => (
              <p key={line} className="shelf-receipt-note">
                {line}
              </p>
            ))}
        </>
      )}
      <div className="shelf-receipt-actions">
        {undone ? null : <IconButton icon="undo" label="Undo" name="Undo this layout" kbd="U" busy={busy} disabled={busy} onClick={onUndo} />}
        <Button onClick={onDone}>Done</Button>
        {failure === null ? null : (
          <Answer above>
            <FailureNotice failure={failure} title={failureTitle(failure.code)} compact />
          </Answer>
        )}
      </div>
    </section>
  )
}
