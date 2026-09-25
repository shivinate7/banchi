# A card's identity follows its SKU

**Status, 2026-09-24. APPROVED BY THE OWNER, NOT BUILT.** The owner answered all seven questions
of section 12 the same day. This revision carries his rulings. Ruling 5 adds a store-owned SKU
table to the plan (section 3.2), and ruling 4 keeps the read name out of search (section 5.2).
The build goes straight to lanes (section 11), with no `OPEN` step.

Nothing here writes the store. Every number below was measured read-only. The store source is
a `sqlite3 -readonly` backup copy of `inventory/store.sqlite`, taken 2026-09-24 11:58 local. The
export sources are the owner's two cached exports, `inventory/.exports/riftbound/` (2026-09-14,
10,191 rows) and `inventory/.exports/pokemon/` (2026-09-19, 1,614 rows), and his 11 live
exports under `inventory/.live/`. The store moves under a measurement: the owner corrected
`1/75` six minutes before the copy. Re-measure on the day of any build (section 7.4).

**The owner's words, 2026-09-23, verbatim.**

```
Q: Make a card's name/number/rarity follow its SKU, so the two can never drift apart again?
A: yes derive from sku, with the caution/care that we know that the same sku can say near
   mint and near mint foil while those are two cards so we'll need one more granularity
   layer i think, have an agent figure this out hollistically
Earlier: how is this even possible that we have SKUs independent of names?
```

**The short answer.** The SKU already is the finest layer. A SKU never says both Near Mint and
Near Mint Foil. One PRODUCT has both. So a card's name, number, rarity and set derive from its
SKU exactly, and nothing about a name or a number can pick a SKU. The layer the owner senses is
the PRINTING (normal, foil, holofoil, reverse holofoil). It lives only in the SKU's `Condition`
cell. The store keeps every SKU's facts in its own table, and a card's identity is written from
that table. The model's reading stays on the card as evidence, under its own name. Once a SKU
is bound, the reading never again answers for the card's identity.

## 1. Why a SKU and a name can disagree today

The store was built as a record of READINGS first. D36 (the run owns what the model read, the
store owns the slot) and D67 (the set code is stripped for the eye, never in the record) both
keep the model's reading as a durable fact. D67 says so directly: normalizing the record would
hide the misread rate. So `cards.name`, `cards.number` and `cards.printed_total` are the
model's read, written by `Inventory.record_identification` in `store/master.py`.

The SKU arrived later, as a second, independent column: the catalog row the join (D11) or a
human (D4, D46) chose. D213 (the set is a stored fact) then made `set_name` and `rarity` follow
the SKU, written at the moment a SKU is committed. It left `name` and `number` as the read, on
purpose. Two writers since overwrite them from a catalog row: the D252 correction (a wrong
answer gets a correct route) and the D253 near-miss correction (a card lists off name AND number
agreeing). No other writer does, and nothing checks the pair.

**Measured, 3,510 cards, 3,502 with a SKU.** `rarity` equals the SKU row's `Rarity` on 3,502 of
3,502. `set_name` equals the SKU row's `Set Name` on 3,502 of 3,502. `condition` equals the SKU
row's `Condition` on 3,502 of 3,502. D213's rule holds everywhere it applies. The drift is in
the two fields D213 did not reach:

| field, against the SKU's own row | cards |
|---|---|
| name identical | 2,956 |
| name equal after `pipeline/join._name_compare_key` (case, accents, a catalog qualifier) | 260 |
| name a near miss, not disputed (`pipeline/join.name_disputes` is False) | 222 |
| name disputed (58 identified, 6 sold) | 64 |
| number equal after the set-code strip and `pipeline/join.number_index_key` | 3,056 |
| number different | 241 |
| number blank | 205 |

D255's own report (`./pkmnscan cards sku-names`) ran six minutes earlier on the live store. It
reads 65 disputed (59 identified, 6 sold). The one-card difference is `1/75`, corrected between
the two reads. The brief's figure of 57 is an earlier count.

## 2. The layers, measured

Six exports, read with the `csv` module: the four committed fixtures (Riftbound, One Piece,
wide Pokemon, SV09) and the owner's two cached exports. 33,648 rows in total.

**A SKU is one row.** `TCGplayer Id` is unique in every file: 0 duplicate ids in 33,648 rows.
Each id carries exactly one `Condition` cell. **No SKU maps to two conditions or two finishes.**

**The `Condition` cell is two facts fused: a grade and a printing.** Every cell in the six files
splits into one grade prefix and one printing suffix.

| game | printings (the cell's suffix) | grades |
|---|---|---|
| Riftbound, One Piece | (none), `Foil` | Near Mint, Lightly Played, Moderately Played, Heavily Played, Damaged |
| Pokemon | (none), `Holofoil`, `Reverse Holofoil` | the same five |
| sealed, any game | none | `Unopened` |

**A product is (Product Line, Set Name, Product Name, Number, Rarity).** The export has no
product id (D254 found this). Grouped on those columns, file by file: 5,393 product groups.
**`Rarity` never differs between the SKUs of one product: 0 of 5,393.** In the five full
exports, a product has 5 SKUs (one printing), 10 SKUs (two printings), or 1 SKU (sealed). SV09
is a Near Mint only file, so its products have 1 or 2 SKUs, one per printing.

**Some printings are PRODUCTS, not conditions.** TCGplayer models foil and holofoil as a
condition suffix. It models other printings as a separate product, with a qualified name and
the same number. So a number alone cannot pick a product either. Measured, the `(set, number)`
pairs that carry more than one product name:

- 40 in the cached Riftbound export: `(Metal) (Best Of)`, `(Metal) (Prize Wall)`.
- 197 in the One Piece fixture: `(Alternate Art)`, `(Dash Pack)`.
- 100 in the wide Pokemon fixture: `(Poke Ball Pattern)`, `(Master Ball Pattern)`.

**No language layer.** No export carries a language column, and no `Condition` cell names a
language. Other product lines: unmeasured.

**SKU facts are stable over what was measured.** 10,078 Riftbound SKUs appear in both the
committed fixture and the owner's 2026-09-14 export. 0 of them changed any of Product Line, Set
Name, Product Name, Number, Rarity or Condition. Over the owner's 13 on-disk files (2
cached exports, 11 live exports, 19,663 rows), no SKU carries two different values in any of
those six columns. The two Pokemon fixture files share no SKU, so Pokemon stability across
time is unmeasured.

**The owner's case, on his own store.** 832 distinct products are held. **84 of them are held
under two SKUs, one Near Mint and one Near Mint Foil, across 317 cards.** Example: Vendetta
`Baccai Sandspinner` `001/166` Common, 2 copies under 9422134 (Near Mint) and 2 under 9446030
(Near Mint Foil). Name, number, rarity and set are equal for both. Only the printing differs. A
second shape: five Showcase runes (`Mind Rune (R03a)` and four more) are held in two sets with
equal name, number and rarity. Only the set differs.

**The layers, named.**

```
product   = product line x set x product name x number x rarity   (name, number, rarity, set)
printing  = product x finish                                      (the Condition suffix)
SKU       = printing x grade                                      (TCGplayer Id, one Condition cell)
```

Grade is constant on this store: every one of the 3,502 SKU-bound cards is Near Mint grade.
That is 641 `Near Mint` and 2,319 `Near Mint Foil` Riftbound cards, and 542 `Near Mint` Pokemon
cards. D137 (the catalog is Near Mint by rule) is why. So on this store a SKU is one printing of
one product.

**What follows.** Identity derives DOWN from the SKU, never up. Name, number, rarity and set
are product facts, so every SKU of a product carries the same four. The printing is the
`Condition` suffix. The game's own vocabulary, `pipeline/variant.vocabulary` (`finishes` and
`condition_by_finish` in `pipeline/games.py`), maps it to a finish key such as `foil`. That
primitive exists, and nothing new is needed for it.

## 3. The data model

### 3.1 Three groups of facts on a card

A `+` marks a field or a table that does not exist yet.

| group | fields | written by | meaning |
|---|---|---|---|
| evidence | +`read_name`, +`read_number`, +`read_printed_total`; `detected_finish`, `confidence`; the capture claims `set_hint`, `metadata_finish`, `rarity_claim` | the identification, and the operator at the shutter | what the camera read and what the operator said. Only the next identification of the same photograph rewrites it. Never searchable (ruling 4) |
| binding | `sku`; +`bound_by`, +`bound_at`, +`identity_source`, +`read_disputes` | the one writer, section 4 | which SKU this card is, who chose it, and when |
| identity | `name`, `number`, `printed_total`, `rarity`, `set_name`, `condition`; `number_key`, `number_display` (already derived in `store/master._card_columns`) | the one writer only, from the SKU table | what the card is. Every screen and the search index read this |

`condition` moves from the binding group to the identity group. It is a SKU fact, and the one
writer copies it from the SKU table. It stays on the card because it is the key into
`listings`.

**`identity_source` has two values.** `sku`: the identity fields equal the SKU table's row.
`read`: the card has no SKU, or it is a held card from the migration (section 7), or its SKU is
absent from the table (section 3.2). In each case the identity fields equal the evidence
fields. There is no third value. A card with a SKU and `identity_source = read` is RESIDUE, and
the count of residue may only go down.

**`bound_by` names the act.** One of `join`, `answer`, `group_answer`, `correction`, `confirm`,
`migration`. It lives on the card record, bound to its `cid` (D172, the first photograph is the
name). It never lives in the position-keyed `events` table alone. **Measured why:** a human
answered position `6/53` on 2026-09-02. That card then moved, and the store captured a NEW card
at the same key on 2026-09-14. A scan of `events` by position credits the new card with the old
card's answer. A replay that scopes acts by position alone is wrong for every reused key.

**`read_disputes`** holds `pipeline/join.name_disputes(read_name, [the card's own identity
name])`. The caller computes it at each write that changes either side. It needs no export,
because the identity name is on the card. It is stored, not computed per request, because
`#/inventory` is a polled route (D213's first ground). Cost of computing it per request:
unmeasured.

### 3.2 The SKU table (ruling 5: build it now)

**Why a table, and not a live join to an export.** D213 refused a live join for `set_name` on
two grounds. The route is polled. An export ages out of `inventory/.exports/` (D166). A table
in the store answers both. A SKU lookup is one indexed probe. A row outlives the file that
brought it. So the one writer reads the table, never an export file.

**The primitives, checked first.**

| primitive | what it is | fit |
|---|---|---|
| `pipeline/pricearchive.merged_export_rows_by_sku` (D254 tier b) | every cached export merged into `sku -> row`, rebuilt from disk on each call | the right SHAPE, in memory. The table is its persisted form, and this function becomes a reader of the table |
| `pipeline/sku_name_contradictions.Catalog` (D255) | every row of one export by SKU and by name, all conditions, in memory | the same shape again. The merged report reads the table instead |
| `export_for` in `cli/cmd_cards.py` (D213 backfill) | a `sku -> (set, rarity)` walk over cached exports | the same shape a third time. Retired by the press in section 7 |
| `pipeline/join.Catalog` | one export, narrowed to the game's Near Mint rows (D137), built per join | NOT reused. It is the join's candidate universe, and its completeness is the export's (D64, D65). A table of every SKU ever seen has no completeness claim, so a join must never read candidates from it |
| `readings` table (D189) | per SKU: market, name, set, condition, source | NOT reused. It is a FULL REPLACE cache by design, so it drops a SKU whose source file goes. That is the one behaviour this table must never have |
| `listings` table (D34, D109) | per SKU: condition and the pushed, staged and live counts | NOT reused. It holds counts, no product facts. It joins to the table on the SKU |
| `pipeline/catalog.py` over `vendor/pokemon-tcg-data/catalog.sqlite` (D15, step 9) | the pokemontcg.io snapshot, Pokemon only | NOT a source. Measured: 0 cards in the 174 vendored set files carry any TCGplayer field, so no SKU and no product id. `catalog.sqlite` is also not built on the main checkout (the file is absent). It stays a possible later cross-check for Pokemon rarity and number |

So three in-memory copies of one map, SKU to its export row, already exist. The table is that
map, written down once, and the three copies become readers of it.

**The schema.** +`skus`, one D88 table (a `TableSpec` in `store/skus.py`, the shape
`store/readings.py` uses), schema version 11.

| column | holds |
|---|---|
| `key` | the `TCGplayer Id` |
| `product_line`, `set_name`, `product_name`, `number`, `rarity`, `condition` | the six fact cells, verbatim |
| `grade`, `printing` | the `Condition` cell split into its grade prefix and its printing suffix. NULL for a cell outside the five grades. Such a cell: unmeasured in the live exports' non-card lines (sleeves, playmats) |
| `first_seen`, `last_seen` | the stamp of the oldest and newest file that carried the row, from the file's own name. Never the time of the press (D166: a reuse never touches the reading's time) |
| `source` | the newest file that carried the row |
| `payload` | the whole row as read, for any column not promoted |

Indexes: `product_line`, and `(product_line, set_name, product_name, number)` for the product
layer. Two SQL views give the upper layers, with no second copy to drift. +`sku_products`
groups by product line, set, product name and number. +`sku_printings` adds `printing`. The
audit (section 4.3) reports a product whose SKUs disagree on `rarity`. Measured: 0 today.

**No `game` column.** A `Product Line` does not name one game: `pokemon` and `pokemon_code`
share `Pokemon` in `pipeline/games.py`. The game stays a per-card claim (D21). At bind time the
writer compares the card's game entry's `product_line` with the row's `product_line`. A
difference is the refusal `game_mismatch`.

**How it is filled.** An upsert, keyed on the SKU, at every place a TCGplayer export enters the
store:

1. A fetched Filtered Export (D64, D166), in `server/pipeline_routes._keep_export`, in the same
   press that keeps the file. A reuse inside D166's window adds nothing, because the file is
   already in.
2. A fetched live export (D104), in `server/pipeline_routes.do_live_export`.
3. An export a person hands the CLI: `cli/cmd_join.py`'s `--export`, and
   `./pkmnscan reconcile --live <file>`.
4. A one-time backfill press over every file already on disk: a new top-level command, `skus`,
   with a subcommand `adopt` (previews by default, `--write` applies), the shape of
   `prices adopt` and `readings adopt`. It reads `inventory/.exports/*/*.csv` and
   `inventory/.live/*.csv`.

**Measured, the backfill's reach.** Those 13 files hold 12,052 distinct SKUs (11,805 from the
exports, 858 from the live exports). They cover **916 of the 916 SKUs on the store's cards**.
They also cover **54 of the 54 SKUs in `listings` with no card** (D109). The live exports alone
cover all 54. Product lines in the union: Riftbound 10,194, Pokemon 1,812, One Piece 42, YuGiOh
2, Card Sleeves 1, Playmats 1. The table keeps a row for an unregistered product line too. A
SKU's facts do not depend on this repo's game registry.

**How it stays fresh, and why it never deletes.**

- An incoming row for a new SKU inserts.
- An incoming row whose facts equal the stored ones moves `last_seen` and `source` forward.
- An incoming row from an OLDER file than `last_seen` changes nothing. Newest wins by the
  file's own stamp, D189's rule for readings.
- An incoming row from a newer file with DIFFERENT facts writes the new facts. It also appends
  one +`sku_facts_changed` event with the old facts. Cards bound to that SKU then disagree with
  the table. The audit (4.3) names them. `cards identity --write` derives them again. Its
  preview lists each card with the old and the new identity. Measured frequency: 0 changes
  over 13 files and over the one fixture pair.
- **No row is ever deleted, whatever a card points at.** `store/skus.py` exposes an upsert and
  reads. It has no delete, no clear and no full replace. This is `price_history`'s rule (D219:
  the archive never deletes), not the rule of `readings`. A SKU that TCGplayer stops listing
  keeps its row. The audit reports it as not seen since `last_seen`, for information only.

**A SKU the table lacks.** `bind_sku` refuses `sku_unknown` and changes nothing. Three callers
always hold the row in hand. The join, the review answer and the correction read the chosen row
from an export. Each upserts that row first, in the same transaction, so each finds
it. The confirm press binds the card's current SKU, which the table already holds. The
migration measured 0 bound SKUs absent from the table. A card that still meets `sku_unknown`
keeps `identity_source = read`, with the reason on the card. `cards identity` lists it, and the
next fill plus `cards identity --write` binds it.

### 3.3 What each identity field holds after the change

- `name` holds the table's `product_name` verbatim. Screens draw it through one composer. The
  composer drops the trailing collector number TCGplayer embeds in some Pokemon names (`Stufful
  - 111/132`). The rule now lives at `store/numbers.strip_name_suffix`, over the pattern
  `store/numbers.NAME_NUMBER_SUFFIX` — moved from the leaf module's own doorstep, beside
  `join_key`, `display_number`, `strip_set_code` and `split_catalog_number`.
  `pipeline/join.name_index_key` imports the same pattern rather than keeping a second copy.
  **Measured: 150 of the 3,502 SKU-bound cards carry such a name.** A
  trailing qualifier such as `(Alternate Art)` stays on screen, because it names a different
  product (section 2). 91 SKU-bound cards carry one.
- `number` and `printed_total` hold `pipeline/join.catalog_number_fields(game, number)`.
  Section 6.
- `rarity`, `set_name` and `condition` hold the table's cells.
- The finish key (`normal`, `foil`, `holo`, `reverse_holo`) is the table's `printing` read
  through the card's game vocabulary, at read time. It is never stored twice.

### 3.4 Where the reading lives, and how it is recovered

The model's reading already lives in three places: the run's `identifications.json` (D36), the
store's `identifications` table (keyed by photograph digest), and `cards.name`/`number`. After
this change the third copy moves to `read_*`. **Measured: all 3,510 cards have an
`identifications` entry under their `cid`.** 3,506 of 3,510 cards hold a name, number and total
identical to that entry. The 4 that differ are exactly the four D252 corrections (`4/176`,
`4/442`, `6/563`, `1/75`). A correction overwrote their `name` and `number`. So the backfill
takes `read_*` from the `identifications` entry. It recovers the model's read for every card,
including the four.

**D36's warning, answered.** D36 calls the identification cache "another derived copy a future
defect could leave stale". `read_*` is a fourth copy. It is never a key and never binds a slot;
the photograph digest does that, untouched. `Inventory.record_identification` writes `read_*`
in the same call that writes the reading today, so the copy moves with its source.

## 4. The writers

### 4.1 One writer

A new method `Inventory.bind_sku` in `store/master.py` is the only code that sets `sku`, the
identity fields, `bound_by`, `bound_at` and `identity_source`. It takes the card key, the SKU,
the act (`bound_by`) and the caller's `read_disputes`. It reads the SKU's row from the SKU table
(3.2), never from an export file. It writes the identity through `catalog_number_fields` and
the composer rules above, and it appends one history event. It refuses `sku_unknown` and
`game_mismatch` and then writes nothing. A companion, `Inventory.unbind_sku`, restores a
previous binding for an undo. `Inventory.set_state` loses its `sku`, `condition`, `set_name`,
`rarity` and `name` parameters and moves state only.

`store/` imports nothing from `pipeline/`. The `import layering` row of `make docs-audit`
checks this and reads 15 files, 0 imports. So the dispute test runs in the caller, and
`bind_sku` takes its answer. A join caller refuses to bind a card whose read disputes the row.
This never fires after D253, which queues such a card. It is counted and reported if it fires.

**Lane 1 review correction, 2026-09-24.** The first pass took `number`/`printed_total` as
caller-supplied parameters, on the reasoning above. `store/` cannot import
`pipeline/games.py`, so it could not run the strategy dispatch itself. That let a caller hand
`bind_sku` any pair. `bind_sku(..., number="999", printed_total="999")`, on a row whose
`Number` cell was `024/132`, was accepted whole. The row disagreed and the write went
through anyway. The dispatch moved to `store/numbers.py`. It is keyed on the STRATEGY NAME
now, never the game. `pipeline/join.catalog_number_fields(game, raw)` is now a two-line
delegator through `games.get(game)["join_key"]`. `bind_sku`/`unbind_sku` take
`number_strategy` in place of `number`/`printed_total`. Both derive from `row.number`
themselves. A caller can no longer make this method write a value the row does not own.
There is no parameter left to hand one through. `read_disputes` keeps its original shape: it
has no row of its own to derive from, so it stays the caller's answer.
`scripts/identity-store-selftest.py`'s case 11 proves it two ways. The retired kwargs raise
`TypeError`. The wrong `number_strategy` for a game still only ever reads `row.number`,
never an arbitrary string.

### 4.2 Every writer that sets a SKU or fills the table, and what it does after

The list comes from a grep for `set_state(`, `.sku =`, `.name =`, `.number =`, `.rarity =`,
`.set_name =` and `record_identification(`. The grep covered `server/`, `store/`, `pipeline/`,
`cli/`, `identify/`, `codes/` and `scripts/`. The fill points come from the export writers in
`server/pipeline_routes.py` and the two CLI commands that take a file.

| writer | writes today | after |
|---|---|---|
| `cli/cmd_emit.run` and `cli/cmd_emit.run_merged` (the join's commit) | `set_state(sku, condition, set_name, rarity, name=D253 near-miss)` | upsert the matched rows, then `bind_sku(bound_by=join)`. D253's `JoinReport.name_corrections` retires: the identity name is the row's by construction |
| `server/capture_server.do_review_answer` (D4 candidate, D46 `from_catalog`) | `sku`, `condition`, `set_name`, `rarity`. Leaves `name` and `number` as the read | upsert the chosen row, then `bind_sku(bound_by=answer)`. This is the largest drift source: 147 human-bound cards hold a number the SKU disputes |
| `server/capture_server._reverse_answer` (D28 undo) | restores `sku`, `condition`, `set_name`, `rarity` | `unbind_sku` to the recorded previous binding |
| `server/capture_server.do_review_group_answer` (D29) | `sku`, `condition`, `set_name`, `rarity` | upsert, then `bind_sku(bound_by=group_answer)` per card |
| `server/capture_server.do_correct_answer` (D252) | `sku`, `condition`, `set_name`, `rarity`, `name`, `number`, `printed_total` | upsert, then `bind_sku(bound_by=correction)`, and the D34 release as today |
| `server/capture_server._reverse_correction` | restores the seven fields, key by key | `unbind_sku`. Section 8.3 covers old history lines |
| +`POST /inventory/<box>/<index>/confirm` | does not exist | `bind_sku(current sku, bound_by=confirm)`. Section 8 |
| `server/pipeline_routes._keep_export` (D64, D166) | keeps the fetched file | also upserts every row into the SKU table |
| `server/pipeline_routes.do_live_export` (D104) | keeps the fetched live file | also upserts every row into the SKU table |
| `cli/cmd_join.py` with `--export`, and `./pkmnscan reconcile --live <file>` | read the file | also upsert every row into the SKU table |
| `Inventory.record_identification`, called by `cli/cmd_identify.run` and `codes/scan.py` | `name`, `number`, `printed_total`, `confidence`, `detected_finish` | the same values into `read_*`. On a card with no SKU the identity follows the read. On a SKU-bound card the identity stays, and the caller recomputes `read_disputes` |
| `Inventory.move_card` (D83) | clears `sku` and `condition` on the tombstone; the transplant keeps both | unchanged. The tombstone keeps its identity as frozen history (D134); the audit exempts `moved` |
| `export_for` in `cli/cmd_cards.py` (`cards variants --write`, D213 backfill) | `set_name`, `rarity` | retired. `cards identity --write` (section 7) binds the whole identity |
| `scripts/correction-rarity-number-repair.py` | `rarity`, `number`, `printed_total` on three cards, already run (3 `rarity_number_repaired` events) | deleted after the migration. It is a one-shot repair |
| `scripts/demo-seed.py` | assigns `name`, `number`, `printed_total`, `sku` directly | fills the demo store's SKU table from its manifest, sets `read_*`, and calls `bind_sku` (section 5.9) |
| `cli/cmd_reconcile.py` listings writes (D87, D109) | `listings` rows only. Never a card's `sku` (measured by grep) | unchanged, beside the fill above |
| `server/capture_server._sell`, `do_retire` | state only | unchanged |

### 4.3 The mechanism that keeps them together

The owner asked that the two can never drift again. D173 (a rule that can be enforced is
enforced) requires a mechanism, not a sentence. Three, each proving a different half.

1. **One writer, checked by a machine.** A new `make docs-audit` row, +`identity writers`,
   reads the Python AST of `server/`, `store/`, `pipeline/`, `cli/`, `codes/` and `scripts/`.
   It fails a commit that assigns `sku`, `condition`, `name`, `number`, `printed_total`,
   `rarity` or `set_name` on a card outside the methods it allows.
   **AS BUILT (lane 7): seven methods at first, not the two this plan named — now six.**
   `bind_sku`, `unbind_sku`, `restore_identity` and `hold_sku` choose or restore an
   identity. `record_identification` and `move_card` are pre-existing, already-argued
   holdovers from earlier lanes' own review rounds. `set_state` was a third holdover,
   flagged as a deviation from this section's own "done when" line below, until D258
   closed it: every caller that passed it `sku`/`condition`/`set_name`/`rarity`/`name`
   moved to `bind_sku` or `hold_sku`, and the five parameters and the row's own membership
   were removed together. This row reconciles all six against one another. See the
   decision entry, "Identity follows the SKU", for the argument and the field. Its allow
   list is a constant exported from `store/master.py`, never a copy of it. It is trusted
   only once a planted `card.name = ...` in a fixture file turns it red.
2. **The store's own audit, part of the one merged report (ruling 6).**
   +`./pkmnscan cards identity` reads the store and the SKU table, never an export file. Three
   verdicts, D172's shape: pass, fail, not known. It fails on any of these:
   - a card bound `sku` whose identity fields differ from its table row;
   - a card or a `listings` row whose SKU is absent from the table;
   - a product whose SKUs disagree on `rarity`.
   It is a read-only press, never on the commit path, because no commit check reads the
   owner's store.
3. **The residue count.** The same report prints how many SKU-bound cards still carry
   `identity_source = read`. **NOT MECHANIZED as a ratchet:** the count lives in the owner's
   store, which no commit reads. The review queue carries each held card instead (section 7.3),
   and Home's Review tile counts it (D198).

## 5. The readers

A reader of `name`, `number`, `printed_total`, `rarity` or `set_name` is one of two kinds. **A
reader of identity** gets the SKU's facts with no code change, because the field names stay.
**A reader of evidence** must move to `read_*`, or it goes blind. It would compare the SKU's
name against the SKU's rows, and it would never find a dispute. This section names every
reader the grep found, and its kind.

### 5.1 The join: evidence, and the one reader that must not change meaning

`pipeline/join.py` compares an `IdentifiedCard`'s read name and number against catalog rows
(D146, D162, D253). It must keep comparing the READ. Three builders make an `IdentifiedCard`:

- `cli/resolve.py` builds one from a run record's `identification`. Unchanged: a run record is
  the read.
- `cli/resolve.store_payload`, the store-backed join (D188), builds `identification` from
  `card.name` and `card.number`. **It must move to `read_*`.**
- `cli/requeue.identified`, the queue refresh (D167), builds from `card.name` and
  `card.number`. **It must move to `read_*`.**

If either stays on `card.name`, the D253 check sees the SKU's own name and agrees with itself.
It then releases every disputed card it refreshes. The lane that moves them carries a mutation
arm: a disputed fixture card, refreshed through a builder that reads `name`, must turn the
check red.

The join keeps reading its candidate rows from the export, never from the SKU table (3.2).

### 5.2 Search: the catalog name only (ruling 4)

The owner ruled: "Catalog name only". Search indexes the identity, and `read_*` is evidence
that no search reads.

`cards_fts` (`store/db.py`, schema version 7) already indexes `name`, `number`, `sku`,
`set_hint`, `note`, `number_key` and `number_display`. **No FTS change is needed.** Once the
one writer puts the catalog's values into `name` and `number`, the existing update trigger
indexes them. `read_*` lives in the payload, and no trigger reads it. `note` stays indexed: an
operator types it, and it is not a reading. A card with `identity_source = read` (no SKU, or
held) is found by its identity, which for that card is still the read, exactly as today.

`server/capture_server._match_rank` needs no change: it ranks `name` and `number`, now the
catalog's. `server/capture_server.do_search` groups by SKU and returns the group's distinct
`names`. After the change a SKU group holds one name by construction. The migration's 3,450
card updates each fire the FTS update trigger once. Their total cost is unmeasured, and lane 2
times it on a copy.

### 5.3 Identity readers that change with no code

Each reads the field names that stay, and so draws the SKU's product.

| reader | what it draws |
|---|---|
| `#/inventory` copies list and section list (`BoxBrowse`, `server/capture_server._number_display`, `_card_number_key`) | product name and number |
| `#/inventory` Details (`app/src/CardHero.tsx`, `CardDetailsSection`) | product name and number, plus the new read line (5.4) |
| the landmark walk (`_walk`, D116) | a neighbour draws its product name |
| Home's recent deck (`do_inventory_recent`) | product name |
| `#/graveyard` (`do_graveyard`), box delete (`do_delete_box`) | the name at burial. Frozen history, never derived again (D134) |
| orders and the walk (`_pick_row`, `server/capture_server._walk_plan_sku_display`, `_walk_plan_take`) | product name, which now matches the buyer's order line |
| the Fulfiller's screen (`app/src/Fulfillment.tsx`) | `card.name` and `card.number_display`. No new string reaches it. Section 5.8 |
| holdings (`server/pipeline_routes.py` `_value_rows`, D236, D250) | reads the market reading's name first, the card's second. Both now agree |
| the archive subject key (`pipeline/pricearchive.py`, D234) | `number_key` composes from the catalog pair, so D234's glued-code repair has nothing to repair on a SKU-bound card |
| `#/pricing` (`server/pipeline_routes.py` `do_pipeline_worklist`) | SKU-keyed rows. Whether any row falls back to a card's name: unmeasured |

**Price history (D254) changes one line.** Tier (b) today reads
`pipeline/pricearchive.merged_export_rows_by_sku`, rebuilt from disk. It reads the SKU table
instead. Tier (c), the card's own name and number, now equals tier (b) for every SKU-bound
card. D254's order is unchanged.

### 5.4 The one new thing a screen draws

`CardDetailsSection` draws one extra line, **"Read as {read_name} {read number}"**, only when
`read_disputes` is true. A card whose read agrees draws nothing new. The Fulfiller never sees
it (D5). The words pass D196 (no decision, path or pipeline noun on screen). They raise
`#/inventory`'s visible word count only on a disputed card. Whether the D194 fixture holds one:
unmeasured. A raise of the pinned ceiling is the owner's word, never a quiet pin.

### 5.5 One report for D242 and D255 (ruling 6)

The owner ruled: "Merge them". Today D255 (`pipeline/sku_name_contradictions.py`,
`./pkmnscan cards sku-names`) compares `card.name` against the SKU's row. D242
(`pipeline/sku_number_contradictions.py`, `./pkmnscan cards contradictions`) finds one SKU with
two stored numbers. After the change both read the SKU's own values, so both read zero forever.
A guard that cannot see its subject proves nothing.

The merged report is `./pkmnscan cards identity` (4.3), with a name half and a number half. Both
halves compare `read_*` against the SKU table's row, through the join's own tests
(`pipeline/join.name_disputes`, and the number fold in section 6). Both exclude any card whose
`bound_by` is `answer`, `group_answer`, `correction` or `confirm`. A human who chose that SKU
off the photograph has already answered the report's question. Without the exclusion, the
report flags `Rell, Noxus` under `Rell, Magnetic` forever, after the owner confirmed it. A guard
that goes red when nothing is wrong is spent. The report also carries the residue count and the
three audit failures of 4.3. `cards sku-names` and `cards contradictions` retire; each prints
one line that names `cards identity`.

### 5.6 The D239 checks

`pipeline/identity_checks.py` flags misread shapes in the `name`, `number` and `set_name` it is
given (D239, four stored-data checks). It takes plain records, so it needs no change. Its one
caller, `_checks` in `cli/cmd_cards.py`, builds the records from `card.name` and `card.number`.
The caller moves to `read_*`. `set_name` stays on identity; it is a SKU fact since D213.

### 5.7 The review queue

The queue entry's own `read` block is a copy of the reading, taken when the entry is written.
It is unchanged. `app/src/ReviewQueue.tsx` draws both candidate sets off `candidates` and
`name_matched_skus` (D253), never off the reason. The one addition is a label for the new
reason in section 7.3.

### 5.8 The Fulfiller's floors

`docs/DESIGN.md`'s floors are 20px body, 32px position labels, a 320px photograph, 44px
targets, 7:1 contrast, no jargon and no route out. This change adds no element, so it touches
none of them. The name string changes. **Measured: the longest product name on a held SKU is
41 characters (`Kennen, Keeper of Balance (Alternate Art)`).** The longest read name is 152
characters (`3/987`, card rules text misread as a title). 458 cards get a longer name than
today. `make design-check` verifies the wrap at 390. This spec assumes nothing about it.

### 5.9 The demo

`scripts/demo-seed.py` copies `name`, `number`, `printed_total` and `sku` from its manifest of
real, QR-cleared cards straight onto the record. After the change it upserts the manifest's
catalog rows into the demo store's SKU table, writes `read_*` from the manifest, and binds
through `bind_sku`. The recorded wire bundle changes shape (new fields). So `make demo-record`
records it again, and `make demo-freshness` proves the bundle matches. `docs/specs/demo.md`'s
refusals stay: the static build reaches no new route, and the confirm press refuses there like
every other write.

## 6. The number, per game

`pipeline/join.catalog_number_fields` (D252's amendment) already decomposes a catalog `Number`
cell by the game's own `join_key` strategy. It is the identity number's only source. Its input
is the SKU table's `number` cell.

| game | strategy | identity `number` | identity `printed_total` | example |
|---|---|---|---|---|
| Pokemon | `number_and_printed_total` | the numerator, by `store/numbers.split_catalog_number` on the LAST `/` | the denominator | `024/132` gives `024` and `132` |
| Riftbound, One Piece | `printed_code` | the cell, verbatim | empty | `145a/219`, `OP15-003`, `T01 // T02` |
| any other | `name_only`, `not_joined`, or unknown | the cell, verbatim | empty | the safe default |

`number_key` and `number_display` stay derived in `store/master._card_columns`, the one
chokepoint every card row passes. Nothing sets them directly.

**The read number keeps its raw form.** `read_number` holds exactly what the model returned,
set code and all (`OGN • 217/298`, `UR1 / 283/219`, `319 / 482 / 166 + EN`). D55 and D67 keep
repairing and stripping it where a read is drawn or joined.

**How agreement is tested (the migration and the report).** Pokemon: `store/numbers.join_key`
of the read pair against the row's cell. Every other game: `store/numbers.strip_set_code` of
the read, then both sides through `pipeline/join.number_index_key`. This is the join's own fold.
**Measured: 590 Riftbound cards store a number string that differs from their SKU's cell.**
Most are a glued set code, which D67 already strips on screen. How many change on screen after
the change: unmeasured.

One Piece: no card on the store. The rule is Riftbound's, and it is proved on the fixture only.

## 7. The migration

### 7.1 The acceptance bar, and how the owner ruled on it

The brief's bar: **zero cards change in a way the owner has not confirmed.** Nothing may be
rewritten silently where the photograph has not been checked.

A CHANGE is the drawn identity moving to a different card. One case is the drawn name moving
to a name the read disputes. The other is the drawn number moving to a number the read does not
equal after the join's fold. A spelling change draws the same card: case, accent, a catalog
qualifier, an embedded number, or a near miss that D146's own tolerance accepts. The owner's
rulings 1 and 2 (section 12) approve the classes below that derive.

**What the migration never changes:** a SKU, a listing count, a price, a queue answer, a
photograph, a `cid`, or a reading. It fills the SKU table, writes `read_*` (a copy), the
binding bookkeeping, and the identity fields.

### 7.2 The classes, measured

Each card lands in exactly one class, tested in this order.

| class | test | cards | identity moves | spelling only | no visible change | ruling |
|---|---|---|---|---|---|---|
| T3 human | the newest human act on THIS card (answer or correction, after its own capture) chose this SKU | 612 | 177 (30 name, 139 number, 8 both) | 93 | 342 | derive; the 38 disputed names are listed once in the preview (ruling 2) |
| T5 held | the read name disputes the SKU, or is blank, and no human act | 28 | 28 (name) | 0 | 0 | held |
| T4s held | the read name agrees, the number does not, and the name names more than one product in the game's export | 24 | 24 (number) | 0 | 0 | held |
| T4u | the read name agrees, the number does not, and the name names exactly one product | 70 | 70 (number) | 0 | 0 | derive (ruling 1) |
| T1 | name equal after the fold, number equal or blank | 2,609 | 0 | 198 | 2,411 | derive |
| T2 | name a near miss, not disputed; number equal or blank | 159 | 0 | 159 | 0 | derive |
| T6 | no SKU | 8 | nothing to derive | | | unchanged |

The classes sum to 3,510. 3,450 cards derive. The 52 held cards are 42 identified and 10 sold.
T5 is 22 identified and 6 sold; 2 of the sold carry a blank read name. T4s is 20 identified
and 4 sold. Every SKU a card carries is in the SKU table after the backfill (3.2), so no card
falls to `sku_unknown`.

**Why each derives.**

- **T1, T2.** The read and the SKU name the same card. The change is spelling. No photograph
  is needed to say so. D146's tolerance (`NAME_DISPUTE_SIMILARITY`, 0.80, fitted by D251) is
  the test the join itself uses.
- **T3.** A human chose the SKU on the review screen, photo first (D4), or corrected it (D252).
  That is the photograph checked. **Measured risk: human answers are not perfect.** The store
  holds 4 `sku_corrected` events against 690 `answered` events. The owner found and corrected 4
  wrong human answers. All 4 sit in T3 under their corrected SKU. 38 T3 cards will draw a name
  their read disputes. One is `1/14`, read `Jax, Icathia` under `Jax, Unmatched`, which the
  owner confirmed. The press prints the 38 once in its preview, before `--write`.
- **T4u.** D162 already lets this evidence list a card: the owner's ruling of 2026-09-12 says a
  name that names exactly one card decides alone. The number was the misread. Example: `1/223`
  read `Aspirant's Climb` `061/298`, and the only `Aspirant's Climb` is `276/298`. The owner
  ruled that D162 covers the migration too.

**Why each is held.**

- **T5.** Two signals disagree and nobody has looked. `3/201` read `Yasuo, Ionia` under `Yasuo,
  Remorseful` `076/298`: the region line read as the title, D254's shape. `4/15` read `Dragon's
  Rage` under `Fox-Fire` `256/298`, D254's worked example. `2/365` read `Garganacl` `024` under
  `Pyroar` `024/132`.
- **T4s.** The name agrees, but it names more than one product, and the number disagrees. The
  number is the evidence that would have picked between them. Example: `1/374` read `Swain,
  Visionary` `065/100` under `065/166`.

### 7.3 The path

1. **Schema step, on open (lane 0).** Schema version 11 adds the `skus` table, its two views
   and its indexes. It also adds an indexed `identity_source` column on `cards`. The residue
   count is then one probe. The new card fields otherwise live in the payload and need no
   column. FTS is unchanged (5.2). The DDL runs inside `_upgrade`'s one transaction, the shape
   D213 used for version 8.
2. **Fill the table (lane 0): `skus adopt --write`.** Section 3.2.
3. **The press (lane 2): `./pkmnscan cards identity --write`.** It previews by default. It never
   runs at open time, for D213's reason: its answer depends on what the table holds, and that
   grows between runs.
   - For every card: backfill `read_*` from the `identifications` entry for its `cid`. Fall
     back to the card's current fields only where no entry exists (0 cards today).
   - For T1, T2, T3 and T4u: `bind_sku(bound_by=migration)`, with the class recorded on the
     event. The preview lists T3's 38 disputed names once.
   - For T4s and T5: write `identity_source = read`. Leave every identity field exactly as it
     is today. The screen draws what it draws now. **Zero held cards change.**
   - For each held card that is identified (42), open a review entry under a new reason,
     +`listing_disputed`, in `pipeline/routing.py` beside `NAME_DISPUTED`. The entry carries
     the photograph, the read, the SKU's own row, and D253's two candidate sets. Those are the
     rows the read name finds and the rows the read number finds. `Queue.upsert`
     (`store/queues.py`) accepts it, because a held card has no answered entry. Measured:
     every held card is in the no-human class. Label on screen: "Is the listing the right
     card?"
   - For each held card that is sold (10): report only (ruling 3). The report lists it. D252
     refuses to correct a departed card (`card_departed`), and the sale went out under the SKU.
   - Re-runnable. The press skips a card already bound. It also skips a card whose SKU moved
     between the preview and the write, the in-lock re-check `cards photos` already makes.
4. **Answering a held card.** Section 8.

### 7.4 The replay, before any write

A read-only replay, in D253's manner: `scripts/identity-replay.py` (lane 2). It opens a COPY of
the store through `store/db.py:open_read_only` and the on-disk exports read-only. It fills an in-memory
SKU table, runs the press's classifier and its would-be writes in memory, and prints the table
in 7.2. It asserts six things, and fails on any miss:

1. Every held card's drawn `name`, `number` and `number_display` equal today's, byte for byte.
2. No card's `sku`, `condition`, `state`, `cid` or `photo` differs. No `listings` or `queues`
   row differs, except the new `listing_disputed` entries.
3. Every card bound `sku` has identity fields equal to its SKU table row.
4. Every T3 card's SKU equals the newest human act ON THAT CARD. The replay scopes acts by the
   card's own capture time, never by position alone (the `6/53` finding, section 3.1). It does
   not credit a moved card with acts at its old key, so a moved card falls to a later class.
   That errs toward holding.
5. Every card whose drawn identity moves is in T3 or T4u.
6. Every SKU on a card or in `listings` is in the SKU table.

**The bar: zero identity moves outside T3 and T4u.** Run the replay on the day of the write.
The store moved in six minutes during this measurement.

## 8. The right SKU, the wrong name

### 8.1 After the change it is "confirm"

For a card bound `sku`, the name already follows the SKU. The drawn name is the right product
the moment the SKU is right. There is nothing to correct. The "Read as" line (5.4) keeps the
camera's version visible when it disputes.

For a held card (`identity_source = read`, a SKU the read disputes), the owner gives one of two
answers:

- **The listing is right.** +`POST /inventory/<box>/<index>/confirm` calls
  `bind_sku(current sku, bound_by=confirm)`. It releases no listing, because the SKU does not
  move. History event +`identity_confirmed`. `{"undo": true}` returns the card to
  `identity_source = read` (D28's shape).
- **The listing is the wrong card.** The D252 correction, unchanged in meaning: a new SKU, the
  old SKU released through `Listing.release` (D34), and now `bound_by=correction`.

On `#/review`, the server routes a `listing_disputed` answer inside `do_review_answer`. An
answer with the card's own current SKU goes to confirm. An answer with any other SKU goes to
the correction. The server routes it, so no screen can pick the wrong one. On `#/inventory`,
the D252 pane (`ListingCorrection` in `app/src/CardHero.tsx`) gains a second press, "The
listing is right". It draws only on a held card, inside the slot D252 already reserves (D118).

### 8.2 `sku_unchanged` stays

`do_correct_answer` refuses `sku_unchanged`, because a correction to the same SKU does nothing.
That stays true. Its refusal text now names the other press, in the operator's words: "This
card already lists as that. If the listing is right, confirm it." D196 holds.

### 8.3 Old history lines

`_reverse_correction` reads `restores_to` key by key. It restores a key only where the line
records it (D252's amendment: a missing key is not a null claim). After the change a line
records the previous binding (`sku`, `bound_by`), and `unbind_sku` derives the identity again
from the SKU table. A line written before the change still carries `name`, `number`, `rarity`
and `set_name`. `unbind_sku` ignores them and derives the identity from the SKU. The 4 real
`sku_corrected` lines on the store are the fixture for this.

## 9. Risks, and what is given up

1. **A wrong SKU now looks right.** Today a misbound card draws the camera's name, which at
   least disagrees with the listing. After the change it draws the listing's name, cleanly.
   Four things protect the outcome. D253 refuses to bind a disputing read at the join. The one
   writer refuses it too (4.1). `read_disputes` draws "Read as" in Details. Held cards stay
   drawn as read until answered. One case stays open: a wrong human answer on a card whose
   read AGREED with the wrong SKU. Its rate is unmeasured. The 4 corrections in 690 answers
   bound it from above.
2. **The camera's version leaves the lists and search (ruling 4).** Only Details draws it, and
   only when it disputes. A search for a misspelling the camera made no longer finds the card.
   The owner chose this.
3. **A TCGplayer rename.** The table takes the newer facts and keeps the old ones in an event
   (3.2). The report names the bound cards that now differ, and the press derives them again.
   Measured frequency: 0 over 13 files and one fixture pair.
4. **The table only grows.** It holds every SKU any export ever carried: 12,052 rows today.
   It grows only by SKUs it has not seen; a fetch of a known set adds no row. Disk cost on the
   owner's store: unmeasured. That is the price of never deleting.
5. **Filling on a fetch adds work to the press.** Upserting about 10,000 rows inside the fetch's
   write: cost unmeasured. Lane 0 times it on a copy of the store.
6. **The D194 word ceiling** may rise on `#/inventory` by the "Read as" line. That is the
   owner's word, never a quiet pin.
7. **Given up:** D253's near-miss name write, `cards variants`, `cards sku-names`,
   `cards contradictions`, the repair script, three in-memory SKU maps, and every per-field
   identity write in D252's route. The one writer, the one table and the one report subsume
   each, and none is lost.

## 10. Decisions this amends or cites

Each is argued as `CLAUDE.md` requires: the premise that changes, and what protects the
outcome now.

- **D213 (the set is a stored fact, and the hint was never one). AMENDED, widened.** The
  premise that changes: `name` and `number` are "what the model read", so they stay the read
  once a SKU is bound. In effect that premise failed. Measured: 64 cards draw a name their own
  listing disputes, and 241 a number. D213's rule for `set_name` and `rarity` now covers name,
  number and condition: written at the moment of binding, never a live join. The source moves
  from an export file to the SKU table, which answers D213's second ground better than a file
  can: a row outlives its export. "The hint was never a fact" generalizes: the READ was never
  one either.
- **D252 (a wrong answer gets a correct route). AMENDED.** The route upserts the chosen row and
  writes one binding through `bind_sku`, instead of seven fields. Its undo derives the identity
  again. `sku_unchanged` stays, with a new remedy text. A new sibling press, confirm, answers
  the case D252 cannot: the SKU right, the drawn name wrong. The outcome D252 protects stays
  protected: the D34 release of the old SKU is untouched, and the next live reconcile shows
  what to lower.
- **D253 (a card lists off name AND number agreeing). AMENDED in one part, kept in substance.**
  The agreement rule, D162's release and the replay stand. `JoinReport.name_corrections` and
  the `name` parameter of `set_state` retire: the identity name is the row's by construction.
  The two store-backed builders (5.1) move to `read_*`. That move is what keeps the READ name
  the thing the join checks. The premise that changes: "it does not build a second write path
  for a card's stored name". This spec replaces every such path with one.
- **D255 (one SKU, a disputing name) and D242 (one SKU, two stored numbers). AMENDED, merged
  (ruling 6).** One report, `cards identity`, reads `read_*` against the SKU table and excludes
  cards a human bound. The premise that changes: "the card's own stored name and number" are no
  longer the read. D242's original class becomes empty by construction, which is the outcome it
  protected.
- **D239 (four stored-data checks). AMENDED.** Its caller builds the name and number from
  `read_*`.
- **D254 (a product resolves from its SKU). AMENDED in one line.** Tier (b) reads the SKU table
  instead of merging cached exports on each call. The tier order and the owner's ruling stand.
- **D15 (catalog data is vendored). CITED, NOT A SOURCE.** Measured: the vendored snapshot
  carries no TCGplayer id, so it cannot fill a SKU row.
- **D64, D104, D166 (the Filtered Export and the live export are fetched; the export is a
  property of the game). CITED.** They are the table's sources. Their files stay on disk as the
  evidence for a reading, unchanged. The join keeps reading its candidates from them (D65).
- **D189 (the market reading is a table). CITED.** Its full-replace shape is refused for the
  SKU table, because a replace drops a row a card may point at. Its newest-wins rule is reused.
- **D219 (the archive never deletes). CITED.** The SKU table takes its never-delete rule.
- **D21 (game is a per-card claim). CITED.** The table holds a product line, never a game.
- **D36 (the run owns what the model read; the store owns the slot). CITED, NOT AMENDED.** The
  read stays durable and stays evidence. The digest binding of run to slot is untouched. The
  store gains a copy of the read (3.4), never used as a key.
- **D183 (a number a person reads is never a key). CITED, NOT AMENDED.** Its spirit extends: a
  number the camera read stops answering for the card's identity once a SKU binds. The machine
  key decides.
- **D172 (the first photograph is the name). CITED.** The binding's evidence rides on the card,
  bound to its `cid`, because a position key is reused (`6/53`).
- **D67 (the number a screen draws is composed once). CITED.** It keeps governing the drawn
  read. It argued against normalizing the RECORD of the read; `read_number` stays raw.
- **D162, D146 (a unique name decides; two signals release a claim). CITED, unchanged.** D162's
  standing is the argument for class T4u, and the owner applied it to the migration.
- **D137 (the catalog is Near Mint by rule). CITED.** It is why grade is constant on this store.
  If it lifts, grade already lives where it must: in the SKU table and in `condition`.

## 11. Build plan (ruling 7: straight to lanes)

Each lane is one worker. Two lanes that can run at the same time share no file. Lanes 0 and 7
both touch `CLAUDE.md`. Lane 7 depends on lane 0, so the two never run together. A lane that
"touches the store" changes the owner's `inventory/store.sqlite` the first time its code runs
there. That is a schema step on open, or a press.

| lane | files | depends on | store | screens | done when |
|---|---|---|---|---|---|
| 0. The SKU table | `store/db.py`, `store/skus.py`, `pipeline/skus.py`, `cli/cmd_skus.py`, `cli/__main__.py`, `CLAUDE.md` (the new command's line), `scripts/skus-selftest.py` | none | YES: schema 11 on open (the table, its views, `cards.identity_source`), and `skus adopt --write` | no | the self-test, over the four committed fixtures, proves: rows equal distinct ids; a second adopt changes nothing; an older file never overwrites newer facts; a changed fact writes one event and keeps the row; `store/skus.py` has no delete path. `skus adopt` on a copy of the store previews 12,052 SKUs, 916 of 916 card SKUs, 54 of 54 listing-only SKUs, and 0 conflicts. A version 10 copy opens to 11 with every card, listing and queue row unchanged. The fill of one Riftbound export is timed |
| 1. The one writer | `store/master.py`, `store/numbers.py`, `pipeline/join.py` (the review correction above: `catalog_number_fields`'s dispatch and `_NAME_NUMBER_SUFFIX` moved to `store/numbers.py`; `pipeline/join.py` keeps its public names, now delegating), `scripts/identity-store-selftest.py` | 0 | no (code only; lane 2's press writes the data) | no | the self-test proves `bind_sku` writes identity equal to a table row for Pokemon, Riftbound and a token cell `T01 // T02`, and `unbind_sku` round-trips it. It refuses `sku_unknown` and `game_mismatch` and writes nothing. `record_identification` writes only `read_*` on a bound card. `set_state` takes no identity field. A caller cannot make `bind_sku` write a number the SKU row does not own (case 11). `make harness` is green |
| 2. The press, the merged report, the replay | `cli/cmd_cards.py`, `pipeline/identity_binding.py`, `scripts/identity-replay.py`, `pipeline/sku_name_contradictions.py`, `pipeline/sku_number_contradictions.py`, `cli/cmd_sku_name_contradictions.py`, `cli/cmd_sku_contradictions.py`, `scripts/sku-name-contradictions-selftest.py`, `scripts/sku-number-contradictions-selftest.py`, `pipeline/routing.py`, `app/src/ReviewQueue.tsx` (the new reason's label only) | 0, 1 | YES: `cards identity --write` is the data migration | YES: the one label on `#/review`, at 1440, 820 and 390, light and dark | the self-tests prove every class and its order, the human-bound exclusion, and both report halves. The replay on a copy prints section 7.2 and passes all six asserts. After `--write` on a second copy, the replay reads 52 residue and zero identity moves outside T3 and T4u. The FTS trigger cost of the write is timed. The `reason codes` and `reason emissions` rows of `make docs-audit` are green |
| 3a. The server | `server/capture_server.py`, `server/pipeline_routes.py`, `harness/tests/t7_store_and_seams.py` | 0, 1, 2 | no (code only) | no | T7 proves: each server writer in 4.2 upserts, then leaves identity equal to its table row and `read_*` untouched. Both fetches fill the table. The confirm route and its undo work. A `listing_disputed` answer routes to confirm or to the correction. D252's checks still pass, with the four real history-line shapes as fixtures. `make harness` is green |
| 3b. The CLI writers | `cli/cmd_emit.py`, `cli/cmd_identify.py`, `cli/cmd_join.py`, `cli/cmd_reconcile.py`, `codes/scan.py`, `scripts/identity-cli-selftest.py` | 0, 1 | no (code only) | no | the self-test proves: an emit binds through `bind_sku` and upserts first; a re-identification writes only `read_*` on a bound card; `--export` and `reconcile --live` fill the table. `harness/tests/t3_join_coverage.py` stays green |
| 4. The evidence readers | `cli/requeue.py`, `cli/resolve.py`, `pipeline/pricearchive.py` | 0, 1 | no | no | one mutation arm per builder: a builder that reads `name` instead of `read_name` lets a disputed fixture card through, and the check goes red. D254's tier (b) from the table gives the same product for the 914 card-covered SKUs D254 measured as the merged-export map does, on a copy. `harness/tests/t3_join_coverage.py` stays green |
| 5. The screens | `app/src/types.ts`, `app/src/server.ts`, `app/src/CardHero.tsx`, new or changed specs under `app/tests/` | 3a | no | YES: `#/inventory` Details and its new press, plus a look at `#/fulfillment`, `#/orders`, `#/review` and Home, at 1440, 820 and 390, light and dark | `npx tsc --noEmit` prints nothing. `make design-check` is green, with the Fulfillment floors and the press-stability sweep of `inventory.spec.ts` (D118) over the new press. The D194 and D196 rows are green, or the ceiling raise goes to the owner |
| 6. The demo | `scripts/demo-seed.py` | 0, 1, 5 | the demo store only | YES: the demo build at the three widths, both themes | `make demo`, then `make demo-freshness`, agree |
| 7. The guard and the record | `scripts/docs-audit.py`, `Makefile` (wires the new self-tests into `make check`), a new decision entry under a slug (its number claimed at merge), amendment notes on D213, D239, D242, D252, D253, D254 and D255, `CLAUDE.md`, and `scripts/correction-rarity-number-repair.py`, which it deletes | 0, 2, 3a, 3b, 4 | no | no | the `identity writers` row goes red on a planted assignment and green on the tree. The `check census` and `check registry` rows are green with the new self-tests. `make docs-audit` is green |

**The order.** Lane 0 goes first, then lane 1. Lanes 2, 3b and 4 then run in parallel. Lane 3a
follows lane 2, which owns the new reason. Lane 5 follows lane 3a, which owns the wire. Lane 6
follows lane 5. Lane 7 follows lanes 2, 3a, 3b and 4, because its row stays red until every
writer moves.

**On the owner's store.** Lane 0's schema step runs the first time a merged build opens the
store. The two presses run only on the owner's word, in this order. First, `skus adopt
--write`. Second, the replay; the owner reads its table on the day. Third, `cards identity
--write`.

## 12. The owner's rulings, 2026-09-24

All seven questions are ANSWERED. The owner's words are quoted.

1. **ANSWERED: "Yes, derive them".** A change is the identity moving, not the spelling. D162
   covers T4u's 70 cards. The held count stays 52.
2. **ANSWERED: "Derive, list once".** T3's 38 disputed names derive. The press's preview lists
   them once.
3. **ANSWERED: "Report only".** The 10 held sold cards stay drawn as read, in the report.
4. **ANSWERED: "Catalog name only".** This overrides the first draft's recommendation. Search
   indexes the catalog name only, and `read_*` is not searchable (5.2).
5. **ANSWERED: "yes I'd been saying we build this".** The store-owned SKU table is built now, as
   lane 0 (3.2).
6. **ANSWERED: "Merge them".** D242 and D255 become one report, `cards identity` (5.5).
7. **ANSWERED: "Straight to lanes".** No `OPEN` step. Section 11 is the plan.

## Appendix: how the measurements were taken

All read-only. The store copy came from `sqlite3 -readonly ... ".backup <copy>"`, opened with
`mode=ro&immutable=1`. Python's `csv` module read the exports. The comparison imported the
repo's own functions and restated none: `pipeline/join.name_disputes`,
`pipeline/join._name_compare_key`, `pipeline/join.number_index_key`,
`store/numbers.strip_set_code` and `store/numbers.join_key`. Human acts are the `answered`,
`unanswered`, `sku_corrected` and `sku_correction_undone` events after each card's own
`captured_at`. The SKU-table reach read every CSV under `inventory/.exports/` and
`inventory/.live/`. The vendored-catalog check read every file under
`vendor/pokemon-tcg-data/cards/en/`. The scripts lived in a session scratchpad and are not
committed. Lane 2's replay is their durable, reviewed form.
