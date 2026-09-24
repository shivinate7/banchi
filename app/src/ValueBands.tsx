/* app/src/ValueBands.tsx
 *
 * WHAT IS WORTH PULLING — every card on hand, ranked by what it is worth, with the drawer each
 * one sits in. `#/pricing?band=…`, a lens on the screen where prices are decided (D105) rather
 * than a twelfth route, by D103's own mechanism: `App.tsx` renders under `key={path}` with the
 * query stripped, so this lands under the operator instead of remounting, and it costs no
 * `ROUTES` row — which matters, because a row there moves three mechanical counts.
 *
 * THE OWNER ASKED FOR IT IN THESE WORDS: *"a way to see at all times ... either the most
 * valuable or least valuable cards so maybe i can easily start querying them for bulk
 * collection and taking them out of boxes"*.
 *
 * THE UNIT IS THE COPY AND NEVER THE SKU (D159). Their 122 cards at or
 * above $5 are 38 SKUs — Rengar, Trophy Hunter sits in three slots of box 4 and Vilemaw in
 * seven — so a per-SKU list draws a third of the rows and sends a hand to a third of the
 * drawers it has to open. Seven identical rows is CORRECT here and reads as a defect without
 * saying so, which is what `copy N of M` on the meta line is for.
 *
 * IT WRITES NOTHING, on the owner's ruling: *"read-only now, writes once you've used it"*.
 * Taking a card out of a box stays on `#/inventory`, which is where the store already learns
 * that a card has left — and every row here is a link into it.
 *
 * DIRECTION RE-DEFAULTS THE VIEW, WHICH IS THE MOST OPINIONATED CALL ON THE SCREEN, and the
 * contiguity measurement is the whole argument: the band at or above $5 is 122 cards in 87
 * separate reaches (1.40 a reach) and the band under the cut-off is 1,042 in 160 (6.51). The
 * rich end is a pick list and a drawer summary has no errand in it; the cheap end IS a drawer
 * question — 646 of those 1,042 cards are two drawers entire. So `Worth the most` opens on
 * cards and `Worth the least` on drawers, and one press moves either.
 *
 * PAGINATED, AS OF STORE-SCALING ITEM 7 (D159's aggregates, computed server-side). This
 * component USED to hold the whole store's `copies` array in memory and slice/sort/filter it
 * four different ways (`ordered`, `slice`, `stacks`, `pulls`). It fetches now:
 *
 *   1. Aggregates ALONE (`getValueAggregates`) — `boxes`, `unrankable`, `totals`, `sources` —
 *      fetched once, since D159's arithmetic is store-wide and does not vary by band or box
 *      (T7's own `check_value_page` asserts this identity). Every chip count (`p1`/`p5`/`p10`/
 *      `cutoff`) is arithmetic over these figures — never a row fetch.
 *   2. The ROWS for the current band, fetched with `getValuePage` at exactly the size the
 *      aggregates already say the band should be (a percentile share or the cut-off split),
 *      so "Show N more" over a KNOWN-SIZE band is a DOM throttle exactly as it always was — the
 *      whole band is already in memory, just not all rendered at once. A TYPED PRICE has no
 *      known size ahead of time, so its rows accumulate page by page until one fails the
 *      predicate or the store runs out.
 *   3. The GAPS disclosure fetches lazily, page by page, ONLY once opened, and "Show N more"
 *      there is a REAL network fetch (not a DOM reveal) — gaps.total can be in the hundreds and
 *      the panel is closed by default.
 *
 * `stack_index`/`stack_of` NOW TRAVEL ON THE ROW (server-computed), replacing the old
 * client-side `stacks()` — "copy N of M" needs the whole band's own SKU counts, which a client
 * holding one page can no longer compute for itself. `pulls()` (the reach/spots-and-drawers
 * measurement) STAYS CLIENT-SIDE: every fetch strategy above ends with the FULL current band in
 * `rows` before the reach line is drawn (a known-size band is fetched whole; a typed-price band
 * is fetched until exhausted), so nothing here computes a reach off a partial page — flagged in
 * the PR as a deliberate simplification against the playbook's suggestion of a server-side
 * `reach` field, since this fetch strategy makes the two equivalent.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button, Chip, EmptyState, Notice, PageHeader, Pill, Segmented, Stat } from './kit'
import { PositionLabel } from './PositionLabel'
import { getValueAggregates, getValuePage } from './server'
import type { ValueAggregates } from './server'
import { placePartsOf } from './position'
import type { ValueBox, ValueCopy } from './types'
import './ValueBands.css'

/** Which end of the money the operator is looking at — their own two words. */
export type ValueEnd = 'top' | 'bottom'

/** How far into that end the band reaches. Each is a SLICE of the one order the server already
 *  sorted: nothing here re-ranks, so the cheap end is the rich end read backwards and the two
 *  can never disagree about a tie.
 *
 *  THERE IS NO `everything`, AND THE MEASUREMENT IS WHY. 2,245 ranked rows answer no question
 *  the operator asked. The widest band this control can produce is a typed price at a low
 *  figure, which is a band somebody chose. */
type Cut = 'p1' | 'p5' | 'p10' | 'cutoff' | 'price'

/** Whether the body draws copies or drawers — *"both, and I pick"*. */
type View = 'cards' | 'drawers'

/** THE THREE PERCENTILE STOPS ARE FIXED, AND THE CURVE IS THE ARGUMENT. Measured on the owner's
 *  store: the top 1% is 18 cards carrying 18.7% of the value, the top 5% is 92 carrying 53.8%,
 *  the top 10% is 185 carrying 71.5%, and the remaining 2,060 hold 28.5%. Three stops describe
 *  that whole curve. A slider or a typed N invites hunting for a precision this distribution
 *  does not have — and the money axis, where precision IS available, has its own typed field. */
const SHARES: Record<'p1' | 'p5' | 'p10', number> = { p1: 1, p5: 5, p10: 10 }

/** How many rows a single network page carries, and (for a known-size band) how many are drawn
 *  before the operator asks for more. The screen does NOT virtualize — `#/pricing` already
 *  draws ~423 pricing rows, each with a text input, a popover anchor and per-keystroke field
 *  state, where a row here is a link and two figures. What a page does is keep the FIRST paint
 *  cheap on a 1,042-row cheap band; pressing for more is the operator saying they want it. */
const PAGE = 200

const ENDS: readonly { value: ValueEnd; label: string }[] = [
  { value: 'top', label: 'Worth the most' },
  { value: 'bottom', label: 'Worth the least' },
]

const VIEWS: readonly { value: View; label: string }[] = [
  { value: 'cards', label: 'Cards' },
  { value: 'drawers', label: 'Drawers' },
]

/** `Pricing.tsx`'s own money alphabet, spelled here rather than imported so this screen's field
 *  cannot be loosened by an edit to that one. */
const PRICE = /^\d*(\.\d{0,2})?$/

function num(text: string | null | undefined): number | null {
  if (text === null || text === undefined || String(text).trim() === '') return null
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/** `$1,387.72` from a wire string, or an em dash.
 *
 *  SEPARATED, WHICH `money()` IS NOT, AND THE DIFFERENCE IS THE SCALE. That helper renders one
 *  card's price, where four figures never occur and a comma would be noise. Every money figure
 *  on THIS screen is a total over a band or a drawer — $2,531.64 on the owner's store today,
 *  and a store ten times the size is five digits — so `$1387.72` is a number a person has to
 *  count the digits of. It takes a string because the wire sends money as one, for the reason
 *  every price in this repo is a string. */
function cash(text: string | null | undefined): string {
  const value = num(text)
  return value === null
    ? '—'
    : `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function whole(n: number): string {
  return n.toLocaleString()
}

/** HOW MANY TIMES A HAND GOES INTO A DRAWER to collect this band.
 *
 *  A run of consecutive indices in one box is ONE reach; a gap starts another. This is the
 *  measurement that argued for the whole screen — 122 cards in 87 reaches at the rich end
 *  against 1,042 in 160 at the cheap one — so the same list is a shopping trip at one end and
 *  a sweep at the other, and the operator can see which before walking anywhere.
 *
 *  IT IS COMPUTED HERE RATHER THAN SERVED because it is a property of the BAND, and the band is
 *  chosen on this screen, and the fetch strategies below always land the FULL current band in
 *  `rows` before this runs.
 *
 *  THE SECTION COMES OFF THE COMPOSED LABEL AND IS NEVER RECOMPUTED. `types.ts` forbids a
 *  client computing a section boundary and D10 is why — the dividers are whoever put them in
 *  the box. A row the server would not compose a label for counts toward no section, which is
 *  the honest answer rather than a guess. */
function pulls(rows: readonly ValueCopy[]): { reaches: number; boxes: number; sections: number } {
  const byBox = new Map<number, number[]>()
  const sections = new Set<string>()
  for (const row of rows) {
    const seen = byBox.get(row.box)
    if (seen === undefined) byBox.set(row.box, [row.index])
    else seen.push(row.index)
    /* THE SECTION OFF THE ONE LABEL READER (`position.ts:placePartsOf`), since the server's label
       names the box, the section and the card with commas (D-a-box-is-shown-by-its-name). */
    const section = placePartsOf(row.label)?.section ?? null
    if (section !== null) sections.add(`${row.box}/${section}`)
  }
  let reaches = 0
  for (const indices of byBox.values()) {
    indices.sort((a, b) => a - b)
    reaches += 1
    for (let i = 1; i < indices.length; i += 1) {
      const here = indices[i]
      const before = indices[i - 1]
      if (here !== undefined && before !== undefined && here - before > 1) reaches += 1
    }
  }
  return { reaches, boxes: byBox.size, sections: sections.size }
}

/** The scoped figures a cut's wanted count is computed from — store-wide, or one drawer's own,
 *  off the SAME aggregates block regardless of which band is on screen (T7's D159 arm). */
function scopedFigures(
  aggregates: ValueAggregates,
  box: number | null,
): { valued: number; under_cutoff: number; at_or_over: number } {
  if (box === null) return aggregates.totals
  const drawer = aggregates.boxes.find((one) => one.box === box)
  return drawer === undefined
    ? { valued: 0, under_cutoff: 0, at_or_over: 0 }
    : { valued: drawer.valued, under_cutoff: drawer.under_cutoff, at_or_over: drawer.at_or_over }
}

/** How many rows the current cut wants, or `null` for a typed price — unknowable ahead of a
 *  fetch, which is why that one cut alone accumulates page by page rather than in one call. */
function wantedCount(
  cut: Cut,
  end: ValueEnd,
  figures: { valued: number; under_cutoff: number; at_or_over: number },
): number | null {
  if (cut === 'price') return null
  if (cut === 'cutoff') return end === 'top' ? figures.at_or_over : figures.under_cutoff
  /* A PERCENTILE BAND NEVER ROUNDS TO NOTHING WHILE THERE IS SOMETHING TO RANK. `Math.round(3 *
     5 / 100)` is 0, so a store with fewer than ten priced cards opened on an EMPTY default band
     — a screen reporting that a store with cards in it holds nothing valuable. The top 5% of
     three cards is the top card, which is the honest reading of the question. */
  return figures.valued === 0 ? 0 : Math.max(1, Math.round((figures.valued * SHARES[cut]) / 100))
}

/** Where a copy is, or the store key when the server would compose no label.
 *
 *  ONE RENDERER FOR BOTH LISTS, because the two drew the same fallback and a fallback typed
 *  twice is a rule with two copies. `flow` is the only thing that differs: the band's rows are
 *  cards with room for a stacked block, and the unrankable list is a dense run.
 *
 *  A LABEL THE SERVER WOULD NOT COMPOSE MAY NEVER BE SUBSTITUTED (D58, on D56's rule). It is
 *  null for a box whose walk degraded or a pooled card that never had a slot, and
 *  `Box N · Section N · Card M` here would be the numbering D58 replaced, drawn beside rows
 *  that are not in it. */
function Where({ row, flow }: { readonly row: ValueCopy; readonly flow: 'stack' | 'run' }) {
  if (row.label !== null) return <PositionLabel label={row.label} flow={flow} lead="slot" />
  return (
    <span className="value-nolabel">
      {/* sigil-ok: there is NO slot for this row — the server composed no label, so D58's count
          does not exist and the store key is the only honest address left. D71's ruling is that
          the FIGURE goes and the treatment stays; inventing a count here would be worse. */}
      no label <span className="bn-mono">{`B${row.box} #${row.index}`}</span>
    </span>
  )
}

function ValueRow({ row }: { readonly row: ValueCopy }) {
  const asking = typeof row.answer === 'string' || typeof row.answer === 'number' ? String(row.answer) : null
  const held = row.answer !== null && typeof row.answer === 'object'
  /* `stack_index`/`stack_of` ARE THE SERVER'S NOW (store-scaling item 7) — the whole reason
     they travel on the row rather than being grouped client-side is that the client no longer
     holds every OTHER copy of this SKU to count against. */
  const which = row.stack_of === undefined || row.stack_of === null || row.stack_of < 2
    ? null
    : `copy ${row.stack_index ?? '?'} of ${row.stack_of}`
  const meta = [row.set_name, row.condition, which].filter(Boolean) as string[]
  return (
    <a
      className="value-row"
      href={`#/inventory?box=${row.box}`}
      title={`Open box ${row.box} in the inventory`}
    >
      <span className="value-where">
        <Where row={row} flow="stack" />
      </span>
      <span className="value-identity">
        <span className="value-name">{row.name ?? 'Nobody has named this one'}</span>
        <span className="value-meta">
          {meta.map((part, i) => (
            <span key={i}>{part}</span>
          ))}
          {row.live === 0 ? null : (
            <span className="value-live">
              <span className="bn-dot bn-dot-live" />
              {`${row.live} listed`}
            </span>
          )}
        </span>
      </span>
      <span className="value-money">
        <span className="value-market">{cash(row.market)}</span>
        {held ? (
          <Pill tone="warn" size="sm">Held back</Pill>
        ) : asking === null ? null : (
          <span className="value-asking">{`asking ${cash(asking)}`}</span>
        )}
      </span>
    </a>
  )
}

function DrawerCard({ drawer, threshold, onScope }: {
  readonly drawer: ValueBox
  readonly threshold: string | null
  readonly onScope: () => void
}) {
  const cut = threshold === null ? 'your cut-off' : `$${threshold}`
  /* A DRAWER'S TOTAL IS A FLOOR WHENEVER ANY OF ITS CARDS HAS NO PRICE, and saying otherwise is
     a silent drop wearing the shape of a total. Box 4 is 633 cards of which 215 have never been
     priced; `$1,665.22` claims to be what the drawer is worth and is what 418 of its cards are
     worth. Box 1's figure is drawn from 154 of 322. */
  const floored = drawer.unpriced > 0
  /* THE VERDICT PILL IS A FACT AND NOT A THRESHOLD — drawn only when NOTHING in the drawer is
     at or over the cut-off. There is no "mostly bulk": a fuzzy ratio nobody can see is how a
     rule stops being one. And it is suppressed whenever a card in the drawer has no price,
     however `at_or_over` reads: box 5 is 102 of 102 priced cards under the cut-off and two
     cards nobody has read, so its errand is "read those two, then the drawer goes" rather than
     "the drawer goes". */
  const allBulk = drawer.at_or_over === 0 && drawer.unpriced === 0 && drawer.valued > 0
  return (
    <article className="bn-panel value-drawer">
      <header className="value-drawer-head">
        <span className="value-drawer-title">{drawer.name ?? `Box ${drawer.box}`}</span>
        {drawer.name === null ? null : <span className="value-drawer-index">{`Box ${drawer.box}`}</span>}
      </header>
      <div className="value-drawer-figures">
        <Stat value={whole(drawer.cards)} label="cards" />
        <Stat
          value={<>{floored ? <span className="value-atleast">at least </span> : null}{cash(drawer.total)}</>}
          label="in the drawer"
        />
        <Stat value={cash(drawer.per_card)} label="a card" />
        <Stat value={cash(drawer.top)} label="best card" />
      </div>
      {/* THE VERDICT SLOT HOLDS ONE HEIGHT FOR EVERY STATE IT CAN BE IN (D118). Three things can
          land here — the pill, the press, or a sentence — and a slot that took each one's own
          height would move every drawer below it whenever the band moved. */}
      <div className="value-drawer-verdict">
        {drawer.valued === 0 ? (
          <span className="value-drawer-says">Nothing in it has a price yet, so none of it can be ranked.</span>
        ) : allBulk ? (
          <Pill tone="warn">{`Nothing in it is over ${cut}`}</Pill>
        ) : drawer.at_or_over === 0 ? (
          <span className="value-drawer-says">{`None of its ${whole(drawer.valued)} priced cards is over ${cut}.`}</span>
        ) : (
          <>
            <span className="value-drawer-says">
              {drawer.under_cutoff === 0
                ? `Not one of its ${whole(drawer.valued)} priced cards is under ${cut}.`
                : `${whole(drawer.under_cutoff)} of its ${whole(drawer.valued)} priced cards are under ${cut}.`}
            </span>
            {/* THE STRONGEST MOVE ON THE SCREEN, and it falls straight out of the numbers: a
                drawer that is bulk except for N cards offers those N as one press, so the
                operator makes one reach and then the drawer goes whole. */}
            <Button size="sm" onClick={onScope}>
              {`Show the ${whole(drawer.at_or_over)} worth listing`}
            </Button>
          </>
        )}
      </div>
      {drawer.unpriced === 0 ? null : (
        <p className="value-drawer-gap">
          {`${whole(drawer.unpriced)} of its cards have never been priced.`}
        </p>
      )}
    </article>
  )
}

export function ValueBands({ end, onEnd, onLeave }: {
  readonly end: ValueEnd
  readonly onEnd: (next: ValueEnd) => void
  readonly onLeave: () => void
}) {
  const [aggregates, setAggregates] = useState<ValueAggregates | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const [cut, setCut] = useState<Cut>('p5')
  const [price, setPrice] = useState('5.00')
  /* THE VIEW FOLLOWS DIRECTION AND IS RE-APPLIED ON EVERY PRESS OF IT — see the file header for
     the contiguity argument. It is not persisted: this is a lens, not a habit, and D27's device
     memory is for how a browser is dressed rather than for a one-sitting choice. */
  const [view, setView] = useState<View>(end === 'top' ? 'cards' : 'drawers')
  const [box, setBox] = useState<number | null>(null)
  const [shown, setShown] = useState(PAGE)
  const [openGaps, setOpenGaps] = useState(false)

  /* THE CURRENT BAND'S OWN ROWS — fetched WHOLE for a known-size cut (percentile/cut-off) and
     accumulated page by page for a typed price, per the file header. */
  const [rows, setRows] = useState<ValueCopy[]>([])
  const [rowsFailed, setRowsFailed] = useState<string | null>(null)

  /* THE WIDEST BAND'S OWN EXTREME — what an empty band has to name — fetched independently of
     `cut`, since "nothing is worth $50 or more" is only half an answer without "the most
     valuable card you own is $47.57" even when the CURRENT cut has zero rows. */
  const [best, setBest] = useState<ValueCopy | null>(null)

  /* THE UNRANKABLE DISCLOSURE — lazy, and its own network-driven "Show N more" (never a DOM
     reveal of an already-fetched array): `gaps.total` can be in the hundreds and the panel is
     closed by default. */
  const [gapRows, setGapRows] = useState<ValueCopy[]>([])
  const [gapsNext, setGapsNext] = useState<string | null>(null)
  const [gapsLoadingMore, setGapsLoadingMore] = useState(false)

  /* A MONOTONIC GENERATION, NOT A "STILL MOUNTED" BOOLEAN (w1b). The old `liveAgg.current`
   * guard answered one question — has this instance unmounted? — and answered it WRONG the
   * one place it mattered: React's StrictMode double-invokes every mount effect in dev,
   * reusing the SAME fiber (and so the same ref) across the simulated unmount/remount, which
   * means both of the resulting `readAggregates()` calls saw `liveAgg.current === true`
   * throughout. Whichever response happened to LAND LAST won — not whichever request started
   * last — so a slow first call landing after a fast second one silently overwrote a correct,
   * already-rendered answer with a stale one (confirmed: cold-loading `#/pricing?band=…` with
   * the aggregates request delayed reproduces a badge and row count that regress back to the
   * first response's numbers seconds after the second, correct one had already drawn). The
   * rows effect two cursors down already had the right shape for this — a monotonic counter,
   * captured at call time, checked before the write lands — so the aggregates fetch adopts
   * the same one rather than inventing a second mechanism. */
  const aggGeneration = useRef(0)
  const readAggregates = useCallback(async () => {
    const mine = ++aggGeneration.current
    setFailed(null)
    try {
      const answer = await getValueAggregates()
      if (aggGeneration.current === mine) setAggregates(answer)
    } catch (error) {
      if (aggGeneration.current === mine) setFailed(error instanceof Error ? error.message : String(error))
    }
  }, [])

  useEffect(() => {
    void readAggregates()
  }, [readAggregates])

  /* THE PAGE RESETS WHEN THE BAND MOVES. `shown` counts into a list that has just been replaced,
     so carrying it over draws 400 rows of a 12-row band's successor without anybody asking. */
  useEffect(() => setShown(PAGE), [end, cut, price, view, box])

  /* THE CURRENT BAND'S ROWS. A generation token guards against a stale fetch (a quick cut/box
     change mid-flight) landing after a newer one already resolved. */
  const generation = useRef(0)
  useEffect(() => {
    if (aggregates === null || view !== 'cards') return
    const mine = ++generation.current
    setRowsFailed(null)
    void (async () => {
      try {
        const figures = scopedFigures(aggregates, box)
        const collected: ValueCopy[] = []
        if (cut === 'price' || cut === 'cutoff') {
          /* A PREDICATE FETCH, NEVER A BLIND LIMIT, EVEN THOUGH THE CUT-OFF'S COUNT IS ALREADY
             KNOWN (`figures.under_cutoff`/`at_or_over`, from the aggregates). Fetching exactly
             that many rows off the TOP of the band and trusting them all to satisfy the bar
             is only safe when the aggregate and the row order agree byte for byte — true of a
             real store, but not something this component should assume rather than check: the
             SAME real cut-off `slice()` used to apply client-side (`market >= bar` / `< bar`)
             is applied here too, per PAGE fetched, stopping at the first row that fails it —
             the exact mechanism `price` already needs because ITS count is never known ahead
             of a fetch. */
          const bar = cut === 'cutoff' ? num(aggregates.threshold) : num(price)
          let after: string | null = null
          for (;;) {
            const page = await getValuePage({ band: end, box, after, limit: PAGE })
            let stoppedEarly = false
            for (const row of page.rows) {
              const market = num(row.market)
              const passes = bar === null ? true : market !== null && (end === 'top' ? market >= bar : market < bar)
              if (!passes) {
                stoppedEarly = true
                break
              }
              collected.push(row)
            }
            if (stoppedEarly || page.next === null) break
            after = page.next
            if (generation.current !== mine) return
          }
        } else {
          const wanted = wantedCount(cut, end, figures) ?? 0
          let after: string | null = null
          while (collected.length < wanted) {
            const limit = Math.min(PAGE, wanted - collected.length)
            const page = await getValuePage({ band: end, box, after, limit })
            collected.push(...page.rows)
            if (page.next === null) break
            after = page.next
            if (generation.current !== mine) return
          }
        }
        if (generation.current === mine) setRows(collected)
      } catch (error) {
        if (generation.current === mine) {
          setRowsFailed(error instanceof Error ? error.message : String(error))
        }
      }
    })()
  }, [aggregates, box, cut, end, price, view])

  /* THE EXTREME OF THE WHOLE BAND (unfiltered by the cut), for the empty-band sentence. */
  useEffect(() => {
    let live = true
    void (async () => {
      try {
        const page = await getValuePage({ band: end, box, limit: 1 })
        if (live) setBest(page.rows[0] ?? null)
      } catch {
        if (live) setBest(null)
      }
    })()
    return () => {
      live = false
    }
  }, [end, box])

  /* THE GAPS DISCLOSURE resets whenever the box scope changes, and fetches its first page only
     once opened. */
  useEffect(() => {
    setGapRows([])
    setGapsNext(null)
  }, [box])

  useEffect(() => {
    if (!openGaps || gapRows.length > 0 || gapsNext !== null) return
    let live = true
    void (async () => {
      const page = await getValuePage({ band: 'gaps', box, after: null, limit: PAGE })
      if (live) {
        setGapRows(page.rows)
        setGapsNext(page.next)
      }
    })()
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openGaps, box])

  const loadMoreGaps = useCallback(async () => {
    if (gapsNext === null) return
    setGapsLoadingMore(true)
    try {
      const page = await getValuePage({ band: 'gaps', box, after: gapsNext, limit: PAGE })
      setGapRows((seen) => [...seen, ...page.rows])
      setGapsNext(page.next)
    } finally {
      setGapsLoadingMore(false)
    }
  }, [gapsNext, box])

  const reach = useMemo(() => pulls(rows), [rows])
  const worth = useMemo(() => rows.reduce((sum, row) => sum + (num(row.market) ?? 0), 0), [rows])

  /* EVERY BAND'S COUNT IS ON ITS OWN CHIP, so the default hides nothing — the operator can see
     that the cheap end holds 1,042 cards without pressing anything. Arithmetic over the
     aggregates alone (see the file header) — no row fetch needed for a chip count. */
  const counts = useMemo(() => {
    if (aggregates === null) return null
    const figures = scopedFigures(aggregates, box)
    return {
      p1: wantedCount('p1', end, figures) ?? 0,
      p5: wantedCount('p5', end, figures) ?? 0,
      p10: wantedCount('p10', end, figures) ?? 0,
      cutoff: wantedCount('cutoff', end, figures) ?? 0,
    }
  }, [aggregates, box, end])

  const drawers = useMemo(() => {
    if (aggregates === null) return []
    const order = [...aggregates.boxes]
    /* WHICH DRAWER HOLDS THE MONEY AND WHICH DRAWER IS BULK ARE TWO QUESTIONS, which is why
       `ValueBox` carries both figures: the rich end ranks on the drawer's total and the cheap
       end on what a card out of it is worth. */
    return end === 'top'
      ? order.sort((a, b) => (num(b.total) ?? 0) - (num(a.total) ?? 0))
      : order.sort((a, b) => (num(a.per_card) ?? 0) - (num(b.per_card) ?? 0))
  }, [aggregates, end])

  const takeEnd = useCallback(
    (next: ValueEnd) => {
      onEnd(next)
      setView(next === 'top' ? 'cards' : 'drawers')
      setBox(null)
    },
    [onEnd],
  )

  if (failed !== null) {
    return (
      <main className="bn-page value-page">
        <PageHeader title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <Notice tone="danger" title="The store could not be read" code={failed}>
          Waiting on the capture server.
        </Notice>
        <div><Button variant="primary" onClick={() => void readAggregates()}>Try again</Button></div>
      </main>
    )
  }

  if (aggregates === null || counts === null) {
    return (
      <main className="bn-page value-page">
        <PageHeader title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <p className="value-loading">Reading every card on hand…</p>
        <div className="bn-skeleton value-skeleton" aria-hidden="true" />
      </main>
    )
  }

  const gaps = aggregates.unrankable
  const scoped = box === null ? null : aggregates.boxes.find((one) => one.box === box) ?? null
  /* A BAND THAT IS REAL MONEY AND ROUNDS TO NOTHING SAYS SO RATHER THAN SAYING ZERO — the two
     cards worth listing in box 2 are $0.72 of $2,531.64, and "0% of everything you own" is a
     false sentence about a band the operator is standing in. `money.ts:roundsToNothing` makes
     the same distinction about a figure. */
  const percent = aggregates.totals.valued === 0 ? 0 : (worth / (num(aggregates.totals.value) ?? 1)) * 100
  const share = percent > 0 && percent < 0.5 ? 'under 1%' : `${Math.round(percent)}%`

  if (aggregates.totals.cards === 0) {
    return (
      <main className="bn-page value-page">
        <PageHeader title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <EmptyState
          icon="box"
          title="Nothing is in a box yet"
          body="Capture a box to see its most and least valuable cards here."
          actions={<Button variant="primary" onClick={() => { window.location.hash = '#/capture' }}>Capture a box</Button>}
        />
      </main>
    )
  }

  return (
    <main className="bn-page value-page">
      <PageHeader
        title="What's worth pulling"
        lede={`${whole(aggregates.totals.valued)} of ${whole(aggregates.totals.cards)} cards on hand carry a price, ${cash(aggregates.totals.value)} at market.`}
        actions={<Button onClick={onLeave}>Back to pricing</Button>}
      />

      {aggregates.totals.valued === 0 ? (
        <EmptyState
          icon="sparkles"
          title="Nothing here has a price yet"
          body={`${whole(aggregates.totals.cards)} cards in ${whole(aggregates.boxes.length)} drawers — none priced yet. Run a box to price them.`}
          actions={<Button variant="primary" onClick={() => { window.location.hash = '#/runs' }}>Start a run</Button>}
        />
      ) : (
        <>
          {aggregates.sources.length === 1 ? (
            <Notice tone="info" title="These prices came out of one file">
              The ranking only covers what's been read.
            </Notice>
          ) : null}

          {rowsFailed === null ? null : (
            <Notice tone="danger" title="This band could not be fetched" code={rowsFailed}>
              Try another band, or come back later.
            </Notice>
          )}

          <div className="bn-panel value-bar">
            <div className="value-bar-controls">
              <Segmented label="Which end of the store" value={end} options={ENDS} onChange={takeEnd} />
              <div className="value-bands">
                <Chip pressed={cut === 'p1'} count={counts.p1} onClick={() => setCut('p1')}>
                  {end === 'top' ? 'Top 1%' : 'Bottom 1%'}
                </Chip>
                <Chip pressed={cut === 'p5'} count={counts.p5} onClick={() => setCut('p5')}>
                  {end === 'top' ? 'Top 5%' : 'Bottom 5%'}
                </Chip>
                <Chip pressed={cut === 'p10'} count={counts.p10} onClick={() => setCut('p10')}>
                  {end === 'top' ? 'Top 10%' : 'Bottom 10%'}
                </Chip>
                <Chip
                  pressed={cut === 'cutoff'}
                  count={counts.cutoff}
                  onClick={() => setCut('cutoff')}
                  title="Set at the top of the screen"
                >
                  {aggregates.threshold === null
                    ? end === 'top' ? 'Over your cut-off' : 'Under your cut-off'
                    : end === 'top' ? `Over $${aggregates.threshold}` : `Under $${aggregates.threshold}`}
                </Chip>
                {/* A CHIP THAT CONTAINS A FIELD, WHICH THE KIT DOES NOT HAVE. `Chip` is a
                    button and `.bn-input` is a field; `Pricing.css`'s `.pricing-flat` already
                    hand-rolls the pair, and this is the SECOND instance. A third makes it a kit
                    component; two is a pattern with a precedent. */}
                <span className={['value-field', cut === 'price' ? 'value-field-on' : ''].filter(Boolean).join(' ')}>
                  <span className="value-field-sign">$</span>
                  <input
                    className="value-field-input"
                    inputMode="decimal"
                    value={price}
                    aria-label={end === 'top' ? 'Worth this many dollars and up' : 'Worth under this many dollars'}
                    onFocus={() => setCut('price')}
                    onChange={(event) => {
                      if (PRICE.test(event.target.value)) {
                        setPrice(event.target.value)
                        setCut('price')
                      }
                    }}
                  />
                  <span className="value-field-says">{end === 'top' ? 'and up' : 'and under'}</span>
                </span>
              </div>
              <Segmented label="How to show them" value={view} options={VIEWS} onChange={setView} />
            </div>
            <p className="value-standing">
              {view === 'drawers' ? (
                end === 'top'
                  ? `Your ${whole(aggregates.boxes.length)} drawers, richest first.`
                  : `Your ${whole(aggregates.boxes.length)} drawers, cheapest card first.`
              ) : rows.length === 0 ? (
                'Nothing sits in that band.'
              ) : (
                <>
                  {`${whole(rows.length)} cards, ${cash(worth.toFixed(2))} — ${share} of everything you own. `}
                  {`They sit in ${whole(reach.reaches)} separate ${reach.reaches === 1 ? 'spot' : 'spots'} across ${whole(reach.boxes)} ${reach.boxes === 1 ? 'drawer' : 'drawers'}.`}
                </>
              )}
            </p>
          </div>

          {scoped === null ? null : (
            <div className="value-scope">
              <span className="value-scope-says">
                {`Only ${scoped.name ?? `box ${scoped.box}`} — ${whole(scoped.cards)} cards.`}
              </span>
              <Button size="sm" onClick={() => setBox(null)}>Every drawer</Button>
            </div>
          )}

          {/* THE COUNT IS ABOVE THE LIST AND THE ROWS ARE AT THE FOOT, and both are permanent.
              A card with no price is never ranked and never out of sight; the strip says so
              where the operator is reading, and the section says which three things are wrong
              and what to do about each. */}
          {gaps.total === 0 ? null : (
            <div className="bn-well value-gapline">
              <span>
                <strong>{`${whole(gaps.total)} cards have no price yet and are not in this list.`}</strong>{' '}
                {end === 'bottom'
                  ? 'They are not bulk until somebody has read them.'
                  : 'Nothing has been dropped — there is just nothing to rank them on.'}
              </span>
              <Button size="sm" onClick={() => setOpenGaps((open) => !open)} aria-expanded={openGaps}>
                {openGaps ? 'Hide them' : 'Show them'}
              </Button>
            </div>
          )}

          {view === 'drawers' ? (
            <div className="value-drawers">
              {drawers.map((drawer) => (
                <DrawerCard
                  key={drawer.box}
                  drawer={drawer}
                  threshold={aggregates.threshold}
                  onScope={() => {
                    setBox(drawer.box)
                    setCut('cutoff')
                    onEnd('top')
                    setView('cards')
                  }}
                />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              icon="search"
              title={cut === 'price' ? `Nothing is worth ${cash(price)} ${end === 'top' ? 'or more' : 'or less'}` : 'Nothing sits in that band'}
              body={
                best === null
                  ? 'Nothing here has a price.'
                  : `The ${end === 'top' ? 'most' : 'least'} valuable card you own is ${best.name ?? 'one nobody has named'} at ${cash(best.market)}, in box ${best.box}.`
              }
              actions={<Button onClick={() => setCut('p10')}>Show me that one</Button>}
            />
          ) : (
            <div className="bn-panel value-list">
              <div className="value-heads" aria-hidden="true">
                <span>Where</span>
                <span>Card</span>
                <span className="value-heads-money">Worth</span>
              </div>
              {rows.slice(0, shown).map((row) => (
                <ValueRow key={`${row.box}/${row.index}`} row={row} />
              ))}
              {rows.length > shown ? (
                <div className="value-more">
                  <Button onClick={() => setShown((seen) => seen + PAGE)}>
                    {`Show ${whole(Math.min(PAGE, rows.length - shown))} more`}
                  </Button>
                  <span className="value-more-says">{`${whole(shown)} of ${whole(rows.length)} shown`}</span>
                </div>
              ) : null}
            </div>
          )}

          {gaps.total === 0 ? null : (
            <section className="bn-panel value-gaps">
              <h2 className="value-gaps-title">{`${whole(gaps.total)} cards with no price — not ranked`}</h2>
              <p className="value-gaps-says">
                On the shelf, unranked — each needs a different fix.
              </p>
              {/* ALL THREE ARE DRAWN, INCLUDING AT ZERO — a true and useful statement, and it is
                  what keeps this panel's height off the state of the store (D118). */}
              <ul className="value-causes">
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.never_identified)}</span>
                  <span className="value-cause-says">
                    <strong>Never identified.</strong> Photographed, not yet run.
                  </span>
                  {gaps.never_identified === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/runs' }}>Start a run</Chip>
                  )}
                </li>
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.read_nothing)}</span>
                  <span className="value-cause-says">
                    <strong>Nothing was read off the photograph.</strong> No name and no number came back.
                  </span>
                  {gaps.read_nothing === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/inventory' }}>Look at them</Chip>
                  )}
                </li>
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.no_reading)}</span>
                  <span className="value-cause-says">
                    <strong>No export prices them.</strong> Read and named, but no catalogue row matches.
                  </span>
                  {gaps.no_reading === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/runs' }}>Fetch an export</Chip>
                  )}
                </li>
              </ul>
              {!openGaps ? null : (
                <div className="value-gap-rows">
                  {gapRows.map((row) => (
                    /* THE MONEY TRACK IS NOT DRAWN IN THIS SECTION. An empty money cell in a
                       column of dollar figures reads as zero, which is the confusion the whole
                       section exists to prevent. */
                    <a className="value-gap-row" key={`${row.box}/${row.index}`} href={`#/inventory?box=${row.box}`}>
                      <span className="value-where">
                        <Where row={row} flow="run" />
                      </span>
                      <span className="value-gap-name">{row.name ?? 'Nobody has named this one'}</span>
                    </a>
                  ))}
                  {/* A PANEL WHOSE WHOLE SUBJECT IS NOT DROPPING ANYTHING MAY NOT DROP ANYTHING
                      QUIETLY. It paged at 200 with no line saying so, which on the owner's 390
                      is 190 cards silently missing from the one place they are accounted for.
                      `gaps.total` is the aggregate figure and never `gapRows.length`, so the
                      "N of M" line is honest even before the last page has been fetched. */}
                  {gapsNext === null ? null : (
                    <div className="value-more">
                      <Button onClick={() => void loadMoreGaps()} disabled={gapsLoadingMore}>
                        {`Show ${whole(Math.min(PAGE, gaps.total - gapRows.length))} more`}
                      </Button>
                      <span className="value-more-says">
                        {`${whole(gapRows.length)} of ${whole(gaps.total)} shown`}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </main>
  )
}
