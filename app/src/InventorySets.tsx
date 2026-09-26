import { useEffect, useState } from 'react'

import { describeFailure, getInventorySets, type Failure } from './server'
import type { SetGroupCard } from './types'
import { EmptyState, Loading, Notice, Pill, Section } from './kit'
import { patchViewQuery } from './kit/viewState'
import './InventorySets.css'

/* THE OWNER'S "BY SET ORDER" VIEW (D-set-view), a second way of walking `#/inventory`
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
    patchViewQuery({ view: null, box: String(card.box), card: card.cid })
    return
  }
  const text = card.name ?? card.sku ?? card.number_display
  patchViewQuery({ view: null, box: null, card: null, q: text })
}

function SetCardRow({ card }: { readonly card: SetGroupCard }) {
  return (
    <button type="button" className="bn-list-row sets-card-row" onClick={() => openInWalk(card)}>
      <span className="bn-mono sets-card-number">{card.number_display ?? '—'}</span>
      <span className="sets-card-name">{card.name ?? 'Not identified yet'}</span>
      <Pill tone="default">{plural(card.qty, 'copy', 'copies')}</Pill>
    </button>
  )
}

function GroupTitle({ game, setName }: { readonly game: string | null; readonly setName: string }) {
  const label = gameLabel(game)
  return (
    <span className="bn-dotline">
      {label ? <span>{label}</span> : null}
      <span>{setName}</span>
    </span>
  )
}

export function InventorySets({ reloadToken = 0 }: { readonly reloadToken?: number }) {
  const [report, setReport] = useState<Awaited<ReturnType<typeof getInventorySets>> | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)

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

  if (failure !== null) {
    return <Notice tone="danger" title={failure.message} code={failure.code} />
  }
  if (report === null) return <Loading shape="rows" rows={6} />

  const total = report.groups.reduce((sum, group) => sum + qtyOf(group.cards), 0) + qtyOf(report.no_set)
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
      {report.groups.map((group) => (
        <Section
          key={`${group.game ?? ''}:${group.set_name}`}
          title={<GroupTitle game={group.game} setName={group.set_name} />}
          count={plural(qtyOf(group.cards), 'card')}
        >
          <div className="bn-list">
            {group.cards.map((card) => (
              <SetCardRow key={card.sku ?? `${card.name ?? ''}|${card.number_display ?? ''}`} card={card} />
            ))}
          </div>
        </Section>
      ))}
      {report.no_set.length === 0 ? null : (
        <Section title="No set on file" count={plural(qtyOf(report.no_set), 'card')}>
          <div className="bn-list">
            {report.no_set.map((card) => (
              <SetCardRow key={card.sku ?? `${card.name ?? ''}|${card.number_display ?? ''}`} card={card} />
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}
