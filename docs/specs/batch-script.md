# Batch script v2

`./banchi identify | join | emit | reconcile` is live code. Gate B put 53 real cards through
all four commands and reconciled back with zero unmatched in either direction. `docs/GATES.md`'s
build-order step 4 carries the run record.

`make docs-audit` couples this file to `pipeline/`, `identify/`, `geometry/`, `store/` and
`cli/`. Twenty staged lines under any of them, without this file, asks the coupling question.

Every threshold here is a number. An adjective in this file is a defect.

---

## 1. Scope

The four commands wire the pure modules `pipeline/{tcgcsv,variant,pricing,join}.py` and
`identify/{prompt,batch}.py` into a pipeline. They add:

- pricing rules: undercut %, markup %, basis and rounding
- multi-set catalog keying
- the identification cache and the run lifecycle
- crop retry for unreadable cards
- the inventory master store and its `pushed`, `staged` and `live` counts

**Logic never lives in `harness/`.** The harness tests the pipeline, so the pipeline cannot live
inside it. New logic goes in `pipeline/`, `identify/` and `geometry/`. The harness grows tests
only.

**Not built.** Nothing here reads pokemontcg.io (D15). Nothing here prompts interactively,
because the pipeline runs unattended.

---

## 2. Commands

There are four commands. A batch takes minutes to hours, and the pricing decision needs a
human. One blocking command would put a person in the middle of a poll loop.

```
banchi identify   <capture-dir>   submit, wait, collect, cache. Costs money.
banchi join       <run-dir>       resolve against the export. Free, re-runnable.
banchi emit       <run-dir> ...   write the import CSV. Free, re-runnable.
banchi reconcile  <run-dir> <staged-export.csv>   confirm what TCGplayer staged.
banchi reconcile  --live <my-pricing.csv>         the whole store, both directions (D87).
                      Previews. --write settles `live`. Reachable on #/runs.
```

Each command resumes and re-runs on its own. `join` and `emit` cost nothing, so re-running them
after a review or a price change is free.

`identify` also selects cards from the store instead of a directory: `--all`, `--state`,
`--box`, `--bid`, `--section`, `--game`, `--since`, `--keys` and `--run` (D180). With no path and
no selection flag it refuses. `join` takes `--keys` for a store-backed join. `emit` takes several
run directories and writes one file across them.

---

## 3. Storage

One master store sits under the runs and the runs feed it. A run is an immutable input. Deleting
one must never cost money or state.

```
inventory/
  store.sqlite          MASTER (D88). One SQLite file: cards, boxes, listings, the
                        identification cache, both standing queues, the order ledger and the
                        history. One table each, one transaction per write.
                        store.sqlite-wal and -shm beside it are the database.
  legacy-json/          the JSON files this store was migrated from. Moved aside whole on the
                        first open and read by nothing. MIGRATED.json says what was imported
                        and how to reverse it.
  prices.json           the pricing corpus (D86). A file.
  codes.jsonl           the code ledger (C8). A file.
  .lock                 the writer's exclusive lock file.

runs/<YYYY-MM-DD>-<label>-<nn>/
  manifest.json         inputs: capture dir, export path, mtime and sha256, prompt
                        fingerprint, flags, batch ids, and usage. `usage.cost_usd` is written at
                        collect from `identify/cost.py`, at the rates in force that day.
  identifications.json  what this run read, before caching.
  report.txt            the join report, both directions, verbatim.
  import.csv            THE import file: one press, one spreadsheet (D99), across games and
                        across the listed and sub-threshold split.
  import-listed.csv, import-subthreshold.csv   `--split-threshold` only.
  import-<game>.csv     `--split-games` only.
  reconcile.txt         written by reconcile.
```

**Write discipline.** Every `Store.write()` is one SQLite transaction over every table. It opens
inside an exclusive lock on `.lock`. It commits whole on a clean exit, or not at all (D88). The
lock is still needed, because atomicity prevents torn writes and does not prevent lost updates.
Two writers that each read, modify and write back would erase each other. So the session reads
inside the lock. The capture server uses the same lock and the same transaction. It is a second
writer and not a second owner.

The history is the `events` table. It is append-only and it is the audit trail: when a card was
captured, identified, pushed, staged, live and sold. D10 makes this worth keeping. Positions are
never renumbered and sold cards leave permanent gaps, so the history is inventory truth over
time. The rows that describe a change commit in the same transaction as the change.

---

## 4. `identify`

### 4.1 Preflight

The preflight always prints before anything is submitted: card count, total payload bytes, batch
chunk count, estimated cost, prompt fingerprint, and cache hits against sends. `--dry-run` does
everything except the API call. Sidecar problems, unreadable images and a mistyped directory
then surface for free.

### 4.1a The claim — the last free act before the money

Between the preflight and the first submitted byte, the press claims the cards it is about to
buy (D174). The claim is one row in the store's `submissions` table. It holds the position keys of
the send list and not the selection. A second press over any of those cards is refused on
intersection, and the refusal names the receipt and the overlapping cards.

The claim is written inside the same `Store.write()` that recomputes the send list from the
cache. Two presses can both finish deciding before either has claimed, so the list that §4.1
printed cannot be trusted. `--dry-run` claims nothing.

The same commit that banks the answers (§4.6) releases the claim, or neither happens. A run that
dies in between keeps its claim on purpose. The batch is paid for and its results keep for 29
days, so the cards stay held until somebody looks. The way out is the release control on `#/runs`.
`--run-dir` re-entering a run releases that run's own claim as it resumes.

### 4.2 Input

The input is photos plus JSON sidecars: position, box, set hint, finish toggle, game and other
claims (`docs/specs/capture-server.md` §6.3).

| Sidecar state | Behavior |
|---|---|
| Present and valid | Normal path. |
| Missing or malformed, and the filename carries the position | The position is recovered from the filename and treated as equivalent. The same server writes both. |
| Missing, and no position recoverable | The card is still identified, then routed to the main review queue flagged `no_position`. A skipped card is v1 bug #5 wearing a report. |

A missing set hint or finish toggle is not an error. The ladder's rung 2 exists for that case.

### 4.3 Images

Photos are downscaled to 1568px on the longest edge (`--max-edge`). The API bills anything larger
and then discards it. Originals are never modified, because the review queue and any retry read
them from disk.

### 4.4 Batching, resume, retry

Submission uses `identify.batch.run_batch` unchanged: one submission, one poll, collect by
`custom_id`. There is no per-card path.

Batch ids are written to `manifest.json` before the first poll. Re-running `identify` on a run
directory with an unfinished batch reattaches and collects by default. Results stay retrievable
for 29 days, so a re-submit would pay twice for an answer you already own. `--force-resubmit`
pays again on purpose, for example after a prompt change.

Per-request failures are `errored`, `expired`, `canceled` and `malformed`. Each is retried within
a bounded budget: default 1, `--retry-budget`. The run report gives the count and the reasons, so
a systematic failure cannot look like scattered bad luck. A card that still fails after the
budget goes to the main review queue as `identification_failed`. No identification means no price,
and an unpriced card is not a cheap card.

### 4.5 Crop retry

A card that returns `low` confidence or `malformed` is re-sent once, within the retry budget,
with cropped regions attached beside the full image. A `025` that is 40px wide in a downscaled
full-card image is a coin flip. The same digits, cropped and upscaled, are not.

Region location, in order:

1. **Find the card in the frame** with `geometry`. Detect the card's boundary and register it to
   a known rectangle. There are two methods, in order: segment by tone, and if that refuses,
   search for the card's border. `CardBox.method` says which one answered. The tone method's
   premise, a background flat relative to the card's contrast, is false on this rig. The border
   search found the card in all 53 Gate B photographs, where the tone method found none. See the
   T6 section of `docs/GATES.md`.
2. **Crop within the registered card** with generous fractional bands: title band and number
   corner. Generous bands mean that a small rotation or offset does not push the number out of
   frame. The bands are cut from a card-shaped rectangle. `geometry.corrected_bounds` applies the
   aspect correction, and both the primary image and `geometry/crop.py`'s `registered_card` share
   it (D75).
3. **If detection fails, there is no crop retry.** The card goes straight to the main review
   queue. If the card cannot be found at all, a human should look. A blind crop produces a miss
   that is indistinguishable from a bad read. The report names detection failures, so a rig
   problem shows as a pattern.

`geometry` is its own module because the feeder needs the same detection. It runs at batch time
and not at capture time, because D1 requires capture to be fast, offline and dumb.

The fallback, `opencv-python-headless`, was not taken. The tone method did not fail for want of a
better library. Its premise failed. The border search is about forty lines of numpy.
`requirements.txt` still omits opencv, now against a measurement.

`--crop` (D32) spends the pixel budget on the card and not the desk. It is off by default. It
crops to `geometry.detect_card`'s box before the downscale. It first corrects the box toward a
real card's 63/88 proportions, because the detector's boxes come back short for their width. A
frame where detection refuses is sent whole, and the preflight names the count.

A frame where detection answered and the box was not the card is also sent whole (D75). The
detector cannot say "found the wrong thing". `identify/images.py`'s `crop_refusal` declines a
crop under 30% of the frame that keeps under half the frame's detail. The preflight names that
count separately from the detection refusals, with the reason per card. The same guard stands in
front of the crop retry.

### 4.6 The cache

The cache is keyed by position. Each entry stores the identification, the photo's sha256, the
prompt fingerprint, the timestamp and `cleared_by_human`.

An answer is reused when the position and the photo hash still match. The position is the
identity. The photo hash is the staleness check: it makes a re-shot photo get re-read and not
answered with the old picture's reading.

**The press hashes before it decodes** (D163). The reuse test needs only the sha256 of the bytes on disk. So `identify` hashes every photograph and asks the store what it already owns. It refuses what has no prompt. Only then does it crop and downscale what it will send. Hashing costs about 0.7 ms a photograph. Cropping and preparing costs about 115 ms.

`Item.stage` names where a photograph stopped in the preflight. The preflight's four figures read
it: cache hits, to send, unreadable and refused. `Item.photo_sha256` carries the digest apart from
the prepared bytes, because `cli/resolve.py`'s `realign` (D36) treats a record without a digest as
one it cannot re-bind.

**The prompt fingerprint is recorded and not enforced.** It is not part of the reuse test.

| Situation | Behavior |
|---|---|
| Run died at card 300 of 500 | 300 reused, 200 sent. |
| 200 new cards added to the box | Only the new 200 sent. |
| Card 47 re-shot | Photo hash changed, so it is re-read automatically. |
| Prompt changed | **Reused, not invalidated.** The report states how many answers came from an older prompt. |
| Prompt changed, `--reidentify-stale` | Re-reads only weak, uncleared entries: confidence `low`, or currently in a queue, and `cleared_by_human == false`. |

**A human-cleared identification is permanent.** Once a person has looked at the photo and picked
the row, no re-run, prompt change or re-identification pass overwrites it. If a later run reads
that photo and disagrees, the report says so. The human answer stands.

Why a prompt change does not invalidate: T1 must invalidate strictly. A score has to come from the prompt being scored, and the harness does that. Production inventory is a different problem. Re-reading thousands of correct answers because one line was reworded costs real money to mostly reproduce them. The recorded fingerprint makes a targeted re-read possible.

---

## 5. `join`

### 5.1 Catalog and multi-set keying

The catalog is built from the TCGplayer Filtered CSV export and nothing else. It is narrowed to
the conditions this product lists (D137): the game's own `condition_by_finish` values plus
`Unopened`. Sealed product survives, and every play grade goes. A play grade is not a finish, so
no number loses one.

**The join key is per game.** `pipeline/games.py` names each game's strategy and
`pipeline/join.py` implements it:

| strategy | games | key |
|---|---|---|
| `number_and_printed_total` | `pokemon` | `zfill(3)(number) + "/" + printedTotal` |
| `printed_code` | `riftbound`, `one_piece` | the printed identifier, verbatim |
| `name_only` | `pokemon_code` | no key: the blank-`Number` rows, by name |
| `not_joined` | `misc` | never joined at all |

`161/159` is a secret rare and not an error. `misc` is identified and submitted to the batch API
but never joined, because no export or price exists for it.

Only the key is per game. `pipeline/join.py`'s `_walk` is one ladder for every game. It builds the key, looks it up, and repairs it once where the game declares a repair. It then tries the blank-`Number` name, then D35's name rung. `KeyStrategy` is the per-game part, as a value. Three parallel lookup functions were measured to fail. A rung landed in one game's copy alone, and `riftbound` returned zero candidates for cards whose rows were in the export. A rung added to `_walk` cannot land in one game and not another.

Both sides of a comparison go through one fold: `number_index_key` for the number and
`name_index_key` for the name. Never join on two spellings of one rule. `_repair_set_code` is the
second rung for the printed-code games. It removes a set code the model glued onto the front of
the identifier. It matches by shape (two to five letters, no digits, then one separator) and runs
only after the key has missed (D55).

A key is unique only within a set. Multi-set runs are required, so:

1. At catalog build, compute the keys that map to rows in more than one `Set Name`. This is
   cheap, deterministic and known before any card joins.
2. Keys that do not collide join as usual.
3. A colliding key uses the sidecar set hint to pick among the candidate sets.
4. No hint, or a hint that matches none of the candidates, goes to the main review queue as
   `set_ambiguous`. It is never guessed.

The collision count is reported at catalog build. The set hint is not authoritative everywhere
(D2 and the prompt call it optional and possibly wrong). The identification schema has no set
field. Adding one is a prompt change plus a full T1 re-run, to read a set symbol that prints far
less legibly than the digits.

`variant.resolve` builds `by_condition = {row[CONDITION]: row}`. That silently keeps the last row
when two rows share a condition string, which is what a cross-set key collision produces. The set
hint step closes that hole.

### 5.2 Export staleness

The export's mtime, age and sha256 are recorded in `manifest.json`, and the age prints on every
run. Warn only. Never refuse. A stale export is a judgment call, and a hard stop on age would
block a legitimate run for a reason the operator can see.

### 5.3 The ladder

`pipeline/variant.resolve` is used unchanged. D3 is settled.

D3's rung 0, a human's answer from the review screen, is applied by `join_batch` above the ladder
and not inside it. It nulls confidence, so the routing table below cannot re-queue an answered
card. Every rung that `resolve` walks infers a finish from evidence, and an answer is not an
inference. Rung 0 falls through to the ladder when the current export no longer carries that SKU,
or carries it under a different Condition.

Rung 3 never contradicts a finish claim (D3). A detection outside the claimed set is dropped.
`metadata_detection_disagreement` is retired. A card with no claim walks the same ladder.
`metadata_not_stocked` and `no_catalog_row` still refuse.

`join --dry-run` previews the join and writes nothing. It walks the ladder once and counts what would queue by reason code. It returns before the first write: no queues, no `inventory/prices.json` change, no `report.txt` and no manifest. The counts come off `entries_for`, the same function the write uses. A preview built from another source can be wrong in the one way that matters.

The CLI prints raw reason codes with no gloss table. `app/src/reasons.ts` holds the only label
map in the product. The `reason codes` row of `make docs-audit` reconciles the labels against the
constants and `docs/DESIGN.md`. The `reason emissions` row reconciles them against the rosters
that the pipeline publishes (`variant.LADDER_REASONS` and `routing.ROUTING_REASONS`), and it fails
on a declared reason with no producer.

### 5.4 Routing — which queue a card lands in

Confidence describes how legible the title and collector number were. It is the only signal that a
card was guessed at. A misread `026/198` as `025/198` is still a valid number that joins to a real
row, so nothing downstream can catch it.

| Condition | Destination |
|---|---|
| Resolved cleanly, confidence `medium` or `high` | Listed, unless the row was reached by name (next row). |
| Row found by name because the number could not be read (D35) | **Main queue if the row is at least $0.40, parked if below. Never listed on the name alone.** `join_batch` rewrites the resolution to `REVIEW` before routing and keeps the chosen row. The entry then carries one candidate under one shared reason, which is D29's group-answer eligibility. Rung 0 is exempt: a card a human has answered is listed on that answer. |
| Confidence `low`, resolved market at least $0.40 | **Main review queue.** A wrong listing on a $12 card ships the wrong card to a buyer, which is worse than a tap. |
| Confidence `low`, resolved market under $0.40 | **Parked** in the low-value queue. Not listed, not dropped, never in the main queue. |
| Ladder to review (D3 reasons) | Main queue if the cheapest candidate row is at least $0.40, parked if below. |
| No catalog row, or identification failed | **Main queue, sorted last.** No price is not a low price. A misread secret rare is exactly this case. |
| Matched row with blank or $0.00 market price | **`no_market_data`. Never auto-priced, never swept into the sub-threshold flat price.** A missing price is an unknown price. Handing away a $40 chase card at the floor is the failure this prevents. |

`--review-below-confidence=none|low|medium` (default `low`) tunes the confidence rule. `none`
means confidence never routes on its own.

Main-queue sort (`store/queues.py`'s `QueueEntry.sort_key`): three tiers. First come entries that
have waited `STARVATION_DAYS` (30) or more, oldest first. Then priced entries, descending by
price. Then unpriced entries. You work the known-valuable cards first, and price alone would never
release a card with no catalog row. A tier and not a blended score keeps the order among priced
cards predictable.

### 5.5 The queues

`review` and `parked` are standing queues keyed by position, not per run. Each entry holds the
position, photo path, what was read, confidence, reason, candidate rows and first-seen date.

Every run report leads with the standing queue totals and their age
(`14 cards in review, oldest 22 days`). `emit` restates them beside the row count it wrote. You
see the number when choosing what to work on, and again when you commit an import file.

Parked cards are candidates for the D9 Bulk Lots exit. An unidentifiable 15-cent card may never
be worth a tap.

### 5.6 Reviews never block emit

An unresolved card sits at a known position in a box. It is not lost and it is not urgent.
Holding 400 good cards hostage to 7 ambiguous ones is the wrong trade.

`join` reports both directions in full and writes every unmatched card to a queue before any
output exists. `emit` then writes the matched cards. The hard rule is to never write output before
reporting unmatched rows in both directions. The report and the queue files satisfy it. Suppression
does not. `join.emit_import` raises `OutputSuppressed` only when `report.ok` is false. A routed
card is not in `unmatched_cards`, so a run whose reviews all reached a queue passes.

---

## 6. Pricing

### 6.1 Rules

```
rule    = match | undercut:PCT | markup:PCT
basis   = market (default) | low          --basis
```

The default basis is `TCG Market Price`, the recent actual-sale average. An undercut then prices
below the going rate and does not chase one desperate seller. D8 names Market as the pricing
source and D9's threshold check uses it, so one number does both jobs. `--basis=low` switches to
`TCG Low Price`, for a box you want gone.

The threshold check always uses `TCG Market Price`, whatever the basis. D9 says market at or above
$0.40 earns a listing. That is a statement about value and not about pricing strategy.

### 6.2 Order of operations

```
price = clamp_floor( round_2dp_half_up( rule(basis_price) ) )
```

Round to two decimals, half up. Then clamp to the floor, in that order, so rounding can never sneak a price under it. Floor and threshold are both $0.40 by default. They are one figure and not two defaults that agree (D9). The operator's `policy.threshold` in `inventory/prices.json` does three jobs. It earns a listing, it sets the price the cheap half goes out at, and it is the price below which nothing goes out. `SkuMatch.list_price` clamps at `SkuMatch.threshold`. `pipeline/pricing.py`'s `THRESHOLD` and `FLOOR` are what a store that never set one reads.

There is deliberately no `policy.floor`. A floor above the cut-off makes the join price a card the
cut-off calls listable above its own market. A floor below it undercuts the price the cheap half
already goes out at. A second key could only ever be set wrong.

### 6.3 Sub-threshold disposition — `inventory/prices.json` `policy.sub_threshold`, default flat $0.49 (D86, D9)

D9 forbids the script from guessing what happens to a sub-threshold card. The decision is a
document and not a flag, so `#/pricing` is an editor for an existing contract and not a second
code path.

The answer is the store's standing policy and not a run's (D86). `pipeline/corpus.py` reads
`policy.sub_threshold` out of `inventory/prices.json` and projects it into every run's
`Decisions`. Where the key is absent or null, the corpus applies the default, flat $0.49
(`DEFAULT_SUB_THRESHOLD`), on read, and writes it on the next save. A fresh store's first `emit`
is therefore not refused for want of an answer. `"floor"` and a written flat price say what they
say. `join` names the standing disposition on its own `sub-threshold` line every run. `emit`
still refuses on an unanswered `no_market_data` card.

```jsonc
{
  "version": 1,
  "policy": {
    "rule": "match",                    // match | undercut:PCT | markup:PCT
    "basis": "market",                  // market | low
    "sub_threshold": {"flat": "0.49"}   // "floor" | {"flat": "0.25"} — the default when silent
  },
  "skus": {                             // one answer per SKU, for the whole store (D86)
    "8823901": {"value": "0.35"},       // a price, above or below the threshold
    "8823944": {"value": null, "channel": "unknown"}   // no market price: a price, or "unlisted"
  }
}
```

---

## 7. `emit`

`emit` writes one import file, `import.csv`, with every row it has (D99). That covers rows above the D9 cut-off and below it, across every game in the send. Two flags split it, on two axes. Neither is the default:

- `--split-threshold` gives the old pair back: `import-listed.csv` above the cut-off and
  `import-subthreshold.csv` below it, one pair per game. The split is not cosmetic. The valuable
  cards can be staged and moved live while the bulk file waits. A pricing mistake on the cheap
  file cannot touch the valuable one.
- `--split-games` writes one file per game, if Import to Staged refuses a file that spans two
  `Product Line`s. That is unestablished. `fixtures/staged-import-accepted.csv` proves the format
  for one line only. A merged file whose games carry different export headers is refused and not
  written.

`--listed-only` is not a split. It drops the sub-threshold rows and says how many it left for a
later press.

Every file obeys the no-duplicate-SKU rule on its own. The two buckets are disjoint SKU sets of one
report, so one `import_rows` call over their union prices and writes each SKU once. The live cap
is spent once across everything one press writes. `add_to_quantity` is per SKU inside a run, and
`pipeline/merge.py` re-derives it over the union of positions across runs.

A send can name a quantity per card (D7): `--quantity SKU=N`, repeatable. It puts exactly N copies
of that card in the file for this press. It is bounded by the copies on hand that are not already
listed, and never by what TCGplayer holds. That distinguishes it from `--cap`. `0` sends none of
the card without holding it. The report names every card given a figure, says "asked 9, only 3 can
go" where the shelf is short, and names back a SKU the send does not hold. A merged send spends the
figure once across the union. Nothing is recorded. The figure belongs to the press.

`--cap N` holds a SKU to N copies live, counting what is already out. There is no standing cap
(D7). It refuses while a sent copy is pending. `join.LIVE_QUANTITY_CAP` (4) is only the figure a
press may offer. `--live-guard FILE` trims rows so TCGplayer never holds more copies than are on
hand. `--reprice-live` adds a price-only row per live card the screen names.

The byte format is `pipeline.tcgcsv` unchanged: unquoted header, fully quoted data fields, CRLF.
Only `Add to Quantity` and `TCG Marketplace Price` are ever written. `TCGplayer Id` is never
modified. `check_only_writable_changed` runs per row against the catalog original.

`emit` refuses, loudly and writing nothing, when:

- the run-wide sub-threshold choice is unset while sub-threshold SKUs exist
- two rows in one file share a `TCGplayer Id`
- any non-writable column differs from the catalog original
- a `no_market_data` SKU has no hand-entered price

`emit` does not refuse for a non-empty review queue. It restates the queue totals beside the row
counts it wrote.

On success, `emit` makes two writes per SKU. They are about different things.

**The cards get their identity.** `sku`, `condition` and the run that decided them are written to
every copy the run matched, and the transition is appended to the history. Every copy gets it, not
only the listable subset. The identity write runs over `uncommitted_positions`, so a card held past
D7's live cap is still findable by `GET /search`, `copies_on_hand` and `positions_for_sku`. The
cap bounds the listing and never the record. It runs over `uncommitted_positions` and not
`positions`, because every terminal copy of a matched SKU is committed, and `set_state` has no
terminal guard. Iterating those would move a sold card back to `identified`.

**The listing gets the count.** `pushed` is bumped by the copies that actually reached an import
file, which is `live_positions` and nothing wider. `pushed`, `staged` and `live` are counts on the
SKU's `Listing` (D7) and not card states. The card stays at `identified`. Passing `pushed` to
`set_state` raises `UnknownState`.

### 7.1 Send the rest: a store-backed run with gone cards

A store-backed run (a sweep, or `join --keys`) records `{cid, name}` per card in its manifest.
When the run holds a card the store no longer has, `emit` and the send do not stop. They send
every card still there (`resolve.store_backed_payload`).

- Each gone card is named by its last-known name. The name shows in the send's receipt
  (`SendCard`), in the CLI's `emit` and `join` output, and in the "nothing to send" refusal
  (`resolve.gone_sentence`).
- Cards count by `cid`. Two cards with one name both count. One card held by two runs counts once.
- A run whose cards are all gone refuses.
- A manifest with keys and no card map refuses and writes nothing.

Proven by `check_send_skips_gone_card` and `check_send_store_backed_follows_cards`
(`harness/tests/t7/send_markdown.py`) and the "skipped cards" case in `app/tests/pricing.spec.ts`.

---

## 8. `reconcile` and listing states

Writing a CSV proves only that a CSV was written. Three counts, each confirmed by something
outside this script:

| Count | Confirmed by |
|---|---|
| `pushed` | `emit` wrote the row into an import file. |
| `staged` | **Export From Staged** download, diffed by `reconcile`. |
| `live` | Quantity against that SKU in a later Filtered Export (`Total Quantity`). |

Collapsing `staged` and `live` would make D7's refill math wrong. `Add to Quantity = min(cap -
live, backstock)` reads the live number, and an import staged but never moved live has no live
quantity. The pipeline computes this arithmetic as of D59, with one per-SKU figure of copies out.
D59 restored it. It does not argue against it.

`reconcile <run-dir> <staged-export.csv>` uses `join.reconcile_import` and reports both
directions: rows TCGplayer has that the run did not send, and rows the run sent that did not land.
This is the machine-checkable round trip against the real system.

`reconcile --live` is the second form, and it is not run-scoped (D87). It reads one full My
Pricing export against every SKU in the store, whatever run or box it came from. It reports both
directions: copies this pipeline sent that TCGplayer no longer holds, and SKUs TCGplayer holds that
were never sent from here. A per-run reconcile cannot report the second half, because a run only
knows what it sent. `reconcile --phantoms` lists SKUs TCGplayer holds beyond what is on hand. It is
read-only.

`reconcile --live` writes `live` and only `live`. `pushed` is the cumulative record of what was
sent, because an import file holds the last delta only (D54). Rewriting it would destroy the only
cumulative record.

`cli/cmd_join.py` draws `staged` down by the rise in live quantity that a fresh Filtered Export
reports. `join` refreshes `live` whenever it loads a fresh export. It does this only where the
export is the newer reading. One older than the store's `live_as_of` is kept out, and the join
report names each SKU it kept (D87). `live` is read from `Total Quantity` and from nowhere else.

**A ceiling over `pushed`.** `emit` writes `pushed`, and `reconcile` is the only thing that clears it. An operator who never downloads an Export From Staged never clears it. The claim then stands forever over an import that went live long ago. `cli/resolve.py`'s `_copies_out` answers, per SKU:

    min(live + pushed + staged, max(live, copies not sold))

- The newer reading of `live` is a floor and cannot be argued below. D8 and D11 put the authority
  in `Total Quantity` for the moment the file was read. `Listing.live_reading` picks whichever of
  the store's `live_as_of` and the file's mtime is later. A stale export is then harmless in both
  directions.
- The physical count is a ceiling. TCGplayer cannot hold more copies of a SKU than this Mac owns
  and has not sold. `store/master.py`'s `Inventory.copies_not_sold` is a fact about cardboard. It
  needs no write, no second CSV and no inference about whether an import landed.
- A retired copy still counts as sent (D26). It left this box, and TCGplayer was never told, so its
  row is still out there. Freeing a slot under the cap for it would be wrong.

The ceiling bounds what this pipeline may claim is out there. It says nothing about which stage a
copy is at. Only an Export From Staged answers that. That is why the ceiling is not a reason to
collapse `staged` into `live`.

Cards that sit in `staged` for more than 14 days (`master.STAGED_STALE_DAYS`) are named in the run
report. That catches an import that was staged and never moved live.

---

## 9. Configuration

| Knob | Default | Where |
|---|---|---|
| `--max-edge` | 1568 | image downscale, longest edge |
| `--retry-budget` | 1 | per-card retries after a batch failure or a weak read |
| `--review-below-confidence` | `low` | `none` \| `low` \| `medium` |
| `--dry-run` (join) | off | preview both queues, write nothing |
| `--basis` | `market` | `market` \| `low` |
| `--rule` | `match` | `inventory/prices.json` `policy.rule`, seeded by the flag on the first join of an empty corpus (D86) |
| threshold and floor | $0.40 and $0.40 | D9, `pipeline/pricing.py`. One figure. Both follow `policy.threshold` when it is set (D99) |
| `--cap N` (emit) | none | D7: a ceiling on copies live per SKU, asked for per send |
| `--quantity SKU=N` (emit) | none | D7: a send quantity per card, this press only. Composes with `--cap` to the tighter |
| cards per section | no default | D10: dividers are declared, never assumed |
| staged-stale warning | 14 days | run report only |
| `--force-resubmit` | off | pay again for an existing batch |
| `--reidentify-stale` | off | re-read weak uncleared entries after a prompt change |
| `--dry-run` (identify) | off | everything except the API call |
| `--variant` | unset | fills the finish where a sidecar records none. Never overrides one |

`--variant` fills gaps and does not override. D3 establishes that the capture toggle is a claim. A flag that could flatten a box you toggled stack by stack would defeat it. The flag exists for a directory of photos with no sidecars. There, every card stocked in more than one finish would otherwise cost a review-queue tap. Its `choices` are Pokemon's three finishes.

**The ladder's finish vocabulary is per game.** `variant.resolve` takes a `game` and reads that
game's entry in `pipeline/games.py` through `variant.vocabulary`. `cli/resolve.py`'s whitelist for
the model's detected finish and `identify/sidecar.py`'s reader follow the same vocabulary. A
finish outside the vocabulary is reported and never dropped.

**D3 rung 1's claim is a set.** One member determines the finish. Two or more filter the candidate rows and let rungs 2 and 3 choose within what survives. `--variant` is unchanged by that — it still fills a gap and still never overrides. It fills the gap with a one-member claim, which is what every record from before the set claim reads as.

---

## 10. Failure modes

| Failure | Behavior |
|---|---|
| Script dies mid-poll | Batch ids persisted before the first poll. A re-run reattaches and collects. |
| Batch expires (24h API cap) | Reported per card, retried within budget, then main queue. |
| Photo has no sidecar and no recoverable position | Identified, main queue, `no_position`. |
| Card boundary not detectable | No crop retry, main queue, named in the report. |
| Card located, box is not the card | Crop refused with its reason. The whole frame is sent. No crop retry. Named in the report as `unfit crop` (D75). |
| Two sets collide on one join key | The set hint disambiguates. Otherwise main queue, `set_ambiguous`. |
| Matched row has no market price | `no_market_data`. Never auto-priced. |
| Sub-threshold decision missing | `emit` refuses to write anything. |
| Concurrent write by the capture server | Exclusive lock, one transaction. |
| Run directory deleted | Costs nothing. Cache and inventory live in the master store. |

---

## 11. Harness changes

Logic lives in `pipeline/`, `identify/` and `geometry/`. Tests live in `harness/`.

- **T3 (join coverage)** covers multi-set key collisions: a colliding key resolved by set hint, a
  colliding key with no hint going to review, and non-colliding keys unaffected.
- **T4 (variant ladder)** covers the confidence routing table and the queue-routing rules: low and
  expensive goes to main, low and cheap goes to parked, unpriced goes to main sorted last.
- **T5 (pricing rules)** covers these rules: undercut and markup against both bases, and
  rounding half up at two decimals. It covers the floor clamp applied after rounding, the threshold
  always read from market price, and the `no_market_data` refusal. A wrong price is a distinct failure from a wrong
  match and has its own failing test name.
- **T6 (card geometry)** uses synthetic composites only: a card rectangle rendered at a known
  offset, scale and rotation, so the answer key is exact. A green T6 is not a detection rate. It
  measures the algorithm against images this repo drew. The tone method found the card in 0 of the
  53 Gate B photographs, and the border search found 53 of 53. The gates corpus's `T6` entry
  carries the measurement, and `docs/debts/` records what it leaves.

Adding a harness test requires editing `docs/GATES.md`, `harness/run.py`'s `TESTS` list and
`README.md`. That is a deliberate contract change. `make harness` runs the current set.

---

## Deliberately not built

- Charm pricing (.99/.49). It is a second rule that interacts with the floor and the undercut.
- A set field in the identification schema.
- Capture-time card registration. D1 keeps capture dumb.
- Any pokemontcg.io access (D15).
- Interactive prompts of any kind.
