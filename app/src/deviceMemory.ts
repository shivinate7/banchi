/**
 * WHAT THIS BROWSER REMEMBERS ABOUT ITSELF — the whole of it, in one file.
 *
 * D27 permits `localStorage` for facts about THIS MACHINE and nothing else, and CLAUDE.md's
 * ban is about the other thing entirely: nothing about a card, a position or the inventory
 * goes in browser storage, because D13 puts that one truth on the Mac so two devices cannot
 * disagree about where a card is. Neither rule has moved. What moved is that Banchi's shell
 * has preferences of its own, and they are the same KIND of fact `useCamera.ts` already
 * stores — meaningless on the Fulfiller's laptop, wrong if shared, and about no card.
 *
 * THE THEME IS THE CLEAREST CASE. A person who chose dark chose it for the room they are
 * sitting in. Putting it on the server would make the owner's phone in the garage follow the
 * laptop in the office, and putting it in `sessionStorage` would ask them again every tab.
 * The rail's width is the same fact about the same screen.
 *
 * WHY THEY ARE IN THIS FILE RATHER THAN AT THEIR CALL SITES. `app/eslint.config.js` bans the
 * store rather than the key, because a selector cannot read a key passed as a const — so the
 * exception has to be a FILE, and a file the reviewer can read whole. `useCamera.ts` is the
 * other one and it holds the other two keys. Between them that is every `localStorage` call
 * in the app, and adding a third key means adding it here where the argument is, in front of
 * whoever is reviewing the diff.
 *
 * EVERY ACCESS IS WRAPPED. Private windows, cleared site data and browsers set to block
 * storage all throw on the accessor itself, and a preference is never worth a blank screen.
 */

const THEME_KEY = 'banchi.theme'
const RAIL_KEY = 'banchi.rail'

export type Theme = 'light' | 'dark'

/** The theme the operator CHOSE, or null where they have not — which is not the same as
 *  light. A null here is what lets the shell keep following the system. */
export function storedTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    return stored === 'light' || stored === 'dark' ? stored : null
  } catch {
    return null
  }
}

export function rememberTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    /* storage unavailable — the theme still applies for this session */
  }
}

/** Whether the nav is collapsed to the rail, or null where this browser has no opinion. */
export function storedRail(): boolean | null {
  try {
    const stored = localStorage.getItem(RAIL_KEY)
    if (stored === 'rail') return true
    if (stored === 'wide') return false
    return null
  } catch {
    return null
  }
}

export function rememberRail(rail: boolean): void {
  try {
    localStorage.setItem(RAIL_KEY, rail ? 'rail' : 'wide')
  } catch {
    /* storage unavailable — the rail still moves for this session */
  }
}
