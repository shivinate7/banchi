import { useEffect, useId, useRef, useState } from 'react'

import type { Persona } from './PositionBar'
import './SearchField.css'

/* The one input in the search-and-sell flow: type a card's name, get every copy of it.
 *
 * A CONTROLLED INPUT THAT REPORTS EVERY KEYSTROKE, AND THE TIMER IS NOT HERE BY DEFAULT. This
 * is the one place this component departs from how it was specified, so it is argued rather
 * than left to be discovered: the debounce lives in `useSearch.ts`, beside the request it
 * protects, because a timer in both files is 400ms of a person waiting for a screen and
 * neither file owns the number. `useSearch` already holds the two other rules about when to
 * ask — an empty query asks nothing, and a slow answer to an old keystroke is discarded — and
 * splitting "when do we ask the server" across two modules is how those three rules stop
 * agreeing.
 *
 * `debounceMs` IS STILL HERE AND DEFAULTS TO 0, for the caller who wires this to something
 * that is not `useSearch`. Pass a delay there and this holds the typed text locally while the
 * timer runs, so what is on screen is always what was typed — a field that lags its own
 * keystrokes is the one thing a debounce must never buy.
 *
 * THE `/` HOTKEY IS OWNER-SIDE AND THE ABSENCE OF IT IS FULFILLER-SIDE, both deliberate.
 * docs/DESIGN.md: "Every choice shows its key" because an owner-side hour is a keyboard and
 * not a mouse — and, one sentence later, "The Fulfiller's screens are touch and show none."
 * That is not only about drawing the chip. A global key listener that steals `/` on a screen
 * whose user has no keyboard is invisible surface with no upside, so his skin registers none.
 */

/** Where the caret goes when the owner presses this. A single character, and the same one the
 *  chip draws — one constant so the hint and the handler cannot drift into describing
 *  different keys. */
const HOTKEY = '/'

/** What the field is called, per persona. His is an instruction and the owner's is a name:
 *  docs/DESIGN.md's copy rules put the pipeline's register on the owner's screens and plain
 *  sentences on his, and "Search" is a word about a tool rather than about a card. */
const LABEL: Record<Persona, string> = {
  owner: 'Search cards',
  fulfiller: 'Type the name of the card',
}

export type SearchFieldProps = {
  value: string
  onChange: (next: string) => void

  /** Required, not defaulted — see `CardLocations.tsx` for the same argument. A skin you get
   *  by forgetting is a skin nobody chose. */
  persona: Persona

  /** Focus on mount. The owner's search screen wants it; a field that grabs focus on the
   *  Fulfiller's device pops a software keyboard over the first thing he was going to read, so
   *  his caller should leave it off. Left as the caller's decision rather than derived from
   *  `persona`, because that is a screen's judgement and not a property of the persona. */
  autoFocus?: boolean

  placeholder?: string

  /** Off by default. See the header: the debounce belongs beside the request, and `useSearch`
   *  holds it. This exists for a caller who has no such hook behind it. */
  debounceMs?: number
}

export function SearchField({
  value,
  onChange,
  persona,
  autoFocus,
  placeholder = 'Card name',
  debounceMs = 0,
}: SearchFieldProps) {
  const id = useId()
  const input = useRef<HTMLInputElement | null>(null)
  const timer = useRef<number | null>(null)

  /* What is on screen. Equal to `value` in the default pass-through case and ahead of it while
   * a debounce is running — which is the whole reason it exists. */
  const [draft, setDraft] = useState(value)

  /* The last text this component sent up. It is what tells a `value` the parent changed on its
   * own — a cleared search, a query restored from a URL — apart from the echo of our own
   * `onChange` coming back one render later. Without it, an echo arriving mid-debounce would
   * reset the draft and delete a character the person had already typed. */
  const sent = useRef(value)

  /* `onChange` through a ref so a debounced commit calls the CURRENT handler rather than the
   * one captured in the render where the key was pressed. 200ms is long enough for a parent to
   * re-render with a new closure, and a stale one writes into a state setter nobody is reading
   * any more — a class of bug that presents as "the first search after switching cards does
   * nothing". */
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
      /* A modified `/` is somebody else's shortcut — the browser's Find, an OS binding — and
       * stealing it is how a hotkey becomes the thing people ask you to remove. */
      if (event.metaKey || event.ctrlKey || event.altKey) return

      /* Typing `/` inside any other field is typing a slash. Without this the hotkey makes it
       * impossible to put a slash in a collector number anywhere else on the screen, which is
       * the character that separates one from its printed total. */
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
      /* Selected rather than appended to. Pressing the hotkey means "search for something", and
       * the something is almost never the previous query plus a slash. */
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
      {/* A real <label> in both skins, hidden visually on the owner's rather than replaced by
          an aria-label. Two mechanisms for one job is one that can be deleted without the other
          noticing, and a hidden label still reaches a screen reader, still grows the click
          target, and still shows up in the accessibility tree the way the visible one does. */}
      <label className="search-field-label" htmlFor={id}>
        {LABEL[persona]}
      </label>

      <div className="search-field-box">
        <input
          className="search-field-input"
          id={id}
          ref={input}
          type="search"
          /* Off on all four: a card name is not a word, an address or a sentence, and a browser
             correcting `Eiscue` to `Escue` mid-search is a wrong answer the person has to
             notice to undo. */
          /* ESC HANDS FOCUS BACK, AND THE QUERY SURVIVES. Reported from the rig: the
             leader chord lands focus here (autoFocus doing its job), and there was no way
             out but a click — an input does not blur itself on Escape, so every keyboard
             route into this field was a one-way door. Blurring is the whole fix: focus
             returns to the document and every hotkey the field was swallowing works again.

             `preventDefault` matters as much as the blur. On a `type="search"` input,
             Chrome's NATIVE Escape clears the text — silently, keeping focus — so without
             it the first Esc eats the query the person typed and gives back nothing. The
             query is the screen's state, not the field's; leaving the field should no more
             erase it than scrolling away would. Emptying the box stays one keystroke
             (select-all, delete) and clearing-on-Esc was considered and declined: the
             filtered list is what the person is about to act ON, and vanishing it as a
             side effect of putting the keyboard down is the mis-tap this app keeps
             designing out of other screens. */
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

        {/* Owner-side only, and absent rather than hidden on his. docs/DESIGN.md: his screens
            are touch and show no keys. */}
        {persona === 'owner' ? <kbd className="search-field-key">{HOTKEY}</kbd> : null}
      </div>
    </div>
  )
}
