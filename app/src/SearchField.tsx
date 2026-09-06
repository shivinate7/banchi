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

  /** Off by default — see the header. */
  debounceMs?: number
}

export function SearchField({
  value,
  onChange,
  persona,
  autoFocus,
  placeholder = 'Card name, number or SKU',
  debounceMs = 0,
}: SearchFieldProps) {
  const id = useId()
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

  const handle = (next: string) => {
    setDraft(next)
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
    <div className={`search-field search-field-${persona}`}>
      {/* A real <label> in both skins, hidden visually on the owner's rather than replaced by an
          aria-label. */}
      <label className="search-field-label" htmlFor={id}>
        {LABEL[persona]}
      </label>

      <div className="search-field-box">
        {persona === 'owner' ? <Icon name="search" size={16} className="search-field-icon" /> : null}
        <input
          className="search-field-input"
          id={id}
          ref={input}
          type="search"
          /* ESC hands focus back and the query survives: an input does not blur itself on
             Escape, and on a `type="search"` input Chrome's native Escape clears the text. */
          onKeyDown={(event) => {
            if (event.key !== 'Escape') return
            event.preventDefault()
            event.currentTarget.blur()
          }}
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
            aria-label="Clear the search"
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
      </div>
    </div>
  )
}
