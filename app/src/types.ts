/* The shapes the capture server speaks.
 *
 * Types and nothing else, so this file emits no JavaScript at all. Under
 * verbatimModuleSyntax every importer has to write `import type` anyway, and a module that
 * compiles to nothing cannot quietly become a second place behaviour lives — which is the
 * whole reason server.ts exists as one owner of the wire (capture-app spec section 4).
 *
 * FIELD NAMES ARE THE SERVER'S, IN THE SERVER'S OWN CASE. Renaming `set_hint` to `setHint`
 * across the wire types was considered and rejected: it puts a translation layer between
 * `server/capture_server.py:_card_summary` and the screen, and the first thing anyone
 * debugging a run does is hold what the app shows against `inventory.json`. Two vocabularies
 * for one record makes that comparison a lookup. The one place camelCase does appear is
 * `server.capture()`'s argument object, which is a TypeScript call site rather than a
 * record — see the note there.
 *
 * Nothing here is validated at runtime; server.ts casts. The reasoning is recorded there,
 * next to the casts, rather than here.
 */

/** The variant toggle on the capture screen, and what the server validates a capture's
 *  `variant` against — `pipeline/variant.py:FINISHES`, same three strings in the same
 *  spelling. D3 rung 1: this is a *claim* the operator makes per stack, not a hint, which
 *  is why a mis-toggled card reviews rather than being silently corrected downstream. */
/* THE FINISH VOCABULARY IS DATA NOW, NOT A TYPE, and this used to be
 * `'normal' | 'holo' | 'reverse_holo'` — Pokemon's three, hard-coded.
 *
 * That union was correct while Pokemon was the only game and it became a defect the moment
 * it was not. `GameEntry.finishes` is `string[]` and differs per game — Riftbound and One
 * Piece stock `normal | foil`, with no reverse holo at all, and `misc` declares none. A
 * literal union of one game's strings cannot express another's, so a screen typed against it
 * silently kept drawing Pokemon's chips whatever game was chosen. Reported from the rig.
 *
 * Widened to `string` deliberately rather than to a union of every game's finishes: that
 * union would be a second copy of `pipeline/games.py` maintained by hand on this side, which
 * is the mirror `types.ts` and `CaptureScreen.tsx` both already refuse for the registry
 * itself. The vocabulary has ONE home and the server is what enforces it — a finish outside
 * the chosen game's list is refused with `variant_invalid`, and the app's job is to offer
 * only what `GET /games` said, never to re-decide it. */
export type Finish = string

/** What the finish control on the capture screen holds. A SET since D3 rung 1's amendment
 *  of 2026-08-23, and `[]` is NO CLAIM: the operator has not said anything about this
 *  stack, so nothing is sent and `sidecar_payload` writes no `variant` key at all — the
 *  file stays a record of claims actually made, which is the rule `set_hint` already
 *  followed on this side of the wire and `variant` did not.
 *
 *  HOW MANY MEMBERS IT HAS DECIDES WHAT IT DOES, and that is the whole of the amendment.
 *  One member DETERMINES, exactly as this rung always has. Two or more FILTER: the
 *  candidate rows narrow to the claimed finishes and the rungs below choose within what
 *  survives. A stack that genuinely holds two finishes had no honest claim available
 *  before — name one and be wrong about half the cards, or claim nothing and throw away
 *  the half of the truth you did know.
 *
 *  `[]` RATHER THAN `null`, AND NOT BOTH. It was `Finish | null` and the null was the
 *  no-claim state; an empty set is the same state, and D3 says so outright ("an empty set
 *  is no claim at all, identical to the null this field has always allowed"). Two spellings
 *  of one state is the thing a reader has to learn and the thing a `?? []` somewhere gets
 *  wrong. `InventoryCard.rarity_claim` is the shape this is deliberately copying — D3
 *  chose it precisely so a capture screen whose claims all work one way is one rule to hold.
 *
 *  THE EMPTY CLAIM IS WHAT KEEPS D3 RUNGS 2 AND 3 REACHABLE, and that is the reason it
 *  exists rather than tidiness — the argument transfers from the null verbatim.
 *  `pipeline/variant.py:resolve` consults the catalog (rung 2, CATALOG_FORCED) and
 *  cross-checks detection (rung 3) only where no claim was made. An app that always sends
 *  one makes both rungs dead for every card this product will ever capture: a holofoil-only
 *  SV-era rare shot with an untouched control would return METADATA_NOT_STOCKED and cost a
 *  review-queue tap, where the single catalog row would have decided it with no attention
 *  at all. Not touching the control is not a claim of `normal`, and once the sidecar is
 *  written the two are indistinguishable.
 *
 *  A SEPARATE TYPE RATHER THAN A FOURTH MEMBER OF `Finish`. Widening `Finish` itself is the
 *  shorter edit and the wrong one: `Finish` is the wire enum, and the server answers
 *  anything outside THE CHOSEN GAME's finishes with `variant_invalid`. A no-claim member
 *  living inside it would typecheck at `server.capture()`'s `variant` argument and fail at
 *  the rig. Two names keep "what the operator can choose" and "what the wire accepts" from
 *  collapsing into one set. */
export type FinishClaim = readonly Finish[]

/** One entry of `pipeline/games.py`, as `GET /games` serves it (D21, D22).
 *
 *  A STRUCTURAL MIRROR OF THE REGISTRY, NOT A COPY OF ITS CONTENTS. There is deliberately
 *  no `app/src/games.ts` holding the four game keys and their rarity lists: that would be a
 *  second hand-authored copy of a hand-authored file, kept in step by nobody, buying nothing
 *  the wire does not already give. So `key` is `string` and not a union — the app learns what
 *  a game is at runtime, from the one place the pipeline learns it.
 *
 *  Every field the registry authors is here, including the ones no screen reads yet, for the
 *  same reason `do_games` serves them: a projection would be a third opinion about what a
 *  game is, and the first screen that wanted `card_aspect` would have to change a route.
 */
export type GameEntry = {
  /** The registry key. What travels on the wire as `game`, and what lands in the record. */
  key: string

  /** What a picker shows. `Pokémon`, `Pokémon code cards`, `Misc` — accented and spaced,
   *  unlike `key`. Never derived from `key` on this side; the registry authors both. */
  display: string

  /** The export's exact `Product Line` cell, or `null` for a game that spans several at
   *  once and therefore has none. `null` rather than `''` is load-bearing on the Python
   *  side — see the `misc` entry — so the type keeps the distinction rather than folding
   *  both into a falsy string. */
  product_line: string | null

  /** The export's `Rarity` cells, verbatim and in stack order. Empty for a game with no
   *  rarity ladder that means anything (`misc`), which D23 makes narrow nothing. */
  rarities: string[]

  /** The finish enum for this game, and the `Condition` string each finish maps to. Same
   *  three strings as `Finish` for `pokemon`; a different set, or none, elsewhere. */
  finishes: string[]
  condition_by_finish: Record<string, string>

  /** Rarity -> the finishes it may claim. A SUPERSET of what any one export proves, which
   *  D23 makes load-bearing: a chip excluded by a rarity claim renders unselectable, and
   *  that is only safe while this exceeds reality. */
  finish_by_rarity: Record<string, string[]>

  /** D24: does this card have a box, section and card position at all? `false` for code
   *  cards, which are a count rather than a place. */
  located: boolean

  /** Strategy NAMES, dispatched in the Python module that owns each behaviour —
   *  `pipeline/join.py`, `identify/prompt.py`, `geometry/crop.py`. Carried here because the
   *  registry authors them, and because `prompt` is how a screen can tell a game that is
   *  never identified (`operator_note`) from one whose prompt is merely unwritten. */
  join_key: string
  prompt: string
  crop_bands: string[]

  /** Short edge over long. `null` for a game whose cards are not one size — picking either
   *  of two real answers would be authoring a number nobody measured. */
  card_aspect: number | null

  /** THESE TWO FLAGS ARE NOT THE SAME FLAG, AND A SCREEN THAT TREATS THEM ALIKE IS WRONG.
   *
   *  `unverified: true` is a measurement somebody owes: no TCGplayer export has been seen,
   *  so the entry has no product line and no rarities and nothing captured under it could
   *  ever be joined. That is an ERROR STATE — the server refuses a capture naming it, and a
   *  screen should say so and say what would fix it.
   *
   *  `catalogued: false` is the finished answer: this game spans several product lines at
   *  once, so there is no export that would settle it and none is coming. `misc` is that,
   *  permanently and correctly. It is captured, located and described in a free-text note,
   *  and rendering it as a fault would put a red flag on 1% of the shelf forever. */
  unverified: boolean
  catalogued: boolean
}

/** What `GET /games` answers. `default` is D21's read-side backfill, published rather than
 *  guessed at: the app needs a game to start on, and picking the first entry or hardcoding
 *  `'pokemon'` would be a second decision that has to agree with `games.DEFAULT_GAME` and
 *  would stop agreeing the day the registry is reordered. */
export type GameRegistry = {
  default: string
  games: GameEntry[]
}

/** What `POST /capture` and `PUT /inventory/<box>/<index>` answer with: where the card
 *  landed. */
export type CardSummary = {
  box: number
  index: number

  /** `"<box>/<index>"`, the store's own key. Not a label and not a SKU. */
  key: string

  /** `Box 3 · Section 2 · Card 17`, rendered by `pipeline/join.py:Position.label` at 25
   *  cards per section. The app displays this string and never composes a second one
   *  (capture-app spec section 5.1) — a client-side renderer is a copy of D10's divider
   *  size that nothing keeps in step with the pipeline's.
   *
   *  STILL A STRING FOR A POOLED CARD (D24), and a different one: the capture screen
   *  prints this for where the card landed, so the server answers the pooled fact —
   *  `pipeline/join.py:pooled_label`, "Pokémon code cards · pooled" — never a position
   *  label and never nothing. The nulls live one level down, in `place`. */
  label: string
  section: number | null
  card: number | null

  /** True only on the first capture into a box. Deliberately NOT a dialog: the owner
   *  declined a confirmation step on a new box number, and the cost of that — a typo like
   *  33 for 3 is a valid box, a real photo and a real listing — is paid down by showing
   *  this on screen as information. It catches the first typo only; a second capture into
   *  the same phantom box looks ordinary. */
  new_box: boolean

  /** False when this was a replay of a `capture_id` the server had already committed. The
   *  card is the original one and no index was burned. This is how a retried capture is
   *  told from a new one — the HTTP status (201 vs 200) says the same thing, and the app
   *  reads this field instead so that one shape answers the question. */
  created: boolean

  /** A FILESYSTEM PATH ON THE MAC, not a URL. A browser cannot load it. Use
   *  `server.photoUrl(box, index)` to display the photo — that is D6's route and the
   *  reason it exists. */
  photo: string | null

  capture_id: string | null
}

/** `GET /status`. Counts, the next index per box, and whether the store is healthy. */
export type ServerStatus = {
  captures_root: string
  store: string
  store_exists: boolean
  cards: number

  /** Card counts by pipeline state (`captured`, `identified`, `pushed`, …). Open-ended on
   *  purpose: the states belong to the pipeline, and an app that enumerated them here would
   *  need editing every time one is added. */
  states: Record<string, number>

  /** How many cards are still waiting in each standing queue — open entries only, so an
   *  answered card leaves this count the moment it leaves the screen that works it.
   *
   *  EITHER SIDE IS NULL WHEN THAT FILE HOLDS AN ENTRY THAT CANNOT BE ORDERED, and the null
   *  is a refusal to count rather than an empty queue. `len(Queue)` runs `open_entries`, so
   *  counting is a sort: a `market` that is not a number or a `box` that arrived as a JSON
   *  string raises inside it. `server/capture_server.py:_queue_depth` catches that per queue
   *  and answers null, so a corrupt `review.json` does not also hide what is sitting in
   *  parked, and `problem` names the file to go and repair.
   *
   *  NOT WIDENED WHEN THE SERVER WAS, which is the mistake this comment exists to stop
   *  repeating: `_queue_depth` landed with a note saying this pair "has to widen to
   *  `number | null` to match", the two changes were made by different groups, and this side
   *  stayed `number` while T7 asserted the null. Nothing broke, because no screen reads this
   *  field yet — which is exactly what makes it worth typing correctly now. The first reader
   *  would have been handed a `number` that is sometimes null, and this module casts rather
   *  than validates, so nothing would have caught it before the arithmetic.
   *
   *  A COUNT THAT IS WRONG IN THE DIRECTION OF "THERE IS MORE TO DO" IS WORSE THAN NO COUNT
   *  HERE, which is why the server refuses rather than substituting `len(queue.entries)`.
   *  That number counts cleared entries too, so it says there is work left after the last
   *  card has been answered — and this is the number the owner works from. A reader must
   *  render the gap, never coerce the null to zero. */
  queues: { review: number | null; parked: number | null }

  /** Box number (as a string key) to the index the next capture into it would get. This is
   *  the list of boxes already in use, and the capture screen's box picker is built from it
   *  — no second route (capture-app spec section 5.2).
   *
   *  DISPLAY ONLY. Never send it back as a position: `Inventory.allocate_capture` takes no
   *  index precisely so there is no parameter through which a client's stale read can
   *  become a lost update.
   *
   *  Null when the inventory holds a card whose box or index is not a number, in which case
   *  `problem` says so. The two always travel together. */
  next_index: Record<string, number> | null

  /** Present only when something is wrong that did not warrant failing the health route.
   *  Show it verbatim. */
  problem?: string
}

/** One card in `GET /inventory`. Mirrors `store/master.py:Card` field for field, because
 *  the server serialises that dataclass with `asdict` — plus the three decorated fields
 *  below, which the dataclass does not carry and `do_inventory` adds on the way out. */
export type InventoryCard = {
  box: number
  index: number

  /* ---- decorated by the server, not stored ----
   *
   * `server/capture_server.py:do_inventory` adds these three to each row after `to_payload`
   * has built it, the same three `POST /capture` and `PUT /inventory` have always answered
   * with. They exist so the app never composes a position label — see `CardSummary.label`
   * for the rule and D10 for the divider size that a second renderer would copy.
   *
   * OPTIONAL, AND THAT IS THE CONTRACT RATHER THAN CAUTION ABOUT AN UNFAMILIAR ROUTE. The
   * decoration is skipped for any record whose box or index will not coerce to an int: a
   * placeholder label would name a position that does not exist, which is the one thing a
   * position label may never do, so the server leaves the row bare and `GET /status`
   * reports it. Declaring them required would make every reader's narrowing look redundant
   * and invite its deletion, at which point that row renders `undefined` as a location.
   *
   * `?:` rather than `| undefined` on a required key: both typecheck the same reads, and
   * the optional form is what an absent JSON key actually is. The second form would also
   * force every construction of this type to spell the fields out, which matters the day a
   * test builds one.
   *
   * WIRE-ONLY, and never written back. `Inventory.parse` filters on `Card.__annotations__`,
   * so a label that reached `inventory.json` would be dropped silently on the next reload.
   * Nothing in this app writes an inventory row, so the rule costs nothing here — it is
   * recorded because the reason it is safe on this side is that there is no PUT of a whole
   * row to accidentally round-trip one through. */
  label?: string
  section?: number
  card?: number

  /** The fourth decoration, typed late: `do_inventory` has sent the whole `Place` block
   *  beside the three flat keys since the block existed, and nothing on this side read it
   *  until D24 needed the one field only the block carries. A POOLED CARD IS THE ROW THAT
   *  MAKES THE DIFFERENCE VISIBLE: it arrives with `place` (carrying `located: false` and
   *  the game's display name) and WITHOUT the three flat keys — where a row whose position
   *  will not coerce arrives with neither, so a design fact and a fault never share a
   *  shape. Optional for the same reason the three above are. */
  place?: Place

  /** Filesystem path again, not a URL. See `CardSummary.photo`. */
  photo: string | null

  set_hint: string | null

  /** The capture-time finish claim. Typed loosely rather than as `FinishClaim` on purpose:
   *  this comes off disk, and the store holds records written before the server validated
   *  anything. Narrowing it here would make the type assert something about
   *  `inventory.json` that only `POST /capture` and `PUT /inventory` enforce.
   *
   *  BOTH SHAPES, PERMANENTLY. D3 rung 1's claim became a set on 2026-08-23 and there is no
   *  migration — a bare string reads as a one-member set, all 682 records written before it
   *  carry one, and `_card_row` ships `asdict(card)` raw. So the wire really does carry two
   *  shapes and this says so; the union is what makes a renderer that forgets the array
   *  case a compile error rather than a screen printing `normal,reverse_holo`. */
  metadata_finish: string | string[] | null

  /** Which game the operator said this card is (D21). Loose `string | null` for the same
   *  reason `metadata_finish` is: this comes off disk, and records written before the field
   *  existed carry none. `null` here is NOT a no-claim the way a null finish is — D21 is
   *  explicit that the two do not transfer, because a ladder infers a finish and nothing
   *  infers a game — it means "written before the field existed", and the pipeline reads it
   *  as `pokemon`. A screen showing a game should apply `GameRegistry.default` the same way,
   *  and never invent its own fallback. */
  game: string | null

  /* D23's stack claim as the record carries it: a list of the game's exact Rarity cells,
   * or null where the operator claimed nothing. Never a string — the sidecar reader
   * defends against that spelling; this type states the honest one. */
  rarity_claim: string[] | null

  /** Free text the operator typed after the capture, saying what a card the pipeline will
   *  never identify actually is. Only ever set through `PUT /inventory/<box>/<index>` —
   *  never in a capture body, because the feeder does not wait for a keyboard. */
  note: string | null

  captured_at: string | null
  capture_id: string | null

  /* Everything below is written by the four commands — identify, join, emit, reconcile.
   * The app READS state and never sets it. That is not a simplification for this pass: the
   * app-side CSV import was struck from build-order step 7 because every state transition
   * is already owned elsewhere (capture-app spec section 2.1). */
  name: string | null
  number: string | null
  printed_total: string | null
  confidence: string | null
  sku: string | null
  condition: string | null
  state: string
  state_at: string | null

  /** Why a retired copy left — one of the four the server validates (`pulled`, `damaged`,
   *  `lost`, `given_away`) — and null on a card in any other state. Written only by
   *  `POST /inventory/<box>/<index>/retire` and cleared by its reversal; loose `string`
   *  for the reason every stored field here is — this comes off disk, and the store owns
   *  the vocabulary (D26). */
  retire_reason: string | null
  run: string | null
}

/** `GET /inventory`, whole. Keys of `cards` are `store.master.position_key` — `"3/17"` for
 *  box 3, card 17 — so a lookup is `inventory.cards[`${box}/${index}`]`, and under
 *  noUncheckedIndexedAccess that read is `InventoryCard | undefined`. */
/* One SKU's progress through TCGplayer, as QUANTITIES rather than as addresses.
 *
 * D7 amended: copies of a SKU are fungible, so `pushed`, `staged` and `live` count copies at
 * each stage and name no position at all. They were per-card states until 2026-08-23 and
 * `store/master.py:check_state` now refuses them as card states — which is why a screen that
 * wants "how many of this are listed" reads it here and cannot count it off the copies.
 *
 * `live` IS AN ESTIMATE BETWEEN RUNS, deliberately. D8 and D11 put the authority in the
 * TCGplayer export's `Total Quantity`, which `./pkmnscan join` reads on every run; a sale
 * decrements this locally and the next join corrects it. Do not render it as a fact about
 * the marketplace — render it as what this store last believed. */
export type Listing = {
  sku: string
  condition: string | null
  pushed: number
  staged: number
  live: number
  at: string | null
  staged_at: string | null
}

export type Inventory = {
  version: number
  cards: Record<string, InventoryCard>

  /* Schema v2 added both, and `do_inventory` answers with `to_payload()` verbatim — so they
   * have been on this wire since the day the store gained them. Declared optional because a
   * v1 payload predates them and this type is cast, never validated: a screen reading a
   * pre-v2 store must find `undefined` rather than a crash. */
  boxes?: Record<string, BoxRecord>
  listings?: Record<string, Listing>
}

// -------------------------------------------------------------------- the standing queues

/* `GET /queues` and the answer that clears one of its entries.
 *
 * WRITTEN IN ReviewQueue.tsx AND MOVED HERE, which is what that file asked for in as many
 * words: "THESE TYPES BELONG IN types.ts AND ARE HERE BECAUSE OF FILE OWNERSHIP, NOT DESIGN
 * — move them the moment both files are writable together." They were, 7b's screens were
 * wired, and two copies of one contract is the drift the whole one-owner rule in server.ts
 * exists to prevent. Nothing about them changed on the way across; the header comment they
 * carried is the paragraph below.
 *
 * Field for field out of `store/queues.py:QueueEntry`, `cli/resolve.py:_candidate_rows` and
 * `server/capture_server.py:_queue_row`, in the server's own case for the reason stated at
 * the top of this file: the first thing anyone debugging a run does is hold what the app
 * shows against `review.json`, and two vocabularies for one record makes that a lookup.
 */

/** The two standing queues — `store/queues.py:MAIN` and `PARKED`, same strings. */
export type QueueName = 'review' | 'parked'

/** One catalog row this card could be. `cli/resolve.py:_candidate_rows` builds these, and
 *  every value is a cell out of the TCGplayer export exactly as it was read — `market` is a
 *  string, and may be empty or `0.00`, which D9 calls an unknown price rather than a low
 *  one. */
export type CandidateRow = {
  sku: string
  name: string
  set: string
  number: string
  condition: string
  market: string
}

/** What identification said, as `cli/resolve.py:queue_entry` recorded it. Every field is
 *  optional and nullable because a pre-join failure fills almost none of them. */
export type QueueRead = {
  name?: string | null
  number?: string | null
  printed_total?: string | null
  set_hint?: string | null
  /** D3 rung 1's claim, as `cli/resolve.py:queue_entry` recorded it. A LIST since the
   *  amendment of 2026-08-23 — and still a bare string in any `review.json` written before
   *  it, which is why both shapes are named. A queue file outlives the run that wrote it.
   *
   *  The union is the guard. `ReviewQueue.tsx`'s `text()` returns null for anything that is
   *  not a string, so a set arriving under a `string | null` annotation would render as
   *  "no claim" and vanish from the sentence — no crash, no console warning, nothing red in
   *  `tsc`, `lint` or Playwright, while the screen asked the operator to judge a card
   *  against a claim they never made. Naming the array here makes that a compile error. */
  metadata_finish?: string | string[] | null
  detected_finish?: string | null
}

/** One card waiting for a human. `store/queues.py:QueueEntry`, minus the two Python
 *  properties `asdict` drops (`age_days`, `price`) — see `ReviewQueue.tsx:seenText` for what
 *  the screen does about the first of them.
 *
 *  THE `Wire` SUFFIX IS LOAD-BEARING, unlike the bare names above it. `store/queues.py`
 *  exports a `QueueEntry` this is deliberately not a translation of: two of that record's
 *  fields are properties rather than data, so a type here called `QueueEntry` would claim a
 *  correspondence it does not have. `CandidateRow` and `QueueRead` have no such twin. */
export type QueueEntryWire = {
  position: string
  box: number
  index: number
  label: string
  photo: string | null
  read: QueueRead
  confidence: string | null
  reason: string
  candidates: CandidateRow[]
  first_seen: string

  /** The decisive market price as a string, or null for unpriced. `Decimal` serialised with
   *  `str()`, so it is exact — see `ReviewQueue.tsx:priceOf` for why it is never turned into
   *  a number for anything but a comparison. */
  market: string | null

  /** Always false in this payload: `GET /queues` serves `open_entries`, which filters on
   *  exactly this. Kept because it is a real field of the record and a subtraction maintained
   *  by hand is the thing that drifts — the route's own reasoning for not stripping it. */
  cleared_by_human: boolean

  /** DECORATED BY THE ROUTE, not stored. `QueueEntry.age_days` is a property, so `asdict`
   *  drops it and `_queue_row` adds it back — the same shape `do_inventory` uses for the
   *  position label, and for the same reason: computing it in the app would put a second copy
   *  of `store/queues.py:_age_days`'s date arithmetic in a second language. Null when
   *  `first_seen` is missing or unparsable, because that helper refuses to guess. Optional on
   *  this side so an older server running on the Mac renders a gap rather than `undefined`. */
  age_days?: number | null
}

/** `GET /queues`. Both queues, each already in `store/queues.py:sort_key` order. */
export type QueueSnapshot = {
  review: QueueEntryWire[]
  parked: QueueEntryWire[]
}

// -------------------------------------------------------------------------- the sale, both ways

/** What `POST /inventory/<box>/<index>/sold` answers, in either direction.
 *
 *  A SUBSET OF THE BODY, the same shape `server.ts:undoCapture` takes of a much larger one.
 *  `server/capture_server.py:do_mark_sold` also returns `box`, `index`, `state`,
 *  `previous_state` and the whole card row; no screen reads any of them, and naming a field
 *  here is a claim that something does.
 *
 *  `restores_to` IS THE FIELD THAT WAS DROPPED TWICE AND MUST NOT BE AGAIN. The route computes
 *  it deliberately and says so in its own comment — "null on a sale means the undo control
 *  should not be offered, which is worth knowing at the moment of the sale rather than at the
 *  tap that fails" — and it reached no screen: this type was written as `{ position: string }`,
 *  and the Fulfillment view's own wrapper returned `Promise<void>` on top of that. The result
 *  was an Undo offered for a sale the server had already said it could not reverse, whose only
 *  behaviour was a refusal telling a retired non-technical user to press it again. Null means
 *  `history.jsonl` records no earlier state for the card, so an undo will refuse as
 *  `sold_origin_unknown`; on a reversal it is always null, because there is then nothing left
 *  to put back.
 *
 *  A PIPELINE STATE WORD (`live`, `pushed`, `staged`), never a sentence, and read as
 *  present-or-null rather than displayed. Nothing on the Fulfillment view may render it: that
 *  vocabulary is the owner's, and D5's second persona has no use for a state name. */
/** What `PUT /inventory/<box>` answers — retroactive capture claims applied to many cards
 *  in ONE write (the owner's ask, 2026-08-23: "if i accidentally didn't do it at the
 *  capture level, i'd like to be able to do it retroactively").
 *
 *  `eligible` counts what the sweep could touch, `applied` what actually moved, and
 *  `unchanged` the difference — a restatement of what a card already says writes nothing
 *  and logs nothing, so the two numbers disagree on purpose and the screen should say so
 *  rather than reporting `eligible` as a success count.
 *
 *  `skipped` names the sold and retired cards the sweep would not touch. They are not
 *  failures: D26 and D10 make those records history, and a claim correction is not a thing
 *  history accepts. Named rather than merely counted, because "3 cards were skipped" with
 *  no numbers is the sentence an operator cannot act on. */
export type BoxClaimResult = {
  box: number
  eligible: number
  applied: number
  unchanged: number
  skipped_terminal: number
  skipped: { index: number; state: string }[]
  sidecars_rewritten: number
}

/** What `POST /inventory/<box>/<index>/remove` answers — D10 ruling 1's mid-box delete with
 *  the cards behind it slid forward.
 *
 *  `shifted` is the count that moved down one index, and it is 0 when the target was the
 *  top of its box (which is undo's case, reached by a different route). A non-zero value
 *  means every label above the deleted card has just changed, and the screen has to say
 *  that: it is the one operation in the product that renumbers, permitted only because the
 *  physical cards really do slide forward in a contiguous stack. */
export type RemoveResult = {
  deleted: string
  box: number
  index: number
  photo_deleted: boolean
  sidecar_deleted: boolean
  review_deleted: boolean
  parked_deleted: boolean
  cache_deleted: boolean
  shifted: number
  next_index: number
}

/** What `DELETE /boxes/<box>` answers — D10 ruling 3's whole-box delete.
 *
 *  Counts per kind rather than booleans, because a box holds many of each, and these
 *  numbers ARE the receipt: this is the most destructive action in the product and the only
 *  evidence it happened correctly is what it says it removed.
 *
 *  `directory_removed` false is not a failure. The server removes the photo directory only
 *  when the files it enumerated were all it held; a stray left behind keeps the directory
 *  and says so, rather than deleting something nobody accounted for. */
export type BoxDeleteResult = {
  deleted_box: number
  cards: number
  photos: number
  sidecars: number
  review_deleted: number
  parked_deleted: number
  cache_deleted: number
  registry_deleted: boolean
  directory_removed: boolean
}

/** Copies at each TCGplayer stage. Stages sitting at zero are omitted rather than sent as 0,
 *  which is the same convention `join` and `reconcile` print their closing lines with. */
export type ListingStages = Partial<Record<'pushed' | 'staged' | 'live', number>>

/** One SKU on `GET /boxes/<box>/listings`, and the same row echoed back by the release.
 *
 *  THE BUDGET IS THE BOX'S UNSOLD COPIES (D34, owner's ruling 2026-08-24). Each SKU gives up
 *  at most `copies_here`, so a release reached from box 1 can never give up a commitment only
 *  box 3's copies could account for. Where the SKU is shared that leaves a remainder — and a
 *  remainder keeps the card listing-held, so the box stays refused. That is the intended
 *  outcome, not a failure, and `still_held` is what says so BEFORE the press. */
export type BoxListingRow = {
  sku: string
  condition: string | null

  /** Unsold, unretired copies of this SKU in this box. The release budget, and the number an
   *  operator counts when they look in the box. */
  copies_here: number

  before: ListingStages
  releases: ListingStages
  after: ListingStages

  /** True when something remains after the release — so this SKU still holds the box. */
  still_held: boolean

  /** Other boxes holding an unsold copy of this SKU, and how many each holds. Empty in the
   *  ordinary case. Rendered, never dropped: it is the whole reason the preflight exists. */
  also_in_boxes: { box: number; copies: number }[]
}

/** `GET /boxes/<box>/listings` — FREE, read-only, and the step that comes first (D34).
 *
 *  The screen draws this on opening the release panel, and the control that releases does not
 *  exist until it has answered — D33's preflight-then-confirm shape applied to a claim instead
 *  of an invoice. The first build reported the blast radius in the RECEIPT, which was honest
 *  and too late; this is that moved ahead of the press. */
export type BoxListingPlan = {
  box: number

  /** How many SKUs hold something. Zero is ordinary — most boxes are never listed. */
  skus: number

  /** What the release would give up in total, per stage. */
  releases: ListingStages

  /** SKUs that would still hold something afterwards. */
  still_held: string[]

  /** Every other box holding a copy of a SKU this release touches. */
  also_in_boxes: number[]

  /** Whether the box would actually become deletable. NOT the same as "something would be
   *  released": a box every one of whose SKUs is shared can give up real copies and stay
   *  refused, which is exactly what this flag is here to state up front. */
  frees_box: boolean

  listings: BoxListingRow[]
}

/** What `POST /boxes/<box>/listings/release` answers (D34).
 *
 *  THE RECEIPT IS THE ONLY EVIDENCE, and that is why every field is a count of something given
 *  up rather than a status word. After the write the store has no record the counts ever
 *  stood, and a box deleted straight afterwards takes the cards that would have implied them. */
export type ListingReleaseResult = {
  box: number

  /** How many SKUs were touched. Never 0: the route refuses `nothing_to_release` instead. */
  released: number

  /** Every SKU touched, with what it gave up and what it kept. */
  listings: BoxListingRow[]

  /** Those SKUs by name, in full — the list that makes the claim checkable against TCGplayer. */
  skus: string[]

  given_up: ListingStages
  still_held: string[]
  frees_box: boolean
  also_in_boxes: number[]

  /** Store-wide totals AFTER. Empty means nothing anywhere is staged. */
  listings_after: ListingStages
}

export type SaleResult = {
  /** `"<box>/<index>"`, the store's own key — `master.position_key`, not a label. */
  position: string

  /** True when this call reversed a sale rather than recording one. The app reads this
   *  rather than comparing states, so one field answers "which way did that go" in both
   *  directions. */
  undone: boolean

  /** What an undo of THIS call would put the card back to, or null when there is none.
   *  D10: sold is a state and never a removal, so a reversal is a state transition backwards
   *  and this is the state it goes back to. */
  restores_to: string | null
}

/** Why a retired card left (D26). The send-side union — the four words the server's
 *  `retire_reason_invalid` refusal enumerates — while the record's own `retire_reason`
 *  stays a loose string, the same split `BoxState` draws between what may be SET and what
 *  comes off disk. A closed vocabulary rather than free text so the history stays
 *  greppable; a card that needs a sentence gets one in `note`, through `updateCard`. */
export type RetireReason = 'pulled' | 'damaged' | 'lost' | 'given_away'

/** What `POST /inventory/<box>/<index>/retire` answers, in either direction.
 *
 *  `SaleResult`'s shape on the sibling route (D26: `retired` is `sold`'s sibling — a copy
 *  that left inventory without a sale, record kept, gap permanent), and a subset of the
 *  body by the same rule: the route also returns `state`, `previous_state`, `reason` and
 *  the whole card row, and naming a field here is a claim that something reads it. The
 *  same warning travels with `restores_to`: null on a retirement means the reversal WILL
 *  refuse (`retired_origin_unknown`), so a screen that reads it never draws an Undo whose
 *  only behaviour is that refusal — the defect `SaleResult` records as having shipped
 *  twice before the field was read. */
export type RetireResult = {
  /** `"<box>/<index>"`, the store's own key — `master.position_key`, not a label. */
  position: string

  /** True when this call reversed a retirement rather than recording one. */
  undone: boolean

  /** What an undo of THIS call would put the card back to, or null when there is none. */
  restores_to: string | null
}

/** D4's one-tap choice, as `POST /review/<box>/<index>/answer` takes it.
 *
 *  BOTH VALUES ARE COPIED OFF ONE CANDIDATE ROW, never composed. The route refuses a SKU the
 *  pipeline did not offer — CLAUDE.md's hard rule about never guessing an identification,
 *  enforced at the seam rather than trusted to the screen — and it checks `condition` against
 *  the offered row rather than deriving it, so that a screen drawn from a queue file a later
 *  join has rewritten is caught instead of writing a wrong finish onto a real card.
 *
 *  A NAMED TYPE RATHER THAN AN INLINE ARGUMENT, which is the opposite of what `server.capture`
 *  does one file over. The difference is that this object is assembled off a rendered row and
 *  passed down through a callback before it reaches the wire, so it has a life on the screen
 *  side; `capture`'s argument is built at the call site and consumed immediately. */
export type ReviewAnswer = {
  box: number
  index: number
  sku: string
  condition: string
}

/** What the card carried before an answer overwrote it — the pair a reversal puts back.
 *
 *  BOTH MEMBERS ARE LEGITIMATELY NULL AND THAT IS THE COMMON CASE, which is the one thing to
 *  know before reading this. A card sitting in a review queue has usually never carried a SKU
 *  at all — that is why it is in a queue — so the pair is `{sku: null, condition: null}` and
 *  putting it back means returning the card to carrying no answer. Read the OBJECT as
 *  present-or-null; never test its members for emptiness, which is the mistake that would
 *  suppress the undo on exactly the cards that most need it.
 *
 *  A CATALOG SKU AND A CONDITION STRING, never a sentence. Owner-side only, like everything
 *  the review queue draws: this vocabulary is the pipeline's. */
export type AnswerOrigin = {
  sku: string | null
  condition: string | null
}

/** What `POST /review/<box>/<index>/answer` answers, in either direction.
 *
 *  A SUBSET OF THE BODY, the same shape `SaleResult` above takes of the sale's. The route also
 *  returns `answered`, `box`, `index`, `sku`, `condition`, the two cleared flags, the two
 *  reopened flags and the whole card row; naming a field here is a claim that something reads
 *  it, and `server/capture_server.py` holds the full shape.
 *
 *  THE TWO CLEARED FLAGS ARE DELIBERATELY ABSENT even though something does read them.
 *  `ReviewQueue.tsx:clearedQueues` takes an `unknown` and reads them off the body itself,
 *  because it has to tell "the server said false" from "an older server said nothing" and a
 *  typed `boolean` erases that difference — its own docstring has the argument and the card it
 *  would otherwise redraw.
 *
 *  `restores_to` IS THE FIELD `SaleResult` RECORDS AS HAVING BEEN DROPPED TWICE, and this is
 *  the second route to carry it. Null means the reversal will refuse and the undo must not be
 *  drawn: either the answered SKU is already out of this Mac (`undo_too_late`) or the store's
 *  history cannot say what the answer replaced (`answer_origin_unknown`). On a reversal it is
 *  always null and means only that there is nothing left to reverse — not that a second undo
 *  is available. */
/** Why a human closed a queued question without answering it. D37, and `store/queues.py`'s
 *  `STAND_DOWN_REASONS` verbatim — a second friendly vocabulary is the drift D16 exists to
 *  catch, so these render beneath their labels exactly as a routing reason does.
 *
 *  DELIBERATELY NOT `RetireReason`. Those four all say the CARD left inventory; these three
 *  say the QUESTION closed while the card stayed exactly where it is. */
export type StandDownReason = 'wasted_position' | 'cannot_settle' | 'not_listing'

/** `POST /review/<box>/<index>/stand-down`, both directions. */
export type StandDownResult = {
  /** `"<box>/<index>"`, the store's own key. */
  position: string

  /** True when this call took a stand-down back rather than recording one. `AnswerResult`'s
   *  `undone` under the same name, so one client shape reads either route. */
  undone: boolean

  /** The reason recorded, echoed back — on the reversal it is the reason being withdrawn. */
  reason: StandDownReason | null

  /** The QUEUE's own reason for asking, beside the operator's reason for declining. Absent on
   *  a reversal, which is about the stand-down and not about the question. */
  queue_reason?: string

  /** Always true on the recording direction: a stand-down writes nothing downstream, so
   *  nothing downstream can hold it. Typed anyway so this reads like `AnswerResult`. */
  reversible?: boolean
}

export type AnswerResult = {
  /** `"<box>/<index>"`, the store's own key — `master.position_key`, not a label. */
  position: string

  /** True when this call took an answer back rather than recording one. Read this rather than
   *  comparing a card's SKU against a queue file, so one field answers "which way did that go"
   *  in both directions. */
  undone: boolean

  /** What an undo of THIS call would put back, or null when it would be refused. */
  restores_to: AnswerOrigin | null
}

/** One member of a group answer, as `POST /review/group-answer` reports it back.
 *
 *  THE CLEARED FLAGS ARE TYPED BOOLEANS HERE AND DELIBERATELY ABSENT FROM `AnswerResult`,
 *  and the difference is the route's age, not a change of mind. The single answer predates
 *  its flags, so a screen there has to tell "the server said false" from "an older server
 *  said nothing" and reads them off an `unknown`; this route was born carrying them, an
 *  older server answers it `no_such_route` outright, and a type that hedged against a
 *  server shape that has never existed would be caution about nothing.
 *
 *  `restores_to` KEEPS THE SINGLE ANSWER'S CONTRACT PER MEMBER: null means an undo of that
 *  member would be refused, decided at the write rather than at the press that fails. The
 *  screen offers the group's undo only when EVERY member can come back — a control that
 *  reverses eleven of sixteen on its best day is the defect `SaleResult` records, at
 *  scale. */
export type GroupAnswerRow = {
  /** `"<box>/<index>"`, the store's own key — `master.position_key`, not a label. */
  position: string
  box: number
  index: number
  sku: string
  condition: string
  restores_to: AnswerOrigin | null
  review_cleared: boolean
  parked_cleared: boolean
}

/** What `POST /review/group-answer` answers. One direction only — the reversal is the
 *  single answer's `{"undo": true}`, looped per position by the screen holding the group
 *  receipt, so a partial reversal reports per position instead of pretending a group has
 *  one outcome.
 *
 *  ALL OR NOTHING, WHICH IS WHY THIS SHAPE ONLY DESCRIBES SUCCESS. The route validates
 *  every position before writing any (docs/DECISIONS.md, "A homogeneous queue may be
 *  answered as a group" — the entry that reopens D4, narrowly), and a group with one
 *  refused member refuses whole in `group_entry_refused` or `group_not_uniform` with
 *  nothing written — so a body of this type means every named position was answered.
 *
 *  `reason` AND `condition` ARE THE GROUP'S SHARED FACTS, stated once because the route
 *  just proved they are shared: one reason code across the group, one condition string
 *  across every member's lone candidate row. The receipt line is built from them. */
export type GroupAnswerResult = {
  /** Every answered position, in request order. */
  answered: string[]
  count: number
  reason: string
  condition: string
  results: GroupAnswerRow[]
}

// --------------------------------------------------------- where a card sits inside its box

/** Where one card is, and how far into its box that is.
 *
 *  `GET /search` hangs one of these off every copy, and the server decorates every card it
 *  already serves with one too. THE FLAT `label`/`section`/`card` KEYS DO NOT GO AWAY —
 *  `CardSummary` and `InventoryCard` keep theirs, and the screens reading them are unchanged.
 *  This is a second, richer view of the same fact, added because one question the flat keys
 *  cannot answer turned out to be the one the owner asks at the box: not *which* slot, but
 *  *how far in* — whether to open the lid at the front or dig to the back.
 *
 *  THE CLIENT RENDERS `label` AS GIVEN AND COMPUTES NO SECTION ARITHMETIC. Same rule
 *  `CardSummary.label` states, restated here because this record hands the client the raw
 *  numbers that make breaking it easy: D10's cards-per-divider is a configurable pipeline
 *  constant, and a client that re-derives a section boundary from `index` owns a copy of it
 *  that nothing keeps in step with `pipeline/join.py`.
 *
 *  WHAT IS PERMITTED IS PRESENTATION, and the line runs between a drawing and a claim. A
 *  percentage computed from `fraction`, or a track segment whose width comes from
 *  `section_start` and `section_end`, describes a picture of numbers the server sent —
 *  nothing downstream reads it and no card moves if it is off by a pixel. `Section 2 · Card
 *  17` assembled out of `index` and a divider size is a position claim, it is what somebody
 *  carries to a physical box, and it is forbidden. `app/src/PositionBar.tsx` is the one
 *  component that draws from these numbers and it argues the same line at its own `spansOf`.
 */
export type Place = {
  /** `Box 3 · Section 2 · Card 17`, composed by `pipeline/join.py:Position.label`. Displayed
   *  as given. See the paragraph above, and `server.ts:positionLabel` for the read that
   *  refuses to substitute anything when it is missing.
   *
   *  NULL FOR A POOLED CARD (D24), never for a fault. A game whose registry entry says
   *  `located: false` has no position to name, so its block carries no label, no section
   *  and no fraction — `located` below is what says this is the design fact rather than
   *  the coerce-failure, which arrives as no block at all. */
  label: string | null

  /** D24's split between a key and a place: does this card have a position at all? False
   *  for a pooled game's card — a count, not a location — whose `box`/`index` below are
   *  the store key and the photo route's arguments, never a slot. Optional because an
   *  older server omits it, and absent must read as located: every block that server
   *  sends carries a real label. */
  located?: boolean

  /** The registry key and display name of the game, PRESENT ONLY ON A POOLED BLOCK — the
   *  honest thing a screen shows where a label would have gone. `GET /games` stays the
   *  registry's one home; these two fields are a stamp, not a second copy. */
  game?: string
  game_display?: string

  box: number

  /** The card's sequential position in the box — D10's allocator number, 1-based, and the
   *  numerator of the `#40 of 250` sentence. Not the slot within a section; that is `card`.
   *  On a pooled block it is the KEY's second half, not a position — see `located`. */
  index: number

  section: number | null
  card: number | null

  /** What the owner calls this box, or null when he has not named it. A label for humans and
   *  never an identifier: `box` is the identifier, and two boxes may carry the same name. */
  box_name: string | null

  /** The first and last `index` of the section this card is in. `section_end` is null when
   *  the section has no end yet — the open end of an open box, and the whole of a box that
   *  declares no sections at all. A null is "not decided", never "unbounded at zero". */
  section_start: number
  section_end: number | null

  /** How many cards the box holds. For a closed box that number is final; for an open one it
   *  is how many are in it so far and it moves with the next capture. `box_closed` is what
   *  says which of those two sentences is true, and it is the whole reason both fields are on
   *  the wire rather than one. */
  box_total: number
  box_closed: boolean

  /** How far into the box this card sits, 0 to 1, or null when the server cannot say — an
   *  empty box, or a record whose numbers do not support the division. NULL IS NOT ZERO and
   *  must never be coerced to it: zero is the front of the box, which is a specific and wrong
   *  place to send somebody. The same rule `ServerStatus.queues` states for its own nulls. */
  fraction: number | null

  /** The nearest records that are still physically in the box on either side of this one —
   *  D30's digital half. `Card 17` is the seventeenth SLOT, not the seventeenth card you can
   *  count, and once a section has holes those two stop being the same number; the neighbours
   *  are what make the label countable by hand again. Sold and retired records are passed
   *  over, never named — a departed card cannot be the thing you count from. `prev`/`next`
   *  are null past the box's ends; a neighbour's `name` is null when nothing has identified
   *  it yet, and the screen degrades to its index (`#41`), never to a blank.
   *
   *  THE WHOLE FIELD IS NULL WHEN THE SERVER DEGRADED IT — a record in the store whose
   *  position will not read, the same event that nulls the denominator — and ABSENT on an
   *  older server. Both render as no sentence: `server.ts:placeSentence` is the one composer,
   *  and it refuses to guess for the same reason `positionLabel` does. Optional for the
   *  reason every late decoration in this file is. */
  neighbors?: { prev: PlaceNeighbor | null; next: PlaceNeighbor | null } | null

  /** How many indices inside this card's own section bounds hold a sold or retired record —
   *  the permanent gaps (D10), and the other half of D30's sentence: the count says why a
   *  hand-count of the section comes out short. An unallocated tail index is not a gap; the
   *  server counts terminal RECORDS, so that is true by construction. Null when the walk
   *  degraded (see `neighbors` — the two null together), absent on an older server, and NULL
   *  IS NOT ZERO: zero says "this section is countable", null says "cannot say". */
  section_gaps?: number | null
}

/** One side of `Place.neighbors`: the record's index in the box, and its identified name or
 *  null. The index is D10's allocator number — the same space as `Place.index` — so `#41`
 *  drawn from it is a slot a hand can count to, not a store key. */
export type PlaceNeighbor = {
  index: number
  name: string | null
}

// ------------------------------------------------------------------------------- the search

/** One physical copy in a search result: the store's own key, its pipeline state, and where
 *  it is. Deliberately NOT the whole `InventoryCard` — the search answers "where are my
 *  copies of this card", and a screen that also received `confidence` and `capture_id` would
 *  invite a second inventory view to grow inside a search result. */
export type SearchCopy = {
  /** `"<box>/<index>"`, `store.master.position_key`. Identity for React, and the string a
   *  `curl /inventory` is grepped with. Never parsed into a position — a store key and a
   *  physical location agree for the first section of a box and diverge after it. */
  key: string

  /** The pipeline's own word for what this ONE PHYSICAL CARD is — `captured`, `identified`,
   *  `sold`, or since D26 `retired`: it left inventory without a sale, and it is exactly as
   *  gone as a sold copy — not sellable, not on hand, its gap permanent.
   *
   *  `pushed`, `staged` AND `live` ARE NOT MEMBERS OF THIS SET ANY MORE and a screen must not
   *  test for them. They are quantities per SKU, held in `SearchGroup.listed`, because copies
   *  are fungible: the owner's ruling is that marking three of fifteen live means any three,
   *  not three specific slots. `store/master.py:check_state` refuses them, which is what stops
   *  a caller reaching for the old per-position flag and quietly getting one back.
   *
   *  THE PRACTICAL CONSEQUENCE FOR EVERY SCREEN THAT DRAWS A SELL CONTROL: every copy that
   *  has not left — not `sold`, not `retired` — is sellable. There is no state to filter on
   *  to find "the listed ones", because that question no longer has a per-copy answer.
   *
   *  Loose for the reason `InventoryCard.state` is: `store/master.py` owns the list, and an
   *  app that enumerated it here would need editing every time one is added. Owner-side
   *  screens show it verbatim; the Fulfiller's may not show it at all (D5). */
  state: string
  state_at: string | null

  /** Whether `GET /photo/<box>/<index>` has bytes to serve. A hint that saves a request and a
   *  broken image, never a guarantee: undo deletes a photo, so a screen still has to handle
   *  the load failing. */
  has_photo: boolean

  place: Place
}

/** One SKU and every copy of it, which is D7's map with the position work already done.
 *
 *  `sku` is null for the group of copies the pipeline has written no import row for yet —
 *  the same group `Inventory.tsx` renders as "No SKU yet", and for the same reason: a card is
 *  given a SKU when `emit` writes its row and never before.
 *
 *  `names` IS A LIST BECAUSE THE COPIES MAY DISAGREE. Two copies read as `Rhyhorn` and
 *  `Rhydhorn` are a run worth looking at, and a group that silently showed the first would
 *  hide it. Same argument `Inventory.tsx:distinct` makes at more length. */
export type SearchGroup = {
  sku: string | null
  names: string[]
  number: string | null
  printed_total: string | null
  set_hint: string | null
  condition: string | null

  /** How many copies have reached each of the three listing states. Three counts and not one,
   *  because `staged` and `live` are two facts about two different things — D7's refill maths
   *  reads the LIVE number, and an import that was staged and never moved live has no live
   *  quantity at all. Merging them here would hide exactly the box that is not earning. */
  listed: { pushed: number; staged: number; live: number }

  /** Copies still in the boxes — D7: "copies on hand is a count of UNSOLD positions".
   *
   *  NOT `copies.length`, AND THE TWO MUST NOT BE USED INTERCHANGEABLY. `copies` carries the
   *  sold ones as well, because D10 keeps a sold record at a permanent gap and CLAUDE.md's
   *  rule is that nothing silently drops a card — so a group with four copies of which one is
   *  sold reports `on_hand: 3` and sends four entries. A screen wanting "how many are still
   *  there" reads this field; a screen wanting "how many rows to draw" reads the array. */
  on_hand: number

  /** D7's live quantity cap — 4 today, and configurable there.
   *
   *  IT ARRIVES ON THE WIRE, WHICH IS WHAT `Inventory.tsx` SAID WOULD SETTLE IT. That screen
   *  refuses to draw `2 of 4 live` and says why: `pipeline/join.py:LIVE_QUANTITY_CAP` is a
   *  configurable Python constant, and writing the 4 in TypeScript is a copy nothing keeps in
   *  step. The condition it named — "settled by the server reporting the cap" — is met here,
   *  so a screen holding this group may draw the denominator. */
  cap: number

  copies: SearchCopy[]
}

/** `GET /search?q=<text>`. `query` is what the server searched for, echoed back — a slow
 *  answer to an old keystroke is recognisable as one, which is the same job the sequence
 *  guard in `useSearch.ts` does from the other end. */
export type SearchResult = {
  query: string
  groups: SearchGroup[]
}

// --------------------------------------------------------------------------------- the boxes

/** One section of one box, as `GET /boxes` reports it. `start` and `end` are `index` values in
 *  the same space as `Place.index`, so a span drawn from these and a marker drawn from
 *  `Place.fraction` are measuring the same box. */
export type SectionDetail = {
  section: number
  start: number
  end: number
  count: number
}

/** What a box's `state` may be SET to, which is one thing and not the same thing as what may
 *  come back off disk.
 *
 *  Narrow because it is sent: the server refuses anything it does not know as
 *  `box_state_invalid`, and a union caught at the call site is better than a refusal caught at
 *  the rig. Exactly the split `Finish` and `InventoryCard.metadata_finish` already draw — what
 *  the wire accepts, and what a record written before the server validated anything may hold.
 *
 *  ASSUMED, AND THE ONE TYPE IN THIS FILE THAT IS. The route contract names the refusals
 *  `box_state_invalid` and `box_closed` without publishing the vocabulary they police; these
 *  two words are read off those codes and off `Place.box_closed`, which is a boolean and so
 *  admits exactly two states. If the server speaks a third, this union is the one edit. */
export type BoxState = 'open' | 'closed'

/** One box: what it is called, how it is divided, and how full it is. `GET /boxes` serves a
 *  list of these and `POST`/`PUT /boxes` answer with the one they wrote.
 *
 *  `state` IS A LOOSE STRING HERE AND A UNION AT THE SEND SIDE, which is not an inconsistency
 *  — see `BoxState`. This value comes off disk. */
export type BoxRecord = {
  box: number
  name: string | null

  /** THE BOX'S DIVIDER INDICES, not a count of sections. D10 as amended 2026-08-23: a box
   *  "carries its own list of divider indices — `[1, 31, 56]` means section 2 starts at card
   *  31", set by the New section control at the moment the real divider goes in.
   *
   *  AN EMPTY LIST IS "UNDECLARED", NOT "ONE SECTION", and the difference is load-bearing:
   *  D10 says an empty list is what the 25-rule renders, which is what keeps every label
   *  written before boxes existed byte-identical. A screen may not read `[]` as a box with no
   *  dividers and draw one span from it — `sections_detail` is where the rendered answer is,
   *  computed once by `pipeline/join.py:Position` against whichever rule applies.
   *
   *  ONE FIELD IN THIS RECORD IS TYPED FROM D10 RATHER THAN FROM THE ROUTE CONTRACT, and it
   *  is this one — the contract named `sections` without saying what shape it takes, on the
   *  same day the decision that owns the concept was amended to make it a list. If the server
   *  answers a count, this is the one edit and the call sites fail loudly at the compiler
   *  rather than quietly at the box. */
  sections: number[]
  state: string
  capacity: number
  fill: number
  next_index: number
  cards: number
  sold: number

  /** Cards in this box that are `retired` (D26), and cards whose SKU holds a listing stage
   *  (D7 amended). Added with D34 so the delete panel can name WHICH of
   *  `box_not_empty_of_commitments`'s three grounds is holding the box open before anything
   *  is pressed — the three have different remedies, and `sold` alone could not tell them
   *  apart. `listed` counts CARDS, not SKUs and not copies: it is the number the refusal
   *  itself would name. */
  retired: number
  listed: number
  sections_detail: SectionDetail[]
}

/** `GET /boxes`, whole. The envelope, where `BoxRecord` is the element — named the way
 *  `QueueSnapshot` wraps `QueueEntryWire`, so a reader can tell at the import which of the two
 *  is a list. */
export type BoxSummary = {
  boxes: BoxRecord[]
}

/* ------------------------------------------------------------------ the pipeline seam
 *
 * The four commands of batch script v2, as `server/pipeline_routes.py` answers for them.
 * Until these existed the pipeline was the one capability in the product with no way in:
 * every run this project has done was driven by somebody typing commands in a terminal,
 * and `docs/GATES.md` records the cost of that — "the owner had no visibility into emitted
 * import files; their names exist only in CLI output the owner never sees when someone
 * else drives the commands".
 *
 * THE CONSOLE FIELD IS THE COMMAND'S OWN STDOUT AND IS MEANT TO BE SHOWN VERBATIM.
 * `docs/DESIGN.md`'s copy rule makes the owner's screens the place the pipeline's own words
 * appear rather than a paraphrase — being able to grep what you saw is worth more than a
 * consistent register — and a run report is the densest thing this product ever says.
 */

/** Which of the four steps a run is waiting for. Derived from the run directory on every
 *  read, never stored: `cli/runs.py` makes a run an immutable input rather than state. */
export type RunPhase =
  | 'ready'
  | 'identifying'
  | 'identify'
  | 'join'
  | 'emit'
  | 'reconcile'
  | 'done'

/** What a run was scoped to. `whole_box` is the common case and costs no temporary
 *  anything; a selection builds a directory of symlinks that is swept after 48 hours. */
export type RunScope = {
  box: number
  whole_box: boolean
  /** How many cards were selected, or null for a whole box — where the count is whatever
   *  is on disk at the moment the run starts rather than a number chosen in advance. */
  cards: number | null
}

/** One downloadable artefact. `is_import` is what lets a screen offer the file the owner
 *  actually came for without knowing the per-game naming rule. */
export type RunFile = {
  name: string
  bytes: number
  modified: number
  is_import: boolean
}

export type RunSummary = {
  run: string
  path: string
  created_at?: string | null
  updated_at?: string | null
  capture_dir?: string | null
  scope?: RunScope | null
  started_by?: string | null
  /** A child process is still driving this run. Checked with signal 0 rather than trusted
   *  from a pid file, because the file outlives the process it names. */
  live: boolean
  pid: number | null
  phase: RunPhase
  batch_ids: string[]
  collected: boolean
  joined: boolean
  counts: Record<string, number>
  /** The run was joined with D3 rung 3 switched off, and how many cards that resolved.
   *  Reported rather than inferred from a smaller queue: these are the cards the operator
   *  took responsibility for. */
  bypass_detection: boolean
  bypassed: number | null
  usage: { input_tokens?: number; output_tokens?: number }
}

export type RunDetail = RunSummary & {
  console: string
  files: RunFile[]
  manifest: Record<string, unknown>
}

/** What a run WOULD cost. Free, and creates no run directory at all — `identify --dry-run`
 *  returns before `runs.create`. The two numbers a screen must show before it may ask to
 *  spend; null where the preflight did not print the line, so a changed preflight shows as
 *  a missing figure rather than as a confident zero. */
export type RunPreflight = {
  ok: boolean
  exit_code: number
  scope: RunScope
  capture_dir: string
  console: string
  photographs: number | null
  cache_hits: number | null
  to_send: number | null
  estimate_usd: number | null
  /** A live run already reading these cards. The screen disables its own confirm on this
   *  rather than letting the operator press a button that is going to refuse. */
  busy_run: string | null
}

export type RunStarted = {
  run: string
  path: string
  pid: number
  scope: RunScope
  argv: string[]
}

/** A free step's result. A non-zero `exit_code` arrives as a 200 with `ok: false` — `emit`
 *  refusing while a price is unanswered is the most useful thing that command does, and an
 *  HTTP error would put a stack trace where the sentence naming the SKU belongs. */
export type RunStepResult = {
  ok: boolean
  exit_code: number
  step: 'join' | 'emit' | 'reconcile'
  run: string
  console: string
  dry_run: boolean
  files: RunFile[]
  summary: RunSummary
}

/** An uploaded CSV. Uploaded rather than named by path: a screen cannot know what is on
 *  the server's disk, and a route that opened any absolute path a request named would be a
 *  file-read primitive guarded by an origin header. */
export type CsvUpload = { name: string; content: string }
