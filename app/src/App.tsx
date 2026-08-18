import { useEffect, useState } from 'react'
import type { ComponentType } from 'react'

import { CaptureScreen } from './CaptureScreen'
import { PullPreview } from './PullPreview'
import { ReviewQueue } from './ReviewQueue'
import { Inventory } from './Inventory'
import { Fulfillment } from './Fulfillment'
import { Gallery } from './Gallery'
import './App.css'

/* The app shell: six routes across two personas, and the chrome that moves between them.
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

type Route = {
  readonly path: string
  /** Utility face, uppercase — see App.css. Names the view, not the machinery behind it. */
  readonly label: string
  readonly view: ComponentType
  readonly persona: Persona
}

/* One table drives both the nav and the render. The alternative — a `ROUTES` array for the
 * chrome and a `switch` for the render — is more greppable and keeps two lists of the same
 * path strings that nothing checks agree. That is the drift D16 exists to catch, in
 * miniature, so the table wins and the switch is gone. It matters more at six routes than it
 * did at three, and it will matter more again at nine.
 *
 * ORDERED THE WAY THE OWNER WORKS, which is what a nav built from this table is read as: shoot
 * a box, answer what the run could not, look up what is in the boxes, check a position against
 * its photo. The Fulfiller's view and the component sheet sit after that run of four because
 * neither is a step in it.
 *
 * `persona` IS REQUIRED ON EVERY ROW rather than optional-and-defaulted. A new screen has to
 * say whose it is, and the cost of getting that wrong is asymmetric — an owner screen marked
 * `fulfiller` loses its nav, while a Fulfiller screen marked `owner` puts a strip of links to
 * the capture screen's hard-delete undo (D10) under the thumb of the person docs/DESIGN.md
 * says may reach no destructive action at all.
 */
const ROUTES: readonly Route[] = [
  { path: '/', label: 'Capture', view: CaptureScreen, persona: 'owner' },
  { path: '/review', label: 'Review queue', view: ReviewQueue, persona: 'owner' },
  { path: '/inventory', label: 'Inventory', view: Inventory, persona: 'owner' },
  { path: '/pull', label: 'Pull preview', view: PullPreview, persona: 'owner' },
  /* D5's second persona, and the one route here that is somebody else's whole product. It is
   * listed all the same: his device opens this hash and stays on it, but the owner needs a way
   * in to see what he sees, and a screen reachable only by typing a URL is a screen that gets
   * checked once. The link points INTO the view, which is not what the constraints table
   * forbids — that row is about routes OUT, and none exists once the nav stops rendering. */
  { path: '/fulfillment', label: 'Fulfillment', view: Fulfillment, persona: 'fulfiller' },
  // Step 6's component sheet, no longer the root. It stays in the build because a
  // component sheet that is rendered by the build is one that cannot go stale.
  { path: '/gallery', label: 'Gallery', view: Gallery, persona: 'owner' },
]

/* THE SHELL DRAWS NO CHROME OVER THE FULFILLER'S VIEW, and this is the decision this file
 * makes on 7b's behalf rather than a detail of it.
 *
 * docs/DESIGN.md's constraints table requires zero destructive actions reachable from that
 * view and asserts no route to settings or import. The nav is a strip of links to every other
 * screen, and the capture screen one of them reaches carries an undo that hard-deletes a
 * record, a sidecar and a photo (D10). It is also measured by the same table's other rows: the
 * links are 11px in the utility face, tap targets well under 44px, and set closer together
 * than 12px. Every one of those is correct on the owner's screens — "the owner's screens are a
 * tool — dense is fine" — and every one of them is a failure on his.
 *
 * NOT RENDERED, rather than hidden in CSS. Fulfillment.css carried a `display: none` rule
 * while this file was another group's, and said itself that it was a bridge: a component that
 * is not rendered cannot be reached by a keyboard, a screen reader or a stray tap, while
 * `display: none` earns those three properties by accident and loses them to one specificity
 * change. That rule is deleted; this is the fix it named.
 *
 * A SET RATHER THAN A `route.persona !== 'owner'` COMPARISON at the render, because the
 * question the shell asks is "does this view get chrome", and personas are not the only reason
 * an answer could be no. An unknown hash renders NoSuchView WITH the nav — that dead end is
 * the owner's, and the nav is the whole of what it tells him to do next.
 */
const CHROME_FREE: ReadonlySet<Persona> = new Set<Persona>(['fulfiller'])

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

/* An unknown hash renders this rather than falling back to the capture screen.
 *
 * The fallback was the obvious choice and is wrong here: the root route is the screen that
 * photographs cards into a box, so a stale bookmark or a typed '#/pulls' would land on a
 * live capture screen looking exactly like the view that was asked for. Per docs/DESIGN.md's
 * copy rules an error says what happened and what to do next, which is also why this names
 * the hash it could not resolve instead of saying "not found".
 */
function NoSuchView({ path }: { path: string }) {
  return (
    <main className="no-such-view">
      <p>
        No view at <code className="no-such-view-path">#{path}</code>.
      </p>
      <p>Pick one from the row above.</p>
    </main>
  )
}

export function App() {
  const path = useHashPath()
  const route = ROUTES.find((candidate) => candidate.path === path)
  const chrome = route === undefined || !CHROME_FREE.has(route.persona)

  return (
    <>
      {/* Plain anchors, no click handler. An href to a hash changes location and fires
          hashchange on its own, which is the whole reason hash routing costs nothing —
          intercepting the click to call a navigate() would add code to reproduce what the
          browser already does, and would break middle-click and open-in-new-tab with it. */}
      {chrome ? (
        <nav className="app-nav">
          {ROUTES.map((candidate) => (
            <a
              key={candidate.path}
              className="app-nav-link"
              href={`#${candidate.path}`}
              // aria-current, not a class name, because the current route is a fact about the
              // document rather than a style. App.css selects on it, so the two cannot drift.
              aria-current={candidate.path === path ? 'page' : undefined}
            >
              {candidate.label}
            </a>
          ))}
        </nav>
      ) : null}

      {route === undefined ? <NoSuchView path={path} /> : <route.view />}
    </>
  )
}
