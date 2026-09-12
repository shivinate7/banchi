import type { GameRegistry, InventoryCard } from './types'
import { GAP_MINUTES, sittings } from './storeHistory'

/* WHAT TO IDENTIFY, AS A STATE AND ITS NARROWINGS — the composer's first stage, in the
 * vocabulary the front door already speaks.
 *
 * THE DEFECT THIS MODULE IS THE ANSWER TO. `standing.ts` emits the store's one ranked sentence
 * on `#/` — *"412 cards are photographed and not identified"* — and it deliberately names no
 * box, because `ServerStatus.states` is store-wide and attributing a store-wide figure to one
 * drawer would be a sentence the data cannot support. That sentence routed to `#/runs`, whose
 * first stage asked `Which boxes`. So the front door spoke in STATES and the room behind it
 * spoke in DRAWERS, and the operator was told a fact about the whole store and then asked to
 * pick a drawer — which is a second question, about a different thing, with no way to answer
 * the first.
 *
 * `#/pricing` HAD ALREADY SOLVED THIS AND IS THE MODEL. `pipeline_routes.py:_unreachable`
 * answers `{captured, in_review, unjoined, reallocated}` — four states, store-wide, a door
 * each — under a docstring saying they are "named rather than left out (`CLAUDE.md`: never
 * silently drop a card)". `captured` is the one of the four this composer can act on; the
 * other three have their own doors, and this module does not invent a press for them.
 *
 * ─── THE DRAWER IS A NARROWING, NOT THE QUESTION ────────────────────────────────────────────
 *
 * The selection starts as every card in the state, and a drawer, a game or a sitting NARROWS
 * it. That inverts the old stage without costing the old press: ticking one drawer yields the
 * cart `[{box: N}]`, whole box and no indices, which is byte for byte what pressing that box
 * sent before. `Ticking box 4 alone IS today's press` is the test of this file.
 *
 * TWO OF THE THREE NARROWINGS CROSS DRAWERS AND ONE DOES NOT, and that is what decides
 * whether a leg carries `indices`. A drawer tick names the drawer, and "everything not yet
 * identified in box 4" is exactly "box 4" to `identify` — the cache is what skips the cards
 * already answered, which is the same reason a whole-box press has always been safe. A game or
 * a sitting cuts ACROSS drawers, so each leg carries the matching indices, which is the shape
 * `#/inventory`'s handoff has always produced. Nothing new goes on the wire.
 *
 * ─── WHY THE FIGURES ARE DERIVED HERE AND NOT READ OFF A ROUTE ──────────────────────────────
 *
 * `BoxRecord` carries no per-state counts — `cards`, `on_hand`, `sold`, `retired`, `moved`,
 * `listed`, and none of them is "not yet identified" — and `ServerStatus.states` is one number
 * for the whole store. So the per-drawer, per-game and per-sitting figures have exactly one
 * source on today's wire: `GET /inventory`'s card map, where `state` is a field the server
 * wrote and this module only counts.
 *
 * THAT IS NOT `server.ts`'s FORBIDDEN ARITHMETIC. What that module forbids is computing a rule
 * the pipeline owns — the send list, the cost, a price. Counting records whose `state` field
 * equals `'captured'` is reading a field, and `Home.tsx` already clusters the same payload into
 * sittings for the same reason. The number that GATES THE SPEND is still the server's: the
 * preflight's `total`, unchanged.
 *
 * A ROUTE THAT ANSWERED THESE COUNTS WOULD REPLACE ONE FUNCTION HERE and nothing else, which
 * is why deriving them is not a fork.
 *
 * ─── THE SITTING IS `storeHistory.ts`'s, AND THERE IS NO SECOND DEFINITION ──────────────────
 *
 * `GAP_MINUTES` is 30 because the answer does not move across a four-fold plateau, and that
 * constant is imported rather than restated so that `#/`, `#/capture` and this stage cannot
 * disagree about where one sitting ends. The window comes from `sittings()` over EVERY card —
 * not over the un-identified subset — because a sitting is a fact about the store's history
 * rather than about what is left in it: clustering the subset alone splits one real sitting in
 * two wherever the identified cards filled a gap, and then undercounts it.
 */

/** The pipeline state this composer can act on. `_unreachable`'s own first name for it, and
 *  the only one of its four with a press behind it here. */
export const CAPTURED = 'captured'

/** What to identify: a state, and up to three narrowings of it. Empty lists mean "not
 *  narrowed on that axis" — never "nothing", which is a state this screen cannot be in. */
export type RunSelection = {
  readonly state: typeof CAPTURED
  /** Drawers ticked. Empty is every drawer holding the state. */
  readonly boxes: readonly number[]
  /** Games ticked. Empty is every game. */
  readonly games: readonly string[]
  /** Only the cards photographed in the newest sitting. */
  readonly sitting: boolean
}

/** The default, and the one the primary row draws as ticked. */
export const EVERYTHING: RunSelection = { state: CAPTURED, boxes: [], games: [], sitting: false }

/** Is anything narrowing the state? The primary row reads pressed when this is false. */
export function narrowed(selection: RunSelection): boolean {
  return selection.boxes.length > 0 || selection.games.length > 0 || selection.sitting
}

/** Does this selection cut WITHIN a drawer? The one question that decides whether a leg
 *  carries `indices` — see the header. A drawer tick alone does not. */
export function cutsWithinADrawer(selection: RunSelection): boolean {
  return selection.games.length > 0 || selection.sitting
}

/** One card in the state, reduced to the four facts the chips and the legs are built from. */
export type Pending = {
  readonly box: number
  readonly index: number
  /** The game key as the record carries it. Never null: `InventoryCard.game` is null on a
   *  record written before the field existed and `types.ts` says the pipeline reads that as
   *  `pokemon`, so the registry's own default is applied here rather than at three call
   *  sites. */
  readonly game: string
  /** `captured_at` as epoch milliseconds, or null where the record carries none — which is
   *  not a zero and never joins a sitting. */
  readonly at: number | null
}

/** Every card the store holds in the state, in `(box, index)` order.
 *
 *  ORDERED HERE SO NO CALLER HAS TO. The indices on a leg are what the route turns into a
 *  symlink directory and what the operator reads back on the reading stage; an order that
 *  depended on object key iteration would be stable in practice and unstated, which is the
 *  kind of thing that moves under a store migration. */
export function pending(
  cards: Record<string, InventoryCard> | null,
  registry: GameRegistry | null,
): Pending[] {
  if (cards === null) return []
  const fallback = registry?.default ?? 'pokemon'
  const rows: Pending[] = []
  for (const card of Object.values(cards)) {
    if (card.state !== CAPTURED) continue
    if (typeof card.box !== 'number' || typeof card.index !== 'number') continue
    const stamp = typeof card.captured_at === 'string' ? Date.parse(card.captured_at) : NaN
    rows.push({
      box: card.box,
      index: card.index,
      game: typeof card.game === 'string' && card.game !== '' ? card.game : fallback,
      at: Number.isFinite(stamp) ? stamp : null,
    })
  }
  return rows.sort((a, b) => (a.box === b.box ? a.index - b.index : a.box - b.box))
}

/** The newest sitting's window, in epoch milliseconds, or null where the store has no stamped
 *  card at all. Read off `storeHistory.sittings` over EVERY card for the reason in the header:
 *  the boundary is a fact about the history, not about the leftovers. */
export function newestSitting(
  cards: Record<string, InventoryCard> | null,
): { readonly from: number; readonly to: number } | null {
  const all = sittings(cards, GAP_MINUTES)
  const last = all[all.length - 1]
  if (last === undefined) return null
  const from = Date.parse(last.from)
  const to = Date.parse(last.to)
  return Number.isFinite(from) && Number.isFinite(to) ? { from, to } : null
}

/** A card of the newest sitting. Inclusive at both ends: `sittings` takes them from the first
 *  and last card IN the group, so both boundary cards are members of it. */
function inSitting(row: Pending, window: { from: number; to: number } | null): boolean {
  if (window === null || row.at === null) return false
  return row.at >= window.from && row.at <= window.to
}

/** What each narrowing would hold, so every chip carries its own count before it is pressed.
 *
 *  EVERY FIGURE IS THE UNNARROWED ONE, and that is a decision rather than an oversight. A
 *  chip's count says what THAT narrowing holds — `Box 4 · 133` is a fact about box 4 — and not
 *  what it holds under whatever else is ticked. Counts that moved on every press would be four
 *  numbers re-describing one selection, and the selection's own figure is already stated once,
 *  on the footer line, where the scope belongs. It also keeps D118: no chip appears, vanishes
 *  or changes width when another is pressed. */
export type Census = {
  /** Every card in the state. */
  readonly total: number
  /** How many drawers hold one. */
  readonly drawers: number
  /** Per drawer, ascending by box. Drawers with none are not here; the caller draws the
   *  registry's own list and reads a missing entry as zero. */
  readonly byBox: ReadonlyMap<number, number>
  /** Per game, most first, then by key so the order is total. */
  readonly byGame: readonly { readonly game: string; readonly cards: number }[]
  /** The newest sitting: its window and how many of these cards are in it. Null where the
   *  store has no stamped card, or where nothing in the state falls inside it — a chip that
   *  narrowed to nothing is not offered. */
  readonly sitting: { readonly from: number; readonly to: number; readonly cards: number } | null
}

export function census(
  rows: readonly Pending[],
  window: { readonly from: number; readonly to: number } | null,
): Census {
  const byBox = new Map<number, number>()
  const games = new Map<string, number>()
  let inWindow = 0
  for (const row of rows) {
    byBox.set(row.box, (byBox.get(row.box) ?? 0) + 1)
    games.set(row.game, (games.get(row.game) ?? 0) + 1)
    if (inSitting(row, window)) inWindow += 1
  }
  return {
    total: rows.length,
    drawers: byBox.size,
    byBox: new Map([...byBox].sort((a, b) => a[0] - b[0])),
    byGame: [...games]
      .map(([game, cards]) => ({ game, cards }))
      .sort((a, b) => (b.cards === a.cards ? a.game.localeCompare(b.game) : b.cards - a.cards)),
    sitting: window === null || inWindow === 0 ? null : { ...window, cards: inWindow },
  }
}

/** The cards this selection is over, in `(box, index)` order. */
export function selected(
  selection: RunSelection,
  rows: readonly Pending[],
  window: { readonly from: number; readonly to: number } | null,
): Pending[] {
  const boxes = selection.boxes.length === 0 ? null : new Set(selection.boxes)
  const games = selection.games.length === 0 ? null : new Set(selection.games)
  return rows.filter((row) => {
    if (boxes !== null && !boxes.has(row.box)) return false
    if (games !== null && !games.has(row.game)) return false
    if (selection.sitting && !inSitting(row, window)) return false
    return true
  })
}

/** One leg per drawer, the shape `Runs.tsx` hands the composer and `server.ts` puts on the
 *  wire. `indices` is present only where the selection cuts within a drawer. */
export type SelectionLeg = { readonly box: number; readonly indices: readonly number[] }

/** The cart this selection is.
 *
 *  A DRAWER TICK WITH NO CROSS-CUTTING FILTER IS A WHOLE-BOX LEG, EVEN THOUGH THIS FUNCTION
 *  KNOWS EXACTLY WHICH CARDS IT WOULD BE. That is the point: `{box: 4}` is what the operator
 *  pressed before this change and what `_resolve_legs` has always read as the whole drawer, and
 *  sending the indices instead would build a symlink directory for a scope the route can
 *  already express — a different request for the same intent, on the press that spends money.
 *
 *  A TICKED DRAWER HOLDING NOTHING STILL GETS ITS LEG. The operator asked for that drawer; the
 *  preflight is the thing entitled to answer "nothing to send", and it says so with the figure
 *  on screen. Dropping the leg here would make the drawer they ticked silently absent from the
 *  cost stage. */
export function legsFor(
  selection: RunSelection,
  rows: readonly Pending[],
  window: { readonly from: number; readonly to: number } | null,
): SelectionLeg[] {
  const within = cutsWithinADrawer(selection)
  const matched = selected(selection, rows, window)
  const byBox = new Map<number, number[]>()
  if (!within && selection.boxes.length > 0) {
    for (const box of [...new Set(selection.boxes)]) byBox.set(box, [])
  }
  for (const row of matched) {
    const held = byBox.get(row.box)
    if (held === undefined) byBox.set(row.box, within ? [row.index] : [])
    else if (within) held.push(row.index)
  }
  return [...byBox]
    .sort((a, b) => a[0] - b[0])
    .map(([box, indices]) => ({ box, indices: indices.sort((a, b) => a - b) }))
}

/* ------------------------------------------------------------------ the filter, in the hash
 *
 * A FILTER LIVES IN THE ADDRESS BECAUSE COMPONENT STATE IS NOT A PLACE. `#/runs?state=captured`
 * is what the front door's sentence now points at, and `#/runs?state=captured&box=4` is a
 * drawer's share of it — bookmarkable, linkable from Home, and survivable across a reload,
 * none of which a `useState` has ever been.
 *
 * IT SHARES THE QUERY WITH `?run=`, which `Runs.tsx` has read since Home started linking a run,
 * and neither reader touches the other's keys.
 *
 * ANYTHING UNPARSEABLE IS NO FILTER AT ALL — never a half-read one. Same rule `runHandoff.ts`
 * applies to a stale handoff and D3 rung 0 applies to an identification: a partially understood
 * scope is a scope the operator did not choose, and the press after it spends money. An absent
 * or unknown `state` therefore answers null, and every other key is read only under a `state`
 * that resolved.
 */

const STATE_KEY = 'state'
const BOX_KEY = 'box'
const GAME_KEY = 'game'
const SITTING_KEY = 'sitting'

/** The query half of a hash, whatever the hash's shape. */
function query(hash: string): URLSearchParams {
  return new URLSearchParams(hash.split('?')[1] ?? '')
}

/** The selection the address names, or null where it names none.
 *
 *  A GAME KEY IS NOT VALIDATED AGAINST THE REGISTRY HERE. It cannot be: the registry is
 *  fetched, and a filter has to be readable before that answers. A key the store holds no card
 *  of narrows to nothing and the screen says so with its own figure, which is the honest
 *  rendering of a bookmark whose cards have since been identified. */
export function selectionFromHash(hash: string): RunSelection | null {
  const params = query(hash)
  if (params.get(STATE_KEY) !== CAPTURED) return null
  const boxes = [
    ...new Set(
      params
        .getAll(BOX_KEY)
        .map((value) => Number(value))
        .filter((box) => Number.isInteger(box) && box >= 1),
    ),
  ].sort((a, b) => a - b)
  const games = [...new Set(params.getAll(GAME_KEY).filter((game) => game !== ''))].sort()
  return { state: CAPTURED, boxes, games, sitting: params.get(SITTING_KEY) === '1' }
}

/** The query string for a selection — the keys this module owns, in a fixed order so one
 *  selection has one spelling and a bookmark is stable. Every other key in the hash is the
 *  caller's to carry; `hashFor` below is what does the carrying. */
export function queryFor(selection: RunSelection): string {
  const params = new URLSearchParams()
  params.set(STATE_KEY, selection.state)
  for (const box of [...selection.boxes].sort((a, b) => a - b)) params.append(BOX_KEY, String(box))
  for (const game of [...selection.games].sort()) params.append(GAME_KEY, game)
  if (selection.sitting) params.set(SITTING_KEY, '1')
  return params.toString()
}

/** `#/runs?state=captured&box=4`, preserving every key in `hash` this module does not own.
 *
 *  `null` CLEARS THE FILTER RATHER THAN WRITING AN EMPTY ONE, so closing the dialog leaves an
 *  address that does not reopen it. */
export function hashFor(hash: string, selection: RunSelection | null): string {
  const path = hash.split('?')[0] ?? '#/runs'
  const kept = new URLSearchParams()
  for (const [key, value] of query(hash)) {
    if (key === STATE_KEY || key === BOX_KEY || key === GAME_KEY || key === SITTING_KEY) continue
    kept.append(key, value)
  }
  const mine = selection === null ? '' : queryFor(selection)
  const rest = kept.toString()
  const both = [mine, rest].filter((part) => part !== '').join('&')
  return both === '' ? path : `${path}?${both}`
}

/* ------------------------------------------------------------------------ toggling a chip */

/** Ticking or unticking one drawer. Unticking the last one goes back to every drawer rather
 *  than to nothing: "nothing selected" is a state this stage cannot be in, because the
 *  question it asks is answered by default and the answer is the state itself. */
export function toggleBox(selection: RunSelection, box: number): RunSelection {
  const held = new Set(selection.boxes)
  if (held.has(box)) held.delete(box)
  else held.add(box)
  return { ...selection, boxes: [...held].sort((a, b) => a - b) }
}

/** The same for a game. */
export function toggleGame(selection: RunSelection, game: string): RunSelection {
  const held = new Set(selection.games)
  if (held.has(game)) held.delete(game)
  else held.add(game)
  return { ...selection, games: [...held].sort() }
}

/** The same for the sitting. */
export function toggleSitting(selection: RunSelection): RunSelection {
  return { ...selection, sitting: !selection.sitting }
}

/** What a game is called. The registry authors both halves of that and `types.ts` forbids
 *  deriving one from the other, so a key the registry does not name draws its key — which is
 *  what the store actually holds, and is why a chip is only offered for a game the registry
 *  DOES name (see `gameChips`). */
export function gameLabel(registry: GameRegistry | null, key: string): string {
  return registry?.games.find((entry) => entry.key === key)?.display ?? key
}

/** Which games get a chip: the ones the store holds cards of AND the registry can name.
 *
 *  A GAME THE REGISTRY DOES NOT NAME IS STILL IN THE STATE AND IS NEVER DROPPED — it is in
 *  `total`, in its drawer's count and in the unnarrowed cart. What it does not get is a chip,
 *  because the chip would have to be captioned with a raw enum value, which `docs/DESIGN.md`'s
 *  register rule refuses. The narrowing is unavailable; the cards are not lost. */
export function gameChips(
  registry: GameRegistry | null,
  byGame: Census['byGame'],
): readonly { readonly game: string; readonly cards: number; readonly label: string }[] {
  if (registry === null) return []
  const named = new Map(registry.games.map((entry) => [entry.key, entry.display]))
  return byGame
    .filter((row) => named.has(row.game))
    .map((row) => ({ ...row, label: named.get(row.game) as string }))
}
