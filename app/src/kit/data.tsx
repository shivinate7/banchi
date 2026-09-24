import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent, ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'

import { Icon, type IconName } from './Icon'
import { cropStyle, type Crop } from './index'
import { hasSheet, openSheet, sheetHref } from './sheets'
import { storedBoxRecency } from '../deviceMemory'
import { moneyGrouped, moneySigned } from '../money'
import { PositionLabel } from '../PositionLabel'
import type { Place } from '../types'
import './data.css'

/* THE KIT'S DATA PRIMITIVES: how a figure, a card, a box, a place, a status and a filter are
 * drawn, ONE WAY EACH, on every screen.
 *
 * WHY THIS FILE EXISTS (the owner, 2026-09-23): "say a new page in the sidebar gets built
 * tomorrow, it should be able to autocall/inherit the properties of the other pages". A page
 * built tomorrow imports these and inherits every rule below without knowing it. A screen that
 * draws one of these things by hand is the drift the UX review measured: money in four faces,
 * dates in seven formats, a box named six ways, a missing photo drawn four ways.
 *
 * THE RULES EACH PRIMITIVE CARRIES, so a caller never has to remember them:
 *  - MONEY IS MONO, always with `$`, inside inputs and chips too (D221, the owner's ruling
 *    2026-09-23). `Money` is the only way a dollar figure is drawn.
 *  - MONO IS FOR MACHINE STRINGS ONLY: SKUs, run ids, card numbers, key caps, and money. A
 *    count, a date, a box number and a name are Inter.
 *  - A SEPARATOR IS DRAWN BY CSS, NEVER TYPED (D218). `Sep` is the one separator.
 *  - A BOX IS ITS NAME, THEN ITS NUMBER (D132), and a list of boxes is MOST RECENT FIRST (the
 *    owner's ruling, 2026-09-23). `BoxLabel` and `boxesMostRecentFirst`.
 *  - A CARD'S LINE NAMES ITS FINISH, so two printings of one card never look the same.
 *  - A PRODUCT OPENS BY SKU, NEVER BY ONE COPY (D212: every copy is fungible).
 *  - A FILTER COMBINES WITH EVERY OTHER, IN ANY ORDER, and a pick list NEVER opens the native OS
 *    menu (the owner's rulings, 2026-09-23). `Select`, `FilterChips` and `SortControl` draw
 *    Capture's own option rows: a check mark, the name, the count on the right.
 *  - EVERY FILTER CONTROL IN ONE BAR IS ONE HEIGHT (`--bn-control-h`), and its width sits
 *    between one floor and one cap, in `data.css`.
 *
 * NOT A SCREEN'S FILE. A screen passes data in and gets the drawing back. Nothing here fetches.
 */

/* ============================================================================================
 * Sep — the one separator between two facts on a line.
 * ============================================================================================ */

/** The dot between two facts, drawn by CSS (D218). A screen reader hears a comma, so two facts
 *  never run together into one word. */
export function Sep() {
  return (
    <span className="bn-sep">
      <span className="bn-sr">, </span>
    </span>
  )
}

/* ============================================================================================
 * Money and Count — a figure, drawn one way.
 * ============================================================================================ */

/** A dollar figure: mono, tabular, always `$`, grouped past a thousand. `—` where there is none.
 *  `signed` draws a change (`+$1.20`, `−$0.35`). */
export function Money({
  value,
  signed,
  className,
}: {
  readonly value: number | null | undefined
  readonly signed?: boolean
  readonly className?: string
}) {
  const empty = typeof value !== 'number'
  return (
    <span className={['bn-money', className].filter(Boolean).join(' ')} data-empty={empty ? 'true' : undefined}>
      {signed ? moneySigned(value) : moneyGrouped(value)}
    </span>
  )
}

/** `1,179` in Inter tabular figures. */
function countText(value: number): string {
  return Number.isFinite(value) ? Math.round(value).toLocaleString('en-US') : '—'
}

/** How many of a thing: ONE count style everywhere, a quiet badge in tabular figures, never
 *  `(1179)` in brackets. `label` is what a screen reader hears after the number. */
export function Count({
  value,
  label,
  tone,
  className,
}: {
  readonly value: number
  readonly label?: string
  /** `strong` is the one count on a row that asks for attention. */
  readonly tone?: 'strong'
  readonly className?: string
}) {
  const text = countText(value)
  return (
    <span className={['bn-count', tone === 'strong' ? 'bn-count-strong' : '', className ?? ''].filter(Boolean).join(' ')}>
      {label === undefined ? (
        text
      ) : (
        <>
          <span aria-hidden="true">{text}</span>
          <span className="bn-sr">{`${text} ${label}`}</span>
        </>
      )}
    </span>
  )
}

/** `a`, `a and b`, `a, b and c`. */
function listWords(items: readonly string[]): string {
  if (items.length <= 1) return items[0] ?? ''
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1] ?? ''}`
}

/** What a narrowed list says above itself: `12 of 40 cards, filtered by Pokémon and Rare` and a
 *  Clear press. With no filter and nothing hidden it says only `40 cards`. Every narrowed list
 *  states how many it hides (the filtering review, FLT-13). */
export function FilterCount({
  shown,
  total,
  noun = { one: 'card', many: 'cards' },
  filters = [],
  onClear,
  className,
}: {
  readonly shown: number
  readonly total: number
  readonly noun?: { readonly one: string; readonly many: string }
  /** The active filters, in words: `['Pokémon', 'Rare']`. */
  readonly filters?: readonly string[]
  readonly onClear?: () => void
  readonly className?: string
}) {
  const narrowed = filters.length > 0 || shown !== total
  const word = (narrowed ? total : shown) === 1 ? noun.one : noun.many
  return (
    <p className={['bn-filtercount', className].filter(Boolean).join(' ')} role="status" aria-live="polite">
      <span className="bn-filtercount-figure">
        {narrowed ? `${countText(shown)} of ${countText(total)} ${word}` : `${countText(shown)} ${word}`}
      </span>
      {filters.length > 0 ? <span className="bn-filtercount-by">{`, filtered by ${listWords(filters)}`}</span> : null}
      {narrowed && onClear !== undefined ? (
        <button type="button" className="bn-filtercount-clear" onClick={onClear}>
          Clear
        </button>
      ) : null}
    </p>
  )
}

/* ============================================================================================
 * StatusBadge — one tone per meaning.
 * ============================================================================================ */

/** The meanings a status can have. A screen maps its own states onto these, and the tone
 *  follows: the review found "needs pricing" in two colours on one screen, and blue meaning
 *  several different things. */
export type StatusKind =
  /** Waits on the OWNER. The one attention tone. */
  | 'needs'
  /** Moving now, with nothing for the owner to do. */
  | 'working'
  /** Finished well. */
  | 'done'
  /** Stopped, and the owner must look. */
  | 'failed'
  /** Waits on somebody else: a buyer, the marketplace, a run. */
  | 'waiting'
  /** A plain fact with no state. */
  | 'neutral'

export type StatusTone = 'warn' | 'accent' | 'ok' | 'danger' | 'default'

/** The one tone for each meaning. Amber is ONLY "needs the owner"; blue is ONLY "moving now";
 *  a neutral count is never coloured. */
export const STATUS_TONES: Readonly<Record<StatusKind, StatusTone>> = {
  needs: 'warn',
  working: 'accent',
  done: 'ok',
  failed: 'danger',
  waiting: 'default',
  neutral: 'default',
}

const STATUS_ICONS: Readonly<Record<StatusKind, IconName | null>> = {
  needs: 'alert',
  working: 'refresh',
  done: 'check',
  failed: 'x',
  waiting: 'clock',
  neutral: null,
}

/** A state as a pill, in its meaning's one tone, with the icon that says the same thing in a
 *  second channel for a reader who cannot tell the colours apart. */
export function StatusBadge({
  status,
  children,
  size,
  className,
}: {
  readonly status: StatusKind
  readonly children: ReactNode
  readonly size?: 'sm'
  readonly className?: string
}) {
  const tone = STATUS_TONES[status]
  const icon = STATUS_ICONS[status]
  return (
    <span
      className={[
        'bn-pill',
        'bn-status',
        tone === 'default' ? '' : `bn-pill-${tone}`,
        size === 'sm' ? 'bn-pill-sm' : '',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
      data-status={status}
    >
      {icon === null ? null : <Icon name={icon} size={size === 'sm' ? 10 : 12} />}
      {children}
    </span>
  )
}

/* ============================================================================================
 * ProductLink and OrderLink — a name that opens where the thing lives.
 * ============================================================================================ */

/** True for a press the browser should handle itself: a new tab, a new window, a download. */
function modified(event: ReactMouseEvent): boolean {
  return event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey
}

/** A product's name that opens the product, by SKU (D212: never one copy). It opens the product
 *  sheet where one is registered, and the product page where none is. It is a real link, so a
 *  middle-click opens the page in a new tab either way. */
export function ProductLink({
  sku,
  name,
  children,
  className,
}: {
  readonly sku: string
  /** A caption the sheet may show while it loads. Defaults to the text of `children`. */
  readonly name?: string
  readonly children: ReactNode
  readonly className?: string
}) {
  const props = name === undefined ? { sku } : { sku, name }
  return (
    <a
      className={['bn-datalink', className].filter(Boolean).join(' ')}
      href={sheetHref('product', props)}
      onClick={(event) => {
        if (modified(event) || !hasSheet('product')) return
        event.preventDefault()
        openSheet('product', props)
      }}
    >
      {children}
    </a>
  )
}

/** An order's number that opens the order. `orderKey` is the STORE KEY (`source:number`), the
 *  one `#/orders` can resolve; a bare number resolves to nothing there. */
export function OrderLink({
  orderKey,
  children,
  className,
}: {
  readonly orderKey: string
  readonly children: ReactNode
  readonly className?: string
}) {
  return (
    <a
      className={['bn-datalink', className].filter(Boolean).join(' ')}
      href={sheetHref('order', { orderKey })}
      onClick={(event) => {
        if (modified(event) || !hasSheet('order')) return
        event.preventDefault()
        openSheet('order', { orderKey })
      }}
    >
      {children}
    </a>
  )
}

/* ============================================================================================
 * CardLine and CardThumb — one card, drawn one way.
 * ============================================================================================ */

/** A card's identity on one line: its name, then set, number, finish and rarity. THE FINISH IS
 *  ALWAYS SAID when it is known, so a foil and a normal printing of one card never read as the
 *  same row. With `sku`, the name opens the product. */
export function CardLine({
  name,
  sku,
  set,
  number,
  condition,
  finish,
  rarity,
  layout = 'stack',
  className,
}: {
  /** Null for a card nothing has identified yet. */
  readonly name: string | null
  readonly sku?: string | null
  readonly set?: string | null
  /** The collector number as `cardNumber.ts:collectorNumber` composes it. */
  readonly number?: string | null
  /** The TCGplayer condition, which carries the finish (`Near Mint Holofoil`). Drawn whole:
   *  the grade stays on every row (the owner's ruling, 2026-09-23). */
  readonly condition?: string | null
  /** The finish on its own (`Reverse holo`), for a card with no condition string, or one whose
   *  condition does not already say it. */
  readonly finish?: string | null
  readonly rarity?: string | null
  /** `stack`: the name, then the facts under it. `inline`: one line. */
  readonly layout?: 'stack' | 'inline'
  readonly className?: string
}) {
  const facts: { readonly key: string; readonly node: ReactNode }[] = []
  if (set) facts.push({ key: 'set', node: <span className="bn-cardline-set">{set}</span> })
  if (number) facts.push({ key: 'number', node: <span className="bn-cardline-number">{number}</span> })
  if (condition) facts.push({ key: 'condition', node: <span className="bn-cardline-finish">{condition}</span> })
  if (finish && !(condition ?? '').toLowerCase().includes(finish.toLowerCase())) {
    facts.push({ key: 'finish', node: <span className="bn-cardline-finish">{finish}</span> })
  }
  if (rarity) facts.push({ key: 'rarity', node: <span className="bn-cardline-rarity">{rarity}</span> })

  const title =
    name === null ? (
      <span className="bn-cardline-name is-unknown">Not identified yet</span>
    ) : sku ? (
      <ProductLink sku={sku} name={name} className="bn-cardline-name">
        {name}
      </ProductLink>
    ) : (
      <span className="bn-cardline-name">{name}</span>
    )

  return (
    <span className={['bn-cardline', `bn-cardline-${layout}`, className ?? ''].filter(Boolean).join(' ')}>
      {title}
      {facts.length === 0 ? null : (
        <span className="bn-cardline-facts">
          {layout === 'inline' ? <Sep /> : null}
          {facts.map((fact, at) => (
            <span key={fact.key} className="bn-cardline-fact">
              {at === 0 ? null : <Sep />}
              {fact.node}
            </span>
          ))}
        </span>
      )}
    </span>
  )
}

export type CardThumbSize = 'sm' | 'md' | 'lg'

/** A card's photograph at one of three sizes, in a card-shaped frame. A card with no photograph,
 *  or one that will not load, draws THE ONE "no photo" state at every size. */
export function CardThumb({
  src,
  alt,
  size = 'md',
  crop = null,
  focus,
  className,
}: {
  /** The photograph's URL, or null when there is none. */
  readonly src: string | null
  /** What the photograph shows, usually the card's name. */
  readonly alt: string
  readonly size?: CardThumbSize
  /** Where the card sits inside the rig's frame (`POST /pipeline/crop-preview`). */
  readonly crop?: Crop | null
  readonly focus?: number
  readonly className?: string
}) {
  const [failed, setFailed] = useState<string | null>(null)
  const missing = src === null || failed === src
  const style = missing ? undefined : cropStyle(crop, focus)
  return (
    <span
      className={['bn-thumb', `bn-thumb-${size}`, className ?? ''].filter(Boolean).join(' ')}
      data-missing={missing ? 'true' : undefined}
      role={missing ? 'img' : undefined}
      aria-label={missing ? `${alt}: no photo` : undefined}
    >
      {missing ? (
        <>
          <Icon name="image" size={size === 'sm' ? 14 : size === 'md' ? 18 : 24} />
          {size === 'sm' ? null : (
            <span className="bn-thumb-none" aria-hidden="true">
              No photo
            </span>
          )}
        </>
      ) : (
        <img
          className={style === undefined ? 'bn-thumb-img' : 'bn-thumb-img bn-crop'}
          data-cropped={style === undefined ? undefined : 'true'}
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          style={style}
          onError={() => setFailed(src)}
        />
      )}
    </span>
  )
}

/* ============================================================================================
 * BoxLabel and the box order.
 * ============================================================================================ */

/** A box as every screen names it: its NAME first, then `Box 3` (D132). A box with no name is
 *  `Box 3` alone. The number is Inter, not mono: it is a label, not a machine string. */
export function BoxLabel({
  box,
  name,
  className,
}: {
  readonly box: number
  readonly name?: string | null
  readonly className?: string
}) {
  const named = typeof name === 'string' && name.trim() !== ''
  return (
    <span className={['bn-boxlabel', className].filter(Boolean).join(' ')}>
      {named ? (
        <>
          <span className="bn-boxlabel-name">{name}</span>
          <Sep />
          <span className="bn-boxlabel-number">{`Box ${box}`}</span>
        </>
      ) : (
        <span className="bn-boxlabel-name">{`Box ${box}`}</span>
      )}
    </span>
  )
}

/** When this browser last reached for each box, by box number (`deviceMemory.ts`). */
export type BoxRecency = ReadonlyMap<number, string>

/** A list of boxes, MOST RECENT FIRST (the owner's ruling, 2026-09-23, for every list of boxes).
 *
 *  THREE TERMS. The box this browser reached for last leads. A box it never reached for sorts
 *  after every box it has, NEWEST BOX FIRST by its true index `bid` (D145), which only grows as
 *  boxes are made. The box number breaks what is left. Returns a new array. */
export function boxesMostRecentFirst<T extends { readonly box: number; readonly bid?: number | null }>(
  boxes: readonly T[],
  recency: BoxRecency = storedBoxRecency(),
): T[] {
  return [...boxes].sort((left, right) => {
    const ra = recency.get(left.box) ?? ''
    const rb = recency.get(right.box) ?? ''
    if (ra !== rb) return ra > rb ? -1 : 1
    const ba = left.bid ?? -1
    const bb = right.bid ?? -1
    if (ba !== bb) return bb - ba
    return left.box - right.box
  })
}

/* ============================================================================================
 * Location — where a card is.
 * ============================================================================================ */

/** Where a card is, as the server's place label says it, drawn by `PositionLabel`. The card
 *  number in that label counts WITHIN THE SECTION (the owner's ruling, 2026-09-23;
 *  `pipeline/join.py:Position.card`). Give `place` and the box and section names come with it. */
export function Location({
  place,
  label,
  boxName,
  sectionName,
  flow,
  lead,
  fallback = 'No place on record',
  className,
}: {
  readonly place?: Place | null
  /** The server's label, when there is no `place` block to hand over. */
  readonly label?: string | null
  readonly boxName?: string | null
  readonly sectionName?: string | null
  readonly flow?: 'stack' | 'run'
  readonly lead?: 'path' | 'slot'
  /** What is drawn where there is no label: a card kept as a count, or one not placed yet. */
  readonly fallback?: ReactNode
  readonly className?: string
}) {
  const text = place?.label ?? label ?? null
  const usable = typeof text === 'string' && text.trim() !== ''
  return (
    <span className={['bn-location', className].filter(Boolean).join(' ')}>
      {usable ? (
        <PositionLabel
          label={text}
          flow={flow}
          lead={lead}
          boxName={place?.box_name ?? boxName ?? null}
          sectionName={place?.section_name ?? sectionName ?? null}
        />
      ) : (
        <span className="bn-location-none">{fallback}</span>
      )}
    </span>
  )
}

/* ============================================================================================
 * The pick list: Select, FilterChips and SortControl draw from this one panel.
 *
 * CAPTURE'S OPTION ROWS, LIFTED (the owner, 2026-09-23: its picker is "pretty decent"): a check
 * mark, the name, and a figure on the right. A long list gets Capture's type-to-narrow entry at
 * its top. The panel is the kit's own and never the native OS menu (the owner's ruling).
 *
 * FIXED, IN A PORTAL, so no scrolling or clipping parent can cut it, and it covers the page
 * rather than pushing it: opening a list never moves what is under it (D118).
 * ============================================================================================ */

/** One choice in a pick list. */
export type PickOption<T extends string = string> = {
  readonly value: T
  readonly label: ReactNode
  /** What the type-to-narrow entry matches. Defaults to `label` when that is a string. */
  readonly text?: string
  /** How many rows this choice would show, under the other active filters. */
  readonly count?: number
}

/** A list longer than this gets the type-to-narrow entry. */
const NARROW_FROM = 8

function optionText<T extends string>(option: PickOption<T>): string {
  if (option.text !== undefined) return option.text
  return typeof option.label === 'string' ? option.label : option.value
}

type PanelPlace = { readonly top: number; readonly left: number; readonly width: number; readonly maxHeight: number }

const GUTTER = 16
const PANEL_MIN_W = 224
const PANEL_MAX_H = 360

/** Where the panel goes: under its trigger, or above when there is more room there, never past
 *  the viewport's 16px gutter. */
function placePanel(anchor: HTMLElement): PanelPlace {
  const rect = anchor.getBoundingClientRect()
  const vw = document.documentElement.clientWidth
  const vh = window.innerHeight
  const width = Math.min(Math.max(rect.width, PANEL_MIN_W), vw - GUTTER * 2)
  const left = Math.min(Math.max(rect.left, GUTTER), vw - GUTTER - width)
  const below = vh - rect.bottom - GUTTER
  const above = rect.top - GUTTER
  const down = below >= Math.min(PANEL_MAX_H, 200) || below >= above
  const room = Math.max(120, (down ? below : above) - 4)
  const maxHeight = Math.min(PANEL_MAX_H, room)
  return { top: down ? rect.bottom + 4 : rect.top - 4 - maxHeight, left, width, maxHeight }
}

function useAnchoredPlace(open: boolean, anchor: RefObject<HTMLElement | null>): PanelPlace | null {
  const [place, setPlace] = useState<PanelPlace | null>(null)
  useLayoutEffect(() => {
    if (!open) {
      setPlace(null)
      return
    }
    const update = () => {
      if (anchor.current !== null) setPlace(placePanel(anchor.current))
    }
    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [open, anchor])
  return place
}

function PickPanel<T extends string>({
  id,
  label,
  options,
  selected,
  multiple,
  anchor,
  onPick,
  onClose,
  onClear,
}: {
  readonly id: string
  readonly label: string
  readonly options: readonly PickOption<T>[]
  readonly selected: ReadonlySet<T>
  readonly multiple: boolean
  readonly anchor: RefObject<HTMLElement | null>
  readonly onPick: (value: T) => void
  /** `true` hands focus back to the trigger. */
  readonly onClose: (returnFocus: boolean) => void
  readonly onClear?: () => void
}) {
  const place = useAnchoredPlace(true, anchor)
  const panel = useRef<HTMLDivElement | null>(null)
  const list = useRef<HTMLDivElement | null>(null)
  const entry = useRef<HTMLInputElement | null>(null)
  const [narrow, setNarrow] = useState('')
  const searchable = options.length >= NARROW_FROM

  const shown = useMemo(() => {
    const needle = narrow.trim().toLowerCase()
    if (needle === '') return options
    return options.filter((option) => optionText(option).toLowerCase().includes(needle))
  }, [options, narrow])

  const firstSelected = shown.findIndex((option) => selected.has(option.value))
  const [active, setActive] = useState(firstSelected === -1 ? 0 : firstSelected)
  const activeAt = shown.length === 0 ? -1 : Math.min(active, shown.length - 1)

  /* Focus lands inside on open: the entry when the list is long, the list itself otherwise. */
  useEffect(() => {
    if (searchable) entry.current?.focus()
    else list.current?.focus()
  }, [searchable])

  /* The active row stays in view as the arrows move it. */
  useEffect(() => {
    if (activeAt < 0) return
    document.getElementById(`${id}-opt-${activeAt}`)?.scrollIntoView({ block: 'nearest' })
  }, [id, activeAt])

  /* A press anywhere outside the panel and its trigger closes it, and leaves focus where the
   * press put it. */
  useEffect(() => {
    const onDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      if (target === null) return
      if (panel.current?.contains(target) || anchor.current?.contains(target)) return
      onClose(false)
    }
    document.addEventListener('pointerdown', onDown, true)
    return () => document.removeEventListener('pointerdown', onDown, true)
  }, [anchor, onClose])

  const onKey = (event: ReactKeyboardEvent) => {
    const last = shown.length - 1
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setActive(activeAt >= last ? 0 : activeAt + 1)
        return
      case 'ArrowUp':
        event.preventDefault()
        setActive(activeAt <= 0 ? last : activeAt - 1)
        return
      case 'Home':
        if (event.target === entry.current) return
        event.preventDefault()
        setActive(0)
        return
      case 'End':
        if (event.target === entry.current) return
        event.preventDefault()
        setActive(last)
        return
      case 'Enter': {
        event.preventDefault()
        const option = shown[activeAt]
        if (option !== undefined) onPick(option.value)
        return
      }
      case ' ': {
        if (event.target === entry.current) return
        event.preventDefault()
        const option = shown[activeAt]
        if (option !== undefined) onPick(option.value)
        return
      }
      case 'Escape':
        event.preventDefault()
        event.stopPropagation()
        onClose(true)
        return
      case 'Tab':
        onClose(false)
        return
      default:
    }
  }

  if (place === null) return null

  const style: CSSProperties = { top: place.top, left: place.left, width: place.width, maxHeight: place.maxHeight }
  const activeId = activeAt >= 0 ? `${id}-opt-${activeAt}` : undefined

  return createPortal(
    <div ref={panel} className="bn-pick-panel" style={style} onKeyDown={onKey} data-bn-pick-panel>
      {searchable ? (
        <div className="bn-pick-entry">
          <Icon name="search" size={14} />
          <input
            ref={entry}
            className="bn-pick-entry-input"
            type="text"
            value={narrow}
            placeholder="Type to narrow"
            aria-label={`Narrow ${label}`}
            aria-controls={`${id}-list`}
            aria-activedescendant={activeId}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setNarrow(event.target.value)
              setActive(0)
            }}
          />
        </div>
      ) : null}
      <div
        ref={list}
        id={`${id}-list`}
        className="bn-pick-list"
        role="listbox"
        aria-label={label}
        aria-multiselectable={multiple ? true : undefined}
        aria-activedescendant={searchable ? undefined : activeId}
        tabIndex={searchable ? -1 : 0}
      >
        {shown.map((option, at) => {
          const on = selected.has(option.value)
          return (
            <div
              key={option.value}
              id={`${id}-opt-${at}`}
              className="bn-pick-opt"
              role="option"
              aria-selected={on}
              data-active={at === activeAt ? 'true' : undefined}
              data-zero={option.count === 0 ? 'true' : undefined}
              data-multiple={multiple ? 'true' : undefined}
              onPointerDown={(event) => event.preventDefault()}
              onPointerMove={() => {
                if (at !== activeAt) setActive(at)
              }}
              onClick={() => onPick(option.value)}
            >
              <span className="bn-pick-mark" aria-hidden="true">
                <Icon name="check" size={11} strokeWidth={3} />
              </span>
              <span className="bn-pick-name">{option.label}</span>
              {option.count === undefined ? null : <span className="bn-pick-count">{countText(option.count)}</span>}
            </div>
          )
        })}
        {shown.length === 0 ? <p className="bn-pick-empty">Nothing matches that.</p> : null}
      </div>
      {onClear !== undefined && selected.size > 0 ? (
        <div className="bn-pick-foot">
          <button type="button" className="bn-pick-clear" onClick={onClear}>
            Clear
          </button>
        </div>
      ) : null}
    </div>,
    document.body,
  )
}

/** Open and close a pick list, with focus handed back to the trigger on Escape and on a pick. */
function usePick(): {
  readonly open: boolean
  readonly toggle: () => void
  readonly close: (returnFocus: boolean) => void
  readonly trigger: RefObject<HTMLButtonElement | null>
} {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement | null>(null)
  const close = useCallback((returnFocus: boolean) => {
    setOpen(false)
    if (returnFocus) trigger.current?.focus()
  }, [])
  const toggle = useCallback(() => setOpen((was) => !was), [])
  return { open, toggle, close, trigger }
}

/** The trigger every pick list shares: the label, the current value, a chevron. */
function PickTrigger({
  id,
  triggerRef,
  open,
  label,
  value,
  icon,
  active,
  onToggle,
  onKeyDown,
  className,
}: {
  readonly id: string
  readonly triggerRef: RefObject<HTMLButtonElement | null>
  readonly open: boolean
  readonly label: string
  readonly value: ReactNode
  readonly icon?: IconName
  readonly active: boolean
  readonly onToggle: () => void
  readonly onKeyDown?: (event: ReactKeyboardEvent<HTMLButtonElement>) => void
  readonly className?: string
}) {
  return (
    <button
      ref={triggerRef}
      type="button"
      className={['bn-pick', className].filter(Boolean).join(' ')}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={open ? `${id}-list` : undefined}
      data-active={active ? 'true' : undefined}
      onClick={onToggle}
      onKeyDown={onKeyDown}
    >
      {icon === undefined ? null : <Icon name={icon} size={14} className="bn-pick-icon" />}
      <span className="bn-pick-label">{label}</span>
      {value === null ? null : <span className="bn-pick-value">{value}</span>}
      <Icon name={open ? 'chevronUp' : 'chevronDown'} size={14} className="bn-pick-chev" />
    </button>
  )
}

/** Arrow keys on a closed trigger open its list, as a native select does. */
function openOnArrow(open: boolean, toggle: () => void) {
  return (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (open) return
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    toggle()
  }
}

/** Pick one of a list. The kit's own panel, never the native OS menu (the owner's ruling,
 *  2026-09-23). The trigger says what it is (`label`) and what is picked. */
export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
  placeholder = 'Any',
  icon,
  className,
}: {
  readonly label: string
  /** Null when nothing is picked; the trigger then shows `placeholder`. */
  readonly value: T | null
  readonly options: readonly PickOption<T>[]
  readonly onChange: (next: T) => void
  readonly placeholder?: string
  readonly icon?: IconName
  readonly className?: string
}) {
  const id = useId().replace(/:/g, '')
  const pick = usePick()
  const current = options.find((option) => option.value === value)
  const selected = useMemo(() => new Set(value === null ? [] : [value]), [value])
  return (
    <>
      <PickTrigger
        id={id}
        triggerRef={pick.trigger}
        open={pick.open}
        label={label}
        value={current === undefined ? <span className="bn-pick-placeholder">{placeholder}</span> : current.label}
        icon={icon}
        active={false}
        onToggle={pick.toggle}
        onKeyDown={openOnArrow(pick.open, pick.toggle)}
        className={className}
      />
      {pick.open ? (
        <PickPanel
          id={id}
          label={label}
          options={options}
          selected={selected}
          multiple={false}
          anchor={pick.trigger}
          onPick={(next) => {
            onChange(next)
            pick.close(true)
          }}
          onClose={pick.close}
        />
      ) : null}
    </>
  )
}

/** One facet of a filter bar: its name, its choices, and whether several may be picked. */
export type FilterFacet<T extends string = string> = {
  readonly key: string
  readonly label: string
  readonly options: readonly PickOption<T>[]
  /** Several at once (the default), or one. */
  readonly multiple?: boolean
  readonly icon?: IconName
}

/** What every facet has picked, by facet key. A facet with nothing picked may be absent. */
export type FilterValue = Readonly<Record<string, readonly string[]>>

/** The words for what a facet has picked: `Pokémon`, or `Pokémon +2`. */
function pickedWords(facet: FilterFacet, picked: readonly string[]): ReactNode {
  const first = facet.options.find((option) => option.value === picked[0])
  const head = first === undefined ? (picked[0] ?? '') : first.label
  return picked.length <= 1 ? head : (
    <>
      {head}
      <span className="bn-fchip-more">{` +${picked.length - 1}`}</span>
    </>
  )
}

function FacetChip({
  facet,
  picked,
  onChange,
}: {
  readonly facet: FilterFacet
  readonly picked: readonly string[]
  readonly onChange: (next: readonly string[]) => void
}) {
  const id = useId().replace(/:/g, '')
  const pick = usePick()
  const multiple = facet.multiple !== false
  const selected = useMemo(() => new Set(picked), [picked])
  const active = picked.length > 0
  return (
    <span className="bn-fchip" data-active={active ? 'true' : undefined}>
      <PickTrigger
        id={id}
        triggerRef={pick.trigger}
        open={pick.open}
        label={facet.label}
        value={active ? pickedWords(facet, picked) : null}
        icon={facet.icon}
        active={active}
        onToggle={pick.toggle}
        onKeyDown={openOnArrow(pick.open, pick.toggle)}
      />
      {active ? (
        <button
          type="button"
          className="bn-fchip-clear"
          aria-label={`Clear ${facet.label}`}
          onClick={() => {
            onChange([])
            pick.trigger.current?.focus()
          }}
        >
          <Icon name="x" size={12} />
        </button>
      ) : null}
      {pick.open ? (
        <PickPanel
          id={id}
          label={facet.label}
          options={facet.options}
          selected={selected}
          multiple={multiple}
          anchor={pick.trigger}
          onPick={(value) => {
            if (!multiple) {
              onChange(selected.has(value) ? [] : [value])
              pick.close(true)
              return
            }
            /* The order the owner picked in is kept: the first pick names the chip. */
            onChange(selected.has(value) ? picked.filter((one) => one !== value) : [...picked, value])
          }}
          onClose={pick.close}
          onClear={() => onChange([])}
        />
      ) : null}
    </span>
  )
}

/** A filter bar: one chip per facet. EVERY FACET WORKS IN ANY ORDER AND COMBINES WITH THE
 *  OTHERS — no facet waits on another (the owner's ruling, 2026-09-23, against Inventory's forced
 *  game, then set, then rarity). The caller gives each option the count it would show under the
 *  OTHER active facets, and a choice with none is drawn faint but still offered. */
export function FilterChips({
  facets,
  value,
  onChange,
  label = 'Filters',
  className,
}: {
  readonly facets: readonly FilterFacet[]
  readonly value: FilterValue
  readonly onChange: (next: FilterValue) => void
  readonly label?: string
  readonly className?: string
}) {
  const activeCount = facets.filter((facet) => (value[facet.key] ?? []).length > 0).length
  return (
    <div className={['bn-filterchips', className].filter(Boolean).join(' ')} role="group" aria-label={label}>
      {facets.map((facet) => (
        <FacetChip
          key={facet.key}
          facet={facet}
          picked={value[facet.key] ?? []}
          onChange={(next) => onChange({ ...value, [facet.key]: next })}
        />
      ))}
      {activeCount >= 2 ? (
        <button type="button" className="bn-filterchips-clear" onClick={() => onChange({})}>
          Clear all
        </button>
      ) : null}
    </div>
  )
}

/** The words a sort direction is said in, per key: a price reads `High to low`, a name `Z to A`. */
export type SortOption<K extends string = string> = {
  readonly key: K
  readonly label: string
  /** What ascending means for this key. Default `Low to high`. */
  readonly asc?: string
  /** What descending means for this key. Default `High to low`. */
  readonly desc?: string
  /** The direction a first pick of this key starts in. Default `desc`. */
  readonly first?: 'asc' | 'desc'
}

export type SortValue<K extends string = string> = { readonly key: K; readonly dir: 'asc' | 'desc' }

/** How a list is ordered: WHAT it is sorted by, and WHICH WAY, both in words on the control, so
 *  the current order is never hidden in an icon (the filtering review, FLT-19). */
export function SortControl<K extends string>({
  options,
  value,
  onChange,
  label = 'Sort',
  className,
}: {
  readonly options: readonly SortOption<K>[]
  readonly value: SortValue<K>
  readonly onChange: (next: SortValue<K>) => void
  readonly label?: string
  readonly className?: string
}) {
  const current = options.find((option) => option.key === value.key)
  const asc = current?.asc ?? 'Low to high'
  const desc = current?.desc ?? 'High to low'
  return (
    <span className={['bn-sort', className].filter(Boolean).join(' ')}>
      <Select
        label={label}
        value={value.key}
        options={options.map((option) => ({ value: option.key, label: option.label }))}
        onChange={(key) => {
          if (key === value.key) return
          const next = options.find((option) => option.key === key)
          onChange({ key, dir: next?.first ?? 'desc' })
        }}
      />
      <button
        type="button"
        className="bn-sort-dir"
        aria-label={`Order: ${value.dir === 'asc' ? asc : desc}. Press to reverse.`}
        onClick={() => onChange({ key: value.key, dir: value.dir === 'asc' ? 'desc' : 'asc' })}
      >
        <span className="bn-sort-dir-words" aria-hidden="true">
          {value.dir === 'asc' ? asc : desc}
        </span>
      </button>
    </span>
  )
}
