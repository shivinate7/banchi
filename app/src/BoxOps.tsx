import { useCallback, useEffect, useId, useState, type ReactNode } from 'react'

import type {
  BoxClaimResult,
  BoxDeleteResult,
  BoxRecord,
  GameEntry,
  BoxListingPlan,
  BoxListingRow,
  BoxPhotoPlan,
  Listing,
  ListingReleaseResult,
  MoveCardsResult,
  PhotoReclaimResult,
  Place,
  ProductEntry,
  SectionDetail,
} from './types'
import type { Failure } from './server'
import {
  applyBoxClaims,
  deleteBox,
  describeFailure,
  getBoxListings,
  getBoxPhotos,
  getGames,
  moveCards,
  reclaimBoxPhotos,
  releaseBoxListings,
  updateBox,
} from './server'
import { spansOf } from './position'
import { ReadingAge } from './CardLocations'
import { readingAgo } from './cardState'
import { Button, Icon, Notice, Pill, Stat, boxesMostRecentFirst, type IconName } from './kit'
import { UNNAMED_BOX } from './kit/data'
import { toast } from './kit/toast'
import { Overlay } from './InventoryOverlay'
import './BoxOps.css'

/* The box operations — D20's object, made visible and editable.
 *
 * `BoxIdentity` is the reading: number, name, lid, census and the track, drawn at the top of
 * the box's own walk. `BoxOps` is the "Manage box" sheet: rename, dividers, seal, claims over
 * the ticked cards, move, and — last, and red — the three destructive operations. Every write
 * route answers with the box row it wrote and nothing here patches that into anything: it
 * calls `onChanged`, and the owner of the read re-reads the boxes AND the inventory together,
 * because a divider edit relabels every card in the box.
 */

/** The word `state` carries when the lid is on. */
const CLOSED = 'closed'

/** No listing records handed down. Not the same as "this store has listed nothing". */
const NO_LISTINGS: Readonly<Record<string, Listing>> = {}

/* HOW STALE THE STALEST LISTING FIGURE IN THIS STORE IS — the OLDEST `Listing.at` in the map.
 *
 * A box-scoped answer would be better and there is nothing to compute one from until the
 * release plan has been fetched: `BoxRecord` carries `listed` (a count of CARDS held) and no
 * SKUs.
 *
 * IT IS THE OLDEST AND NOT THE NEWEST, WHICH IS THE WHOLE POINT. Read store-wide, the newest
 * stamp claims a freshness this box does not have: measured against the live store the newest
 * was three hours old while box 1's own 56 SKUs ran from seventeen hours to four days, so the
 * cell said `read 3 hours ago` directly above a release plan whose every line said
 * `read 1 day ago`. The oldest is a BOUND rather than a stamp — nothing in the map is older
 * than it — so it can understate freshness and can never overstate it, and it is worded as a
 * bound (`read within 4 days`) so it is not mistaken for a reading taken then. The per-SKU
 * age, which is exact and box-scoped, is on every line of the plan below. */
/** The oldest `live_as_of` in the store — a BOUND on staleness, not any one SKU's age.
 *
 *  `live_as_of` AND NOT `at` SINCE D115, and the switch matters more than it looks. `at` is
 *  stamped by every writer of every field, so before D115 a sale dragged this bound forward
 *  and understated how stale the store's readings were; after D115 a sale writes the counter
 *  and touches `at` while observing nothing at all about `live`, which would make the age look
 *  FRESHER exactly as the figure got STALER. `live_as_of` is the field that means "when this
 *  reading was taken" and it is the only honest source for a reading age. */
function oldestReading(listings: Readonly<Record<string, Listing>>): string | null {
  let oldest: string | null = null
  let when = Number.POSITIVE_INFINITY
  for (const entry of Object.values(listings)) {
    const at = entry?.live_as_of
    if (typeof at !== 'string') continue
    const parsed = Date.parse(at)
    if (Number.isNaN(parsed) || parsed >= when) continue
    when = parsed
    oldest = at
  }
  return oldest
}

/** `read within 4 days` — the bound above, said as a bound. Null when nothing has been read. */
function readingBound(at: string | null): string | null {
  const ago = readingAgo(at)
  if (ago === null) return null
  if (ago === 'just now') return 'read just now'
  return `read within ${ago.replace(/ ago$/, '')}`
}

/** One write at a time: `Store.write()` takes the file lock per call. */
type Busy = boolean

/** Every write in this file, with its lock discipline, its refusal handling and its re-read in
 *  one place. `write` returns the answer, or null for a refusal, so a caller can close its own
 *  editor on success and leave it open on a refusal. */
function useBoxWrite(onChanged: () => void): {
  busy: Busy
  trouble: Failure | null
  write: <T>(run: () => Promise<T>) => Promise<T | null>
} {
  const [busy, setBusy] = useState<Busy>(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)

  const write = useCallback(
    async <T,>(run: () => Promise<T>): Promise<T | null> => {
      if (busy) return null
      setBusy(true)
      setTrouble(null)
      try {
        const answer = await run()
        onChanged()
        return answer
      } catch (err) {
        setTrouble(describeFailure(err))
        return null
      } finally {
        setBusy(false)
      }
    },
    [busy, onChanged],
  )

  return { busy, trouble, write }
}

/** The refusal panel: the server's sentence, then the greppable code beneath it. */
function Trouble({ failure }: { failure: Failure | null }) {
  if (failure === null) return null
  return <Notice tone="danger" title={failure.message} code={failure.code} />
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/**
 * One box operation, drawn as a row in the sheet: an icon, what the press does, the value or
 * quantity it is about, and a chevron. The detail is inside the button so it is part of the
 * accessible name ("Seal box, freezes at 543"); the explicit `aria-label` supplies the comma.
 */
function Op({
  icon,
  label,
  detail,
  said,
  busy,
  danger = false,
  expanded,
  running,
  disabled = false,
  onClick,
}: {
  icon: IconName
  label: string
  detail?: string
  /** This row has nothing to do yet — the detail says why — and is not pressable. */
  disabled?: boolean
  /** The accessible name in full, where the drawn label is shorter than the sentence. */
  said?: string
  busy: boolean
  /** THIS row is the one whose write is in flight. `busy` alone only greys every row out,
   *  which is a control saying nothing while it works; this puts the ring on the one that
   *  was pressed and swaps its detail for a word. */
  running?: boolean
  danger?: boolean
  expanded?: boolean
  onClick: () => void
}) {
  return (
    <button
      className={danger ? 'boxops-op boxops-op-danger' : 'boxops-op'}
      type="button"
      aria-label={said ?? (detail === undefined ? label : `${label}, ${detail}`)}
      aria-expanded={expanded}
      aria-busy={running ? true : undefined}
      data-running={running ? 'true' : undefined}
      disabled={busy || disabled}
      onClick={onClick}
    >
      <span className="boxops-op-icon">
        {running ? <span className="boxops-op-spin" aria-hidden="true" /> : <Icon name={icon} size={16} />}
      </span>
      <span className="boxops-op-label">{label}</span>
      {running ? (
        <span className="boxops-op-detail">writing…</span>
      ) : detail === undefined ? null : (
        <span className="boxops-op-detail">{detail}</span>
      )}
      <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={14} className="boxops-op-chev" />
    </button>
  )
}

/** A number off the wire, or null for anything that is not one. Null is not zero. */
function known(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** The dividers the box is actually rendered with, read off the server's own spans. */
function rendered(record: BoxRecord): number[] {
  return record.sections_detail
    .map((detail) => detail.start)
    .filter((start): start is number => typeof start === 'number' && Number.isFinite(start))
}

/**
 * The indices in a divider field, or null when the text is not a list of numbers. The layout
 * rule itself lives in `store/master.py:check_sections`, which refuses rather than repairing.
 * An empty field is `[]`, a real request meaning undeclared.
 */
function readIndices(text: string): number[] | null {
  const tokens = text.match(/[^\s,]+/g) ?? []
  const out: number[] = []
  for (const token of tokens) {
    if (!/^\d+$/.test(token)) return null
    out.push(Number(token))
  }
  return out
}

/** The declared layout as a field's worth of text, in the card-number space every other
 *  number on this screen is in (D58). */
function writeIndices(record: BoxRecord): string {
  if (record.sections.length > 0 && record.sections_detail.length === 0) {
    return record.sections.join(', ')
  }
  return record.sections_detail.map((detail) => detail.start).join(', ')
}

/** A `Place` carrying this box's own numbers into `spansOf`, and nothing else. `slot` is 0:
 *  outside every span, so nothing comes back `current`. */
function trackPlace(record: BoxRecord, total: number): Place {
  return {
    label: '',
    box: record.box,
    index: 0,
    slot: 0,
    section: 0,
    card: 0,
    box_name: record.name,
    section_start: 1,
    section_end: null,
    box_total: total,
    box_closed: record.state === CLOSED,
    fraction: null,
  }
}

/** The denominator this box is drawn against: the cards it holds (D58). */
function denominator(record: BoxRecord): number {
  return known(record.on_hand) ?? 0
}

/** The first index at which two layouts start disagreeing, or null when they agree. */
function firstChange(before: readonly number[], after: readonly number[]): number | null {
  const reach = Math.max(before.length, after.length)
  for (let at = 0; at < reach; at += 1) {
    const was = before[at]
    const now = after[at]
    if (was === undefined) return now ?? null
    if (now === undefined) return was
    if (was !== now) return Math.min(was, now)
  }
  return null
}

/** Which sections a relabel reaches, and how many cards are in them. */
function reached(record: BoxRecord, from: number): { sections: number[]; cards: number } {
  const hit = record.sections_detail.filter((detail: SectionDetail) => {
    const end = known(detail.end)
    return end === null || end >= from
  })
  return {
    sections: hit.map((detail) => detail.section),
    cards: hit.reduce((total, detail) => total + (known(detail.count) ?? 0), 0),
  }
}

/* ---------------------------------------------------------------------- the reading ---- */

/** What this box is, drawn at the top of the walk: number, name, lid, census, and the track
 *  with the selected card's marker on it. `actions` is the slot beside the name — the gear
 *  that opens the sheet. */
export function BoxIdentity({
  record,
  at = null,
  actions,
}: {
  record: BoxRecord
  /** Where the selected card sits in this box, 0..1 — the server's own `fraction`. */
  at?: number | null
  actions?: ReactNode
}) {
  const sealed = record.state === CLOSED
  const holds = known(record.on_hand)
  const total = denominator(record)
  const spans = spansOf(trackPlace(record, total), record.sections_detail)

  /* The copies are on hand and the BOX is sealed: `sealed at 543` closes the line and the pill
     beside it carries the state, so no count is ever called sealed. The captured figure is
     dropped only where it would repeat the seal. */
  const sealedAt = sealed && record.capacity !== null ? record.capacity : null

  /* THE CENSUS TRIAD (D41), BROUGHT TO THIS PANEL. `CardLocations`' own three figures — copies,
     in the boxes, live on TCGplayer — are `bn-stat` tiles: a big tabular-nums value over a
     muted label, no separators. This panel's facts are the same shape now, one `bn-stat` per
     field. `fill unread` and `sealed at N` are not counts of what is in the box — the first is
     an unread state, the second is D20's frozen capacity, a denominator rather than a fourth
     thing IN the box — so both stay plain text, after the figures. */
  const censusStats: { key: string; value: number; label: string }[] = []
  const censusNotes: string[] = []
  if (holds === null) censusNotes.push('fill unread')
  else censusStats.push({ key: 'on-hand', value: holds, label: 'on hand' })
  if (record.sold > 0) censusStats.push({ key: 'sold', value: record.sold, label: 'sold' })
  if (record.retired > 0) censusStats.push({ key: 'retired', value: record.retired, label: 'retired' })
  if (record.moved > 0) censusStats.push({ key: 'moved', value: record.moved, label: 'moved' })
  if (sealedAt !== record.cards) censusStats.push({ key: 'captured', value: record.cards, label: 'captured' })
  if (sealedAt !== null) censusNotes.push(`sealed at ${sealedAt}`)

  return (
    <div className="boxops-identity">
      <div className="boxops-identity-top">
        {/* THE NAME ALONE (D-a-box-is-shown-by-its-name): the number is the store's key, never
            drawn. An unnamed box has a stored default name since the locating lane. THE STATE
            PILL ONLY FOR THE EXCEPTION, ON THE NAME'S LINE (UX-269, UX-221's rule): on the
            figures' line an "open" pill sat inline for one box and wrapped alone for another,
            and nearly every box is open, so the word told the hand nothing. Sealed is drawn. */}
        <div className="boxops-identity-text">
          <h2 className="boxops-identity-name">{record.name ?? UNNAMED_BOX}</h2>
        </div>
        {sealed ? (
          <Pill tone="default" icon="lock" className="boxops-state boxops-state-sealed">
            sealed
          </Pill>
        ) : null}
        {actions}
      </div>

      <div className="boxops-identity-line">
        {censusStats.length === 0 ? null : (
          <div className="boxops-stats bn-stat-row">
            {censusStats.map((stat) => (
              <Stat key={stat.key} value={stat.value} label={stat.label} className="boxops-stat" />
            ))}
          </div>
        )}
        {censusNotes.map((note) => (
          <span key={note} className="boxops-identity-note">
            {note}
          </span>
        ))}
      </div>

      {/* The track is the box: one segment per section, as wide as the cards it holds, with the
          selected card's marker from the server's own `fraction`. */}
      {spans.length === 0 ? null : (
        <div
          className="boxops-track"
          role="img"
          aria-label={`${record.name ?? UNNAMED_BOX}, ${spans.length} ${spans.length === 1 ? 'section' : 'sections'}`}
        >
          {spans.map((span, i) => (
            <span
              className="boxops-span"
              key={`${span.start}-${span.end}`}
              style={{ flexGrow: span.end - span.start + 1 }}
              title={`Section ${i + 1}${record.sections_detail[i]?.name ? `: ${record.sections_detail[i]?.name}` : ''}, cards #${span.start}–#${span.end}`}
            />
          ))}
          {at === null ? null : (
            <span
              className="boxops-mark"
              style={{ left: `${Math.min(100, Math.max(0, at * 100))}%` }}
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------------ the sheet ---- */

type Editing = 'name' | 'sections' | 'section-names' | 'claims' | 'move' | null

export function BoxOps({
  record,
  onChanged,
  selection = [],
  boxes = [],
  listings = NO_LISTINGS,
  open,
  onClose,
}: {
  record: BoxRecord
  onChanged: () => void
  /** The indices the walk currently has ticked, in this box. Empty means the whole box — the
   *  widening happens here, where the scope sentence on the control says so. */
  selection?: readonly number[]
  /** The registry, for the move's destination picker. */
  boxes?: readonly BoxRecord[]
  /** Every SKU's listing record, off `GET /inventory`. Read for the reading age beside this
   *  box's listing figures, and never for a second copy of the counts. */
  listings?: Readonly<Record<string, Listing>>
  open: boolean
  onClose: () => void
}) {
  const { busy, trouble, write } = useBoxWrite(onChanged)
  const onWrite = (patch: {
    name?: string
    sections?: number[]
    state?: 'open' | 'closed'
    section_names?: Record<number, string>
  }) => write(() => updateBox(record.box, patch))
  /* D132 — one draft per section, keyed by ordinal, seeded from what the wire says now. */
  const [sectionNames, setSectionNames] = useState<Record<number, string>>({})
  const [editing, setEditing] = useState<Editing>(null)
  const [draft, setDraft] = useState('')
  const [refused, setRefused] = useState<string | null>(null)
  const [claimed, setClaimed] = useState<BoxClaimResult | null>(null)
  const [moveTo, setMoveTo] = useState('')
  const [moved, setMoved] = useState<MoveCardsResult | null>(null)
  const [proposed, setProposed] = useState<number[] | null>(null)
  /* Which direct-write op was pressed, so the row that fired says so rather than the whole
     list going quietly grey. */
  const [firing, setFiring] = useState<'lid' | null>(null)
  const moveId = useId()
  const readAt = oldestReading(listings)
  /* Said in full once, so the note and its hover cannot drift apart. */
  const boundHelp =
    readAt === null
      ? ''
      : `Believed live at TCGplayer, store-wide. None older than ${readingAgo(readAt)}; exact age is on the release plan below.`

  const scope =
    selection.length > 0
      ? `the ${count(selection.length, 'selected card', 'selected cards')}`
      : `all ${count(record.cards, 'card', 'cards')} in ${record.name ?? UNNAMED_BOX}`

  const applyClaims = async (patch: ClaimPatch) => {
    const result = await write(() =>
      applyBoxClaims(record.box, patch, selection.length > 0 ? [...selection] : undefined),
    )
    if (result !== null) {
      setClaimed(result)
      setEditing(null)
    }
  }

  /* D83. `indices: null` moves every on-hand card. The server's own refusals are the ones
     with something true to say about a destination this component cannot check. */
  const doMove = async () => {
    const toBox = Number.parseInt(moveTo.trim(), 10)
    if (!Number.isInteger(toBox) || toBox < 1) {
      setRefused('Choose a destination box.')
      return
    }
    const result = await write(() =>
      moveCards(record.box, selection.length > 0 ? [...selection] : null, toBox),
    )
    if (result !== null) {
      setMoved(result)
      setEditing(null)
    }
  }

  const sealed = record.state === CLOSED
  const fill = known(record.fill)

  const startEdit = (which: Exclude<Editing, null>) => {
    setRefused(null)
    setProposed(null)
    setClaimed(null)
    setMoved(null)
    setMoveTo('')
    setEditing(which)
    setDraft(which === 'name' ? (record.name ?? '') : writeIndices(record))
    setSectionNames(
      Object.fromEntries(record.sections_detail.map((detail) => [detail.section, detail.name ?? ''])),
    )
  }

  /* Every section's name goes in one PUT, blanks included — a blank CLEARS, which is how a
     name is taken off again, and the server refuses nothing for a section left unnamed. */
  const saveSectionNames = async () => {
    if (await onWrite({ section_names: sectionNames })) closeEdit()
  }

  const closeEdit = () => {
    setEditing(null)
    setProposed(null)
    setRefused(null)
  }

  const saveName = async () => {
    if (await onWrite({ name: draft.trim() })) closeEdit()
  }

  const proposeSections = () => {
    const indices = readIndices(draft)
    if (indices === null) {
      setRefused(
        'A section starts at a card number, counting the cards in the box — like 1, 31, 56.',
      )
      return
    }
    setRefused(null)
    setProposed(indices)
  }

  const saveSections = async () => {
    if (proposed === null) return
    if (await onWrite({ sections: proposed })) closeEdit()
  }

  if (!open) return null

  /* S4: MOST RECENT FIRST — the same rule `Inventory.tsx:MovePanel` and the rail sort by.
     `boxes` arrives in the server's own order (box number), which said nothing about which
     box the hand was likeliest to reach for. */
  const others = boxesMostRecentFirst(boxes.filter((candidate) => candidate.box !== record.box))

  return (
    <Overlay kind="sheet" label={`Manage ${record.name ?? UNNAMED_BOX}`} onClose={onClose} className="boxops-sheet">
      <header className="inv-sheet-head">
        <div className="inv-sheet-head-text">
          <span className="bn-eyebrow">{sealed ? 'Sealed box' : 'Open box'}</span>
          <h2 className="inv-sheet-title">{record.name ?? UNNAMED_BOX}</h2>
        </div>
        <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
          Close
        </Button>
      </header>

      <div className="inv-sheet-body boxops-body">
        {editing === null ? (
          <>
            <section className="boxops-group">
              <h3 className="bn-label">About this box</h3>
              <dl className="boxops-census">
                <Census label="Captured" value={record.cards} />
                <Census label="On hand" value={known(record.on_hand)} />
                <Census label="Sold" value={record.sold} />
                <Census label="Retired" value={record.retired} />
                <Census label="Moved" value={record.moved} />
                {/* A LIVE FIGURE NEVER STANDS WITHOUT ITS AGE — and this age is a BOUND, not
                    a stamp, because it is store-wide: a box record carries a count of held
                    cards and no SKUs. The oldest reading can only understate freshness, and
                    the wording says `within` so it is not read as a moment. The exact,
                    box-scoped age is on every line of the release plan below. */}
                <Census
                  label="Listing-held"
                  value={record.listed}
                  note={
                    record.listed === 0 || readAt === null ? undefined : (
                      <span className="inv-readage boxops-readbound" title={boundHelp}>
                        {readingBound(readAt)}
                      </span>
                    )
                  }
                  help={
                    readAt === null
                      ? 'Cards believed live at TCGplayer. No listing figure written yet.'
                      : boundHelp
                  }
                />
                {/* THE TWO FIGURES KEEP NO NOTE (UX-259, cut list #17), and the second is named
                    for what it is to the owner, never the store's "index" (D196). */}
                <Census label="Fill" value={known(record.fill)} help="The highest card position ever captured in this box." />
                <Census label="Next capture" value={known(record.next_index)} help="Where the next card captured into this box lands." />
                {sealed ? <Census label="Sealed at" value={known(record.capacity)} /> : null}
              </dl>
            </section>

            {record.sections.length > 0 && record.sections_detail.length === 0 ? (
              <Notice tone="warn" title="This box has a declared layout that will not validate">
                Its sections could not be drawn. The raw list is in the sections editor; save a
                corrected one.
              </Notice>
            ) : null}

            <section className="boxops-group">
              <h3 className="bn-label">Box</h3>
              <div className="boxops-ops">
                <Op icon="tag" label="Rename" detail={record.name ?? 'unnamed'} busy={busy} onClick={() => startEdit('name')} />
                <Op
                  icon="divider"
                  label="Edit sections"
                  detail={
                    record.sections.length === 0
                      ? 'not declared'
                      : count(record.sections_detail.length, 'section', 'sections')
                  }
                  busy={busy}
                  onClick={() => startEdit('sections')}
                />
                <Op
                  icon="tag"
                  label="Name sections"
                  detail={
                    record.sections_detail.length === 0
                      ? 'declare sections first'
                      : (() => {
                          const named = record.sections_detail.filter((detail) => detail.name).length
                          return named === 0 ? 'none named' : `${named} of ${record.sections_detail.length} named`
                        })()
                  }
                  busy={busy}
                  disabled={record.sections_detail.length === 0}
                  onClick={() => startEdit('section-names')}
                />
                {sealed ? (
                  <Op
                    icon="unlock"
                    label="Re-open box"
                    detail="capacity clears"
                    busy={busy}
                    running={firing === 'lid'}
                    onClick={() => {
                      setFiring('lid')
                      void onWrite({ state: 'open' }).finally(() => setFiring(null))
                    }}
                  />
                ) : (
                  /* The number is on the control: sealing freezes capacity at the fill and every
                     fraction in the product then divides by it. */
                  <Op
                    icon="lock"
                    label="Seal box"
                    detail={fill === null ? 'fill unreadable' : `freezes at ${fill}`}
                    busy={busy || fill === null}
                    running={firing === 'lid'}
                    onClick={() => {
                      setFiring('lid')
                      void onWrite({ state: 'closed' }).finally(() => setFiring(null))
                    }}
                  />
                )}
              </div>
            </section>

            {selection.length > 0 || record.cards > 0 || (record.on_hand ?? 0) > 0 ? (
              <section className="boxops-group">
                <h3 className="bn-label">
                  Cards
                  {selection.length > 0 ? (
                    <Pill tone="accent">{selection.length} ticked</Pill>
                  ) : (
                    <span className="boxops-group-note">whole box</span>
                  )}
                </h3>
                <div className="boxops-ops">
                  {selection.length > 0 || record.cards > 0 ? (
                    <Op
                      icon="wand"
                      label="Set claims"
                      detail={
                        selection.length > 0
                          ? `${selection.length} ticked`
                          : count(record.cards, 'card', 'cards')
                      }
                      busy={busy}
                      onClick={() => startEdit('claims')}
                    />
                  ) : null}
                  {selection.length > 0 || (record.on_hand ?? 0) > 0 ? (
                    <Op
                      icon="package"
                      label="Move to box"
                      detail={
                        selection.length > 0
                          ? `${selection.length} ticked`
                          : count(record.on_hand ?? 0, 'card', 'cards')
                      }
                      busy={busy}
                      onClick={() => startEdit('move')}
                    />
                  ) : null}
                </div>
              </section>
            ) : null}

            {claimed === null ? null : <ClaimReceipt result={claimed} boxLabel={record.name ?? UNNAMED_BOX} />}

            {moved === null ? null : (
              <Notice
                tone="ok"
                title={`Moved ${count(moved.moved, 'card', 'cards')} from ${record.name ?? UNNAMED_BOX} to ${boxName(boxes, moved.to_box)}.`}
              >
                The {count(moved.moved, 'position', 'positions')} left behind
                {moved.moved === 1 ? ' stays' : ' stay'} permanently empty — the same gap a sale
                or a retirement leaves.
              </Notice>
            )}

            <Trouble failure={trouble} />

            <section className="boxops-group boxops-group-danger">
              <h3 className="bn-label">Danger</h3>
              <div className="boxops-ops">
                <ReleaseListings record={record} boxes={boxes} listings={listings} onChanged={onChanged} />
                <ReclaimPhotos record={record} onChanged={onChanged} />
                <DeleteBox record={record} onChanged={onChanged} onDeleted={onClose} />
              </div>
            </section>
          </>
        ) : editing === 'claims' ? (
          <EditorFrame title="Set claims" onBack={closeEdit}>
            <ClaimEditor
              scope={scope}
              game={null}
              busy={busy}
              onApply={(patch) => void applyClaims(patch)}
              onCancel={closeEdit}
            />
            <Trouble failure={trouble} />
          </EditorFrame>
        ) : editing === 'name' ? (
          <EditorFrame title="Rename" onBack={closeEdit}>
            <Field
              label="Name"
              value={draft}
              onChange={setDraft}
              placeholder="SV commons"
              autoFocus
              hint="Each box has its own name. Leave it empty for a default name."
            />
            <Trouble failure={trouble} />
            <div className="boxops-actions">
              <Button variant="ghost" onClick={closeEdit}>
                Cancel
              </Button>
              <Button variant="primary" busy={busy} onClick={() => void saveName()}>
                Save name
              </Button>
            </div>
          </EditorFrame>
        ) : editing === 'move' ? (
          <EditorFrame title="Move to box" onBack={closeEdit}>
            <div className="bn-field">
              <label className="bn-field-label" htmlFor={moveId}>
                Destination box
              </label>
              {others.length > 0 ? (
                <select
                  id={moveId}
                  className="bn-select"
                  value={moveTo}
                  data-autofocus=""
                  onChange={(event) => setMoveTo(event.target.value)}
                >
                  <option value="">Choose a box…</option>
                  {others.map((candidate) => {
                    // `<option>` renders plain text only, so the name and the sealed state
                    // fold into one parenthetical rather than a typed separator (D218).
                    return (
                      <option key={candidate.box} value={String(candidate.box)}>
                        {candidate.name ?? UNNAMED_BOX}
                        {candidate.state === CLOSED ? ' (sealed)' : ''}
                      </option>
                    )
                  })}
                </select>
              ) : (
                <input
                  id={moveId}
                  className="bn-input bn-input-mono"
                  type="text"
                  inputMode="numeric"
                  placeholder="e.g. 7"
                  autoComplete="off"
                  value={moveTo}
                  onChange={(event) => setMoveTo(event.target.value)}
                />
              )}
              <p className="bn-field-hint">
                {selection.length > 0
                  ? `Moves the ${count(selection.length, 'selected card', 'selected cards')}. The positions here stay permanently empty.`
                  : `Moves all ${count(record.on_hand ?? 0, 'card', 'cards')} on hand in ${record.name ?? UNNAMED_BOX} — the same operation a merge is, from this side.`}
              </p>
            </div>
            {refused === null ? null : <Notice tone="warn">{refused}</Notice>}
            <Trouble failure={trouble} />
            <div className="boxops-actions">
              <Button variant="ghost" onClick={closeEdit}>
                Cancel
              </Button>
              <Button variant="primary" busy={busy} onClick={() => void doMove()}>
                Move
              </Button>
            </div>
          </EditorFrame>
        ) : editing === 'section-names' ? (
          <EditorFrame title="Name sections" onBack={closeEdit}>
            <p className="boxops-editor-lead">
              A word for each section, drawn beside its number on every label — <b className="bn-facts"><span>Section 2</span> <span>Rares</span></b>.
              Leave one blank to clear it. The name follows its divider if the layout is edited later.
            </p>
            <div className="boxops-section-names">
              {record.sections_detail.map((detail) => (
                <Field
                  key={detail.section}
                  label={
                    <span className="bn-facts">
                      <span>Section {detail.section}</span>{' '}
                      <span>#{detail.start}{detail.end === null ? ' onward' : `–#${detail.end}`}</span>
                    </span>
                  }
                  value={sectionNames[detail.section] ?? ''}
                  onChange={(next) => setSectionNames((held) => ({ ...held, [detail.section]: next }))}
                  placeholder="unnamed"
                  autoFocus={detail.section === 1}
                />
              ))}
            </div>
            <Trouble failure={trouble} />
            <div className="boxops-actions">
              <Button variant="ghost" onClick={closeEdit}>
                Cancel
              </Button>
              <Button variant="primary" busy={busy} onClick={() => void saveSectionNames()}>
                Save names
              </Button>
            </div>
          </EditorFrame>
        ) : (
          <EditorFrame title="Edit sections" onBack={closeEdit}>
            <Field
              label="Section starts"
              value={draft}
              onChange={setDraft}
              placeholder="1, 31, 56"
              mono
              autoFocus
              hint="Where each section's numbering starts."
            />
            {refused === null ? null : <Notice tone="warn">{refused}</Notice>}
            <Trouble failure={trouble} />

            {proposed === null ? (
              <div className="boxops-actions">
                <Button variant="ghost" onClick={closeEdit}>
                  Cancel
                </Button>
                <Button variant="primary" busy={busy} onClick={proposeSections}>
                  Check this layout
                </Button>
              </div>
            ) : (
              <Relabel
                record={record}
                proposed={proposed}
                busy={busy}
                onSave={() => void saveSections()}
                onCancel={() => setProposed(null)}
              />
            )}
          </EditorFrame>
        )}
      </div>
    </Overlay>
  )
}

function Census({
  label,
  value,
  help,
  note,
}: {
  label: string
  value: number | null
  help?: string
  /** A quieter line under the figure — how old the reading behind it is, and nothing else. */
  note?: ReactNode
}) {
  return (
    <div className="boxops-census-cell" title={help}>
      <dt>{label}</dt>
      <dd>
        {value === null ? '—' : value.toLocaleString()}
        {note === undefined ? null : <span className="boxops-census-note">{note}</span>}
      </dd>
    </div>
  )
}

function EditorFrame({
  title,
  onBack,
  children,
}: {
  title: string
  onBack: () => void
  children: ReactNode
}) {
  return (
    <div className="boxops-editor">
      <button type="button" className="boxops-back" onClick={onBack}>
        <Icon name="chevronLeft" size={14} /> All settings
      </button>
      <h3 className="boxops-editor-title">{title}</h3>
      {children}
    </div>
  )
}

/** What editing the dividers will do, said before it is done. A relabel, not a renumber. */
function Relabel({
  record,
  proposed,
  busy,
  onSave,
  onCancel,
}: {
  record: BoxRecord
  proposed: readonly number[]
  busy: Busy
  onSave: () => void
  onCancel: () => void
}) {
  const from = firstChange(rendered(record), proposed)
  const hit = from === null ? null : reached(record, from)

  return (
    <div className="boxops-relabel">
      <p className="boxops-relabel-head">
        {proposed.length === 0 ? (
          'One undivided section'
        ) : (
          <>
            New sections start at{' '}
            <span className="boxops-relabel-list">{proposed.join(', ')}</span>
          </>
        )}
      </p>

      {from === null ? (
        <Notice tone="info">Already the box's layout — nothing changes.</Notice>
      ) : (
        <Notice tone="warn" title="A relabel, not a renumber.">
          No card moves. Cards from #{from} on get a new section only.{' '}
          {hit === null || hit.sections.length === 0
            ? 'How many cards that reaches could not be read from this box.'
            : `That reaches ${hit.sections.length === 1 ? 'section' : 'sections'} ${hit.sections.join(', ')} — ${count(hit.cards, 'card', 'cards')}, counted by whole section.`}
        </Notice>
      )}

      <div className="boxops-actions">
        <Button variant="ghost" onClick={onCancel}>
          Back
        </Button>
        <Button variant="primary" busy={busy} onClick={onSave}>
          Save sections
        </Button>
      </div>
    </div>
  )
}

/** One labelled text field. */
function Field({
  label,
  value,
  onChange,
  placeholder,
  hint,
  mono = false,
  autoFocus = false,
}: {
  label: ReactNode
  value: string
  onChange: (next: string) => void
  placeholder?: string
  hint?: string
  mono?: boolean
  autoFocus?: boolean
}) {
  const id = useId()
  return (
    <div className="bn-field">
      <label className="bn-field-label" htmlFor={id}>
        {label}
      </label>
      <input
        className={mono ? 'bn-input bn-input-mono' : 'bn-input'}
        id={id}
        type="text"
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        placeholder={placeholder}
        value={value}
        data-autofocus={autoFocus ? '' : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint === undefined ? null : <p className="bn-field-hint">{hint}</p>}
    </div>
  )
}

// ---------------------------------------------------------------- retroactive capture claims

/* THE CLAIM EDITOR — one body, two scopes: every card in a box (or a selection of it), and one
 * card on the detail panel. Every field is tri-state: off (the field is omitted), on and filled
 * (set it), on and empty (send `null`, clear the claim). `game` has no cleared form. The game
 * select drives the finish, rarity and product vocabularies whether or not it is sent. Nothing
 * is pre-armed.
 *
 * PRODUCT IS THE ONE ROW THAT CAN BE ABSENT ENTIRELY, and the registry decides it rather than
 * this file: `GET /games` serves `product_game` — `codes/products.py:GAME` on the wire — and the
 * row is drawn only while the selected game IS that game. Hardcoding `pokemon_code` here would
 * be the registry mirror `CaptureScreen.tsx` refuses for exactly the same control, and a
 * Product picker over a box of Pokemon singles offers a claim nothing downstream would ever
 * read. Switching the game away from it disarms the row rather than leaving an invisible field
 * armed. */

type ClaimField = 'game' | 'setHint' | 'variant' | 'rarityClaim' | 'product' | 'note'

export type ClaimPatch = {
  setHint?: string | null
  /** D3 rung 1's finish claim, a LIST: one member determines, two or more filter. `null`
   *  clears the claim. */
  variant?: readonly string[] | null
  game?: string
  rarityClaim?: string[] | null
  /** C10/D70's product claim, a SCALAR where the two above are sets: a stack came out of one
   *  sealed product, so "two products at once" is not a state. `null` clears it back to no
   *  claim, which is what `#/codes` counts as unclaimed and what both channel lanes refuse. */
  product?: string | null
  note?: string | null
}

export function ClaimEditor({
  scope,
  game,
  busy,
  onApply,
  onCancel,
}: {
  /** What the apply will reach, as a sentence. Drawn on the button as well as above the fields. */
  scope: string
  /** The game whose vocabulary the chips are drawn from before the operator changes it. Null
   *  falls back to the registry's own default. */
  game: string | null
  busy: boolean
  onApply: (patch: ClaimPatch) => void
  onCancel: () => void
}) {
  const [entries, setEntries] = useState<readonly GameEntry[] | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)
  const [productList, setProductList] = useState<readonly ProductEntry[]>([])
  const [productGame, setProductGame] = useState<string | null>(null)
  const [armed, setArmed] = useState<readonly ClaimField[]>([])
  const [pickedGame, setPickedGame] = useState<string | null>(game)
  const [setHint, setSetHint] = useState('')
  const [variant, setVariant] = useState<readonly string[]>([])
  const [rarity, setRarity] = useState<readonly string[]>([])
  const [product, setProduct] = useState('')
  const [note, setNote] = useState('')
  const [refused, setRefused] = useState<string | null>(null)

  /* The registry, once. If the read fails the two chip rows say they have no vocabulary, and
     the product row is not drawn at all — `productGame` stays null, so nothing equals it. */
  useEffect(() => {
    let live = true
    getGames()
      .then((registry) => {
        if (!live) return
        setEntries(registry.games)
        setFallback(registry.default)
        /* `?? []` AND `?? null` BECAUSE THE COMMENT ABOVE ALREADY PROMISES THIS, and until
           2026-09-05 the code did not keep the promise: a registry that answered no products
           overwrote the `[]` this state starts as with `undefined`, and the next read of
           `productList.length` threw inside the editor's render. The subtree came out of the
           DOM with no message anywhere — which is what four cases in
           `app/tests/inventory.spec.ts` were dying on, and they said only that an element had
           been detached. `GET /games` on a current server always sends both, so the shapes
           this defends against are an older server and a test's stub; the first is real and
           the second is how it was found. */
        setProductList(registry.products ?? [])
        setProductGame(registry.product_game ?? null)
      })
      .catch(() => {
        if (!live) return
        setEntries([])
      })
    return () => {
      live = false
    }
  }, [])

  const key = pickedGame ?? fallback
  const entry = entries?.find((candidate) => candidate.key === key) ?? null
  /* The product claim belongs to one game and the registry says which (`codes/products.py:GAME`
     over the wire). A registry that answered no products is the same "not drawn" as a game that
     does not claim them. */
  const showsProduct = productGame !== null && key === productGame && productList.length > 0
  const picked = productList.find((candidate) => candidate.key === product) ?? null
  const isArmed = (field: ClaimField) => armed.includes(field)
  const arm = (field: ClaimField, on: boolean) =>
    setArmed((held) =>
      on ? [...held.filter((f) => f !== field), field] : held.filter((f) => f !== field),
    )

  /* A ROW THAT IS NOT DRAWN IS NOT ARMED. Arm Product against the code-card game, change the
     game select to Pokemon, and without this the row is gone from the screen while its claim
     is still in the patch — a write nobody can see they asked for. Same reference back when
     there is nothing to disarm, so this settles in one pass. */
  useEffect(() => {
    if (showsProduct) return
    setArmed((held) => (held.includes('product') ? held.filter((f) => f !== 'product') : held))
  }, [showsProduct])

  const submit = () => {
    if (armed.length === 0) {
      setRefused('Switch on a field before applying. Nothing was sent.')
      return
    }
    setRefused(null)

    const patch: ClaimPatch = {}
    if (isArmed('game') && key !== null) patch.game = key
    if (isArmed('setHint')) patch.setHint = setHint.trim() === '' ? null : setHint.trim()
    if (isArmed('variant')) patch.variant = variant.length === 0 ? null : [...variant]
    if (isArmed('rarityClaim')) patch.rarityClaim = rarity.length === 0 ? null : [...rarity]
    if (isArmed('product')) patch.product = product === '' ? null : product
    if (isArmed('note')) patch.note = note.trim() === '' ? null : note.trim()
    onApply(patch)
  }

  return (
    <div className="boxops-claims">
      <p className="boxops-claim-scope">Change claims on {scope}</p>
      <p className="bn-field-hint">Switch a field on to change it. Empty clears it.</p>

      <ClaimRow field="game" label="Game" armed={isArmed('game')} onArm={arm} says="required — nothing to clear it to">
        <select
          className="bn-select"
          value={key ?? ''}
          disabled={entries === null}
          onChange={(event) => setPickedGame(event.target.value)}
          aria-label="Game"
        >
          {entries === null ? <option value="">reading the registry…</option> : null}
          {(entries ?? []).map((candidate) => (
            <option key={candidate.key} value={candidate.key}>
              {candidate.display}
            </option>
          ))}
        </select>
      </ClaimRow>

      <ClaimRow field="setHint" label="Set hint" armed={isArmed('setHint')} onArm={arm} says="leave empty to clear it">
        <PlainInput value={setHint} onChange={setSetHint} placeholder="ME01" label="Set hint" mono />
      </ClaimRow>

      <ClaimRow
        field="variant"
        label="Finish"
        armed={isArmed('variant')}
        onArm={arm}
        says="none chosen clears it, and the ladder infers the finish instead"
      >
        {(entry?.finishes ?? []).length === 0 ? (
          <p className="boxops-machine">
            {entry === null ? 'finishes: unread' : `finishes: none for ${entry.display}`}
          </p>
        ) : (
          <div className="boxops-chips">
            {(entry?.finishes ?? []).map((name) => {
              const on = variant.includes(name)
              return (
                <button
                  key={name}
                  className="boxops-chip"
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    setVariant((held) =>
                      held.includes(name)
                        ? held.filter((f) => f !== name)
                        : (entry?.finishes ?? []).filter((f) => f === name || held.includes(f)),
                    )
                  }
                >
                  {on ? <Icon name="check" size={12} /> : null}
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </ClaimRow>

      <ClaimRow field="rarityClaim" label="Rarity" armed={isArmed('rarityClaim')} onArm={arm} says="none chosen clears it">
        {(entry?.rarities ?? []).length === 0 ? (
          <p className="boxops-machine">
            {entry === null ? 'rarities: unread' : `rarities: none for ${entry.display}`}
          </p>
        ) : (
          <div className="boxops-chips">
            {(entry?.rarities ?? []).map((name) => {
              const on = rarity.includes(name)
              return (
                <button
                  key={name}
                  className="boxops-chip"
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    setRarity((held) =>
                      held.includes(name) ? held.filter((r) => r !== name) : [...held, name],
                    )
                  }
                >
                  {on ? <Icon name="check" size={12} /> : null}
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </ClaimRow>

      {!showsProduct ? null : (
        <ClaimRow
          field="product"
          label="Product"
          armed={isArmed('product')}
          onArm={arm}
          says="which sealed product the stack came out of — none chosen clears it"
        >
          <div className="boxops-product">
            <select
              className="bn-select"
              value={product}
              onChange={(event) => setProduct(event.target.value)}
              aria-label="Product"
            >
              <option value="">No claim</option>
              {productList.map((candidate) => (
                <option key={candidate.key} value={candidate.key}>
                  {candidate.display}
                </option>
              ))}
            </select>
            {/* Outlined off the premium lane: a default pill's fill is `--bn-surface-2`, which
                is this row's own ground, so Bulk would read as bare text. */}
            {picked === null ? null : (
              <Pill tone={picked.premium ? 'accent' : 'default'} outline={!picked.premium}>
                {picked.premium ? 'Premium' : 'Bulk'}
              </Pill>
            )}
          </div>
        </ClaimRow>
      )}

      <ClaimRow field="note" label="Note" armed={isArmed('note')} onArm={arm} says="free text — the only handle an unidentified card has">
        <PlainInput value={note} onChange={setNote} placeholder="blue-eyes, japanese" label="Note" />
      </ClaimRow>

      {!showsProduct ? null : (
        <p className="bn-field-hint">A code card with no product cannot be sold until it has one again.</p>
      )}
      {refused === null ? null : <Notice tone="warn">{refused}</Notice>}

      <div className="boxops-actions">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" busy={busy} onClick={submit}>
          Apply to {scope}
        </Button>
      </div>
    </div>
  )
}

/** One tri-state row: the switch that arms it, the label, the rule for its empty form, and the
 *  control. The control is not disabled while the row is off: what the switch decides is
 *  whether the value is SENT. */
function ClaimRow({
  field,
  label,
  says,
  armed,
  onArm,
  children,
}: {
  field: ClaimField
  label: string
  says: string
  armed: boolean
  onArm: (field: ClaimField, on: boolean) => void
  children: ReactNode
}) {
  const id = useId()
  return (
    <div className={armed ? 'boxops-claim-row boxops-claim-armed' : 'boxops-claim-row'}>
      <div className="boxops-claim-head">
        <div className="boxops-claim-words">
          <label className="boxops-claim-label" htmlFor={id}>
            {label}
          </label>
          <span className="boxops-claim-says">{says}</span>
        </div>
        <input
          className="boxops-check"
          id={id}
          type="checkbox"
          role="switch"
          aria-checked={armed}
          checked={armed}
          onChange={(event) => onArm(field, event.target.checked)}
        />
      </div>
      <div className="boxops-claim-control">{children}</div>
    </div>
  )
}

/** A text input with no `<label>` of its own — `ClaimRow` owns the label. */
function PlainInput({
  value,
  onChange,
  placeholder,
  label,
  mono = false,
}: {
  value: string
  onChange: (next: string) => void
  placeholder?: string
  label: string
  mono?: boolean
}) {
  return (
    <input
      className={mono ? 'bn-input bn-input-mono' : 'bn-input'}
      type="text"
      aria-label={label}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="off"
      spellCheck={false}
      placeholder={placeholder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

/** The receipt a box-wide apply leaves: what the scope reached, what actually changed, and
 *  which sold or retired cards the route stepped over. */
function ClaimReceipt({ result, boxLabel }: { result: BoxClaimResult; boxLabel: string }) {
  return (
    <div className="boxops-receipt">
      <Notice
        tone="ok"
        title={
          result.applied === 0
            ? 'Nothing changed — every card in scope already said this.'
            : `${count(result.applied, 'card', 'cards')} changed.`
        }
        code={`${boxLabel}: eligible ${result.eligible}, applied ${result.applied}, unchanged ${result.unchanged}, sidecars ${result.sidecars_rewritten}, skipped ${result.skipped_terminal}`}
      >
        {result.skipped.length === 0
          ? null
          : /* A bulk write's receipt names the RECORDS it stepped over, by the key it aimed by.
               These cards were not touched, so none has a slot in the result to count to, and an
               operator matching this line against the store needs the key it was aimed by. */
            // sigil-ok: a bulk write's receipt names the records it skipped, by the key it aimed by
            `Stepped over: ${result.skipped.map((row) => `#${row.index} ${row.state}`).join(', ')}`}
      </Notice>
    </div>
  )
}

/** One SKU's line in the plan and in the receipt, with the age of the figures it is quoting. */
/** A box's own NAME off the registry (S1: never the number a person reads on the drawer).
 *  'another box' when the registry does not carry this box at all — the same fallback the
 *  release receipt above already used for a box this screen never loaded. */
function boxName(boxes: readonly BoxRecord[], box: number): string {
  const found = boxes.find((candidate) => candidate.box === box)
  return found === undefined ? 'another box' : (found.name ?? UNNAMED_BOX)
}

function ListingLine({
  row,
  at,
  boxes = [],
}: {
  row: BoxListingRow
  at?: string | null
  /** The registry, to name the other boxes a SKU is also held in (S1: never the number). */
  boxes?: readonly BoxRecord[]
}) {
  const gives = Object.entries(row.releases)
  const keeps = Object.entries(row.after)
  return (
    <p className="boxops-machine boxops-line">
      <span className="boxops-line-text bn-facts">
        <span>{row.sku}</span>{' '}
        <span>{gives.length === 0 ? 'nothing' : gives.map(([k, n]) => `${n} ${k}`).join(' ')}</span>
        {keeps.length === 0 ? null : (
          <>
            {' '}
            <span>keeps {keeps.map(([k, n]) => `${n} ${k}`).join(' ')}</span>
          </>
        )}
        {row.also_in_boxes.length === 0 ? null : (
          <>
            {' '}
            <span>
              also {row.also_in_boxes.map((o) => `${boxName(boxes, o.box)} (${o.copies})`).join(', ')}
            </span>
          </>
        )}
      </span>
      <ReadingAge at={at} />
    </p>
  )
}

/* THE LISTING RELEASE — D34. Two steps and the first is free: opening the row fetches the plan,
 * and the button that asserts does not exist until that has answered. Draws nothing when there
 * is nothing to release. */
/* A listing stage as the owner reads it, never the pipeline's word for it (D196). */
function stageWords(stage: string): string {
  if (stage === 'pushed') return 'sent'
  if (stage === 'staged') return 'waiting to go live'
  return stage
}

function ReleaseListings({
  record,
  boxes = [],
  listings = NO_LISTINGS,
  onChanged,
}: {
  record: BoxRecord
  /** The registry, to name the other boxes that hold copies. */
  boxes?: readonly BoxRecord[]
  listings?: Readonly<Record<string, Listing>>
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [plan, setPlan] = useState<BoxListingPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<ListingReleaseResult | null>(null)

  const box = record.box

  useEffect(() => {
    if (!open) return
    let ignore = false
    setLoading(true)
    setPlan(null)
    setTrouble(null)
    getBoxListings(box)
      .then((answer) => {
        if (!ignore) setPlan(answer)
      })
      .catch((err) => {
        if (!ignore) setTrouble(describeFailure(err))
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [open, box])

  const run = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      const result = await releaseBoxListings(box)
      setReceipt(result)
      setOpen(false)
      setPlan(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  if (receipt !== null) {
    const gave = Object.entries(receipt.given_up)
    return (
      <div className="boxops-receipt">
        <Notice
          tone="ok"
          title={`Released ${count(receipt.released, 'SKU', 'SKUs')} in ${record.name ?? UNNAMED_BOX}${
            gave.length === 0 ? '.' : `, giving up ${gave.map(([stage, n]) => `${n} ${stageWords(stage)}`).join(', ')}.`
          }`}
        >
          Nothing was deleted — these are counts, and staging again re-establishes them.
          {receipt.frees_box ? null : (
            <>
              {' '}
              <strong>{record.name ?? UNNAMED_BOX} is still held.</strong>{' '}
              {count(receipt.still_held.length, 'SKU', 'SKUs')} kept copies this box could not
              account for
              {receipt.also_in_boxes.length === 0
                ? ''
                : `, and ${receipt.also_in_boxes.map((b) => boxName(boxes, b)).join(', ')} hold copies of them`}
              , so the delete will go on refusing.
            </>
          )}
        </Notice>
        {receipt.listings.map((row) => (
          <ListingLine key={row.sku} row={row} at={listings[row.sku]?.live_as_of} boxes={boxes} />
        ))}
      </div>
    )
  }

  if (record.listed === 0) return null

  return (
    <>
      <Op
        icon="flag"
        danger
        label="Release listing hold"
        detail={count(record.listed, 'card', 'cards')}
        said={`Release the listing hold on ${count(record.listed, 'card', 'cards')}…`}
        busy={false}
        expanded={open}
        onClick={() => setOpen((held) => !held)}
      />
      {!open ? null : (
        <div className="boxops-confirm">
          <p className="boxops-confirm-text">
            {count(record.listed, 'card', 'cards')} in {record.name ?? UNNAMED_BOX}{' '}
            {record.listed === 1 ? 'belongs' : 'belong'} to a SKU this store believes TCGplayer
            holds. Release only if{' '}
            <strong>you've checked TCGplayer and it holds none of them</strong> — nothing here
            can verify that. Every figure below is last-written, not read now.
          </p>

          {loading ? <p className="bn-field-hint">Reading what these SKUs are holding…</p> : null}

          {plan === null ? null : (
            <>
              <Notice tone={plan.frees_box ? 'info' : 'warn'}>
                Each SKU gives up at most the copies this box holds.{' '}
                {plan.frees_box ? (
                  <>This releases {record.name ?? UNNAMED_BOX} completely.</>
                ) : (
                  <>
                    <strong>This will not free {record.name ?? UNNAMED_BOX}.</strong>{' '}
                    {count(plan.still_held.length, 'SKU', 'SKUs')} will keep copies
                    {plan.also_in_boxes.length === 0
                      ? ''
                      : ` also held by ${plan.also_in_boxes.map((b) => boxName(boxes, b)).join(', ')}`}
                    .
                  </>
                )}
              </Notice>
              <div className="boxops-lines">
                {plan.listings.map((row) => (
                  <ListingLine key={row.sku} row={row} at={listings[row.sku]?.live_as_of} boxes={boxes} />
                ))}
              </div>
            </>
          )}

          <Trouble failure={trouble} />
          <div className="boxops-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false)
                setPlan(null)
                setTrouble(null)
              }}
            >
              Cancel
            </Button>
            {/* Absent, not disabled, until the free step has answered. */}
            {plan === null || plan.skus === 0 ? null : (
              <Button variant="danger-solid" icon="flag" busy={busy} onClick={() => void run()}>
                TCGplayer holds none of these — release
              </Button>
            )}
          </div>
        </div>
      )}
    </>
  )
}

/* PHOTO RECLAMATION — D89. Deletes the photographs of a box's SOLD cards and keeps every record.
 * The free count is read on opening, and the control that fires does not exist until it has
 * answered. Both presses name the box. */
function ReclaimPhotos({ record, onChanged }: { record: BoxRecord; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [plan, setPlan] = useState<BoxPhotoPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<PhotoReclaimResult | null>(null)

  const box = record.box

  useEffect(() => {
    if (!open) return
    let ignore = false
    setLoading(true)
    setPlan(null)
    setTrouble(null)
    getBoxPhotos(box)
      .then((answer) => {
        if (!ignore) setPlan(answer)
      })
      .catch((err) => {
        if (!ignore) setTrouble(describeFailure(err))
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [open, box])

  const run = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      const result = await reclaimBoxPhotos(box)
      setReceipt(result)
      setOpen(false)
      setPlan(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  if (receipt !== null) {
    return (
      <div className="boxops-receipt">
        <Notice
          tone="ok"
          title={`Reclaimed ${count(receipt.reclaimed, 'photograph', 'photographs')} from ${record.name ?? UNNAMED_BOX}, ${megabytes(receipt.bytes)}.`}
          code={receipt.keys.join(', ')}
        >
          Records stay sold; each keeps its photograph's digest. No undo.
          {receipt.already_reclaimed > 0
            ? ` ${count(receipt.already_reclaimed, 'card', 'cards')} had been reclaimed before.`
            : ''}
        </Notice>
      </div>
    )
  }

  if (record.sold === 0) return null

  return (
    <>
      <Op
        icon="image"
        danger
        label="Reclaim photographs"
        detail={count(record.sold, 'sold card', 'sold cards')}
        said={`Reclaim the photographs of ${count(record.sold, 'sold card', 'sold cards')} in ${record.name ?? UNNAMED_BOX}…`}
        busy={false}
        expanded={open}
        onClick={() => setOpen((held) => !held)}
      />
      {!open ? null : (
        <div className="boxops-confirm">
          <p className="boxops-confirm-text">
            Deletes the <strong>photograph</strong> of every sold card in {record.name ?? UNNAMED_BOX}; records
            stay.{' '}
            <strong>No undo</strong> — a photograph can't be regenerated.
          </p>

          {loading ? <p className="bn-field-hint">Counting what a reclaim would delete…</p> : null}

          {plan === null ? null : (
            <Notice tone={plan.reclaimable.cards === 0 ? 'info' : 'warn'}>
              {plan.reclaimable.cards === 0 ? (
                <>
                  Nothing to reclaim: no sold card in {record.name ?? UNNAMED_BOX} still has a photograph on disk
                  {plan.reclaimed.cards > 0
                    ? ` — ${count(plan.reclaimed.cards, 'was', 'were')} reclaimed already`
                    : ''}
                  .
                </>
              ) : (
                <>
                  <strong>
                    {count(plan.reclaimable.cards, 'photograph', 'photographs')},{' '}
                    {megabytes(plan.reclaimable.bytes)}, would go
                  </strong>
                  {plan.reclaimed.cards > 0
                    ? ` (${count(plan.reclaimed.cards, 'card', 'cards')} reclaimed already)`
                    : ''}
                  . Untouched: the {count(plan.on_hand_photos, 'photograph', 'photographs')} of
                  cards still on hand, and every retired card's.
                </>
              )}
            </Notice>
          )}

          <Trouble failure={trouble} />
          <div className="boxops-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false)
                setPlan(null)
                setTrouble(null)
              }}
            >
              Cancel
            </Button>
            {plan === null || plan.reclaimable.cards === 0 ? null : (
              <Button variant="danger-solid" icon="trash" busy={busy} onClick={() => void run()}>
                Delete {count(plan.reclaimable.cards, 'photograph', 'photographs')} from {record.name ?? UNNAMED_BOX}{' '}
                permanently
              </Button>
            )}
          </div>
        </div>
      )}
    </>
  )
}

/** Bytes as the unit a person compares a disk against. */
function megabytes(bytes: number): string {
  const mb = bytes / 1_000_000
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb).toLocaleString()} MB`
}

/* THE WHOLE-BOX DELETE — the most destructive action in the product, and the one place that
 * gates. Two presses that both name the box; the server keeps the refusal
 * (`box_not_empty_of_commitments`) and it is shown whole.
 *
 * D134 (2026-09-11): a sold, retired or moved record no longer answers that refusal — it is
 * buried instead, readable afterward on `#/graveyard`, and only a listed copy still blocks.
 * The Notice below draws that distinction before the press: what will be buried and lost is
 * separate from what will refuse outright. */
function DeleteBox({
  record,
  onChanged,
  onDeleted,
}: {
  record: BoxRecord
  onChanged: () => void
  onDeleted: () => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)

  const run = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      const result: BoxDeleteResult = await deleteBox(record.box)
      setOpen(false)
      toast({
        kind: 'ok',
        icon: 'trash',
        title: `${record.name ?? UNNAMED_BOX} is gone. There is no undo.`,
        body: `${count(result.cards, 'card', 'cards')} and ${count(result.photos, 'photograph', 'photographs')} deleted.${
          result.buried > 0 ? ` ${count(result.buried, 'sold or retired card', 'sold or retired cards')} moved to the graveyard.` : ''
        }${result.directory_removed ? '' : ' One photo folder stays: it holds a file the delete did not expect.'}`,
        ttlMs: 12000,
      })
      onChanged()
      onDeleted()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Op
        icon="trash"
        danger
        label="Delete this box…"
        detail="no undo"
        busy={false}
        expanded={open}
        onClick={() => setOpen((held) => !held)}
      />
      {!open ? null : (
        <div className="boxops-confirm">
          <p className="boxops-confirm-text">
            Deletes <strong>every record, photograph and sidecar</strong> in {record.name ?? UNNAMED_BOX}{' '}
            — {count(record.cards, 'card', 'cards')}, plus its queue entries, id cache, and the
            box. <strong>No undo.</strong>
          </p>
          <Notice tone={record.listed === 0 ? 'info' : 'warn'}>
            {record.listed === 0
              ? `${
                  record.sold + record.retired + record.moved === 0
                    ? 'Nothing in this box has departed.'
                    : `${count(record.sold + record.retired + record.moved, 'departed record', 'departed records')} will be buried, photographs deleted.`
                } No undo.`
              : `Refused: ${count(record.listed, 'card', 'cards')} listed — release the hold first.${
                  record.sold + record.retired + record.moved > 0
                    ? ` ${count(record.sold + record.retired + record.moved, 'other departed record', 'other departed records')} will be buried once it goes through.`
                    : ''
                }`}
          </Notice>
          <Trouble failure={trouble} />
          <div className="boxops-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false)
                setTrouble(null)
              }}
            >
              Cancel
            </Button>
            <Button variant="danger-solid" icon="trash" busy={busy} onClick={() => void run()}>
              Delete this box permanently
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
