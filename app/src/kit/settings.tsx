import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'

import { Icon, type IconName } from './Icon'
import { Button, Notice, Segmented } from './index'
import { describeFailure, failureTone, type Failure } from '../server'

/* THE SETTINGS SHEET'S PARTS (D275, every screen inherits the scaffold; the owner: "Kit first").
 * Manage box was the first sheet built as rows of one-line settings that each open an editor, and
 * its parts lived in `BoxOps.tsx`. They are here so the next sheet is built from the same parts at
 * the same bar. Nothing in this file names a box: a screen passes labels, details and the write
 * it wants run, and keeps its own nouns. Screens import these from `./kit`, and the
 * `R2-class` row of `make kit-adoption` refuses a `bn-set-*` class outside the kit. */

/** `1 card`, `2 cards`. */
export function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** One write at a time, with its refusal handling and its re-read in one place. `write` runs the
 *  call and returns the answer, or null for a refusal, so a caller can close its own editor on
 *  success and leave it open on a refusal. `onChanged` is the screen's own re-read, called after a
 *  write that landed. The screen supplies what is written; this knows nothing of it. */
export function useSheetWrite(onChanged: () => void): {
  busy: boolean
  trouble: Failure | null
  write: <T>(run: () => Promise<T>) => Promise<T | null>
} {
  const [busy, setBusy] = useState(false)
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
export function SettingsTrouble({ failure }: { failure: Failure | null }) {
  if (failure === null) return null
  return <Notice tone={failureTone(failure)} title={failure.message} code={failure.code} />
}

/** One titled group of rows: a small head, an optional quieter note beside it, and the rows on one
 *  edge. `danger` reddens the head. The rows are `SettingsOp`s, or a component that draws one. */
export function SettingsGroup({
  title,
  note,
  danger = false,
  children,
}: {
  title: string
  /** A quieter line beside the title, about the group as a whole. */
  note?: string
  danger?: boolean
  children: ReactNode
}) {
  return (
    <section className={danger ? 'bn-set-group bn-set-group-danger' : 'bn-set-group'}>
      <h3 className="bn-label">
        {title}
        {note === undefined ? null : <span className="bn-set-group-note">{note}</span>}
      </h3>
      <div className="bn-set-ops">{children}</div>
    </section>
  )
}

/** The overview group: a head over a grid of `SettingsCensus` figures. */
export function SettingsFigures({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="bn-set-group">
      <h3 className="bn-label">{title}</h3>
      <dl className="bn-set-census">{children}</dl>
    </section>
  )
}

/**
 * One setting, drawn as a row in the sheet: an icon, what the press does, the value or quantity it
 * is about, and a chevron. The detail is inside the button so it is part of the accessible name
 * ("Rename, WB1 R4"); the explicit `aria-label` supplies the comma.
 */
export function SettingsOp({
  icon,
  label,
  detail,
  said,
  busy,
  danger = false,
  expanded,
  running,
  runningLabel = 'writing…',
  chevron = true,
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
  /** What the detail says while `running`. A screen whose write is not a "write" names its own. */
  runningLabel?: string
  /** A row that acts where it stands, rather than opening something, draws no chevron. */
  chevron?: boolean
  danger?: boolean
  expanded?: boolean
  onClick: () => void
}) {
  return (
    <button
      className={danger ? 'bn-set-op bn-set-op-danger' : 'bn-set-op'}
      type="button"
      aria-label={said ?? (detail === undefined ? label : `${label}, ${detail}`)}
      aria-expanded={expanded}
      aria-busy={running ? true : undefined}
      data-running={running ? 'true' : undefined}
      disabled={busy || disabled}
      onClick={onClick}
    >
      <span className="bn-set-op-icon">
        {running ? <span className="bn-set-op-spin" aria-hidden="true" /> : <Icon name={icon} size={16} />}
      </span>
      <span className="bn-set-op-label">{label}</span>
      {running ? (
        <span className="bn-set-op-detail">{runningLabel}</span>
      ) : detail === undefined ? null : (
        <span className="bn-set-op-detail">{detail}</span>
      )}
      {chevron ? <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={14} className="bn-set-op-chev" /> : null}
    </button>
  )
}

/** One figure in the overview grid: a label over a number. A null value draws a dash, never a
 *  zero. `note` is a quieter line under the figure and may wrap. Wrap the cells in
 *  `<dl className="bn-set-census">`. */
export function SettingsCensus({
  label,
  value,
  help,
  note,
}: {
  label: string
  value: number | null
  help?: string
  note?: ReactNode
}) {
  return (
    <div className="bn-set-census-cell" title={help}>
      <dt>{label}</dt>
      <dd>
        {value === null ? '—' : value.toLocaleString()}
        {note === undefined ? null : <span className="bn-set-census-note">{note}</span>}
      </dd>
    </div>
  )
}

/** The frame an opened setting draws in: a way back, a title, then the screen's own editor. */
export function SettingsEditor({
  title,
  onBack,
  children,
}: {
  title: string
  onBack: () => void
  children: ReactNode
}) {
  return (
    <div className="bn-set-editor">
      <button type="button" className="bn-set-back" onClick={onBack}>
        <Icon name="chevronLeft" size={14} /> All settings
      </button>
      <h3 className="bn-set-editor-title">{title}</h3>
      {children}
    </div>
  )
}

/** One group of pickable items, in the order they are drawn. `index` is the item's own stable
 *  number, which the picker hands back. */
export type PickGroup = {
  readonly key: string
  readonly title: string
  readonly cards: readonly { readonly index: number; readonly label: string; readonly departed?: boolean }[]
}

/* THE ITEMS A SETTING REACHES, PICKED BESIDE THE ACT (D314, picked inside the sheet; the list
 * carries no ticks). It opens on the whole set; "Some cards" starts with every item picked, so
 * narrowing is unpicking. A group's check is partial while some of its items are picked.
 * `picked` is null for all, or the list of picked indices. */
export function CardPicker({
  whole,
  sections,
  picked,
  onChange,
}: {
  /** What the unnarrowed choice is called: "Whole box". The screen says its own noun. */
  whole: string
  sections: readonly PickGroup[]
  picked: readonly number[] | null
  onChange: (next: readonly number[] | null) => void
}) {
  const all = sections.flatMap((section) => section.cards.map((card) => card.index))
  const held = new Set(picked ?? [])
  const set = (next: Set<number>) => onChange(all.filter((index) => next.has(index)))
  const toggle = (indices: readonly number[], on: boolean) => {
    const next = new Set(held)
    for (const index of indices) {
      if (on) next.add(index)
      else next.delete(index)
    }
    set(next)
  }
  return (
    <div className="bn-set-picker">
      <Segmented
        label="Cards to include"
        value={picked === null ? 'all' : 'some'}
        options={[
          { value: 'all', label: `${whole}, ${count(all.length, 'card', 'cards')}` },
          { value: 'some', label: 'Some cards' },
        ]}
        onChange={(next) => onChange(next === 'all' ? null : all)}
      />
      {picked === null ? null : (
        <>
          <div className="bn-set-picker-bar">
            <span className="bn-set-picker-count" aria-live="polite">
              {picked.length} of {all.length} picked
            </span>
            <Button size="sm" variant="quiet" onClick={() => onChange(all)}>
              All
            </Button>
            <Button size="sm" variant="quiet" onClick={() => onChange([])}>
              None
            </Button>
          </div>
          <ul className="bn-set-picker-list">
            {sections.map((section) => {
              const indices = section.cards.map((card) => card.index)
              const n = indices.filter((index) => held.has(index)).length
              return (
                <li key={section.key} className="bn-set-picker-group">
                  <label className="bn-check bn-set-picker-head">
                    <input
                      type="checkbox"
                      checked={n > 0 && n === indices.length}
                      ref={(node) => {
                        if (node !== null) node.indeterminate = n > 0 && n < indices.length
                      }}
                      aria-label={`All of ${section.title}`}
                      onChange={(event) => toggle(indices, event.target.checked)}
                    />
                    <span>{section.title}</span>
                  </label>
                  <ul>
                    {section.cards.map((card) => (
                      <li key={card.index}>
                        <label className="bn-check bn-set-picker-card">
                          <input
                            type="checkbox"
                            checked={held.has(card.index)}
                            onChange={(event) => toggle([card.index], event.target.checked)}
                          />
                          <span>{card.label}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
