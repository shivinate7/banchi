# A card's identity follows its SKU

**Status: BUILT.** D258 (identity follows the SKU) records the ruling. The SKU table
(`store/skus.py`), the one writer (`Inventory.bind_sku`), `pipeline/identity_binding.py`,
`pipeline/identity_checks.py` and `cards identity --write` are in the tree. Whether `--write`
has run on the owner's store: unmeasured here. Section 11 holds the checks each part keeps.

**The rule.** One writer sets a card's name, number, printed total, rarity, set and condition.
It copies them from the SKU's row when it binds the SKU. What the camera read stays on the card
as evidence, under its own `read_*` names. Once a SKU is bound, the read never again answers
for the card's identity. Nothing about a name or a number can pick a SKU.

**The layer the owner sensed is the printing.** A SKU never says both Near Mint and Near Mint
Foil. One PRODUCT has both. The printing (normal, foil, holofoil, reverse holofoil) lives only
in the SKU's `Condition` cell. So a SKU is the finest layer.

## 1. Why a SKU and a name can disagree

The store began as a record of READINGS. D36 (the run owns what the model read) and D67 (the
set code is stripped for the eye, never in the record) both say so. `cards.name` and
`cards.number` were the model's read. The SKU arrived later as a second, independent column. It holds the catalog row
that the join or a human chose. D213 (the set is a stored fact) made `set_name` and `rarity`
follow the SKU. It left `name` and `number` as the read.

The two could then drift. A misread number sat under a right SKU. A name disputed the listing.
Nothing checked the pair.

The fix moves the read out of the identity fields and into `read_*`. The identity fields hold
the SKU's facts. A guard (4.3) keeps it so.

## 2. The layers

```
product   = product line x set x product name x number x rarity   (name, number, rarity, set)
printing  = product x finish                                      (the Condition suffix)
SKU       = printing x grade                                      (TCGplayer Id, one Condition cell)
```

- **A SKU is one row.** `TCGplayer Id` is unique in an export. Each id carries one `Condition`
  cell. So no SKU maps to two conditions or two finishes.
- **The `Condition` cell fuses a grade and a printing.** The grade is one of Near Mint, Lightly
  Played, Moderately Played, Heavily Played or Damaged. The printing is the suffix. It is none,
  `Foil` (Riftbound, One Piece), `Holofoil` or `Reverse Holofoil` (Pokemon). Sealed product
  carries `Unopened` and no split. `store/skus.split_condition` is the one place a cell is
  parsed.
- **A product has no id in the export.** It is the five columns above. `Rarity` does not differ
  between the SKUs of one product.
- **Some printings are separate PRODUCTS.** TCGplayer models foil as a condition suffix. It
  models `(Alternate Art)`, `(Metal)` and `(Poke Ball Pattern)` as a second product. That
  product has a qualified name and the same number. A number alone cannot pick a product.
- **No language layer.** No export column or `Condition` cell names a language.
- **SKU facts were stable** across every pair of exports compared. Pokemon stability across
  time: unmeasured.
- **Grade is constant on this store.** The catalog is Near Mint by rule (D137). So a SKU is
  one printing of one product. If that rule lifts, grade already lives in the SKU table and in
  `condition`.

Identity derives DOWN from the SKU, never up. The game's own vocabulary reads the printing at
read time (`pipeline/variant.vocabulary`, `finishes` and `condition_by_finish` in
`pipeline/games.py`). The store never keeps it twice.

## 3. The data model

### 3.1 Three groups of facts on a card

| group | fields | written by | meaning |
|---|---|---|---|
| evidence | `read_name`, `read_number`, `read_printed_total`; `detected_finish`, `confidence`; the capture claims `set_hint`, `metadata_finish`, `rarity_claim` | the identification, and the operator at the shutter | what the camera read and the operator said. Only the next identification of the same photograph rewrites it. Never searchable |
| binding | `sku`, `bound_by`, `bound_at`, `identity_source`, `read_disputes` | the one writer (section 4) | which SKU this card is, who chose it, and when |
| identity | `name`, `number`, `printed_total`, `rarity`, `set_name`, `condition`; `number_key`, `number_display` (derived in `store/master._card_columns`) | the one writer only, from the SKU table | what the card is. Every screen and the search index read this |

`condition` is a SKU fact. It stays on the card because it keys `listings`.

**`identity_source` has two values.** `sku`: the identity fields equal the SKU table's row.
`read`: the card has no SKU, or is held (7.3), or its SKU is absent from the table. Then the
identity fields equal the evidence. A card with a SKU and `identity_source = read` is RESIDUE.

**`bound_by` names the act.** It is one of `BOUND_BY_ACTS` in `store/master.py`: `join`,
`answer`, `group_answer`, `correction`, `confirm`, `migration`. It lives on the card record,
bound to its `cid` (D172, the first photograph is the name). It never lives in the
position-keyed `events` table alone. A position key is reused. A card answered at one key can
move, and a new card can take the key. A replay that scopes acts by position alone credits the
new card with the old card's answer. Scope acts by the card's own capture time.

**`read_disputes`** is `pipeline/join.name_disputes(read_name, [identity name])`. The caller
computes it at each write that changes either side, and `bind_sku` stores it. `store/` imports
nothing from `pipeline/`, so the store cannot compute it. It is stored, not computed per
request, because `#/inventory` is a polled route.

### 3.2 The SKU table

`skus` is one D88 table (`TableSpec` in `store/skus.py`, the shape of `store/readings.py`).
`_add_skus` in `store/db.py` adds it. The step is idempotent, and a later schema step runs it
again. So a store stamped by a branch that lacked the table still gets it.

**Why a table, not a live join to an export.** `#/inventory` is polled, and an export ages out
of `inventory/.exports/` (D166). A table answers both. A lookup is one indexed probe, and a row
outlives its file. The one writer reads the table, never an export file.

**Not reused, and why.**

- `pipeline/join.Catalog` is the join's candidate universe. Its completeness is the export's
  (D65). A table of every SKU ever seen has no completeness claim. The join must never read
  candidates from it.
- `readings` (D189) is a FULL REPLACE cache. It drops a SKU whose source file goes. The SKU
  table must never do that.
- `listings` (D34, D109) holds counts, not product facts. It joins to `skus` on the SKU.
- The pokemontcg.io snapshot (D15) carries no TCGplayer id. It cannot fill a SKU row.

**Columns.**

| column | holds |
|---|---|
| `key` | the `TCGplayer Id` |
| `product_line`, `set_name`, `product_name`, `number`, `rarity`, `condition` | the six fact cells, verbatim |
| `grade`, `printing` | the `Condition` cell split. NULL for a cell outside the five grades |
| `first_seen`, `last_seen` | the stamp of the oldest and newest file that carried the row, from the file's own name (`pipeline/skus.stamp_of`). Never the time of the press (D166) |
| `source` | the newest file that carried the row |
| `payload` | the whole row as read |

Two views give the upper layers with no second copy to drift. `sku_products` groups by product
line, set, product name and number. `sku_printings` adds `printing`. The audit reports a
product whose SKUs disagree on `rarity`.

**No `game` column.** A `Product Line` does not name one game: `pokemon` and `pokemon_code`
share `Pokemon`. The game stays a per-card claim (D21). At bind time the writer compares the
`product_line` of the card's game entry with the row's. A difference is the refusal
`game_mismatch`.

**How it is filled.** `pipeline/skus.apply_rows` folds rows in at every place an export enters
the store.

1. A fetched Filtered Export: `server/pipeline_routes._keep_export`.
2. A fetched live export: `server/pipeline_routes.do_live_export`.
3. An export a person hands the CLI: `cli/cmd_join.py` (`--export`), `cli/cmd_reconcile.py`
   (`reconcile --live`) and `cli/cmd_emit.py`.
4. The backfill: `./pkmnscan skus adopt [--write]`. It previews by default. It reads
   `inventory/.exports/*/*.csv` and `inventory/.live/*.csv`.

**Freshness, and why it never deletes.** `Skus.fold` gives one of four results.

- New SKU: insert.
- Same facts: move `last_seen` and `source` forward.
- A row from an OLDER file than `last_seen`: no change. The file's own stamp decides, and the
  newest wins (D189's rule).
- A row from a newer file with DIFFERENT facts: write the new facts and reset `first_seen`. The
  caller appends one `sku_facts_changed` event that holds the old facts. Cards bound to that
  SKU then disagree with the table. The audit names them. `cards identity --write` derives
  them again.
- **No row is ever deleted.** `store/skus.py` has an upsert and reads. It has no delete, clear
  or full replace (D219, the archive never deletes). A SKU that TCGplayer stops listing keeps
  its row, because a card bound to it still needs its facts. `scripts/skus-selftest.py` proves
  it.

**A SKU the table lacks.** `bind_sku` refuses `sku_unknown` and changes nothing. The join, the
review answer and the correction each hold the chosen row. Each upserts it first, in the same
transaction. The confirm press binds the card's current SKU, which the table already holds. A
card that still meets `sku_unknown` keeps `identity_source = read`. `cards identity` lists it.

### 3.3 What each identity field holds

- `name` holds the table's `product_name` verbatim. Screens draw it through one composer. The
  composer drops the trailing collector number that TCGplayer embeds in some Pokemon names
  (`Stufful - 111/132`). The rule is `store/numbers.strip_name_suffix` over
  `NAME_NUMBER_SUFFIX`. `pipeline/join.name_index_key` imports the same pattern. A trailing
  qualifier such as `(Alternate Art)` stays, because it names a different product.
- `number` and `printed_total` come from the SKU row's `number` cell (section 6).
- `rarity`, `set_name` and `condition` hold the table's cells.

### 3.4 Where the reading lives

The model's reading lives in three places. They are the run's `identifications.json` (D36),
the store's `identifications` table (keyed by photograph digest), and `read_*` on the card.
`Inventory.record_identification` writes `read_*` in the same call that writes the reading. So
the copy moves with its source. `read_*` is never a key and never binds a slot. The digest
does that.

The migration recovers `read_*` from the `identifications` entry under the card's `cid`. It
does not use the card's current fields, because a correction may have overwritten them.

## 4. The writers

### 4.1 One writer

`Inventory.bind_sku` (`store/master.py`) is the only code that chooses a card's `sku`, identity
fields, `bound_by`, `bound_at` and `identity_source`. It takes the card key, the SKU, the act
and the caller's `read_disputes`. It reads the row from the SKU table. It derives the number
pair itself, and it appends one history event. It refuses `sku_unknown` and `game_mismatch`,
and then it writes nothing. `unbind_sku` restores a previous binding for an undo. It derives
the identity from the SKU table again.

`bind_sku` takes `number_strategy`, never a number. The dispatch lives in `store/numbers.py`
and is keyed on the strategy name. So a caller cannot make the writer store a number that the
row does not own. `pipeline/join.catalog_number_fields(game, raw)` delegates through
`games.get(game)["join_key"]`. `store/` imports nothing from `pipeline/` (the `import layering`
row of `make docs-audit`). So the dispute test runs in the caller.

`Inventory.set_state` moves state only. `restore_identity` and `hold_sku` are the other two
identity writers. They restore an undone binding and record a held card.

### 4.2 Every writer that sets a SKU or fills the table

| writer | what it does |
|---|---|
| `cli/cmd_emit.run`, `run_merged` (the join's commit) | upserts the matched rows, then `bind_sku(bound_by=join)` |
| `server/capture_server.do_review_answer` (D4 candidate, D77 `from_catalog`) | upserts the chosen row, then `bind_sku(bound_by=answer)` |
| `server/capture_server.do_review_group_answer` (D29) | upserts, then `bind_sku(bound_by=group_answer)` per card |
| `server/capture_server.do_correct_answer` (D252) | upserts, then `bind_sku(bound_by=correction)`, and the D34 release of the old SKU |
| `server/capture_server._reverse_answer`, `_reverse_correction` (undo) | `unbind_sku` to the recorded previous binding. Section 8.3 |
| `server/capture_server.do_confirm_identity` (`POST /inventory/<box>/<index>/confirm`) | `bind_sku(current sku, bound_by=confirm)`. Section 8 |
| `_keep_export`, `do_live_export`, `cmd_join --export`, `reconcile --live` | fill the table |
| `Inventory.record_identification` (from `cli/cmd_identify.run`, `codes/scan.py`) | writes `read_*`. On a card with no SKU the identity follows the read. On a SKU-bound card the identity stays, and the caller recomputes `read_disputes` |
| `Inventory.move_card` (D83) | clears `sku` and `condition` on the tombstone. The transplant keeps both. A tombstone keeps its identity as frozen history (D134), and the audit exempts `moved` |
| `scripts/demo-seed.py` | fills the demo store's SKU table from its manifest, sets `read_*`, and calls `bind_sku` (5.9) |
| `cli/cmd_reconcile.py` listings writes (D87, D109) | `listings` rows only. Never a card's `sku` |
| `server/capture_server._sell`, `do_retire` | state only |

`cards variants` and the `export_for` backfill are retired into `cards identity --write`.

### 4.3 The mechanism that keeps them together

D173 (a rule that can be enforced is enforced) needs a mechanism, not a sentence. There are
three.

1. **One writer, checked by a machine.** The `identity writers` row of `make docs-audit` reads
   the Python AST of `server/`, `store/`, `pipeline/`, `cli/`, `codes/` and `scripts/`. It
   fails a commit that assigns `sku`, `condition`, `name`, `number`, `printed_total`, `rarity`
   or `set_name` on a card outside `IDENTITY_WRITERS` (`store/master.py`). The six methods are
   `bind_sku`, `unbind_sku`, `restore_identity`, `hold_sku`, `record_identification` and
   `move_card`. The row reads the constant, never a copy. Its own exception list,
   `IDENTITY_WRITERS_ALLOWED`, is empty and ratcheted. It sees only a `card.<field>`
   assignment.
2. **The store's own audit.** `./pkmnscan cards identity` reads the store and the SKU table,
   never an export file. It gives three verdicts (D172's shape): pass, fail, not known. It
   fails on any of these:
   - a card bound `sku` whose identity differs from its row.
   - a card or `listings` row whose SKU is absent from the table.
   - a product whose SKUs disagree on `rarity`.

   It is read-only and never on the commit path, because no commit check reads the owner's
   store.
3. **The residue count.** The same report prints how many SKU-bound cards carry
   `identity_source = read`. **NOT MECHANIZED as a ratchet:** the count lives in the owner's
   store, which no commit reads. The review queue carries each held card (7.3). Home's Review
   tile counts it (D121).

## 5. The readers

A reader of IDENTITY gets the SKU's facts with no code change, because the field names stay. A
reader of EVIDENCE must use `read_*`. Otherwise it goes blind. It would compare the SKU's name
against the SKU's own row and never find a dispute.

### 5.1 The join: evidence

`pipeline/join.py` compares an `IdentifiedCard`'s read name and number against catalog rows
(D23, D162, D253). It must keep comparing the READ. Three builders make an `IdentifiedCard`.

- `cli/resolve.py` builds from a run record's `identification`, which is the read.
- `cli/resolve.store_payload` (D188) builds from the card, and uses `read_*`.
- `cli/requeue.identified` (D167) builds from the card, and uses `read_*`.

If a store-backed builder used `card.name`, the D253 check would see the SKU's own name and
agree with itself. It would then release every disputed card it refreshed.
`scripts/identity-readers-selftest.py` holds a mutation arm per builder. The join reads its
candidate rows from the export, never from the SKU table.

### 5.2 Search: the catalog name only

The owner ruled: "Catalog name only". Search indexes the identity. `read_*` lives in the
payload, and no FTS trigger reads it. `cards_fts` already indexes `name`, `number`, `sku`,
`set_hint`, `note`, `number_key` and `number_display`, so it needed no change. `note` stays
indexed, because an operator types it. A card with `identity_source = read` is found by its
identity, which for that card is the read. `server/capture_server.do_search` groups by SKU. A
SKU group holds one name by construction. A search for a misspelling of the camera does not
find the card.

### 5.3 Identity readers that change with no code

Every screen that draws `name`, `number` or `rarity` now draws the SKU's product. That covers
the `#/inventory` lists and Details, the landmark walk, Home's recent deck, orders and the
walk, holdings (`_value_rows`, D236) and the Fulfiller's screen. `#/graveyard` and box delete
draw the name at burial, which is frozen history (D134).

`number_key` composes from the catalog pair. So D234's glued-code repair has nothing to repair
on a SKU-bound card. Price history (D254) tier (b) reads the SKU table. It no longer merges
cached exports on each call. Tier (c) now equals tier (b) for every SKU-bound card.

### 5.4 The one new thing a screen draws

`CardDetailsSection` (`app/src/CardHero.tsx`) draws one extra line, "Read as {read name}
{number}". It draws only when `read_disputes` is true. The Fulfiller never sees it (D5). It
passes D196 (no decision, path or pipeline noun on screen).

### 5.5 One report

`./pkmnscan cards identity` (4.3) is the one report. It has a name half and a number half. Both
compare `read_*` against the SKU table's row. They use the join's own tests
(`pipeline/join.name_disputes`, and the number fold in section 6).

Both halves exclude a card whose `bound_by` is `answer`, `group_answer`, `correction` or
`confirm`. A human chose that SKU off the photograph, so the question is answered. Without the
exclusion the report flags the same card forever, and a guard that cries wolf is spent. The
report also carries the residue count and the three audit failures of 4.3.

`cards sku-names` and `cards contradictions` are retired. Each prints one line that names
`cards identity`. A guard that reads the SKU's own values could never go red.

### 5.6 The D239 checks

`pipeline/identity_checks.py` flags misread shapes in the name, number and set it is given. Its
caller, `_checks` in `cli/cmd_cards.py`, builds the records from `read_*`. `set_name` stays on
identity, because it is a SKU fact.

### 5.7 The review queue

A queue entry's `read` block is a copy of the reading, taken when the entry is written.
`app/src/ReviewQueue.tsx` draws both candidate sets off `candidates` and `name_matched_skus`
(D253), never off the reason. The reason `listing_disputed` has one label: "Is the listing the
right card?".

### 5.8 The Fulfiller's floors

The change adds no element, so it touches none of `docs/DESIGN.md`'s floors. On some cards the
product name is longer than the read name. `make design-check` verifies the wrap.

### 5.9 The demo

`scripts/demo-seed.py` upserts the manifest's catalog rows into the demo store's SKU table. It
writes `read_*` from the manifest, and it binds through `bind_sku`. The static build reaches no
new route. The confirm press refuses there like every other write (`docs/specs/demo.md`).

## 6. The number, per game

`pipeline/join.catalog_number_fields` decomposes the SKU table's `number` cell. It uses the
game's own `join_key` strategy. It is the identity number's only source.

| game | strategy | identity `number` | identity `printed_total` | example |
|---|---|---|---|---|
| Pokemon | `number_and_printed_total` | the numerator, by `store/numbers.split_catalog_number` on the LAST `/` | the denominator | `024/132` gives `024` and `132` |
| Riftbound, One Piece | `printed_code` | the cell, verbatim | empty | `145a/219`, `OP15-003`, `T01 // T02` |
| any other | `name_only`, `not_joined`, or unknown | the cell, verbatim | empty | the safe default |

`number_key` and `number_display` stay derived in `store/master._card_columns`. Every card row
passes through it. Nothing sets them directly.

**The read number keeps its raw form**, set code and all (`OGN • 217/298`). D55 and D67 repair
and strip it where a read is drawn or joined.

**Agreement test (the migration and the report).** For Pokemon, compare `store/numbers.join_key`
of the read pair with the row's cell. For every other game, apply `store/numbers.strip_set_code`
to the read. Then pass both sides through `pipeline/join.number_index_key`. This is the join's
own fold.

One Piece: the rule is Riftbound's, and only the fixture proves it.

## 7. The migration

### 7.1 The acceptance bar

**Zero cards change in a way the owner has not confirmed.** A CHANGE is the drawn identity
moving to a different card. That means a name the read disputes, or a number the read does not
equal after the join's fold. A spelling change draws the same card. Case, accent, a catalog
qualifier, an embedded number and a near miss inside D23's tolerance are spelling changes.

The migration never changes a SKU, a listing count, a price, a queue answer, a photograph, a
`cid` or a reading. It fills the SKU table. It writes `read_*`, the binding bookkeeping and the
identity fields.

### 7.2 The classes

`pipeline/identity_binding.py` puts each card in exactly one class. It tests them in this order.

| class | test | ruling |
|---|---|---|
| T3 human | the newest human act on THIS card (answer or correction, after its own capture) chose this SKU | derive. The press previews the names the read disputes once |
| T5 held | the read name disputes the SKU, or is blank, and no human act | held |
| T4s held | the read name agrees, the number does not, and the name names more than one product in the game's export | held |
| T4u | the read name agrees, the number does not, and the name names exactly one product | derive (D162: a unique name decides alone) |
| T1 | name equal after the fold, number equal or blank | derive |
| T2 | name a near miss inside D23's tolerance (`NAME_DISPUTE_SIMILARITY`, D251), number equal or blank | derive |
| T6 | no SKU | unchanged |

A card whose SKU is absent from the table is `SKU_UNKNOWN`.

T1 and T2 differ from the SKU only in spelling. No photograph is needed to say so. T3 rests on
a photograph that a human checked (D4, D252). Human answers are not perfect. The owner has
corrected wrong ones. So the press lists each T3 card that draws a name its read disputes.

T4s and T5 are two signals that disagree while nobody has looked. So they are held. Class
counts on the owner's store: unmeasured here.

### 7.3 The path

1. **Schema step, on open.** `_add_skus` adds the `skus` table, its views and its indexes. It
   adds an indexed `identity_source` column on `cards`, so the residue count is one probe. The
   other new card fields live in the payload. FTS is unchanged. The DDL runs inside `_upgrade`'s
   one transaction. `check_schema_eleven_then_twelve` in T7 builds each older shape.
2. **Fill the table:** `./pkmnscan skus adopt --write` (3.2).
3. **The press:** `./pkmnscan cards identity --write`. It previews by default. It never runs at
   open time, because its answer depends on what the table holds, and that grows.
   - Every card: backfill `read_*` from the `identifications` entry for its `cid`.
   - T1, T2, T3, T4u: `bind_sku(bound_by=migration)`, with the class recorded on the event.
   - T4s, T5: write `identity_source = read`. Leave every identity field as it is. No held card
     changes on screen.
   - Each held card that is identified opens a review entry under `listing_disputed`
     (`pipeline/routing.LISTING_DISPUTED`). The entry carries the photograph, the read, the
     SKU's own row and D253's two candidate sets. It goes to both queues, because a human may
     have cleared the card in either (`held_review_entry`).
   - Each held card that is sold: report only. D252 refuses to correct a departed card
     (`card_departed`), and the sale went out under the SKU.
   - The press is re-runnable. It skips a card already bound. It also skips a card whose SKU
     moved between the preview and the write (an in-lock re-check).
4. **Answering a held card.** Section 8.

### 7.4 The replay, before any write

`scripts/identity-replay.py` opens a COPY of the store read-only (`store/db.open_read_only`)
and the on-disk exports. It runs the classifier and its would-be writes in memory. It prints
the class table. It fails on any miss of these six:

1. Every held card's drawn `name`, `number` and `number_display` equal today's, byte for byte.
2. No card's `sku`, `condition`, `state`, `cid` or `photo` differs. No `listings` or `queues`
   row differs, except the new `listing_disputed` entries.
3. Every card bound `sku` has identity fields equal to its SKU row.
4. Every T3 card's SKU equals the newest human act ON THAT CARD, scoped by the card's own
   capture time. A moved card falls to a later class, which errs toward holding.
5. Every card whose drawn identity moves is in T3 or T4u.
6. Every SKU on a card or in `listings` is in the SKU table.

**The bar: zero identity moves outside T3 and T4u.** The store moves under a measurement. Run
the replay on the day of the write.

## 8. The right SKU, the wrong name

### 8.1 After the change it is "confirm"

For a card bound `sku`, the name already follows the SKU. So there is nothing to correct. The
"Read as" line (5.4) keeps the camera's version visible when it disputes.

For a held card, the owner gives one of two answers.

- **The listing is right.** `POST /inventory/<box>/<index>/confirm` (`do_confirm_identity`)
  calls `bind_sku(current sku, bound_by=confirm)`. It releases no listing, because the SKU does
  not move. The history event is `identity_confirmed`. `{"undo": true}` returns the card to
  `identity_source = read` (D28's shape).
- **The listing is the wrong card.** This is the D252 correction. It sets a new SKU. It
  releases the old SKU through `Listing.release` (D34). It records `bound_by=correction`.

On `#/review`, `do_review_answer` routes a `listing_disputed` answer. The card's own current
SKU goes to confirm. Any other SKU goes to the correction. The server routes it, so no screen
can pick the wrong one.

On `#/inventory`, the D252 pane (`ListingCorrection` in `app/src/CardHero.tsx`) has a second
press, "The listing is right". It draws only on a held card. It sits in the slot that D252
already reserves (D118).

### 8.2 `sku_unchanged` stays

`do_correct_answer` refuses `sku_unchanged`, because a correction to the same SKU does nothing.
On a held card, the refusal text also names the other press: "If the listing is right, press
"The listing is right" instead."

### 8.3 Old history lines

`_reverse_correction` restores a key only where the line records it (D252: a missing key is not
a null claim). A line now records the previous binding (`sku`, `bound_by`). `unbind_sku`
derives the identity from the SKU table. A line written before the change still carries `name`,
`number`, `rarity` and `set_name`. `unbind_sku` ignores them.

## 9. Risks, and what is given up

1. **A wrong SKU now looks right.** A misbound card used to draw the camera's name. That name
   at least disagreed with the listing. Now it draws the listing's name, cleanly. Four things
   protect the outcome.
   - D253 refuses to bind a disputing read at the join.
   - The one writer refuses it too.
   - `read_disputes` draws "Read as" in Details.
   - Held cards stay drawn as read until answered.

   One case stays open: a wrong human answer on a card whose read AGREED with the wrong SKU.
   Its rate is unmeasured.
2. **The camera's version leaves the lists and search.** Only Details draws it, and only when
   it disputes. The owner chose this.
3. **A TCGplayer rename.** The table takes the newer facts and keeps the old ones in an event.
   The report names the bound cards that now differ. The press derives them again.
4. **The table only grows.** That is the price of never deleting. Disk cost: unmeasured.
5. **Filling on a fetch adds work to the press.** The cost of upserting about 10,000 rows in
   the fetch's write: unmeasured.
6. **Given up:** D253's near-miss name write (`JoinReport.name_corrections`), `cards variants`,
   `cards sku-names`, `cards contradictions`, three in-memory SKU maps, and every per-field
   identity write in D252's route. The one writer, the one table and the one report replace
   each of them.

## 10. Decisions this amends or cites

- **D213 (the set is a stored fact). Widened.** `name`, `number` and `condition` follow the SKU
  like `set_name` and `rarity`. They are written at binding, never by a live join. The source
  is the SKU table. It answers D213's second ground better than a file, because a row outlives
  its export. The hint was never a fact, and the read was never one either.
- **D252 (a wrong answer gets a correct route).** The route upserts the chosen row and writes
  one binding through `bind_sku`. `sku_unchanged` stays. A sibling press, confirm, answers the
  case D252 cannot: the SKU is right and the drawn name is wrong. The D34 release is untouched.
- **D253 (a card lists off name AND number agreeing).** Kept in substance. The identity name is
  the row's by construction, so the near-miss name write is gone. The two store-backed builders
  read `read_*`. That keeps the READ as the thing the join checks.
- **D242 (one SKU, a disputing name or two stored numbers).** Merged into `cards identity`. Its
  original class is empty by construction. That is the outcome it protected.
- **D239 (four stored-data checks).** Its caller builds from `read_*`.
- **D254 (a product resolves from its SKU).** Tier (b) reads the SKU table.
- **D189, D219.** The table refuses D189's full replace and takes D219's never-delete rule. It
  reuses D189's newest-wins rule.
- **D36 (the run owns what the model read).** Unchanged. `read_*` is a copy, never a key.
- **D183 (a number a person reads is never a key).** Extended. A number the camera read stops
  answering for identity once a SKU binds.
- **D162, D23.** A unique name decides alone. That is the argument for class T4u.
- **D65, D104, D166.** The exports are the table's sources. The join still reads its candidates
  from them.
- **D137 (the catalog is Near Mint by rule).** It is why grade is constant here.

## 11. Build status

Every part is built. Each part keeps one check.

- **The SKU table:** `scripts/skus-selftest.py` proves these points. Rows equal distinct ids. A
  second adopt changes nothing. An older file never overwrites newer facts. A changed fact
  writes one event and keeps the row. `store/skus.py` has no delete path.
- **The one writer:** `scripts/identity-store-selftest.py` proves these points.
  - `bind_sku` writes identity equal to a table row for Pokemon, Riftbound and a token cell
    (`T01 // T02`).
  - `unbind_sku` round-trips it.
  - `sku_unknown` and `game_mismatch` write nothing.
  - A caller cannot hand `bind_sku` a number that the row does not own.
- **The press, the report, the replay:** `scripts/identity-binding-selftest.py` proves every
  class, its order and the human-bound exclusion. `scripts/identity-replay.py` holds 7.4.
- **The server writers:** `harness/tests/t7_store_and_seams.py` proves that each writer in 4.2
  upserts. It proves identity then equals its row and `read_*` is untouched. It proves confirm
  and its undo work.
- **The CLI writers:** `scripts/identity-cli-selftest.py`.
- **The evidence readers:** `scripts/identity-readers-selftest.py`.
- **The guard:** the `identity writers` row of `make docs-audit`.

## 12. Rulings that stand

- A change is the identity moving, not the spelling. D162 covers T4u.
- T3's disputed names derive, and the preview lists them once.
- Held sold cards stay drawn as read. Only the report lists them.
- Search indexes the catalog name only (5.2).
- The store-owned SKU table is built (3.2).
- One report replaces D242's two (5.5).
