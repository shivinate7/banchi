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
export type Finish = 'normal' | 'holo' | 'reverse_holo'

/** What the finish control on the capture screen holds, which is one state wider than the
 *  wire enum. `null` is NO CLAIM: the operator has not said anything about this stack, so
 *  nothing is sent and `sidecar_payload` writes no `variant` key at all — the file stays a
 *  record of claims actually made (D3 rung 1), which is the rule `set_hint` already
 *  followed on this side of the wire and `variant` did not.
 *
 *  THE NULL IS WHAT KEEPS D3 RUNGS 2 AND 3 REACHABLE, and that is the reason it exists
 *  rather than tidiness. `pipeline/variant.py:resolve` consults the catalog (rung 2,
 *  CATALOG_FORCED) and cross-checks detection (rung 3) only where `metadata_finish` is
 *  None. An app that always sends a claim makes both rungs dead for every card this product
 *  will ever capture: a holofoil-only SV-era rare shot with an untouched toggle would
 *  return METADATA_NOT_STOCKED and cost a review-queue tap, where the single catalog row
 *  would have decided it with no attention at all. Not touching a toggle is not a claim of
 *  `normal`, and once the sidecar is written the two are indistinguishable.
 *
 *  A SEPARATE TYPE RATHER THAN A FOURTH MEMBER OF `Finish`. Widening `Finish` itself is the
 *  shorter edit and the wrong one: `Finish` is the wire enum, and the server answers
 *  anything outside `pipeline/variant.py:FINISHES` with `variant_invalid`. A no-claim member
 *  living inside it would typecheck at `server.capture()`'s `variant` argument and fail at
 *  the rig. Two names keep "what the operator can choose" and "what the wire accepts" from
 *  collapsing into one set. */
export type FinishClaim = Finish | null

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
   *  size that nothing keeps in step with the pipeline's. */
  label: string
  section: number
  card: number

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

  /** Filesystem path again, not a URL. See `CardSummary.photo`. */
  photo: string | null

  set_hint: string | null

  /** The capture-time variant toggle. Typed as a loose string rather than `Finish | null`
   *  on purpose: this comes off disk, and the store holds records written before the
   *  server validated anything. Narrowing it here would make the type assert something
   *  about `inventory.json` that only `POST /capture` and `PUT /inventory` enforce. */
  metadata_finish: string | null

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
  run: string | null
}

/** `GET /inventory`, whole. Keys of `cards` are `store.master.position_key` — `"3/17"` for
 *  box 3, card 17 — so a lookup is `inventory.cards[`${box}/${index}`]`, and under
 *  noUncheckedIndexedAccess that read is `InventoryCard | undefined`. */
export type Inventory = {
  version: number
  cards: Record<string, InventoryCard>
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
  metadata_finish?: string | null
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
