import { useEffect, useState } from 'react'
import type { InventoryCard } from './types'
import type { Failure } from './server'
import { describeFailure, positionLabel, getInventory } from './server'
import './Inventory.css'

/* The inventory view — build-order step 7b. D7's SKU -> positions map, made visible.
 *
 * D7 collapses copies to ONE import row with a copy count and keeps EVERY copy as its own
 * position with its own photo, "because that is what makes an order pull addressable: the
 * app maps SKU -> all positions holding it, and the pull marks one of them sold". That
 * sentence names an app that did not exist when it was written. This is it: one row per
 * SKU carrying the count, expanding to the individual positions holding it.
 *
 * NOTHING HERE WRITES, AND THAT IS A CHOICE RATHER THAN A MISSING ROUTE. This comment used
 * to say the sale "needs a route that does not exist"; `POST /inventory/<box>/<index>/sold`
 * shipped in the same commit as this file, and `server.ts:markSold` calls it — from
 * Fulfillment.tsx, which is where D5 puts a pull. His view earns that write by carrying the
 * guards docs/DESIGN.md asserts on it and only on it: photo-confirm before each pull, undo
 * on every mark-sold with a ten-second window, no destructive action reachable at all. A
 * sold button on a dense owner-side table would be the same irreversible-looking write with
 * neither guard, and a second place to perform one action — which is how two devices end up
 * disagreeing about which copy went. Rejected on the same grounds: making these rows link
 * into his view, which would put a route to the Fulfillment screen in the owner's hands and
 * nothing else, for a lookup that is already answered here. D7's map exists to make a pull
 * ADDRESSABLE; performing it is his screen's job.
 *
 * OWNER-SIDE, so this is the dense end of docs/DESIGN.md's one system, two densities, and
 * the Fulfillment floors do not bind. It speaks the pipeline's vocabulary — `sku`, `pushed`,
 * `staged` — which the Fulfillment banned-word list forbids outright; borrowing his floors
 * here would make it look like his screen and set the expectation that it is safe for him
 * to read, which it is not (D5).
 *
 * ONE GET, GROUPED IN THE BROWSER, KEPT NOWHERE. `GET /inventory` answers with the whole
 * card map and the grouping below is a view of it — not a second store. There is no
 * module-level cache and no state above this component on purpose: leaving the screen
 * throws the response away and coming back re-reads it. D13 has exactly one place inventory
 * lives, and the failure a browser-side copy produces is the same one spec 5.5 rejected
 * queue-and-continue over — two answers to "where is this card", one of them stale and
 * neither of them labelled.
 *
 * THREE THINGS THIS SCREEN DELIBERATELY DOES NOT COMPUTE, because the numbers they need are
 * not on this wire and approximating them is worse than omitting them:
 *
 *   the live cap      `pipeline/join.py:LIVE_QUANTITY_CAP` is 4 and D7 calls it
 *                     configurable. Writing `2 of 4 live` here would put a configurable
 *                     Python constant into TypeScript with nothing keeping the two in step
 *                     — the mistake PullPreview.tsx records having made with D10's divider
 *                     size and undone. Settled by the server reporting the cap, or by the
 *                     run report; until then the state tally below is the honest form.
 *   the refill maths  `Add to Quantity = min(cap - live, backstock)` reads `live` from the
 *                     export's `Total Quantity` (`SkuMatch.live_before`), which is a
 *                     TCGplayer fact this app has never seen. The store's own `live` state
 *                     is the nearest thing and it is what the tally counts.
 *   the price         D8 routes every price through the export and the inventory record
 *                     carries none, so there is no money on this screen at all. Settled by
 *                     a price reaching the wire.
 */

/** One physical card at one position, exactly as `GET /inventory` sent it. `key` is the
 *  store's own `"<box>/<index>"` — identity for React, and the string a `curl /inventory`
 *  is grepped with. Never parsed into a position: a store key and a physical location agree
 *  for the first 25 cards in a box and diverge from card 26 on. */
type Copy = { key: string; card: InventoryCard }

/** One listing state and how many of a group's copies are in it. */
type Tally = { state: string; count: number }

/** One SKU and every copy holding it — one row of D7's map.
 *
 *  `sku` is null for the one group that is not a SKU. Every other field is the DISTINCT set
 *  of what the copies say, in the order the copies say it, rather than one value lifted off
 *  the first copy — see `distinct` for why that matters. */
type Group = {
  sku: string | null
  copies: Copy[]
  names: string[]
  conditions: string[]
  numbers: string[]
  states: Tally[]
}

/* The lifecycle order the states are DISPLAYED in, and deliberately not an enumeration of
 * the enum. `store/master.py:STATES` owns that list, and types.ts already argues that an app
 * enumerating pipeline states needs editing every time one is added.
 *
 * So this is a display order with a guard: a state not named here still renders, after these
 * and in the order it was met. A new state in `store/master.py` therefore shows up unsorted
 * rather than disappearing, which is CLAUDE.md's never-silently-drop-a-card rule applied to
 * a tally instead of to a row.
 *
 * `staged` and `live` are kept apart here because they are kept apart in the store, and
 * `store/master.py` says why in as many words: collapsing them makes D7's refill math wrong,
 * since `min(cap - live, backstock)` reads the LIVE number and an import that was staged and
 * never moved live has no live quantity at all. A display that merged them would hide
 * exactly the box that is not earning.
 */
const STATE_ORDER: readonly string[] = [
  'captured',
  'identified',
  'pushed',
  'staged',
  'live',
  'sold',
]

/* A record that reached the store with no state, said in a shape no state can be confused
 * with: lower case with a space, which no member of `STATES` contains. Same trick as the
 * capture screen's `no claim` and the pull preview's `no label · 3/30` — a stand-in for a
 * machine string must never be readable as one.
 *
 * The type says `state: string` and `store/master.py` defaults the field, so this should be
 * unreachable. It exists because the alternative is a copy that counts toward the group total
 * and appears in no tally, which is a card going quietly missing from a number the screen is
 * read for. */
const NO_STATE = 'no state'

/* This file's copy of `describeFailure` said "worth sharing when a third screen needs it, not
 * before". A third screen needed it in the same session, so it is in server.ts now, beside
 * the `ServerError` it destructures — which is where all three copies' comments pointed. */

/* The position label is READ off the wire and never composed here — `server.ts:positionLabel`
 * holds the rule and the argument for it, since this file and the pull preview carried
 * identical copies. What is still this screen's is the fallback at the call site: a row with
 * no label shows the store key with the words `no label` in front of it, because `3/30` bare
 * reads like a position and is not one. */

/* The collector number as the model returned it, unpadded, or null when there is none to
 * show. `pipeline/join.py:join_key` zero-fills to three digits to match the export's
 * `Number` column; doing that here would put a string on screen that nothing in the run ever
 * said. Same rule and the same shape as the pull preview's, which is the third small reader
 * of this record — a shared module is the fix if a fourth arrives. */
function collectorNumber(card: InventoryCard): string | null {
  if (card.number === null || card.number.trim() === '') return null
  return card.printed_total === null ? card.number : `${card.number}/${card.printed_total}`
}

/* Every distinct value the copies carry, in the order they carry it, blanks dropped.
 *
 * THE POINT IS THAT IT DOES NOT PICK. Two copies of one SKU that were read as `Rhyhorn` and
 * `Rhydhorn` are one identification that went wrong — a T1 recorded miss, name misread with
 * the number right — and taking the first copy's name would put the wrong one on screen half
 * the time and hide the disagreement the other half. Showing both is not a judgement about
 * which is correct, which is a thing this screen has no business making. */
function distinct(values: readonly (string | null)[]): string[] {
  const seen: string[] = []
  for (const value of values) {
    if (value === null) continue
    const trimmed = value.trim()
    if (trimmed !== '' && !seen.includes(trimmed)) seen.push(trimmed)
  }
  return seen
}

function tally(copies: readonly Copy[]): Tally[] {
  const counts = new Map<string, number>()
  for (const copy of copies) {
    const state =
      typeof copy.card.state === 'string' && copy.card.state.trim() !== ''
        ? copy.card.state
        : NO_STATE
    counts.set(state, (counts.get(state) ?? 0) + 1)
  }
  const known = STATE_ORDER.filter((state) => counts.has(state))
  const rest = [...counts.keys()].filter((state) => !STATE_ORDER.includes(state))
  return [...known, ...rest].map((state) => ({ state, count: counts.get(state) ?? 0 }))
}

/* The whole card map, grouped into D7's rows.
 *
 * BOX-WALK ORDER THROUGHOUT — box, then index. Inside a group it is the order
 * `store/master.py:positions_for_sku` returns, which is the order a pull walks the boxes in;
 * between groups it orders by each group's earliest copy, because a `Map` keeps insertion
 * order and the copies are sorted before they are bucketed.
 *
 * Rejected for the group order: copy count descending, which puts D7's multi-copy cases —
 * the ones this screen exists for — at the top. It loses because the order would reshuffle
 * every time a copy sells, and a row you looked at yesterday would be somewhere else today;
 * the count is on every row anyway. ASSUMPTION, and the doc does not settle it: docs/DESIGN.md
 * argues a sort order for the review queue only, where price decides. Watching the owner look
 * something up here settles it.
 *
 * The arithmetic matches PullPreview.tsx's. A record whose box will not coerce to a number
 * sorts wherever `Object.entries` put it rather than being dropped — it is the same record
 * `do_inventory` leaves without a label and `GET /status` reports, and it stays on screen. */
function groupBySku(cards: Record<string, InventoryCard>): Group[] {
  const copies: Copy[] = Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)

  /* Keyed by `string | null` with no sentinel string, because a sentinel would have to be a
   * value no TCGplayer Id can take and nothing here can promise that. `null` is a key a Map
   * holds natively. */
  const buckets = new Map<string | null, Copy[]>()
  for (const copy of copies) {
    // An empty string is not a SKU. Treated as none rather than as a group of its own, which
    // would be a row nothing can ever be listed under.
    const raw = copy.card.sku
    const sku = raw === null || raw.trim() === '' ? null : raw.trim()
    const held = buckets.get(sku)
    if (held === undefined) buckets.set(sku, [copy])
    else held.push(copy)
  }

  const groups = [...buckets.entries()].map(([sku, held]) => ({
    sku,
    copies: held,
    names: distinct(held.map((copy) => copy.card.name)),
    conditions: distinct(held.map((copy) => copy.card.condition)),
    numbers: distinct(held.map((copy) => collectorNumber(copy.card))),
    states: tally(held),
  }))

  // The no-SKU group last, wherever its earliest copy landed. It is the one group that is not
  // a row of D7's map, and reading down a list of SKUs should not run through it.
  return [...groups.filter((g) => g.sku !== null), ...groups.filter((g) => g.sku === null)]
}

/** `1 copy`, `4 copies`. */
function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/* The date a copy entered its current state, without the time.
 *
 * A day is the granularity anything here is acted on — `store/master.py` measures a stale
 * staged import in days, and D7's refill is a decision made per import rather than per
 * minute. The full stamp is in `inventory.json` for anyone who needs the seconds.
 *
 * A stamp that does not split is shown whole rather than blanked: it is what the store
 * actually holds, and the screen's job is to say so. */
function sinceDay(stamp: string | null): string {
  if (stamp === null || stamp.trim() === '') return 'unknown'
  const day = stamp.split('T')[0]
  return day === undefined || day === '' ? stamp : day
}

export function Inventory() {
  /* Null means "not read yet", which is a different thing from an empty array, and the two
   * render differently below — a store with no cards in it is a fact, and a store that has
   * not answered is not. */
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first response can land after the
    // second one; the flag makes the late arrival a no-op rather than a flicker. Same shape
    // as the pull preview's.
    let live = true
    getInventory().then(
      (inventory) => {
        if (!live) return
        // Grouped once, here, rather than memoised at render: the response is the only input
        // and it changes exactly when this runs.
        setGroups(groupBySku(inventory.cards))
        setFailure(null)
      },
      (err) => {
        if (!live) return
        setGroups(null)
        setFailure(describeFailure(err))
      },
    )
    return () => {
      live = false
    }
  }, [reloads])

  /* Three counts, and the third is the one worth publishing beside the other two: copies the
     pipeline has written no import row for. It is the gap between what is in the boxes and
     what is for sale, and a screen that reported only SKUs and copies would let that number
     grow without ever naming it. */
  const skus = groups === null ? 0 : groups.filter((group) => group.sku !== null).length
  const copies = groups === null ? 0 : groups.reduce((n, group) => n + group.copies.length, 0)
  const withoutSku =
    groups === null ? 0 : (groups.find((group) => group.sku === null)?.copies.length ?? 0)

  return (
    <main className="inventory">
      <header className="inventory-head">
        <h1 className="inventory-title">Inventory</h1>
        <p className="inventory-lede">
          Every copy of every card, grouped by the SKU it was listed under. One SKU is one row
          in an import file; each copy beneath it is a physical card at its own position, and a
          pull takes one of them. Nothing on this screen changes anything.
        </p>
        <div className="inventory-controls">
          {/* A reload is a GET, and re-reading the store is not acting on it. It earns its
              place for the reason the pull preview's does: the alternative is teaching the
              owner to reload the browser. No accent fill — docs/DESIGN.md reserves the solid
              fill for a screen with exactly one thing to do, and this screen's one thing is
              to be read. */}
          <button
            className="inventory-reload"
            type="button"
            onClick={() => setReloads((n) => n + 1)}
          >
            Reload
          </button>
          {groups === null ? null : (
            <span className="inventory-count">
              {count(skus, 'sku', 'skus')} · {count(copies, 'copy', 'copies')}
              {withoutSku === 0 ? null : ` · ${withoutSku} without a sku`}
            </span>
          )}
        </div>
      </header>

      {failure === null ? null : (
        <div className="inventory-note">
          <p className="inventory-note-text">{failure.message}</p>
          {/* The code beneath the sentence, never the sentence again — docs/DESIGN.md's
              human-label-large, machine-string-small rule. What goes here is the greppable
              token, which is the only way from what is on screen to what the server said. */}
          <p className="inventory-machine">{failure.code}</p>
        </div>
      )}

      {groups === null && failure === null ? (
        <p className="inventory-note-text">Reading the inventory.</p>
      ) : null}

      {groups !== null && groups.length === 0 ? (
        <p className="inventory-note-text">No cards captured yet.</p>
      ) : null}

      {groups !== null && groups.length > 0 ? (
        <div className="inventory-groups">
          {groups.map((group) => (
            <GroupRow key={group.sku ?? 'without-a-sku'} group={group} />
          ))}
        </div>
      ) : null}
    </main>
  )
}

/* One group: the summary that is always visible, and the copies underneath it.
 *
 * `<details>` rather than a button and a `useState` set of open keys, for the reason App.tsx
 * gives for using plain anchors and no click handler: the browser already does this, and
 * reproducing it in React would be code to keep working — keyboard, focus and the open state
 * itself — in exchange for nothing this screen needs.
 *
 * COLLAPSED BY DEFAULT, and this one is an ASSUMPTION the doc does not settle. A Gate B run
 * may be two hundred cards (capture-app spec §10.1), and open by default is a two-hundred-row
 * wall on a screen whose first job is to say how many copies of what exist. The summary
 * carries the count and the state tally, which is most of what a lookup wants; the positions
 * are one click away. Watching a real run settles it — if every group gets opened, they
 * should start open. */
function GroupRow({ group }: { group: Group }) {
  const loose = group.sku === null

  /* The copy rows carry a card name only where the summary above cannot say it for them:
   * the no-SKU group, whose copies are DIFFERENT cards, and a SKU whose copies were read as
   * more than one name. A SKU group is by definition one card, and repeating its name down
   * forty rows is the dense-grey-table failure docs/DESIGN.md names by the front door. */
  const showNames = loose || group.names.length > 1

  /* The machine line under the name. `sku: null` rather than a friendlier phrase for the
   * group that has none — the field and its state, in the shape the pull preview's
   * `photo: null` panel established, so the screen and a `curl /inventory` use one vocabulary.
   *
   * Distinct values are joined rather than reduced to one. For `sku` there is only ever the
   * one; for condition and number there should be, and a group showing two is a run worth
   * looking at rather than a display to tidy. */
  const meta = loose
    ? ['sku: null']
    : [
        `sku ${group.sku ?? ''}`,
        ...(group.conditions.length > 0 ? [group.conditions.join(' / ')] : []),
        ...(group.numbers.length > 0 ? [group.numbers.join(' / ')] : []),
      ]

  return (
    <details className="inventory-group">
      <summary className="inventory-summary">
        {/* Drawn rather than left to the browser's own disclosure triangle. The native marker
            is sized and coloured by the browser and differs between the one the owner works
            in and the Chromium `make screenshot` renders — and comparing that render against
            the reference is the loop docs/DESIGN.md calls mandatory. A glyph in the utility
            face is one system in both. */}
        <span className="inventory-marker" aria-hidden="true" />

        {/* The copy count is the number D7 is about, so it is the utility face and the
            heaviest thing in the row. */}
        <span className="inventory-copies-count">{count(group.copies.length, 'copy', 'copies')}</span>

        <span className="inventory-main">
          <span className="inventory-name">
            {loose
              ? 'No SKU yet'
              : group.names.length === 0
                ? 'Not identified yet'
                : group.names.join(' / ')}
          </span>
          <span className="inventory-meta">{meta.join(' · ')}</span>
        </span>

        {/* Every state present, none of them merged. `staged` and `live` are two facts about
            two different things — see STATE_ORDER. */}
        <span className="inventory-tally">
          {group.states.map((entry) => (
            <span className="inventory-tally-item" key={entry.state}>
              <span className="inventory-tally-state">{entry.state}</span>
              <span className="inventory-tally-count">{entry.count}</span>
            </span>
          ))}
        </span>
      </summary>

      <div className="inventory-body">
        {loose ? (
          <p className="inventory-note-text">
            A card is given a SKU when <code className="inventory-inline">emit</code> writes its
            row into an import file, and never before — so this group holds every copy the
            pipeline has not pushed yet. Cards still to be identified or joined are here, and so
            are the backstock copies past the live cap, which{' '}
            <code className="inventory-inline">emit</code> leaves unpushed by design (D7). None
            of them is lost: each one sits at a position in a box, and stays visible here until a
            run writes a row for it.
          </p>
        ) : null}

        {/* A table because this is one: four fields repeated per copy, read down a column.
            docs/DESIGN.md's warning about the cataloguing tools that became spreadsheets is
            about hierarchy and weight rather than about the element — and the hierarchy here
            is between the group above and its copies, which are deliberately quieter. */}
        <table className={showNames ? 'inventory-table inventory-table-named' : 'inventory-table'}>
          <thead>
            <tr>
              <th className="inventory-cell-position">Position</th>
              {showNames ? <th className="inventory-cell-name">Card</th> : null}
              <th className="inventory-cell-state">State</th>
              <th className="inventory-cell-since">Since</th>
            </tr>
          </thead>
          <tbody>
            {group.copies.map((copy) => (
              <tr key={copy.key}>
                <td className="inventory-cell-position">
                  {positionLabel(copy.card) ?? `no label · ${copy.key}`}
                </td>
                {showNames ? (
                  <td className="inventory-cell-name">
                    {copy.card.name ?? 'not identified yet'}
                  </td>
                ) : null}
                {/* The pipeline's own word, verbatim. A friendly label would be a second
                    vocabulary nothing audits, which is the drift docs/DESIGN.md shows reason
                    codes as machine strings to avoid. */}
                <td className="inventory-cell-state">{copy.card.state}</td>
                <td className="inventory-cell-since">{sinceDay(copy.card.state_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
