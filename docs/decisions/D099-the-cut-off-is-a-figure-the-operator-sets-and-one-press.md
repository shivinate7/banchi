## D99 — The cut-off is a figure the operator sets, and one press writes one spreadsheet

**Built 2026-09-03, from the owner's instruction, verbatim: *"emit by default only should now emit only one spreadsheet by default (with the ability to split if needed)"*.** Two changes, recorded together because they meet at one seam — the threshold decides which bucket a card is in, and the bucket used to decide which file it was written to. Change either alone and the other is left describing a shape that no longer exists.

### One: the threshold stops being a module constant

**`pipeline/corpus.py`'s `policy.threshold` is the D9 cut-off, and `pipeline/pricing.py:THRESHOLD` is what a store that has never set one reads.** D9 has said *"both configurable"* since it was written and nothing could configure it: the figure was a module literal no flag, env var, document or route could reach. That is the shape D10's `CARDS_PER_SECTION` was deleted for — a number the product asserts about the operator's business with no way for the operator to disagree — and the argument transfers whole. D9's derivation is untouched: $0.40 is still $60/hr against a ~20s marginal pull. What moved is who may say otherwise — **and, on the merge with main, what a store that has chosen nothing reads.** See *The default is one figure too* below.

**It goes in the corpus and not in the run, which is D86 applied rather than reopened.** A run's `decisions.json` held two kinds of fact and the per-SKU half was a property of the CARD; the threshold is neither. It is a property of the OPERATOR'S HOUR — a labor bar, which is what D9 derives it from — so it is standing policy for the store, beside `rule` and `basis`, with the same per-run override shape D48 keeps for the lot that genuinely differs.

**`SkuMatch.threshold` is a field beside `rule` and `basis`, and that is the whole of the threading.** `listable` reads it, `join_batch` sets it on every match and cuts `SubThresholdBucket`'s bands from the same figure, `cli/resolve.py:load` takes it and hands it to BOTH `join_batch` and `default_router` — a run whose queue was routed by one cut-off and whose file was partitioned by another is a run that disagrees with itself — and `pipeline/merge.py:_merged_match` carries the newest leg's, with `_agree_policy` refusing a send whose runs override it differently. A match therefore carries the policy it was built under, so a report cannot answer `listable` with a figure changed after it was computed.

**Validated where it is read, as `check_basis` is.** `pricing.check_threshold` returns a `Decimal` or raises `InvalidThreshold` naming the value; `Corpus.parse` calls it and discards the result, exactly as it does `Rule.parse` and `check_basis`, so a document that cannot be priced refuses at the read rather than in the middle of an `emit` an hour later. It is a `ValueError` and NOT a `MalformedDecisions`, which is the third instance of the shape D49 already paid for twice — so every `except` that names those two names this one, and `pkmnscan prices show` widened to `ValueError` because it is the one command whose whole job is showing you this file. **It does not round**: `0.405` is a boundary somebody typed, and rounding it here would move a decision by a cent without saying so.

**On the wire as `policy.threshold`**, round-tripped by `GET`/`PUT /pricing` like every other policy key, and written into the payload even when it is the default — a control cannot draw its own current value off a key that appears only once somebody has changed it. `GET /pipeline/pricing` reports the STORED figure where it used to report the newest run's `pricing.json` cell; those stopped being the same kind of fact the moment the cut-off became settable. A run's table says what the join that wrote it partitioned by, which is a record and a stale one the hour after the figure changes. **The floor is unchanged and is still the constant** — nobody has asked for that one, and D9's clamp argument is about a market collapsing rather than about an operator's bar.

### Two: `emit` writes `import.csv`, and the splits are flags

**One press writes one spreadsheet.** It wrote `import-listed.csv` and `import-subthreshold.csv` per game per run — two uploads for one errand, twelve for a send of three runs over two games. The merged path D86 built already wrote one file across runs; this is that shape made the default for one run as well, so `emit` has one answer to "how many files" regardless of how many runs are named.

**Two flags split it on two axes, and `--listed-only` is deliberately neither.** `--split-threshold` puts the old pair back under the old names — an operator staging the valuable cards apart from the bulk gets the files they used to get, not a differently-named approximation. `--split-games` is unchanged and is the way back if Import to Staged turns a multi-`Product Line` file away, which is still unestablished: `fixtures/staged-import-accepted.csv` proves the format for one line only, the owner said they would test it, and a merged file whose games carry different export HEADERS is refused with a sentence naming the flag rather than written. `--listed-only` DROPS the sub-threshold rows instead of filing them elsewhere, and now says how many it left for a later press rather than letting them vanish.

**What the old split was for is not repealed, and this is the part worth writing down.** Two files meant the valuable cards could be staged and moved live while the bulk waited, and a pricing mistake on the cheap file could not touch the valuable one. Both arguments survive; what changed is which is the DEFAULT. The owner's measurement is their own errand: they import one file.

**THE MERGE IS NOT A CONCATENATION, AND INSIDE ONE RUN IT COULD NOT HAVE BEEN.** The two buckets are disjoint SKU sets of one report — `_game_only` partitions on `listable` — and `add_to_quantity` is per SKU, so a row's quantity is the same figure whichever file it lands in and the cap is spent once by construction. ACROSS runs it is `pipeline/merge.py`, unchanged: the union of positions deduped on `(box, index)`, the cap re-derived over it, and D86's measurement standing — three separate emits over three real runs wrote two SKUs past the cap of 4; one merged emit wrote none. **The no-duplicate-SKU rule likewise becomes a property rather than a discipline**: one `import_rows` call per game over the union of the two SKU sets, so a SKU is priced once and written once, and `join.write_import` still asserts it because a property nothing checks is a comment.

**D54's empty guard is per file and was widened, not weakened.** `emit` still never opens an import file until it has at least one row for it, and merging gives that failure one more way to happen — a file can now be empty for every game at once, and under `--split-threshold` a send whose every row is above the cut-off would otherwise write a header-only `import-subthreshold.csv` over a good one. `_warn_stale` globs `import*.csv` now: it named the two bucket files and would have said nothing about the one the default press leaves behind, which is exactly the stale file it exists to name.

**`_artifacts`' `is_import` was wrong from the day the merged file was added** — it tested `startswith("import-")` and `IMPORT_MERGED` is `import.csv` with no hyphen, so the run panel's import affordance never appeared over it. Fixed here because the default now lands on it.

### What is NOT built, named rather than left to be discovered

**Both halves landed the same day.** The threshold's control is on `#/pricing` and the emit split
is a quiet option behind the press; the paragraphs that named them as owed are discharged below
rather than deleted, because what the screen half found is worth more than the fact that it
shipped.

**`POST /pipeline/emit` and `POST /pipeline/runs/<name>/emit` both accept `listed_only`, `split_games` and `split_threshold`** — the same three whichever route, because a screen that could ask for a split on a send of three and not on a send of one would be answering a question about how many runs are open. `app/src/server.ts` sends `split_threshold` from both presses and `split_games` from neither.

**No `--threshold` flag.** D49 makes one file the place a pricing answer is written and `#/pricing` the press that writes it; a flag would be a second place to state it and therefore a second thing that can disagree, which is the argument that keeps `--rule` and `--basis` off that screen pointed the other way.

**What would reopen this.** An operator who never uses `--split-threshold` — the two-file argument would then be dead rather than demoted, and the flag and the two name helpers should go. And an Import to Staged that refuses a multi-`Product Line` file, which would make `--split-games` the default rather than the way back.

---

