import { useEffect, useId, useRef, useState } from 'react'

import type { Persona } from './position'
import { Icon } from './kit'
import './SearchField.css'

/* The one input in the search-and-sell flow: type a card's name, get every copy of it.
 *
 * A controlled input that reports every keystroke; the debounce lives beside the request in
 * `useSearch.ts`. `debounceMs` is here for a caller with no such hook behind it and defaults
 * to 0. The `/` hotkey is owner-side only: the Fulfiller's screens are touch and show no keys.
 */

/** Where the caret goes when the owner presses this. One constant, so the chip and the handler
 *  cannot drift into describing different keys. */
const HOTKEY = '/'

/** What the field is called, per persona. His is an instruction and the owner's is a name. */
const LABEL: Record<Persona, string> = {
  owner: 'Search cards',
  fulfiller: 'Type the name of the card',
}

export type SearchFieldProps = {
  value: string
  onChange: (next: string) => void

  /** Required, not defaulted. A skin you get by forgetting is a skin nobody chose. */
  persona: Persona

  /** Focus on mount. A screen's judgement rather than a property of the persona. */
  autoFocus?: boolean

  placeholder?: string

  /** Overrides the per-persona default below. A screen searching something other than
   *  cards — an order, a buyer — names its own field rather than inheriting "Search cards". */
  label?: string

  /** Off by default — see the header. */
  debounceMs?: number

  /** A search that runs on a PRESS rather than on every keystroke. When given, Enter in the
   *  field calls it, and so does the button `submitLabel` names. A press on an empty field
   *  calls nothing and says what to type instead (`emptyHint`): a press that does nothing and
   *  says nothing reads as broken (UX review, 2026-09-23). */
  onSubmit?: (text: string) => void

  /** The button beside the field, when `onSubmit` is given. No label, no button: Enter only. */
  submitLabel?: string

  /** What an empty press says. Defaults to the placeholder's own words. */
  emptyHint?: string

  /** `'lg'` (the default, `--bn-control-h-lg`) everywhere this field stands alone. `'bar'` is
   *  for a caller that sits this field beside OTHER controls sharing `--bn-control-h` — today
   *  only `kit/filters.tsx:FilterBar` (the owner's gripe 3, "the filters aren't even the same
   *  widths") — and takes that shorter height there ONLY: every other `SearchField` on the
   *  product is untouched. Below 767px, or on a coarse pointer, `--bn-control-h` itself is
   *  raised to 42px (`tokens.css`), so the 40px thumb floor still holds at any width narrower
   *  than that, `FilterBar`'s own 639px phone stack included. */
  controlHeight?: 'lg' | 'bar'

  /** True while what is on screen is not yet the answer to what is in the box (`useSearch`'s
   *  `loading`). The search mark turns into a spinner, in the same place, so the field keeps
   *  its size (D118). */
  busy?: boolean
}

export function SearchField({
  value,
  onChange,
  persona,
  autoFocus,
  placeholder = 'Card name, number or SKU',
  label,
  debounceMs = 0,
  onSubmit,
  submitLabel,
  emptyHint,
  controlHeight = 'lg',
  busy = false,
}: SearchFieldProps) {
  const id = useId()
  const hintId = useId()

  /* True from an empty press until the next keystroke. The hint is a reply to a press, so
   * typing is what takes it away. */
  const [askedEmpty, setAskedEmpty] = useState(false)
  const input = useRef<HTMLInputElement | null>(null)
  const timer = useRef<number | null>(null)

  /* What is on screen. Equal to `value` in the default pass-through case and ahead of it while
   * a debounce is running. */
  const [draft, setDraft] = useState(value)

  /* The last text this component sent up, so a `value` the parent changed on its own can be
   * told apart from the echo of our own `onChange`. */
  const sent = useRef(value)

  const latest = useRef(onChange)
  useEffect(() => {
    latest.current = onChange
  })

  useEffect(() => {
    if (value === sent.current) return
    sent.current = value
    setDraft(value)
  }, [value])

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  useEffect(() => {
    if (persona !== 'owner') return

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== HOTKEY) return
      /* A modified `/` is somebody else's shortcut. */
      if (event.metaKey || event.ctrlKey || event.altKey) return

      /* Typing `/` inside any other field is typing a slash. */
      const target = event.target
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT')
      ) {
        return
      }

      event.preventDefault()
      input.current?.focus()
      /* Selected rather than appended to: pressing the hotkey means "search for something". */
      input.current?.select()
    }

    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [persona])

  useEffect(() => {
    if (autoFocus) input.current?.focus()
  }, [autoFocus])

  const submit = () => {
    if (onSubmit === undefined) return
    const text = draft.trim()
    if (text === '') {
      setAskedEmpty(true)
      input.current?.focus()
      return
    }
    setAskedEmpty(false)
    /* A press is the moment the parent must hold what is in the box, debounce or not. */
    if (timer.current !== null) {
      window.clearTimeout(timer.current)
      timer.current = null
    }
    if (sent.current !== draft) {
      sent.current = draft
      latest.current(draft)
    }
    onSubmit(text)
  }

  const handle = (next: string) => {
    setDraft(next)
    if (askedEmpty && next.trim() !== '') setAskedEmpty(false)
    if (timer.current !== null) window.clearTimeout(timer.current)

    if (debounceMs <= 0) {
      sent.current = next
      latest.current(next)
      return
    }

    timer.current = window.setTimeout(() => {
      timer.current = null
      sent.current = next
      latest.current(next)
    }, debounceMs)
  }

  return (
    <div className={`search-field search-field-${persona}${controlHeight === 'bar' ? ' search-field-bar' : ''}`}>
      {/* A real <label> in both skins, hidden visually on the owner's rather than replaced by an
          aria-label. */}
      <label className="search-field-label" htmlFor={id}>
        {label ?? LABEL[persona]}
      </label>

      <div className="search-field-box" aria-busy={busy ? true : undefined} data-busy={busy ? 'true' : undefined}>
        {persona !== 'owner' ? null : busy ? (
          <span className="search-field-spin" aria-hidden="true" />
        ) : (
          <Icon name="search" size={16} className="search-field-icon" />
        )}
        <input
          className="search-field-input"
          id={id}
          ref={input}
          type="search"
          /* ESC hands focus back and the query survives: an input does not blur itself on
             Escape, and on a `type="search"` input Chrome's native Escape clears the text. */
          onKeyDown={(event) => {
            if (event.key === 'Enter' && onSubmit !== undefined) {
              event.preventDefault()
              submit()
              return
            }
            if (event.key !== 'Escape') return
            event.preventDefault()
            event.currentTarget.blur()
          }}
          aria-describedby={askedEmpty ? hintId : undefined}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          placeholder={placeholder}
          value={draft}
          onChange={(event) => handle(event.target.value)}
        />

        {persona === 'owner' && draft !== '' ? (
          <button
            type="button"
            className="search-field-clear"
            aria-label="Clear search"
            onClick={() => {
              handle('')
              input.current?.focus()
            }}
          >
            <Icon name="x" size={14} />
          </button>
        ) : null}

        {/* Owner-side only, and absent rather than hidden on his: his screens are touch and
            show no keys. */}
        {persona === 'owner' ? <kbd className="search-field-key">{HOTKEY}</kbd> : null}

        {onSubmit !== undefined && submitLabel !== undefined ? (
          <button type="button" className="search-field-submit" onClick={submit}>
            {submitLabel}
          </button>
        ) : null}
      </div>

      {/* Mounted always and filled only on an empty press, so the line it takes is reserved
          from the first paint and a press never moves what is below the field (D118). */}
      {onSubmit === undefined ? null : (
        <p className="search-field-hint" id={hintId} role="status" aria-live="polite">
          {askedEmpty ? (emptyHint ?? `Type a ${placeholder.charAt(0).toLowerCase()}${placeholder.slice(1)} first.`) : ''}
        </p>
      )}
    </div>
  )
}
