## D202 — Build-order step 9's first two pieces landed; the mirror stays dry-run

**Step 9 (D15) names three pieces in order: snapshot the catalog, build the SQLite index, fill the image mirror.** This entry records that the first two are BUILT and the third is RECORDED but deliberately NOT FILLED — the working agreement's own vocabulary, applied to a step rather than to a screen.

### Piece 1 — BUILT: the snapshot

`vendor/pokemon-tcg-data/` is a committed copy of `PokemonTCG/pokemon-tcg-data` at commit
`8b4e387930ead7be6595b4d4c59b7ba7a3a79f08` (2026-07-16), recorded in
`vendor/pokemon-tcg-data/SNAPSHOT.json` alongside the fetch timestamp and a file count/byte
total, exactly as D15 asks so a later score is attributable to a catalog revision.

**Narrower than the whole upstream tree, and that is a decision rather than an omission.** Only `cards/en/*.json` (174 files, one per set) and `sets/en.json` are vendored — 176 files, 26,520,219 bytes. `decks/` (83 files, 688 KB) and the v1-conversion Ruby script are NOT vendored: nothing downstream of this step reads a decklist, and the join key this step exists to serve touches only the two directories that are here. GATES.md's own "183 files, 27.4 MB" estimate predates this fetch and counted the whole tree; the number moved because the tree itself grew (more sets released) between when that estimate was written and today, not because this snapshot is missing anything the join needs.

`scripts/catalog-refresh.py` is the refresh target (`make catalog-refresh`). It shallow-clones
upstream into a throwaway directory, diffs it against the tracked copy, and — unless
`--dry-run` — replaces the tracked copy and rewrites `SNAPSHOT.json`. It WRITES, so per D18 it
never runs on the commit path; it runs on the owner's word, the same shape as
`make catalog-index` and `make demo-seed`.

**Upstream publishes no license file** (D15 already says so). Recorded again here because this entry is the one that actually vendored the bytes: private, single-operator use, no redistribution.

### Piece 2 — BUILT: the SQLite index

`scripts/catalog-index.py` (`make catalog-index`) builds
`vendor/pokemon-tcg-data/catalog.sqlite` — two tables, `sets` and `cards`, joined **by filename**: `cards/en/sv1.json` holds every card of set id `sv1`, and `sets/en.json`'s `sv1` row is where `printedTotal` lives, which is half the join key exactly as D15 says. Measured on the current snapshot: 174 sets, 20,444 cards, zero card files naming a set absent from `sets/en.json`.

**The join_key column is composed the way `pipeline/join.py`'s own docstring composes the human-read form (`zfill(3)(number) + "/" + printedTotal`), then folded through `pipeline.join.number_index_key` — imported, not reimplemented.** That function's own docstring records the last time this repo had two independent copies of this fold and they silently disagreed (padding on one side, verbatim on the other, 950 rows lost to `no_catalog_row`). Importing it is what makes that specific defect structurally impossible between the vendored index and the live TCGplayer join, even though — see below — nothing wires the two together today.

`pipeline/catalog.py` is the read-only reader: `CatalogIndex.open()` refuses with
`CatalogNotBuilt` rather than building the index implicitly (a reader that can silently
trigger a multi-second build or a network fetch on the read path is the shape D18 exists to
forbid), and otherwise answers `cards_by_join_key`, `cards_by_name`, `card_by_id` and
`set_by_id` against the SQLite file `scripts/catalog-index.py` wrote.

**This does NOT change what the join matches today, and it is not wired into `pipeline/join.py`.** That module's own docstring already says its vendored-catalog caller is `harness/eval/fixtures.py` alone, matching a card's identification against one TCGplayer export's `Number` column — nothing about that changes here. What this piece adds is a place a FUTURE caller can look a card up by the same key without re-deriving the fold: D46 ("a card the pipeline could not place is offered the catalog, and a human may point at a row") is the standing candidate, and it remains unbuilt. Wiring `pipeline/catalog.py` into a screen or a review-queue path is a separate task with its own reason and its own decision — "Scope is argued, not gated" does not mean scope arrives for free because the primitive now exists.

**Guard, red-first:** `scripts/catalog-index-selftest.py` (`make catalog-index-selftest`) builds a synthetic two-set fixture, asserts the join lands on the same key `number_index_key` composes by hand for an unpadded lookup, and asserts a card file naming an absent set is REFUSED rather than silently skipped. Every case in it failed before `scripts/catalog-index.py` and `pipeline/catalog.py` existed, because neither an index nor a reader existed to pass or fail against.

**Deliberately NOT wired into `make check`'s own numbered list.** That list is reconciled by `make docs-audit`'s `check census` row against `make help` and the Makefile recipe, in a fixed order (D161) — three files that must move together. Adding a row there is a change to that census and belongs to a session arguing specifically for it, not a side effect of landing a catalog reader nothing yet calls. The guard runs today as `make catalog-index-selftest`, verified by hand and in this branch's own `make check` run (unaffected, since it is outside the list).

### Piece 3 — RECORDED, NOT FILLED: the image mirror

`scripts/catalog-image-mirror.py` (`make catalog-mirror`) builds the manifest — one row per
card's hires image (`images.large`, matching `harness/eval/fixtures.py`'s own `IMAGE_SIZE`
choice), derived from the vendored snapshot with no network call — and implements a
resumable (a non-empty destination file is skipped without a request), rate-limited
(`MIN_INTERVAL_S` between requests) downloader with a state file for cross-run progress.

**`ARGS=--dry-run` is the only mode this branch ran, per its own hard limit.** It HEAD-samples up to 200 images (rate-limited) and extrapolates a total from the sample's average Content-Length, writing nothing under the mirror destination. Measured 2026-09-13:

```
manifest: 20444 files
sampled: 200 (of which 199 answered a HEAD)
average size: 744870 bytes
extrapolated total: 15228121664 bytes (~14.18 GB)
```

Against D15's own ~16.7 GB estimate (834 KB average across a 197-image sample) — the same
order of magnitude, the difference being sample noise across two different 200-ish-image
draws from a 20,444-image population. Both numbers say the same thing: filling this mirror is
a double-digit-gigabyte, single-operator disk decision, not something any `make` target
should reach for on its own.

**The bare `make catalog-mirror` has never been run on this checkout, and nothing here runs it.** `harness/images/` — the default destination, per D15's own instruction to move that role rather than duplicate it — is untouched: still the 133 MB T1 sample it was before this branch, confirmed by directory listing before and after the dry run.

### What retiring the retry/backoff scaffolding in `harness/eval/fixtures.py` would cost, and why this branch did not do it

GATES.md's step 9 note says "retiring the retry/backoff scaffolding in that file is part of
the step" — meaning `harness/eval/fixtures.py` would stop calling `api.pokemontcg.io` live and
read the vendored snapshot instead. **This branch does not do that, and says so rather than leaving it implied.** T1's ground truth mechanism is D112-shaped: a committed `manifest.json`, a `scorer_fingerprint()` that lets an ordinary `make harness` run assert against a banked score in 3 ms instead of replaying, and a HOLDOUT/TUNE split hashed off each card id. Swapping its fetch path is a change to the ONE thing T1 exists to hold still, and it would need its own measurement — that the vendored snapshot's 150-card EVAL_SETS selection matches what the live API returned when `manifest.json` was banked, byte for byte, or the fingerprint check silently starts comparing against a different population. That measurement is real work with its own risk of quietly changing what T1 scores, and doing it inside a task scoped to "vendor the catalog, don't touch matching" is exactly the kind of scope creep "check whether it is yours to do" is not an invitation to overreach into — this is recorded as OPEN rather than done quietly.

### Governed by

D15 (this step exists and is scoped by it), D18 (both generators write and neither gates),
D112 (T1's own labels-vs-images split, which is why fixtures.py is untouched here), D25
(the join partitions by game — `pipeline/catalog.py` deliberately does not, because the
vendored catalog is pokemon-only and carries no `Product Line`).
