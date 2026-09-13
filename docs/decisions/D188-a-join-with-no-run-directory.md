## D188 — A join reads the store directly when there is no run directory to replay

**`pkmnscan join` no longer requires a run directory.** `pkmnscan join --keys 3/1,3/2,3/3 --export <file>` resolves those three cards straight off the store's own `Card` records — no `identify` run, no `identifications.json`, no frozen snapshot to reconcile. A run directory still works exactly as it always has (`pkmnscan join <run-dir> --export <file>`); the two paths are siblings, chosen by which argument is given, and everything downstream of "here is a `Resolved`" — the report, the standing queues, `inventory/prices.json`, `pricing.json` — reads identically off either one. Built 2026-09-12, as PR G of the coordinated selection generalization D180 began.

### What stood, and why it was narrower than the store

`cli/runs.py`'s own header has said since it was written: *"A run is an IMMUTABLE INPUT, not state... deleting `runs/2026-08-03-box3-01/` costs nothing but the paperwork. That property is worth defending: it is what makes it safe to re-run anything."* That was only ever half true of `join`. `resolve.load(run, exports)` called `run.read_identifications()` unconditionally, which raises the moment `identifications.json` is missing — so a deleted run directory could not, in fact, be safely "re-run": there was nothing to point `join` at, even though every fact `join` needs (`name`, `number`, `printed_total`, `confidence`, `detected_finish`, `game`, `set_hint`, `metadata_finish`, `rarity_claim`, `box`, `index`, `photo`) is sitting on the live `store/master.py:Card` row and always has been.

D180 solved the identical problem on the `identify` side — a press no longer needs a capture directory to name what it is over, a `Selection` does. This is the same move on the read side: `join` no longer needs a run's frozen file to name what it is over, the store's own records do, when there is no reason to prefer the frozen copy.

### The two loaders, and which fact tells them apart

`cli/resolve.py` now has two entry points that both produce a `Resolved`:

- **`load(run, exports, ...)`** — unchanged. Reads `run.read_identifications()`, then `realign`s it (D36: a run directory is immutable and the store is not, so a card may have moved slot since it was identified) and `refuse_reallocated`s it (D36 amended: a box's number may have been deleted and reused since). This is the **replay path** — replaying a FROZEN snapshot against the store as it now stands.
- **`load_from_store(run, keys, exports, ...)`** — new. Builds the identical `{"cards": {...}}` shape `store_payload(keys, inventory)` produces, straight off the CURRENT store, and hands it to the same shared tail (`_resolve`, factored out of `load`'s old body) the file path uses. **Neither `realign` nor `refuse_reallocated` runs here**, and that is the whole of "realign behind the replay branch": there is no frozen snapshot to reconcile, because `store_payload` reads a card's position at the instant it is called — a reused box's cards are simply whichever cards are there NOW, correct by construction rather than by a check that runs afterward.

`run` is still a required argument to `load_from_store` — it is not the source of the identifications, it is where **this join's own output** lands. `cli/cmd_join.py` creates it with `runs.create(...)` only once the selection and its export are both known good (mirroring `identify`'s own D180 timing: a request that will refuse has not yet left a directory in `runs/` to clean up), and it carries a `selection` block in its manifest — `identify`'s own style — but never `identifications.json`, because there is no snapshot to freeze. A `--dry-run` store-backed join creates **no run directory at all**: `runs.create` would `mkdir` and write a manifest a moment before the preview's own "no manifest" line printed, so the dry-run path builds an in-memory `Run` that is never saved.

### The plan's own named risk, settled by a diff

The coordinator's plan flagged the store-backed loader's field completeness as "the most likely place PR G is wrong" and asked for a field-by-field diff against the file path over real identifications, not a claim it was checked. That diff is now in `harness/tests/t7_store_and_seams.py:check_store_backed_join`:

- Three cards (two claiming one number, one holo-only — the same two ladder shapes `check_pipeline_routes`'s fixture exercises) are written into the store through the ORDINARY writers `identify` uses — `record_capture` and `record_identification` — and into a run's `identifications.json` in the identical shape `cli/cmd_identify.py:run` writes.
- `resolve.load(run, ...)` and `resolve.load_from_store(run, keys, ...)` are run over the same three keys, and every `SkuMatch` the two produce is compared by **dataclass equality** — not a hand-picked subset of fields, whatever fields `SkuMatch` and `Position` happen to carry today or gain tomorrow.
- The queue entries the ambiguous third card earns (`resolve.entries_for`) are compared the same way, candidates list included.
- `via_store.realigned`, `.departed` and `.unverified_boxes` are asserted empty, which is the direct assertion that the replay branch never ran.

All of it passes. **What the diff actually caught, while building it**: the first draft of the test fixture forgot to mirror `metadata_finish` — the operator's capture-time toggle claim (rung 1) — onto the store's `Card` row, seeding it only into the run's identifications file. The two loaders then legitimately disagreed on which ladder rung resolved the finish (`stages: ['metadata']` vs `stages: ['detection']`/`['catalog_forced']`), because `store_payload` correctly read `card.metadata_finish` as `None` (the honest state of a card `record_capture` was never given a claim for). That was a bug in the TEST fixture, not in `store_payload` — but it is exactly the shape of bug this diff exists to catch, and it would not have been caught by comparing SKU sets or match counts alone.

### `submitted`, and what it is for

`cli/cmd_identify.py` now writes a `submitted` field into every run's manifest — the sorted position keys that were actually sent to the model this run (`to_send`, after the claim negotiation narrows it against cards another run banked in the meantime — D174). It sits beside `scope` (which drawer) and `selection` (what was asked): `selection` is the query, `scope` is the derived drawer, `submitted` is what was actually billed. `cli/runs.py:Run.submitted` is the cheap reader, and `cli/cmd_identify.py:_run_keys_of` — the `--run <name>` selection term's own resolver — now reads it first, falling back to `read_identifications()` only for a run written before this field existed. Measured against this PR's own fixture: a `--run <name>` selection no longer has to open a run's (potentially megabyte-sized) `identifications.json` to learn which keys it covers.

### `rescue`'s own replay-branch guard

`pkmnscan rescue` exists entirely to repair a FROZEN run's stale positions (D36) — it reads `source.read_identifications()` unconditionally, same as `load` did. A store-backed join's run directory has no such file, so `rescue` now checks for `identifications.json` before reading it and refuses by name — *"it looks like a store-backed join's own output directory... there is nothing here for `rescue` to re-bind"* — rather than crashing on a missing file or, worse, silently doing nothing useful. This is the same "replay branch" distinction as `resolve.py`'s, stated at `rescue`'s own front door: a store-backed join can never be stranded in D36's sense, because every read of it is already current.

One existing, unrelated constraint in `rescue` was left alone on purpose: it refuses to rescue a run whose cards land across more than one CURRENT box, citing D48 ("a run is still one box"). D48 is overtaken by D180, so that citation is now stale prose sitting on a still-live behavioral constraint — `Run.scope`/D145's `bid` are still singular, so a multi-box rescue would need a scope shape this pipeline does not have yet. Reworking that is a separate argument nobody has made, and `harness/tests/t7_store_and_seams.py` asserts the exact refusal text (`"(D48)"` included), so touching it is out of scope here. Named rather than quietly left for someone to trip over.

### What is proved, and what is not

**Proved.** `make harness`, 9 of 9, including the new field-by-field diff. The CLI end to end: both-arguments and neither-argument refused with a named remedy; a bad `--keys` entry refused by name (`store_payload` never silently drops a card the store has no record of, per `CLAUDE.md`); a real, positioned, never-identified card routed to the main review queue exactly as an `identify` failure would (not refused, not dropped); a store-backed dry run writes nothing, including no run directory; a real store-backed join writes exactly one run directory with `report.txt` and `pricing.json` but no `identifications.json`; `rescue` refuses that directory by name.

**NOT proved, and named rather than glossed over: `pkmnscan emit` does not yet accept a store-backed join's run directory.** `emit` calls `resolve.load(run_dir, ...)` internally, which is the file-replay path — pointed at a store-backed join's output, it refuses cleanly (`identifications.json does not exist — run 'pkmnscan identify' first`), never a crash, but a store-backed join today can populate the review queue and seed `inventory/prices.json` and cannot itself produce the CSV a human uploads to TCGplayer. That is real, uncommitted-for-here work — `cli/cmd_emit.py` was explicitly out of this PR's scope — and the remedy until it lands is `pkmnscan emit <a run directory>` for any positions that also came through an ordinary `identify` run, or a future PR giving `emit` the same two-loader shape `join` has now.

**NOT proved: a selection wider than "explicit keys."** `join --keys` is the one term wired through the CLI; `identify`'s fuller vocabulary (`--box`, `--bid`, `--state`, `--game`, `--since`, `--run`) was deliberately not extended to `join` in this PR — `pipeline/selection.py`'s `Selection`/`narrow()` are built around scanning `Capture` objects off disk, and reusing them for a post-identification, store-only filter would need either a second filter function over `Card` rows or an adapter reconciling two different "does this term apply" answers (`Capture.game_or_default` vs `Card.game`, `Capture.has_position` vs a stored `Card` always having one). That is real design work belonging to whoever picks it up next, not a two-line addition.

### What would reopen this

**A caller that wants `join --box 3` or `join --state identified` directly**, rather than resolving keys by hand or through a script and passing `--keys`. The measurement to take first is how often an operator's actual want is "everything identified, across drawers, that has never been joined" rather than "these specific keys" — `--run <name>` (an existing `identify` selection term) already answers a related but narrower question for a single past run's cards, unaffected by this entry.

**`emit` gaining the same two loaders.** The natural shape is `resolve.load`/`resolve.load_from_store` staying exactly as they are and `cli/cmd_emit.py` growing the identical `run_dir is None` branch `cmd_join.py` has — `Resolved` already carries everything `emit` reads (`matches`, `photos`) regardless of which loader built it.

### Footnote, added by `D199`

`server/pipeline_routes.py:_phase` was never updated to know this path exists: it gated every
stage past `"ready"`/`"identify"` on `manifest.get("collected")` alone, and a store-backed join
never writes `collected` — so a run that had gone all the way through `join`, with real
`counts.skus` and `pricing.json` on disk, still read `"Not started"` on `#/runs`, disagreeing
with `RunPanel.tsx`'s own SKU stats on the same manifest. `_phase` now treats `joined` as
sufficient evidence identification happened, by either loader this entry names — `collected or
joined` gates the first branch rather than `collected` alone. `harness/tests/
t7_store_and_seams.py:check_store_backed_join` asserts it directly on the store-backed run's own
manifest.
