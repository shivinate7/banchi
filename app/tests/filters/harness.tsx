import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'

import '../../src/tokens.css'
import '../../src/base.css'
import '../../src/kit.css'

import { FilterBar } from '../../src/kit/filters'
import { FILTER_FACETS, FILTER_ROWS, FilterSpecimens, useFilteredRows } from '../../src/kit/filters.specimens'
import { useFacetParams, useSortParam, useViewFlag, useViewParam } from '../../src/kit/viewState'
import type { SortOption } from '../../src/kit/data'

/* THE TEST PAGE FOR THE FILTER BAR AND THE URL VIEW STATE (mirrors `tests/kit-data/`'s own
 * harness: no router, no store, no server — `filters.spec.ts` does not wait on a real screen to
 * mount either of these). `?theme=dark` draws the dark theme, same as `kit-data`'s page; the
 * view-state demo below reads and writes the HASH's own query string, which is a different
 * thing from `window.location.search` and so never collides with the theme flag. */

const DEMO_SORTS: readonly SortOption<'name' | 'price'>[] = [
  { key: 'name', label: 'Name', asc: 'A to Z', desc: 'Z to A', first: 'asc' },
  { key: 'price', label: 'Price' },
]

/** Every `viewState.ts` hook, bound to a real `FilterBar` over the specimen rows, plus a few
 *  presses and a readout, so a spec can drive the URL and read back what each hook thinks the
 *  URL says. Hide sold is ON by default here, as it is on Inventory (D132). */
function ViewStateDemo() {
  const [q, setQ] = useViewParam('q')
  const [hideSold, setHideSold] = useViewFlag('hidesold', true)
  const [facets, setFacets] = useFacetParams(FILTER_FACETS)
  const [sort, setSort] = useSortParam<'name' | 'price'>({ key: 'name', dir: 'asc' }, { options: DEMO_SORTS })
  const counted = useFilteredRows(facets, q, hideSold)

  return (
    <section data-view-state-demo style={{ marginTop: 'var(--bn-6)', display: 'flex', flexDirection: 'column', gap: 'var(--bn-2)' }}>
      <FilterBar
        facets={counted.facets}
        value={facets}
        onChange={setFacets}
        search={{ query: q, onChange: setQ }}
        sort={{ options: DEMO_SORTS, value: sort, onChange: setSort, defaultValue: { key: 'name', dir: 'asc' } }}
        hide={{ checked: hideSold, onChange: setHideSold, label: 'Hide sold', count: counted.soldHere, defaultChecked: true }}
        count={{ shown: counted.shown.length, total: FILTER_ROWS.length }}
      />
      <p data-q>{q}</p>
      <p data-hide>{String(hideSold)}</p>
      <p data-game>{(facets.game ?? []).join(',')}</p>
      <p data-set>{(facets.set ?? []).join(',')}</p>
      <p data-sort>{`${sort.key}:${sort.dir}`}</p>
      <button type="button" data-set-q onClick={() => setQ('pikachu')}>
        set q
      </button>
      <button type="button" data-clear-q onClick={() => setQ('')}>
        clear q
      </button>
      <button type="button" data-toggle-hide onClick={() => setHideSold(!hideSold)}>
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

/** A bar whose search FAILED (`useSearch`'s `failure`), on the test page only: the kit page
 *  draws the busy state, and a failure beside it would contradict it. */
function FailureDemo() {
  const [retries, setRetries] = useState(0)
  const [q, setQ] = useState('pikachu')
  return (
    <section data-failure-demo style={{ marginTop: 'var(--bn-6)' }}>
      <FilterBar
        facets={[]}
        value={{}}
        onChange={() => undefined}
        search={{
          query: q,
          onChange: setQ,
          failure: { code: 'unreachable', message: 'The server did not answer.', kind: 'retry' },
          onRetry: () => setRetries((n) => n + 1),
        }}
        count={{ shown: 0, total: 0 }}
      />
      <p data-retries>{retries}</p>
    </section>
  )
}

/** A bar handed a value with a pick no option carries, straight, with no URL reader in front of
 *  it: the bar's own count line must still never say the word. */
function RawValueDemo() {
  return (
    <section data-raw-demo style={{ marginTop: 'var(--bn-6)' }}>
      <FilterBar
        facets={FILTER_FACETS}
        value={{ game: ['pokemon', 'bogus'] }}
        onChange={() => undefined}
        count={{ shown: 12, total: FILTER_ROWS.length }}
      />
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
      <FailureDemo />
      <RawValueDemo />
    </main>
  </StrictMode>,
)
