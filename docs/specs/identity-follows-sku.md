# A card's identity follows its SKU

**Status, 2026-09-24. SPECIFIED, NOT BUILT. The owner approves this spec before any lane
starts.** Nothing here writes the store. Every number below was measured read-only. The store
source is a `sqlite3 -readonly` backup copy of `inventory/store.sqlite`, taken 2026-09-24 11:58
local. The export sources are the owner's two cached exports: `inventory/.exports/riftbound/`
(2026-09-14, 10,191 rows) and `inventory/.exports/pokemon/` (2026-09-19, 1,614 rows). The store
moves under a measurement: the owner corrected `1/75` six minutes before the copy. Re-measure on
the day of any build (section 7.4).

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
cell. The model's reading stays on the card as evidence, under its own name. Once a SKU is
bound, the reading never again answers for the card's identity.

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

**The `Condition` cell is two facts fused: a grade and a printing.**

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

**SKU facts are stable over the one pair measured.** 10,078 Riftbound SKUs appear in both the
committed fixture and the owner's 2026-09-14 export. 0 of them changed any of Product Line, Set
Name, Product Name, Number, Rarity or Condition. The two Pokemon files share no SKU, so Pokemon
stability is unmeasured.

**The owner's case, on his own store.** 832 distinct products are held. **84 of them are held
under two SKUs, one Near Mint and one Near Mint Foil, across 317 cards.** Example: Vendetta
`Baccai Sandspinner` `001/166` Common, 2 copies under 9422134 (Near Mint) and 2 under 9446030
(Near Mint Foil). Name, number, rarity and set are equal for both. Only the printing differs. A
second shape: five Showcase runes (`Mind Rune (R03a)` and four more) are held in two sets with
equal name, number and rarity. Only the set differs.

**The layers, named.**

```
product   = game x set x product name x number x rarity      (name, number, rarity, set)
printing  = product x finish                                 (the Condition suffix)
SKU       = printing x grade                                 (TCGplayer Id, one Condition cell)
```

Grade is constant on this store: every one of the 3,502 SKU-bound cards is Near Mint grade.
That is 641 `Near Mint` and 2,319 `Near Mint Foil` Riftbound cards, and 542 `Near Mint` Pokemon
cards. D137 (the catalog is Near Mint by rule) is why. So on this store a SKU is one printing of
one product.

**What follows.** Identity derives DOWN from the SKU, never up. Name, number, rarity and set
are product facts, so every SKU of a product carries the same four. The printing derives from
`condition` through the game's own vocabulary, `pipeline/variant.vocabulary` (`finishes` and
`condition_by_finish` in `pipeline/games.py`), inverted. The primitive exists; nothing new is
needed for it. No new column holds the printing, because `condition` already holds it, and
`condition` is the key into `listings`.

## 3. The data model

### 3.1 Three groups of facts on a card

A `+` marks a field that does not exist yet.

| group | fields | written by | meaning |
|---|---|---|---|
| evidence | +`read_name`, +`read_number`, +`read_printed_total`; `detected_finish`, `confidence`; the capture claims `set_hint`, `metadata_finish`, `rarity_claim` | the identification, and the operator at the shutter | what the camera read and what the operator said. Only the next identification of the same photograph rewrites it |
| binding | `sku`, `condition`; +`bound_by`, +`bound_at`, +`identity_source`, +`read_disputes` | the one writer, section 4 | which catalog row this card is, who chose it, and when |
| identity | `name`, `number`, `printed_total`, `rarity`, `set_name`; `number_key`, `number_display` (already derived in `store/master._card_columns`) | the one writer only | what the card is. Every screen reads this |

**`identity_source` has two values.** `sku`: the identity fields equal the SKU's own row.
`read`: the card has no SKU, or it is a held card from the migration (section 7), and the
identity fields equal the evidence fields. There is no third value. A card with a SKU and
`identity_source = read` is RESIDUE, and the count of residue may only go down.

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

### 3.2 Stored at write, not joined at read

**Considered and refused: a live join from SKU to export on every read.** D213 refused this for
`set_name` on two grounds, and both still hold. The route is polled. An export ages out of
`inventory/.exports/` (D166), and a name that vanishes with it is worse than a stored one. So
identity is MATERIALIZED: a pure function of the SKU's catalog row. One writer writes it at the
moment the SKU is bound, and an audit checks it (section 4.3). "Derived" in this spec means
exactly that.

**Considered and deferred: a store-owned SKU table.** One row per SKU: product line, set,
product name, number, rarity, condition, first seen, last seen. Every export the store reads
fills it, and nothing clears it, in the manner of `price_history` (D219). It would let the audit
and D254's tier (b) run with no export on disk, and it would catch a TCGplayer rename. The
owner's outcome does not need it: the materialized fields already survive an export aging out.
Open question 4.

### 3.3 What each field holds after the change

- `name` holds the SKU row's `Product Name` verbatim. Screens draw it through one composer. The
  composer drops the trailing collector number TCGplayer embeds in some Pokemon names (`Stufful
  - 111/132`). The rule exists as `pipeline/join._NAME_NUMBER_SUFFIX`. It moves to the leaf
  module `store/numbers.py`, beside `join_key`, `display_number`, `strip_set_code` and
  `split_catalog_number`. **Measured: 150 of the 3,502 SKU-bound cards carry such a name.** A
  trailing qualifier such as `(Alternate Art)` stays on screen, because it names a different
  product (section 2). 91 SKU-bound cards carry one.
- `number` and `printed_total` hold `pipeline/join.catalog_number_fields(game, row Number)`.
  Section 6.
- `rarity` and `set_name` hold the SKU row's cells, as D213 already writes them.
- The printing is `condition` read through the game vocabulary, at read time. It is a pure
  lookup on a short string, and it is never stored twice.

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

A new method `Inventory.bind_sku` in `store/master.py` is the only code that sets `sku`,
`condition`, the identity fields, `bound_by`, `bound_at` and `identity_source`. It takes the
card key, the catalog row, the game, the act (`bound_by`) and the caller's `read_disputes`. It
writes the identity from the row through `catalog_number_fields` and the composer rules above.
It appends one history event. A companion, `Inventory.unbind_sku`, restores a previous binding
for an undo. `Inventory.set_state` loses its `sku`, `condition`, `set_name`, `rarity` and `name`
parameters and moves state only.

`store/` imports nothing from `pipeline/` (measured: no such import in `store/*.py`). So the
dispute test runs in the caller, and `bind_sku` takes its answer. A join caller refuses to bind
a card whose read disputes the row. This never fires after D253, which queues such a card. It
is counted and reported if it fires.

### 4.2 Every writer that sets a SKU today, and what it does after

The list comes from a grep for `set_state(`, `.sku =`, `.name =`, `.number =`, `.rarity =`,
`.set_name =` and `record_identification(`. The grep covered `server/`, `store/`, `pipeline/`,
`cli/`, `identify/`, `codes/` and `scripts/`.

| writer | writes today | after |
|---|---|---|
| `cli/cmd_emit.run` and `cli/cmd_emit.run_merged` (the join's commit) | `set_state(sku, condition, set_name, rarity, name=D253 near-miss)` | `bind_sku(bound_by=join)`. D253's `JoinReport.name_corrections` retires: the identity name is the row's by construction |
| `server/capture_server.do_review_answer` (D4 candidate, D46 `from_catalog`) | `sku`, `condition`, `set_name`, `rarity`. Leaves `name` and `number` as the read | `bind_sku(bound_by=answer)`. This is the largest drift source: 147 human-bound cards hold a number the SKU disputes |
| `server/capture_server._reverse_answer` (D28 undo) | restores `sku`, `condition`, `set_name`, `rarity` | `unbind_sku` to the recorded previous binding |
| `server/capture_server.do_review_group_answer` (D29) | `sku`, `condition`, `set_name`, `rarity` | `bind_sku(bound_by=group_answer)` per card |
| `server/capture_server.do_correct_answer` (D252) | `sku`, `condition`, `set_name`, `rarity`, `name`, `number`, `printed_total` | `bind_sku(bound_by=correction)`, and the D34 release as today |
| `server/capture_server._reverse_correction` | restores the seven fields, key by key | `unbind_sku`. Section 8.3 covers old history lines |
| +`POST /inventory/<box>/<index>/confirm` | does not exist | `bind_sku(current sku, bound_by=confirm)`. Section 8 |
| `Inventory.record_identification`, called by `cli/cmd_identify.run` and `codes/scan.py` | `name`, `number`, `printed_total`, `confidence`, `detected_finish` | the same values into `read_*`. On a card with no SKU the identity follows the read. On a SKU-bound card the identity stays, and the caller recomputes `read_disputes` |
| `Inventory.move_card` (D83) | clears `sku` and `condition` on the tombstone; the transplant keeps both | unchanged. The tombstone keeps its identity as frozen history (D134); the audit exempts `moved` |
| `cli/cmd_cards.py` `export_for` (`cards variants --write`, D213 backfill) | `set_name`, `rarity` | superseded by `cards identity --write` (section 7), which binds the whole identity |
| `scripts/correction-rarity-number-repair.py` | `rarity`, `number`, `printed_total` on three cards, already run (3 `rarity_number_repaired` events) | retired after the migration. It is a one-shot repair |
| `scripts/demo-seed.py` | assigns `name`, `number`, `printed_total`, `sku` directly | sets `read_*` and calls `bind_sku` (section 5.10) |
| `cli/cmd_reconcile.py` (D87 live reconcile, D109 listings with no card) | `listings` rows only. Never a card's `sku` (measured by grep) | unchanged. 54 listings name a SKU no card holds; they have no card to derive onto |
| `server/capture_server._sell`, `do_retire` | state only | unchanged |

### 4.3 The mechanism that keeps them together

The owner asked that the two can never drift again. D173 (a rule that can be enforced is
enforced) requires a mechanism, not a sentence. Three, each proving a different half.

1. **One writer, checked by a machine.** A new `make docs-audit` row, +`identity writers`,
   reads the Python AST of `server/`, `store/`, `pipeline/`, `cli/`, `codes/` and `scripts/`.
   It fails a commit that assigns `sku`, `condition`, `name`, `number`, `printed_total`,
   `rarity` or `set_name` on a card outside the two methods it allows. Its allow list is a
   constant exported from `store/master.py`, never a copy of it. It is trusted only once a
   planted `card.name = ...` in a fixture file turns it red.
2. **The store's own audit.** +`./pkmnscan cards identity` reads every card with
   `identity_source = sku`. It compares the identity fields against the SKU's row in the
   newest cached export. Three verdicts, D172's shape: pass, fail, not known (no export, or the
   SKU is absent). It is a read-only press, like `cards audit`, never on the commit path,
   because no commit check reads the owner's store.
3. **The residue count.** The same press prints how many SKU-bound cards still carry
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

### 5.2 Search: identity first, evidence second

`cards_fts` (`store/db.py`, schema version 7) indexes `name`, `number`, `sku`, `set_hint`,
`note`, `number_key` and `number_display`. After the change `name` indexes the product name. A
new FTS column `read_name` indexes the reading. The trigger reads it out of the payload by
`json_extract`, exactly as it already reads `note`. `server/capture_server._match_rank` ranks
identity as today. It places `read_name` in the substring pass only, beside `note`. So a camera
misspelling can still find a card, and it never outranks a product name. Rebuilding the index
is a schema step (section 11, lane 1). Its cost on 3,510 cards is unmeasured.

`server/capture_server.do_search` groups by SKU and returns the group's distinct `names`. After
the change a SKU group holds one name by construction.

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
| the Fulfiller's screen (`app/src/Fulfillment.tsx`) | `card.name` and `card.number_display`. No new string reaches it. Section 5.9 |
| holdings (`server/pipeline_routes.py` `_value_rows`, D236, D250) | reads the market reading's name first, the card's second. Both now agree |
| price history (`pipeline/pricehistory.py`, D254) | tier (c), the card's own name and number, now equals tier (b) for every SKU-bound card. D254's order is unchanged |
| the archive subject key (`pipeline/pricearchive.py`, D234) | `number_key` composes from the catalog pair, so D234's glued-code repair has nothing to repair on a SKU-bound card |
| `#/pricing` (`server/pipeline_routes.py` `do_pipeline_worklist`) | SKU-keyed rows. Whether any row falls back to a card's name: unmeasured |

### 5.4 The one new thing a screen draws

`CardDetailsSection` draws one extra line, **"Read as {read_name} {read number}"**, only when
`read_disputes` is true. A card whose read agrees draws nothing new. The Fulfiller never sees
it (D5). The words pass D196 (no decision, path or pipeline noun on screen). They raise
`#/inventory`'s visible word count only on a disputed card. Whether the D194 fixture holds one:
unmeasured. A raise of the pinned ceiling is the owner's word, never a quiet pin.

### 5.5 The D255 report (one SKU, a disputing name)

`pipeline/sku_name_contradictions.py` reads `card.name` against the SKU row. After the change
that is the SKU's own name, so the report reads zero forever. A guard that cannot see its
subject proves nothing. **It moves to `read_name`.** It also excludes any card whose `bound_by`
is `answer`, `group_answer`, `correction` or `confirm`. A human who chose that SKU off the
photograph has already answered the report's question. Without the exclusion, the report flags
`Rell, Noxus` under `Rell, Magnetic` forever, after the owner confirmed it. A guard that goes
red when nothing is wrong is spent.

### 5.6 The D242 report (one SKU, two stored numbers)

`pipeline/sku_number_contradictions.py` finds one SKU carrying two stored numbers. After the
change the identity number is one per SKU by construction, so the class is empty. It moves to
`read_number` with the same exclusion, and it becomes the number half of the D255 report. Open
question 6 asks whether the two merge into one `cards identity` report.

### 5.7 The D239 checks

`pipeline/identity_checks.py` flags suspicious shapes in stored `name`, `number` and
`set_name` (D239, four stored-data checks). The shapes are misread shapes. The `name` and
`number` reads move to `read_*`. The `set_name` read stays on identity; it is a SKU fact since
D213.

### 5.8 The review queue

The queue entry's own `read` block is a copy of the reading, taken when the entry is written.
It is unchanged. `app/src/ReviewQueue.tsx` draws both candidate sets off `candidates` and
`name_matched_skus` (D253), never off the reason. The one addition is a label for the new
reason in section 7.3.

### 5.9 The Fulfiller's floors

`docs/DESIGN.md`'s floors are 20px body, 32px position labels, a 320px photograph, 44px
targets, 7:1 contrast, no jargon and no route out. This change adds no element, so it touches
none of them. The name string changes. **Measured: the longest product name on a held SKU is
41 characters (`Kennen, Keeper of Balance (Alternate Art)`).** The longest read name is 152
characters (`3/987`, card rules text misread as a title). 458 cards get a longer name than
today. `make design-check` verifies the wrap at 390. This spec assumes nothing about it.

### 5.10 The demo

`scripts/demo-seed.py` copies `name`, `number`, `printed_total` and `sku` from its manifest of
real, QR-cleared cards straight onto the record. After the change it writes `read_*` from the
manifest and binds through `bind_sku`. The recorded wire bundle changes shape (new fields). So
`make demo-record` records it again, and `make demo-freshness` proves the bundle matches.
`docs/specs/demo.md`'s refusals stay: the static build reaches no new route, and the confirm
press refuses there like every other write.

## 6. The number, per game

`pipeline/join.catalog_number_fields` (D252's amendment) already decomposes a catalog `Number`
cell by the game's own `join_key` strategy. It is the identity number's only source.

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

**How agreement is tested (the migration and the audit).** Pokemon: `store/numbers.join_key`
of the read pair against the row's cell. Every other game: `store/numbers.strip_set_code` of
the read, then both sides through `pipeline/join.number_index_key`. This is the join's own fold.
**Measured: 590 Riftbound cards store a number string that differs from their SKU's cell.**
Most are a glued set code, which D67 already strips on screen. How many change on screen after
the change: unmeasured.

One Piece: no card on the store. The rule is Riftbound's, and it is proved on the fixture only.

## 7. The migration

### 7.1 The acceptance bar, and how this spec reads it

The brief's bar: **zero cards change in a way the owner has not confirmed.** Nothing may be
rewritten silently where the photograph has not been checked.

This spec reads a CHANGE as the drawn identity moving to a different card. One case is the
drawn name moving to a name the read disputes. The other is the drawn number moving to a number
the read does not equal after the join's fold. A spelling change draws the same card: case,
accent, a catalog qualifier, an embedded number, or a near miss that D146's own tolerance
accepts. The owner's
word of 2026-09-23 confirms the RULE; it does not confirm any single card. **This reading is
open question 1.**

**What the migration never changes:** a SKU, a condition, a listing count, a price, a queue
answer, a photograph, a `cid`, or a reading. It writes `read_*` (a copy), the binding
bookkeeping, and the identity fields.

### 7.2 The classes, measured

Each card with a SKU lands in exactly one class, tested in this order.

| class | test | cards | identity moves | spelling only | no visible change |
|---|---|---|---|---|---|
| T3 human | the newest human act on THIS card (answer or correction, after its own capture) chose this SKU | 612 | 177 (30 name, 139 number, 8 both) | 93 | 342 |
| T5 held | the read name disputes the SKU, or is blank, and no human act | 28 | 28 (name) | 0 | 0 |
| T4s held | the read name agrees, the number does not, and the name names more than one product in the game's export | 24 | 24 (number) | 0 | 0 |
| T4u | the read name agrees, the number does not, and the name names exactly one product | 70 | 70 (number) | 0 | 0 |
| T1 | name equal after the fold, number equal or blank | 2,609 | 0 | 198 | 2,411 |
| T2 | name a near miss, not disputed; number equal or blank | 159 | 0 | 159 | 0 |
| T6 | no SKU, or the SKU is absent from the export | 8 | nothing derives | | |

The classes sum to 3,510. By state, the 52 held cards are 42 identified and 10 sold. T5 is 22
identified and 6 sold; 2 of the sold carry a blank read name. T4s is 20 identified and 4 sold.

**Why each derives.**

- **T1, T2.** The read and the SKU name the same card. The change is spelling. No photograph
  is needed to say so. D146's tolerance (`NAME_DISPUTE_SIMILARITY`, 0.80, fitted by D251) is
  the test the join itself uses.
- **T3.** A human chose the SKU on the review screen, photo first (D4), or corrected it (D252).
  That is the photograph checked. **Measured risk: human answers are not perfect.** The store
  holds 4 `sku_corrected` events against 690 `answered` events. The owner found and corrected 4
  wrong human answers. All 4 sit in T3 under their corrected SKU. 38 T3 cards will draw a name
  their read disputes. One is `1/14`, read `Jax, Icathia` under `Jax, Unmatched`, which the
  owner confirmed. Open question 2.
- **T4u.** D162 already lets this evidence list a card: the owner's ruling of 2026-09-12 says a
  name that names exactly one card decides alone. The number was the misread. Example: `1/223`
  read `Aspirant's Climb` `061/298`, and the only `Aspirant's Climb` is `276/298`. D162's own
  standing is 209 of 209 on its measured shapes. Open question 1 asks whether that standing
  covers a migration too.

**Why each is held.**

- **T5.** Two signals disagree and nobody has looked. `3/201` read `Yasuo, Ionia` under `Yasuo,
  Remorseful` `076/298`: the region line read as the title, D254's shape. `4/15` read `Dragon's
  Rage` under `Fox-Fire` `256/298`, D254's worked example. `2/365` read `Garganacl` `024` under
  `Pyroar` `024/132`.
- **T4s.** The name agrees, but it names more than one product, and the number disagrees. The
  number is the evidence that would have picked between them. Example: `1/374` read `Swain,
  Visionary` `065/100` under `065/166`.

### 7.3 The path

1. **Schema step, on open (lane 1).** The new payload fields need no column. `identity_source`
   becomes an indexed column, so the residue count is one probe. `cards_fts` gains `read_name`,
   its three triggers change, and the index is rebuilt once. The DDL and the rebuild run inside
   `_upgrade`'s one transaction, the shape D213 used for version 8. Schema version 11.
2. **The press (lane 2): `./pkmnscan cards identity`.** It previews by default, and `--write`
   applies. It never runs at open time, for D213's reason: it reads an export, and the export
   on disk changes between runs.
   - For every card: backfill `read_*` from the `identifications` entry for its `cid`. Fall
     back to the card's current fields only where no entry exists (0 cards today).
   - For T1, T2, T3, and T4u if the owner says so: `bind_sku(bound_by=migration)` from the
     SKU's row, with the class recorded on the event.
   - For T4s and T5: write `identity_source = read`. Leave every identity field exactly as it
     is today. The screen draws what it draws now. **Zero held cards change.**
   - For each held card that is identified, open a review entry under a new reason,
     +`listing_disputed`, in `pipeline/routing.py` beside `NAME_DISPUTED`. The entry carries
     the photograph, the read, the SKU's own row, and D253's two candidate sets. Those are the
     rows the read name finds and the rows the read number finds. `Queue.upsert`
     (`store/queues.py`) accepts it, because a held card has no answered entry. Measured:
     every held card is in the no-human class. Label on screen: "Is the listing the right
     card?"
   - For each held card that is sold (10): report only. D252 refuses to correct a departed card
     (`card_departed`), and the sale went out under the SKU. Open question 3.
   - Re-runnable. The press skips a card already bound. It also skips a card whose SKU moved
     between the preview and the write, the in-lock re-check `cards variants` already makes.
3. **Answering a held card.** Section 8.

### 7.4 The replay, before any write

A read-only replay, in D253's manner: `+scripts/identity-replay.py` (lane 2). It opens a COPY of
the store with `mode=ro&immutable=1` and the cached exports read-only. It runs the press's
classifier and its would-be writes in memory, and prints the table in 7.2. It asserts five
things, and fails on any miss:

1. Every held card's drawn `name`, `number` and `number_display` equal today's, byte for byte.
2. No card's `sku`, `condition`, `state`, `cid` or `photo` differs. No `listings` or `queues`
   row differs, except the new `listing_disputed` entries.
3. Every card bound `sku` has identity fields equal to its SKU row.
4. Every T3 card's SKU equals the newest human act ON THAT CARD. The replay scopes acts by the
   card's own capture time, never by position alone (the `6/53` finding, section 3.1). It does
   not credit a moved card with acts at its old key, so a moved card falls to a later class.
   That errs toward holding.
5. Every card whose drawn identity moves is in a class the owner approved.

**The bar: zero identity moves outside the approved classes.** Run the replay on the day of the
write. The store moved in six minutes during this measurement.

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
records the previous binding (`sku`, `condition`, `bound_by`), and `unbind_sku` derives the
identity again from it. A line written before the change still carries `name`, `number`,
`rarity` and `set_name`. `unbind_sku` ignores them and derives the identity from the SKU. The 4
real `sku_corrected` lines on the store are the fixture for this.

## 9. Risks, and what is given up

1. **A wrong SKU now looks right.** Today a misbound card draws the camera's name, which at
   least disagrees with the listing. After the change it draws the listing's name, cleanly.
   Four things protect the outcome. D253 refuses to bind a disputing read at the join. The one
   writer refuses it too (4.1). `read_disputes` draws "Read as" in Details. Held cards stay
   drawn as read until answered. One case stays open: a wrong human answer on a card whose
   read AGREED with the wrong SKU. Its rate is unmeasured. The 4 corrections in 690 answers
   bound it from above.
2. **The camera's version leaves the lists.** Only Details draws it, and only when it disputes.
   Search still finds it (5.2).
3. **A SKU with no export row cannot bind.** It stays `identity_source = read` with its reason.
   The press answers it again once an export arrives, D213's own precedent. 8 cards today.
4. **A TCGplayer rename leaves a stored name stale.** Measured: 0 renames in 10,078 SKUs over
   one pair of files. The audit (4.3) reads the newest export and fails on any. The deferred
   SKU table (3.2) is the durable answer.
5. **The FTS rebuild** runs once, at open, in the owner's store. Cost unmeasured; lane 1
   measures it on a copy before merge.
6. **The D194 word ceiling** may rise on `#/inventory` by the "Read as" line. That is the
   owner's word, never a quiet pin.
7. **Given up:** D253's near-miss name write, `cards variants`, the repair script, and every
   per-field identity write in D252's route. The one writer subsumes each, and none is lost.

## 10. Decisions this amends or cites

Each is argued as `CLAUDE.md` requires: the premise that changes, and what protects the
outcome now.

- **D213 (the set is a stored fact, and the hint was never one). AMENDED, widened.** The
  premise that changes: `name` and `number` are "what the model read", so they stay the read
  once a SKU is bound. In effect that premise failed. Measured: 64 cards draw a name their own
  listing disputes, and 241 a number. D213's rule for `set_name` and `rarity` now covers name
  and number: written from the SKU's row at the moment of binding, never a live join. D213's
  two grounds against a live join still hold and still govern (3.2). "The hint was never a
  fact" generalizes: the READ was never one either.
- **D252 (a wrong answer gets a correct route). AMENDED.** The route writes one binding through
  `bind_sku` instead of seven fields. Its undo derives the identity again. `sku_unchanged`
  stays, with a new remedy text. A new sibling press, confirm, answers the case D252 cannot:
  the SKU right, the drawn name wrong. The outcome D252 protects stays protected: the D34
  release of the old SKU is untouched, and the next live reconcile shows what to lower.
- **D253 (a card lists off name AND number agreeing). AMENDED in one part, kept in substance.**
  The agreement rule, D162's release and the replay stand. `JoinReport.name_corrections` and
  the `name` parameter of `set_state` retire: the identity name is the row's by construction.
  The two store-backed builders (5.1) move to `read_*`. That move is what keeps the READ name
  the thing the join checks. The premise that changes: "it does not build a second write path
  for a card's stored name". This spec replaces every such path with one.
- **D255 (one SKU, a disputing name). AMENDED.** Reads `read_name`. Excludes cards a human
  bound. Becomes the residue's report. The premise that changes: "the card's own stored `name`"
  is no longer the read.
- **D242 (one SKU, two stored numbers). AMENDED.** Reads `read_number`, with D255's exclusion.
  Its original class becomes empty by construction, which is the outcome it protected.
- **D239 (four stored-data checks). AMENDED.** The name and number checks read `read_*`.
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
  standing is the argument for class T4u.
- **D137 (the catalog is Near Mint by rule). CITED.** It is why grade is constant on this store.
  If it lifts, grade already lives where it must, in `condition`.
- **D254 (a product resolves from its SKU). CITED, unchanged.** Its tier (c) becomes equal to
  tier (b) for every SKU-bound card.

## 11. Build plan

Lanes run in the order given. Files are disjoint between lanes. Each lane is one worker.

| lane | files | store migration | screens | done when |
|---|---|---|---|---|
| 1. The model and the one writer | `store/master.py`, `store/db.py`, `store/numbers.py`, `harness/tests/t7_store_and_seams.py` | YES: schema 11 on open (column, FTS column, triggers, rebuild) | no | T7 proves `bind_sku` writes identity equal to a real fixture row, for Pokemon, Riftbound and a token cell, round trip through `unbind_sku`. `record_identification` writes only `read_*` on a bound card. A store at version 10 opens to 11 with every card intact. The FTS rebuild is timed on a copy of the owner's store. `make harness` is green |
| 2. The press and the replay | `cli/cmd_cards.py`, `+pipeline/identity_binding.py`, `+scripts/identity-replay.py`, `pipeline/routing.py`, and a self-test beside it | YES: `cards identity --write` is the data migration | no | a self-test on literal rows proves every class and its order. The replay on a copy prints section 7.2 and passes all five asserts. After `--write` on a second copy, the replay reads zero residue outside the held classes |
| 3. The server writers | `server/capture_server.py`, `server/pipeline_routes.py`, `cli/cmd_emit.py`, `cli/cmd_identify.py`, `codes/scan.py` | no | no | T7 extended: each writer in 4.2 leaves identity equal to its row and `read_*` untouched. The confirm route and its undo work. A `listing_disputed` answer routes to confirm or to the correction. D252's existing checks still pass, with the four real history-line shapes as fixtures. `make harness` is green |
| 4. The evidence readers | `cli/requeue.py`, `cli/resolve.py`, `pipeline/sku_name_contradictions.py`, `pipeline/sku_number_contradictions.py`, `pipeline/identity_checks.py`, their CLIs and self-tests | no | no | one mutation arm per builder: a builder that reads `name` instead of `read_name` lets a disputed fixture card through, and the test goes red. D255's self-test adds the human-bound exclusion. `harness/tests/t3_join_coverage.py` stays green |
| 5. The screens | `app/src/types.ts`, `app/src/server.ts`, `app/src/CardHero.tsx`, `app/src/ReviewQueue.tsx`, specs under `app/tests/` | no | YES: `#/inventory` Details and `#/review`, plus a look at `#/fulfillment`, `#/orders` and Home, at 1440, 820 and 390, light and dark | `npx tsc --noEmit` prints nothing. `make design-check` is green, with the Fulfillment floors and the press-stability sweep of `inventory.spec.ts` (D118) over the new press. The D194 and D196 rows are green, or the ceiling raise goes to the owner |
| 6. The demo | `scripts/demo-seed.py`, the demo bundle | no (the demo store only) | YES: the demo build at the three widths | `make demo`, then `make demo-freshness`, agree |
| 7. The guard and the record | `scripts/docs-audit.py`, a new decision entry under a slug, its number claimed at merge, amendment notes on D213, D242, D252, D253, D255 and D239 | no | no | the `identity writers` row goes red on a planted assignment and green on the tree. `make docs-audit` is green |

Lane 1 goes first. Lanes 2, 3 and 4 then run in parallel. Lane 5 follows lane 3, which owns
the wire. Lane 6 follows lane 5. Lane 7 follows lane 3, because its row stays red until every
writer moves. The press (lane 2) runs on the owner's store only after two things. The owner
reads the replay's table on the day. Then the owner says the word.

## 12. Open questions for the owner

1. **Is a "change" the identity moving, and not the spelling?** Recommended: yes. Then the
   spelling-only classes T1 and T2 derive under the 2026-09-23 word; 357 cards draw a new
   spelling. Second part: does D162's standing ruling cover T4u? That is 70 cards whose name is
   unique and whose number was the misread. Recommended: yes. The conservative option holds
   T4u too, which gives 122 held cards instead of 52.
2. **T3's 38 disputed names.** A human chose each SKU off the photograph. Recommended: derive
   them. The press's preview prints the 38 once, so the owner can look before `--write`.
3. **The 10 held sold cards.** Recommended: report only, drawn as read. D252 cannot correct a
   departed card, and the sale went out under the SKU.
4. **The store-owned SKU table (3.2).** Recommended: defer. The materialized fields meet the
   outcome. Build it when a rename is first measured, or when a bound SKU is found with no
   export row.
5. **Search keeps the read name (5.2).** Recommended: yes, in the substring pass only.
6. **D242 and D255 as one report**, `cards identity`, with a name half, a number half and the
   human-bound exclusion. Recommended: yes.
7. **The build order.** After approval, either add this work to the `OPEN` list in
   `docs/map.py` and its mirror under `docs/gates/steps/`, or hand it straight to lanes. This
   branch adds neither, because the owner has not approved a build.

## Appendix: how the measurements were taken

All read-only. The store copy came from `sqlite3 -readonly ... ".backup <copy>"`, opened with
`mode=ro&immutable=1`. Python's `csv` module read the exports. The comparison imported the
repo's own functions and restated none: `pipeline/join.name_disputes`,
`pipeline/join._name_compare_key`, `pipeline/join.number_index_key`,
`store/numbers.strip_set_code` and `store/numbers.join_key`. Human acts are the `answered`,
`unanswered`, `sku_corrected` and `sku_correction_undone` events after each card's own
`captured_at`. The scripts lived in a session scratchpad and are not committed. Lane 2's replay
is their durable, reviewed form.
