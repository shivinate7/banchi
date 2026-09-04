import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentType, ErrorInfo, KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'
import { isEditableTarget } from './keys'
import { rememberRail, storedRail, storedTheme } from './deviceMemory'
import { getStatus, onServerBoot } from './server'
import { Button, Icon, Kbd, Logo, applyTheme, readTheme, useLeave, type IconName, type Theme } from './kit'
import { Toaster, toast } from './kit/toast'

import { Home } from './Home'
import { CaptureScreen } from './CaptureScreen'
import { Runs } from './Runs'
import { ReviewQueue } from './ReviewQueue'
import { Inventory } from './Inventory'
import { Pricing } from './Pricing'
import { Orders } from './Orders'
import { Shipping } from './Shipping'
import { Codes } from './Codes'
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
  /** What a person might TYPE to find this screen in the palette — the verbs it holds. */
  readonly keywords?: string
}

export const ROUTES: readonly Route[] = [
  { path: '/', label: 'Home', icon: 'home', view: Home, persona: 'owner', group: 'home', hotkey: 'h', nav: true, keywords: 'start overview' },
  { path: '/capture', label: 'Capture', icon: 'camera', view: CaptureScreen, persona: 'owner', group: 'work', hotkey: 'c', nav: true, tab: true, keywords: 'camera photograph scan feeder new box section' },
  { path: '/runs', label: 'Runs', icon: 'play', view: Runs, persona: 'owner', group: 'work', hotkey: 'r', nav: true, keywords: 'pipeline identify join emit reconcile import csv' },
  { path: '/review', label: 'Review', icon: 'inbox', view: ReviewQueue, persona: 'owner', group: 'work', hotkey: 'q', nav: true, tab: true, keywords: 'queue answer questions parked' },
  { path: '/pricing', label: 'Pricing', icon: 'tag', view: Pricing, persona: 'owner', group: 'work', hotkey: 'p', nav: true, keywords: 'price hold write files emit worklist' },
  { path: '/orders', label: 'Orders', icon: 'cart', view: Orders, persona: 'owner', group: 'sell', hotkey: 'o', nav: true, tab: true, keywords: 'pull sell fetch orders paste ledger' },
  { path: '/shipping', label: 'Shipping', icon: 'truck', view: Shipping, persona: 'owner', group: 'sell', hotkey: 's', nav: true, keywords: 'ship lanes envelope parcel export' },
  { path: '/inventory', label: 'Inventory', icon: 'box', view: Inventory, persona: 'owner', group: 'library', hotkey: 'i', nav: true, tab: true, keywords: 'boxes find a card where search sold retire move' },
  { path: '/codes', label: 'Codes', icon: 'qr', view: Codes, persona: 'owner', group: 'library', hotkey: 'd', nav: true, keywords: 'code cards qr redeem read a box' },
  { path: '/fulfillment', label: 'Cards to pull', icon: 'hand', view: Fulfillment, persona: 'fulfiller', group: 'aside' },
  { path: '/gallery', label: 'Kit', icon: 'grid', view: Gallery, persona: 'owner', group: 'aside' },
]

const GROUPS: readonly { readonly id: Group; readonly label: string | null }[] = [
  { id: 'home', label: null },
  { id: 'work', label: 'Workflow' },
  { id: 'sell', label: 'Sell' },
  { id: 'library', label: 'Library' },
]

/* THE GROUPS THE NAV DELIBERATELY DOES NOT DRAW, declared rather than implied.
 *
 * `aside` holds the two routes reached from somewhere other than the nav list: the
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

const CHROME_FREE: ReadonlySet<Persona> = new Set<Persona>(['fulfiller'])
const LEADER = ','
const CHORD_MS = 1000

function hasChrome(route: Route | undefined): boolean {
  return route !== undefined && !CHROME_FREE.has(route.persona)
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
const RING: readonly Route[] = ROUTES.filter((r) => r.hotkey !== undefined)
const STEP_SHORTCUTS = 'Meta+ArrowLeft Meta+ArrowRight'

function useRouteStep(enabled: boolean, path: string): void {
  useEffect(() => {
    if (!enabled) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey) return
      if (!event.metaKey && !event.ctrlKey) return
      if (isEditableTarget(event.target)) return
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

function useServerPresence(enabled: boolean): { state: ServerState; cards: number | null; retry: () => void } {
  const [state, setState] = useState<ServerState>('unknown')
  const [cards, setCards] = useState<number | null>(null)
  const check = useCallback(async () => {
    try {
      const status = await getStatus()
      setState('online')
      setCards(status.cards)
    } catch {
      setState('offline')
    }
  }, [])
  useEffect(() => {
    if (!enabled) return
    void check()
    const timer = window.setInterval(() => void check(), 15000)
    const onFocus = () => void check()
    window.addEventListener('focus', onFocus)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [enabled, check])
  useEffect(() => {
    if (!enabled) return
    return onServerBoot(() => {
      toast({ kind: 'status', icon: 'refresh', title: 'Server restarted', body: 'Banchi is running your latest code.' })
      void check()
    })
  }, [enabled, check])
  return { state, cards, retry: () => void check() }
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
   default, and above it there is room for the words. */
function readRail(): boolean {
  return storedRail() ?? window.innerWidth < 1280
}

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

    return (
      <main className="no-such-view">
        <div className="no-such-view-card bn-anim-in">
          <Logo size={40} />
          <h1 className="bn-title" style={{ marginTop: 16 }}>
            This screen stopped.
          </h1>
          <p className="bn-lede" style={{ marginTop: 8 }}>
            Something in it threw. Reloading the screen usually clears it; if not, the error below says what.
          </p>
          <p className="no-such-view-path" style={{ marginTop: 12 }}>
            {this.state.error.message}
          </p>
          <div className="no-such-view-doors">
            <button type="button" className="no-such-view-door" onClick={() => this.setState({ error: null })}>
              <Icon name="refresh" /> Reload this screen <Icon name="arrowRight" />
            </button>
            <a className="no-such-view-door" href="#/">
              <Icon name="home" /> Go home <Icon name="arrowRight" />
            </a>
          </div>
        </div>
      </main>
    )
  }
}

/* ---- unknown route -------------------------------------------------------------------- */
function NoSuchView({ path }: { path: string }) {
  return (
    <main className="no-such-view">
      <div className="no-such-view-card bn-anim-in">
        <Logo size={40} />
        <h1 className="bn-title" style={{ marginTop: 16 }}>
          Nothing lives at this address.
        </h1>
        <p className="bn-lede" style={{ marginTop: 8 }}>
          Banchi has no screen called <span className="no-such-view-path">#{path}</span>. Try one of these.
        </p>
        <div className="no-such-view-doors">
          <a className="no-such-view-door" href="#/">
            <Icon name="home" /> Home <Icon name="arrowRight" />
          </a>
          <a className="no-such-view-door" href="#/inventory">
            <Icon name="box" /> Inventory <Icon name="arrowRight" />
          </a>
          <a className="no-such-view-door" href="#/fulfillment" target="_blank" rel="noopener">
            <Icon name="hand" /> Cards to pull <Icon name="external" />
          </a>
        </div>
      </div>
    </main>
  )
}

/* ---- command palette -------------------------------------------------------------------- */
type Command = { readonly id: string; readonly group: string; readonly label: string; readonly icon: IconName; readonly hint?: string; readonly keywords?: string; readonly run: () => void }

function CommandPalette({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: readonly Command[] }) {
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!open) return
    setQuery('')
    setCursor(0)
    const timer = window.setTimeout(() => input.current?.focus(), 10)
    return () => window.clearTimeout(timer)
  }, [open])
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q === '') return commands
    return commands.filter((c) => `${c.group} ${c.label} ${c.hint ?? ''} ${c.keywords ?? ''}`.toLowerCase().includes(q))
  }, [commands, query])
  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(0, matches.length - 1)))
  }, [matches.length])
  const leave = useLeave(open)
  if (!leave.mounted) return null
  const leaving = leave.leaving ? 'true' : undefined
  const grouped: { group: string; items: Command[] }[] = []
  for (const command of matches) {
    const last = grouped[grouped.length - 1]
    if (last !== undefined && last.group === command.group) last.items.push(command)
    else grouped.push({ group: command.group, items: [command] })
  }
  let index = -1
  return (
    <>
      <div className="bn-scrim" onClick={onClose} data-leaving={leaving} />
      <div className="bn-cmdk" role="dialog" aria-label="Command palette" data-leaving={leaving}>
        <div className="bn-cmdk-input">
          <Icon name="search" size={18} className="bn-muted" />
          <input
            ref={input}
            value={query}
            placeholder="Jump to a screen…"
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
                const hit = matches[cursor]
                if (hit !== undefined) {
                  onClose()
                  hit.run()
                }
              } else if (event.key === 'Escape') {
                event.preventDefault()
                onClose()
              }
            }}
          />
          <Kbd>esc</Kbd>
        </div>
        <div className="bn-cmdk-list" role="listbox">
          {matches.length === 0 ? <div className="bn-cmdk-empty">Nothing matches “{query}”.</div> : null}
          {grouped.map((section) => (
            <div key={section.group}>
              <div className="bn-cmdk-group">{section.group}</div>
              {section.items.map((command) => {
                index += 1
                const at = index
                return (
                  <button
                    key={command.id}
                    type="button"
                    role="option"
                    aria-selected={at === cursor}
                    className="bn-cmdk-item"
                    onMouseEnter={() => setCursor(at)}
                    onClick={() => {
                      onClose()
                      command.run()
                    }}
                  >
                    <Icon name={command.icon} size={16} />
                    <span>{command.label}</span>
                    {command.hint ? <span className="bn-cmdk-item-hint">{command.hint}</span> : null}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
        <div className="bn-cmdk-foot">
          <span>
            <Kbd>↑</Kbd> <Kbd>↓</Kbd> move
          </span>
          <span>
            <Kbd>↵</Kbd> open
          </span>
          <span>
            <Kbd>,</Kbd> + letter jumps anywhere
          </span>
        </div>
      </div>
    </>
  )
}

/* ---- which-key overlay for the leader ------------------------------------------------------ */
function WhichKey({ armed }: { armed: boolean }) {
  if (!armed) return null
  return (
    <div className="bn-whichkey bn-anim-pop" role="status" aria-live="polite">
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
   THE ONLY PLACE THE PRODUCT SAYS IT IS KEYBOARD-DRIVEN. The rebuild took the inline ⌘←/⌘→
   keycaps out of the nav and the owner chose one reference over putting them back, so this
   sheet has to be COMPLETE: every binding, read out of the screen that owns it, grouped by
   where it applies. A screen's keys are dead while another screen is open and each group
   says so in a sentence rather than leaving it to be discovered.

   The caps here are written with a bare <kbd> rather than the kit's <Kbd>, which is
   aria-hidden — correct beside a labelled button, wrong here, where the key IS the content
   and a screen reader that skips it reads a list of verbs with no shortcuts in it. */

type Binding = {
  /** One entry per alternative that does the same thing; a chord is one string (`⌘K`, `,C`). */
  readonly keys: readonly string[]
  readonly does: string
  /** The condition, when the key is armed by something narrower than the screen. */
  readonly when?: string
  /** Read the caps as a sequence rather than as alternatives. */
  readonly seq?: boolean
}

type KeyGroup = {
  readonly id: string
  readonly title: string
  readonly icon: IconName
  readonly where: string
  /** The screen this group belongs to, so the sheet can offer the way there. */
  readonly at?: string
  readonly rows: readonly Binding[]
}

/* The capture screen's option keycaps, in its own order: `CaptureScreen.tsx` builds them by
   striking its twelve reserved letters out of `1234567890a…z`. Written out rather than
   summarised, because the nth key is the nth option and an operator counts along the row. */
const CAPTURE_OPTION_KEYS = '1234567890adeijklmnqwxyz'.toUpperCase().split('')

const SHORTCUTS: readonly KeyGroup[] = [
  {
    id: 'anywhere',
    title: 'Anywhere',
    icon: 'keyboard',
    where: 'Works on every one of your screens.',
    rows: [
      { keys: ['?'], does: 'Open this sheet' },
      { keys: ['⌘K', 'Ctrl K'], does: 'Open the command palette' },
      { keys: ['⌘←', '⌘→'], does: 'Step to the screen before or after this one, in workflow order' },
      { keys: ['⌘↑', '⌘↓'], does: 'The same step, for a keyboard without arrow pairs' },
      { keys: ['⌘.'], does: 'Collapse the sidebar to its rail, or open it again' },
      { keys: ['Esc'], does: 'Close whatever is over the screen — this sheet, the palette, the phone menu' },
    ],
  },
  {
    id: 'jump',
    title: 'Jump to a screen',
    icon: 'zap',
    where: 'Press the comma, then the letter. The letters appear on screen and you have a second to choose.',
    rows: [
      { keys: [',H'], does: 'Home' },
      { keys: [',C'], does: 'Capture' },
      { keys: [',R'], does: 'Runs' },
      { keys: [',Q'], does: 'Review' },
      { keys: [',P'], does: 'Pricing' },
      { keys: [',O'], does: 'Orders' },
      { keys: [',S'], does: 'Shipping' },
      { keys: [',I'], does: 'Inventory' },
      { keys: [',D'], does: 'Codes' },
    ],
  },
  {
    id: 'palette',
    title: 'The command palette',
    icon: 'command',
    where: 'Only while the palette is open.',
    rows: [
      { keys: ['↑', '↓'], does: 'Move down the list' },
      { keys: ['↵'], does: 'Run the highlighted command' },
      { keys: ['Esc'], does: 'Close it and leave the screen as it was' },
    ],
  },
  {
    id: 'capture',
    title: 'Capture',
    icon: 'camera',
    at: '/capture',
    where: 'Only while Capture is open.',
    rows: [
      { keys: ['C'], does: 'Take the photograph', when: 'while the trigger is on Manual' },
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
      {
        keys: CAPTURE_OPTION_KEYS,
        seq: true,
        does: 'Choose the option with that keycap beside it',
        when: 'while a field is open — the caps run in this order, and options past the last one are mouse-only',
      },
      { keys: ['↵'], does: 'Take the box you typed, or make a new one', when: 'in the Box field' },
      { keys: ['Esc'], does: 'Close the open field' },
    ],
  },
  {
    id: 'runs',
    title: 'Runs',
    icon: 'play',
    at: '/runs',
    where: 'Only while Runs is open.',
    rows: [{ keys: ['←', '→'], does: 'Walk the box, card by card', when: 'while a preview is on screen' }],
  },
  {
    id: 'review',
    title: 'Review',
    icon: 'inbox',
    at: '/review',
    where: 'Only while Review is open.',
    rows: [
      { keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], seq: true, does: 'Answer with that candidate — or that row of the export, while the lookup is open' },
      { keys: ['G'], does: 'Answer the whole group at once', when: 'when every card left asks the same question' },
      { keys: ['↵'], does: 'Confirm the group', when: 'while the group offer is up' },
      { keys: ['Esc'], does: 'Go back to one card at a time', when: 'while the group offer is up' },
      { keys: ['S'], does: 'Skip this card and come back to it' },
      { keys: ['C'], does: 'Clear the skips and start round again', when: 'when everything left is skipped' },
      { keys: ['X'], does: 'Close this question without answering it' },
      { keys: ['1', '2', '3', '4', '5', '6', '7'], seq: true, does: 'Pick the reason it is closed', when: 'while the close panel is up' },
      { keys: ['L'], does: 'Look this card up in the export' },
      { keys: ['Esc'], does: 'Leave the lookup, or the close panel, or the queue drawer' },
      { keys: ['R'], does: 'Reload the queue' },
      { keys: ['U'], does: 'Undo the newest answer' },
    ],
  },
  {
    id: 'pricing',
    title: 'Pricing',
    icon: 'tag',
    at: '/pricing',
    where: 'Only while Pricing is open. Everything but R and T is pressed inside a price field.',
    rows: [
      { keys: ['R'], does: 'Reload the worklist', when: 'not on a phone' },
      { keys: ['T'], does: 'Hold to read the price history of the row under the pointer; let go and it closes' },
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
      { keys: ['Esc'], does: 'Cancel the hold, or close the history, the photograph, the files dialog or the run picker' },
    ],
  },
  {
    id: 'inventory',
    title: 'Inventory',
    icon: 'box',
    at: '/inventory',
    where: 'Only while Inventory is open.',
    rows: [
      { keys: ['/'], does: 'Jump into the search field; Esc hands focus back and keeps what you typed' },
      { keys: ['←', '→'], does: 'Step to the card before or after this one in the walk' },
      { keys: ['PgUp', 'PgDn'], does: 'Jump by section', when: 'with the card list focused' },
      { keys: ['Home', 'End'], does: 'Go to the first or last card the filter leaves', when: 'with the card list focused' },
      { keys: ['X'], does: 'Tick the selected card', when: 'with the card list focused' },
      { keys: ['Esc'], does: 'Close the open sheet or panel' },
    ],
  },
  {
    id: 'orders',
    title: 'Orders',
    icon: 'cart',
    at: '/orders',
    where: 'Only while Orders is open, in the two-pane layout on a wide window.',
    rows: [
      { keys: ['J', '↓'], does: 'Select the next order' },
      { keys: ['K', '↑'], does: 'Select the order before it' },
    ],
  },
  {
    id: 'codes',
    title: 'Codes',
    icon: 'qr',
    at: '/codes',
    where: 'Only while Codes is open.',
    rows: [{ keys: ['Esc'], does: 'Close the open sheet' }],
  },
  {
    id: 'fulfillment',
    title: 'Cards to pull',
    icon: 'hand',
    where: 'The hand-off screen. It runs without this shell, so these two are all it answers to — and this sheet cannot be opened from it.',
    rows: [
      { keys: ['/'], does: 'Jump into the search field' },
      { keys: ['Esc'], does: 'Close the enlarged photograph' },
    ],
  },
]

const BINDING_COUNT = SHORTCUTS.reduce((total, group) => total + group.rows.length, 0)

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

function KeysSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null)
  const leave = useLeave(open)

  /* Focus comes back to whatever the operator was on. Keyed on `open` alone, so the restore
     fires the moment it closes rather than after the leave animation. */
  useEffect(() => {
    if (!open) return
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      if (before !== null && document.contains(before)) before.focus({ preventScroll: true })
    }
  }, [open])

  /* And focus goes INTO the sheet — on `leave.mounted` as well as `open`, because `useLeave`
     raises `mounted` from an effect: on the first render after the press the dialog is not in
     the document yet and the ref is still null. Focusing on `open` alone silently did nothing
     and left the operator's focus on the page behind the scrim. Tab then cycles inside. */
  useEffect(() => {
    if (!open || !leave.mounted) return
    const frame = window.requestAnimationFrame(() => panel.current?.focus({ preventScroll: true }))
    return () => window.cancelAnimationFrame(frame)
  }, [open, leave.mounted])

  if (!leave.mounted) return null
  const leaving = leave.leaving ? 'true' : undefined

  const trap = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab' || panel.current === null) return
    const stops = [...panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]')]
    const first = stops[0]
    const last = stops[stops.length - 1]
    if (first === undefined || last === undefined) return
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === panel.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <>
      <div className="bn-scrim" onClick={onClose} data-leaving={leaving} />
      <div
        ref={panel}
        className="bn-dialog app-keys"
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-keys-title"
        tabIndex={-1}
        onKeyDown={trap}
        data-leaving={leaving}
      >
        <header className="app-keys-head">
          <div className="app-keys-head-top">
            <h2 className="app-keys-title" id="app-keys-title">
              <Icon name="keyboard" size={20} />
              Keyboard shortcuts
            </h2>
            <Button variant="ghost" icon="x" kbd="Esc" onClick={onClose} className="app-keys-close">
              Close
            </Button>
          </div>
          {/* Its own line, at every width: beside the button it wrapped to five lines on a
              phone and pushed the first real row off the screen. */}
          <p className="app-keys-lede">
            Banchi is meant to be driven from the keyboard. Everything it answers to is here, in {BINDING_COUNT} entries
            — a row that shows several caps is a run of keys, not one. A screen’s own keys work only while that screen
            is open.
          </p>
        </header>

        <div className="app-keys-body">
          {SHORTCUTS.map((group) => (
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
                  <div
                    key={`${group.id}-${at}`}
                    className={row.keys.length > 3 ? 'app-keys-row app-keys-row-wide' : 'app-keys-row'}
                  >
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
        </div>

        <footer className="app-keys-foot">
          <span>
            <kbd className="bn-kbd">?</kbd> opens this sheet from anywhere, unless you are typing in a field.
          </span>
          <span className="app-keys-foot-end">
            <kbd className="bn-kbd">Esc</kbd> closes it
          </span>
        </footer>
      </div>
    </>
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

/* ---- sidebar ---------------------------------------------------------------------------------- */
function Sidebar({
  path,
  rail,
  onToggleRail,
  armed,
  server,
  cards,
  theme,
  onToggleTheme,
  onPalette,
}: {
  path: string
  rail: boolean
  onToggleRail: () => void
  armed: boolean
  server: ServerState
  cards: number | null
  theme: Theme
  onToggleTheme: () => void
  onPalette: () => void
}) {
  return (
    <aside className="bn-side">
      <a className="bn-brand" href="#/" aria-label="Banchi home">
        <Logo size={32} />
        <span className="bn-brand-text">
          <span className="bn-brand-name">Banchi</span>
          <span className="bn-brand-tag">every card has an address</span>
        </span>
      </a>
      <button type="button" className="bn-side-collapse" onClick={onToggleRail} aria-label={rail ? 'Expand the sidebar' : 'Collapse the sidebar'}>
        <Icon name={rail ? 'chevronRight' : 'chevronLeft'} size={14} />
      </button>
      <nav className="bn-nav app-nav" aria-label="Screens" aria-keyshortcuts={STEP_SHORTCUTS} data-armed={armed ? 'true' : undefined}>
        {GROUPS.map((group) => (
          <div key={group.id} className="bn-nav-group">
            {group.label ? <div className="bn-nav-group-label">{group.label}</div> : null}
            {ROUTES.filter((r) => r.group === group.id && inNav(r)).map((route) => (
              <NavLink key={route.path} route={route} current={route.path === path} />
            ))}
          </div>
        ))}
      </nav>
      <div className="bn-side-foot">
        <a className="bn-nav-link" href="#/fulfillment" target="_blank" rel="noopener" data-tip="Cards to pull">
          <Icon name="hand" size={18} />
          <span className="bn-nav-text">Cards to pull</span>
          <Icon name="external" size={14} className="bn-faint" />
        </a>
        <Button variant="ghost" icon="command" onClick={onPalette} data-tip="Search">
          <span className="bn-side-foot-text">Search</span>
          <Kbd>⌘K</Kbd>
        </Button>
        <Button variant="ghost" icon={theme === 'dark' ? 'sun' : 'moon'} onClick={onToggleTheme}>
          <span className="bn-side-foot-text">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        </Button>
        <div className="bn-server" data-state={server} title={server === 'offline' ? 'The capture server is not answering' : 'Capture server'}>
          <span className={`bn-dot ${server === 'online' ? 'bn-dot-ok' : server === 'offline' ? 'bn-dot-danger' : ''}`} />
          <span className="bn-side-foot-text">
            {server === 'online' ? 'Server online' : server === 'offline' ? 'Server offline' : 'Checking server…'}
            {server === 'online' && cards !== null ? <span className="bn-server-detail"> · {cards.toLocaleString()} cards</span> : null}
          </span>
        </div>
      </div>
    </aside>
  )
}

/* ---- phone chrome ------------------------------------------------------------------------------- */
/* Every owner screen draws its own h1 directly under this bar, so the bar carries the
   wordmark rather than repeating (or, on Codes, contradicting) the screen's name. */
function PhoneBar({ route, onMenu, onPalette }: { route: Route | undefined; onMenu: () => void; onPalette: () => void }) {
  return (
    <header className="bn-topbar">
      <a className="bn-topbar-brand" href="#/" aria-label="Banchi home">
        <Logo size={26} />
      </a>
      <span className="bn-topbar-title">{route === undefined ? 'Not found' : 'Banchi'}</span>
      <Button variant="ghost" icon="search" iconOnly onClick={onPalette}>
        Search
      </Button>
      <Button variant="ghost" icon="menu" iconOnly onClick={onMenu}>
        Menu
      </Button>
    </header>
  )
}

function TabBar({ path, onMore }: { path: string; onMore: () => void }) {
  const tabs = ROUTES.filter((r) => r.tab)
  return (
    <nav className="bn-tabbar" aria-label="Primary">
      {tabs.map((route) => (
        <a key={route.path} className="bn-tab-link" href={`#${route.path}`} aria-current={route.path === path ? 'page' : undefined}>
          <Icon name={route.icon} size={22} />
          <span>{route.label}</span>
        </a>
      ))}
      <button type="button" className="bn-tab-link" onClick={onMore}>
        <Icon name="more" size={22} />
        <span>More</span>
      </button>
    </nav>
  )
}

function Drawer({ open, path, onClose, theme, onToggleTheme, server }: { open: boolean; path: string; onClose: () => void; theme: Theme; onToggleTheme: () => void; server: ServerState }) {
  const leave = useLeave(open)
  if (!leave.mounted) return null
  const leaving = leave.leaving ? 'true' : undefined
  return (
    <>
      <div className="bn-scrim" onClick={onClose} data-leaving={leaving} />
      <div className="bn-sheet bn-sheet-left bn-drawer" role="dialog" aria-label="Screens" data-leaving={leaving}>
        <div className="bn-drawer-head">
          <a className="bn-brand" href="#/" onClick={onClose}>
            <Logo size={30} />
            <span className="bn-brand-text">
              <span className="bn-brand-name">Banchi</span>
              <span className="bn-brand-tag">every card has an address</span>
            </span>
          </a>
          <Button variant="ghost" icon="x" iconOnly onClick={onClose}>
            Close
          </Button>
        </div>
        <nav className="bn-nav" aria-label="All screens">
          {GROUPS.map((group) => (
            <div key={group.id} className="bn-nav-group">
              {group.label ? <div className="bn-nav-group-label">{group.label}</div> : null}
              {ROUTES.filter((r) => r.group === group.id && inNav(r)).map((route) => (
                <NavLink key={route.path} route={route} current={route.path === path} onNavigate={onClose} />
              ))}
            </div>
          ))}
        </nav>
        <div className="bn-side-foot">
          <a className="bn-nav-link" href="#/fulfillment" target="_blank" rel="noopener">
            <Icon name="hand" size={18} />
            <span className="bn-nav-text">Cards to pull</span>
            <Icon name="external" size={14} className="bn-faint" />
          </a>
          <Button variant="ghost" icon={theme === 'dark' ? 'sun' : 'moon'} onClick={onToggleTheme}>
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </Button>
          <div className="bn-server" data-state={server}>
            <span className={`bn-dot ${server === 'online' ? 'bn-dot-ok' : server === 'offline' ? 'bn-dot-danger' : ''}`} />
            {server === 'online' ? 'Server online' : server === 'offline' ? 'Server offline' : 'Checking server…'}
          </div>
        </div>
      </div>
    </>
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
  const [theme, toggleTheme] = useTheme()
  const [palette, setPalette] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [keysOpen, setKeysOpen] = useState(false)
  const { state: server, cards, retry } = useServerPresence(chrome)

  useEffect(() => {
    const name = route?.label ?? 'Not found'
    document.title = route?.persona === 'fulfiller' ? 'Cards to pull' : route?.path === '/' ? 'Banchi' : `${name} · Banchi`
  }, [route])

  useEffect(() => {
    setDrawer(false)
    setPalette(false)
    setKeysOpen(false)
  }, [path])

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
        event.preventDefault()
        toggleRail()
        return
      }
      /* `?` IS THE ONLY UNMODIFIED KEY THE SHELL TAKES, and it yields to typing. A question
         mark is a legitimate character in a box name, a card name and a search — `keys.ts`
         is the one place that judgement is made and every other handler in the app already
         asks it. The palette's own input answers to the same test, so `?` typed there is
         typed and not swallowed. */
      if (event.key === '?' && !event.repeat && !isEditableTarget(event.target)) {
        event.preventDefault()
        setKeysOpen(true)
        return
      }
      if (event.key === 'Escape') {
        setPalette(false)
        setDrawer(false)
        setKeysOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [chrome, toggleRail])

  const commands = useMemo<Command[]>(() => {
    const goTo: Command[] = ROUTES.filter((r) => r.nav).map((r) => ({
      id: `go:${r.path}`,
      group: 'Go to',
      label: r.label,
      icon: r.icon,
      hint: r.hotkey ? `, ${r.hotkey.toUpperCase()}` : undefined,
      keywords: r.keywords,
      run: () => go(r.path),
    }))
    const extras: Command[] = [
      { id: 'pull', group: 'Hand-off', label: 'Open Cards to pull in a new tab', icon: 'hand', run: () => window.open('#/fulfillment', '_blank') },
      { id: 'theme', group: 'Appearance', label: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode', icon: theme === 'dark' ? 'sun' : 'moon', run: toggleTheme },
      { id: 'rail', group: 'Appearance', label: rail ? 'Expand the sidebar' : 'Collapse the sidebar', icon: 'columns', hint: '⌘ .', run: toggleRail },
      { id: 'keys', group: 'Help', label: 'Keyboard shortcuts', icon: 'keyboard', hint: '?', keywords: 'hotkeys bindings reference cheatsheet keys shortcut arrow leader', run: () => setKeysOpen(true) },
      { id: 'kit', group: 'Developer', label: 'Component kit', icon: 'grid', run: () => go('/gallery') },
    ]
    return [...goTo, ...extras]
  }, [theme, rail, toggleRail, toggleTheme])

  if (!chrome) {
    return (
      <RouteBoundary path={path} plain>
        {route === undefined ? <NoSuchView path={path} /> : <route.view />}
      </RouteBoundary>
    )
  }

  return (
    <div className="bn-shell" data-rail={rail ? 'true' : undefined} data-route={route?.path ?? 'none'}>
      <Sidebar
        path={path}
        rail={rail}
        onToggleRail={toggleRail}
        armed={arm !== null}
        server={server}
        cards={cards}
        theme={theme}
        onToggleTheme={toggleTheme}
        onPalette={() => setPalette(true)}
      />
      <div className="bn-shell-main">
        <PhoneBar route={route} onMenu={() => setDrawer(true)} onPalette={() => setPalette(true)} />
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
          <RouteBoundary path={path}>{route === undefined ? <NoSuchView path={path} /> : <route.view />}</RouteBoundary>
        </div>
      </div>
      <TabBar path={path} onMore={() => setDrawer(true)} />
      <Drawer open={drawer} path={path} onClose={() => setDrawer(false)} theme={theme} onToggleTheme={toggleTheme} server={server} />
      <CommandPalette open={palette} onClose={() => setPalette(false)} commands={commands} />
      <KeysSheet open={keysOpen} onClose={() => setKeysOpen(false)} />
      <WhichKey armed={arm !== null} />
      <Toaster />
    </div>
  )
}
