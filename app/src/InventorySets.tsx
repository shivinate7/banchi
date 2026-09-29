import { useEffect, useMemo, useState } from 'react'

import { describeFailure, getInventorySets, getSoldPrices, type Failure, type SoldPricesLookup, failureTone } from './server'
import type { SetGroup, SetGroupCard } from './types'
import { EmptyState, Loading, Money, Notice, Pill, Select } from './kit'
import { patchViewQuery, useViewParam } from './kit/viewState'
import './InventorySets.css'

/* THE OWNER'S "BY SET ORDER" VIEW (D293), a second way of walking `#/inventory`
 * (D264's own precedent: a view switch lives INSIDE Inventory rather than as a fourth
 * screen — D31, one owner-side view of stored cards). `Inventory.tsx` reads `view=sets` off
 * the URL (D285) and renders this in place of the box walk; it holds no state of its own
 * that Inventory.tsx needs back.
 *
 * ONE STORE-WIDE READ, SERVER-AGGREGATED — `GET /pipeline/sets`, one row per distinct card
 * with its quantity, never one row per physical copy (`do_pipeline_sets`'s own header has
 * the count: 2,455 on-hand cards behind 771 rows on the owner's store).
 *
 * A TAP BUILDS NO NEW WALK. It writes the same `box`/`card` pair `BoxBrowse.tsx`'s
 * `wantedCard` already reads off the hash (Review's place pill uses the identical link),
 * and clears `view` in the same write so the screen that lands is the ordinary box walk —
 * one `patchViewQuery` call, a same-path query change and so a REPLACE, never a push
 * (D201: a route change lands at the top, a same-path query change does not).
 *
 * THE OWNER'S REBUILD, 2026-09-26: photos are the main view (not a 40px afterthought), one
 * set on screen at a time with a picker to switch, and no location on the tile — the owner:
 * "i dont need location unless i click on the card itself then maybe it opens the regular
 * inventory view of the card", which the tap above already does and this rebuild does not
 * touch.
 */

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

function gameLabel(game: string | null): string | null {
  if (game === null || game.trim() === '') return null
  const spaced = game.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function qtyOf(cards: readonly SetGroupCard[]): number {
  return cards.reduce((sum, card) => sum + card.qty, 0)
}

/** Walk to this card, the way Review's place pill already does — no new mechanism.
 *
 *  `box: null` IS A REAL ROW, not a fault: `do_pipeline_sets` still ships it (never a
 *  silent drop) for a record whose position will not coerce, and `box=<n>&card=<cid>`
 *  cannot aim the walk at a row with no box to switch to. The fallback is the OTHER
 *  existing deep link, `?q=<text>` (D285's own key for a screen's search text) — the
 *  store-wide search `useSearch()` already runs, seeded once by `BoxBrowse.tsx`'s own
 *  `qParam` — which lands on whichever box the search finds a match in, exactly as
 *  typing the name would. The card's own name is what a person reads at the drawer, so
 *  it is the first choice; the SKU and the composed number are what is left when even
 *  that is blank. */
function openInWalk(card: SetGroupCard): void {
  if (card.box !== null) {
    patchViewQuery({ view: null, set: null, box: String(card.box), card: card.cid })
    return
  }
  const text = card.name ?? card.sku ?? card.number_display
  patchViewQuery({ view: null, set: null, box: null, card: null, q: text })
}

/** THE MAIN VIEW ON THIS SCREEN, per the owner's own ask (`D301`): "if it'd be easy
 *  to live pull all the photos without much lag I'd be happy to have the stock photos show as
 *  the main view on say set view or pricing." A join miss, or a load failure, draws no image
 *  at all — this screen never carried one before, so "nothing" is the honest fallback here
 *  (unlike Pricing's thumb, there is no owner photograph handy to fall back to: this row has
 *  no `idx` to build one from). */
function SetCardImage({ url }: { readonly url: string | null }) {
  const [failed, setFailed] = useState(false)
  if (url === null || failed) return null
  return (
    <img className="sets-card-img" src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
  )
}

/** One tile — the image, then the composed number, the name, the copy count and the market
 *  price. NO LOCATION: the owner's own ruling, 2026-09-26 — a box or a shelf is what opening
 *  the card answers, never what the tile itself says. */
function SetCardTile({ card, market }: { readonly card: SetGroupCard; readonly market: string | null }) {
  return (
    <button type="button" className="sets-tile" onClick={() => openInWalk(card)}>
      <SetCardImage url={card.image_url} />
      <span className="sets-tile-number bn-mono">{card.number_display ?? '—'}</span>
      <span className="sets-tile-name">{card.name ?? 'Not identified yet'}</span>
      <span className="sets-tile-meta">
        {/* A FOIL AND A NORMAL PRINTING CAN SHARE THE IMAGE ABOVE (the owner's own addition,
            mid-build) — this is what still tells the two rows apart. `null` for a plain Near
            Mint print with no finish suffix to name, and for a `sku_unknown` row. */}
        {card.printing === null ? null : <Pill tone="default">{card.printing}</Pill>}
        <Pill tone="default">{plural(card.qty, 'copy', 'copies')}</Pill>
      </span>
      <Money value={market === null ? null : Number(market)} className="sets-tile-price" />
    </button>
  )
}

/** One set the store holds a card of, plus the group's own cards — the picker's own list and
 *  the grid's own source, built once from `GET /pipeline/sets`' groups and its `no_set` list
 *  (a card with no set is a choice here too, never a silent drop, D196: the sentence is the
 *  client's own since the route composes no prose). `label` is the SERVER's own name
 *  VERBATIM — `do_pipeline_sets` already resolves a community code prefix ("ME01: Mega
 *  Evolution") against the vendored catalogue the same way the image join does, trying the
 *  unstripped name first, so this file has no regex of its own to keep in step with it (the
 *  review round, 2026-09-27: a client-side blind strip once turned a REAL colon-bearing set
 *  name, "Celebrations: Classic Collection", into "Classic Collection"). */
type SetOption = { readonly key: string; readonly game: string | null; readonly label: string; readonly count: number; readonly cards: readonly SetGroupCard[] }

function setOptionsOf(groups: readonly SetGroup[], noSet: readonly SetGroupCard[]): SetOption[] {
  const options: SetOption[] = groups.map((group) => ({
    key: `${group.game ?? ''}:${group.set_name}`,
    game: group.game,
    label: group.set_name,
    count: qtyOf(group.cards),
    cards: group.cards,
  }))
  if (noSet.length > 0) {
    options.push({ key: '__no_set__', game: null, label: 'No set on file', count: qtyOf(noSet), cards: noSet })
  }
  return options
}

export function InventorySets({ reloadToken = 0 }: { readonly reloadToken?: number }) {
  const [report, setReport] = useState<Awaited<ReturnType<typeof getInventorySets>> | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [setParam, setSetParam] = useViewParam('set', '')
  const [prices, setPrices] = useState<SoldPricesLookup>({})

  useEffect(() => {
    let live = true
    setFailure(null)
    getInventorySets()
      .then((next) => {
        if (live) setReport(next)
      })
      .catch((err: unknown) => {
        if (live) setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloadToken])

  const options = useMemo(
    () => (report === null ? [] : setOptionsOf(report.groups, report.no_set)),
    [report],
  )
  const current = options.find((option) => option.key === setParam) ?? options[0] ?? null

  /* THE MARKET FIGURE ON EACH TILE (D221: money stays mono, via `Money`) — the same
   *  `readings`/price-history reading `do_pipeline_value`'s own `market` field already draws
   *  for an on-hand card, reached through the NAMED-SKU route (`GET /pipeline/price-now`,
   *  `getSoldPrices`) rather than the whole-store `ValueTable` shape, which store-scaling
   *  item 7 measured at ~739KB and deliberately never fetches unpaginated any more. Scoped to
   *  the SET ON SCREEN, not the whole store, so a switch never asks for more than this grid
   *  is about to draw. */
  useEffect(() => {
    if (current === null) return
    const skus = Array.from(new Set(current.cards.map((card) => card.sku).filter((sku): sku is string => sku !== null)))
    if (skus.length === 0) {
      setPrices({})
      return
    }
    let live = true
    getSoldPrices(skus)
      .then((next) => {
        if (live) setPrices(next)
      })
      .catch(() => {
        if (live) setPrices({})
      })
    return () => {
      live = false
    }
    // `current` IS A STABLE REFERENCE ACROSS RENDERS, never a fresh object every render:
    // `options` is memoized on `[report]` above, and `.find` returns one of ITS elements, so
    // `current`'s identity only changes when `report` or `setParam` actually changes which
    // set is picked — never merely on a re-render. Depending on the whole object (rather
    // than `current?.key` alone) is therefore exactly as safe and is what lets this effect
    // also react to `current.cards` changing under the same key (a same-set re-fetch that
    // landed a different card list), which `?.key` alone would have missed.
  }, [current])

  if (failure !== null) {
    return <Notice tone={failureTone(failure)} title={failure.message} code={failure.code} />
  }
  if (report === null) return <Loading shape="cards" rows={12} />

  const total = qtyOf(report.groups.flatMap((group) => group.cards)) + qtyOf(report.no_set)
  if (total === 0) {
    return (
      <EmptyState
        icon="layers"
        title="No cards on hand yet"
        body="Identify a run and its cards will group here, by set, in printed order."
      />
    )
  }

  return (
    <div className="inventory-sets">
      <div className="sets-picker">
        <Select
          label="Set"
          value={current?.key ?? null}
          placeholder="Choose a set…"
          options={options.map((option) => ({
            value: option.key,
            label: option.label,
            text: option.label,
            count: option.count,
          }))}
          onChange={(next) => setSetParam(next === (options[0]?.key ?? '') ? '' : next)}
        />
      </div>
      {current === null ? null : (
        <>
          <div className="sets-header bn-dotline">
            {gameLabel(current.game) ? <span>{gameLabel(current.game)}</span> : null}
            <span>{current.label}</span>
            <span>{plural(current.count, 'card')}</span>
          </div>
          <div className="sets-grid">
            {current.cards.map((card) => (
              <SetCardTile
                key={card.sku ?? `${card.name ?? ''}|${card.number_display ?? ''}`}
                card={card}
                market={card.sku === null ? null : prices[card.sku]?.market ?? null}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
