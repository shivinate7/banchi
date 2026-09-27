import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import { Button, FailureNotice, Icon, IconButton, Segmented, useUndoHotkey } from './kit'
import { Page } from './kit/Page'
import { describeFailure, getBoxes, moveSectionsBatch, undoSectionMove } from './server'
import type { Failure } from './server'
import { isEditableTarget } from './keys'
import type { BoxRecord, SectionDetail, SectionMoveBatchResult, SectionMoveBatchStep } from './types'
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
 * SCOPE CUT (deviation, reported): the card-level "Some cards" range move (`docs/specs/
 * box-map.md`'s "next slice", built 2026-09-25) is not carried into edit mode. It wrote through
 * a different route (`POST /boxes/<box>/cards/move`) with its own gap grammar (a card index,
 * not a section ordinal), which the batch/rollback mechanism this lane built does not cover.
 * The owner's ask here is the box LAYOUT — whole sections — and the fence says not to change
 * what a section move means or which cards travel with it; removing a screen that moves
 * individual cards is a capability question for the owner, not a layout question, so it is
 * flagged here rather than silently dropped or silently rebuilt on top of a second batch
 * mechanism this lane had no time to prove. */

type Scope = 'one' | 'after' | 'all'

type Lifted = {
  readonly box: number
  readonly section: number
  readonly scope: Scope
}

type Dest = number | 'new'

/** A gap's id on the page: `s:<n>` in front of a section, `end`. */
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

function boxName(record: WorkingBox): string {
  if (record.name) return record.name
  return record.box < 0 ? 'New box' : 'Unnamed box'
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
 *  dragging is what Confirm will produce. */
function applyDraft(base: readonly WorkingBox[], moves: readonly SectionMoveBatchStep[]): WorkingBox[] {
  let boxes = base.slice()
  let seq = 0
  for (const move of moves) {
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
  const [tokens, setTokens] = useState<Record<string, string> | null>(null)
  const [moves, setMoves] = useState<readonly SectionMoveBatchStep[]>([])
  const [lifted, setLifted] = useState<Lifted | null>(null)
  const [dest, setDest] = useState<Dest | null>(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<SectionMoveBatchResult | null>(null)
  const [undone, setUndone] = useState(false)
  const [over, setOver] = useState<GapId | null>(null)

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

  const putDown = useCallback(() => {
    setLifted(null)
    setDest(null)
    setOver(null)
  }, [])

  const enterEdit = useCallback(() => {
    if (records === null) return
    setTokens(Object.fromEntries(records.map((r) => [String(r.box), r.layout_token ?? ''])))
    setMoves([])
    setReceipt(null)
    setFailure(null)
    setUndone(false)
    setMode('edit')
  }, [records])

  const cancelEdit = useCallback(() => {
    setMode('view')
    setTokens(null)
    setMoves([])
    putDown()
    setFailure(null)
  }, [putDown])

  const queue = useCallback(
    (step: SectionMoveBatchStep) => {
      setMoves((was) => [...was, step])
      putDown()
    },
    [putDown],
  )

  const confirm = useCallback(async () => {
    if (busy) return
    if (moves.length === 0 || tokens === null) {
      cancelEdit()
      return
    }
    setBusy(true)
    setFailure(null)
    try {
      setReceipt(await moveSectionsBatch({ tokens, moves }))
      setUndone(false)
      setMode('view')
      setTokens(null)
      setMoves([])
      putDown()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      load()
    }
  }, [busy, moves, tokens, cancelEdit, putDown, load])

  const undo = useCallback(async () => {
    if (receipt === null || undone || busy) return
    setBusy(true)
    setFailure(null)
    try {
      await undoSectionMove(receipt.move)
      setUndone(true)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
      load()
    }
  }, [receipt, undone, busy, load])

  /* One drop: a section lands in front of a section of the destination, or at its near end. */
  const dropAt = useCallback(
    (gap: GapId) => {
      if (source === null || range === null || dest === null) return
      const before = gap === 'end' ? null : Number(gap.slice(2))
      queue({ box: source.box, first: range.first, last: range.last, toBox: dest, before })
    },
    [source, range, dest, queue],
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

  const moving = lifted?.scope === 'all' && source !== null ? boxName(source) : liftedName
  const gaps: Gaps = { over, name: moving, onPut: dropAt, busy }
  const destRecord = dest === null || dest === 'new' ? null : (byBox.get(dest) ?? null)
  const pairReady = dest !== null && source !== null && range !== null
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
      status={failure === null ? null : <FailureNotice failure={failure} title={failureTitle(failure.code)} />}
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
          <Button variant="primary" icon="grip" onClick={enterEdit} disabled={records === null}>
            Edit layout
          </Button>
        )}
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
          onScope={(scope) => setLifted({ ...lifted, scope })}
          onDest={setDest}
          onCancel={putDown}
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
          />
          {dest === source.box ? null : <BoxRow record={destRecord} fullest={fullest} gaps={gaps} editing={editing} />}
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
        <MoveReceipt result={receipt} undone={undone} busy={busy} onUndo={() => void undo()} onDone={() => setReceipt(null)} />
      )}
    </Page>
  )
}

/** The one sentence the owner reads when a drop is refused. `draft_stale`: a box the draft
 *  saw changed since Edit layout was pressed (an S on the rig, another device's move), so
 *  nothing in the draft was applied, and the map has read the boxes again. Every other
 *  refusal keeps the plain title, with the server's words behind it. */
function failureTitle(code: string): string {
  return code === 'draft_stale' || code === 'section_gone'
    ? 'A box changed since Edit layout was pressed, so nothing in the draft was applied. The map shows it as it is now.'
    : 'That layout did not save.'
}

function LiftBar({
  name,
  source,
  lifted,
  range,
  destinations,
  dest,
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
  readonly onScope: (scope: Scope) => void
  readonly onDest: (dest: Dest) => void
  readonly onCancel: () => void
}) {
  const total = source.sections_detail.length
  const after = total - lifted.section
  const count = movingCount(source, range.first, range.last)
  const scopes: { value: Scope; label: string }[] = [{ value: 'one', label: 'This section' }]
  if (after > 0) scopes.push({ value: 'after', label: after === 1 ? 'This and the next' : `This and the ${after} after it` })
  if (total > 1) scopes.push({ value: 'all', label: 'The whole box' })
  const others = destinations.filter((r) => r.box !== source.box)
  const what = lifted.scope === 'all' ? boxName(source) : name
  return (
    <section className="shelf-lift" aria-label="Move sections">
      <p className="shelf-lift-line" aria-live="polite">
        {dest === null ? (
          <>
            <strong>{what}</strong>, {cards(count)}. Which box does it go to?
          </>
        ) : (
          <>
            <strong>{what}</strong>, {cards(count)}. Drag it to a gap, or press a gap.
          </>
        )}
      </p>
      {dest === null ? <Segmented value={lifted.scope} label="What moves" options={scopes} onChange={onScope} /> : null}
      <div className="shelf-dests" role="group" aria-label="Which box">
        {others.map((r) => (
          <Button
            key={r.box}
            variant={dest === r.box ? 'primary' : 'default'}
            aria-pressed={dest === r.box}
            onClick={() => onDest(r.box)}
          >
            {boxName(r)}
          </Button>
        ))}
        {total > 1 && lifted.scope !== 'all' ? (
          <Button variant={dest === source.box ? 'primary' : 'default'} aria-pressed={dest === source.box} onClick={() => onDest(source.box)}>
            Another place in {boxName(source)}
          </Button>
        ) : null}
        <Button variant={dest === 'new' ? 'primary' : 'default'} aria-pressed={dest === 'new'} icon="plus" onClick={() => onDest('new')}>
          New box
        </Button>
        <Button variant="quiet" onClick={onCancel} kbd="Esc">
          Cancel
        </Button>
      </div>
    </section>
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
 *  read-only outside edit mode. */
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
  const inRange = (s: number) => range != null && s >= range.first && s <= range.last
  /* In a section reorder, no gap is offered inside or right after the moved sections: it
     would put them where they already are. */
  const offered = (before: number | null) => {
    if (!reorder || range == null) return true
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
            {gaps && offered(d.section) ? <Gap gaps={gaps} id={`s:${d.section}`} where={where(d)} /> : null}
            {block(d)}
          </li>
        ))}
        {gaps && offered(null) ? (
          <li className="shelf-slot">
            <Gap gaps={gaps} id="end" where={`at the end of ${boxName(record)} nearest you`} />
          </li>
        ) : null}
      </ol>
    </section>
  )
}

function MoveReceipt({
  result,
  undone,
  busy,
  onUndo,
  onDone,
}: {
  readonly result: SectionMoveBatchResult
  readonly undone: boolean
  readonly busy: boolean
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
        </>
      )}
      <div className="shelf-receipt-actions">
        {undone ? null : <IconButton icon="undo" label="Undo" name="Undo this layout" kbd="U" busy={busy} disabled={busy} onClick={onUndo} />}
        <Button onClick={onDone}>Done</Button>
      </div>
    </section>
  )
}
