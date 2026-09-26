import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import { Button, FailureNotice, Icon, IconButton, Segmented } from './kit'
import { Page } from './kit/Page'
import { describeFailure, getBoxes, getInventoryBox, moveRange, moveSections, undoSectionMove } from './server'
import type { Failure } from './server'
import { isEditableTarget } from './keys'
import type { BoxRecord, InventoryCard, SectionDetail, SectionMoveResult } from './types'
import './BoxShelf.css'

/* THE SHELF: every box drawn from above, and a section moved as one object (D264).
 *
 * The owner's picture: "sections being literally like modular building blocks where if i select
 * move sections, i then select which box i want to move this section into, and after selecting
 * i get a side by side 2d birds view and i literally can drag and drop the section before or
 * after section i want of the other box". So the acts are three: pick up a section, pick the box,
 * then drop it into a gap of that box, drawn beside the box it came from.
 *
 * THE NEXT SLICE (owner, 2026-09-25): a lifted section also shows its cards, and one card or a
 * range moves by itself, to a gap in front of any card or at the end of any section.
 *
 * CARD 1 IS AT THE FAR BACK, AT THE TOP (`docs/specs/box-map.md` section 5.2). A block's height
 * follows its count, with a 44px floor so a small section is still a target. COUNTS ONLY: the
 * owner ruled no money on the map in v1.
 *
 * EVERY INPUT HAS A PATH. A pointer drags the lifted block onto a gap. A thumb taps a gap. The
 * keyboard tabs to a gap and presses Enter. Esc puts the section down. The save is at once; the
 * receipt under the map is the physical instruction, with Undo on `U`. */

type Scope = 'one' | 'after' | 'all' | 'cards'

type Lifted = {
  readonly box: number
  readonly section: number
  readonly scope: Scope
}

type Dest = number | 'new'

/** A gap's id on the page: `s:<n>` in front of a section, `end`, `c:<index>` in front of a
 *  card, `e:<n>` at a section's end. */
type GapId = string

/** One view of Inventory: the walk or the shelf. The switch lives in both headers. */
/** `#/inventory`'s three views, one `view` URL key (D285): the walk, the Shelf (D264) and
 *  the owner's "by set" view (D-set-view). */
export type InventoryView = 'walk' | 'shelf' | 'sets'

export function ShelfSwitch({ view, onView }: { readonly view: InventoryView; readonly onView: (next: InventoryView) => void }) {
  return (
    <Segmented
      value={view}
      label="View"
      size="sm"
      options={[
        { value: 'walk', label: 'Walk' },
        { value: 'shelf', label: 'Shelf' },
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

function boxName(record: BoxRecord): string {
  return record.name ?? 'Unnamed box'
}

function cardName(card: InventoryCard): string {
  return card.name ?? 'An unread card'
}

const onHand = (card: InventoryCard) => card.state !== 'sold' && card.state !== 'retired' && card.state !== 'moved'

/** A box's on-hand cards by section, in the order they stand (the card's order key, D265). */
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

/** The sections a lift takes, first and last ordinal. */
function rangeOf(record: BoxRecord, lifted: Lifted): { first: number; last: number } {
  const count = record.sections_detail.length
  if (lifted.scope === 'all') return { first: 1, last: count }
  if (lifted.scope === 'after') return { first: lifted.section, last: count }
  return { first: lifted.section, last: lifted.section }
}

function movingCount(record: BoxRecord, first: number, last: number): number {
  return record.sections_detail
    .filter((d) => d.section >= first && d.section <= last)
    .reduce((sum, d) => sum + d.count, 0)
}

function aimOf(record: BoxRecord, first: number, last: number) {
  const inRange = record.sections_detail.filter((d) => d.section >= first && d.section <= last && d.count > 0)
  const head = inRange[0]
  const tail = inRange[inRange.length - 1]
  if (head === undefined || tail === undefined) return null
  return {
    count: inRange.reduce((sum, d) => sum + d.count, 0),
    first: head.first_cid ?? null,
    last: tail.last_cid ?? null,
  }
}

/** A block's height: its count against the fullest section on the shelf, floored at 44px. */
function blockStyle(count: number, fullest: number): CSSProperties {
  const share = fullest > 0 ? count / fullest : 0
  return { '--shelf-share': share.toFixed(3) } as CSSProperties
}

/** One box's cards, read when a lift or a destination needs them. */
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

export function BoxShelf({ onView }: { readonly onView: (next: InventoryView) => void }) {
  const [records, setRecords] = useState<readonly BoxRecord[] | null>(null)
  const [readFailure, setReadFailure] = useState<Failure | null>(null)
  const [lifted, setLifted] = useState<Lifted | null>(null)
  const [picked, setPicked] = useState<{ from: number; to: number } | null>(null)
  const [dest, setDest] = useState<Dest | null>(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<SectionMoveResult | null>(null)
  const [undone, setUndone] = useState(false)
  const [over, setOver] = useState<GapId | null>(null)
  const [reads, setReads] = useState(0)

  const load = useCallback(() => {
    setReads((n) => n + 1)
    getBoxes()
      .then((summary) => {
        setRecords(summary.boxes)
        setReadFailure(null)
      })
      .catch((err: unknown) => setReadFailure(describeFailure(err)))
  }, [])
  useEffect(load, [load])

  const byBox = useMemo(() => new Map((records ?? []).map((r) => [r.box, r])), [records])
  const fullest = useMemo(
    () => Math.max(1, ...(records ?? []).flatMap((r) => r.sections_detail.map((d) => d.count))),
    [records],
  )
  const source = lifted === null ? null : (byBox.get(lifted.box) ?? null)
  const range = source !== null && lifted !== null ? rangeOf(source, lifted) : null
  const liftedDetail = source !== null && lifted !== null ? source.sections_detail[lifted.section - 1] : undefined
  const liftedName = liftedDetail === undefined ? '' : sectionName(liftedDetail)
  const cardMode = lifted?.scope === 'cards'

  const sourceCards = useBoxCards(cardMode && lifted !== null ? lifted.box : null, reads)
  const destCards = useBoxCards(cardMode && typeof dest === 'number' ? dest : null, reads)
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

  const run = useCallback(
    async (write: () => Promise<SectionMoveResult>) => {
      if (busy) return
      setBusy(true)
      setFailure(null)
      try {
        setReceipt(await write())
        setUndone(false)
        putDown()
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
        load()
      }
    },
    [busy, putDown, load],
  )

  /* One drop, whichever input made it. A section lands in front of a section or at the end; a
     card or a range lands in front of a card or at a section's end. */
  const dropAt = useCallback(
    (gap: GapId) => {
      if (source === null || range === null || dest === null) return
      if (cardMode) {
        if (chosen.length === 0 || dest === 'new') return
        const beforeCard = gap.startsWith('c:') ? Number(gap.slice(2)) : null
        const sectionEnd = gap.startsWith('e:') ? Number(gap.slice(2)) : null
        const first = chosen[0]
        const last = chosen[chosen.length - 1]
        const aim = { count: chosen.length, first: first?.cid ?? null, last: last?.cid ?? null }
        void run(() => moveRange(source.box, chosen.map((c) => c.index), { toBox: dest, beforeCard, sectionEnd }, aim))
        return
      }
      const before = gap === 'end' ? null : Number(gap.slice(2))
      void run(() => moveSections(source.box, range.first, range.last, { toBox: dest, before }, aimOf(source, range.first, range.last)))
    },
    [source, range, dest, cardMode, chosen, run],
  )

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

  /* Esc puts the section down. U undoes the move the receipt shows. Both yield to typing. */
  const keys = useRef({ putDown, undo, lifted, receipt })
  keys.current = { putDown, undo, lifted, receipt }
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || isEditableTarget(event.target)) return
      if (event.key === 'Escape' && keys.current.lifted !== null) {
        event.preventDefault()
        keys.current.putDown()
      } else if ((event.key === 'u' || event.key === 'U') && keys.current.receipt !== null) {
        event.preventDefault()
        void keys.current.undo()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  /* THE POINTER DRAG. The lifted block follows nothing on screen (a press never moves the rest
     of the page, D118); the gap under the pointer opens instead, and the release drops there. */
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

  const verdict =
    records === null
      ? null
      : `${records.length === 1 ? '1 box' : `${records.length} boxes`}, drawn from above. Card 1 is at the far back, at the top.`

  const moving = cardMode ? chosenName : lifted?.scope === 'all' && source !== null ? boxName(source) : liftedName
  const gaps: Gaps = { over, name: moving, onPut: dropAt, busy }
  const destRecord = dest === null || dest === 'new' ? null : (byBox.get(dest) ?? null)
  const pairReady = dest !== null && source !== null && range !== null && (!cardMode || chosen.length > 0)

  return (
    <Page
      className="shelf"
      icon="box"
      lede="Every box and its sections. Pick up a section to move it to another box or another place."
      verdict={verdict}
      actions={<ShelfSwitch view="shelf" onView={onView} />}
      status={failure === null ? null : <FailureNotice failure={failure} title="That move did not happen." />}
      loading={records === null && readFailure === null}
      empty={readFailure === null ? null : <FailureNotice failure={readFailure} title="The boxes could not be read." onRetry={load} />}
    >
      {records !== null && lifted !== null && source !== null && range !== null ? (
        <LiftBar
          name={liftedName}
          source={source}
          lifted={lifted}
          range={range}
          records={records}
          dest={dest}
          chosenName={cardMode ? chosenName : null}
          onScope={(scope) => {
            setLifted({ ...lifted, scope })
            setPicked(null)
            if (scope === 'cards' && dest === 'new') setDest(null)
          }}
          onDest={setDest}
          onCancel={putDown}
        />
      ) : null}

      {records !== null && cardMode && dest === null ? (
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
          <BoxColumn
            record={source}
            fullest={fullest}
            range={range}
            lifted={lifted}
            dragHandlers={dragHandlers}
            busy={busy}
            gaps={dest === source.box ? gaps : undefined}
            reorder={dest === source.box}
            cardGaps={dest === source.box && cardMode ? sourceCards : null}
            skip={chosen.map((c) => c.index)}
          />
          {dest === source.box ? null : (
            <BoxColumn record={destRecord} fullest={fullest} gaps={gaps} cardGaps={cardMode ? destCards : null} />
          )}
        </div>
      ) : (
        <div className="shelf-boxes">
          {records.map((record) => (
            <BoxColumn
              key={record.box}
              record={record}
              fullest={fullest}
              range={lifted !== null && lifted.box === record.box ? range : null}
              lifted={lifted}
              busy={busy}
              onLift={(section) => {
                setReceipt(null)
                setFailure(null)
                setPicked(null)
                setLifted({ box: record.box, section, scope: 'one' })
                setDest(null)
              }}
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

function LiftBar({
  name,
  source,
  lifted,
  range,
  records,
  dest,
  chosenName,
  onScope,
  onDest,
  onCancel,
}: {
  readonly name: string
  readonly source: BoxRecord
  readonly lifted: Lifted
  readonly range: { first: number; last: number }
  readonly records: readonly BoxRecord[]
  readonly dest: Dest | null
  readonly chosenName: string | null
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
  scopes.push({ value: 'cards', label: 'Some cards' })
  const others = records.filter((r) => r.box !== source.box)
  const cardMode = lifted.scope === 'cards'
  const what = cardMode ? chosenName || 'No card picked' : lifted.scope === 'all' ? boxName(source) : name
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
          return (
            <Button
              key={r.box}
              variant={dest === r.box ? 'primary' : 'default'}
              aria-pressed={dest === r.box}
              disabled={cardMode && !chosenName}
              onClick={() => onDest(r.box)}
            >
              {boxName(r)}
            </Button>
          )
        })}
        {(total > 1 && lifted.scope !== 'all') || cardMode ? (
          <Button
            variant={dest === source.box ? 'primary' : 'default'}
            aria-pressed={dest === source.box}
            disabled={cardMode && !chosenName}
            onClick={() => onDest(source.box)}
          >
            Another place in {boxName(source)}
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

/* THE LIFTED SECTION'S CARDS (the next slice). One press picks a card; a second press picks the
 * last card of a range; a third starts again. */
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

function BoxColumn({
  record,
  fullest,
  range,
  lifted,
  onLift,
  gaps,
  reorder,
  dragHandlers,
  busy,
  cardGaps,
  skip,
}: {
  readonly record: BoxRecord | null
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
  /* In a section reorder, no gap is offered inside or right after the moved sections: it would
     put them where they already are. */
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
      onPointerDown={inRange(d.section) && dragHandlers ? dragHandlers.onDragStart : undefined}
      onPointerMove={inRange(d.section) && dragHandlers ? dragHandlers.onDragMove : undefined}
      onPointerUp={inRange(d.section) && dragHandlers ? dragHandlers.onDragEnd : undefined}
      onPointerCancel={inRange(d.section) && dragHandlers ? dragHandlers.onDragEnd : undefined}
    >
      <span className="shelf-block-text">
        <span className="shelf-block-name">{sectionName(d)}</span>
        <span className="shelf-block-count">{cards(d.count)}</span>
      </span>
      {onLift && !gaps && d.count > 0 ? (
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
        <span className="shelf-box-count">{cards(record.on_hand ?? 0)}</span>
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

function MoveReceipt({
  result,
  undone,
  busy,
  onUndo,
  onDone,
}: {
  readonly result: SectionMoveResult
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
            {result.receipt.steps.map((step) => (
              <li key={step}>{step}</li>
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
        {undone ? null : <IconButton icon="undo" label="Undo" name="Undo this move" kbd="U" busy={busy} disabled={busy} onClick={onUndo} />}
        <Button onClick={onDone}>Done</Button>
      </div>
    </section>
  )
}
