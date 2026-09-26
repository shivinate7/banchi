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

  /** MUST EVERY CARD OF THIS GAME NAME ITS SET BEFORE ITS EXPORT MAY BE FETCHED?
   *
   *  `true` on a game whose whole TCGplayer category has been weighed and found too close
   *  to the transport's own ceiling to widen into on a guess. D76 scopes an export to the
   *  sets the run's cards name and widens the moment they stop agreeing, so on such a game
   *  ONE unhinted card is the whole difference between a narrow fetch and a refused one.
   *  `server/pipeline_routes.py:_scope_for_run` refuses that run; this flag is why.
   *
   *  READ HERE SO THE CAPTURE SCREEN CAN SAY SO AT THE RIG, WHERE IT IS FREE TO FIX. It
   *  NEVER gates the shutter — D65 and `setHint.ts` both hold that the rig does not stop
   *  for an autocomplete, and a capture that refused mid-feeder would be a card on the
   *  floor. The screen draws a note; the fetch is what refuses.
   *
   *  IT IS THE REGISTRY'S OWN FIELD AND NOT A COPY OF THE RULE. `GET /games` serves the
   *  entry verbatim, so the boolean an operator meets on the capture screen is the same
   *  literal `_scope_for_run` refuses on — there is no second threshold here to drift. */
  export_needs_hint?: boolean

  /** What this game's whole category weighs, where anyone has measured it. Bytes, or absent.
   *
   *  The evidence for the flag above, carried so a sentence can quote a figure instead of
   *  an adjective: Pokemon is 32,629,598 B, 97% of the 32 MB the download is refused past,
   *  against 238,482 B for one set. Absent means nobody has weighed it — never zero. */
  export_category_bytes?: number

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
/** One product a code card can have come out of, as `GET /games` serves it (C10). */
export type ProductEntry = {
  key: string
  display: string
  /** C11's tier. A premium code lists at roughly 46x a booster code, and keeping the two
   *  populations apart is the whole of what the Codes screen is for. */
  premium: boolean
  /** TPCi's SOFT redemption limit for this product type — past it a code grants a little
   *  in-game currency instead of the product, rather than being refused. Listing copy needs
   *  it and a buyer will ask. */
  redeem_limit: number
}

export type GameRegistry = {
  default: string
  games: GameEntry[]
  /** C10's product vocabulary. Served BESIDE `games` rather than inside a registry entry:
   *  `scripts/docs-audit.py` reads `pipeline/games.py` with `ast.literal_eval`, so that file
   *  can import nothing from this repo and could not carry this list without a second
   *  hand-authored copy of it. */
  products: ProductEntry[]
  /** Which game claims a product — `codes/products.py:GAME`, over the wire. The capture
   *  screen compares its chosen game against this to decide whether to draw the product
   *  picker, rather than hardcoding a game key on this side. That mirror is the thing
   *  `CaptureScreen.tsx` refuses for the registry itself, and it is no more acceptable for
   *  one string than for the whole vocabulary. */
  product_game: string
}

/** What `POST /capture` and `PUT /inventory/<box>/<index>` answer with: where the card
 *  landed. */
export type CardSummary = {
  box: number
  index: number

  /** `"<box>/<index>"`, the store's own key. Not a label and not a SKU. */
  key: string

  /** `Box 3 · Section 2 · Card 17`, rendered by `pipeline/join.py:Position.label` against
   *  the box's own dividers. The app displays this string and never composes a second one
   *  (capture-app spec section 5.1) — a client-side renderer is a copy of a rule nothing
   *  keeps in step with the pipeline's, and that rule moved on 2026-08-29 when the
   *  25-cards-per-divider default was deleted (D10, amended).
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
   *  `server.photoUrl(box, index, cid)` to display the photo — that is D6's route and the
   *  reason it exists. */
  photo: string | null

  capture_id: string | null

  /** THE CARD'S OWN NAME, so a client can address the PHOTOGRAPH rather than the slot
   *  (D172). Pass it to `photoUrl` as the third argument and the URL becomes
   *  `GET /photo/by-card/<cid>`, which means one thing forever: frozen at issue, unique in
   *  the store, and unmoved by the mid-box delete and the undo that both put a different
   *  card in one `(box, index)`.
   *
   *  THIS IS THE SHAPE THE SLOT ROUTE SERVES WORST, which is why the server puts it here
   *  first: the capture screen draws the frame it has just taken, at an index the box has
   *  never had before, and a browser that cached that index is the undo hazard
   *  `do_photo`'s own docstring opens with.
   *
   *  RAW, exactly as `_card_summary` sends it. A cid comes in four shapes and only two name
   *  a photograph — `photoUrl` holds that predicate so no caller has to know them, and a
   *  `moved:` or `nophoto:` name falls back to the slot rather than 404ing.
   *
   *  Optional because a server predating D172 sends no key at all, which is what an absent
   *  key honestly is; `photoUrl` reads `undefined` as "no name offered". */
  cid?: string | null

  /** THE FULL PLACE BLOCK, ALWAYS SENT (`server/capture_server.py:_card_summary` builds it
   *  off `_Places.of` for every response) but untyped here until R1d: `label`, `section`
   *  and `card` above are the same values duplicated for callers that predate this field
   *  (`_card_summary`'s own docstring). `place.box_total` is D58's on-hand count of the box
   *  AFTER this capture — the freshest answer there is, since the write that produced it
   *  is the same one this response reports on. Reading it here, rather than adding a
   *  second server field, is `_Places`' "one renderer" rule held from the wire side: a
   *  capture's own response already carries the count, so nothing needs to compute it
   *  again. */
  place: Place
}

/** `GET /status`. Counts, the next index per box, and whether the store is healthy. */
export type ServerStatus = {
  /** WHICH PROCESS ANSWERED. `make up` restarts the capture server whenever a watched Python
   *  file changes (D53), and a restart is otherwise invisible from here — same port, same
   *  store, and the only symptom of NOT having restarted is the one `docs/GATES.md` records:
   *  whole-second timestamps written two hours after the millisecond fix landed, because the
   *  process predated it.
   *
   *  Optional because a server predating the header (D73) does not send it, and the honest response to
   *  its absence is to say nothing rather than to claim a reload. */
  boot_id?: string
  started_at?: number

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

  /** The collector number as a screen draws it — `198/219`, unpadded, with a glued set code
   *  removed (D67). `pipeline/join.py:display_number` composes it and `cardNumber.ts` is the
   *  only thing here that reads it.
   *
   *  A FOURTH FLAT DECORATION AND THE ONLY UNCONDITIONAL ONE. The three above are a POSITION
   *  and are omitted when the server cannot work one out; a number is a fact about the card, so
   *  a pooled row and a row whose box will not coerce both carry theirs. Null where the card
   *  has no number at all.
   *
   *  IT DOES NOT REPLACE `number` AND `printed_total` BELOW, which stay exactly as the store
   *  holds them — what the model read, D36's durable fact and what `identifications.json` is
   *  reconciled against. This is the rendering. Optional for the reason every decoration here
   *  is: an absent key is what an older server actually sends, and `collectorNumber` composes
   *  the raw pair when it is missing. */
  number_display?: string | null

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

  /** THE CATALOGUE'S OWN SET (D213), ALREADY ON THIS WIRE AND NEVER TYPED HERE UNTIL NOW.
   *  `server/capture_server.py:_card_row` and `do_inventory` both ship `asdict(card)`
   *  raw — `store/master.py:Card.set_name` has carried this field since schema 8, and it
   *  reached `#/inventory`'s per-box read on every request since, with nothing on this side
   *  declaring it: the gap this filter closes was never a missing route, only a missing
   *  line in this file. `null` on every card identified before the field existed, or whose
   *  SKU resolves to no set — see `SearchGroup.set`, the same fact by the same name off
   *  `do_search`'s different renderer. */
  set_name: string | null

  /** The catalogue's own rarity, same source and same write moment as `set_name` above, and
   *  the same "already on the wire" note applies. Kept beside `rarity_claim` below and never
   *  merged into it — see `SearchGroup.rarity`'s longer note, which is the same fact. */
  rarity: string | null

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

  /** THE CARD'S OWN NAME (D172) — see `CardSummary.cid`, which is the same field arriving
   *  through the same `asdict`. Pass it to `photoUrl` and the photograph is addressed by
   *  name rather than by slot.
   *
   *  RAW HERE, AND THAT IS WORTH SAYING TWICE. `_card_row` and `do_inventory` ship
   *  `asdict(card)` and apply no predicate, where `_copy_row` filters — so an
   *  `InventoryCard` really can arrive carrying a `moved:` tombstone's name (D83) or a
   *  `nophoto:` one, neither of which names a photograph. `photoUrl` refuses both and falls
   *  back to the slot; no screen reading this field needs to know the four shapes.
   *
   *  It is NOT `photo_sha256` below. That one is set only by D89's reclaim and records the
   *  digest of a photograph that has been DELETED; this is a name that was frozen at issue
   *  and outlives every re-shoot — which is exactly why the two can differ. */
  cid?: string | null

  /** D89. Set together by the reclaim and by nothing else: the digest of the photograph that
   *  used to be at `photo`, and when it was deleted. Both null while the file is on disk —
   *  the file is the fact then, and a copy of its digest here would be a second thing to
   *  keep true through a re-shoot. A screen that finds these set draws "reclaimed", which is
   *  a different fact from "missing": one is a store that gave a photograph up on purpose
   *  after the card sold, the other is a store that lost something. */
  photo_sha256: string | null
  photo_reclaimed_at: string | null

  /* Everything below is written by the four commands — identify, join, emit, reconcile.
   * The app READS state and never sets it. That is not a simplification for this pass: the
   * app-side CSV import was struck from build-order step 7 because every state transition
   * is already owned elsewhere (capture-app spec section 2.1). */
  name: string | null
  number: string | null
  printed_total: string | null
  confidence: string | null

  /** THE EVIDENCE GROUP'S OWN COPY OF WHAT THE CAMERA READ
   *  (`docs/specs/identity-follows-sku.md` §3.1/§3.4/§4.1, lane 1). `record_identification`
   *  writes these three — never `name`/`number`/`printed_total` directly on a card `bind_sku`
   *  has bound — so a reading and a catalogue-derived identity can coexist and disagree
   *  without either overwriting the other. `read_number`/`read_printed_total` keep the
   *  model's raw shape, set code and all (D67, D55): unlike `number`/`printed_total`, no
   *  fold ever runs on these two. Null on every card identified before these fields existed.
   *  Never searchable (§5.2, ruling 4) and never rendered outside Details' own "Read as"
   *  line below (§5.4), which draws only when `read_disputes` is true.
   *
   *  OPTIONAL, on `types.ts`'s own standing rule for a server decoration: a server that
   *  predates this change sends no such key at all, and every fixture built before this
   *  change stays a valid `InventoryCard` rather than needing three new nulls typed in. */
  read_name?: string | null
  read_number?: string | null
  read_printed_total?: string | null

  sku: string | null
  condition: string | null

  /** THE BINDING GROUP (§3.1, lane 1): which SKU this card is, who chose it, and when —
   *  written only by `Inventory.bind_sku`/`unbind_sku`, never by `set_state`.
   *
   *  `identity_source` is `"sku"` when `name`/`number`/`printed_total`/`rarity`/`set_name`
   *  equal the SKU table's own row for `sku`, and `"read"` when the card has no SKU yet, is a
   *  HELD card (a SKU whose own reading disputes it, or a migration leftover, §7), or the SKU
   *  is absent from the table — in which case those same fields equal the evidence fields
   *  instead. There is no third value. `POST /inventory/<box>/<index>/confirm`
   *  (`server.ts:confirmIdentity`) is the press that turns a held card's `"read"` into
   *  `"sku"` with no new SKU; `CardHero.tsx:ListingCorrection` is where it lives, beside the
   *  D252 correction and inside the same reserved slot (D118).
   *
   *  `bound_by` is one of `join`, `answer`, `group_answer`, `correction`, `confirm`,
   *  `migration` — the act that last wrote the binding. `bound_at` is when.
   *
   *  Null on every card written before this change (a pre-migration record on a server that
   *  has not yet run `cards identity --write`, §7). Optional for the same reason the
   *  evidence group above is: an older server sends no such key. */
  identity_source?: string | null
  bound_by?: string | null
  bound_at?: string | null

  /** `pipeline/join.name_disputes(read_name, [identity name])` (§3.1), computed by the
   *  server at every write that changes either side and stored rather than joined live —
   *  `#/inventory` is a polled route. Gates the "Read as" line in Details (§5.4): a card
   *  whose read agrees draws nothing new. Optional and read as false where absent — a card
   *  from a server that predates this field, or a fixture that predates it, is a card with
   *  no recorded dispute rather than a third state. */
  read_disputes?: boolean

  /** identity-follows-sku.md §5.4/§8.1, the owner's ruling on Details' two identity lines
   *  (2026-09-24, verbatim: "show listing name and/or hide when identical i dont think it's
   *  an or situation") — BOTH rules, never an either/or. Computed server-side, every
   *  request, off the card's CURRENT shown `name`/`number`
   *  (`server/capture_server.py:_listing_decoration`) — never off `read_disputes` above,
   *  which answers a different question once, at bind time. The screen holds no fold logic
   *  of its own (CLAUDE.md: "No pipeline logic in the browser").
   *
   *  `listing` is the card's current SKU, read off the `skus` table (§3.2) and composed the
   *  same way `Inventory.bind_sku` composes one onto a card. `null` when the card carries no
   *  SKU, or a SKU the table does not (yet) hold (§3.2's escape hatch) — nothing to compare.
   *
   *  `listing_differs` draws "Listed as": the listing's own name or number disagrees with
   *  what `name`/`number` already show, so the photo's reading and the listing can be read
   *  side by side right above the confirm press. False on a card `identity_source: "sku"`
   *  except the rare case the row's own facts changed since the bind (§9, risk 3).
   *
   *  `reading_differs` draws "Read as": `read_name`/`read_number` disagree with the same
   *  shown pair. Always false on a HELD card (`identity_source: "read"`) — there the shown
   *  pair equals the read pair by construction, which is the fix: the line no longer
   *  repeats "Card:"/"Number:" word for word. It draws only after a confirm, or on a
   *  SKU-bound card whose reading disputes it.
   *
   *  Both folds are `pipeline/join.name_disputes` and §6's per-game number rule, never a
   *  raw string compare — a spelling-only difference lights neither line.
   *
   *  Optional, `types.ts`'s own standing rule for a server decoration: a server that
   *  predates this, or a route that omits it (`GET /inventory`, unscoped), sends no such
   *  key — read as `null`/`false`, never a third state. */
  listing?: { name: string; number: string | null; printed_total: string | null } | null
  listing_differs?: boolean
  reading_differs?: boolean

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
 * `live` IS THE EXPORT'S READING AND NOTHING ELSE, WITH ITS TIME (D115). D8 and D11 put the
 * authority in the TCGplayer export's `Total Quantity`, which `./pkmnscan join` and
 * `reconcile --live` read, and an export corrects it only where the export was read LATER than
 * `live_as_of` (D87 amended, `store/master.py:Listing.observe_live`).
 *
 * A SALE NO LONGER TOUCHES IT. It used to decrement this locally and stamp it now — a delta
 * wearing a reading's clothes — which is how one copy came to be subtracted twice: once by an
 * export that already knew, once by the sale. What has sold here since the reading is
 * `sold_here`, and the number to DRAW is the two together.
 *
 * Do not render `live` as a fact about the marketplace — render the estimate as what this
 * store believes now, `live` as what it last read, and `live_as_of` as when. `live_as_of` is
 * null on a record nothing has read `live` for yet — an emit's record before any join or
 * reconcile — and the export then answers whatever its age. */
export type Listing = {
  sku: string
  condition: string | null
  pushed: number
  staged: number
  live: number
  at: string | null
  staged_at: string | null
  live_as_of: string | null
  /** Copies sold HERE since `live_as_of`. A delta this store made, never a reading — see the
   *  block above. `reconcile --live` clears it when it adopts a reading taken after them. */
  sold_here: number
  /** When the newest counted sale happened. What stops an export fetched BEFORE a sale from
   *  cancelling it — the protection the old restamp of `live_as_of` used to buy. */
  sold_here_at: string | null
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
  /** This row's `Rarity` cell, and HALF OF WHAT `rarity_claim_mismatch` MEANS. Optional
   *  rather than nullable, and absent rather than empty, because `cli/resolve.py` omits the
   *  key for a row whose cell is blank — D23 reads a missing rarity as evidence of nothing,
   *  and an empty string on screen would assert the row is unrated. Absent too on every
   *  entry in a `review.json` written before 2026-09-11, which a queue file outliving its
   *  run makes an ordinary case rather than a migration. */
  rarity?: string

  /** WHICH READING OF THE PHOTOGRAPH FOUND THIS ROW, on the one entry where that question
   *  has two answers. A `name_disputed` card offers both readings — the rows the NAME found
   *  and the row the NUMBER found — so the list holds two different cards and the operator
   *  needs to know which signal argued for which.
   *
   *  ABSENT EVERYWHERE ELSE, and that absence is the contract rather than a gap: a list with
   *  one provenance does not need it stated, and `cli/resolve.py:_candidate_rows` omits the
   *  key unless the entry carries the split. A row drawing no provenance tag is the normal
   *  case, not a row whose provenance was lost. */
  found_by?: 'name' | 'number'
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
  /** D23's stack claim — the OTHER half of what `rarity_claim_mismatch` means, against the
   *  `rarity` on each `CandidateRow` above. A list, for `metadata_finish`'s reason: the
   *  claim has always been a set. Null means nobody claimed anything; absent means a queue
   *  file written before 2026-09-11, and the screen draws the same sentence for both, which
   *  is the honest one — it does not know what was claimed. */
  rarity_claim?: string[] | null
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

  /** DECORATED BY THE ROUTE, the card's whole place block and its stable name (D172), so the
   *  review screen draws the place the way Inventory does and links to THIS card
   *  (`#/inventory?box=<n>&card=<cid>`). Optional: an older server sends neither. */
  place?: Place
  cid?: string | null
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

  /** D58's counted number for the box, after this remove — `on_hand`, the same fact
   *  `BoxRecord.on_hand` and a capture's own `place.box_total` carry. Read from here rather
   *  than recomputed on the client: a remove changes it exactly as an undo does, and
   *  neither event refreshes `GET /boxes` on its own (R1c/R1d, D58). */
  on_hand: number
}

/** What `POST /inventory/<box>/<index>/move` answers — D83's third door.
 *
 *  Unlike `RemoveResult`, nothing here EVER renumbers a neighbour: the source position
 *  becomes a permanent tombstone (same shape as a sale or a retirement) and the card is
 *  recorded fresh at `new_box`/`new_index`. `card` is the transplant as it now reads —
 *  the same shape `GET /inventory` rows carry — so the screen can redraw it without a
 *  second read. Undo is not a separate result shape: moving the transplant back is this
 *  same call again, in the other direction. */
export type MoveResult = {
  moved: string
  to: string
  box: number
  index: number
  new_box: number
  new_index: number
  photo_moved: boolean
  sidecar_moved: boolean
  review_moved: boolean
  parked_moved: boolean
  cache_moved: boolean
  card: InventoryCard
}

/** What `POST /inventory/<box>/move` answers — D83's batched move: a ticked selection, a
 *  section, or (via `indices: null`) a whole box, which is what a merge is from the
 *  caller's side. `cards` carries one row per card in the same shape `MoveResult` uses,
 *  minus its own `card` field — the screen already knows what moved without re-fetching
 *  each one. */
export type MoveCardsResult = {
  box: number
  to_box: number
  moved: number
  cards: Omit<MoveResult, 'card'>[]
}

/** What `DELETE /boxes/<box>` answers — D10 ruling 3's whole-box delete.
 *
 *  Counts per kind rather than booleans, because a box holds many of each, and these
 *  numbers ARE the receipt: this is the most destructive action in the product and the only
 *  evidence it happened correctly is what it says it removed.
 *
 *  `directory_removed` false is not a failure. The server removes the photo directory only
 *  when the files it enumerated were all it held; a stray left behind keeps the directory
 *  and says so, rather than deleting something nobody accounted for.
 *
 *  `buried` is D134's amendment to ruling 3 (2026-09-11): a sold, retired or moved record no
 *  longer blocks this delete — it is buried, and `cards` counts it same as before while
 *  `buried` says how many of those `cards` left through a departure door rather than as
 *  ordinary on-hand junk. `#/graveyard` is where a buried record is read afterward. */
export type BoxDeleteResult = {
  deleted_box: number
  cards: number
  buried: number
  photos: number
  sidecars: number
  review_deleted: number
  parked_deleted: number
  cache_deleted: number
  registry_deleted: boolean
  directory_removed: boolean
}

/** One row of `GET /graveyard` (D134): a card that has left inventory, whichever of the
 *  two doors it went through, drawn in one shape regardless of which.
 *
 *  `buried` is what tells the two sources apart. `false` means this record is a sold,
 *  retired or moved card still standing in a box nobody has deleted — the same records
 *  `#/inventory` already draws as departed. `true` means its box WAS deleted (D134): the
 *  record itself is gone, and this row is read out of the `buried` history line instead.
 *  `buried_at` is null in the first case and the burial's own timestamp in the second.
 *
 *  `box_name` and `order` are best-effort: the box may never have been named, and `order`
 *  is only ever set when `Ledger.holder_of` finds this copy pulled against one. Every other
 *  field mirrors the departed `Card` (or the buried line's copy of it) whole — `null` means
 *  the record never carried that claim, not that it was withheld. */
export type DepartedCard = {
  left_at: string | null
  how: 'sold' | 'retired' | 'moved'
  box: number
  index: number
  box_name: string | null
  name: string | null
  number: string | null
  game: string | null
  set_hint: string | null
  sku: string | null
  condition: string | null
  retire_reason: string | null
  moved_to: string | null
  order: string | null
  run: string | null
  captured_at: string | null
  photo_sha256: string | null
  buried: boolean
  buried_at: string | null
}

/** `GET /graveyard` (D134): every departed card the store still knows about, newest
 *  departure first — the merge of what is still standing and what was buried. */
export type GraveyardPayload = {
  departed: DepartedCard[]
}

/** `GET /boxes/<box>/photos` — what a reclaim over this box would delete (D89). FREE and
 *  read-only, and the step that comes first: the control that deletes does not exist until
 *  this has answered, D34's preflight shape applied to bytes instead of counts.
 *
 *  `reclaimable` is the SOLD cards whose photograph is still on disk — not retired ones (D26
 *  keeps that photograph so the retirement can be questioned) and not cards on hand (the pull
 *  preview needs theirs). `reclaimed` is the sold cards whose photograph already went.
 *  `on_hand_photos` is what the box keeps afterwards, so the panel can say what a reclaim
 *  does NOT touch. */
export type BoxPhotoPlan = {
  box: number
  reclaimable: { cards: number; bytes: number; indices: number[] }
  reclaimed: { cards: number; indices: number[] }
  on_hand_photos: number
}

/** `POST /boxes/<box>/photos/reclaim`'s receipt (D89). `keys` is every record whose
 *  photograph went, so the claim is checkable afterwards — each of those records now carries
 *  `photo_sha256` and `photo_reclaimed_at`. There is no undo: the bytes are gone. */
export type PhotoReclaimResult = {
  box: number
  reclaimed: number
  bytes: number
  keys: string[]
  already_reclaimed: number
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

  /** The order line a REVERSAL released, or null (`docs/specs/undo.md` §4). Always null on a sale — recording
   *  a pull is `POST /orders/pull`'s job, already done before a card reaches this route sold —
   *  and null on a reversal that held no order line. Additive: every field above this one is
   *  unmoved. */
  order_released: { key: string; sku: string } | null
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
  /** D46 — this SKU came out of the catalog lookup, not out of the entry's offered rows.
   *
   *  Only ever true for an entry with NO candidates. The server re-reads the row out of the
   *  export the card was joined against and takes the condition from there, so this flag
   *  widens which rows may be chosen and never what may be written: an unknown SKU still
   *  refuses, as `sku_not_in_catalog`. Absent on every ordinary answer. */
  fromCatalog?: boolean
}

/** One catalog row offered by `GET /review/<box>/<index>/catalog` (D46).
 *
 *  DELIBERATELY THE SAME SHAPE AS `CandidateRow`, because the screen draws both through one
 *  component: a row the pipeline found and a row a person went and found look identical once
 *  they are on screen, and the difference that matters — whether the machine could find it —
 *  is carried by the surrounding copy rather than by the row. */
export type CatalogLookup = {
  box: number
  index: number
  game: string
  query: string
  searched?: boolean
  rows: CandidateRow[]
  found: number
  truncated: boolean
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

/** `POST /inventory/<box>/<index>/correct`, both directions (D252).
 *
 *  THE GAP `AnswerResult`'s OWN UNDO LEAVES: `undo_too_late` refuses the moment the wrong SKU
 *  has gone out — pushed, staged or live — which for a real mistake is usually already true.
 *  This route rewrites an identified card's SKU to a different catalog row REGARDLESS of the
 *  queue, and it never trusts the wire for the row: the server re-reads it from the card's
 *  own export, exactly as a D46 `fromCatalog` answer does.
 *
 *  `released` IS WHAT THE OLD SKU GAVE UP, through `Listing.release` (D34) — the count the
 *  next live reconcile reads as over-listed. Read it for the receipt's own words, never to
 *  decide anything: nothing on this screen edits a listing count directly. */
export type CorrectResult = {
  /** `"<box>/<index>"`, the store's own key. */
  position: string
  box: number
  index: number

  /** True when this call took a correction back rather than recording one — `AnswerResult`'s
   *  own field, under the same name. */
  undone: boolean

  /** The SKU the card carries after this call — the new one on a correction, the old one on
   *  its reversal. */
  sku: string
  condition: string

  /** The SKU this call replaced. Absent on a reversal, which restores it rather than naming
   *  it again. */
  previous_sku?: string | null

  /** What `Listing.release` gave up on the SKU this call replaced, by stage — `{pushed: 1}`
   *  for the ordinary case. Absent on a reversal, and empty when the old SKU carried no
   *  listing record at all (never pushed, so nothing to give up). */
  released?: Record<string, number>

  /** What an undo of THIS call would put back, or null when it would be refused —
   *  `AnswerOrigin`'s own shape, with the name the correction also restores. */
  restores_to: (AnswerOrigin & { name: string | null }) | null

  /** The card as `GET /inventory` would draw it, after this write. */
  card: InventoryCard
}

/** `POST /inventory/<box>/<index>/confirm`, both directions
 *  (`docs/specs/identity-follows-sku.md` §8.1).
 *
 *  THE RIGHT SKU, THE WRONG NAME. `CorrectResult` above answers "this listing is the wrong
 *  card"; this route answers the sibling case — a HELD card (`identity_source: 'read'`)
 *  whose SKU is already correct, so nothing needs to move. It NEVER TAKES A `sku` IN THE
 *  BODY: the listing already on the card is what gets confirmed, never a new one. The
 *  server's three refusals mirror `do_confirm_identity`'s own checks — `card_not_found`
 *  (404); `card_departed`, `not_identified`, `already_confirmed`, `sku_unknown` (409); on
 *  undo, `not_confirmed` (409) — so `CardHero.tsx`'s own control offers this press only
 *  where the server would not refuse it: an on-hand, SKU-carrying, held card.
 *
 *  UNLIKE `CorrectResult`, there is no `restores_to` to read before offering Undo:
 *  `do_confirm_identity` always captures the full identity snapshot before it writes, so a
 *  fresh confirm's own reversal is never refused for want of one — only for having moved on
 *  since (a second confirm, a correction, a fresh answer). */
export type ConfirmResult = {
  /** `"<box>/<index>"`, the store's own key. */
  position: string
  box: number
  index: number

  /** True on the write direction — the SKU already on the card is now confirmed. */
  confirmed: boolean

  /** True when this call took a confirm back rather than recording one —
   *  `AnswerResult`/`CorrectResult`'s own field, under the same name. */
  undone: boolean

  /** The SKU the card carries — unchanged by this route in either direction, since a
   *  confirm never moves the SKU (§8.1). Read for the receipt's own words. */
  sku: string
  condition: string

  /** The card as `GET /inventory` would draw it, after this write — `identity_source` is
   *  `'sku'` after a confirm and `'read'` after its undo. */
  card: InventoryCard
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
  /** The one condition GRADE the whole group shared — `near mint` for every real group on
   *  this store. It was `condition`, the full string, until 2026-09-12: the group may now
   *  mix finishes (`Near Mint` beside `Near Mint Foil`), so a single condition at the top
   *  would misdescribe half the members. Each row's own condition is on its own result. */
  grade: string
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

  /** Where the card stands in its box, 1 at the far back (D265). The sort key a walk orders
   *  by. It equals `index` until a section is placed into the box. Never drawn. Optional
   *  because an older server omits it: then `index` is the order. */
  order?: number

  /** The card's sequential position in the box — D10's allocator number, 1-based. THE STORE
   *  KEY: the `/inventory/<box>/<index>` path every write aims by, the `<index>.jpg` the
   *  photograph is named after, and half of `key`. It stopped being the numerator of the
   *  `#40 of 250` sentence with D58 — `slot` is — and the two differ by the number of cards
   *  that have left the box in front of this one.
   *  On a pooled block it is the KEY's second half, not a position — see `located`. */
  index: number

  /** This card's number among the cards ACTUALLY IN THE BOX (D58), 1-based, and the
   *  numerator of `#40 of 250`. Null for a card that has left by either door and for one the
   *  server could not count — in both cases `label`, `section` and `card` are null too, and
   *  a screen must draw the absence rather than fall back to `index`, which counts in the
   *  numbering system D58 replaced. */
  slot: number | null

  section: number | null
  card: number | null

  /** What the owner calls this box, or null when he has not named it. A label for humans and
   *  never an identifier: `box` is the identifier, and two boxes may carry the same name. */
  box_name: string | null
  /** The section's own name, or null. D132 — read-time join, never stored on a card. */
  section_name?: string | null

  /** The first and last `index` of the section this card is in. `section_end` is null when
   *  the section has no end yet — the open end of an open box, and the whole of a box that
   *  declares no sections at all. A null is "not decided", never "unbounded at zero". */
  section_start: number
  section_end: number | null

  /** How many cards the box holds now (D58). A box has no lid (`D-sealed-boxes-removed`), so
   *  this number always moves with the next capture. */
  box_total: number

  /** How far into the box this card sits, 0 to 1, or null when the server cannot say — an
   *  empty box, or a record whose numbers do not support the division. NULL IS NOT ZERO and
   *  must never be coerced to it: zero is the front of the box, which is a specific and wrong
   *  place to send somebody. The same rule `ServerStatus.queues` states for its own nulls. */
  fraction: number | null

  /** The ADJACENT records that are still physically in the box on either side of this
   *  one — D30's digital half. `Card 17` is the seventeenth SLOT, not the seventeenth card you
   *  can count, and once a section has holes those two stop being the same number; the
   *  neighbours are what make the label countable by hand again. Sold and retired records are
   *  passed over, never named — a departed card cannot be the thing you count from. An
   *  on-hand card nothing has named IS a neighbour (the owner's ruling, 2026-09-24, LOC-28,
   *  amending D116), said as "an unread card"; `PlaceNeighbor.unread` counts the run.
   *  `prev` (toward the back) and `next` (toward the front) are null past the box's ends.
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

/** One side of `Place.neighbors`: where the neighbouring record is, in BOTH spaces, and its
 *  identified name or null.
 *
 *  THIS COMMENT SAID THE OPPOSITE OF THE TRUTH UNTIL D92, and it is the third place the two
 *  spaces were confused in writing. It read "the index is D10's allocator number — the same
 *  space as `Place.index` — so `#41` drawn from it is a slot a hand can count to, not a store
 *  key". Both halves of that are right and the conclusion inverts them: `Place.index` IS the
 *  store key, D58 made the drawn number a COUNT, and a `#41` composed from the key is
 *  therefore precisely NOT the slot a hand counts to. `server.ts:placeParts` had the same
 *  fact recorded correctly as a known hazard on the very next screen, and neither reader
 *  checked the other — which is what the `make check` row added with D92 now does.
 *
 *  `slot` is what a renderer draws; `index` is for a caller that needs to ADDRESS the card
 *  (D45's way back into the walk) and no renderer may put a bare `#` in front of it. */
export type PlaceNeighbor = {
  /** D58's count — this card's number among the cards actually in the box. What gets drawn. */
  slot: number
  /** D10's allocator number: `/inventory/<box>/<index>`, the `<index>.jpg`. Never drawn bare. */
  index: number
  name: string | null

  /** How many unread cards stand in a row on this side, starting with this neighbour, up to
   *  the next named card or the box's end (the owner's ruling, 2026-09-24, LOC-28). Zero on a
   *  named neighbour. Drawn as "an unread card" or "3 unread cards" (`server.ts:neighborWords`).
   *  Departed cards are never counted here: the box closed up over them (D58).
   *
   *  Optional for the reason every late field in this file is: an older server sends a
   *  neighbour without it, and a nameless side then reads as one unread card. */
  unread?: number
}

// ------------------------------------------------------------------------------- the search

/** One physical copy in a search result: the store's own key, its pipeline state, where it is,
 *  and the id a write aims by.
 *
 *  STILL NOT THE WHOLE `InventoryCard`, AND THAT RULE IS INTACT: the search answers "where are
 *  my copies of this card", and a row carrying `confidence`, the run and the metadata would
 *  invite a second inventory view to grow inside a search result. What this comment said until
 *  D93 was that `capture_id` was one of the fields being kept out, and that cost the order walk
 *  the ability to aim at any copy but the ones the resolver had already picked — so choosing a
 *  different copy meant walking to it first, which is the flow the owner called unintuitive.
 *  An identity is not a view. */
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

  /** THE ID EVERY WRITE AIMS BY, and the reason a copy can be picked off this list at all (D93).
   *
   *  `POST /orders/pull` checks it against the card actually at the slot and refuses
   *  `capture_id_mismatch` rather than selling whatever slid into the index after a mid-box
   *  delete (D10 ruling 1, D58) — so an id, and not a `(box, index)`, is what a copy is chosen
   *  BY. Null for a record written before ids were kept and for one `emit` created rather than
   *  the camera; a copy carrying null cannot be taken, and the screen says so rather than
   *  sending a target the server would refuse. */
  capture_id: string | null

  /** THE NAME, FOR THE SAME ONE READER `capture_id` IS HERE FOR, one layer along (D172).
   *  `CardLocations.tsx` and `Inventory.tsx` draw a copy's photograph off this row, and the
   *  carve-out D93 argued for `capture_id` applies unchanged: what this type refuses is a
   *  SECOND INVENTORY VIEW growing inside a search result, and a name is not a view.
   *
   *  ALREADY FILTERED, unlike `InventoryCard.cid`. `_copy_row` applies
   *  `store/photos.py:is_photo_cid` before it puts the field here, so a `moved:` tombstone
   *  and a `nophoto:` card arrive as null — the same answer `has_photo` gives, for the same
   *  reason. `photoUrl` applies the predicate again anyway; one side filtering is not a
   *  reason for the other to stop. */
  cid?: string | null

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

  /** The whole collector number as a screen draws it, agreed across the copies, or null.
   *
   *  AGREED ON THE FOLDED FORM, WHICH IS WHY IT IS A THIRD FIELD AND NOT A RENDERING OF THE TWO
   *  ABOVE (D67). `_agreed` returns null the moment the copies disagree, correctly — but five
   *  copies of one card storing `198/219`, `UNL • 198/219` and `UNL - 198/219` are not
   *  disagreeing about the card, only about what the model glued to the front of it. Folded,
   *  they agree and the group can draw a number; genuinely different reads (`044/106` against
   *  `044/166`) still null both fields and the group still says nothing. */
  number_display: string | null
  set_hint: string | null

  /** THE CATALOGUE'S OWN SET, BESIDE `set_hint` AND NEVER A REPLACEMENT FOR IT
   *  (D213). `set_hint` above is the
   *  operator's own claim, typed at the shutter; this is read off the export row the SKU
   *  resolved to at identification time. `null` on every card identified before this field
   *  existed, until `./pkmnscan cards identity --write` or the next identification fills
   *  it — a screen prefers this and falls back to `set_hint`. */
  set: string | null

  /** The catalogue's own rarity, same source and same write moment as `set`. Kept beside
   *  `InventoryCard.rarity_claim` and never merged into it — a disagreement between the
   *  two is itself information (see the governing decision). */
  rarity: string | null

  condition: string | null

  /** How many copies have reached each of the three listing states. Three counts and not one,
   *  because `staged` and `live` are two facts about two different things — D7's refill maths
   *  reads the LIVE number, and an import that was staged and never moved live has no live
   *  quantity at all. Merging them here would hide exactly the box that is not earning. */
  listed: { pushed: number; staged: number; live: number }

  /** Copies sold HERE since the reading in `listed.live` was taken (D115).
   *
   *  BESIDE `listed` AND NOT INSIDE IT, because it is not a stage: `store/master.py` keeps it
   *  out of `LISTING_STAGES` so D34's box-delete release cannot surrender it and it is not
   *  summed into the store's stage totals. What a screen draws is `listed.live - sold_here`,
   *  floored — see `app/src/cardState.ts:forSale`.
   *
   *  REQUIRED HERE AND OPTIONAL ON `PricingSku.listing`, WHICH IS NOT AN INCONSISTENCY. This
   *  one is composed per request by `capture_server.py` off the live store, so the server
   *  decides it exists; that one is read back out of a file `join` wrote at some earlier
   *  moment, and a file cannot gain a field it was written before. */
  sold_here: number

  /** When `listed.live` was read, or null where nothing has read it. Drawn beside the figure:
   *  a live count is never shown without its age (the owner, 2026-09-03). This is the stamp to
   *  use rather than `Listing.at`, which every writer touches — including a sale, which after
   *  D115 observes nothing about `live` and would make the age look fresher as the figure got
   *  staler. */
  live_as_of: string | null

  /** Copies still in the boxes — D7: "copies on hand is a count of UNSOLD positions".
   *
   *  NOT `copies.length`, AND THE TWO MUST NOT BE USED INTERCHANGEABLY. `copies` carries the
   *  sold ones as well, because D10 keeps a sold record at a permanent gap and CLAUDE.md's
   *  rule is that nothing silently drops a card — so a group with four copies of which one is
   *  sold reports `on_hand: 3` and sends four entries. A screen wanting "how many are still
   *  there" reads this field; a screen wanting "how many rows to draw" reads the array. */
  on_hand: number


  /** How many copies of this SKU could be live — WHAT THE SHELF HOLDS, since D7's standing
   *  cap was deleted (amended 2026-09-08). It was `min(cap, on hand)` while a cap existed,
   *  and the pair `cap`/`listable` was on the wire so a screen could draw either the rule or
   *  what the rule permitted here. There is no rule now, so there is one field.
   *
   *  THE DENOMINATOR A SCREEN ACTUALLY WANTS, AND `cap` IS NOT IT. The two differ whenever the
   *  shelf holds fewer than a playset, and that is most of the store: a card the owner has one
   *  of was drawn as `listed 0 of 4`, which reads as three copies of headroom that do not
   *  exist. `cap` is the RULE; this is what the rule permits here.
   *
   *  Both are on the wire because they answer different questions and a screen may want either
   *  — "what is the ceiling" versus "how many of these could be live". Neither is computed in
   *  the browser: `server.ts` records that the app is forbidden from computing the live cap,
   *  and a `Math.min` over `cap` here would be that rule kept in two places. */
  listable: number

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
  /** The operator's own word for the section — `Rares` — or null where none was given.
   *  Joined at read time by ordinal (D132), the way `box_name` is (D56). */
  name: string | null
  /** The box map's landmarks and aim (D264): the first and last card on hand in the section,
   *  by name for the eye (null where no card is named) and by cid for a move's aim. Null for
   *  an empty section. Absent from an older server. */
  first_name?: string | null
  last_name?: string | null
  first_cid?: string | null
  last_cid?: string | null
}

/** What `POST /boxes/<box>/sections/move` answers (D264): the move's id for Undo, the
 *  physical instruction, and both boxes as `GET /boxes` draws them. */
export type SectionMoveResult = {
  move: string
  box: number
  to_box: number
  /** The box a split made, or null. */
  created: number | null
  moved: number
  /** Each moved section's new ordinal in the destination. */
  landed: number[]
  receipt: {
    heading: string
    steps: string[]
    renumbered: string[]
  }
  boxes: BoxRecord[]
}

/** Where a section move lands: in front of a section of `toBox`, or at its near end (null). */
export type SectionMoveTarget = {
  toBox: number | 'new'
  before: number | null
}

/** Where a card or a range lands (D264): in front of a card of `toBox` (its stored index),
 *  or after the last card of one of its sections. */
export type CardMoveTarget = {
  toBox: number
  beforeCard: number | null
  sectionEnd: number | null
}

/** What `POST /boxes/sections/undo` answers. */
export type SectionUndoResult = {
  move: string
  undone: boolean
  boxes: BoxRecord[]
}

/** One box: what it is called, how it is divided, and how full it is. `GET /boxes` serves a
 *  list of these and `POST`/`PUT /boxes` answer with the one they wrote.
 *
 *  `state` IS A LOOSE STRING HERE AND A UNION AT THE SEND SIDE, which is not an inconsistency
 *  — see `BoxState`. This value comes off disk. */
export type BoxRecord = {
  box: number

  /** THE TRUE INDEX OF THIS DRAWER — allocated once at its creation, never reused, and never
   *  rendered (D145). The owner said the last part twice: *"a box needs an index # not visible
   *  anywhere in the app thats a true index rather than cheaply using boxes as an index"*.
   *
   *  NOTHING IN `app/` MAY DRAW THIS. It is in the same relationship to `box` that `Place.index`
   *  is to `Place.slot` (D58): the key a machine joins on, beside the number a person reads off
   *  the drawer. What a screen draws is the ANSWER a comparison of two of these produces — and
   *  today there is exactly one such answer, the capture screen's restore.
   *
   *  WHY A CLIENT NEEDS IT AT ALL, which `box_bid` on a run row does not make obvious: the
   *  capture screen remembers a box between sittings (D142), and `next_box_number` hands a
   *  deleted box's number straight back out to the next drawer. The number cannot tell those
   *  two drawers apart and this can.
   *
   *  `null` IS AN ORDINARY ANSWER. A box that holds cards but has no registry entry has no id,
   *  and neither does a store an older build migrated — `store/master.py:Box.bid` is optional
   *  forever, for `Card.rarity_claim`'s reason. Absent altogether from a server predating the
   *  field, which is the same nothing. */
  bid: number | null
  name: string | null

  /** THE BOX'S DIVIDER INDICES, not a count of sections. D10 as amended 2026-08-23: a box
   *  "carries its own list of divider indices — `[1, 31, 56]` means section 2 starts at card
   *  31", set by the New section control at the moment the real divider goes in — which is
   *  `S` on the capture screen, built 2026-08-29 and calling `openSection` in `server.ts`.
   *
   *  AN EMPTY LIST IS "UNDECLARED", AND SINCE 2026-08-29 THAT RENDERS AS ONE SECTION. The
   *  paragraph here used to say the difference was load-bearing because `[]` was what the
   *  25-cards-per-divider rule rendered; that rule is deleted (D10, amended), and an
   *  undeclared box is now the single undivided section it physically is. The prohibition
   *  it protected still stands and is the reason this note is rewritten rather than cut: a
   *  screen may not derive spans from this list. `sections_detail` is the rendered answer,
   *  computed once by `pipeline/join.py:Position`, and it is the only thing that stays right
   *  when the rule underneath it moves — as it just did.
   *
   *  ONE FIELD IN THIS RECORD IS TYPED FROM D10 RATHER THAN FROM THE ROUTE CONTRACT, and it
   *  is this one — the contract named `sections` without saying what shape it takes, on the
   *  same day the decision that owns the concept was amended to make it a list. If the server
   *  answers a count, this is the one edit and the call sites fail loudly at the compiler
   *  rather than quietly at the box. */
  sections: number[]
  fill: number
  next_index: number
  cards: number

  /** Cards this box HOLDS: located records that have not left by either door (D58). The
   *  denominator of every number the screens draw for this box, and none of the three above
   *  it — `cards` counts records including departed ones, `fill` is the allocator's
   *  high-water mark, and `capacity` is what the box froze at when it was sealed. Null when
   *  the server could not count the box, which is not zero: an empty box holds none, and an
   *  uncountable one is not known to. */
  on_hand: number | null
  sold: number

  /** Cards in this box that are `retired` (D26), and cards whose SKU holds a listing stage
   *  (D7 amended). Added with D34 so the delete panel can name WHICH of
   *  `box_not_empty_of_commitments`'s three grounds is holding the box open before anything
   *  is pressed — the three have different remedies, and `sold` alone could not tell them
   *  apart. `listed` counts CARDS, not SKUs and not copies: it is the number the refusal
   *  itself would name. */
  retired: number

  /** Cards moved OUT of this box to another one (D83) — `retired`'s sibling on the same
   *  panel. A box left holding only sold, retired or moved records after a merge no longer
   *  blocks a delete (D134): those records are buried, and only `listed` below still
   *  refuses. Drawn for the same reason it always was — so the delete panel can say what
   *  the box holds before the press, not just after a refusal. */
  moved: number
  listed: number
  sections_detail: SectionDetail[]

  /** How many of this box's cards pass D213's game/set/rarity filter — present ONLY while a
   *  filter is active, and absent (never zero-by-default) while it is not, matching
   *  `server/capture_server.py:_box_row`'s own contract. `BoxBrowse.tsx` reads this to grey
   *  a box in the rail exactly the way a search's own `matches` count already does — one
   *  behaviour, two sources, so the box rail never learns a second way to say "nothing here". */
  matches?: number
}

/** One value of a facet, with how many cards in the whole store carry it (D213). `null`
 *  is the unclassified bucket — a real value, not an absence, and never dropped from the
 *  list: `game` and `count` (etc.) are the field names `_card_facets` sends, so this stays
 *  one contract for both readers of `_rows`'s output. */
export type FacetCount = { readonly count: number }
export type GameFacet = FacetCount & { readonly game: string | null }
export type SetFacet = FacetCount & { readonly set: string | null }
export type RarityFacet = FacetCount & { readonly rarity: string | null }

/** `GET /boxes`'s `facets` block — the game/set/rarity vocabulary this store actually
 *  holds (D213), never a hardcoded list. `sets` and `rarities` are keyed by game, because
 *  D213's whole reason for a dropdown over chips is that one game's set list must not leak
 *  into another's; a game with no cards of its own is simply absent as a key. The empty
 *  string key holds cards with no game claim at all (`_card_facets`'s own docstring says
 *  why `""` is safe to use this way) — no card in the owner's store has ever needed it. */
export type InventoryFacets = {
  games: GameFacet[]
  sets: Record<string, SetFacet[]>
  rarities: Record<string, RarityFacet[]>
}

/** `GET /boxes`, whole. The envelope, where `BoxRecord` is the element — named the way
 *  `QueueSnapshot` wraps `QueueEntryWire`, so a reader can tell at the import which of the two
 *  is a list. */
export type BoxSummary = {
  boxes: BoxRecord[]
  facets: InventoryFacets
  /** Every card, grouped by box, game, set, rarity and whether it left (sold, retired or
   *  moved). `#/inventory` folds these for its facet counts and per-box matches, so a pick in
   *  any order costs no request (FLT-09). `null` is the unclassified bucket. Absent from an
   *  older server, where the rail shows no counts. */
  facet_cells?: FacetCell[]
}

export type FacetCell = {
  readonly box: number | null
  readonly game: string | null
  readonly set: string | null
  readonly rarity: string | null
  readonly gone: boolean
  readonly count: number
}

/** The filter `BoxBrowse.tsx` sends `getBoxes` (D213). A key ABSENT from this object means
 *  "not filtering that facet" — the three-state `getBoxes` needs and a plain `string | null`
 *  cannot give, since `null` here means "filter for the unclassified bucket" and must be
 *  told apart from "no filter at all". `Partial` is exactly that: TypeScript's own way to
 *  say a key may be missing rather than merely `undefined`-valued. */
export type InventoryFacetFilter = Partial<{
  game: string | null
  set: string | null
  rarity: string | null
}>

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

/* ------------------------------------------------------------------- pricing (D49)
 *
 * The per-SKU table `cli/cmd_join.py` writes beside `report.txt`, served with this run's
 * answers by `GET /pipeline/runs/<name>/pricing`. Field names are the server's own, in the
 * server's own case, which is this file's standing rule — so a screen can be held against
 * `pricing.json` on disk without a translation table in between.
 */

/** One SKU, priced. Every figure here was computed by `pipeline/pricing.py` at join time;
 *  the client performs no arithmetic on money, anywhere. */
/** ONE BUCKET — a day on `month`, a week on `annual`. What the endpoint said, coerced.
 *
 *  `market` is a STANDING figure and is present on buckets that sold nothing, which is why
 *  `quantity` is beside it rather than implied: every weighted figure in the payload filters
 *  on `quantity > 0`, because including a bucket with no sales weights TCGplayer's opinion
 *  equally with a transaction. A sparkline may draw the standing price; a mean may not. */
export type HistoryPoint = {
  /** ISO date, or null for a bucket whose stamp would not parse. */
  at: string | null
  market: string | null
  quantity: number
  low: string | null
  high: string | null
}

/** ONE RANGE OF ONE SKU. `points` is ASCENDING — oldest first.
 *
 *  THE WIRE ORDER IS THE OPPOSITE AND THE SERVER ALREADY TURNED IT. `infinite-api` sends
 *  newest-first and `Series.parse` sorts; nothing on this side may re-sort or reverse it,
 *  because a list read backwards inverts the sign of every reading with no symptom at all —
 *  a rising card drawn falling. */
export type HistoryRange = {
  range: string
  buckets: number
  /** The span the buckets actually cover, so a caption needs no width table in TypeScript.
   *  The WIDER range is the STALER one: weekly buckets are stamped at the start of their
   *  week, so `annual`'s `to` ran six days behind `month`'s on the same card at one moment. */
  from: string | null
  to: string | null
  latest_market: string | null
  /** THE ANCHOR. A volume-weighted mean of each bucket's market price — the best point
   *  estimate available, and the figure to draw at size. Null when nothing sold in the
   *  range, never zero: D9 is emphatic that a missing price is an UNKNOWN price rather than
   *  a low one, and $0.00 is the reading that hands a chase card away at the floor. */
  vwap: string | null
  /** A SANITY CHECK AND NEVER A RESULT — see `pipeline/pricehistory.py`'s header, which
   *  says so at length. We hold per-bucket lows and highs rather than fills, so a true VWAP
   *  is not computable, only BOUNDED. Measured on Moonfall: $12.54..$20.35 around a point
   *  estimate of $16.33. Drawing this as a price with an error bar of comparable authority
   *  to `vwap` is that paragraph being ignored. */
  bound: {
    low: string
    high: string
    /** The same interval over two denominators, both named, because one card's bound is
     *  honestly "48% wide" and "62% wide" and a bare percentage invites the two to be read
     *  as a disagreement about the same card. */
    width_of_vwap: string
    width_of_low: string
  } | null
  /** Where the price went: the first `window` SOLD buckets against the last. POSITIVE IS
   *  RISING — stated because the wire order is newest-first, so a sign here is one unsorted
   *  list away from meaning its opposite. Nulls when the series holds fewer sold buckets
   *  than one window, rather than a zero that would read as a measurement. */
  momentum: {
    early: string | null
    late: string | null
    change: string | null
    fraction: string | null
    window: number
  }
  /** Copies sold across the range, as the endpoint reports it. How fast this moves. */
  liquidity: number
  transactions: number
  /** Copies per order. Above 1 is playsets rather than singles, which is what decides
   *  whether D7's four-copy cap is actually binding on this card. */
  units_per_transaction: string | null
  /** Volume-weighted mean of (high - low) WITHIN a bucket — sellers disagreeing on one day,
   *  not movement across the range, which is `momentum`'s job. */
  dispersion: string | null
  points: HistoryPoint[]
}

/** What one SKU has been selling for, read from two PUBLIC mirrors on an explicit press.
 *
 *  IT IS A READING BESIDE THE EXPORT AND NEVER A PRICE. D8 makes the Filtered CSV the
 *  pricing source and nothing here reopens that: `market` below is the export's own figure,
 *  carried so the panel can put the two side by side, and no field in this type is ever
 *  written back or fed to a rule.
 *
 *  THE RANGES OVERLAP AND NOTHING MAY MERGE THEM. `annual` is not the year before `month` —
 *  it is 357 days that INCLUDE the same recent days at a coarser width, so concatenating
 *  them double-counts the recent window and skews every weighted figure over the result.
 *  Two readings to present side by side, never two halves to add up. */
export type PriceHistoryPayload = {
  run: string
  sku: string
  product_id: number
  name: string | null
  set_name: string | null
  condition: string | null
  /** The export's `TCG Market Price` for this SKU — what the card is priced against TODAY.
   *  Read at the moment of the join, where every figure under `ranges` was read just now. */
  market: string | null
  /** Finest range first, so `ranges[0]` is the daily one. */
  ranges: HistoryRange[]
  /** A real, catalogued product the endpoint has never seen SELL — measured on two of them.
   *  It answers HTTP 200 with a null result there, so an empty `ranges` is not a failure and
   *  a screen reading it as one would report a join defect over a card that is merely
   *  illiquid. */
  never_sold: boolean
}

/** ONE RANGE OF ONE SKU, AS THE PER-PRODUCT VIEW READS IT (`#/product`, D227).
 *
 *  NOT `HistoryRange` REUSED, ON PURPOSE. The archive-hit path (`source: "archive"`) has no
 *  `Series` object behind it — only the raw buckets `store/pricearchive.py` stored — so it
 *  cannot honestly carry `vwap`, `bound` or `momentum`, all of which are computed from a live
 *  `Series`. `vwap` and `bound` are present only on the live-fallback path
 *  (`source: "live"`), and a reader must check `source` before reaching for either. */
export type ProductHistoryRange = {
  range: string
  width_days: number | null
  buckets: number
  from: string | null
  to: string | null
  latest_market: string | null
  vwap?: string | null
  bound?: {
    low: string
    high: string
    width_of_vwap: string
    width_of_low: string
  } | null
  points: HistoryPoint[]
}

/** One product's market history, addressed by SKU rather than by a run
 *  (`GET /pipeline/products/<sku>/history`, D227).
 *
 *  `source` IS THE ONE FIELD A READER MUST BRANCH ON. `"archive"` means every figure came off
 *  `store/pricearchive.py` with no network reached at all. `"live"` means the archive had
 *  never swept this SKU and the server reached `pipeline/pricehistory.py:Market` once, the
 *  same reading `#/pricing`'s panel already draws. Neither path ever writes.
 *
 *  `history_begins` IS COMPUTED FROM WHAT WAS ACTUALLY READ, never from the 357-day constant
 *  — a year of local archive is not a year of market history, and the two must never be
 *  conflated (`docs/specs/revenue-next.md`). */
export type ProductHistoryPayload = {
  sku: string
  product_id: number | null
  name: string | null
  set_name: string | null
  condition: string | null
  source: 'archive' | 'live'
  ranges: ProductHistoryRange[]
  history_begins: string | null
  never_sold: boolean
}

/** ONE RANGE'S NAMES — `GET /pipeline/holdings-value?range=<range>`, D236. UNSOLD STOCK, never
 *  sold-then-against-now (that is D225's `SoldPricesLookup`, a different figure this must
 *  never merge with). The four ranges overlap on the calendar and are NEVER merged or
 *  concatenated (D62) — one range per call, one range on screen at a time. */
export type HoldingsRange = 'month' | 'quarter' | 'semiannual' | 'annual'

/** ONE BUCKET OF ONE SKU'S HOLDING. `value` is `market` times the SKU's TODAY quantity —
 *  never a past quantity, this store keeps none. `gap_before` is computed from the
 *  immediately preceding STORED point, never the calendar day before it: true means this
 *  point does not continue from the last one, and a screen must break its drawn line there,
 *  never interpolate. A `null` `value` is a real day the source answered with nothing — never
 *  a zero, never plotted. */
export type HoldingsPoint = {
  start: string
  market: string | null
  quantity: number
  value: string | null
  gap_before: boolean
}

/** ONE SKU'S SERIES over the requested range. `points` is ascending, oldest first.
 *  `latest_value` is null when every point is unpriced — never a zero. */
export type HoldingsSeries = {
  sku: string
  name: string
  quantity: number
  latest_value: string | null
  points: HoldingsPoint[]
}

/** ONE CALENDAR START'S PORTFOLIO TOTAL — an honest PARTIAL sum, never a rollup. It sums
 *  only the SKUs actually priced at this exact date; `priced_names` and `unpriced_names`
 *  state the coverage beside the figure so a smaller later total is never read as a loss.
 *  NEVER RECOMPUTE THIS BY SUMMING `HoldingsSeries[].points` — that second total could drift
 *  from the server's own partial-coverage sum, which is the only total this route offers. */
export type HoldingsTotal = {
  start: string
  value: string
  priced_names: number
  unpriced_names: number
  gap_before: boolean
}

/** `GET /pipeline/holdings-value?range=<range>` (D236) — unsold stock, valued by SKU off the
 *  price-history archive, one range at a time. THE POSITION IS THE SKU (D212): a holding is
 *  a quantity, never a slot, a box or a copy list.
 *
 *  `sealed_excluded` AND `unmarked` ARE COUNTED, STATED EXCLUSIONS, NEVER ZERO AND NEVER
 *  OMITTED (owner's ruling, 2026-09-20: "still stands — singles, stated gap"). Sealed product
 *  has no card record, so this route cannot count what sits on the shelf for it; sales of
 *  sealed product are known, unsold sealed stock is not counted here. `unmarked.names` is
 *  on-hand SKUs the archive has never priced in any range — a coverage fact about the sweep,
 *  never an absent card. */
export type HoldingsValuePayload = {
  range: HoldingsRange
  width_days: number
  history_begins: string | null
  /** D236's own entry writes this as a Unix second (`1758345600`). MEASURED AGAINST THE
   *  ROUTE ITSELF, 2026-09-20: it actually answers an ISO string (`store/master.py:now()`'s
   *  own return type, carried through `pipeline/holdings.py:HoldingsReport.at` unconverted
   *  despite that field's `int` type hint there). Typed here as the string the wire actually
   *  sends — never used by this screen's own render, which reads `history_begins` and
   *  `totals[]` instead, but a client reading this field must not be handed a number that
   *  never arrives. Reported rather than "fixed": `pipeline/holdings.py` and its route are
   *  out of this change's fence. */
  at: string
  on_hand_names: number
  series: HoldingsSeries[]
  totals: HoldingsTotal[]
  unmarked: { names: number }
  sealed_excluded: { names: number; reason: string }
}

/** ONE RANGE OF ONE SKU AS A ROW DRAWS IT — a shape and a sign, and deliberately no money.
 *
 *  IT IS NOT A SMALLER `HistoryRange` AND MUST NOT GROW INTO ONE. D62's panel is where a
 *  reading's figures live; D79 gives the row a strip and gives it exactly what a 90px cell
 *  can carry honestly. The row already has four dollar columns and the field a listing price
 *  is typed into, so a fifth figure — a READING rather than a price — would sit inches from
 *  that field inviting a copy across, which is the D8 reopening D62 refused by name. Anything
 *  added here that is denominated in dollars is that refusal being spent.
 *
 *  `points` IS ASCENDING and `null` MEANS NO PRICE AT ALL. The client BREAKS the line at a
 *  null rather than interpolating: measured on Vilemaw's annual, whose oldest buckets predate
 *  the card's printing — 21 of 52 on the run this was built against — and joining through
 *  them would draw a year-long slope that never happened. */
export type TrendRange = {
  range: string
  /** The span these buckets cover. Identical across every SKU of a run — measured, all 46 on
   *  `2026-08-31-box3-01`, both ranges — which is why the SECTION captions it once and the
   *  row does not. A row has no width to say when a range ends and forty-six copies of one
   *  date would be the panel drawn badly. */
  from: string | null
  to: string | null
  /** POSITIVE IS RISING. Dimensionless, which is what makes it safe on this row. */
  fraction: string | null
  points: (string | null)[]
}

/** Many SKUs' shapes in one read — D79, the batched half of D62.
 *
 *  BOTH DIRECTIONS, WHICH IS `CLAUDE.md`'s HARD RULE AND VISIBLE IN THIS TYPE. Every SKU the
 *  route was asked about comes back in `skus` or in `refused`, never absent, and `skipped`
 *  counts the rows it was never asked about — the ones this run can add nothing for. Without
 *  that count a strip drawn over 46 of 60 rows reads as fourteen failures. */
export type TrendsPayload = {
  run: string
  asked: number
  skipped: number
  skus: Record<string, { product_id: number; ranges: TrendRange[] }>
  refused: Record<string, string>
}

export type PricingSku = {
  sku: string
  game: string
  /** THE EXPORT ROW, VERBATIM — all sixteen cells, unmodified, keyed by the CSV's own column
   *  names. The owner asked for "all the data from the CSV shown when I make the decision",
   *  and a subset chosen server-side would be a decision about what matters taken by the
   *  wrong file. */
  row: Record<string, string>
  /** Which import file this SKU is bound for, and therefore which section it draws in.
   *  Decided by the Market cell alone (`pipeline/join.py:prices_for`), so nothing the
   *  operator types can move a row between sections — which is what makes the list stop
   *  reflowing under a commit (D28). */
  bucket: 'listable' | 'sub_threshold' | 'no_market_data'
  copies: number
  add_to_quantity: number
  backstock: number
  /** The export's `Total Quantity` cell for this SKU — what TCGplayer reports LIVE, and
   *  nothing else. It is the narrower of the two figures below and it is the one that reads
   *  0 for a copy sitting on an import nobody has reconciled: measured at 167 pushed copies
   *  across 72 SKUs of the owner's store, zero of them live, where a screen drawing this
   *  alone said TCGplayer holds nothing about SKUs it holds several of. Draw it only where
   *  the sentence means the export (D59). */
  live_before: number
  committed: number
  /** Copies TCGplayer is holding right now — live plus pending, per SKU and across every
   *  box, which is what the cap is actually spent against. `>= live_before` always: D8 and
   *  D11 make the export's live column a FLOOR the store may never argue down, so this
   *  corrects it upward for a push the pipeline has not seen land and never downward
   *  (D59). */
  copies_out: number
  at_cap: boolean
  /** WHY this run adds no row for a SKU it matched, composed by `pipeline/join.py:
   *  SkuMatch.nothing_to_add` — or `null` when it adds one, which is the ordinary case.
   *
   *  A SENTENCE RATHER THAN THE PARTS TO BUILD ONE, and that is the point of the field.
   *  `at_cap` above says a row was not written and cannot say why: at the cap, held out by
   *  an unreconciled push, or every copy in this run already listed or gone. Those have
   *  three different remedies, and a screen reassembling them from `live_before`,
   *  `copies_out` and `committed` would be a second copy of that property's reasoning with
   *  nothing auditing the two against each other — the drift D16 exists to catch. The
   *  client performs no arithmetic on money and none on the cap either (D59). */
  nothing_to_add: string | null
  condition: string
  set_name: string
  name: string
  /** The four export price columns plus the export's own `TCG Marketplace Price`, each
   *  rendered to two decimals or `null` where the cell is blank. `null` is a real answer:
   *  measured, `TCG Direct Low` is blank on 2,060 of 2,476 listable rows in the wide export,
   *  so a snap onto it usually has nothing behind it and must refuse rather than write "". */
  snap: {
    market: string | null
    direct_low: string | null
    low: string | null
    low_with_shipping: string | null
    now: string | null
  }
  /** What each named preset would list this SKU at, `null` where it cannot price it — 394 of
   *  2,476 listable rows carry no `TCG Low Price`, so a Low-based preset genuinely has
   *  nothing to work from. The screen prices what it can and says which it could not. */
  presets: Record<string, string | null>
  /** The run's own rule applied to this SKU, which is the suggestion a row opens carrying. */
  rule_price: string | null
  /** Every copy, in box-walk order. The FIRST is the representative photograph and the
   *  screen names which one it is drawing — there is no quality signal worth trusting, and
   *  confidence is the tempting one and exactly wrong (T1's misses are confident answers
   *  with the digits wrong), so an arbitrary pick made steppable is the honest version.
   *
   *  `box` and `index` ARE THE STORE KEY AND `label` IS A RENDERING OF IT, which is the same
   *  split `Place` states two hundred lines up. The key is what `cli/cmd_join.py` wrote into
   *  `pricing.json` and what `photoUrl` addresses; the label is composed FRESH on every read
   *  by `server/pipeline_routes.py:_relabel_positions` and the one frozen into the file is
   *  never served (D58, on D56's rule) — so a copy that sold after the join reads
   *  `Box 3 · departed · B3 #17` and a divider moved since reads against the layout that is in
   *  the box today.
   *
   *  `null` FOR A LABEL THE SERVER WILL NOT COMPOSE, exactly as `Place.label` is: the box's
   *  walk degraded, or no located record names that box any more. It is not the pooled case
   *  — a pooled copy carries `place_text`'s own string here rather than a gap (D24). What a
   *  caller draws instead is the caller's decision, and `#/pricing` follows `BoxBrowse`'s
   *  `no label · <key>`. */
  positions: { box: number; index: number; label: string | null }[]
  /** The listing record as it stood WHEN THE RUN WAS JOINED, frozen into `pricing.json`.
   *  `sold_here` rides with it since D115: `live` is the export's reading, and a screen
   *  drawing the reading alone would over-report by exactly the copies sold since.
   *
   *  `sold_here` IS OPTIONAL BECAUSE THE RECORD IS FROZEN AND D115 IS NEWER THAN THE FILE
   *  (D115, amended). This is read back off disk rather than composed by the server — the
   *  route serves `pricing.json` through — so the declaration describes what `cli/cmd_join.py`
   *  writes TODAY, and every table written before a field existed contradicts it. Measured on
   *  the owner's store: **all 171** non-null listings across the eight stored runs carry no
   *  `sold_here`, and reading it as a `number` had the screen draw `NaN live`.
   *  `written_at` below is the same class and was already declared this way.
   *
   *  NEVER READ IT BARE. `cardState.ts:forSale` takes the pair and `soldSince` takes this
   *  one; both coerce, and the `?` here is what makes the compiler say so. */
  listing: { pushed: number; staged: number; live: number; sold_here?: number } | null
  /** What TCGplayer holds now, off the NEWEST live export on disk, or null when none was
   *  ever fetched (round 7, R6-1). Every send and every check writes one, so this is minutes
   *  old where `snap.now` is the join's. A price change and a move of live copies are named
   *  against it, and the send refuses if TCGplayer moved again since. Optional: an older
   *  server sends none. */
  live_now?: { export: string; copies: number; price: string | null } | null
}

export type PricingTable = {
  run: string
  threshold: string
  floor: string
  rule: string
  basis: string
  presets: string[]
  games: { game: string; import_listed: string; import_subthreshold: string }[]
  skus: PricingSku[]
  bands: { game: string; label: string; skus: number; copies: number }[]
}

/** A SKU the operator is deliberately not listing. The bare `"unlisted"` string is the same
 *  answer with no reason attached, which is what a terminal user types. */
export type WithheldRecord = {
  withheld: string
  watch_above?: string
  note?: string
}

/** One run's pricing decision, as `GET .../pricing` projects the corpus for one run (D86).
 *  Deliberately loose, for the reason the corpus type below gives: every reader on `#/pricing`
 *  takes this shape, and the corpus is projected into it rather than each reader learning a
 *  new one. */
export type DecisionsDocument = {
  rule?: string
  basis?: string
  sub_threshold?: string | { flat: string } | null
  overrides?: Record<string, string | number | WithheldRecord>
  no_market_data?: Record<string, string | null>
  [key: string]: unknown
}

export type PricingPayload = {
  run: string
  pricing: PricingTable
  decisions: DecisionsDocument | null
  /** When `pricing.json` was last written, as a UNIX SECOND — `cli/cmd_join.py` rewrites it on
   *  every join, so this is the moment a join last read an export and therefore the age of
   *  every figure under `snap`.
   *
   *  IT IS NOT WHEN TCGPLAYER PRICED THE CARD. The export is a file the operator downloaded at
   *  some earlier moment nothing on this machine can see, so a screen drawing this says READ
   *  rather than AS OF — `BoxBrowse.tsx:marketText` is the one that does.
   *
   *  Optional, because a server older than 2026-08-29 answers without it and this type is cast
   *  rather than validated. */
  written_at?: number
}

/* ------------------------------------------------- the cross-run pricing worklist (D86) */

/** One run's own row for a SKU the worklist merged — the whole `PricingSku` that run wrote,
 *  plus which run it came out of.
 *
 *  IT NO LONGER CARRIES AN ANSWER, and the absence is D86's amendment. A leg used to bring its
 *  run's own answer so the screen could compare them; there is one answer now, in the corpus,
 *  so there is nothing to compare. What a leg is still for is WHERE the card is — the boxes on
 *  the row — and which runs a merged emit would cover. */
export type PricingLeg = PricingSku & {
  run: string
}

/** One card across every run in the worklist. A `PricingSku` in its own right — every field
 *  is the NEWEST run's, so the screen draws one reading rather than halves of several — with
 *  the physical copies unioned and three fields the merge adds. */
export type MergedSku = PricingSku & {
  /** Every run holding this SKU, oldest first. The write fans out over exactly this list. */
  in: PricingLeg[]
  /** What the runs SEPARATELY believe they may add. `add_to_quantity` beside it is what can
   *  actually go — `min(claimed, cap - copies_out, copies)`. They differ when runs joined
   *  before either emitted each spent the same room against a global cap. */
  claimed_add: number
  over_cap: boolean
}

/** `GET /pipeline/pricing` — one worklist over several runs.
 *
 *  `decisions` IS KEYED BY RUN AND STAYS THAT WAY. D48 rules that a run's answer file is a
 *  property of what is in the drawer; this route merges the VIEW and never the file, and one
 *  answer to a merged row is one `PUT` per run in that row's `in`. */
export type RosterRun = RunSummary & {
  /** Why this run still has pricing in it, in `emit`'s own words. Empty means answered. For a
   *  person to read, never for a screen to decide on: that is `owed` below. */
  owes: string[]
  /** The machine code for each `owes` reason, in the same order, and the count its sentence
   *  carries (R4). A screen decides on this and never on the sentence. */
  owed: OwedReason[]
  /** Open while it OWES something OR HOLDS AN UNSENT COPY (D156). The
   *  first is `owes`; the second is `unsent` below, and it is what keeps an answered, emitted
   *  run on the worklist for as long as one of its copies is not at TCGplayer. */
  open: boolean
  /** Copies in this run's own positions that the store says TCGplayer does not hold — counted
   *  NOW, against the live store, never off the join's table. Absent from a server older than
   *  2026-09-12, which the picker reads as zero. */
  unsent?: number
}

/** WHY AN EMPTY SEND SENT NOTHING, as figures (R6-2): cards that need a price, priced cards
 *  under the cut-off a listed-only send held back, and cards TCGplayer already held every copy
 *  of, with their names. Rides a `needs_price` or `under_cut_off` refusal's `data.empty`. */
export type EmptySend = {
  needs_price: number
  under_cut_off: number
  live: number
  live_names: string[]
}

/** WHY A RUN OWES, AS A CODE. The same list as `server/pipeline_routes.py:OWE_CODES`, one
 *  literal per line, reconciled both ways by `make readiness-agreement`. */
export type OweCode =
  | 'sub_threshold_unset'
  | 'needs_price'
  | 'never_emitted'
  | 'unreadable'

/** One `owes` reason as a code, with the count its sentence carries, or null. */
export type OwedReason = { code: OweCode; count: number | null }

/** What no worklist can offer, named rather than left out (D156,
 *  `CLAUDE.md`: never silently drop a card). Each figure is a door to the screen that moves
 *  it: `captured` was never identified and `unjoined` was never joined (both `#/runs`),
 *  `in_review` is waiting on a person (`#/review`), and `reallocated` is a run over a drawer
 *  whose number was deleted and reused (D36) — unreachable by any join, and drawn in the
 *  picker as `Box N (deleted)`. */
export type Unreachable = {
  captured: number
  in_review: number
  unjoined: { run: string; cards: number }[]
  /** `cards` is how many of the run's cards this store still HOLDS — not how many it read.
   *  A run over a reallocated drawer withholding nothing and one withholding 99 sellable
   *  cards were the same sentence until this field existed. `null` means the server could
   *  not open the store, which is not the same claim as zero.
   *
   *  A RESCUE ALREADY DISCHARGES PART OF THIS COUNT (`pkmnscan rescue`, D36's own repair):
   *  `cards` is the on-hand figure minus every JOINED rescue's own `rescued_cards`, summed —
   *  an unjoined rescue has not put its cards on any worklist yet and does not subtract.
   *  `rescued` is that sum and `rescued_by` names the rescue run(s); both are absent from a
   *  server older than this field, which a reader treats as zero/none. */
  reallocated: {
    run: string
    box: number | null
    cards: number | null
    rescued?: number
    rescued_by?: string[]
  }[]
}

/** One card's answer as the corpus stores it — D49's shapes, with provenance beside them. */
export type CorpusAnswer = {
  value: string | number | WithheldRecord | null
  at?: string
  from_run?: string
  /** `"price"` for `overrides`, `"unknown"` for `no_market_data`. The channel decides which
   *  gate `emit` measures the answer against, so it is carried rather than inferred. */
  channel?: string
}

/** `GET /pricing` — every listing answer this operator has given, and the standing policy.
 *
 *  ONE DOCUMENT FOR THE STORE (D86, amended). It was one per run, which is why the same card
 *  carried one answer per drawer it had been photographed in — 66 SKUs on this machine, 8
 *  answered twice, 3 of those a hold overridden by a later price. A price is a fact about a
 *  SKU; this is where it lives.
 *
 *  `skus` IS DELIBERATELY LOOSE AND ROUND-TRIPPED WHOLE, exactly as `DecisionsDocument` was:
 *  `PUT /pricing` replaces the document, so a key a later version adds — or `_note`, which a
 *  person writes by hand — has to survive a screen that has never heard of it. */
export type PricingCorpus = {
  version?: number
  policy: {
    rule?: string
    basis?: string
    /* D9's cut-off, as the operator set it: the market price at or above which a card goes in
       the listed file. A string like the other money on this document. Always present on the
       wire — `"0.40"` where the store has never set one — and what `pipeline/join.py` and
       `pipeline/merge.py` partition by, so the split drawn on `#/pricing` is the split emit
       writes. */
    threshold?: string
    sub_threshold?: string | { flat: string } | null
    per_run?: Record<string, Record<string, unknown>>
  }
  skus: Record<string, CorpusAnswer>
  [key: string]: unknown
}

/** Which answers a mass-clear MAY remove, and how old each one is — the ENVELOPE of
 *  `GET /pricing`, never part of the document (D168).
 *
 *  THE SERVER SAYS WHICH; THE SCREEN ONLY COUNTS. `#/pricing` puts the figure in the label
 *  before the press — per scope and per age window — by intersecting `days` with the rows it
 *  drew. Re-deriving membership here would be `pipeline/corpus.py:clearable` written a second
 *  time in TypeScript, on the one file in this product that holds money.
 *
 *  WHAT IS ABSENT FROM `days` IS THE POINT AS MUCH AS WHAT IS IN IT. A hold is a judgement
 *  with a reason, a watch and a note attached (D49) and is never clearable; a `channel` other
 *  than `"price"` is the ABSENCE of an answer, which `emit` reads to refuse. Both are counted
 *  so the sheet can say what it is leaving alone rather than leaving it to be discovered. */
export type PricingClearable = {
  /** SKU -> whole days since that answer was written, or `null` for one carrying no readable
   *  `at`. `null` is honest and not a zero: those answers predate the stamp or were folded in
   *  by the migration, and D103 rules that inventing a date for them is refused — so an age
   *  filter leaves them alone and the sheet names them. */
  days: Record<string, number | null>
  /** Left alone always: a hold is a judgement, not a typed price. */
  holds: number
  /** Left alone always: `channel !== 'price'` is the absence of an answer. */
  unknown: number
}

/** What one press of the mass-clear removed, and everything it left standing. */
export type PricingClearResult = {
  ok: boolean
  /** THE WAY BACK, AND IT IS THE ANSWERS RATHER THAN THE SKUS. Each carries the value and the
   *  date it was typed on, which is what lets `restorePricingAnswers` put a price back without
   *  re-dating it — a restore that stamped would read as a store-wide re-pricing on the next
   *  markdown survey. */
  cleared: Record<string, { value: string | number | null; at?: string; from_run?: string }>
  count: number
  holds: number
  unknown: number
  /** In scope, a typed price, and left alone because an age filter cannot place an answer with
   *  no readable date. Zero when the press asked for every age. */
  undated: number
  answers: number
  revision: string
}

export type PricingWorklist = {
  runs: RunSummary[]
  /** EVERY joined run and what it still owes — the picker's list, not the worklist's. The
   *  picker has to draw runs that are not loaded (that is what makes it a picker) and say
   *  which are worth loading, so this is deliberately wider than `runs` above. */
  roster: RosterRun[]
  skus: MergedSku[]
  written_at: Record<string, number>
  /** A run that could not be read, named rather than dropped — an eight-run worklist must not
   *  fail to draw because one directory predates `pricing.json`. */
  skipped: { run: string; code: string; message: string }[]
  asked: string[]
  /** The two run-wide figures a row is drawn against, off the newest run in the list. Null
   *  where no table could be read, which the screen falls back on rather than blanks. */
  threshold: string | null
  floor: string | null
  /** Optional, for a server that predates it; the deck draws nothing when it is absent. */
  unreachable?: Unreachable
}

/** WHICH DRAWER THIS RUN'S CARDS TURNED OUT TO BE IN — derived from the cards, never from the
 *  path, and `null` on the run where they are in more than one.
 *
 *  IT IS NOT THE SELECTION AND THE TWO ARE BOTH ON THE WIRE. This answers "which drawer", which
 *  `runBoxLabel`, the claim panel and the server's own `refuse_reallocated` (D36) all read;
 *  `RunSelection` below answers "what did the press name", which none of them can reconstruct.
 *  A press over the whole store that swept up only box 3 leaves this identical to a press aimed
 *  at box 3, and a different selection.
 *
 *  `whole_box` IS COUNTED AND NO LONGER INFERRED FROM A PATH. It means what it has always meant
 *  — this run read every photograph the drawer holds — and it is answered by counting the
 *  drawer's own directory, because under a selection the path is the scan ROOT and the drawer is
 *  a filter over what each capture recorded. No temporary directory is built for either case any
 *  more: a ticked selection is a list of position keys on the wire. */
export type RunScope = {
  box: number
  whole_box: boolean
  /** How many cards this run holds in that drawer, or null for a whole box — where the count is
   *  whatever was on disk at the moment the run started rather than a number chosen ahead. */
  cards: number | null
}

/** WHAT A PRESS NAMED. One object, every term optional, and every term NARROWS — so the order
 *  they were given in cannot change which cards were read.
 *
 *  THE BOX IS A TERM AND NOT THE UNIT OF WORK. `POST /pipeline/identify` used to refuse any
 *  request without a positive integer `box` (*"A run is always scoped to one box"*), so
 *  "identify everything that still needs it" was not a sentence this app could say. Each of
 *  these is a name the store already has for a group of cards: the drawers on the shelf, D145's
 *  true indices, the dividers somebody put in one (D10), D21's game claim, `master.STATES`
 *  verbatim, a capture time, the `box/index` keys the cache and the join are keyed by, and a
 *  run's own card list.
 *
 *  `box` AND `bid` ARE ALWAYS ARRAYS HERE, EVEN FOR ONE DRAWER, and the request may send either
 *  shape. One press on this store has named three drawers, so the term is list-valued; a reader
 *  asking which shape it got before it can ask anything else is what D48 argued against for its
 *  own response, and that half of the argument is kept. */
export type RunSelection = {
  paths?: string[]
  state?: string
  box?: number[]
  bid?: number[]
  section?: number
  game?: string
  since?: string
  keys?: string[]
  run?: string
  /** The selection names nothing, so it is every photograph in the store. The screen may send
   *  this; a terminal refuses it without `--all` typed, because the screen has the free
   *  preflight and a confirm in front of it and a terminal has a newline. */
  all?: true
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
  /** Which box this run is over, by the server's own derivation — the manifest's scope block
   *  where there is one, and the capture directory's name where there is not (two of the four
   *  runs on this machine predate `scope` entirely). Sent so the client stops re-deriving it;
   *  `runScope.ts:boxOf` keeps the old derivation only for a server that predates the field. */
  box?: number | null
  /** What the owner calls that box, joined against the registry AT READ TIME (D56).
   *
   *  NEVER STORED ON THE RUN, which is the whole reason it is a field on the wire rather than
   *  something `identify` could have written into the manifest. D20 makes a rename a live edit
   *  to the registry that relabels every card in the box on every screen that draws one, so a
   *  name copied into a run directory would be a second answer that goes stale the moment the
   *  drawer is relabelled. `null` where the box has no name (D20 leaves names optional) or
   *  where the registry no longer holds it (D10 ruling 3). */
  box_name?: string | null
  /** The TRUE INDEX of the drawer this run was over — never displayed, and the owner said so
   *  twice (D145). It is on the wire so the SERVER can tell two drawers wearing
   *  one number apart; `box_former` below is the answer it produces, and that is what a screen
   *  draws. `null` for a run written before the field existed.
   *
   *  NOTHING IN `app/` MAY RENDER THIS. *"a box needs an index # not visible anywhere in the
   *  app"* — it is a join key, in the same relationship to `box` that `Place.index` is to
   *  `Place.slot` (D58): the key the machine joins on, beside the number a person counts to. */
  box_bid?: number | null
  /** The drawer this run was over is not the box wearing its number today: it was deleted, and
   *  D20 handed its number straight back out to the next drawer.
   *
   *  THE COMPLAINT THIS ANSWERS, 2026-09-11: *"i deleted an old box 1, started writing into a
   *  new box (now new box 1) and if i go on say my runs tab it shows that i'd run a 'Box 1' run
   *  a long time ago etc. it's confusing."* Absent or false is the ordinary case and reads
   *  exactly as it always did. */
  box_former?: boolean | null
  started_by?: string | null
  /** A child process is still driving this run.
   *
   *  THE SERVER HOLDS THE HANDLE FOR CHILDREN IT STARTED and asks the process itself; signal 0
   *  over the pid file is the FALLBACK, for a run it did not start — one orphaned across a
   *  restart. This said "checked with signal 0 rather than trusted from a pid file" until
   *  2026-09-11, and signal 0 was the whole rule then: a detached child is still a child,
   *  nothing waited on it, and an unwaited child that exits is a ZOMBIE whose pid signal 0
   *  accepts. A finished run read `live` for as long as the server stayed up. In the fallback
   *  the run's own `identifications.json` is the floor, because the pid may have been reused. */
  live: boolean
  pid: number | null
  phase: RunPhase
  batch_ids: string[]
  collected: boolean
  joined: boolean
  counts: Record<string, number>
  /** What the model read, and what that cost.
   *
   *  `cost_usd` IS THE SERVER'S AND IS NEVER DERIVED HERE. `identify/cost.py` holds the only
   *  rate sheet in this repo; a `tokens * rate` in TypeScript would be the second cost model
   *  `RunPreflightTotal` below forbids for the number the confirm is gated on, and there is no
   *  reason it is safer for the number the receipt reports. Absent where the run recorded no
   *  usable token counts at all — a confident $0.00 is worse than a blank.
   *
   *  `cost_backfilled` MEANS THE FIGURE IS TODAY'S RATES APPLIED TO AN OLD RUN'S TOKENS, not
   *  what the run itself recorded (D21's backfill-at-the-read, one field over). The two agree
   *  until the price sheet moves, and this is the only thing that will say so when it does. */
  usage: {
    input_tokens?: number
    output_tokens?: number
    cost_usd?: number
    cost_backfilled?: boolean
  }
  /** What stopped the automatic match, while the run still waits for one (flow interview, Q4).
   *  Null when nothing did. Optional because an older server sends no key. */
  match_problem?: RunMatchProblem | null
}

/** One reason the automatic match could not run. `step` says whether the catalogue fetch or the
 *  match itself refused. `message` is the server's own sentence, drawn behind a disclosure. */
export type RunMatchProblem = { code: string; message: string; step: 'fetch' | 'join' }

/** `POST /pipeline/runs/<name>/match`. `ran` is false when the run was not waiting for a match,
 *  a match was already running, or a problem stands and no retry was asked. */
export type RunMatchAnswer = {
  ran: boolean
  ok?: boolean
  reason?: 'not_waiting' | 'problem_stands' | 'running'
  problem?: RunMatchProblem
  summary: RunSummary
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
/** ONE PRESS: which cards, and how they are read.
 *
 *  THE READING IS PART OF THE SEND AND NOT A SETTING BESIDE IT. `RunPanel`'s cost estimate has
 *  been voided by a change to the crop or the max edge since D32 was amended — the estimate is
 *  computed from the bytes each card is sent as, and those two decide them — so the reading was
 *  already inside the thing being quoted.
 *
 *  IT IS ONE READING FOR THE PRESS, WHERE IT USED TO BE ONE PER BOX. D48 gave each leg of a
 *  cart its own crop and max edge and called that the deciding argument for a cart at all.
 *  Measured on this store: 12 of 15 runs share one `max_edge`, the three that differ are three
 *  separate presses on three days, and the one multi-drawer press there has ever been gave all
 *  three of its drawers an identical reading. An operator who wants box 3 read at 1200 and box 5
 *  at 900 presses twice. */
export type RunSend = {
  selection: RunSelection
  crop?: boolean
  maxEdge?: number
}



/** Which cards in one leg a live submission is already holding, and whose it is.
 *
 *  THE SENTENCE COMES FROM THE SERVER AND IS NEVER REBUILT HERE. `store/submissions.py`
 *  composes it for both refusal sites — the command's, before it submits, and the route's,
 *  before it spawns — and a third spelling on this side would be a third message an operator
 *  has to learn to read as one thing. */
export type ClaimConflict = {
  /** How many of this press's cards are held. The figure is the point: two is a double-click,
   *  four hundred is a different mistake.
   *
   *  `box` WENT WITH THE CART. A refusal over a cart had to say which leg it was about; there is
   *  one selection now, so the row speaks the vocabulary the claim itself uses. */
  cards: number
  receipts: string[]
  runs: string[]
  sentence: string
}

/** One live claim on the cards a run is paying to read (`GET /pipeline/submissions`).
 *
 *  `holder_alive` IS THE FIELD THE SCREEN BRANCHES ON, and it is reported rather than acted
 *  on. A claim whose holder is gone still blocks: a run killed after it submitted has a batch
 *  in flight nobody collected, and a guard that self-healed that row would offer a green
 *  button over an invoice already rung up. So a live holder means WAIT and a dead one means
 *  the release is offered — and the choice stays the operator's. */
export type SubmissionClaim = {
  receipt: string
  /** Null for a claim written by a press that had not got as far as creating a run. */
  run: string | null
  pid: number
  started_at: string
  cards: number
  /** A few of the positions, never the whole set — a store-wide press claims hundreds. */
  sample: string[]
  capture_dir: string | null
  holder_alive: boolean
}

/** THE FREE COUNT THAT COMES BEFORE THE CONTROL THAT FIRES, which is `BoxPhotoPlan`'s shape
 *  one feature over (D89). `counts` is the WORK this guard is doing — rows, cards locked, and
 *  how many are held by a process that is gone — published rather than inferred from the fact
 *  that nothing has gone wrong. */
export type SubmissionClaims = {
  claims: SubmissionClaim[]
  counts: { claims: number; keys: number; stale: number }
}

/** What a release did. `released: false` is an ordinary answer and not a failure — the claim
 *  was already released, which is what a replayed request and a stale screen both land on. */
export type ClaimRelease = {
  receipt: string
  run: string | null
  released: boolean
  cards: number
  /** The list as it stands after the press, so the caller never re-reads to redraw. */
  claims: SubmissionClaim[]
}

/** The one card the crop preview is showing, and what this reading does to it.
 *
 *  `rect` is in the ORIGINAL frame's pixels and the screen turns it into percentages, so it
 *  can be drawn over the photograph `GET /photo/<box>/<index>` already serves — which is why
 *  changing the reading costs no bytes at all: only the rectangle moves.
 *
 *  `rect` is null when the reading sends the whole frame, and there are THREE reasons it can
 *  be: the crop is off, detection found nothing, or a card was found and the box was refused
 *  as unfit to cut to. They look identical in the payload and mean different things to an
 *  operator — a setting they chose, a photograph to look at, and a detector that answered
 *  confidently and wrongly. `method` and `crop_refused` are what tell them apart.
 */
export type CropSample = {
  box: number
  index: number
  /** Present on a photograph that could not be decoded at all — the run reports the same card
   *  as `unreadable` and sends nothing for it. Every field below is absent with it. */
  unreadable?: string
  /** The card's own game, which decides whether there is a band at all. */
  game?: string
  frame?: [number, number]
  sent?: [number, number]
  rect?: [number, number, number, number] | null
  method?: 'edges' | 'tone' | null
  /** Why a card WAS found and still not cropped to — `identify/images.py:crop_refusal`'s own
   *  sentence, or null. A detected box can be a rectangle inside the card, which crops the
   *  collector number away and reads confidently; the guard refuses those and the run sends
   *  the whole frame instead. Rendered verbatim: it is the pipeline's words, not a code. */
  crop_refused?: string | null
  /** THE BYTES THAT WILL BE SENT, as a data URI — not the stored photograph. The frame draws
   *  these, so the picture changes when the reading does; the 1:1 view is a region of this
   *  same file, which is why the two can never disagree about what is being sent. */
  sent_image?: string
  /** Where the collector number is INSIDE `sent_image`, for the 1:1 view's resting aim. Null
   *  where the registry claims no band for this game — the pointer still reaches every pixel. */
  band_rect?: [number, number, number, number] | null
  /** Its NATIVE pixels, which is the unit D32's frontier table is measured in. */
  band_px?: [number, number] | null
  /** Why there is no band, in the registry's own terms. `pipeline/games.py` holds which bands
   *  a game claims and only `pokemon` claims a number band — the fractions were measured on a
   *  Pokemon card, and a band claimed without that measurement is cut over the wrong pixels. */
  band_absent?: string | null
}

export type CropPreview = {
  scope: RunScope
  capture_dir: string
  crop: boolean
  max_edge: number
  /** Photographs in the scope, so the walk can say what it is one of. */
  total: number
  /** Which card is being shown, already wrapped into range by the server. */
  offset: number
  sample: CropSample
}


/** What this send costs and how many cards it is over. LIFTED SERVER-SIDE, never computed here:
 *  this is the number the confirm is gated on, and arithmetic in TypeScript would be a second
 *  cost model that can disagree with the console printed directly below it. A `null` is a line
 *  the preflight did not print, and the screen draws a blank for it rather than `$0.00`.
 *
 *  `cards` REPLACES `boxes`, WHICH IS D33's ONE NOUN CHANGE. That entry's rule is that the total
 *  is *"the number the operator agrees to spend"*, and boxes are not what is being bought — a
 *  press over 2,535 cards in five drawers reported `5`. It counts the SELECTION; `to_send`
 *  beside it is what will be paid for, and the two differing is the cache doing its job. */
export type RunPreflightTotal = {
  photographs: number | null
  cache_hits: number | null
  to_send: number | null
  estimate_usd: number | null
  cards: number
}

/** ONE QUOTE, where it used to be a list of one or more. D48's rule was that the response shape
 *  must not change with the request, which is exactly why a cart's answer was always a list;
 *  with one selection per press there is one thing being quoted and a one-element list would be
 *  the cart's ghost. */
export type RunPreflight = {
  ok: boolean
  exit_code: number
  selection: RunSelection
  /** What this press is over, in words, composed by the server so the report, the refusals and
   *  this screen cannot describe one press three ways. */
  sentence: string
  /** Which drawer the run WOULD record. Null where the cards are in more than one. */
  scope: RunScope | null
  capture_dirs: string[]
  console: string
  /** A live submission already holding cards in this press, or null (D174). The courtesy half
   *  of the money guard, and the whole of it since the box-level `busy_run` went: a box number
   *  is not something this route takes any more. `sentence` is the server's own refusal text and
   *  is rendered verbatim. */
  claimed: ClaimConflict | null
  total: RunPreflightTotal
}

export type RunStartedRun = {
  run: string
  path: string
  pid: number
  selection: RunSelection
  scope: RunScope | null
  cards: number
  argv: string[]
}

/** A press whose child could not be spawned.
 *
 *  IT IS UNREACHABLE NOW AND THE KEY STAYS. A cart validated every leg before acting on any
 *  precisely because `Popen` could fail on the fourth after three had started — an invoice for
 *  three drawers reported as one failure — so the response named `started` and `failed` side by
 *  side. One child cannot half-start: it spawns or the request refuses, so `failed` is `[]` on
 *  every success. The shape is kept because the screen's partial-send notice is one `length`
 *  check, and a response shape that changed under it would be a reader asking which one it got. */
export type RunStartFailure = {
  code: string
  message: string
  sentence?: string
}

export type RunStarted = {
  started: RunStartedRun[]
  failed: RunStartFailure[]
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

/** `POST /pipeline/runs/<name>/rescue` (D165) — a stranded run's cards, re-addressed to where
 *  they are now.
 *
 *  DELIBERATELY NOT `RunStepResult`'S SHAPE, AND THAT IS THE WHOLE POINT: there is no
 *  `console` field. The owner ruled, 2026-09-13, that raw machine text — stdout, JSON, a CLI
 *  string, a path — is never visible on the front end, not even behind a disclosure, and
 *  `cmd_rescue`'s own report carries backticked `pkmnscan …` invocations and decision numbers.
 *  The server parses that report into the fields below and writes the raw text to a log file
 *  under the run's own directory instead; `log` names it for a person at the machine, and no
 *  screen ever reads it. */
export type RescueResult = {
  ok: boolean
  exit_code: number
  /** True only once a NEW run exists on disk — never merely that `write` was asked for. */
  wrote: boolean
  /** The source run this rescue was asked about. */
  run: string
  /** Why it refused, as a code the sheet's own copy table translates — never the CLI's
   *  sentence. Null when `ok` is true. */
  reason:
    | 'not_stranded'
    | 'no_identifications'
    | 'none_on_shelf'
    | 'spread_across_boxes'
    | 'digest_ambiguous_on_disk'
    | 'digest_twice_in_run'
    | null
  counts: {
    /** Records the source run holds, or null where the line could not be read (a refusal
     *  before the count was printed). */
    records: number | null
    /** Cards found on a shelf and re-addressed — the receipt's headline figure. */
    rebound: number
    /** Records left behind: the cards this run named that have since left the store. */
    not_on_shelf: number
    /** A digest that names two records or two photographs — a question, never a slot. */
    ambiguous: number
  }
  /** Where the rebound cards are now, or null before anything has been found. */
  destination: { box: number; box_name: string | null } | null
  /** An existing rescue already holding these exact cards — `wrote` is false and nothing new
   *  was created. */
  already_rescued: string | null
  /** The new run's name, once `wrote` is true — the sheet's way back in. */
  new_run: string | null
  /** Where the raw report was written, relative to `runs/` — for a person at the machine,
   *  never for a screen to render. */
  log: string
}

/** An uploaded CSV. Uploaded rather than named by path: a screen cannot know what is on
 *  the server's disk, and a route that opened any absolute path a request named would be a
 *  file-read primitive guarded by an origin header. */
/** `modified` is `File.lastModified` — milliseconds since the epoch, the file's own time — and
 *  the server sets the stored copy's mtime from it (`_store_upload`), because that mtime is
 *  when the export's `Total Quantity` was read and the store arbitrates `live` by that time
 *  (D87 amended). Optional: a caller without a `File` sends none and the write time stands. */
export type CsvUpload = { name: string; content: string; modified?: number }

/** What `POST /pipeline/runs/<name>/export` fetched, in the terms the operator filters the
 *  portal in (D64). Free: it downloads the owner's own Filtered Export and spends nothing.
 *
 *  `file` is the name the join is then handed. It is a name and not the bytes: the server
 *  already holds them, and sending a megabyte back through the browser to arrive at them is
 *  not a step. */
/** The real set names for a game, for the capture screen's hint field (D65). Always answers,
 *  even when it could not be fetched: `sets` is empty and `reason` says why, because the rig
 *  must not stop for an autocomplete. */
export type TcgSets = {
  game: string
  sets: { name: string; id: string }[]
  aliases?: Record<string, string>
  reason: string | null
  /** The transport's own remedial sentence, and the FLOOR under an unlabelled `reason` rather
   *  than what the operator normally reads. `server/tcg_export.py` writes a sentence for each
   *  of its refusals — which `.env` value to replace, which knob to set — and this route was
   *  the one of four that used to keep the code and discard it. The screen still writes its
   *  own copy in the operator's terms (`hintReason`); this is what a code that map does not
   *  yet name falls back to, in place of the raw string it used to print. Null on success and
   *  on `no_category`, which is a fact about `pipeline/games.py` and not about the portal. */
  message: string | null
}

export type ExportFetched = {
  ok: boolean
  run: string
  file: string
  bytes: number
  rows: number
  skus: number
  games: string[]
  sets: string[]
  conditions: string[]
  product_lines: string[]
  /** What the last join used, per game this file answers for, beside what arrived. Always
   *  present and `{}` on a run's first fetch; information only — nothing refuses on it. */
  previous: Record<string, { file: string; rows: number; skus: number }>
  source: string
  /** What was ASKED FOR, beside what arrived (D65). The scope is derived from the box's own
   *  capture claims — its game, and the set hints the operator set — so this is the half they
   *  can correct. `widened` is true where no hint resolved and the whole category was taken,
   *  which is slower and always correct; `unresolved_hints` names the hints that did not
   *  match a TCGplayer set, which is the thing worth seeing. */
  asked: ExportAsked
  /** Whether this answer came off a file already on disk rather than off the wire
   *  (D166). The export is a property of the GAME now, kept once in
   *  `inventory/.exports/<game>/`, so a second run over the same game opens no socket at all.
   *
   *  THIS IS THE ONE FIGURE THE REST OF THE RECEIPT CANNOT IMPLY. A reuse and a fetch answer
   *  with the same file, rows, SKUs and sets — the only difference is whether TCGplayer was
   *  asked — so it is said rather than inferred. `age_s` is how old the reading is, and zero
   *  for anything this press observed. */
  reused: boolean
  age_s: number
  /** The directory the game's exports live in. Never inside the run any more, so a client
   *  that composed a path out of the run's name would be wrong in silence. */
  store: string
  /** What this scope weighs against the transport's ceiling (D65/D76), or null where nothing
   *  covering has been measured yet. */
  width: ExportWidth | null
}

/** WHAT A FETCH AT THIS SCOPE WEIGHS, AGAINST THE CEILING IT WOULD BE REFUSED AT (D65/D76).
 *
 *  MEASURED, NEVER ESTIMATED — the only thing that can size an export is an export, so this is
 *  null until the game has been fetched once at a scope that covers what is being asked for.
 *
 *  WHY IT IS ON THE WIRE AT ALL. `server/tcg_export.py:MAX_BYTES` is 32 MB and the fetch
 *  refuses past it. Measured 2026-09-12, the whole Pokemon category is 32,629,598 B —
 *  **97.24% of that cap**, 903 KB of headroom — against 238,482 B for the one set the owner's
 *  543 Pokemon cards all name. So a D76 widening is a 137x change in what comes back and lands
 *  two per cent short of a hard refusal, which is not a thing an operator should discover by
 *  pressing. `widened` says whether the figure is the WIDE one: a narrow reading drawn beside a
 *  widened scope is a measurement of a different request, and saying so is the difference
 *  between a preview and a reassurance. */
export type ExportWidth = {
  bytes: number
  max_bytes: number
  headroom: number
  /** `bytes / max_bytes`, to four places. */
  of_max: number
  near_cap: boolean
  measured: string | null
  from: string
  widened: boolean
}

/** WHAT THE FETCH ASKED TCGPLAYER FOR, AND WHICH OF THE THREE VOICES CHOSE IT (D76).
 *
 *  `widened` is the D65 field and still says the same thing `scope === 'category'` says; what
 *  D76 adds beside it is WHY, because "the whole category" was never the interesting half. A
 *  set filter now needs the box to be unanimous — every card hinted and every hint resolved —
 *  so `reason` is the field that tells an operator whether their box, their game's rule or
 *  their own tick decided, and `hinted`/`cards` is the evidence for the first of those. */
export type ExportAsked = {
  game: string
  category_id: number
  hints: string[]
  set_ids: number[]
  unresolved_hints: string[]
  sets: string[]
  widened: boolean
  scope: 'category' | 'sets'
  /** The game's own rule from `pipeline/games.py`, before any override. */
  policy: 'category' | 'sets'
  chosen_by: 'operator' | 'policy' | 'cards'
  reason:
    | 'game_policy'
    | 'operator_asked'
    | 'no_hints'
    | 'partial_hints'
    | 'unresolved_hints'
    | 'no_hints_resolved'
    | null
  cards: number
  hinted: number
  unhinted: number
}

/** `GET /pipeline/runs/<name>/scope` — the lever's current position, before it is pulled.
 *
 *  NAMED `ExportScope` AND NOT `RunScope`, WHICH IS TAKEN: `RunScope` is the BOX a run was
 *  over — D39's whole-box-or-ticked-selection — and this is the CATALOG the fetch asks for.
 *  Two different scopes, and collapsing their names would be the kind of near-miss that reads
 *  correct at every call site until one of them is wrong.
 *
 *  DEGRADES THE WAY THE CAPTURE SCREEN'S SET LIST DOES. Resolving a hint to a set id needs the
 *  portal, so `asked` is null with `reason` naming the refusal whenever the cookie is stale or
 *  the network is gone — and every count in `games` is local and still draws. A mixed-game run
 *  is a LIST here rather than the `game_required` refusal `POST .../export` makes, because a
 *  screen that must ask which game cannot draw the picker from a route that refuses first. */
export type ExportScope = {
  run: string
  games: {
    game: string
    display: string
    category_id: number
    cards: number
    hinted: number
    unhinted: number
    hints: string[]
    policy: 'category' | 'sets'
  }[]
  scopes: ('category' | 'sets')[]
  asked: ExportAsked | null
  reason: string | null
  message: string | null
  /** What the press would weigh, drawn before it (D65/D76). Null until this game has been
   *  fetched once at a covering scope — and answerable at all only because the exports are
   *  per-game now: per-run copies gave every drawer its own unrelated sample. */
  width: ExportWidth | null
  /** The file a press would answer from without asking TCGplayer, if there is one
   *  (D166). Null means the press opens a socket. */
  reusable: { file: string; age_s: number; window_s: number } | null
}

/** One code on the ledger, as `GET /codes` serves it (C3, C8, C11).
 *
 *  THE CODE STRING IS HERE IN THE CLEAR, and that is correct rather than an oversight. The
 *  server binds loopback, the store is the owner's own machine, and the whole job of the
 *  Codes screen is that the owner can read a code and paste it to a buyer. The repo's opsec
 *  rules govern what reaches a COMMIT — a tracked file, a screenshot, a listing — not what
 *  reaches the owner's own browser. `make screenshot` is the one place those two meet, and
 *  the Codes screen is deliberately absent from `scripts/views.txt` for that reason.
 */
export type CodeEntry = {
  code: string
  /** `held` | `reserved` | `delivered` | `dead`. A CODE's state, never a card's — a card can
   *  be destroyed under D24 while its code is still held and perfectly saleable. */
  state: string
  product: string | null
  product_display: string | null
  premium: boolean
  set_hint: string | null
  /** Where the photograph is. Kept after the card is destroyed, because it becomes the only
   *  surviving evidence of what was printed — which is C8's whole dispute flow. */
  box: number | null
  index: number | null
  photo: string | null
  source: string | null
  scanned_at: string | null
  state_at: string | null
  order_id: string | null
  buyer: string | null
  delivered_at: string | null
  dead_reason: string | null
  /** Whether the code matches the printed 3-4-3-3 layout. REPORTED, never enforced: a payload
   *  that survived the QR's own error correction is likelier to be an unfamiliar print run
   *  than a misread. */
  well_formed: boolean
  /** Non-empty means this code was read at a SECOND position. Either one card photographed
   *  twice, or two cards bearing one code — and if the second, one of them is worth nothing. */
  duplicate_positions: { box: number | null; index: number | null; photo: string | null }[]
}

export type CodeLedger = {
  counts: Record<string, number>
  total: number
  /** C11's two lanes, plus the codes that can enter neither because nobody said what they are. */
  lanes: { bulk: number; premium: number; unclaimed: number }
  by_product: {
    product: string
    display: string
    premium: boolean
    /** `premium` | `bulk` | `none`. The lane that would ACTUALLY take this row's codes, so
     *  the tier table cannot say something the export lane would contradict. An unclaimed
     *  code answers `none`. */
    lane: string
    count: number
  }[]
  duplicates: CodeEntry[]
  entries: CodeEntry[]
  products: { key: string; display: string; premium: boolean; redeem_limit: number }[]
}

export type CodeScanResult = {
  box: number
  photographs: number
  code_cards: number
  decoded: number
  unread: string[]
  malformed: string[]
  preview: boolean
  would?: Record<string, number>
  counts?: Record<string, number>
  stamped?: number
  on_file?: number
}

export type CodeExportResult = {
  lane: string
  product: string | null
  available: number
  count: number
  committed: boolean
  note: string
  sample?: string[]
  codes?: string[]
  order_id?: string
  buyer?: string | null
}


/** One built lot's receipt, as `GET /codes/lots` serves it. NEVER carries the codes —
 *  the manifest is a file on disk and the screen links to it rather than rendering a
 *  thousand bearer instruments into a page and its devtools network tab. */
export type LotReceipt = {
  lot_id: string
  scope: string
  delivery: string
  venue: string
  box: number | null
  count: number
  by_product: { product: string; display: string; premium: boolean; count: number }[]
  sets: string[]
  built_at: string
}

/** What `POST /codes/lots` answers — a plan when `built` is false, a built lot when true. */
export type LotResult = {
  count: number
  box: number | null
  scope: string
  delivery: string
  venue: string
  built: boolean
  premium_in_lot: number
  by_product: { product: string; display: string; premium: boolean; count: number }[]
  sets: { set: string; count: number }[]
  note: string
  sample?: string[]
  lot_id?: string
  /** name -> absolute path. The manifest is here and deliberately not inline. */
  files?: Record<string, string>
  listing?: string
  packing?: string
}
/* ============================================================================ THE ORDERS
 *
 * D63's ledger on the wire, and D69's screen reading it. Field names are the SERVER'S, in
 * the server's own case, for the reason every block above this one is: a rename here is a
 * second spelling of one contract, and the renaming would have to happen somewhere anyway.
 * Nothing in this file is validated at run time — `server.ts` casts, and its own comment
 * argues why.
 */

/** The six words `pipeline/orders.py:LINE_REASONS` enumerates, and the ONE closed vocabulary
 *  on this screen. `app/src/orderReasons.ts` carries the array, the labels and the remedies,
 *  and `scripts/docs-audit.py:check_order_reasons` reconciles that array against the Python
 *  tuple in both directions — the half the compiler cannot do, because TypeScript cannot
 *  import a Python tuple. */
export type OrderLineReason =
  | 'resolved'
  | 'short'
  | 'no_copies_on_hand'
  | 'sku_unknown'
  | 'sku_unseen'
  | 'not_a_single'

/** One line as the FEED said it, stored verbatim. Everything but `sku` and `quantity` is
 *  nullable because a marketplace may say nothing about it, and `store/orders.py` stores
 *  what it was told rather than what it would prefer. `unit_price` is a STRING for
 *  `ShippingRow.value`'s reason one block down: money crosses this wire as text. */
export type OrderLineWire = {
  sku: string
  quantity: number
  name: string | null
  number: string | null
  printing: string | null
  condition: string | null
  rarity: string | null
  unit_price: string | null
  kind: string | null
}

/** What WE have recorded against one line — the ledger's own half, beside the feed's.
 *
 *  `recorded` IS A COUNT AND `copies` ARE CAPTURE IDS. Neither is ever a position: a
 *  position-keyed record is the thing no renumber path remaps (D58 moves the slot a person
 *  counts to, D10 ruling 1 slides every higher index down), and a `capture_id` is the one
 *  identity that survives both. A screen wanting a place asks the resolution for it. */
export type OrderLineProgress = {
  sku: string
  wanted: number
  recorded: number
  outstanding: number
  /** Normally zero, and never created by a pull. A later ingest that REDUCES a quantity
   *  underneath a legitimate pull is what makes it non-zero. */
  over: number
  copies: string[]
  /** How many of `recorded` were closed with NO card behind them — `POST /orders/fill`, D113.
   *  `recorded` is the whole count and this is the part of it nothing in the store can
   *  corroborate, so a screen drawing `recorded` alone cannot tell a pulled line from a
   *  hand-filled one. `reason` is why that was honest: `sealed` or `off_system`. */
  by_hand: number
  reason: string | null
  /** The OPERATOR's claim about what this line is, or null. Never the feed's — that rides on
   *  `OrderLineWire.kind`, and the server prefers the feed wherever it said anything at all.
   *  It lives in the fulfilment map because `ingest` replaces the order record wholesale. */
  declared_kind: OrderLineKind | null
  /** When this line was stood down, and why — `POST /orders/close`, D113. A stood-down line
   *  needs nothing further from this store EVEN WHERE `outstanding` is positive: no copy is
   *  claimed to have gone, it is simply no longer ours to account for. Null is the normal
   *  state. `closed_reason` is `shipped_elsewhere` or `not_shipping`. */
  closed_at: string | null
  closed_reason: OrderCloseReason | null
  at: string | null
}

/** What a line IS, for the resolver's routing. `single` is the default the server applies to
 *  a feed that said nothing, which the TCGplayer feed always does. */
export type OrderLineKind = 'single' | 'sealed' | 'accessory'

/** Why a hand-fill was honest. `sealed` — not a single, picked off a shelf; `off_system` — a
 *  single this store never photographed; `sold_separately` — the copy was here and left through
 *  `#/inventory`'s sale rather than the order pull, so nothing counted it against the order.
 *  All three say a copy WENT, which is what separates them from `OrderCloseReason`. */
export type OrderFillReason = 'sealed' | 'off_system' | 'sold_separately'

/** Why a line was stood down. NEITHER CLAIMS A COPY LEFT, which is what separates these from
 *  `OrderFillReason`: `shipped_elsewhere` is an order that went out without this store
 *  tracking the copies, `not_shipping` is one that will never go — a refund, a cancellation. */
export type OrderCloseReason = 'shipped_elsewhere' | 'not_shipping'

/** One order as the feed said it, with our progress beside it.
 *
 *  `status` IS THE FEED'S OWN WORD, verbatim and unvalidated — `store/orders.py` refuses to
 *  hold a closed vocabulary there, because a marketplace that learns a new word must not be
 *  refused at the door. So NOTHING MAY BRANCH ON IT. `open` is the LEDGER'S answer,
 *  computed by `Ledger.unfulfilled` from its own two maps, and it is the one to branch on. */
export type OrderRow = {
  /** `source:number`, split on the FIRST colon — a number may legally contain one. */
  key: string
  source: string
  number: string
  placed_at: string | null
  status: string | null
  first_seen: string
  changed_at: string | null
  /** The buyer's display name, verbatim off the feed — `D193`, which
   *  amends D69. Nothing else about the person: no address, no email, no payment. Feed
   *  content, so it can be `null` where a paste never carried one and a later fetch has not
   *  named it either. */
  buyer: string | null
  wanted: number
  recorded: number
  open: boolean
  /** The MARKETPLACE's own word that this order is finished — `server/capture_server.py:
   *  _order_row` emits `order_store.is_terminal_status(record.status)` unconditionally, never
   *  the `status` string itself (D114). Distinct from `open`, which is the LEDGER's answer to
   *  "does this still owe copies": a `terminal` order can still owe copies when TCGplayer
   *  reports it shipped before every line was pulled here, which is exactly the case `open`
   *  alone cannot tell a screen about. */
  terminal: boolean
  lines: OrderLineWire[]
  progress: OrderLineProgress[]
}

/** One physical copy the resolver offered, AS IT STANDS RIGHT NOW.
 *
 *  TRUE OF THE SNAPSHOT IT WAS COMPUTED FROM AND OF NO OTHER, and it is never stored (D36).
 *  `box` and `index` are the store key at the instant `GET /orders` read it; `place` is
 *  composed by the server's one renderer over `pipeline/join.py:Position`, which is the only
 *  label formula in this repo. A second one on this screen is the failure this repo has
 *  already recorded three times.
 *
 *  `held_by` IS THAT REQUEST'S OWN REVERSE INDEX, keyed by `capture_id`, and is never
 *  stored either. It says this exact card is already recorded against a line, so the screen
 *  draws it as spoken for rather than offering it to a second order. */
export type PickRow = {
  box: number
  index: number
  capture_id: string | null
  source: 'card' | 'run'
  run: string | null
  card_name: string | null
  card_number: string | null
  condition: string | null
  /** Null where the snapshot holds no card at that key — a copy the resolver named and a
   *  delete took out from under it between one render and the next. */
  state: string | null
  held_by: { order: string; sku: string } | null
  place: Place
}

/** One resolved line: why, the breakdown behind it, and the copies it found.
 *
 *  `fulfilled` IS `len(picks)` — a count DERIVED from the list beside it and never stored.
 *  It is not `OrderLineProgress.recorded`, which is what the ledger says has actually been
 *  pulled; this is what the resolver could offer right now.
 *
 *  `order_key` travels beside `order` because the resolver keys on the NUMBER alone and the
 *  store keys on `source:number`. A number is unique to a marketplace and not across two. */
export type ResolvedLine = {
  order: string
  order_key: string
  sku: string
  reason: OrderLineReason
  wanted: number
  /** What the ledger still owes on this line, and what the resolver was asked to find.
   *  `wanted` is the buyer's number; `wanted - owed` is what has been recorded as pulled. */
  owed: number
  fulfilled: number
  outstanding: number
  on_hand: number
  sold: number
  retired: number
  pooled: number
  line: OrderLineWire
  picks: PickRow[]
}

/** One order's resolution. NO POSTAGE LANE HERE, deliberately: this screen answers "which
 *  copies, and where", and which envelope an order ships in is D61's ruling and `#/shipping`'s
 *  answer, computed from TCGplayer's own shipping export rather than from the ledger. */
export type ResolvedOrder = {
  key: string
  number: string
  complete: boolean
  outstanding: number
  lines: ResolvedLine[]
}

/** `POST /orders/walk-plan` — the ticked-order walk as the fewest drawers to open
 *  (`docs/specs/order-walk-plan.md` §7). `pipeline/walkplan.py:plan` over one snapshot; NOT
 *  STORED (D36), and a plan re-pressed a minute later over a changed store can name
 *  different cards. */
export type WalkPlanRef = { key: string; number: string; buyer: string | null; owed: number }

/** One physical copy of a take's card, anywhere in the store — REBUILT 2026-09-19 (`docs/
 *  specs/order-walk-plan.md` §8, "The stop, rebuilt"). The flat fields the first build carried
 *  (`box`, `index`, `slot`, `card`, `label`, `neighbors`, `box_total`,
 *  `fraction`) are GONE — every one of them now lives inside `place`, which is the full block
 *  `_Places.of` composes, the same dict `do_search` sends. The client composes NOTHING from
 *  the stop any more; the old `neighborShim`/`placeOf` reconstruction is deleted with them. */
export type WalkPlanCopy = {
  /** `SearchCopy.key`, `"<box>/<index>"`. The identity a press sends and a refresh names. */
  key: string
  /** `SearchCopy.state`. */
  state: string
  has_photo: boolean
  capture_id: string | null
  /** The card's own name (D172, D183) — what lets this screen address the photograph the
   *  way `#/inventory` and `#/fulfillment` do, rather than by `photoUrl(box, index)`. Null
   *  for a copy recorded before the field existed. */
  cid: string | null
  /** The full place, exactly what `SearchCopy.place` carries. Includes `box_name`, `section`,
   *  `section_name`, `section_start`, `section_end`, `box_total`, `fraction`,
   *  `neighbors`, `label`, `slot`, `card`. */
  place: Place
  /** True when this copy stands at THIS stop (same box and section) — the solver's reach. */
  here: boolean
}

/** One SKU at one stop: how many to take, and EVERY on-hand copy of this SKU in the whole
 *  store (D93, D97, D212 — widened 2026-09-19, "every copy of the card in the store is drawn,
 *  this drawer's first, all pressable"), not only this stop's own picks. Capping the list at
 *  `wanted`, or at this stop's own copies, would put an address back on a fungible copy.
 *
 *  `copies` ORDER IS LOAD-BEARING AND THE CLIENT MUST NOT RE-SORT: (1) copies with `here: true`,
 *  in the solver's own order (densest first, as before); (2) every other copy, ascending
 *  (box, index). D212: all of them are pressable. D93: none is hidden. */
export type WalkPlanTake = {
  sku: string
  /** The identified card's own name, off its first ranked copy — null where the store holds
   *  no identification for it yet. */
  name: string | null
  /** `198/219`, `pipeline/join.py:display_number` — null where the card has no number. */
  number_display: string | null
  /** For the take header, nullable exactly as `SearchGroup` carries them. */
  set: string | null
  rarity: string | null
  condition: string | null
  wanted: number
  for: WalkPlanRef[]
  copies: WalkPlanCopy[]
  /** The same three fields `SearchGroup` carries for this SKU, off the SAME `Listing` read
   *  `condition`'s own fallback already makes server-side — so a caller synthesising a
   *  `SearchGroup` from a take (`Fulfillment.tsx`'s Owed section) can draw the honest
   *  live-count sentence rather than a fabricated zero. Zeros and null, never absent, for a
   *  SKU with no listing record yet — the same shape `do_search` sends. Optional so a fixture
   *  built before this field existed still type-checks; a caller reading it falls back to the
   *  same zero shape an absent listing sends. */
  listed?: { pushed: number; staged: number; live: number }
  sold_here?: number
  live_as_of?: string | null
}

/** One reach: a drawer to open, and what to take out of it. A pooled stop (D24) is one
 *  synthetic stop per game, cost 1, always last in the walk order — never a section, and
 *  `box`/`section`/`box_name`/`section_name`/`span` are all null on it. */
export type WalkPlanStop = {
  /** `box/<n>/section/<n>`, or `game/<key>` for a pooled stop. */
  key: string
  box: number | null
  box_name: string | null
  section: number | null
  section_name: string | null
  pooled: boolean
  game: string | null
  game_display: string | null
  /** The walk order, ascending box then section, pooled stops last. 1-based. */
  order: number
  /** This stop's section bounds, in D58's slot space — null for a pooled stop. */
  span: { start: number; end: number | null } | null
  /** THE BOX'S OWN TOTAL, so the stop's span chip can read `#242–284 of 987` rather than the
   *  bare span (§8's 2026-09-19 ruling). Optional and null-shaped by omission: an older server
   *  sends none, and the client draws the honest span numbers alone rather than a fabricated
   *  proportion. Null for a pooled stop, same as `span`. */
  box_total?: number | null
  takes: WalkPlanTake[]
}

/** One SKU the store cannot fill at all — reported rather than made infeasible (§5): 23 of
 *  the owner's 59 wanted SKUs are in exactly this state. NOT A STOP and never drawn as one. */
export type WalkPlanShort = {
  sku: string
  /** The feed's own words (`OrderLine.name`) off the first order still owing it — a shortfall
   *  SKU has no guaranteed on-hand copy to identify it by by D172's own rule. */
  name: string | null
  wanted: number
  on_hand: number
  short: number
  for: WalkPlanRef[]
}

/** The plan's own arithmetic, including the two figures that say how hard it was to compute.
 *  `exact: false` is reachable — the solver's wall-clock budget ran out and the greedy
 *  incumbent came back flagged rather than silently passed off as optimal. */
export type WalkPlanCounts = {
  stops: number
  boxes: number
  copies: number
  sections_considered: number
  sections_candidate: number
  exact: boolean
  solve_ms: number
}

export type WalkPlan = {
  cost: string
  stops: WalkPlanStop[]
  shortfall: WalkPlanShort[]
  counts: WalkPlanCounts
}

/** `POST /orders/fill` in both directions — D113. Nothing is sold and no card is touched;
 *  there is no card. `moved` is how many copies this press recorded or reversed. */
export type OrderFillResult = {
  undone: boolean
  order_key: string
  sku: string
  moved: number
  recorded: number
  by_hand: number
  outstanding: number
  reason: string | null
}

/** `POST /orders/line-kind` — the operator's claim, echoed back as stored. Null means the
 *  claim was withdrawn and the feed's own word (or its silence) stands again. */
export type OrderLineKindResult = {
  order_key: string
  sku: string
  kind: OrderLineKind | null
}

/** `POST /orders/close` in both directions — D113. A bulk press: `orders` is how many were
 *  named, `moved` how many actually changed, `lines` how many lines under them. `still_open`
 *  is the ledger's own count AFTER the write, which is what the press was for. */
export type OrderCloseResult = {
  undone: boolean
  /** Which scope the press used. `orders` stood every line of each named order down; `lines`
   *  stood exactly the named lines down and left their siblings alone. */
  scope: 'orders' | 'lines'
  orders: number
  moved: number
  lines: number
  reason: OrderCloseReason | null
  still_open: number
}

/** `POST /orders/reconcile-backlog` preview (`{preview: true}`) — `writes_nothing`, exactly as
 *  `POST /orders/fetch`'s own preview carries it. `breakdown` is grouped by the feed's own
 *  status string, largest first — the whole safety this route offers, since the predicate
 *  itself cannot tell a two-year-old order from a live one sharing its cutoff and its
 *  zero-recorded shape. */
export type ReconcileBacklogPreview = {
  cutoff: string
  total: number
  breakdown: { status: string | null; count: number }[]
  writes_nothing: true
}

/** `POST /orders/reconcile-backlog` press. `closed` is exactly what `reopenOrders` takes, so
 *  the receipt's undo needs no new mechanism. `reason` is always `shipped_elsewhere` — this
 *  route never asks for one. */
export type ReconcileBacklogResult = {
  cutoff: string
  orders: number
  moved: number
  lines: number
  closed: { source: string; number: string }[]
  reason: OrderCloseReason
  still_open: number
}

/** `GET /orders`, out of ONE store snapshot so the list and the resolution cannot disagree.
 *
 *  Only `Ledger.unfulfilled()` orders are resolved, so `resolution.orders` is a subset of
 *  `orders`. `counts` carries EVERY reason including the zeros — reporting only what fired
 *  would make "nothing was short" and "nothing was checked" the same payload — and
 *  `sku_unknown` is structurally UNREACHABLE from this route and always draws a zero,
 *  because it fires only when a run's paperwork names a SKU no card wears and this route
 *  passes no paperwork. That zero is a limit of the route, not a fact about the store. */
export type OrdersPayload = {
  summary: string
  orders: OrderRow[]
  resolution: { orders: ResolvedOrder[]; counts: Record<OrderLineReason, number> }
}

/** `POST /orders/picks` — the second tier `GET /orders` names in its own comment.
 *
 *  `OrdersPayload.resolution.orders[].lines[].picks` IS ALWAYS `[]` NOW (2026-09-16):
 *  decorating a real `place` for every candidate copy of every unfulfilled order was 52% of
 *  `GET /orders`'s wall time, for orders no buyer had opened. Every other field on a line —
 *  `reason`, `on_hand`, `sold`, `retired`, `pooled`, `wanted`, `owed`, `fulfilled`,
 *  `outstanding` — is unchanged and still answers on `GET /orders` alone, because the buyer
 *  list, its reason chips, its status pills and `passesHideUnknown` read none of `picks`.
 *
 *  This route answers the SAME shape (`ResolvedOrder[]`), with real `picks`, for exactly the
 *  order keys asked about — the order or buyer being opened, or every order in a walk pass
 *  in one batch. A key the ledger no longer holds is simply absent from `orders`, not an
 *  error. */
export type OrderPicksPayload = {
  orders: ResolvedOrder[]
}

/** THE PROJECTION, and NOTHING MAY BE ADDED TO IT BEYOND WHAT IS ARGUED HERE.
 *
 *  These two types are the whole of what may leave this browser about a purchase.
 *  `D193` (amending D69) moved this boundary by exactly one word: the
 *  buyer's DISPLAY NAME may cross it. Nothing else about the person does — no address, no
 *  city, no postcode, no email, no payment, no transaction id — and the mechanism that holds
 *  that line is unchanged: `app/src/orderPaste.ts` mints these from whatever was pasted and
 *  NAMES what it dropped; `server/capture_server.py`'s three allowlist tuples are the
 *  backstop, so an unprojected paste refuses BY NAME rather than being stored with those
 *  fields quietly trimmed. A field added here is a field that leaves the machine, and it has
 *  to be argued for in a decision entry before it is typed here. */
export type OrderIngestLine = {
  sku: string
  quantity: number
  name?: string | null
  number?: string | null
  printing?: string | null
  condition?: string | null
  rarity?: string | null
  unit_price?: string | null
  kind?: string | null
}

export type OrderIngestOrder = {
  source: string
  number: string
  placed_at?: string | null
  status?: string | null
  /** The buyer's display name, verbatim off the feed or the console paste — the one
   *  person-shaped field this projection carries (`D193`). `undefined`
   *  where the source said nothing at all (so `store/orders.py:Ledger.ingest` keeps whatever
   *  name it already had rather than erasing it); `null` where the feed explicitly said none. */
  buyer?: string | null
  lines: OrderIngestLine[]
}

/** One order the ledger already knows, matched by a fetch that named it rather than detailed
 *  it (`POST /orders/fetch`'s `names[]`) or by a direct `POST /orders/names` call. Carries
 *  enough to find the record — `source` and `number`, never the ledger's opaque `key` — and
 *  the name to write onto it. Nothing else: this is the SAME one-field boundary as
 *  `OrderIngestOrder.buyer`, spelled out as its own type because `/orders/names` writes
 *  nothing else about the order. */
export type OrderName = {
  source: string
  number: string
  buyer: string
}

/** What `POST /orders/names` did — `store/orders.py:Ledger.name_buyer` run once per entry.
 *  `named` actually changed a stored name; `unchanged` already carried that exact spelling;
 *  `unknown` named an order this ledger has never ingested, so there was nothing to write
 *  onto. `total` is `named + unchanged + unknown`, always. This route is free and re-runnable
 *  — it never fetches and never spends the identify budget — and it exists so a names-only
 *  backfill (every summary a fetch already read) never has to pay for a detail call it does
 *  not otherwise need. */
export type NamesResult = {
  named: number
  unchanged: number
  unknown: number
  total: number
  summary: string
}

/** What `POST /orders/ingest` did. `wrote_nothing` is the honest answer to "did that work"
 *  for a second identical paste: `Ledger.ingest` carries `first_seen` across and stamps
 *  `changed_at` only where something moved, so the second press rewrites nothing at all. */
export type IngestResult = {
  added: number
  changed: number
  unchanged: number
  total: number
  wrote_nothing: boolean
  summary: string
  keys: string[]
}

/** What `POST /orders/fetch {preview: true}` answered (D91): the window counted by the status
 *  STRING TCGplayer gave each order, verbatim — no vocabulary lives on either side of this wire —
 *  and, beside each, how many of them the ledger already holds at that status. Nothing was
 *  detailed and nothing was written. */
export type OrdersPreview = {
  range: string
  total: number
  by_status: { status: string; count: number; known: number }[]
  writes_nothing: true
}

/** What `POST /orders/fetch {statuses: [...]}` or `{all_statuses: true}` answered. `orders`
 *  is EXACTLY the body `POST /orders/ingest` accepts and is the only part sent on —
 *  `ingestOrders(found.orders)` — so the counts beside it reach no allowlist; they are what
 *  the paste note says about the press. `remaining` is what the transport's detail cap left
 *  for the next press (D91): seen and counted, never dropped without a trace.
 *
 *  `names` IS A SEPARATE, CHEAPER ANSWER: every order this press matched that was SKIPPED as
 *  already known (so it never got a detail call and is not in `orders`) but whose search-page
 *  summary carried a buyer the ledger does not yet have on file, or spells differently
 *  (`D193`). `nameOrders` in `app/src/server.ts` is the one place
 *  this array is sent on, to `POST /orders/names` — a names-only backfill this way details
 *  nothing and spends nothing. Empty in the steady state: the second identical press over an
 *  already-named ledger returns no names at all. */
export type OrdersFetched = {
  orders: OrderIngestOrder[]
  matched: number
  skipped_known: number
  detailed: number
  remaining: number
  names: OrderName[]
}

/** One copy coming out of a box. All three are required in both directions.
 *
 *  `index` IS THE STORED INDEX (D58) — the `/inventory/<box>/<index>` path and the
 *  `<index>.jpg` the photograph is named after — and never the slot a person counts to.
 *  `capture_id` is the aim check on the way in (a mid-box delete or a re-shoot changes which
 *  physical card sits at a slot) and the WHOLE of the lookup on the way back. */
export type PullTarget = { box: number; index: number; capture_id: string }

/** A position the caller is still DRAWING and is not pulling — `POST /orders/pull`'s own
 *  `refresh` list. No `capture_id`: nothing is aimed at and nothing is written, so an aim
 *  check on a card nobody is touching would only refuse a re-description over a re-shoot. */
export type PullRefresh = { box: number; index: number }

/** What a pull or its undo did.
 *
 *  `places` ARE THE LABELS AS THEY WERE BEFORE THE WRITE, one per target in request order.
 *  That is the receipt to draw, and `sales[i].card.place.label` is not: a sale moves the
 *  box's occupancy (D58), so the card is departed by the time the answer is composed and
 *  its label reads `Box 3 · departed`. */
export type PullResult = {
  undone: boolean
  order_key: string
  sku: string
  newly: number
  recorded: number
  outstanding: number
  places: Place[]
  /** THE OTHER DIRECTION IN TIME, AND IT IS NOT A SECOND RECEIPT. One `Place` for each
   *  `refresh` position the press actually touched the box of, composed AFTER the write.
   *  The write is what made those cards' description wrong — a pull renumbers everything
   *  behind it in the drawer (D58) — so this is how a screen still holding them says where
   *  they sit now. Empty when nothing asked, and a position in an untouched box is left out
   *  rather than answered (`docs/specs/order-walk-plan.md` §8's ruling of 2026-09-19).
   *  Optional because an older server omits it. */
  refreshed?: Place[]
  sales: SaleResult[]
}

/* ========================================================================== THE SHIPPING
 *
 * D61's three lanes, read off TCGplayer's own `Orders → Export Shipping` file. The batch
 * lives in the capture server's MEMORY for half an hour and touches no disk (D61 forbids
 * persisting buyer PII), so every one of these is true of one process and one upload.
 */

export type ShippingLane = 'envelope' | 'parcel' | 'unjudged'

export type ShippingReason =
  | 'value_at_threshold'
  | 'non_card_signal'
  | 'cards_only'
  | 'no_weight_data'
  | 'no_value_data'
  | 'sub_single_weight'

/** One order as the shipping screen draws it, and EVERY FIELD THIS SCREEN IS ALLOWED TO
 *  KNOW. No name, no address, no city, no postcode — and their absence is the design rather
 *  than an omission to fill in later. The buyer's details cross this wire exactly once, as
 *  the CSV download, which is the one thing that has to carry them.
 *
 *  `value` IS A STRING AND NEVER A NUMBER. It is a `Decimal` on the server and money read
 *  through a float is money that rounds.
 *
 *  `weight_per_item_oz` IS A RENDERING TO FOUR PLACES AND IS NEVER COMPARED CLIENT-SIDE.
 *  The ratio is a `Fraction` on the server; a float pass over that column MOVED the lane
 *  counts, which is the measurement this sentence exists to carry.
 *
 *  `certain` is carried rather than inferred from `reason` here, because
 *  `pipeline/shipping.py:Routing` owns that distinction and a second copy of the rule in
 *  TypeScript is the second-renderer failure this repo has recorded. `item_count` is null
 *  and NEVER 0 for an unparseable cell — absent stays distinguishable from small all the
 *  way to the screen, which is the whole of that module's abstention. */
export type ShippingRow = {
  order: string
  lane: ShippingLane
  reason: ShippingReason
  certain: boolean
  value: string | null
  weight_per_item_oz: string | null
  item_count: number | null
  /** The seam for the deferred pick-location route, and null until it exists. */
  stamp: string | null
}

export type ShippingFile = { name: string; bytes: number }

/** The other half of that seam: null until `POST /shipping/batches/<batch>/stamps` is built,
 *  and typed now so the later route changes no type and no component. */
export type ShippingStamps = {
  ledger_orders: number
  matched: number
  stamped: number
  unstamped: number
}

/** One uploaded export, routed. `batch` is 128 random bits because the file route is a GET
 *  and therefore not behind the origin gate; `expires_in` is seconds and is a TTL rather
 *  than a countdown the screen has to keep. */
export type ShippingBatch = {
  batch: string
  name: string
  expires_in: number
  shipments: number
  rows: ShippingRow[]
  /** Straight from `shipping.lane_counts` / `shipping.reason_counts`, WHICH SEED EVERY KEY
   *  INCLUDING THE ZEROS. Do not filter them: "nothing was unjudged" and "nothing was
   *  checked" must not be the same payload. */
  lane_counts: Record<ShippingLane, number>
  reason_counts: Record<ShippingReason, number>
  parcel_count: number
  file: ShippingFile
  stamps: ShippingStamps | null
}

export type ShippingForgotten = { batch: string; forgotten: boolean }

/* ------------------------------------------------- the stale-listing markdown (D100) */

/** What `POST /pipeline/markdowns` is asked. Every field optional: the defaults live in
 *  `cli/__main__.py` and are the same whichever door the command is reached through.
 *
 *  `percent` and `rule` are the same knob at two altitudes — `percent: 10` is
 *  `rule: 'undercut:10'` spelled the way the screen spells it — and the server takes `rule`
 *  where both arrive. `basis` is `asking | market | low`; `asking` is the operator's own live
 *  price and is deliberately NOT one of `pricing.BASES`, because it is blank on almost every
 *  row of an ordinary Filtered Export and a listing run reading it would silently write no
 *  price at all. */
export type MarkdownAsk = {
  /** A live export this server already holds, named instead of uploaded (D104). Mutually
   *  exclusive with an upload; both together is a refusal rather than a guess. */
  fetched?: string
  days?: number
  percent?: number | string
  rule?: string
  basis?: 'asking' | 'market' | 'low'
  above_market?: number | string
  limit?: number
  again?: boolean
  write?: boolean
}

/** One press of either half. `console` is the command's own stdout, verbatim (D33).
 *
 *  `ok: false` IS AN ANSWER AND NOT AN ERROR, which is this seam's standing contract: a
 *  worklist the command refuses — a raised price, a duplicated SKU — comes back 200 with the
 *  reason in `console`. `stamp` names the markdown directory; null on a preview that made
 *  none. */
export type MarkdownAnswer = {
  ok: boolean
  /** WHETHER `import.csv` IS ACTUALLY THERE, not whether a write was asked for. `apply` exits 0
   *  with nothing written when every row was refused — one unreadable price does it — so the
   *  route answers by looking at the directory. */
  wrote: boolean
  exit_code: number
  console: string
  stamp: string | null
  /** The corpus digest AFTER the press. `apply --write` writes `inventory/prices.json` from a
   *  subprocess, which `emit` never does, so a screen that did not adopt this would have its
   *  operator's next keystroke refused `corpus_moved` for a write it just made itself. */
  revision?: string
}

/** What a push into TCGplayer's STAGED inventory reported back.
 *
 *  `upload_id` IS THE ADDRESS OF THE THING, not a receipt number. It is what a publish scopes
 *  to and what a rollback would undo, so a push that could not report one is a push that can
 *  neither be finished nor reversed — the server refuses rather than returning a partial.
 *
 *  `accepted` IS TCGPLAYER'S COUNT AND `rows` IS OURS, and they are kept apart on purpose: a
 *  file whose rows they silently declined would otherwise read as a success. `messages` is
 *  whatever they said about the rows they would not take, verbatim. */
export type MarkdownPush = {
  pushed: {
    upload_id: string
    /** How many rows this repo sent. */
    rows: number
    /** How many TCGplayer said it took. A gap is the thing to look at. */
    accepted: number
    messages: string[]
    pushed_at?: string
    published_at?: string | null
  }
  stamp: string
}

/** What moving a staged upload live reported back. **This is the one that changes prices.**
 *
 *  `published_at` IS THE LATCH. The route refuses a second publish of the same upload, because
 *  TCGplayer no longer holds those rows staged and a second move would be over rows nobody
 *  here can describe. */
export type MarkdownPublish = {
  published: {
    upload_id: string
    rows: number
    accepted: number
    messages: string[]
    pushed_at?: string
    published_at: string
    result?: unknown
  }
  stamp: string
}

/** What one live-export fetch brought back (D104).
 *
 *  THERE IS NO `shortfall` FIELD AND THERE CANNOT BE ONE. `Export From Live` takes no scope —
 *  no category, no set, no condition, no photo filter — so there is nothing it could have left
 *  out. The first build of this path guessed a FILTERED request and owed such a field; the
 *  measured one does not. An empty answer is refused outright rather than reported. */
export type LiveExportFetched = {
  ok: boolean
  /** The name this server kept it under. What `fetched` on the next request names. */
  fetched: string
  at: string
  rows: number
  /** Rows TCGplayer reported live — `Total Quantity > 0` — and the copies across them. */
  live_rows: number
  live_copies: number
}

/** One live listing the survey saw (D103).
 *
 *  ITS OWN TYPE AND NOT A `PricingSku` WITH HOLES. Twelve of that type's fields are a join's
 *  cap arithmetic, and three of them would be actively FALSE here rather than merely absent:
 *  `at_cap` where the cap is not the question, `positions: []` where the doc says the first is
 *  the representative photograph, and `nothing_to_add: null` — whose own doc says null means
 *  *"it adds one, which is the ordinary case"* — on a row that adds nothing, ever. A screen
 *  reassembling a sentence out of parts that say the wrong thing is the drift D16 exists to
 *  catch, and `app/src/pricingSource.ts`'s adapter is where the two shapes actually meet.
 *
 *  EVERY FIGURE IS TEXT AND EVERY FIGURE WAS COMPUTED SERVER-SIDE. `above_market`, `at_risk`,
 *  `cut` and `given_up` are arithmetic on money, and this client performs none — a price
 *  through a JSON float comes back as binary floating point, and every comparison downstream
 *  is `Decimal`. */
export type MarkdownSku = {
  sku: string
  /** Where the plan put it. `offered` is in the worklist; `deferred` QUALIFIED and fell below
   *  `--limit`; `refused` carries a `skip`. The third state is why this field exists — a
   *  deferred row and an offered row both carry `skip: null`. */
  standing: 'offered' | 'deferred' | 'refused'
  /** A `pipeline/reprice.py` refusal code, or null. Non-null exactly when `standing` is
   *  `refused`, and at most ONE even where three would apply: `plan`'s ladder is an early
   *  exit and `SKIP_ORDER` is its precedence. */
  skip: string | null
  name: string
  condition: string
  /** `Total Quantity` — what TCGplayer says is live, as of the download. */
  live: number
  /** The operator's own asking price, `TCG Marketplace Price`. Null on a live row the export
   *  gave no price for, which is a row nothing can judge a lowering against. */
  asking: string | null
  market: string | null
  above_market: string | null
  at_risk: string
  proposed: string | null
  /** What each named preset would list this row at, priced server-side by
   *  `pipeline/pricing.py:preset_prices` — the SAME function a run's `pricing.json` uses, so
   *  the two doors cannot compute a different number for one card. `null` per key where the
   *  basis column is blank, which is a real answer: 394 of 2,476 rows carry no `TCG Low`. */
  presets: Record<string, string | null>
  cut: string | null
  given_up: string | null
  /** THE PROXY, AND THE FALLBACK RATHER THAN THE ANSWER SINCE 2026-09-06. How long the CARD
   *  has been owned. Read it only where `listed_since` is null, and say which one is being
   *  drawn — D100's sentence is owed for this field and never for the other. */
  owned_since: string | null
  /** `Listing.first_seen_live` — the earliest export observed holding this SKU live, which is
   *  the LISTING's own age and the term the proxy above was standing in for. Null until
   *  `pkmnscan reconcile --live --write` has seen the SKU. */
  listed_since: string | null
  /** Whether any card in this store has ever carried this SKU. Evidence, not a gate: it
   *  explains a row with no thumbnail and no copies, and it stopped being a refusal on
   *  2026-09-06. */
  held_here: boolean
  last_sold: string | null
  priced_at: string | null
  /** The export row, verbatim, all sixteen cells. What an upload's bytes are built from and
   *  what a price history's five identity cells are read out of. */
  row: Record<string, string>
}

/** The lens's whole input — `survey.json` as `GET /pipeline/markdowns/<stamp>/table` serves it. */
export type MarkdownTable = {
  stamp: string
  at: string | null
  asked: Record<string, unknown>
  counts: Record<string, number>
  source: Record<string, unknown>
  skus: MarkdownSku[]
  /** Refusal code -> the operator's sentence, sent once rather than per row and never
   *  re-worded here: `pipeline/reprice.py:SKIP_SENTENCE` is the one table. */
  says: Record<string, string>
  /** The codes no price may be pushed for, decided by the server because `read_back` is what
   *  enforces it and two lists would drift. */
  unpriceable: string[]
  floor: string
}

/** One markdown as the screen lists it. `files` is what the directory actually holds, so
 *  whether the upload has been written is answered by `import.csv` being in it rather than by
 *  a flag that could be true of a file somebody deleted. */
export type MarkdownSummary = {
  stamp: string
  at: string | null
  asked: Record<string, unknown>
  source: string | null
  skus: number
  files: string[]
  /** What TCGplayer is holding staged for this markdown, or null for nothing sent.
   *
   *  IT IS ON THE SUMMARY SO A RELOAD HAS A WAY BACK. The push is a server write, and without
   *  it on the list an operator who pushed and then reloaded would have rows staged at
   *  TCGplayer with no control in this app able to publish them. */
  pushed?: MarkdownPush['pushed'] | null
}

/* ----------------------------------------------- every card on hand, ranked by what it is worth */

/** Why a card on hand carries no market price. Three causes, three different remedies, so a
 *  screen that collapsed them into "unpriced" would be telling the operator to do one thing
 *  about three problems.
 *
 *  `never_identified`  captured and never put through a run. The remedy is `#/runs`.
 *  `read_nothing`      identified, and the model returned neither a name nor a number, so no
 *                      SKU was ever bound. Every one of these has a photograph. The remedy is
 *                      a person looking at it.
 *  `no_reading`        a SKU this machine has never seen a market price for. The remedy is a
 *                      join or a live fetch. */
export type Unrankable = 'never_identified' | 'read_nothing' | 'no_reading'

/** One physical copy on hand, and what it is worth.
 *
 *  THE UNIT IS THE COPY AND NEVER THE SKU, which is the whole reason this type exists beside
 *  `PricingSku`. A hand goes to a slot: measured on the owner's store, the 122 cards at or
 *  above $5 are 38 SKUs — Rengar, Trophy Hunter sits in three slots of box 4 and Vilemaw in
 *  seven — so a per-SKU list draws a third of the rows and sends the operator to a third of
 *  the drawers they actually have to open. */
export type ValueCopy = {
  /** The store key — `/inventory/<box>/<index>`, the `<index>.jpg`, and what `photoUrl`
   *  addresses. `label` beside it is a RENDERING of it, composed fresh on every read against
   *  the box as it stands today (D58, on D56's rule); the label frozen into a run's
   *  `pricing.json` is never served. Same split `PricingSku.positions` states. */
  box: number
  index: number
  /** `null` where the server will not compose one — a box whose walk degraded, or a pooled
   *  card that never had a slot (D24). A caller draws its own fallback; it may never
   *  substitute `Box N · Section N · Card M`, which is the numbering D58 replaced. */
  label: string | null
  sku: string | null
  /** The CATALOGUE's name where there is a reading, the model's where there is not. 172 of
   *  the owner's on-hand cards carry the empty string from the model, which is why this can
   *  still be null on a row that has a photograph. */
  name: string | null
  set_name: string | null
  condition: string | null
  game: string | null
  state: string
  /** What TCGplayer says the card is worth, to two decimals, or `null` with `why` saying
   *  which of the three causes that is. NEVER `"0.00"` for an unreadable cell — a malformed
   *  market price ranked as zero lands at the very bottom of the cheap band and into a bulk
   *  pull, which is a wrong answer wearing the shape of a confident one. */
  market: string | null
  /** What the operator DECIDED to ask for this SKU, which is a different fact from what the
   *  card is worth (D86). Round-tripped as the corpus holds it — a string, a number, or a
   *  `WithheldRecord` — because flattening the last shape would turn a deliberate hold (D49)
   *  into a missing price. */
  answer: string | number | WithheldRecord | null
  /** How many copies of this SKU TCGplayer is holding, NEVER whether this copy is one of
   *  them. `live` is per-SKU and the store does not record which physical copy a push spent
   *  (D147 settles that ordering at the write), so a row claiming "this one is listed" would
   *  be inventing a fact. The operator ruled these are shown with no distinction — 70% of the
   *  copies under their cut-off are live — so it is context on the row and never a filter. */
  live: number
  /** When the reading was taken, as a UNIX SECOND, and which file it came from. Both null on
   *  an unpriced row. */
  read_at: number | null
  source: string | null
  why: Unrankable | null
  /** Which of `stack_of` identical-SKU copies this row is, within the current band/box scope
   *  — `null` for an unpriced row or one with no SKU. ONLY PRESENT ON `GET /pipeline/value`'s
   *  PAGINATED form (store-scaling item 7): the whole-list route's `copies` never carries
   *  these, because a client holding the whole list can still compute "copy N of M" itself
   *  (`app/src/ValueBands.tsx`'s old `stacks()`); a client fetching one page of a band cannot,
   *  since the other copies of a stacked SKU may sit on a page it has not fetched. */
  stack_index?: number | null
  stack_of?: number | null
}

/** One drawer, and whether the whole thing is bulk.
 *
 *  IT IS NOT A ROLLUP OF `copies` AND MUST NOT BE RECOMPUTED FROM ONE. `cards` counts every
 *  card in the drawer including the unpriced ones, and `per_card` divides by that — because
 *  the question at this level is *is this whole box bulk*, and dividing by the priced subset
 *  would flatter box 4 (633 cards, 215 unpriced) against box 2, where every card has a price.
 *  Measured: boxes 2 and 5 are 540 of 542 and 102 of 102 cards under the cut-off, together
 *  646 cards worth $66.79 — those two drawers ARE the bulk, whole. */
export type ValueBox = {
  box: number
  /** D20 leaves a name optional, so `null` is the ordinary case and never a fault. */
  name: string | null
  cards: number
  valued: number
  unpriced: number
  under_cutoff: number
  at_or_over: number
  total: string
  per_card: string
  top: string | null
}

/** Which file a reading came out of, and when. Sorted newest first. A thin list here is what
 *  makes a thin ranking legible as a thin ranking rather than as a store with nothing
 *  valuable in it. */
export type ValueSource = {
  kind: 'run' | 'live'
  name: string
  at: number
  skus: number
}

/** `GET /pipeline/value` — every card on hand, ranked, with nothing dropped.
 *
 *  `copies` ARRIVES SORTED BY MARKET DESCENDING, UNPRICED LAST, ties broken on `(box,
 *  index)`. The band the operator asks for is a SLICE of that one order — a typed price, the
 *  store's own cut-off, a top-N percentile, or the drawers ranked by value — and the slice is
 *  the client's because a percentile cannot be taken without the whole list anyway, and two
 *  sorts of one list is two places for a tie-break to differ.
 *
 *  NOTHING ON HAND IS OMITTED. 390 of the owner's 2,245 on-hand cards carry no market price,
 *  and a ranked view that quietly dropped 17% of the store would be the silent drop this repo
 *  forbids. Those rows are in `copies` with `market: null` and a `why`; `unrankable` counts
 *  them for the header. */
export type ValueTable = {
  at: string
  basis: 'market'
  /** The store's own cut-off (D9, amended) — the line `under_cutoff` partitions on, and the
   *  line `emit` partitions on. `null` only where no policy could be read. */
  threshold: string | null
  sources: ValueSource[]
  copies: ValueCopy[]
  boxes: ValueBox[]
  unrankable: {
    total: number
    never_identified: number
    read_nothing: number
    no_reading: number
    by_box: Record<string, number>
  }
  /** `under_cutoff`/`at_or_over` (store-scaling item 7) are the sum of every box's own
   *  figure — a store-wide chip count no row list is needed to draw, matching the fields
   *  `do_pipeline_value_page`'s `totals` block carries. */
  totals: { cards: number; valued: number; value: string; under_cutoff: number; at_or_over: number }
}

/** `GET /pipeline/sets` — one distinct card on hand, grouped under its set. `box`/`cid` are
 *  a REPRESENTATIVE copy, never every copy: `#/inventory?box=<box>&card=<cid>` is
 *  `BoxBrowse.tsx`'s own deep link (Review's place pill uses it too), and the walk it lands
 *  on already shows every other on-hand copy of `sku` through `CopiesPanel`. `null` on
 *  `box`/`cid` only for a record whose position will not coerce — `do_pipeline_sets`'s own
 *  rule, `do_pipeline_value`'s too. */
export type SetGroupCard = {
  sku: string | null
  cid: string | null
  box: number | null
  name: string | null
  /** The composed form a screen draws (D67) — `cardNumber.ts` composes nothing here, this
   *  is `pipeline/join.py:display_number`'s own string, already on the wire. */
  number_display: string | null
  qty: number
}

/** One game-and-set group, cards in the set's own printed order (server-side natural sort
 *  over the raw number, `do_pipeline_sets:_natural_number_key`). */
export type SetGroup = {
  game: string | null
  set_name: string
  cards: SetGroupCard[]
}

/** `GET /pipeline/sets` whole: every on-hand (`identified`) card, by set, one row per
 *  distinct card with its quantity — never one row per physical copy. `no_set` is every
 *  on-hand card whose `set_name` is empty, in the same shape, so a card with no set is a
 *  group and not a silent drop. */
export type SetsReport = {
  at: string
  groups: SetGroup[]
  no_set: SetGroupCard[]
}

/* ============================================================ the one press (send to live)
 *
 * `server/send_routes.py`, `D273`. One press reads what is live,
 * writes the listing file behind the double-send guard, sends it and makes it live. */

/** Where one send stands. `server/send_routes.py:state_of` is the one rule. `sending` is a press
 *  still running; `unknown` is one TCGplayer did not confirm, whose copies are held until the
 *  live check past the wait. */
export type SendState = 'sending' | 'unknown' | 'written' | 'waiting' | 'checked' | 'short' | 'failed' | 'taken_back'

/** One card the double-send guard held back: TCGplayer already held `live` of `on_hand`. */
export type SendTrim = {
  sku: string
  name: string
  live: number
  on_hand: number
  would: number
  goes: number
}

export type SendSummary = {
  stamp: string
  kind: 'send' | 'download'
  state: SendState
  at: string
  copies: number
  /** Price-only rows (Add to Quantity 0): cards already live whose typed price this send
   *  changed. The mixed send, the owner's ruling of 2026-09-24. */
  prices: number
  /** What the check past the wait found of those prices. `live` is TCGplayer's price then. */
  price_check: {
    expected: number
    matched: number
    missing: { sku: string; name: string; price: string; live: string | null }[]
    /** Cards with no copy live at the check: sold out, so there is no price to show. Settled. */
    gone?: { sku: string; name: string }[]
  } | null
  /** Price changes the button named that the press left out, and why (round 6). */
  prices_left: { sku: string; name: string; why: 'already' | 'not_live' | 'adds_copies' }[]
  /** Live copies this send's listing rows moved to their price (the owner's ruling, round 7). */
  moves: { sku: string; name: string; copies: number; price: string; was: string | null }[]
  /** True when the upload may still wait in TCGplayer's Staged list, including a press that
   *  died mid-push with no `unknown` (round 6). The Staged warning reads this. */
  staged: boolean
  rows: number
  published_at: string | null
  check_after: string | null
  checked_at: string | null
  check: {
    export: string
    found: number
    expected: number
    missing: { sku: string; name: string; sent: number; found: number }[]
  } | null
  trimmed: SendTrim[]
  trimmed_copies: number
  accepted: number | null
  /** Rows TCGplayer's own count turned away. The screen never says more went live than it took. */
  turned_away: number
  failure: { code: string; message: string } | null
  /** Why the outcome is not known. `staged` is true when the upload may still wait in
   *  TCGplayer's Staged list, where a person could publish it by hand. */
  unknown: { stage: string; upload_id: string | null; staged: boolean; file: string | null; at: string } | null
  /** The send's cards are held out of every other send (a press running, or an unknown one). */
  held: boolean
  /** Copies "Take them back" would return now. 0 until a live check has run past the wait. */
  takeable: number
  /** When taking these back becomes possible, while a check past the wait has not run yet. */
  take_back_after: string | null
  files: string[]
  taken_back_at: string | null
  /** What a TAKEN-BACK receipt still warns about, until the owner dismisses it: `staged`, an
   *  upload that may still wait in TCGplayer's Staged list; `old_file`, a downloaded file still
   *  on the Mac. Either, published or uploaded now, would list the copies twice. */
  warning: 'staged' | 'old_file' | 'rolled_back' | null
}

/** One price change the screen names to a send: the price the button counts, and the live
 *  price the row drew beside it. The server sends no price it was not named (round 6). */
export type PriceChange = { sku: string; price: string; was: string | null }

/** Live copies a listing row moves, as the button names them: the new copy carries Banchi's
 *  stored price, and every live copy of the card moves with it (the owner's ruling, round 7). */
export type LiveMove = { sku: string; name: string; copies: number; price: string; was: string | null }

/** One row a send refused, as data (round 7, R6-1): `live_moved` is a named price whose live
 *  price moved since the screen read it; `move_unnamed` is live copies a listing row would
 *  move that the button did not name. Both can be sent again, named. */
export type RefusedPrice = {
  sku: string
  name: string
  why: 'live_moved' | 'move_unnamed' | 'move_count' | 'below_floor' | 'not_saved' | 'not_in_send'
  price: string | null
  live: string | null
  shown: string | null
  copies: number
}

/** `GET /pipeline/sends`. `due` is the one bit the timer and the visit check both read. */
export type SendsStatus = {
  sends: SendSummary[]
  unconfirmed: { copies: number; stamps: string[] }
  due: boolean
  check_at: string | null
  now: string
}

export type SendAnswer = { send: SendSummary; console: string }

export type LiveCheckAnswer = {
  ran: boolean
  check_at?: string | null
  export?: string
  checked: SendSummary[]
}
