/**
 * What the demo's runtime (`demoServer.ts`) and its build step (`app/demoSplit.ts`) must agree on.
 * One home: the canonical key spelling, the two derived Home reads, and where the split files live.
 * Imports nothing, so the Vite config can load it.
 */

type Dict = Record<string, unknown>

/** Where the build writes the split recording, under the app's base path. */
export const DEMO_DATA_DIR = 'demo-data'

/** States that are not on hand. `_box_row` counts `on_hand` as every card not in one. */
export const DEPARTED: ReadonlySet<string> = new Set(['sold', 'retired', 'moved'])

/** The newest cards the build keeps ready for Home's deck, so Home never needs the whole-store read. */
export const DECK_POOL = 64

/**
 * One spelling of a recorded key, whichever side composed it.
 *
 * A GET is its path plus its query pairs SORTED, re-encoded by `URLSearchParams`. The
 * recorder builds `/boxes?game=riftbound&set=Origins` with Python's `urlencode`; the screen
 * builds the same filter with `URLSearchParams` in whatever order its object keys happen to
 * be — and the two encoders even disagree on which characters to escape. Sorting and
 * re-encoding BOTH sides is what makes the lookup exact.
 *
 * A POST read is `POST <path> <body>`, the body re-serialized with its keys sorted — the
 * string `demo-record.py:post_key` writes, re-derived here rather than trusted byte for byte.
 */
export function canonical(key: string): string {
  if (key.startsWith('POST ')) {
    const rest = key.slice(5)
    const space = rest.indexOf(' ')
    if (space < 0) return key
    try {
      return postKey(rest.slice(0, space), JSON.parse(rest.slice(space + 1)) as unknown)
    } catch {
      return key
    }
  }
  const mark = key.indexOf('?')
  if (mark < 0) return key
  const pairs = [...new URLSearchParams(key.slice(mark + 1)).entries()].sort((a, b) =>
    a[0] === b[0] ? (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0) : a[0] < b[0] ? -1 : 1,
  )
  const query = new URLSearchParams(pairs).toString()
  return query === '' ? key.slice(0, mark) : `${key.slice(0, mark)}?${query}`
}

function sortedJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJson)
  if (value !== null && typeof value === 'object') {
    const out: Dict = {}
    for (const name of Object.keys(value as Dict).sort()) out[name] = sortedJson((value as Dict)[name])
    return out
  }
  return value
}

/** The recorded key of a POST read: the verb, the path and the body with its keys sorted. */
export function postKey(path: string, body: unknown): string {
  return `POST ${path} ${JSON.stringify(sortedJson(body))}`
}

/** `GET /inventory/recent` — Home's hero deck, DERIVED from the whole-store read, never replayed.
 *  Home asks for no photograph until this answers (D172). The recording of it is the real
 *  store's answer on the day of the mirror, and that store's newest captures had all sold, so
 *  it recorded `{}` and Home drew no photograph at all. The server's own rule, on the
 *  recorded cards: named, photographed, on hand, newest capture first. A sale here also
 *  leaves the deck without a patch. */
export function recentCards(cards: Record<string, Dict>, limit: number): Dict {
  const picked = Object.entries(cards)
    .filter(([, c]) => c.photo !== null && c.name && !DEPARTED.has(String(c.state)))
    .sort((a, b) => String(b[1].captured_at).localeCompare(String(a[1].captured_at)))
    .slice(0, limit)
  return { cards: Object.fromEntries(picked) }
}

/** `GET /inventory/history` — three fields a card, DERIVED from the whole-store read like `recentCards`. */
export function historyCards(cards: Record<string, Dict>): Dict {
  return {
    cards: Object.fromEntries(
      Object.entries(cards).map(([key, c]) => [key, { captured_at: c.captured_at, box: c.box, state: c.state }]),
    ),
  }
}
