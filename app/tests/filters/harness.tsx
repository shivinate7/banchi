import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '../../src/tokens.css'
import '../../src/base.css'
import '../../src/kit.css'

import { FilterSpecimens } from '../../src/kit/filters.specimens'
import { useFacetParams, useSortParam, useViewFlag, useViewParam } from '../../src/kit/viewState'

/* THE TEST PAGE FOR THE FILTER BAR AND THE URL VIEW STATE (mirrors `tests/kit-data/`'s own
 * harness: no router, no store, no server — `filters.spec.ts` does not wait on a real screen to
 * mount either of these). `?theme=dark` draws the dark theme, same as `kit-data`'s page; the
 * view-state demo below reads and writes the HASH's own query string, which is a different
 * thing from `window.location.search` and so never collides with the theme flag. */

const FACET_KEYS = ['game'] as const

/** Every `viewState.ts` hook, bound to one small block of text and a few presses, so a spec can
 *  drive the URL and read back what each hook thinks the URL says — the one thing no
 *  screenshot can show. */
function ViewStateDemo() {
  const [q, setQ] = useViewParam('q')
  const [hide, setHide] = useViewFlag('hide')
  const [facets, setFacets] = useFacetParams(FACET_KEYS)
  const [sort, setSort] = useSortParam<'name' | 'price'>({ key: 'name', dir: 'asc' })

  return (
    <section data-view-state-demo style={{ marginTop: 'var(--bn-6)', display: 'flex', flexDirection: 'column', gap: 'var(--bn-2)' }}>
      <p data-q>{q}</p>
      <p data-hide>{String(hide)}</p>
      <p data-game>{(facets.game ?? []).join(',')}</p>
      <p data-sort>{`${sort.key}:${sort.dir}`}</p>
      <button type="button" data-set-q onClick={() => setQ('pikachu')}>
        set q
      </button>
      <button type="button" data-clear-q onClick={() => setQ('')}>
        clear q
      </button>
      <button type="button" data-toggle-hide onClick={() => setHide(!hide)}>
        toggle hide
      </button>
      <button type="button" data-set-game onClick={() => setFacets({ ...facets, game: ['pokemon', 'riftbound'] })}>
        set game
      </button>
      <button type="button" data-clear-game onClick={() => setFacets({ ...facets, game: [] })}>
        clear game
      </button>
      <button type="button" data-set-sort onClick={() => setSort({ key: 'price', dir: 'desc' })}>
        set sort
      </button>
      <button type="button" data-reset-sort onClick={() => setSort({ key: 'name', dir: 'asc' })}>
        reset sort
      </button>
    </section>
  )
}

if (new URLSearchParams(window.location.search).get('theme') === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark')
}

const root = document.getElementById('root')
if (root === null) throw new Error('the test page has no #root to mount into')

createRoot(root).render(
  <StrictMode>
    <main style={{ padding: 'var(--bn-4)', background: 'var(--bn-bg)', minHeight: '100vh' }}>
      <FilterSpecimens />
      <ViewStateDemo />
    </main>
  </StrictMode>,
)
