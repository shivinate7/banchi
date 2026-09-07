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
 * other one and it holds the remembered camera and the photo rotation. Adding a device-local
 * key means adding it here, where the argument is, in front of whoever is reviewing the diff.
 *
 * THIS COMMENT CLAIMED THOSE TWO FILES HELD EVERY `localStorage` CALL IN THE APP, and that
 * stopped being true on 2026-09-03. `Orders.tsx` holds a key — `banchi.orders.last-check`,
 * when THIS device last checked TCGplayer — at two call sites carrying an inline disable that
 * argues for it, which the owner ruled on. So the shape is two exempt FILES plus one argued
 * call site, and the roster lives in `CLAUDE.md` where `make docs-audit`'s `storage keys` row
 * reconciles it against this directory in both directions. A comment that counts is a comment
 * that goes stale; the count is checked there, and this one deliberately does not make it.
 *
 * THE ORDER FETCH FILTER (D113) CAME HERE RATHER THAN TO ITS CALL SITE, which is the shape
 * the lint rule's own message asks for and the opposite of what `last-check` did. That key
 * predates this argument being written down; a new one goes where the reviewer is already
 * looking.
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

/* ------------------------------------------------------------------ the order fetch filter */

/**
 * HOW THIS DEVICE NARROWS ITS ORDER FETCH, and why that is a fact about the machine.
 *
 * D91 made `POST /orders/fetch` refuse a call that names no statuses, on an argument
 * `server/order_transport.py` makes at length: TCGplayer never published the status
 * vocabulary, so a guess that drops an order is an envelope that never ships. The owner then
 * ruled out D91's two-press flow, and `Orders.tsx` answered the requirement by echoing back
 * every status the free preview returned — nothing dropped, and nothing narrowed either. This
 * key is the operator's own answer in place of that echo (D113).
 *
 * IT IS A HABIT, NOT A RECORD. "I do not want to look at completed orders" is a statement
 * about how the person at this screen works, the same kind of fact as the remembered camera
 * and the theme; it names no order, no card, no position and no SKU, and losing it costs one
 * press of a control that is on screen. The ledger stays the one truth about what is on the
 * store, which is the whole of what D13's ban protects.
 *
 * ONE KEY FOR BOTH TOGGLES, BECAUSE THEY ARE ONE FACT. `statuses` is which of the window's
 * orders are worth a detail call; `skipKnown` is whether the ones the ledger already holds at
 * that status are worth asking about again. Both answer "what should this press bother with",
 * both are ticked in the same panel, and splitting them would put two rows in `CLAUDE.md`'s
 * roster for one habit.
 *
 * THE STRINGS ARE THE WIRE'S OWN, KEPT VERBATIM. What is written here is exactly what the
 * preview answered, never folded and never mapped, because that is the one comparison the
 * transport does — `status.strip() in wanted` — and a fold on this side would be the first
 * step toward the vocabulary that module refuses to have. A remembered string that a later
 * window does not return is therefore a real possibility, and the screen SAYS SO rather than
 * quietly dropping it.
 *
 * NULL IS NOT AN EMPTY LIST, AND IT IS NOT "UNANSWERED" EITHER — that is what `asked` is for.
 * `statuses: null` means "every status this window holds", which stays the value a confirmed
 * device usually carries: a stored LIST would silently drop a status TCGplayer adds next month,
 * which is the exact drop D91 exists to prevent. An empty list means they ticked everything off,
 * and the screen refuses the press rather than sending a body the wire rejects with a code the
 * operator cannot act on.
 *
 * `asked` IS WHETHER A HUMAN HAS SEEN THE LIST, AND THE FIRST PRESS WAITS FOR IT. The owner
 * decided this on 2026-09-06 against a measurement: 69 of the 83 open orders on their store are
 * ones TCGplayer had already shipped, those orders hold 31 physical copies, and three
 * Ready-to-Ship lines read `short` while the cards sat in boxes — because `resolve_all` serves
 * oldest-first out of one pool and a delivered order is older than a live one. A default of
 * "everything" reproduces that on every device where nobody opens the control.
 *
 * THE ALTERNATIVE WAS A CODED DEFAULT AND IT IS NOT AVAILABLE. "Everything except the shipped
 * ones" needs this file to know that `Shipped - In Transit` means shipped, which is the
 * vocabulary `server/order_transport.py` refuses to have and which would swallow a `Refunded`
 * TCGplayer adds later. So a human is asked, once, in front of the real list — and never again.
 * This is NOT D91's two-press flow, which the owner ruled out: that asked on every press.
 */
const ORDER_FILTER_KEY = 'banchi.orders.fetch-filter'

/** What this device narrows the order fetch to. `statuses: null` is every status the window
 *  holds; `asked` is whether a human has ever been shown that list. */
export type OrderFetchFilter = {
  readonly statuses: readonly string[] | null
  readonly skipKnown: boolean
  readonly asked: boolean
}

/** A device that has never been asked. Every status, nothing skipped — and the first press
 *  stops to show the list rather than acting on this. */
const UNASKED: OrderFetchFilter = { statuses: null, skipKnown: false, asked: false }

export function storedOrderFilter(): OrderFetchFilter {
  try {
    const raw = localStorage.getItem(ORDER_FILTER_KEY)
    if (raw === null) return UNASKED
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return UNASKED
    const list = (parsed as { statuses?: unknown }).statuses
    /* Deduped and stripped on the way out, so a hand-edited value cannot make the fetch body
       something the wire refuses for a reason the operator cannot see. */
    const statuses = Array.isArray(list)
      ? [...new Set(list.filter((one): one is string => typeof one === 'string').map((one) => one.trim()))].filter(
          (one) => one !== '',
        )
      : null
    return {
      statuses,
      skipKnown: (parsed as { skipKnown?: unknown }).skipKnown === true,
      asked: (parsed as { asked?: unknown }).asked === true,
    }
  } catch {
    /* Private mode, blocked storage, or a half-written value. UNASKED, which means the press
       stops and shows the list — the safe direction, because the unsafe one imports orders that
       were delivered a month ago and lets them hold copies a live order needs. A browser that
       refuses storage asks every time, which is the honest consequence of refusing storage. */
    return UNASKED
  }
}

export function rememberOrderFilter(filter: OrderFetchFilter): void {
  try {
    localStorage.setItem(
      ORDER_FILTER_KEY,
      JSON.stringify({
        statuses: filter.statuses === null ? null : [...filter.statuses],
        skipKnown: filter.skipKnown,
        asked: filter.asked,
      }),
    )
  } catch {
    /* Quota or a blocked origin. The choice still holds for this tab; only the next visit is
       asked again. */
  }
}
