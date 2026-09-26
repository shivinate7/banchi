import { Component, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import type { ComponentType, ErrorInfo, ReactNode } from 'react'
import { isEditableTarget } from './keys'
import { rememberRail, storedRail, storedTheme } from './deviceMemory'
import { getStatus, onServerBoot, onServerReachable } from './server'
import { useSearch } from './useSearch'
import { usePoll } from './usePoll'
import { Button, Icon, IconButton, Kbd, KeyHint, Lockup, Modal, Page, PageRouteContext, Sheet, SheetHost,
  applyTheme, openSheet, overlayOpen, readTheme, type IconName, type Theme } from './kit'
import { BLOCK, PARAMS, ROMAN_TRACK_SOLVED } from './kit/lockupGeometry'
import { Toaster, toast } from './kit/toast'
import { SearchField } from './SearchField'

import { Home } from './Home'
import { CaptureScreen } from './CaptureScreen'
import { RunsRedirect } from './Runs'
import { ReviewQueue } from './ReviewQueue'
import { Inventory } from './Inventory'
import { Graveyard } from './Graveyard'
import { Pricing } from './Pricing'
import { Orders } from './Orders'
import { Shipping } from './Shipping'
import { Codes } from './Codes'
import { Revenue } from './Revenue'
import { ProductHistory } from './ProductHistory'
import { Fulfillment } from './Fulfillment'
import { Gallery } from './Gallery'
import './App.css'

/* ============================================================================
   BANCHI SHELL
   A sidebar that collapses to a rail, a phone app bar with a bottom tab bar, a ⌘K palette,
   a which-key overlay for the `,` leader, a server banner, an error boundary per route, a
   toast stack, and a document title per screen. The Fulfiller's screen gets none of it.
   ========================================================================== */

type Persona = 'owner' | 'fulfiller'
type Group = 'home' | 'work' | 'sell' | 'library' | 'aside'

/** One row of the keyboard sheet. */
type Binding = {
  /** One entry per alternative that does the same thing; a chord is one string (`⌘K`, `,C`). */
  readonly keys: readonly string[]
  readonly does: string
  /** The condition, when the key is armed by something narrower than the screen. One short line. */
  readonly when?: string
  /** Read the caps as a sequence rather than as alternatives. */
  readonly seq?: boolean
}

/** A screen's own keys, registered on its `ROUTES` row. `where` defaults to "Only while <label>
 *  is open." */
type ScreenKeys = {
  readonly where?: string
  readonly rows: readonly Binding[]
}

export type Route = {
  readonly path: string
  readonly label: string
  readonly title?: string
  readonly icon: IconName
  readonly view: ComponentType
  readonly persona: Persona
  readonly group: Group
  readonly hotkey?: string
  readonly nav?: boolean
  readonly tab?: boolean
  /** True only for a route whose view redirects elsewhere and renders nothing of its own
   *  (D291's `#/runs`). Read by scripts/kit-adoption.mjs's `--routes` and
   *  `analyze()` (R1 does not apply — there is no page here to render) and by
   *  app/tests/scaffold.spec.ts (the per-route h1/title sweep does not apply either, since
   *  what the browser shows a moment later is the redirect target's own screen). */
  readonly redirect?: boolean
  /** What a person might TYPE to find this screen in the palette — the verbs it holds. */
  readonly keywords?: string
  /** The screen's own keys. The keyboard sheet draws them as the screen's own group. */
  readonly keys?: ScreenKeys
}

/* ---- each screen's own keys ---------------------------------------------------------------
   THE SHEET IS COMPLETE OR IT IS NOTHING: every binding, read out of the screen that owns it.
   Each block is registered on its screen's `ROUTES` row below, so a new screen brings its keys
   with it and the sheet needs no edit. */

/* The capture screen's option keycaps, in its own order: `CaptureScreen.tsx` builds them by
   striking its twelve reserved letters out of `1234567890a…z`. Written out rather than
   summarised, because the nth key is the nth option and an operator counts along the row. */
const CAPTURE_OPTION_KEYS = '1234567890adeijklmnqwxyz'.toUpperCase().split('')

const CAPTURE_KEYS: ScreenKeys = {
  rows: [
    { keys: ['C'], does: 'Take the photograph', when: 'while the trigger is on Manual' },
    { keys: ['Space'], does: 'Pause motion, or resume it', when: 'not while typing' },
    { keys: ['S'], does: 'Put a divider in, at the card you are about to shoot' },
    { keys: ['U'], does: 'Undo the newest capture' },
    { keys: ['B'], does: 'Open or close the Box field' },
    { keys: ['H'], does: 'Open or close the Set hint field' },
    { keys: ['G'], does: 'Open or close the Game field' },
    { keys: ['R'], does: 'Open or close the Rarity field', when: 'when the game has rarities' },
    { keys: ['F'], does: 'Open or close the Finish field', when: 'when the game has finishes' },
    { keys: ['P'], does: 'Open or close the Product field' },
    { keys: ['V'], does: 'Open or close the Camera field' },
    { keys: ['O'], does: 'Open or close the Rotation field' },
    { keys: ['T'], does: 'Open or close the Trigger field' },
    { keys: CAPTURE_OPTION_KEYS, seq: true, does: 'Choose the option with that keycap beside it', when: 'while a field is open' },
    { keys: ['↵'], does: 'Take the box you typed, or make a new one', when: 'in the Box field' },
    { keys: ['Esc'], does: 'Close the open field' },
  ],
}

const REVIEW_KEYS: ScreenKeys = {
  rows: [
    { keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], seq: true, does: 'Answer with that candidate, or that row of the lookup' },
    { keys: ['G'], does: 'Answer the whole group at once', when: 'when every card left asks the same question' },
    { keys: ['↵'], does: 'Confirm the group', when: 'while the group offer is up' },
    { keys: ['Esc'], does: 'Go back to one card at a time', when: 'while the group offer is up' },
    { keys: ['S'], does: 'Skip this card and come back to it' },
    { keys: ['C'], does: 'Clear the skips and start round again', when: 'when everything left is skipped' },
    { keys: ['X'], does: 'Close this question without answering it' },
    { keys: ['1', '2', '3', '4', '5', '6', '7'], seq: true, does: 'Pick the reason it is closed', when: 'while the close panel is up' },
    { keys: ['L'], does: 'Look this card up' },
    { keys: ['Esc'], does: 'Leave the lookup, the close panel or the queue drawer' },
    { keys: ['R'], does: 'Reload the queue' },
    { keys: ['U'], does: 'Undo the newest answer' },
    /* From the runs fold (D291): the same two rows RUNS_KEYS carried
       on its own route, now read while the "Past runs" sheet is open instead. */
    { keys: ['←', '→'], does: 'Walk the box, card by card', when: 'while a run preview is on screen' },
  ],
}

const PRICING_KEYS: ScreenKeys = {
  where: 'Only while Pricing is open. Most keys work inside a price field.',
  rows: [
    { keys: ['R'], does: 'Reload the worklist', when: 'not on a phone' },
    { keys: ['T'], does: 'Hold to read the price history of the row under the pointer' },
    { keys: ['M'], does: 'Snap the price to Market' },
    { keys: ['L'], does: 'Snap the price to Low' },
    { keys: ['S'], does: 'Snap the price to Low with shipping' },
    { keys: ['D'], does: 'Snap the price to Direct low' },
    { keys: ['N'], does: 'Snap the price to what it is now', when: 'when the card is already listed' },
    { keys: ['H'], does: 'Hold this card back instead of pricing it' },
    { keys: ['P'], does: 'Show the photograph of this card' },
    { keys: ['U'], does: 'Undo the last answer' },
    { keys: ['↵'], does: 'Write this price and drop to the next card' },
    { keys: ['⇧↵'], does: 'Write this price and go back up one' },
    { keys: ['↑', '↓'], does: 'Write this price and move' },
    { keys: ['Esc'], does: 'Put the standing answer back and leave the field' },
    { keys: ['B'], does: 'Hold it because you are bullish', when: 'while the hold panel is up' },
    { keys: ['K'], does: 'Hold it because you are keeping it', when: 'while the hold panel is up' },
    { keys: ['X'], does: 'Hold it for a later batch', when: 'while the hold panel is up' },
    { keys: ['↵'], does: 'Set the hold', when: 'while the hold panel is up' },
    { keys: ['Esc'], does: 'Cancel the hold, or close the open panel' },
  ],
}

const ORDERS_KEYS: ScreenKeys = {
  where: 'Only while Orders is open, on a wide window.',
  rows: [
    { keys: ['/'], does: 'Jump into the search field' },
    { keys: ['↓'], does: 'Select the next buyer' },
    { keys: ['↑'], does: 'Select the buyer before it' },
    { keys: ['J'], does: 'Step to the next card in the walk' },
    { keys: ['K'], does: 'Step to the card before it in the walk' },
    { keys: ['U'], does: 'Undo the newest sale' },
  ],
}

const SALES_KEYS: ScreenKeys = {
  rows: [{ keys: ['/'], does: 'Jump into the product search field' }],
}

const INVENTORY_KEYS: ScreenKeys = {
  rows: [
    { keys: ['/'], does: 'Jump into the search field' },
    { keys: ['←', '→'], does: 'Step to the card before or after this one' },
    { keys: ['PgUp', 'PgDn'], does: 'Jump by section', when: 'with the card list focused' },
    { keys: ['Home', 'End'], does: 'Go to the first or last card', when: 'with the card list focused' },
    { keys: ['X'], does: 'Tick the selected card', when: 'with the card list focused' },
    { keys: ['Esc'], does: 'Close the open sheet or panel' },
    { keys: ['U'], does: 'Undo the newest sale or retirement' },
  ],
}

const CODES_KEYS: ScreenKeys = {
  rows: [{ keys: ['Esc'], does: 'Close the open sheet' }],
}

const FULFILLMENT_KEYS: ScreenKeys = {
  where: 'On that screen, where ? lists its own keys.',
  rows: [{ keys: ['Esc'], does: 'Close the enlarged photograph' }],
}

/* THE ONE REGISTRATION POINT (D275). A new screen is one row here plus a view that
   returns `<Page>` from the kit. From this row alone it gets its nav row (`nav: true`), its
   "Go to" entry in the palette, its jump entry and its own keys in the keyboard sheet, its tab
   title, the page scaffold through `PageRouteContext`, and the sheet host. The nav, the ring, the
   phone tab bar and the Fulfiller's door in the sidebar and drawer foot all read this table.
   Three places name a path on purpose, because each is a chosen door and not a list of screens:
   the brand links to Home, the dead-end page offers Home and Inventory, and the crash page offers
   Home. `app/tests/nav.spec.ts` proves the rest with a throwaway row. */
export const ROUTES: readonly Route[] = [
  { path: '/', label: 'Home', icon: 'home', view: Home, persona: 'owner', group: 'home', hotkey: 'h', nav: true, keywords: 'start overview' },
  { path: '/capture', label: 'Capture', icon: 'camera', view: CaptureScreen, persona: 'owner', group: 'work', hotkey: 'c', nav: true, tab: true, keywords: 'camera photograph scan feeder new box section', keys: CAPTURE_KEYS },
  { path: '/review', label: 'Review', icon: 'inbox', view: ReviewQueue, persona: 'owner', group: 'work', hotkey: 'q', nav: true, tab: true, keywords: 'queue answer questions parked pipeline identify join emit import csv reconcile the store live quantities my pricing run runs', keys: REVIEW_KEYS },
  { path: '/pricing', label: 'Pricing', icon: 'tag', view: Pricing, persona: 'owner', group: 'work', hotkey: 'p', nav: true, keywords: 'price hold write files emit worklist markdown stale reprice live listings mark down', keys: PRICING_KEYS },
  { path: '/orders', label: 'Orders', icon: 'cart', view: Orders, persona: 'owner', group: 'sell', hotkey: 'o', nav: true, tab: true, keywords: 'pull sell fetch orders paste ledger', keys: ORDERS_KEYS },
  { path: '/shipping', label: 'Shipping', icon: 'truck', view: Shipping, persona: 'owner', group: 'sell', hotkey: 's', nav: true, keywords: 'ship lanes envelope parcel export' },
  { path: '/revenue', label: 'Sales', icon: 'dollar', view: Revenue, persona: 'owner', group: 'sell', hotkey: 'v', nav: true, keywords: 'revenue sold gross money history search by name retrospective', keys: SALES_KEYS },
  /* THE STALE-LISTING MARKDOWN IS NOT A ROW HERE, AND IT MOVED SCREENS RATHER THAN GAINING ONE.
   *
   * D100 wanted `#/markdown` on D49's precedent — a worklist the operator sits in is what earned
   * `#/pricing` a route — and was refused by arithmetic over a horizontal nav: 1,484.9px to draw
   * eleven links on one row against the owner's 1,440px desk. D95 deleted that strip, and this
   * shell's sidebar was re-measured on 2026-09-04: a tenth link costs 38px inside an existing
   * group against 196px of slack. So it WOULD fit, and it is still not a row.
   *
   * WHAT CHANGED IS WHICH SCREEN HOLDS IT (D105). D100 put the sheet on `#/runs` because it and
   * the store-wide reconcile read the same My Pricing export — "the order is the order of the
   * work". The owner's objection, 2026-09-06: *"that's kinda dumb, this should just live in
   * pricing"*. They are right, and the flaw in the original argument is nameable: reading one
   * file is kinship of IMPLEMENTATION. `#/runs` is the pipeline over a box just photographed;
   * a markdown decides a PRICE over inventory already listed, and this table already has the
   * screen where prices are decided. The sheet opens from `#/pricing`'s header now, and its own
   * step-2 press lands on the screen the operator is already standing on, because the view below
   * is keyed on the hash MINUS its query.
   *
   * `LiveReconcile` STAYED ON `#/runs`, and that is not inconsistency. It writes `live` onto the
   * store's own record — a fact about inventory, settled where the other inventory facts are.
   *
   * SO A ROUTE WOULD STILL BUY NOTHING: the lens already has one (`#/pricing?markdown=<stamp>`,
   * bookmarkable, in the palette, reachable by chord), and a second pricing route would be two
   * screens for one job — which is the complaint this move answers, restated one level up.
   * Adding a row here also moves a count three mechanical checks reconcile (`route census`,
   * `route rosters`, and every spec's pinned roster), so it is a deliberate edit and never a
   * side effect. */
  { path: '/inventory', label: 'Inventory', icon: 'box', view: Inventory, persona: 'owner', group: 'library', hotkey: 'i', nav: true, tab: true, keywords: 'boxes find a card where search sold retire move', keys: INVENTORY_KEYS },
  { path: '/graveyard', label: 'Graveyard', icon: 'headstone', view: Graveyard, persona: 'owner', group: 'library', hotkey: 'g', nav: true, keywords: 'sold retired moved buried departed history gone deleted box' },
  { path: '/codes', label: 'Codes', icon: 'qr', view: Codes, persona: 'owner', group: 'library', hotkey: 'd', nav: true, keywords: 'code cards qr redeem read a box', keys: CODES_KEYS },
  { path: '/fulfillment', label: 'Cards to pull', icon: 'hand', view: Fulfillment, persona: 'fulfiller', group: 'aside', keywords: 'hand-off pull fulfiller new tab', keys: FULFILLMENT_KEYS },
  { path: '/gallery', label: 'Kit', icon: 'grid', view: Gallery, persona: 'owner', group: 'aside', keywords: 'component kit design system tokens' },
  /* THE PER-PRODUCT VIEW IS OFF-NAV ON PURPOSE (D227). It is a deep link, not a destination
   * anyone browses to cold: a product name on another screen opens it, and so does the
   * palette's "Go to" and its card search (D276). `OFF_NAV` below is what keeps
   * this from reading as an omission to `route rosters` and `route census`. No hotkey: a route
   * with no nav entry earns no chord, per this file's own rule for `#/fulfillment` and
   * `#/gallery`. */
  { path: '/product', label: 'Product history', icon: 'chart', view: ProductHistory, persona: 'owner', group: 'aside', keywords: 'sku market price archive per product history sold' },
  /* RUNS FOLDED INTO REVIEW (D291, the owner's ruling, RULINGS.md Q6).
   * `#/runs` stays a registered route, off-nav (the same D227 shape `#/product` above
   * already has), because a route is not a feature — a bookmark, a link Pricing or
   * ValueBands still carries, or a person's own habit all still say `#/runs`. Its view is a
   * redirect: it rewrites the hash to `#/review`, carrying `?run=`/`?state=`/`?box=` over
   * unread by itself, and Review reads them (`RunsContent`'s own hash functions, unchanged)
   * to know which of "Past runs" the operator meant to open. No hotkey, on `#/product`'s own
   * rule for a route with no nav entry. */
  { path: '/runs', label: 'Runs', icon: 'play', view: RunsRedirect, persona: 'owner', redirect: true, group: 'aside', keywords: 'pipeline identify join emit import csv reconcile the store live quantities my pricing' },
]

const GROUPS: readonly { readonly id: Group; readonly label: string | null }[] = [
  { id: 'home', label: null },
  { id: 'work', label: 'Workflow' },
  { id: 'sell', label: 'Sell' },
  { id: 'library', label: 'Library' },
]

/* THE GROUPS THE NAV DELIBERATELY DOES NOT DRAW, declared rather than implied.
 *
 * `aside` holds the routes reached from somewhere other than the nav list: the
 * Fulfiller's screen, which sits in the sidebar foot because it opens in its own tab and is
 * not one of the owner's screens, and the component kit, which is reachable from the command
 * palette only. Both are registered routes and both must stay reachable — they are simply not
 * items in the workflow list.
 *
 * IT IS A CONSTANT BECAUSE A CHECK READS IT. `scripts/docs-audit.py`'s `route rosters` row
 * reconciles every route's group against the groups the nav draws, and without this it can
 * only conclude that two routes have gone unreachable. Deleting this line does not change
 * what the app draws; it changes a passing check into a false alarm, which is the failure
 * mode that teaches people to ignore checks. */
const OFF_NAV: readonly Group[] = ['aside']

/** Is this route an item in the nav list, or is it reached some other way? */
function inNav(route: Route): boolean {
  return route.nav === true && !OFF_NAV.includes(route.group)
}

/** The rows the nav draws in one group, in table order. The sidebar, the drawer and the ring all
 *  read this, so the ring cannot step in an order the nav does not draw (D51). */
function navRows(group: Group): readonly Route[] {
  return ROUTES.filter((route) => route.group === group && inNav(route))
}

/* THE FULFILLER'S DOOR, FROM THE TABLE. Each Fulfiller route opens in its own tab from the
   sidebar foot and the drawer, as it does from the palette: his screen has no way back, so it
   never replaces the owner's. */
const OWN_TAB: readonly Route[] = ROUTES.filter((route) => route.persona === 'fulfiller')

const CHROME_FREE: ReadonlySet<Persona> = new Set<Persona>(['fulfiller'])
const LEADER = ','
const CHORD_MS = 1000

/* An unknown hash gets the OWNER's shell, not none. `NoSuchView` used to draw chromeless — no
   sidebar, no nav, no way back but its own three doors — which meant a fat-fingered URL cost the
   owner their whole nav, a strictly worse outcome than landing on any real owner screen. There is
   no persona to consult for a route that does not exist, so the default is the owner's, exactly
   as `route.view` would be inside the shell for any other route. */
function hasChrome(route: Route | undefined): boolean {
  return route === undefined || !CHROME_FREE.has(route.persona)
}

/* ---- hash routing ------------------------------------------------------------ */
function currentPath(): string {
  const raw = window.location.hash.replace(/^#/, '').split('?')[0] ?? ''
  if (raw === '') return '/'
  return raw.length > 1 ? raw.replace(/\/$/, '') : raw
}

function useHashPath(): string {
  const [path, setPath] = useState(currentPath)
  useEffect(() => {
    const read = () => setPath(currentPath())
    window.addEventListener('hashchange', read)
    read()
    return () => window.removeEventListener('hashchange', read)
  }, [])
  return path
}

export function go(path: string): void {
  window.location.hash = `#${path}`
}

/* ---- the `,` leader ------------------------------------------------------------- */
function useLeader(enabled: boolean, path: string): number | null {
  const [arm, setArm] = useState<number | null>(null)
  useEffect(() => {
    if (!enabled) {
      setArm(null)
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      /* NO GLOBAL KEY ACTS UNDER AN OPEN LAYER. A sheet, a modal, the palette or the drawer owns
         the keyboard while it is open (kit/overlay.tsx's one stack), so the chord never arms
         behind one and never jumps the page out from under it. */
      if (overlayOpen()) return
      if (event.key === LEADER) {
        event.preventDefault()
        event.stopPropagation()
        setArm((previous) => (previous ?? 0) + 1)
        return
      }
      if (arm === null) return
      event.preventDefault()
      event.stopPropagation()
      setArm(null)
      const target = ROUTES.find((candidate) => candidate.hotkey === event.key.toLowerCase())
      if (target === undefined) return
      go(target.path)
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [enabled, arm])
  useEffect(() => {
    setArm(null)
  }, [path])
  useEffect(() => {
    if (arm === null) return
    const disarm = () => setArm(null)
    const timer = window.setTimeout(disarm, CHORD_MS)
    window.addEventListener('blur', disarm)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('blur', disarm)
    }
  }, [arm])
  return arm
}

/* ---- ⌘← / ⌘→ steps the workflow ring ------------------------------------------------ */
const STEP_KEYS = [
  { key: 'ArrowLeft', delta: -1 },
  { key: 'ArrowRight', delta: 1 },
  { key: 'ArrowUp', delta: -1 },
  { key: 'ArrowDown', delta: 1 },
] as const
/* THE RING IS THE DRAWN ORDER (D51): the groups in the order the nav draws them, then the table
   within each group. A row declared outside its group's block in `ROUTES` is still drawn in its
   group, and the step reaches it there. Only a row with a letter is a step (D51's "which"). */
const RING: readonly Route[] = GROUPS.flatMap((group) => navRows(group.id)).filter((r) => r.hotkey !== undefined)
const STEP_SHORTCUTS = 'Meta+ArrowLeft Meta+ArrowRight'

function useRouteStep(enabled: boolean, path: string): void {
  useEffect(() => {
    if (!enabled) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey) return
      if (!event.metaKey && !event.ctrlKey) return
      if (isEditableTarget(event.target)) return
      if (overlayOpen()) return
      const step = STEP_KEYS.find((candidate) => candidate.key === event.key)
      if (step === undefined) return
      const at = RING.findIndex((candidate) => candidate.path === path)
      if (at === -1) return
      event.preventDefault()
      const target = RING[at + step.delta]
      if (target === undefined) return
      go(target.path)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [enabled, path])
}

/* ---- server presence ----------------------------------------------------------------- */
type ServerState = 'unknown' | 'online' | 'offline'

/** The shell's own poll, on `usePoll` (D207) rather than a hand-rolled interval — the
 *  15s cadence and the window-focus refresh are `liveMs`/`idleMs` (there is no live/idle
 *  distinction here, so both carry the same figure) and `refreshOnFocus` respectively.
 *  `useServerPresence` still owns two things `usePoll` cannot: the ONLINE/OFFLINE verdict a
 *  failed request draws no distinction on, and the boot toast, which fires the poll's own
 *  `refresh()` rather than re-implementing a check. */
function useServerPresence(enabled: boolean): { state: ServerState; retry: () => void } {
  const [state, setState] = useState<ServerState>('unknown')
  /* THE FOOT SAYS "Server online" AND NOTHING MORE (TXT-45). It printed the store's card count
     beside it, a third count in the chrome to compare against the screen's own. */
  const { refresh } = usePoll({
    enabled,
    fn: getStatus,
    onData: () => setState('online'),
    onError: () => setState('offline'),
    liveMs: 15000,
    idleMs: 15000,
    refreshOnFocus: true,
  })
  useEffect(() => {
    if (!enabled) return
    return onServerBoot(() => {
      toast({ kind: 'status', icon: 'refresh', title: 'Server restarted', body: 'Banchi is running your latest code.' })
      refresh()
    })
  }, [enabled, refresh])
  /* D207: THE FOOT LEARNS FROM EVERY REQUEST IN THE APP, NOT JUST ITS OWN POLL.
   * `server.ts:request()` is the one seam every call funnels through, and it now reports
   * reachability there — so a poll failing on `#/runs` while this screen sits on `#/pricing`
   * flips this dot within that ONE request rather than waiting up to 15s for the next
   * `/status` tick. A recovering request re-runs the poll to pick the cards figure back up; a
   * failing one sets `offline` directly, with no round trip of its own. */
  useEffect(() => {
    if (!enabled) return
    return onServerReachable((ok) => {
      if (ok) refresh()
      else setState('offline')
    })
  }, [enabled, refresh])
  return { state, retry: refresh }
}

/* ---- theme ---------------------------------------------------------------------------- */
function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(readTheme)
  useEffect(() => {
    // Follow the system while the owner has not chosen; a stored choice wins.
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const follow = () => {
      if (storedTheme() !== null) return
      const next: Theme = media.matches ? 'dark' : 'light'
      if (next === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
      else document.documentElement.removeAttribute('data-theme')
      setTheme(next)
    }
    follow()
    media.addEventListener('change', follow)
    return () => media.removeEventListener('change', follow)
  }, [])
  const toggle = useCallback(() => {
    // One cross-fade for the whole page (base.css reads this), then components keep their own.
    const root = document.documentElement
    root.setAttribute('data-theme-switching', 'true')
    window.setTimeout(() => root.removeAttribute('data-theme-switching'), 360)
    setTheme((previous) => {
      const next: Theme = previous === 'dark' ? 'light' : 'dark'
      applyTheme(next)
      return next
    })
  }, [])
  return [theme, toggle]
}

/* ---- rail state ----------------------------------------------------------------------
   A browser with no opinion gets one from its own width: below 1280 the rail is the honest
   default, and above it there is room for the words. THE NUMBER LIVES IN `App.css`, AS
   `--bn-rail-break-px` — read here and built into a `matchMedia` query at runtime, so the
   1280 the rail answers to and the 1280 a screen's own stylesheet might reference are one
   value with one home, not two numbers that could drift apart under a re-tune. (This is a
   design choice, not something `scripts/js-breakpoints.py`'s D123 row required: that row
   only pairs a `matchMedia`-shaped string literal against a CSS `@media` block, and neither
   the old `window.innerWidth < 1280` nor this file's interpolated query ever gave it one to
   pair — the row reports 0 breakpoints from this file's rail code, before and after.)
   A lazy initializer alone only ever ran once, at mount, so a window dragged narrower kept
   whatever density it started in until a reload; `useRailNarrow` (below) is a live
   `matchMedia` listener instead, the same shape `useMedia`/`TABLET_RAIL` already use. Once a
   person has toggled the rail by hand, `storedRail()` is no longer null and wins outright: a
   resize never overrides an explicit choice. */
function railBreakQuery(): string {
  const raw = typeof window === 'undefined'
    ? ''
    : getComputedStyle(document.documentElement).getPropertyValue('--bn-rail-break-px')
  const px = Number.parseInt(raw, 10)
  return `(max-width: ${(Number.isFinite(px) && px > 0 ? px : 1280) - 1}px)`
}
function readRail(): boolean {
  if (typeof window === 'undefined') return storedRail() ?? false
  return storedRail() ?? window.matchMedia(railBreakQuery()).matches
}
/** Tracks the rail breakpoint live, across a resize, with no width literal of its own — see
    `readRail` above. */
function useRailNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia(railBreakQuery()).matches)
  useEffect(() => {
    const mql = window.matchMedia(railBreakQuery())
    const on = () => setNarrow(mql.matches)
    on()
    mql.addEventListener('change', on)
    return () => mql.removeEventListener('change', on)
  }, [])
  return narrow
}

/* ---- where focus goes on a screen ----------------------------------------------------------- */
/** The screen's own heading: the kit page's h1, else any h1 in the page, else the page itself. */
function screenHeading(): HTMLElement | null {
  return (
    document.querySelector<HTMLElement>('.bn-view [data-bn-page-title]') ??
    document.querySelector<HTMLElement>('.bn-view main h1') ??
    document.querySelector<HTMLElement>('.bn-view main')
  )
}

/** Put focus on the screen's heading, so the next Tab reaches the screen's first control. */
function focusScreen(): void {
  const heading = screenHeading()
  if (heading === null) return
  if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1')
  heading.focus({ preventScroll: true })
}

/* Focus that sits in the chrome, on nothing, or in a layer that is closing. After a navigation
   it is focus nobody put in the new screen. */
const CHROME_FOCUS = '.bn-side, .bn-topbar, .bn-tabbar, .bn-skip, [data-bn-overlay]'

/* ---- error boundary ------------------------------------------------------------------ */
class RouteBoundary extends Component<
  { readonly path: string; readonly plain?: boolean; readonly children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('screen crashed', error, info.componentStack)
  }
  componentDidUpdate(previous: { path: string }) {
    if (previous.path !== this.props.path && this.state.error !== null) this.setState({ error: null })
  }
  render() {
    if (this.state.error === null) return this.props.children

    /* THE FULFILLER'S CRASH PAGE OFFERS NO DOOR OUT, and that is the whole difference.
       docs/DESIGN.md's constraints table forbids any route out of his view, and a crash is
       not an exemption from it — it is the moment he is most likely to press whatever is
       offered. So he gets his own floors (20px body, 44px targets) and exactly one control,
       which retries the screen he is on. No wordmark, no error text, no link home. */
    if (this.props.plain) {
      return (
        <main className="crash-plain">
          <h1 className="crash-plain-title">This screen stopped.</h1>
          <p className="crash-plain-say">Nothing is lost. Tap the button to open it again.</p>
          <button type="button" className="crash-plain-door" onClick={() => this.setState({ error: null })}>
            Open it again
          </button>
        </main>
      )
    }

    /* The owner's crash page is a kit page like every other screen. What the browser said sits
       behind a disclosure (D196): it is for a bug report, not for reading. */
    return (
      <Page title="This screen stopped." lede="Reloading usually fixes it." className="no-such-view">
        <details className="no-such-view-detail">
          <summary>What went wrong</summary>
          <p className="no-such-view-path">{this.state.error.message}</p>
        </details>
        <div className="no-such-view-doors">
          <button type="button" className="no-such-view-door" onClick={() => this.setState({ error: null })}>
            <Icon name="refresh" /> Reload this screen <Icon name="arrowRight" />
          </button>
          <a className="no-such-view-door" href="#/">
            <Icon name="home" /> Go home <Icon name="arrowRight" />
          </a>
        </div>
      </Page>
    )
  }
}

/* ---- unknown route -------------------------------------------------------------------- */
function NoSuchView({ path }: { path: string }) {
  return (
    <Page
      title="Nothing lives at this address."
      lede={
        <>
          Banchi has no screen called <span className="no-such-view-path">#{path}</span>. Try one of these.
        </>
      }
      className="no-such-view"
    >
      {/* No door to #/fulfillment here: this is the OWNER's dead end, and the Fulfiller's
          screen is a different persona's view, not a spare exit — the owner already has
          Home and Inventory, and D95's "the Fulfiller's crash has no door out" is about
          HIS crash page, never a reason to hand him as an escape hatch from someone else's. */}
      <div className="no-such-view-doors">
        <a className="no-such-view-door" href="#/">
          <Icon name="home" /> Home <Icon name="arrowRight" />
        </a>
        <a className="no-such-view-door" href="#/inventory">
          <Icon name="box" /> Inventory <Icon name="arrowRight" />
        </a>
      </div>
    </Page>
  )
}

/* ---- the palette: "Go to" (D276, amends D95) ------------------------------------
   IT SAYS WHAT IT DOES. It was labelled "Search" and found only screens, so a card name typed
   into it answered "Nothing matches" (UX-022). Now it is "Go to": every screen, the off-nav ones
   included (UX-003), and the cards the store holds, which open their product history. It is the
   kit's `Modal`, so it has one Close a thumb can press (UX-156), holds focus, and takes Escape
   from the one stack of layers. */
type Command = { readonly id: string; readonly group: string; readonly label: string; readonly icon: IconName; readonly hint?: string; readonly keywords?: string; readonly run: () => void }

/** A card search starts at this many characters: one letter matches half the store. */
const CARD_QUERY_MIN = 2
/** At most this many cards. The palette jumps; the full list is Inventory's. */
const CARD_LIMIT = 8

/** Where a query hits, ranked so a match on the LABEL — the word a person actually typed for
 *  the screen — outranks one buried in a keyword list, null when the query hits nowhere at all.
 *  Runs's own `keywords` carries "my pricing" for D109's one-press door into the live book, and
 *  Runs is declared before Pricing — so a plain substring filter over the whole joined string
 *  left Runs sitting above Pricing for "pricing" on declaration order alone, never on relevance.
 *  `Array.prototype.sort` has been stable since ES2019, so two commands tied on rank keep the
 *  order `commands` already draws them in and need no second key. */
function rankMatch(c: Command, q: string): number | null {
  const label = c.label.toLowerCase()
  if (label === q) return 0
  if (label.startsWith(q)) return 1
  if (label.includes(q)) return 2
  if (`${c.group} ${c.hint ?? ''} ${c.keywords ?? ''}`.toLowerCase().includes(q)) return 3
  return null
}

function CommandPalette({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: readonly Command[] }) {
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const listId = useId()
  const list = useRef<HTMLDivElement>(null)
  const cards = useSearch()
  const askCards = cards.setQuery
  useEffect(() => {
    if (!open) return
    setQuery('')
    setCursor(0)
  }, [open])
  const q = query.trim().toLowerCase()
  const cardQuery = open && q.length >= CARD_QUERY_MIN ? query.trim() : ''
  useEffect(() => {
    askCards(cardQuery)
  }, [askCards, cardQuery])

  const screens = useMemo(() => {
    if (q === '') return commands
    return commands
      .map((c) => ({ c, rank: rankMatch(c, q) }))
      .filter((scored): scored is { c: Command; rank: number } => scored.rank !== null)
      .sort((a, b) => a.rank - b.rank)
      .map((scored) => scored.c)
  }, [commands, q])

  /* A REFUSED CARD SEARCH HIDES THE CARDS GROUP, WITH ONE LINE. The published demo records no
     search, so there the line says so; anywhere else the server did not answer. */
  const refused = cardQuery !== '' && cards.failure !== null
  const found = useMemo<Command[]>(() => {
    if (cardQuery === '' || cards.results === null) return []
    return cards.results.groups
      .filter((group) => group.sku !== null)
      .slice(0, CARD_LIMIT)
      .map((group) => {
        const sku = group.sku as string
        const name = group.names[0] ?? sku
        return {
          id: `card:${sku}`,
          group: 'Cards',
          label: name,
          icon: 'chart' as const,
          hint: group.number_display ?? group.set ?? undefined,
          run: () => openSheet('product', { sku, name }),
        }
      })
  }, [cardQuery, cards.results])
  const matches = refused ? screens : [...screens, ...found]

  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(0, matches.length - 1)))
  }, [matches.length])
  useEffect(() => {
    list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  const choose = (command: Command | undefined) => {
    if (command === undefined) return
    onClose()
    command.run()
  }

  const grouped: { group: string; items: Command[] }[] = []
  for (const command of matches) {
    const last = grouped[grouped.length - 1]
    if (last !== undefined && last.group === command.group) last.items.push(command)
    else grouped.push({ group: command.group, items: [command] })
  }
  let index = -1
  return (
    <Modal open={open} onClose={onClose} title="Go to" className="bn-cmdk">
      <div className="bn-cmdk-input">
        <Icon name="search" size={18} className="bn-muted" />
        {/* `autoFocus`, not only the kit's first-focus frame: a person types the moment the
            palette opens, and a key that arrives before that frame would be lost. */}
        <input
          autoFocus
          data-autofocus=""
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={matches.length > 0 ? `${listId}-${cursor}` : undefined}
          aria-label="A screen or a card"
          autoComplete="off"
          spellCheck={false}
          value={query}
          placeholder="A screen, or a card’s name"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setCursor((c) => Math.min(c + 1, matches.length - 1))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setCursor((c) => Math.max(c - 1, 0))
            } else if (event.key === 'Enter') {
              event.preventDefault()
              choose(matches[cursor])
            }
          }}
        />
      </div>
      <div className="bn-cmdk-list" role="listbox" id={listId} aria-label="Results" ref={list}>
        {matches.length === 0 && !cards.loading && !refused ? <div className="bn-cmdk-empty">Nothing matches “{query}”.</div> : null}
        {grouped.map((section) => (
          <div key={section.group}>
            <div className="bn-cmdk-group">{section.group}</div>
            {section.items.map((command) => {
              index += 1
              const at = index
              /* AN OPTION IS NOT A TAB STOP. The field owns the keyboard and names the option it
                 points at (`aria-activedescendant`), so the only stops are the field and Close,
                 and the trap holds Tab between them. */
              return (
                <div
                  key={command.id}
                  id={`${listId}-${at}`}
                  role="option"
                  aria-selected={at === cursor}
                  className="bn-cmdk-item"
                  onMouseEnter={() => setCursor(at)}
                  onClick={() => choose(command)}
                >
                  <Icon name={command.icon} size={16} />
                  <span>{command.label}</span>
                  {command.hint ? <span className="bn-cmdk-item-hint">{command.hint}</span> : null}
                </div>
              )
            })}
          </div>
        ))}
        {refused ? (
          <div>
            <p className="bn-cmdk-note">{__BN_DEMO__ ? 'Card search is not in this demo.' : 'Card search did not answer.'}</p>
          </div>
        ) : null}
      </div>
      <div className="bn-cmdk-foot">
        <KeyHint>
          <Kbd>↑</Kbd> <Kbd>↓</Kbd> to move, <Kbd>↵</Kbd> to open, and <Kbd>,</Kbd> then a letter jumps anywhere
        </KeyHint>
      </div>
    </Modal>
  )
}

/* ---- which-key overlay for the leader ------------------------------------------------------ */
function WhichKey({ armed }: { armed: boolean }) {
  if (!armed) return null
  return (
    <div className="bn-whichkey" role="status" aria-live="polite">
      <div className="bn-whichkey-title">
        <Kbd>,</Kbd> then…
      </div>
      <div className="bn-whichkey-grid">
        {RING.map((route) => (
          <span key={route.path} className="bn-whichkey-item">
            <Kbd>{route.hotkey?.toUpperCase()}</Kbd>
            {route.label}
          </span>
        ))}
      </div>
      <span className="bn-whichkey-drain" style={{ animationDuration: `${CHORD_MS}ms` }} />
    </div>
  )
}

/* ---- the shortcuts sheet ------------------------------------------------------------------
   THE ONLY PLACE THE PRODUCT SAYS IT IS KEYBOARD-DRIVEN, so it is COMPLETE: every binding,
   grouped by where it applies. It opens on its keys, with no paragraph about itself (UX-119).
   The shell's own groups are written here. Every screen's group, and every jump entry, is
   DERIVED from `ROUTES`, so a new screen appears here with no edit to this sheet.

   The caps here are written with a bare <kbd> rather than the kit's <Kbd>, which is
   aria-hidden — correct beside a labelled button, wrong here, where the key IS the content
   and a screen reader that skips it reads a list of verbs with no shortcuts in it. */

type KeyGroup = {
  readonly id: string
  readonly title: string
  readonly icon: IconName
  readonly where: string
  /** The screen this group belongs to, so the sheet can offer the way there. */
  readonly at?: string
  readonly rows: readonly Binding[]
}

const ANYWHERE_KEYS: KeyGroup = {
  id: 'anywhere',
  title: 'Anywhere',
  icon: 'keyboard',
  where: 'Works on every one of your screens.',
  rows: [
    { keys: ['?'], does: 'Open this sheet' },
    { keys: ['⌘K', 'Ctrl K'], does: 'Go to a screen, or find a card' },
    { keys: ['⌘←', '⌘→'], does: 'Step to the screen before or after this one, in workflow order' },
    { keys: ['⌘↑', '⌘↓'], does: 'The same step, for a keyboard without arrow pairs' },
    { keys: ['⌘.'], does: 'Collapse the sidebar to its rail, or open it again' },
    { keys: ['R'], does: 'Reload the screen', when: 'where it has a Reload button' },
    { keys: ['Esc'], does: 'Close whatever is over the screen' },
  ],
}

/** Every screen, from `ROUTES`: its `,` letter, or the palette for a screen with none. */
function jumpKeys(): KeyGroup {
  const lettered = ROUTES.filter((route) => route.hotkey !== undefined)
  const unlettered = ROUTES.filter((route) => route.hotkey === undefined)
  return {
    id: 'jump',
    title: 'Jump to a screen',
    icon: 'zap',
    where: 'Press the comma, then the letter.',
    rows: [
      ...lettered.map((route) => ({ keys: [`,${(route.hotkey ?? '').toUpperCase()}`], does: route.label })),
      ...unlettered.map((route) => ({ keys: ['⌘K'], does: route.label, when: 'then type its name' })),
    ],
  }
}

const PALETTE_KEYS: KeyGroup = {
  id: 'palette',
  title: 'Go to',
  icon: 'command',
  where: 'Only while Go to is open.',
  rows: [
    { keys: ['↑', '↓'], does: 'Move down the list' },
    { keys: ['↵'], does: 'Open the highlighted screen or card' },
    { keys: ['Esc'], does: 'Close it and leave the screen as it was' },
  ],
}

/** Each screen's own keys, from its `ROUTES` row. */
function screenKeys(): KeyGroup[] {
  return ROUTES.flatMap((route) =>
    route.keys === undefined
      ? []
      : [{
          id: route.path,
          title: route.label,
          icon: route.icon,
          at: route.persona === 'owner' ? route.path : undefined,
          where: route.keys.where ?? `Only while ${route.label} is open.`,
          rows: route.keys.rows,
        }],
  )
}

const SHORTCUTS: readonly KeyGroup[] = [ANYWHERE_KEYS, jumpKeys(), PALETTE_KEYS, ...screenKeys()]

function Caps({ row }: { row: Binding }) {
  return (
    <span className="app-keys-caps">
      {row.keys.map((cap, at) => (
        <span key={`${cap}-${at}`} className="app-keys-cap">
          {at === 0 || row.seq ? null : <span className="app-keys-join">or</span>}
          <kbd className="bn-kbd">{cap}</kbd>
        </span>
      ))}
    </span>
  )
}

/** A row survives a query if the query hits its own text or its group's title — a group
 *  title match keeps every row in it, so typing "capture" shows the whole Capture group
 *  rather than only the one row that happens to say the word. */
function rowMatches(group: KeyGroup, row: Binding, q: string): boolean {
  if (group.title.toLowerCase().includes(q)) return true
  if (row.does.toLowerCase().includes(q)) return true
  return row.keys.some((k) => k.toLowerCase().includes(q))
}

function KeysSheet({ open, onClose, path }: { open: boolean; onClose: () => void; path: string }) {
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(false)

  /* Reset to the default view every time the sheet opens, rather than carrying the last
     session's search or expansion forward — a filter left on from last time is a sheet that
     looks broken the next time it opens. */
  useEffect(() => {
    if (open) {
      setQuery('')
      setShowAll(false)
    }
  }, [open])

  const q = query.trim().toLowerCase()
  /* DEFAULT VIEW: Anywhere, Jump to a screen, and whichever group belongs to the screen
     already open. Typing a query, or pressing "Show every screen", overrides it. */
  const groups = q === ''
    ? (showAll
        ? SHORTCUTS
        : SHORTCUTS.filter((group) => group.id === 'anywhere' || group.id === 'jump' || group.at === path))
    : SHORTCUTS.map((group) => ({ ...group, rows: group.rows.filter((row) => rowMatches(group, row, q)) })).filter(
        (group) => group.rows.length > 0,
      )
  const hidden = q === '' && !showAll && SHORTCUTS.length > groups.length

  return (
    <Modal open={open} onClose={onClose} title="Keyboard shortcuts" icon="keyboard" className="app-keys">
      <div className="app-keys-search">
        <SearchField value={query} onChange={setQuery} persona="owner" label="Search shortcuts" placeholder="Search shortcuts" autoFocus />
      </div>
      <div className="app-keys-body">
        {groups.length === 0 ? <p className="app-keys-none">No shortcut matches “{query}”.</p> : null}
        {groups.map((group) => (
          <section key={group.id} className="app-keys-group">
            <h3 className="app-keys-group-title">
              <Icon name={group.icon} size={15} />
              {group.title}
            </h3>
            <p className="app-keys-where">
              {group.where}
              {group.at === undefined ? null : (
                <>
                  {' '}
                  <a className="app-keys-goto" href={`#${group.at}`} onClick={onClose}>
                    Go there
                    <Icon name="arrowRight" size={12} />
                  </a>
                </>
              )}
            </p>
            <dl className="app-keys-rows">
              {group.rows.map((row, at) => (
                <div key={`${group.id}-${at}`} className={row.keys.length > 3 ? 'app-keys-row app-keys-row-wide' : 'app-keys-row'}>
                  <dt>
                    <Caps row={row} />
                  </dt>
                  <dd className="app-keys-does">
                    {row.does}
                    {row.when === undefined ? null : <span className="app-keys-when">{row.when}</span>}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        {hidden ? (
          <p className="app-keys-more">
            <button type="button" className="app-keys-show-all" onClick={() => setShowAll(true)}>
              Show every screen’s keys
            </button>
          </p>
        ) : null}
      </div>
    </Modal>
  )
}

/* ---- nav link ------------------------------------------------------------------------------- */
function NavLink({ route, current, onNavigate }: { route: Route; current: boolean; onNavigate?: () => void }) {
  return (
    <a
      className="bn-nav-link app-nav-link"
      href={`#${route.path}`}
      aria-current={current ? 'page' : undefined}
      data-tip={route.label}
      onClick={onNavigate}
    >
      <Icon name={route.icon} size={18} />
      <span className="bn-nav-text">{route.label}</span>
      {route.hotkey ? <Kbd>,{route.hotkey.toUpperCase()}</Kbd> : null}
    </a>
  )
}

/* ---- the server line ------------------------------------------------------------------------ */
function ServerLine({ state }: { state: ServerState }) {
  return (
    <div className="bn-server" data-state={state} title={state === 'offline' ? 'The capture server is not answering' : undefined}>
      <span className={`bn-dot ${state === 'online' ? 'bn-dot-ok' : state === 'offline' ? 'bn-dot-danger' : ''}`} />
      <span className="bn-side-foot-text">
        {state === 'online' ? 'Server online' : state === 'offline' ? 'Server offline' : 'Checking server…'}
      </span>
    </div>
  )
}

/* ---- the tab title ------------------------------------------------------------------------------
   ONE FIXED TITLE: "番地 " and the screen's name in lowercase ("番地 pricing", "番地 home"). The
   owner's ruling, 2026-09-23. It replaced a title that alternated on a timer between the screen and
   "番地 banchi", and a second, joined form under reduced motion. `app/index.html` carries
   "番地 banchi" for the moment before React boots.
   LOWERCASED HERE AND NOWHERE ELSE. The nav, the palette and the keyboard sheet draw the label in
   Title Case; this is the tab's own voice. `toLowerCase` rather than `toLocaleLowerCase`: the labels
   are ASCII English and the locale form has a Turkish dotted-i behaviour nobody here wants.
   THE FULFILLER'S TAB NAMES HIS TASK AND CARRIES NO BRAND (D5). */
function tabTitle(route: Route | undefined): string {
  const name = (route === undefined ? 'Not found' : route.title ?? route.label).toLowerCase()
  return route?.persona === 'fulfiller' ? name : `番地 ${name}`
}

/* ---- sidebar ---------------------------------------------------------------------------------- */
/* docs/specs/logo.md section 16: the open sidebar draws the lockup at kanji 40, and the rail keeps
   the mark at the 32 it already ships. Named here because they are the two numbers the shell
   chooses; everything derived from them comes out of `lockupGeometry.ts`. */
const SIDEBAR_KANJI = 40
const RAIL_MARK = 32
/* THE DRAWER IS THE SIDEBAR ON A PHONE, so it draws the sidebar's number (logo.md section 19).
   Both were rendered at 390 and 320 in both themes before this was written; 32 fits with room and
   reads as a smaller copy, 40 owns the head the way it owns the sidebar's. */
const DRAWER_KANJI = 40

/* AND 34 WHERE THE SCREEN IS SHORT (section 19, amended). The forced choice above was made on
   WIDTH; on a phone in Safari, whose toolbars take about 90px, the drawer's nav list runs past
   the fold. The owner's ruling was to shrink the group labels to fit rather than drop them, and
   the last 15px come from here.
   THE HEIGHT IS THE CONDITION, not the width: a 430x932 Pro Max is a phone and has the room. */
const DRAWER_KANJI_SHORT = 34
const SHORT_SCREEN = '(max-height: 820px)'

/* ONE BRAND SLOT, THREE PLACES (logo.md section 19). The sidebar, the phone's top bar and the
   phone's drawer all draw the SAME `Lockup` — what differs is `--bn-brand-open`, which App.css
   sets per surface, and which the morph reads as the slot's own width. There is no second
   drawing and no branch here: the bar renders this railed and the drawer renders it open.
   The slot's two sizes come from the GENERATED block rather than from tokens: a token would be a
   second copy of a number `lockupGeometry.ts` already carries, and a value typed twice is the
   defect section 13 spent thirty-seven rounds learning. */
function BrandSlot({ kanji = SIDEBAR_KANJI }: { readonly kanji?: number }) {
  return (
    <span
      className="bn-brand-slot"
      style={{
        ['--bn-lockup-w' as string]: `${(kanji * BLOCK.w) / BLOCK.ref}px`,
        ['--bn-lockup-h' as string]: `${(kanji * BLOCK.h) / BLOCK.ref}px`,
        ['--bn-rail-mark' as string]: `${RAIL_MARK}px`,
      }}
    >
      {/* ONE DRAWING, NOT TWO. The rail's empty slot is this same lockup with its bracket morphed
          and its type faded out — logo.md section 1: "with the card removed the same brackets
          become an empty slot, which is the in-product mark." */}
      <Lockup size={kanji} railSize={RAIL_MARK} className="bn-brand-lockup" decorative />
    </span>
  )
}

/* THE TABLET RAIL IS A MEDIA QUERY AND REACT CANNOT SEE IT. App.css rails the shell between 640
   and 1023 by breakpoint, ignoring `data-rail` entirely — so a toggle offered at that width would
   set state the layout does not read and appear to do nothing. Worse than not offering one.
   THE RAIL STARTS AT 640, NOT 768 (the owner's ruling, 2026-09-23): half-width Chrome at 720 is a
   desk, and gets the desktop rail rather than the phone's bars. This query and App.css's own
   must name the same edge; `scripts/js-breakpoints.py` checks it. */
const TABLET_RAIL = '(min-width: 640px) and (max-width: 1023px)'
function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const on = () => setMatches(mql.matches)
    on()
    mql.addEventListener('change', on)
    return () => mql.removeEventListener('change', on)
  }, [query])
  return matches
}

function Sidebar({
  path,
  rail,
  onToggleRail,
  armed,
  server,
  theme,
  onToggleTheme,
  onPalette,
}: {
  path: string
  rail: boolean
  onToggleRail?: () => void
  armed: boolean
  server: ServerState
  theme: Theme
  onToggleTheme: () => void
  onPalette: () => void
}) {
  const brandSlot = <BrandSlot />

  return (
    <aside className="bn-side">
      {/* THE LOCKUP REPLACES THE MARK, THE WORDMARK AND THE TAGLINE TOGETHER (logo.md section 16).
          Both ends of the brand are one drawing and CSS chooses: a JSX branch on `rail` would be
          wrong at 640-1023px, where App.css rails the shell by media query and `data-rail` is
          inert. The drawing is `aria-hidden`: the element that wraps it carries the name. */}
      {/* THE BRAND IS THE TOGGLE. A separate 22px chevron beside it was half clipped by
          `.bn-side`'s `overflow: hidden`. AT 640-1023 IT STAYS A LINK: that breakpoint rails the
          shell by media query and ignores `data-rail`, so a toggle there would do nothing. */}
      {onToggleRail ? (
        <button
          type="button"
          className="bn-brand"
          onClick={onToggleRail}
          aria-label={rail ? 'Expand the sidebar' : 'Collapse the sidebar'}
          aria-expanded={!rail}
        >
          {brandSlot}
          <Icon name={rail ? 'chevronRight' : 'chevronLeft'} size={14} className="bn-brand-chevron" />
        </button>
      ) : (
        <a className="bn-brand" href="#/" aria-label="Home">
          {brandSlot}
        </a>
      )}
      <nav className="bn-nav app-nav" aria-label="Screens" aria-keyshortcuts={STEP_SHORTCUTS} data-armed={armed ? 'true' : undefined}>
        {GROUPS.map((group) => (
          <div key={group.id} className="bn-nav-group">
            {group.label ? <div className="bn-nav-group-label">{group.label}</div> : null}
            {navRows(group.id).map((route) => (
              <NavLink key={route.path} route={route} current={route.path === path} />
            ))}
          </div>
        ))}
      </nav>
      {/* ONE ICON COLUMN AND ONE ROW HEIGHT FOR THE WHOLE SIDEBAR (UX-134): the foot's rows are
          sized to the nav's own in App.css. */}
      <div className="bn-side-foot">
        {OWN_TAB.map((route) => (
          <a key={route.path} className="bn-nav-link" href={`#${route.path}`} target="_blank" rel="noopener" data-tip={route.label}>
            <Icon name={route.icon} size={18} />
            <span className="bn-nav-text">{route.label}</span>
            <Icon name="external" size={14} className="bn-faint" />
          </a>
        ))}
        <Button variant="ghost" icon="search" onClick={onPalette} data-tip="Go to" aria-haspopup="dialog">
          <span className="bn-side-foot-text">Go to</span>
          <Kbd>⌘K</Kbd>
        </Button>
        <Button variant="ghost" icon={theme === 'dark' ? 'sun' : 'moon'} onClick={onToggleTheme}>
          <span className="bn-side-foot-text">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        </Button>
        <ServerLine state={server} />
      </div>
    </aside>
  )
}

/* ---- phone chrome ------------------------------------------------------------------------------- */
/* Every owner screen draws its own h1 directly under this bar, so the bar carries the
   wordmark rather than repeating (or contradicting) the screen's name.
   THE MARK HERE IS THE EMPTY SLOT, NOT THE TILE (logo.md section 19). This bar is the rail's
   own case one breakpoint down, so it draws what the rail draws, off the same `Lockup`, and
   App.css pins the slot railed.
   ONE DOOR TO THE DRAWER (UX-072). The bar had a Menu button that opened the same drawer as
   the tab bar's More; More is the one door now, and the bar keeps Go to. */
function PhoneBar({ onPalette }: { onPalette: () => void }) {
  return (
    <header className="bn-topbar">
      <a className="bn-topbar-brand" href="#/" aria-label="Home">
        <BrandSlot />
      </a>
      {/* THE WORDMARK IS THE LOCKUP'S OWN ROMAN, SET AS TEXT (logo.md section 19, amended). Its
          face, case and tracking come from the geometry and none is typed here. Its ink is the
          shell's own muted text colour, so it reads at 4.5:1 (the drawing's 45% did not). */}
      <span
        className="bn-topbar-wordmark"
        style={{ ['--bn-roman-track' as string]: `${ROMAN_TRACK_SOLVED / PARAMS.romanSize}em` }}
      >
        Banchi
      </span>
      <IconButton icon="search" label="Go to" onClick={onPalette} aria-haspopup="dialog" />
    </header>
  )
}

function TabBar({ path, drawerOpen, onMore }: { path: string; drawerOpen: boolean; onMore: () => void }) {
  const tabs = ROUTES.filter((r) => r.tab)
  /* MORE IS LIT WHEN THE SCREEN IS BEHIND IT (UX-046): every screen shows its place in the bar. */
  const behindMore = !tabs.some((route) => route.path === path)
  return (
    <nav className="bn-tabbar" aria-label="Primary">
      {tabs.map((route) => (
        <a key={route.path} className="bn-tab-link" href={`#${route.path}`} aria-current={route.path === path ? 'page' : undefined}>
          <Icon name={route.icon} size={22} />
          <span>{route.label}</span>
        </a>
      ))}
      <button
        type="button"
        className="bn-tab-link"
        onClick={onMore}
        aria-current={behindMore ? 'page' : undefined}
        aria-haspopup="dialog"
        aria-expanded={drawerOpen}
      >
        <Icon name="more" size={22} />
        <span>More</span>
      </button>
    </nav>
  )
}

/* THE DRAWER IS THE KIT'S SHEET (UX-014), on its own left edge (kit.css carves the drawer out of
   the rise-from-the-bottom rule). So it is modal: focus moves in, stays in, and goes back to More
   when it closes, and Escape is the one stack's. ITS FOOT JOINED THE LIST
   (D266, amends D204): Cards to pull, the theme and the server line are the last rows of the one
   scrolling list, so no row ever sits under a fixed block. */
function Drawer({ open, path, onClose, theme, onToggleTheme, server }: { open: boolean; path: string; onClose: () => void; theme: Theme; onToggleTheme: () => void; server: ServerState }) {
  /* THE ONE PLACE IN THIS SHELL WHERE THE SIZE IS CHOSEN IN JS RATHER THAN IN A STYLESHEET, and
     the reason is the morph: `Lockup` reads the SLOT's measured width against the `size` it was
     handed, so a media query that shrank the slot without telling the component would draw the
     bracket part of the way toward the rail. One source decides and both read it. */
  const short = useMedia(SHORT_SCREEN)
  return (
    <Sheet
      open={open}
      onClose={onClose}
      className="bn-drawer"
      title={
        <>
          <BrandSlot kanji={short ? DRAWER_KANJI_SHORT : DRAWER_KANJI} />
          <span className="bn-sr">Screens</span>
        </>
      }
    >
      <nav className="bn-nav" aria-label="All screens">
        {GROUPS.map((group) => (
          <div key={group.id} className="bn-nav-group">
            {group.label ? <div className="bn-nav-group-label">{group.label}</div> : null}
            {navRows(group.id).map((route) => (
              <NavLink key={route.path} route={route} current={route.path === path} onNavigate={onClose} />
            ))}
          </div>
        ))}
        <div className="bn-nav-group bn-drawer-more">
          {OWN_TAB.map((route) => (
            <a key={route.path} className="bn-nav-link" href={`#${route.path}`} target="_blank" rel="noopener" onClick={onClose}>
              <Icon name={route.icon} size={18} />
              <span className="bn-nav-text">{route.label}</span>
              <Icon name="external" size={14} className="bn-faint" />
            </a>
          ))}
          <button type="button" className="bn-nav-link" onClick={onToggleTheme}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
            <span className="bn-nav-text">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          </button>
          <ServerLine state={server} />
        </div>
      </nav>
    </Sheet>
  )
}

/* ---- the app ------------------------------------------------------------------------------------ */
export function App() {
  const path = useHashPath()
  const route = ROUTES.find((candidate) => candidate.path === path)
  const chrome = hasChrome(route)
  const arm = useLeader(chrome, path)
  useRouteStep(chrome, path)
  const [rail, setRail] = useState(readRail)
  // The rail breakpoint is a WIDTH DEFAULT, not a one-time read: a stored preference
  // (`storedRail()` non-null) always wins and is never overridden here, but a browser with no
  // opinion follows a live resize rather than freezing at whatever density the tab happened to
  // mount at.
  const railNarrowNow = useRailNarrow()
  useEffect(() => {
    if (storedRail() !== null) return
    setRail(railNarrowNow)
  }, [railNarrowNow])
  const [theme, toggleTheme] = useTheme()
  const [palette, setPalette] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [keysOpen, setKeysOpen] = useState(false)
  const { state: server, retry } = useServerPresence(chrome)

  useEffect(() => {
    document.title = tabTitle(route)
  }, [route])

  useEffect(() => {
    setDrawer(false)
    setPalette(false)
    setKeysOpen(false)
  }, [path])

  /* A ROUTE CHANGE LANDS AT THE TOP. `path` is query-stripped (`currentPath`, above), so a
     same-path query change — `#/pricing` -> `#/pricing?band=top` — does not re-fire this and the
     scroll position a click left behind is kept, which is D159's own rule: staleness is a filter,
     never a jump. `.bn-shell-main` carries no `overflow` rule (App.css), so the document — the
     window — is what scrolls at every width this shell is verified at; there is no second
     scroller to reset. */
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [path])

  /* AND FOCUS LANDS ON THE NEW SCREEN (UX-092). After a sidebar link, a `,` chord, the palette or
     the drawer, focus was left in the chrome or on nothing, so the screen's first control was
     fifteen Tabs away. On a navigation, focus that sits in the chrome moves to the screen's
     heading, and one Tab reaches the screen. Focus a screen placed itself (a field it focuses)
     is left alone. Not on the first load: nobody navigated. The last path is held rather than a
     "mounted" flag, because StrictMode runs a mount effect twice and a flag reads the second run
     as a navigation. */
  const shownPath = useRef(path)
  useEffect(() => {
    if (shownPath.current === path) return
    shownPath.current = path
    const frame = window.requestAnimationFrame(() => {
      const now = document.activeElement
      const stray = now === null || now === document.body || (now instanceof HTMLElement && now.closest(CHROME_FOCUS) !== null)
      if (stray) focusScreen()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [path])

  const tabletRail = useMedia(TABLET_RAIL)
  const toggleRail = useCallback(() => {
    setRail((previous) => {
      const next = !previous
      rememberRail(next)
      return next
    })
  }, [])

  useEffect(() => {
    if (!chrome) return
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPalette((open) => !open)
        return
      }
      if ((event.metaKey || event.ctrlKey) && event.key === '.') {
        /* The rail is under the layer, so the key is the layer's (UX-014). */
        if (overlayOpen()) return
        event.preventDefault()
        toggleRail()
        return
      }
      /* `?` IS THE ONLY UNMODIFIED KEY THE SHELL TAKES, and it yields to typing and to an open
         layer. A question mark is a legitimate character in a box name, a card name and a
         search — `keys.ts` is the one place that judgement is made. Escape is not handled here:
         every layer takes its own from the kit's one stack (kit/overlay.tsx). */
      if (event.key === '?' && !event.repeat && !isEditableTarget(event.target) && !overlayOpen()) {
        event.preventDefault()
        setKeysOpen(true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [chrome, toggleRail])

  const commands = useMemo<Command[]>(() => {
    /* EVERY SCREEN, THE OFF-NAV ONES INCLUDED (UX-003). The Fulfiller's opens in its own tab,
       as it does from the sidebar: his screen has no way back. */
    const screens: Command[] = ROUTES.map((r) => ({
      id: `go:${r.path}`,
      group: 'Screens',
      label: r.label,
      icon: r.icon,
      hint: r.hotkey ? `, ${r.hotkey.toUpperCase()}` : r.persona === 'fulfiller' ? 'New tab' : undefined,
      keywords: r.keywords,
      run: r.persona === 'fulfiller' ? () => window.open(`#${r.path}`, '_blank', 'noopener') : () => go(r.path),
    }))
    const extras: Command[] = [
      { id: 'theme', group: 'Appearance', label: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode', icon: theme === 'dark' ? 'sun' : 'moon', run: toggleTheme },
      { id: 'rail', group: 'Appearance', label: rail ? 'Expand the sidebar' : 'Collapse the sidebar', icon: 'columns', hint: '⌘ .', run: toggleRail },
      { id: 'keys', group: 'Help', label: 'Keyboard shortcuts', icon: 'keyboard', hint: '?', keywords: 'hotkeys bindings reference cheatsheet keys shortcut arrow leader', run: () => setKeysOpen(true) },
    ]
    return [...screens, ...extras]
  }, [theme, rail, toggleRail, toggleTheme])

  if (!chrome) {
    /* THE SAME PROVIDER THE CHROMED BRANCH SETS BELOW, MISSING HERE UNTIL ROUND 2's OWN REVIEW
       CAUGHT IT. The Fulfiller's route reads `hasChrome` false and returns here instead of
       falling through to the shell's own render, so a Modal opened from `route.view` (the "?"
       sheet, `Fulfillment.tsx`) called `usePageRoute()` against no provider at all and read
       `null` — never 'fulfiller' — and drew an IconButton's Close instead of the word (D5 spec
       rule 1). */
    return (
      <PageRouteContext.Provider value={route ?? null}>
        <RouteBoundary path={path} plain>
          {route === undefined ? <NoSuchView path={path} /> : <route.view />}
        </RouteBoundary>
      </PageRouteContext.Provider>
    )
  }

  return (
    <div className="bn-shell" data-rail={rail ? 'true' : undefined} data-route={route?.path ?? 'none'}>
      {/* THE FIRST TAB STOP ON EVERY SCREEN (UX-092): past the sidebar, to the screen. A button,
          not an `#anchor` link: the hash is this app's router. */}
      <button type="button" className="bn-skip" onClick={focusScreen}>
        Skip to the screen
      </button>
      <Sidebar
        path={path}
        rail={rail}
        onToggleRail={tabletRail ? undefined : toggleRail}
        armed={arm !== null}
        server={server}
        theme={theme}
        onToggleTheme={toggleTheme}
        onPalette={() => setPalette(true)}
      />
      <div className="bn-shell-main">
        <PhoneBar onPalette={() => setPalette(true)} />
        {server === 'offline' ? (
          <div className="bn-banner" role="alert">
            <Icon name="alert" size={16} />
            <span className="bn-grow">
              Banchi can’t reach the capture server. Screens will show stale or empty data until it answers.
            </span>
            <Button size="sm" variant="quiet" icon="refresh" onClick={retry}>
              Retry
            </Button>
          </div>
        ) : null}
        <div key={path} className="bn-view">
          {/* THE SCAFFOLD READS ITS ROUTE FROM HERE: a view that returns `<Page>` takes its h1
              from the route's `title ?? label` with no prop (D275). */}
          <PageRouteContext.Provider value={route ?? null}>
            <RouteBoundary path={path}>{route === undefined ? <NoSuchView path={path} /> : <route.view />}</RouteBoundary>
          </PageRouteContext.Provider>
        </div>
      </div>
      <TabBar path={path} drawerOpen={drawer} onMore={() => setDrawer(true)} />
      <Drawer open={drawer} path={path} onClose={() => setDrawer(false)} theme={theme} onToggleTheme={toggleTheme} server={server} />
      <CommandPalette open={palette} onClose={() => setPalette(false)} commands={commands} />
      <KeysSheet open={keysOpen} onClose={() => setKeysOpen(false)} path={path} />
      {/* THE ONE PLACE A REGISTERED SHEET IS DRAWN: `openSheet('product', …)` from any screen. */}
      <SheetHost />
      <WhichKey armed={arm !== null} />
      <Toaster />
    </div>
  )
}
