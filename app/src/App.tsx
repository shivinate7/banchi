import { useEffect, useState } from 'react'
import { isEditableTarget } from './keys'
import type { ComponentType } from 'react'

import { CaptureScreen } from './CaptureScreen'
import { PullPreview } from './PullPreview'
import { ReviewQueue } from './ReviewQueue'
import { Inventory } from './Inventory'
import { Boxes } from './Boxes'
import { Fulfillment } from './Fulfillment'
import { Gallery } from './Gallery'
import './App.css'

/* The app shell: seven routes across two personas, and the chrome that moves between them.
 *
 * Hash routing, hand-written. A router library was the alternative and it loses on every
 * axis that matters here: a flat list of routes, no path parameters, no nested layouts, no
 * data loaders, two devices. What it would buy is a dependency to keep current and an API the
 * next session has to know; what it would replace is one listener and one lookup, small
 * enough to read in full rather than trust. 7b doubled the route count and added a second
 * persona without touching either, which is the case that argument was made against.
 *
 * Hash rather than the History API for a second, separate reason: pushState paths need
 * whatever serves the bundle to rewrite unknown paths back to index.html. That is Vite
 * today and something unnamed on the Mac at Gate B, and a route that breaks depending on
 * who is serving is a bad trade for a prettier URL. A hash never reaches a server.
 */

/** Whose screen this is. D5's split, carried in the route table because it is the only place
 *  that can act on it — see `CHROME_FREE` below for the one thing it decides. */
type Persona = 'owner' | 'fulfiller'

/* HOW OFTEN THE OWNER IS IN A SCREEN, which is the only thing the nav's shape encodes.
 *
 * The nav was a flat row of links when there were three routes and it stayed one at seven, so
 * `Gallery` — a component sheet that exists to keep step 6's button from going stale — was
 * drawn exactly as loudly as the screen the owner spends an hour a day in. A row where
 * everything is equally important has thrown away the only thing it knows.
 *
 *   run    the loop a session actually is: shoot a box, then answer what the run could not.
 *   look   the questions that arrive while doing it — what is in the boxes, how this box is
 *          laid out, what is at this position. Reached when asked, not on a rhythm.
 *   aside  not the owner's work at all. The Fulfiller's whole product, which the owner opens
 *          to see what he sees; and the component sheet.
 *
 * ONE AXIS AND NOT TWO. Grouping by persona was the obvious alternative and it is the wrong
 * cut: it puts Fulfillment alone on one side and the other six together on the other, which
 * is a fact the nav already carries in a much stronger form — his view is the one this nav
 * does not render over at all. Cadence is the fact the row was missing.
 */
type Group = 'run' | 'look' | 'aside'

type Route = {
  readonly path: string
  /** Utility face, uppercase — see App.css. Names the view, not the machinery behind it. */
  readonly label: string
  readonly view: ComponentType
  readonly persona: Persona
  readonly group: Group
  /** Second key of the `,` chord — see `LEADER`. Absent means the route has no key and draws
   *  no chip: docs/DESIGN.md's "every choice shows its key" runs in both directions, and a
   *  chip for a key nothing binds is worse than no chip at all. */
  readonly hotkey?: string
}

/* One table drives both the nav and the render. The alternative — a `ROUTES` array for the
 * chrome and a `switch` for the render — is more greppable and keeps two lists of the same
 * path strings that nothing checks agree. That is the drift D16 exists to catch, in
 * miniature, so the table wins and the switch is gone. It matters more at seven routes than it
 * did at three, and it will matter more again at nine.
 *
 * ORDERED THE WAY THE OWNER WORKS, which is what a nav built from this table is read as: shoot
 * a box, answer what the run could not, look up what is in the boxes — and sell a copy out of
 * them — then see how a box is laid out, then check a position against its photo. The
 * Fulfiller's view and the component sheet sit after that run of five because neither is a
 * step in it. `group` now says that out loud rather than leaving it to the order alone, which
 * is a fact the reader had to already know to see.
 *
 * `persona` IS REQUIRED ON EVERY ROW rather than optional-and-defaulted. A new screen has to
 * say whose it is, and the cost of getting that wrong is asymmetric — an owner screen marked
 * `fulfiller` loses its nav, while a Fulfiller screen marked `owner` puts a strip of links to
 * the capture screen's hard-delete undo (D10) under the thumb of the person docs/DESIGN.md
 * says may reach no destructive action at all. `group` is required for the same reason one
 * step down: a new screen that does not say how often it is used gets drawn as though it were
 * used constantly, which is the defect this field was added to fix.
 */
const ROUTES: readonly Route[] = [
  { path: '/', label: 'Capture', view: CaptureScreen, persona: 'owner', group: 'run', hotkey: 'c' },
  {
    path: '/review',
    label: 'Review queue',
    view: ReviewQueue,
    persona: 'owner',
    group: 'run',
    hotkey: 'r',
  },
  {
    path: '/inventory',
    label: 'Inventory',
    view: Inventory,
    persona: 'owner',
    group: 'look',
    hotkey: 'i',
  },
  /* The boxes, after the inventory rather than before it, because that is the order the
   * questions arrive in: what is in the boxes, and then how this box is laid out. D20 makes a
   * box an object with a name, a divider layout and a lid — this is the only screen where any
   * of the four can be set, and the only one that can register a box before a card lands in
   * it. Owner-side without a second thought: sealing a box freezes a number every fraction in
   * the product then divides by. */
  { path: '/boxes', label: 'Boxes', view: Boxes, persona: 'owner', group: 'look', hotkey: 'b' },
  {
    path: '/pull',
    label: 'Pull preview',
    view: PullPreview,
    persona: 'owner',
    group: 'look',
    hotkey: 'p',
  },
  /* D5's second persona, and the one route here that is somebody else's whole product. It is
   * listed all the same: his device opens this hash and stays on it, but the owner needs a way
   * in to see what he sees, and a screen reachable only by typing a URL is a screen that gets
   * checked once. The link points INTO the view, which is not what the constraints table
   * forbids — that row is about routes OUT, and none exists once the nav stops rendering.
   *
   * NO HOTKEY, and the reason is that same missing way out rather than tidiness. This view
   * renders no chrome, so a mistyped chord landing on it would strand whoever pressed it in a
   * room with no door — they would have to know to type a hash to leave. A route reachable
   * only by a deliberate click cannot be arrived at by accident. */
  {
    path: '/fulfillment',
    label: 'Fulfillment',
    view: Fulfillment,
    persona: 'fulfiller',
    group: 'aside',
  },
  // Step 6's component sheet, no longer the root. It stays in the build because a
  // component sheet that is rendered by the build is one that cannot go stale. No hotkey:
  // it is not a step in any loop, and the keys exist for the loop.
  { path: '/gallery', label: 'Gallery', view: Gallery, persona: 'owner', group: 'aside' },
]

/** Drawn in this order, and the only place the group order is fixed. Deriving it from the
 *  order rows happen to appear in `ROUTES` would make a re-ordered table silently re-order
 *  the nav's groups too. */
const GROUP_ORDER: readonly Group[] = ['run', 'look', 'aside']

/* THE SHELL DRAWS NO CHROME OVER THE FULFILLER'S VIEW, and this is the decision this file
 * makes on 7b's behalf rather than a detail of it.
 *
 * docs/DESIGN.md's constraints table requires zero destructive actions reachable from that
 * view and asserts no route to settings or import. The nav is a strip of links to every other
 * screen, and the capture screen one of them reaches carries an undo that hard-deletes a
 * record, a sidecar and a photo (D10). It is also measured by the same table's other rows: the
 * links are small, in the utility face, with tap targets well under 44px and set closer
 * together than 12px. Every one of those is correct on the owner's screens — "the owner's
 * screens are a tool — dense is fine" — and every one of them is a failure on his.
 *
 * NOT RENDERED, rather than hidden in CSS. Fulfillment.css carried a `display: none` rule
 * while this file was another group's, and said itself that it was a bridge: a component that
 * is not rendered cannot be reached by a keyboard, a screen reader or a stray tap, while
 * `display: none` earns those three properties by accident and loses them to one specificity
 * change. That rule is deleted; this is the fix it named.
 *
 * A SET RATHER THAN A `route.persona !== 'owner'` COMPARISON at the render, because the
 * question the shell asks is "does this view get chrome", and personas are not the only reason
 * an answer could be no. AN UNRESOLVED HASH IS THE SECOND REASON, and it is not a persona at
 * all — see `hasChrome` below, which is where that answer is now decided.
 */
const CHROME_FREE: ReadonlySet<Persona> = new Set<Persona>(['fulfiller'])

/* CHROME IS DRAWN FOR A KNOWN OWNER ROUTE AND FOR NOTHING ELSE. The `route === undefined ||`
 * that used to open this expression is the hazard this function exists to close.
 *
 * The old reading was that an unresolved hash is the owner's dead end, so it should keep his
 * nav as the way out of it. That is a guess about who is looking, made by the one part of the
 * app that cannot possibly know: a hash is whatever the browser was pointed at, and a stale
 * bookmark, a mistyped character or a link from an old note reaches this branch identically on
 * either device. D5's second persona is a retired, non-technical family member whose device is
 * supposed to open exactly one screen and stay on it — and the nav the old branch handed him
 * is a row of small links to the capture screen, whose undo hard-deletes a record, its sidecar
 * and its photo with no backup (D10). Every other line in this file spends real effort keeping
 * that strip off his device; a mistyped hash walked around all of it.
 *
 * SO THE SAFE READING IS THE FULFILLER'S, and it is chosen because the two wrong answers cost
 * wildly different amounts. Read it as his and be wrong, and the owner — who knows every route
 * in this app by name — loses one click on a page that hands him a labelled way back. Read it
 * as the owner's and be wrong, and a person who has never seen the owner's screens is handed
 * them, at a density docs/DESIGN.md's constraints table says he cannot read, with a
 * hard-delete two taps away. An asymmetric cost decides an unknowable question; it does not
 * need to be resolved, only survived.
 *
 * WHAT REPLACES THE NAV IS NOT NOTHING — see `NoSuchView`, which answers the question this
 * branch refuses to guess at by asking it out loud and drawing one door per persona.
 */
function hasChrome(route: Route | undefined): boolean {
  return route !== undefined && !CHROME_FREE.has(route.persona)
}

/* ---- the keyboard ---- */

/* A LEADER KEY AND THEN A ROUTE'S INITIAL, e.g. `,` then `r` for the review queue.
 *
 * docs/DESIGN.md is direct about the owner's side — "an hour in the queue is a keyboard and
 * not a mouse", "Every choice shows its key" — and the nav was the one owner-side control in
 * the product with no key at all. What stopped it being a bare letter is that the letter space
 * is contested and getting more so: `c` and `u` are the capture screen's, `s` and `c` and the
 * digits are the review queue's, `/` is the search field's, the arrows are the pull preview's,
 * and a picker landing on the capture screen wants more of them. A bare `n` for the next
 * screen would work on the day it was written and quietly fire twice a fortnight later, on
 * somebody else's screen, in somebody else's file.
 *
 * A CHORD IS NOT MERELY A WAY TO FIND FREE KEYS — it is what makes the collision impossible
 * rather than unlikely. While the leader is armed the next keydown is consumed here and
 * delivered nowhere else (see the capture-phase listener below), so a route key may be a
 * letter another screen has already bound: `,` then `c` reaches the capture screen and does
 * not also take a photograph. Every route therefore gets its own initial, which is the only
 * mapping with nothing to memorise. A scheme where Capture had to be some other letter because
 * `c` was taken would be a scheme the owner has to learn.
 *
 * PUNCTUATION FOR THE LEADER, DELIBERATELY. Every contested key in the paragraph above is a
 * letter or a digit, because every one of them is a mnemonic for something on its screen. `,`
 * is nobody's mnemonic, it is unshifted, and it is what vim's leader convention already trains
 * the fingers to do. `g`, the other obvious choice — gmail and github both use it for exactly
 * this — was rejected precisely because it IS a mnemonic: the picker arriving on the capture
 * screen is a game and rarity picker, and `g` is the first letter it will reach for.
 *
 * WHAT IS BOUND AND WHAT IS NOT: the five routes of the run and the lookups, none of the
 * aside. See the `aside` rows in ROUTES for why Fulfillment in particular must not have one.
 *
 * MODIFIERS ARE NEVER PART OF IT. A held Cmd, Ctrl or Alt returns before anything else
 * happens, exactly as trigger.ts, ReviewQueue.tsx and PullPreview.tsx all do: Cmd-comma is
 * the browser's and the OS's, and a shell that eats it has broken something it does not own.
 * Shift is left off that list for trigger.ts's reason — it does not change which key was
 * pressed, and a held Shift silently killing the nav is the worse of the two failures.
 */
const LEADER = ','

/* HOW LONG THE LEADER STAYS ARMED. An armed leader eats the next keystroke, so a leader that
 * never expired would turn one stray comma into a keystroke lost an hour later, on a screen
 * where that keystroke was an answer or a capture. Long enough to be a deliberate two-key
 * sequence typed by a hand that paused to think; short enough that an accident has cost its
 * one key before you notice. Not a token — this is a duration and not a measurement, and
 * docs/DESIGN.md's scale is spacing. */
const CHORD_MS = 1500


/** `location.hash` as a route path: '' and '#' and '#/' all mean the root. */
function currentPath(): string {
  const raw = window.location.hash.replace(/^#/, '')
  if (raw === '') return '/'
  // Strip one trailing slash so '#/pull/' is not a fourth route that renders nothing.
  // Guarded on length so the root itself survives.
  return raw.length > 1 ? raw.replace(/\/$/, '') : raw
}

function useHashPath(): string {
  const [path, setPath] = useState(currentPath)

  useEffect(() => {
    const read = () => setPath(currentPath())
    window.addEventListener('hashchange', read)
    // Read once on subscribe as well. Between the first render and this effect the hash
    // can already have moved — StrictMode's double-invoke is the cheap case, a hash set
    // during module init is the real one — and a listener alone would never see it.
    read()
    return () => window.removeEventListener('hashchange', read)
  }, [])

  return path
}

/* The leader, armed. Returns null when it is not, and a token that changes on every arm when
 * it is — a boolean would work for the rendering and not for the timer, because re-arming has
 * to restart the countdown and `true` set to `true` again is not a change React can see.
 *
 * `enabled` is the chrome decision, passed in rather than re-derived. A screen with no nav has
 * no keys: on the Fulfiller's view because a keyboard route out is exactly the route out the
 * constraints table forbids, and on the unresolved-hash page because that page is the one
 * place in the app that does not know whose it is, which is the whole of the argument at
 * `hasChrome`. Both fall out of one condition, which is the reason that function returns a
 * boolean about chrome rather than an answer about personas.
 */
function useLeader(enabled: boolean): number | null {
  const [arm, setArm] = useState<number | null>(null)

  useEffect(() => {
    if (!enabled) {
      setArm(null)
      return
    }

    /* CAPTURE PHASE, AND IT IS THE MECHANISM RATHER THAN A DETAIL. A listener registered on
     * `window` for the capture phase is the first one the browser calls for any keydown,
     * before every listener on `document`, on React's root container and on any element, in
     * either phase. `stopPropagation` there is what lets the second key of a chord be a letter
     * another screen has bound: the press is consumed before that screen is offered it.
     *
     * It assumes no other listener in the app registers in the capture phase, where order
     * would fall back to registration order. Nothing does today — trigger.ts, ReviewQueue.tsx,
     * PullPreview.tsx, Inventory.tsx and SearchField.tsx all bubble — and this comment is
     * where a future capture-phase listener will find out that it has a conflict.
     *
     * The bluntness is bounded by the arming, which is the reason this is safe to do at all:
     * unarmed, this handler compares one key and returns. It can only swallow a keystroke that
     * the owner asked it to swallow, one press earlier, on a screen whose chrome is telling
     * him it is armed.
     */
    const onKeyDown = (event: KeyboardEvent) => {
      // The browser's and the OS's. Cmd-comma in particular is a real shortcut on this rig.
      if (event.metaKey || event.ctrlKey || event.altKey) return
      // A comma typed into the set hint is a comma, not a leader.
      if (isEditableTarget(event.target)) return

      if (event.key === LEADER) {
        /* Arming, or re-arming and restarting the clock. Held down, this is the branch a
         * repeat lands in as well, so a leaned-on comma stays armed instead of oscillating
         * between armed and disarmed as each repeat is read as a second key. */
        event.preventDefault()
        event.stopPropagation()
        setArm((previous) => (previous ?? 0) + 1)
        return
      }

      if (arm === null) return

      /* ARMED: THIS PRESS BELONGS TO THE NAV AND TO NOTHING ELSE, whatever it is. One rule and
       * no exceptions, including Escape and including a key that names no route.
       *
       * Letting an unrecognised second key through was the alternative and it is the one that
       * bites: `,` then `3` would fall through to the review queue and write an answer, and `,`
       * then `u` would fall through to the capture screen and delete a card. The cost of the
       * rule as written is one lost keystroke after a stray comma; the cost of the other rule
       * is a write nobody asked for. It is also the simpler sentence to hold in your head,
       * which is what makes the chips lighting up in the nav a complete explanation of what is
       * about to happen.
       */
      event.preventDefault()
      event.stopPropagation()
      setArm(null)

      const target = ROUTES.find((candidate) => candidate.hotkey === event.key.toLowerCase())
      if (target === undefined) return
      window.location.hash = `#${target.path}`
    }

    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [enabled, arm])

  /* Two ways to disarm without pressing anything: time, and leaving. The blur case is the one
   * that would otherwise be a trap — tab away with a leader armed, come back an hour later,
   * and the first key you press is eaten by a chord you have forgotten starting. */
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

/* An unknown hash renders this rather than falling back to the capture screen.
 *
 * The fallback was the obvious choice and is wrong here: the root route is the screen that
 * photographs cards into a box, so a stale bookmark or a typed '#/pulls' would land on a
 * live capture screen looking exactly like the view that was asked for. Per docs/DESIGN.md's
 * copy rules an error says what happened and what to do next, which is also why this names
 * the hash it could not resolve instead of saying "not found".
 *
 * IT NOW DRAWS ITS OWN WAY OUT, because as of `hasChrome` there is no nav above it to be the
 * way out. That is not a consolation prize for losing the nav — it is the better answer, and
 * the nav was only ever standing in for it. The nav is seven links at a density docs/DESIGN.md
 * says one of this app's two users cannot read; this is two doors, one per persona, and the
 * page can hand them over without having to decide which of the two people is holding it.
 *
 * SO IT IS DRAWN TO THE FULFILLER'S FLOORS — 20px body, 44px targets, 12px apart, no word from
 * the banned list — and drawn that way for the same reason `hasChrome` reads the ambiguity his
 * way. His floors are legible to the owner; the owner's density is not legible to him. Meeting
 * the stricter of the two standards is what "cannot know who is looking" cashes out to when
 * something actually has to be rendered. None of it is asserted by
 * app/tests/fulfillment.spec.ts, whose battery is scoped to his view and should stay scoped to
 * it: this page is not his view, it is the page that might be.
 *
 * HIS DOOR IS FIRST AND THE OWNER'S IS SECOND, on the same asymmetry. The owner reads two
 * labels and takes the second; the person who has trouble reading small print takes the first
 * thing on the page, and the first thing on the page is his.
 *
 * NO ACCENT FILL ON EITHER, which docs/DESIGN.md decides for us: solid accent means there is
 * exactly one thing to do, and "a screen with two answers gets no fill". Filling his door
 * would be the shell claiming to know an answer it has just finished admitting it does not
 * have.
 */
function NoSuchView({ path }: { path: string }) {
  return (
    <main className="no-such-view">
      <h1 className="no-such-view-title">Nothing is at this address.</h1>
      <p className="no-such-view-say">This screen was asked for:</p>
      <p className="no-such-view-path">#{path}</p>
      <p className="no-such-view-say">There is no screen with that name. Go to one of these:</p>
      {/* Named exactly as their own screens name them. docs/DESIGN.md's copy rules: an action
          keeps its name through the whole flow, and "Cards to pull" is the heading of the view
          this door opens. A door labelled with a description of a screen is a door you have to
          read twice. */}
      <a className="no-such-view-door" href="#/fulfillment">
        Cards to pull
      </a>
      <a className="no-such-view-door" href="#/">
        Capture
      </a>
    </main>
  )
}

export function App() {
  const path = useHashPath()
  const route = ROUTES.find((candidate) => candidate.path === path)
  const chrome = hasChrome(route)
  const arm = useLeader(chrome)

  return (
    <>
      {/* Plain anchors, no click handler. An href to a hash changes location and fires
          hashchange on its own, which is the whole reason hash routing costs nothing —
          intercepting the click to call a navigate() would add code to reproduce what the
          browser already does, and would break middle-click and open-in-new-tab with it. */}
      {chrome ? (
        <nav
          className="app-nav"
          aria-label="Screens"
          /* The armed leader, on the element the keys belong to. An attribute rather than a
             class for aria-current's reason one line down: it is a fact about the document,
             App.css selects on it, and the two cannot drift. Undefined rather than "false"
             so the attribute is absent when it is not armed — `[data-armed]` then means what
             it says. */
          data-armed={arm === null ? undefined : 'true'}
        >
          {GROUP_ORDER.map((group) => (
            /* A group is a div and not a second <nav> or a <ul>. The links are already in a
               navigation landmark with a name, and cadence is a fact about how loudly to draw
               them rather than a fact a screen reader has any use for — a second landmark, or
               three, would announce a structure the owner did not ask about every time he
               enters the chrome. What the grouping is for is entirely visual: see App.css. */
            <div key={group} className={`app-nav-group app-nav-group-${group}`}>
              {ROUTES.filter((candidate) => candidate.group === group).map((candidate) => (
                <a
                  key={candidate.path}
                  className="app-nav-link"
                  href={`#${candidate.path}`}
                  // aria-current, not a class name, because the current route is a fact about the
                  // document rather than a style. App.css selects on it, so the two cannot drift.
                  aria-current={candidate.path === path ? 'page' : undefined}
                >
                  {candidate.label}
                  {candidate.hotkey === undefined ? null : (
                    /* aria-hidden, unlike the chips on the review queue and the pull preview.
                       Those sit beside a control and label it; this one sits INSIDE the link,
                       so without it every route announces itself as "Capture ,C" — the hint
                       swallowed into the name of the thing it was hinting at. The keys are
                       drawn for an eye on a row it has already learned, and a screen-reader
                       user reaching this nav is on the tab key rather than the chord. */
                    <kbd className="app-nav-key" aria-hidden="true">
                      {LEADER}
                      {candidate.hotkey.toUpperCase()}
                    </kbd>
                  )}
                </a>
              ))}
            </div>
          ))}
        </nav>
      ) : null}

      {route === undefined ? <NoSuchView path={path} /> : <route.view />}
    </>
  )
}
