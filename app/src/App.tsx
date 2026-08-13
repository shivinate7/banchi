import { useEffect, useState } from 'react'
import type { ComponentType } from 'react'

import { CaptureScreen } from './CaptureScreen'
import { PullPreview } from './PullPreview'
import { Gallery } from './Gallery'
import './App.css'

/* The app shell: three owner-side routes and the chrome that moves between them.
 *
 * Hash routing, hand-written. A router library was the alternative and it loses on every
 * axis that matters here: three routes, no path parameters, no nested layouts, no data
 * loaders, one user. What it would buy is a dependency to keep current and an API the
 * next session has to know; what it would replace is one listener and one lookup, small
 * enough to read in full rather than trust.
 *
 * Hash rather than the History API for a second, separate reason: pushState paths need
 * whatever serves the bundle to rewrite unknown paths back to index.html. That is Vite
 * today and something unnamed on the Mac at Gate B, and a route that breaks depending on
 * who is serving is a bad trade for a prettier URL. A hash never reaches a server.
 */

type Route = {
  readonly path: string
  /** Utility face, uppercase — see App.css. Names the view, not the machinery behind it. */
  readonly label: string
  readonly view: ComponentType
}

/* One table drives both the nav and the render. The alternative — a `ROUTES` array for the
 * chrome and a `switch` for the render — is more greppable and keeps two lists of the same
 * three strings that nothing checks agree. That is the drift D16 exists to catch, in
 * miniature, so the table wins and the switch is gone.
 */
const ROUTES: readonly Route[] = [
  { path: '/', label: 'Capture', view: CaptureScreen },
  { path: '/pull', label: 'Pull preview', view: PullPreview },
  // Step 6's component sheet, no longer the root. It stays in the build because a
  // component sheet that is rendered by the build is one that cannot go stale.
  { path: '/gallery', label: 'Gallery', view: Gallery },
]

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

  return (
    <>
      {/* Plain anchors, no click handler. An href to a hash changes location and fires
          hashchange on its own, which is the whole reason hash routing costs nothing —
          intercepting the click to call a navigate() would add code to reproduce what the
          browser already does, and would break middle-click and open-in-new-tab with it. */}
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

      {route === undefined ? <NoSuchView path={path} /> : <route.view />}
    </>
  )
}
