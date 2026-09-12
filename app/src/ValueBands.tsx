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
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button, Chip, EmptyState, Notice, PageHeader, Pill, Segmented, Stat } from './kit'
import { PositionLabel } from './PositionLabel'
import { getValueTable } from './server'
import type { ValueBox, ValueCopy, ValueTable } from './types'
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

/** How many rows are drawn before the operator asks for more. The screen does NOT virtualize —
 *  `#/pricing` already draws ~423 pricing rows, each with a text input, a popover anchor and
 *  per-keystroke field state, where a row here is a link and two figures. What a page does is
 *  keep the FIRST paint cheap on a 1,042-row cheap band; pressing for more is the operator
 *  saying they want it. */
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
 *  chosen on this screen. A server figure would describe a slice the server was not told about.
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
    const part = row.label?.split(' · ')[1]
    if (part !== undefined) sections.add(`${row.box}/${part}`)
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

/** The priced rows at one end, in the order the server sorted them.
 *
 *  A CARD WITH NO PRICE IS IN NEITHER BAND, and that is not a drop: every one is drawn in full
 *  at the foot with the reason it cannot be ranked. A band is a claim about money and a card
 *  with no price belongs to neither end of one — sorting it to the cheap end would sweep it
 *  into a bulk pull, which is the wrong answer wearing the shape of a confident one. */
function ordered(table: ValueTable, end: ValueEnd, box: number | null): ValueCopy[] {
  const priced = table.copies.filter(
    (row) => row.market !== null && (box === null || row.box === box),
  )
  return end === 'top' ? priced : [...priced].reverse()
}

function slice(rows: readonly ValueCopy[], end: ValueEnd, cut: Cut, threshold: string | null, price: string): ValueCopy[] {
  if (cut === 'price' || cut === 'cutoff') {
    const bar = cut === 'cutoff' ? num(threshold) : num(price)
    if (bar === null) return [...rows]
    /* THE CUT-OFF IS A LINE AND THE TWO ENDS TAKE OPPOSITE SIDES OF IT — the same partition
       `emit` makes, where at or above the figure a card earns a listing and below it the card
       is the cheap half (D9, amended). So the cheap end is `< bar` and never `<= bar`, or both
       bands would claim a card sitting exactly on the line. */
    return rows.filter((row) => {
      const market = num(row.market)
      if (market === null) return false
      return end === 'top' ? market >= bar : market < bar
    })
  }
  /* A PERCENTILE BAND NEVER ROUNDS TO NOTHING WHILE THERE IS SOMETHING TO RANK. `Math.round(3 *
     5 / 100)` is 0, so a store with fewer than ten priced cards opened on an EMPTY default band
     — a screen reporting that a store with cards in it holds nothing valuable. Caught by the
     browser suite, on fixtures of one and three rows, before it reached a fresh checkout.
     The top 5% of three cards is the top card, which is the honest reading of the question. */
  return rows.slice(0, Math.max(rows.length === 0 ? 0 : 1, Math.round((rows.length * SHARES[cut]) / 100)))
}

/** Every copy of this SKU in the band's own parent list, so a duplicate row can say which one
 *  it is. Seven Vilemaw rows are seven reaches and therefore seven rows; `copy 3 of 7` is what
 *  keeps that reading as a fact rather than as a repetition. */
function stacks(rows: readonly ValueCopy[]): Map<string, ValueCopy[]> {
  const out = new Map<string, ValueCopy[]>()
  for (const row of rows) {
    if (row.sku === null) continue
    const seen = out.get(row.sku)
    if (seen === undefined) out.set(row.sku, [row])
    else seen.push(row)
  }
  for (const group of out.values()) group.sort((a, b) => a.box - b.box || a.index - b.index)
  return out
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

function ValueRow({ row, stack }: { readonly row: ValueCopy; readonly stack: readonly ValueCopy[] | undefined }) {
  const asking = typeof row.answer === 'string' || typeof row.answer === 'number' ? String(row.answer) : null
  const held = row.answer !== null && typeof row.answer === 'object'
  const which = stack === undefined || stack.length < 2
    ? null
    : `copy ${stack.findIndex((one) => one.box === row.box && one.index === row.index) + 1} of ${stack.length}`
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
          {meta.join(' · ')}
          {row.live === 0 ? null : (
            <>
              {meta.length === 0 ? null : ' · '}
              <span className="value-live">
                <span className="bn-dot bn-dot-live" />
                {`${row.live} listed`}
              </span>
            </>
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
  const [table, setTable] = useState<ValueTable | null>(null)
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
  const [gapsShown, setGapsShown] = useState(PAGE)
  const live = useRef(true)

  const read = useCallback(async () => {
    setFailed(null)
    try {
      const answer = await getValueTable()
      if (live.current) setTable(answer)
    } catch (error) {
      if (live.current) setFailed(error instanceof Error ? error.message : String(error))
    }
  }, [])

  useEffect(() => {
    live.current = true
    void read()
    return () => {
      live.current = false
    }
  }, [read])

  /* THE PAGE RESETS WHEN THE BAND MOVES. `shown` counts into a list that has just been replaced,
     so carrying it over draws 400 rows of a 12-row band's successor without anybody asking. */
  useEffect(() => setShown(PAGE), [end, cut, price, view, box])
  useEffect(() => setGapsShown(PAGE), [box])

  const pool = useMemo(() => (table === null ? [] : ordered(table, end, box)), [table, end, box])
  const rows = useMemo(
    () => (table === null ? [] : slice(pool, end, cut, table.threshold, price)),
    [table, pool, end, cut, price],
  )
  const stack = useMemo(() => stacks(pool), [pool])
  const reach = useMemo(() => pulls(rows), [rows])
  const worth = useMemo(() => rows.reduce((sum, row) => sum + (num(row.market) ?? 0), 0), [rows])
  /* EVERY ON-HAND CARD THIS SCREEN CANNOT RANK, in the order the server sent them. Scoped with
     the band, so a drawer's own unread cards are what its panel lists. */
  const gapRows = useMemo(
    () => (table === null ? [] : table.copies.filter((row) => row.market === null && (box === null || row.box === box))),
    [table, box],
  )

  /* EVERY BAND'S COUNT IS ON ITS OWN CHIP, so the default hides nothing — the operator can see
     that the cheap end holds 1,042 cards without pressing anything. */
  const counts = useMemo(() => {
    if (table === null) return null
    const of = (which: Cut) => slice(pool, end, which, table.threshold, price).length
    return { p1: of('p1'), p5: of('p5'), p10: of('p10'), cutoff: of('cutoff') }
  }, [table, pool, end, price])

  const drawers = useMemo(() => {
    if (table === null) return []
    const order = [...table.boxes]
    /* WHICH DRAWER HOLDS THE MONEY AND WHICH DRAWER IS BULK ARE TWO QUESTIONS, which is why
       `ValueBox` carries both figures: the rich end ranks on the drawer's total and the cheap
       end on what a card out of it is worth. */
    return end === 'top'
      ? order.sort((a, b) => (num(b.total) ?? 0) - (num(a.total) ?? 0))
      : order.sort((a, b) => (num(a.per_card) ?? 0) - (num(b.per_card) ?? 0))
  }, [table, end])

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
        <PageHeader eyebrow="Workflow · Price · By value" title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <Notice tone="danger" title="The store could not be read" code={failed}>
          Nothing was changed. Try again once the capture server is answering.
        </Notice>
        <div><Button variant="primary" onClick={() => void read()}>Try again</Button></div>
      </main>
    )
  }

  if (table === null || counts === null) {
    return (
      <main className="bn-page value-page">
        <PageHeader eyebrow="Workflow · Price · By value" title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <p className="value-loading">Reading every card on hand…</p>
        <div className="bn-skeleton value-skeleton" aria-hidden="true" />
      </main>
    )
  }

  const gaps = table.unrankable
  /* THE WIDEST BAND'S OWN EXTREME, which is what an empty band has to name — "nothing is worth
     $50 or more" is only half an answer without "the most valuable card you own is $47.57". */
  const best = pool.length === 0 ? null : pool[0]
  const scoped = box === null ? null : table.boxes.find((one) => one.box === box) ?? null
  /* A BAND THAT IS REAL MONEY AND ROUNDS TO NOTHING SAYS SO RATHER THAN SAYING ZERO — the two
     cards worth listing in box 2 are $0.72 of $2,531.64, and "0% of everything you own" is a
     false sentence about a band the operator is standing in. `money.ts:roundsToNothing` makes
     the same distinction about a figure. */
  const percent = table.totals.valued === 0 ? 0 : (worth / (num(table.totals.value) ?? 1)) * 100
  const share = percent > 0 && percent < 0.5 ? 'under 1%' : `${Math.round(percent)}%`

  if (table.totals.cards === 0) {
    return (
      <main className="bn-page value-page">
        <PageHeader eyebrow="Workflow · Price · By value" title="What's worth pulling" actions={<Button onClick={onLeave}>Back to pricing</Button>} />
        <EmptyState
          icon="box"
          title="Nothing is in a box yet"
          body="Capture a box and every card in it gets an address and a price. This is where the most and least valuable ones will be."
          actions={<Button variant="primary" onClick={() => { window.location.hash = '#/capture' }}>Capture a box</Button>}
        />
      </main>
    )
  }

  return (
    <main className="bn-page value-page">
      <PageHeader
        eyebrow="Workflow · Price · By value"
        title="What's worth pulling"
        lede={`${whole(table.totals.valued)} of ${whole(table.totals.cards)} cards on hand carry a price, ${cash(table.totals.value)} at market.`}
        actions={<Button onClick={onLeave}>Back to pricing</Button>}
      />

      {table.totals.valued === 0 ? (
        <EmptyState
          icon="sparkles"
          title="Nothing here has a price yet"
          body={`You have ${whole(table.totals.cards)} cards in ${whole(table.boxes.length)} drawers and no run has read any of them. A run reads a box and puts a price on every card in it.`}
          actions={<Button variant="primary" onClick={() => { window.location.hash = '#/runs' }}>Start a run</Button>}
        />
      ) : (
        <>
          {table.sources.length === 1 ? (
            <Notice tone="info" title="These prices came out of one file">
              A thin reading makes a thin ranking, not a store with nothing valuable in it.
            </Notice>
          ) : null}

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
                  title="Your cut-off is set at the top of the pricing screen"
                >
                  {table.threshold === null
                    ? end === 'top' ? 'Over your cut-off' : 'Under your cut-off'
                    : end === 'top' ? `Over $${table.threshold}` : `Under $${table.threshold}`}
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
                  ? `Your ${whole(table.boxes.length)} drawers, richest first.`
                  : `Your ${whole(table.boxes.length)} drawers, cheapest card first.`
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
                  threshold={table.threshold}
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
                pool.length === 0
                  ? 'Nothing here has a price.'
                  : `The ${end === 'top' ? 'most' : 'least'} valuable card you own is ${best?.name ?? 'one nobody has named'} at ${cash(best?.market)}, in box ${best?.box ?? '?'}.`
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
                <ValueRow key={`${row.box}/${row.index}`} row={row} stack={row.sku === null ? undefined : stack.get(row.sku)} />
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
                They are on the shelf and this screen cannot say what they are worth. Each one
                needs a different thing done to it.
              </p>
              {/* ALL THREE ARE DRAWN, INCLUDING AT ZERO — a true and useful statement, and it is
                  what keeps this panel's height off the state of the store (D118). */}
              <ul className="value-causes">
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.never_identified)}</span>
                  <span className="value-cause-says">
                    <strong>Never identified.</strong> These have a photograph and no run has read them.
                  </span>
                  {gaps.never_identified === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/runs' }}>Start a run</Chip>
                  )}
                </li>
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.read_nothing)}</span>
                  <span className="value-cause-says">
                    <strong>Nothing was read off the photograph.</strong> A run looked and came back with no name and no number.
                  </span>
                  {gaps.read_nothing === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/inventory' }}>Look at them</Chip>
                  )}
                </li>
                <li className="value-cause">
                  <span className="value-cause-count">{whole(gaps.no_reading)}</span>
                  <span className="value-cause-says">
                    <strong>No export prices them.</strong> Read and named, and no catalogue row this machine holds matches.
                  </span>
                  {gaps.no_reading === 0 ? <span /> : (
                    <Chip onClick={() => { window.location.hash = '#/runs' }}>Fetch an export</Chip>
                  )}
                </li>
              </ul>
              {!openGaps ? null : (
                <div className="value-gap-rows">
                  {gapRows
                    .slice(0, gapsShown)
                    .map((row) => (
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
                      is 190 cards silently missing from the one place they are accounted for. */}
                  {gapRows.length > gapsShown ? (
                    <div className="value-more">
                      <Button onClick={() => setGapsShown((seen) => seen + PAGE)}>
                        {`Show ${whole(Math.min(PAGE, gapRows.length - gapsShown))} more`}
                      </Button>
                      <span className="value-more-says">
                        {`${whole(gapsShown)} of ${whole(gapRows.length)} shown`}
                      </span>
                    </div>
                  ) : null}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </main>
  )
}
