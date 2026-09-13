# Item 5 — the readings writer

## Goal and done-when

PR #333 (D189) turned `server/pipeline_routes.py:_readings()` from a live two-source walk
into a plain `SELECT` against a new `readings` table (`inventory/store.sqlite`). The table
is filled ONLY by `pkmnscan readings adopt --write` — a manual press. D189's own entry names
the gap and pre-authorizes the fix: *"If a session finds that gap costing something real ...
the fix is to make `join` and `do_live_export` call `readings adopt`'s writer at the end of
their own transactions, not to relitigate this entry."* This item is that fix.

**Done when:**

1. `pkmnscan join <run-dir>` (equivalently `POST /pipeline/runs/<name>/join`, which shells
   out to the identical CLI — see "Call sites" below) leaves the `readings` table current
   for every SKU that run's `pricing.json` just priced, with no `readings adopt` press.
2. `POST /pipeline/live-export` (`do_live_export`) leaves the table current for every SKU
   the newly-fetched export prices, with no press.
3. `pkmnscan readings adopt` still exists, unchanged in behavior, and is documented as the
   hand repair for the cases the two writers above cannot see (a run directory deleted by
   hand outside any command this repo runs — there is no delete-a-run capability — or a
   clock skew). It is not removed and its CLI surface does not change.
4. `GET /pipeline/value` (`do_pipeline_value` → `_readings()`) reflects a join's or a live
   fetch's fresh reading on the very next call, with nothing else run in between.
5. `make harness` T7 passes with a new arm proving (4), and `make readings-selftest` still
   passes 31/31 (the refactor below must not change `collect()`'s observable behavior).
6. The decision entry `docs/decisions/D189-readings-table.md` carries an amendment
   paragraph (see "Steps" §6) rather than a rewritten section — D189's own text is a settled
   record of what PR #333 shipped and why the gap existed; this item closes the gap it named
   and says so in an addition, not a rewrite.

## Depends on / conflicts with

**PR #333 is merged.** `git log --oneline origin/main | grep -i reading` shows
`fc5903a Merge pull request #333 ...` and `655bf42 Cache the market reading in a table;
_readings() becomes a SELECT` on `origin/main` already — **confirm this before starting**,
since this worktree's branch does not itself contain that merge. If for any reason the merge
commit is not yet on `origin/main` when you start, stop and re-read `gh pr view 333 --json
state` — do not reimplement PR #333's own tables from scratch; wait for it.

The decision is already numbered **D189** (`docs/decisions/D189-readings-table.md`,
`docs/decisions/ORDER.json`) — not an unclaimed slug. Do not run `make claim-ids` for it and
do not write a new `## D-<slug>` heading; you are amending an existing, numbered file.

**Conflicts with item 7** (`do_pipeline_value`, `box_views`, `_release_plan` — the plan's
§3 item 7), which also touches `server/pipeline_routes.py`. Item 7's job is to stop
`do_pipeline_value` building card objects and rank over a `select` instead; it does not
touch `_readings()` or the two writers this item wires. If both land in flight at once,
rebase rather than editing around each other — they are adjacent in the same file
(`do_pipeline_value` calls `_readings()` at line 3070) but change disjoint code.

**No conflict with item 2** (per-box read) or item 4 (`_copies_out`) — neither touches
`readings`, `pipeline/readings.py`, `store/readings.py`, `cli/cmd_join.py`, or
`do_live_export`.

## Read first

- `docs/decisions/D189-readings-table.md` — the whole rationale for the manual press and the
  exact paragraph that pre-authorizes this item (quoted above).
- `pipeline/readings.py` — the two-source walk. Read the whole file; it is ~200 lines and
  every function below is touched or extended.
- `store/readings.py` — the two tables and `Readings.replace()`. Read `replace()`'s
  docstring closely: "a SKU whose only source has since been retired ... must disappear
  from this table" — the new `replace_source()` below has to honor the same invariant at
  the scope of ONE source rather than all of them.
- `cli/cmd_join.py` lines 480–690 — the `with store.write() as writable:` block (queues,
  `live`) and the pricing.json write that follows it, outside that block.
- `server/pipeline_routes.py` lines 3510–3580 — `do_live_export`.
- `store/session.py` — `Store.write()`'s docstring: *"EVERYTHING A SESSION TOUCHED IS
  COMMITTED ON A CLEAN EXIT AS ONE TRANSACTION"* and *"WHAT IS NOT IN THE TRANSACTION ...
  photographs and sidecars"*. `pricing.json` is a sidecar in this sense — it is written to
  disk outside any `Store.write()` block today, and this item does not change that; it only
  adds a NEW, separate `Store.write()` call afterward to update `readings`.
- `harness/tests/t7_store_and_seams.py` — `check_readings_adopt_cli` (~line 13334) and
  `check_value_table` (~line 26418), for fixture conventions (`isolated_home()`,
  `seam_run()`, `command()`).
- CLAUDE.md's `D88` rule on the store's one-transaction-per-write shape, and the
  "FIX THE CAUSE, NEVER THE SYMPTOM" hard rule — this item is explicitly the well-scoped
  follow-up D189 asked for, not a new decision.

## Steps

### 1. `pipeline/readings.py` — extract the per-source readers so a caller with data already
   in memory (or a single file already on disk) can reuse the exact parsing rule without
   re-walking every run or re-parsing the whole live CSV.

Current (lines 79–119), `_run_readings`:

```python
def _run_readings(root: Path) -> Tuple[Dict[str, Reading], List[Source]]:
    found: Dict[str, Reading] = {}
    sources: List[Source] = []
    if not root.is_dir():
        return found, sources
    for entry in sorted(root.iterdir()):
        table = entry / RUN_PRICING_FILENAME
        if not entry.is_dir() or not table.is_file():
            continue
        try:
            parsed = json.loads(table.read_text("utf-8"))
            at = int(table.stat().st_mtime)
        except (OSError, ValueError):
            continue
        priced = 0
        for row in parsed.get("skus") or ():
            if not isinstance(row, dict):
                continue
            sku = str(row.get("sku") or "")
            market = (row.get("snap") or {}).get("market")
            if not sku or not market:
                continue
            priced += 1
            candidate = Reading(
                market=str(market), at=at, source=entry.name, kind=KIND_RUN,
                name=row.get("name"), set_name=row.get("set_name"),
                condition=row.get("condition"),
            )
            here = found.get(sku)
            if here is None or candidate.at >= here.at:
                found[sku] = candidate
        if priced:
            sources.append(Source(kind=KIND_RUN, name=entry.name, at=at, skus=priced))
    return found, sources
```

Replace with (new public function `reading_from_table`, then `_run_readings` calls it):

```python
def reading_from_table(parsed: dict, *, at: int, source: str) -> Tuple[Dict[str, Reading], Optional[Source]]:
    """One run's ALREADY-PARSED `pricing.json` (or an equivalent in-memory dict of the same
    shape, `_pricing_table`'s own return value), at a caller-supplied `at`.

    PULLED OUT OF `_run_readings` SO A JOIN CAN CALL IT ON THE TABLE IT JUST BUILT, without a
    disk round trip and without a second, drifting copy of the row-reading rule (`cli/
    cmd_join.py`'s `_pricing_table` already returns exactly this `{"skus": [...]}` shape —
    `pipeline/worklist.py:sku_row`'s fields are `sku`, `snap.market`, `name`, `set_name`,
    `condition`, the same four this function reads). `_run_readings` below still owns the
    file I/O and the mtime; this owns only the row-to-`Reading` rule, which is the part two
    callers now share.
    """
    found: Dict[str, Reading] = {}
    priced = 0
    for row in parsed.get("skus") or ():
        if not isinstance(row, dict):
            continue
        sku = str(row.get("sku") or "")
        market = (row.get("snap") or {}).get("market")
        if not sku or not market:
            continue
        priced += 1
        found[sku] = Reading(
            market=str(market), at=at, source=source, kind=KIND_RUN,
            name=row.get("name"), set_name=row.get("set_name"), condition=row.get("condition"),
        )
    source_row = Source(kind=KIND_RUN, name=source, at=at, skus=priced) if priced else None
    return found, source_row


def _run_readings(root: Path) -> Tuple[Dict[str, Reading], List[Source]]:
    found: Dict[str, Reading] = {}
    sources: List[Source] = []
    if not root.is_dir():
        return found, sources
    for entry in sorted(root.iterdir()):
        table = entry / RUN_PRICING_FILENAME
        if not entry.is_dir() or not table.is_file():
            continue
        try:
            parsed = json.loads(table.read_text("utf-8"))
            at = int(table.stat().st_mtime)
        except (OSError, ValueError):
            continue
        run_found, run_source = reading_from_table(parsed, at=at, source=entry.name)
        for sku, candidate in run_found.items():
            here = found.get(sku)
            if here is None or candidate.at >= here.at:
                found[sku] = candidate
        if run_source is not None:
            sources.append(run_source)
    return found, sources
```

This is a pure refactor — `_run_readings`'s observable output is unchanged; verify with
`make readings-selftest` (still 31/31) before moving on.

Do the identical extraction for `_newest_live_reading` (lines 120–150):

```python
def reading_from_export(export, *, at: int, source: str) -> Tuple[Dict[str, Reading], Optional[Source]]:
    """One ALREADY-PARSED `tcgcsv.Export` (the object `tcgcsv.read_export` returns), at a
    caller-supplied `at`. `do_live_export` has this object in hand the moment it validates
    the fetch — this lets it skip a second parse of a file that can run to several MB at
    50,000 listings, the same file it just wrote and just read once already."""
    found: Dict[str, Reading] = {}
    priced = 0
    for row in export.rows:
        sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
        market = row.get(tcgcsv.MARKET_PRICE_COLUMN) or ""
        if not sku or not market.strip():
            continue
        priced += 1
        found[sku] = Reading(
            market=market.strip(), at=at, source=source, kind=KIND_LIVE,
            name=row.get(tcgcsv.NAME_COLUMN), set_name=row.get(tcgcsv.SET_COLUMN),
            condition=row.get(tcgcsv.CONDITION_COLUMN),
        )
    source_row = Source(kind=KIND_LIVE, name=source, at=at, skus=priced) if priced else None
    return found, source_row


def _newest_live_reading(directory: Path) -> Tuple[Dict[str, Reading], List[Source]]:
    found: Dict[str, Reading] = {}
    sources: List[Source] = []
    fetched = sorted(directory.glob(f"{files.LIVE_PREFIX}*.csv")) if directory.is_dir() else []
    if not fetched:
        return found, sources
    newest = fetched[-1]
    at = live_export_at(newest.name)
    if at is None:
        return found, sources
    try:
        export = tcgcsv.read_export(newest)
    except (tcgcsv.MalformedCsv, OSError):
        return found, sources
    live_found, live_source = reading_from_export(export, at=at, source=newest.name)
    found.update(live_found)
    if live_source is not None:
        sources.append(live_source)
    return found, sources
```

Add `reading_from_table` and `reading_from_export` to the module — no `__all__` exists in
this file, so no export list to update. `collect()` itself (lines 162–192) is untouched.

Re-run `make readings-selftest` — still 31/31, because `golden()` there re-implements the
walk independently and was never coupled to `_run_readings`'s internal shape.

### 2. `store/readings.py` — add `Readings.replace_source`, a scoped sibling of `replace()`.

Insert after `replace()` (which ends the file, after line ~202):

```python
    def replace_source(
        self,
        kind: str,
        name: str,
        found: Dict[str, Reading],
        source: Optional[Source],
        *,
        supersede: Optional[List[str]] = None,
    ) -> None:
        """Fold ONE source's fresh reading into the table without re-running `collect()`
        over every other source.

        `supersede` names every source-name of this `kind` whose rows must be cleared FIRST
        — default `(name,)`, the ordinary case where a source only ever displaces its own
        earlier self (the same run, re-joined; the same live file, re-adopted). A caller
        whose kind has at most one CURRENT member at a time — `KIND_LIVE`, because
        `pipeline/readings.py:_newest_live_reading` only ever credits the single newest
        file — passes every existing source name of that kind, because the moment a fresher
        live file is fetched, every entry the OLD file was carrying stops being true whether
        or not the new file happens to reprice the same SKU. `KIND_RUN` never needs this: two
        run directories coexist and neither's rows expire when a third joins.

        EVERY SKU IN `found` IS WRITTEN UNCONDITIONALLY, not compared against the table's
        current `at` for that SKU. This is deliberately looser than `collect()`'s own
        newest-wins comparison and it is still correct: `found` was built with `at` = the
        moment THIS write just happened (a join's `pricing.json` mtime taken after writing
        it, or a live fetch's own embedded stamp), and by construction nothing already in the
        table can be dated later than the write that is happening right now. A full
        `readings adopt --write` remains the periodic proof that this local reasoning has not
        drifted from `collect()`'s own arbitration.
        """
        for old_name in (supersede if supersede is not None else (name,)):
            old_key = _source_key(kind, old_name)
            if old_key in self.sources:
                del self.sources[old_key]
            for sku, entry in list(self.entries.items()):
                if entry.kind == kind and entry.source == old_name:
                    del self.entries[sku]
        for sku, reading in found.items():
            self.entries[str(sku)] = reading
        if source is not None:
            self.sources[_source_key(source.kind, source.name)] = source
```

Add `List` to the `typing` import at the top of the file if not already present (it currently
imports `Dict, List, NamedTuple, Optional` — `List` is already there, confirm before adding).

### 3. `cli/cmd_join.py` — wire the run-table writer in, right after the file it reads from
   is written, and in a SEPARATE `Store().write()` from the queues/`live` transaction.

Current (lines 673–689):

```python
    pricing_path = run_dir.path(runs.PRICING)
    # A FRESH SNAPSHOT, not the one read at the top of this command. The write block above
    # moved `live` and drew `staged` down, so the snapshot taken before it is stale by
    # exactly the counts this table reports — and a screen drawing `pushed 2 staged 0` from
    # the wrong side of a join is a screen that disagrees with `emit` about what TCGplayer
    # holds. Lock-free, because every write in this store is an atomic replace.
    pricing_path.write_text(
        json.dumps(_pricing_table(run_dir, resolved, choice, store.read()), indent=2) + "\n",
        encoding="utf-8",
    )
    say(f"pricing table    {len(resolved.matches)} SKU(s) -> {pricing_path}")
```

Replace with:

```python
    pricing_path = run_dir.path(runs.PRICING)
    # A FRESH SNAPSHOT, not the one read at the top of this command. The write block above
    # moved `live` and drew `staged` down, so the snapshot taken before it is stale by
    # exactly the counts this table reports — and a screen drawing `pushed 2 staged 0` from
    # the wrong side of a join is a screen that disagrees with `emit` about what TCGplayer
    # holds. Lock-free, because every write in this store is an atomic replace.
    table = _pricing_table(run_dir, resolved, choice, store.read())
    pricing_path.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    say(f"pricing table    {len(resolved.matches)} SKU(s) -> {pricing_path}")

    # -------------------------------------------------------------- readings cache (D189)
    # COLLECTED OUTSIDE THE LOCK, REPLACED INSIDE ONE (D88's ordering: everything not in the
    # transaction is a file, and the file — `pricing_path` — was just written above, outside
    # any lock, exactly like every other write this command already makes to it). `at` is the
    # file's own mtime, taken AFTER the write, so a `readings adopt --write` run any time
    # after this join computes the identical `at` this line just did — the incremental path
    # and the full-recollect path can never disagree about which second this run's reading
    # was taken.
    #
    # ONE SMALL FILE, NEVER THE WHOLE `runs/` DIRECTORY AND NEVER THE LIVE EXPORT. This run's
    # `pricing.json` is already fully built in `table` — no second parse — and nothing here
    # touches any OTHER run's file or the newest live export, which is what keeps a join's
    # own cost from growing with the store: `pipeline/readings.py:collect()`'s expensive half
    # is the live CSV (up to the scale D170 measured for a comparable per-store export at
    # 50,000 cards), and a join never reads that file at all.
    run_found, run_source = readings_walk.reading_from_table(
        table, at=int(pricing_path.stat().st_mtime), source=run_dir.name,
    )
    with store.write() as writable:
        writable.readings.replace_source(readings_store.KIND_RUN, run_dir.name, run_found, run_source)
```

Add the two imports at the top of `cli/cmd_join.py` (currently `from pipeline import corpus,
decisions, join, pricing, routing, worklist` and `from store import master, queues`):

```python
from pipeline import readings as readings_walk
from store import readings as readings_store
```

(`store.session.Store` is already imported as `store` is the LOCAL VARIABLE name bound near
the top of `run()` — check `store = Store()` a few lines above the `with store.write() as
writable:` block at line 495 before assuming the module alias `Store` is free; use whichever
name is not already shadowed. `readings_store` avoids colliding with the existing local
`store` entirely.)

**Dry runs are unaffected.** `args.dry_run` returns via `_preview` well before this code
(line ~486), so nothing here runs on a preview, and nothing here runs on the `run_dir is
None` / `--keys` in-memory-run path either — wait, it does: a store-backed join (`--keys`,
no run directory) still calls `runs.create` unless `args.dry_run`, so `run_dir.path(...)`
and this new block execute identically whether the run came from `identify` or from
`--keys`. No special-casing needed.

### 4. `server/pipeline_routes.py` — wire the live-export writer in, reusing the `export`
   object already parsed to validate the fetch.

Add to the import block (line 131, which already reads
`from pipeline import corpus, decisions, games as game_registry, join, reprice, tcgcsv`):

```python
from pipeline import corpus, decisions, games as game_registry, join, reprice, tcgcsv
from pipeline import readings as readings_walk  # noqa: E402
```

Current `do_live_export` tail (lines 3550–3579):

```python
    name = f"{LIVE_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    path = directory / name
    path.write_bytes(body)

    try:
        export = tcgcsv.read_export(path)
    except (tcgcsv.MalformedCsv, OSError) as exc:
        path.unlink(missing_ok=True)
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "tcg_unexpected_response",
            f"TCGplayer answered with something that is not an export: {exc}. Nothing was kept.",
        ) from None

    live_rows = 0
    live_copies = 0
    for row in export.rows:
        held = tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, ""))
        if held > 0:
            live_rows += 1
            live_copies += held

    return {
        "ok": True,
        "fetched": name,
        "at": master.now(),
        "rows": len(export.rows),
        "live_rows": live_rows,
        "live_copies": live_copies,
    }
```

Replace with (inserting the readings refresh between the row-counting loop and the
`return`):

```python
    name = f"{LIVE_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    path = directory / name
    path.write_bytes(body)

    try:
        export = tcgcsv.read_export(path)
    except (tcgcsv.MalformedCsv, OSError) as exc:
        path.unlink(missing_ok=True)
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "tcg_unexpected_response",
            f"TCGplayer answered with something that is not an export: {exc}. Nothing was kept.",
        ) from None

    live_rows = 0
    live_copies = 0
    for row in export.rows:
        held = tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, ""))
        if held > 0:
            live_rows += 1
            live_copies += held

    # -------------------------------------------------------------- readings cache (D189)
    # THE `export` OBJECT ABOVE IS ALREADY PARSED — this reuses it rather than re-reading
    # `path` a second time, which is the whole cost `pipeline/readings.py:_newest_live_reading`
    # would otherwise pay again on every fetch. `at` comes off the file's own NAME through
    # `live_export_at`, never `master.now()` or the write's wall-clock moment: a full
    # `readings adopt --write` run later reads this same file and must compute the identical
    # `at`, and `pipeline/readings.py:live_export_at`'s docstring is explicit that the stamp
    # in the name is "the only honest clock here" — matching it is what keeps the incremental
    # path and the full recollect path from ever disagreeing about this file's age.
    #
    # SUPERSEDES EVERY EXISTING `live` SOURCE, NOT JUST THIS ONE'S OWN NAME. Unlike a run
    # table, `_newest_live_reading` only ever credits the SINGLE newest live file — the
    # instant this fetch lands, every SKU any OLDER live file was still carrying in `readings`
    # is no longer backed by anything `collect()` would read, whether or not this file
    # happens to reprice the same SKU. `store.read()` here is a second, lock-free read; it
    # costs one connection and no full-table scan (`readings_sources` is small).
    at = readings_walk.live_export_at(name)
    if at is not None:
        live_found, live_source = readings_walk.reading_from_export(export, at=at, source=name)
        stale_live = [
            s.name for s in Store().read().readings.sources.values()
            if s.kind == store_readings.KIND_LIVE
        ]
        with Store().write() as writable:
            writable.readings.replace_source(
                store_readings.KIND_LIVE, name, live_found, live_source,
                supersede=stale_live or [name],
            )

    return {
        "ok": True,
        "fetched": name,
        "at": master.now(),
        "rows": len(export.rows),
        "live_rows": live_rows,
        "live_copies": live_copies,
    }
```

`at is None` only for a filename `live_export_at` cannot parse — impossible for a name this
function just built from `datetime.now(...).strftime(...)`, but the guard costs nothing and
matches `pipeline/readings.py`'s own rule that an unreadable age must never be guessed at
(it would rather skip the incremental refresh than write a `Reading` with a fabricated `at`;
the next full `readings adopt` still catches it).

### 5. `pkmnscan readings adopt` — no code change, confirm behaviorally.

`cli/cmd_readings.py` is untouched by this item. Its job after this item lands is exactly
what D189 already called it: *"the hand repair"* — for a run directory deleted outside any
command this repo runs (there is no run-deletion subcommand; every doc that discusses a run
directory calls it an immutable input), or a genuine clock-skew edge case. Do not remove
`--write`'s preview-by-default shape or `show`.

### 6. Amend `docs/decisions/D189-readings-table.md` — append, do not rewrite.

Append a new section at the end of the file (after "What this does not touch"):

```markdown
### Amended 2026-09-12 — the writer runs inside the ordinary write paths

The gap this entry named — *"the table does not self-maintain ... if a session finds that
gap costing something real, the fix is to make `join` and `do_live_export` call `readings
adopt`'s writer at the end of their own transactions"* — is closed. `cli/cmd_join.py` calls
`store.readings.Readings.replace_source()` immediately after writing `pricing.json`, in a
`Store().write()` opened for that purpose alone (not folded into the earlier queues/`live`
transaction, because `pricing.json` is a sidecar file D88 keeps outside any sqlite
transaction, and the readings refresh reads that file's own post-write mtime). `do_live_
export` does the same immediately after validating the fetch, reusing the already-parsed
export rather than re-reading the file.

Both writers are INCREMENTAL, not a call into `pipeline/readings.py:collect()` — a full
recollect would re-parse every run's `pricing.json` (cheap) and the newest live export
(the one genuinely expensive file, potentially large at 50,000 listings) on every join,
which is exactly the per-request cost this table exists to avoid paying. `store/
readings.py:Readings.replace_source()` folds in one source's fresh reading, superseding
only that source's own prior rows for an ordinary run (two run directories coexist
independently) and every existing `live`-kind row for a live fetch (`_newest_live_reading`
credits only the single newest file, so a fresher fetch invalidates every SKU an older one
was still carrying).

`pkmnscan readings adopt --write` is unchanged and remains the hand repair for what these
two writers cannot see: a run directory removed outside any command this repo runs (there
is no run-delete capability), or a clock skew. Nothing about the preview-by-default CLI
shape changes.
```

Do not touch `docs/decisions/ORDER.json` — D189 is already the correct, allocated entry;
this is an amendment to existing text, not a new entry.

## Call sites

Every writer of every `collect()` input, researched against the merged PR and the current
tree:

| Input `collect()` reads | Writer | File:line | Wired in this item? |
|---|---|---|---|
| `runs/<n>/pricing.json` | `join` (`cli/cmd_join.py`, invoked directly as `pkmnscan join` and by `POST /pipeline/runs/<name>/join` via `server/pipeline_routes.py:do_pipeline_step`, which shells out to the identical CLI at line ~6372 — **one code path, not two**) | `cli/cmd_join.py:685` (pricing.json write) | **Yes** — step 3 |
| newest file under `inventory/.live/` | `do_live_export` (`POST /pipeline/live-export`, in-process, never a subprocess) | `server/pipeline_routes.py:3550` (`path.write_bytes(body)`) | **Yes** — step 4 |
| — (neither input) | `reconcile --live` (`cli/cmd_reconcile.py:run_live`) | writes only `Listing.live` / `Listing.live_as_of` inside `store.write()` at line ~234 | **No — ruled out.** It reads a live export file (fetched earlier, or a hand-uploaded CSV that may not even live under `inventory/.live/`) and never writes a new file there and never writes `pricing.json`. It changes nothing `collect()` reads. |
| — (neither input) | a run directory deletion | **does not exist** — there is no CLI command or route that deletes a run directory; every doc in this repo (`docs/specs/`, CLAUDE.md) calls a run directory an immutable input | **No — no such writer to wire.** This is exactly the case `readings adopt` remains the hand repair for. |
| — (not an input) | the pricing corpus (`inventory/prices.json`, `pipeline/corpus.py`) | `book.write()` | **No.** `pipeline/readings.py:collect()` never reads the corpus — confirmed by reading `_run_readings` and `_newest_live_reading`, neither of which touches `corpus.py` or `prices.json`. `readings` holds a market OBSERVATION; the corpus holds an operator ANSWER (D86) — D189's own closing paragraph makes this distinction explicit. |

## Tests

### `harness/tests/t7_store_and_seams.py` — new arm

Add a new check function, registered the way every other `check_*` in this file is (find
the `CHECKS = [...]` or equivalent registration list near the top/bottom of the file and add
this name to it — follow `check_readings_adopt_cli`'s own registration as the template).

```python
def check_readings_writer_after_join(checks: Checks) -> None:
    """A join leaves `readings` current with no `readings adopt` press (item 5, D189
    amended). `check_readings_adopt_cli` proves the CLI surface over the manual press;
    `check_value_table` proves the two-source arbitration with the table hand-filled. This
    is the one no existing check makes: that `join` itself keeps the table honest as an
    ordinary side effect of the write it already makes.
    """
    checks.note("")
    checks.note("READINGS WRITER — a join refreshes the cache with no adopt press")

    with isolated_home():
        cards = [(1, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards, market="9.99")

        # NO `readings adopt` ANYWHERE ABOVE THIS LINE. If item 5's wiring in
        # `cli/cmd_join.py` were absent or broken, this table would still be empty exactly
        # as it was the moment PR #333 landed.
        current = dict(Store().read().readings.entries)
        checks.ok(
            len(current) >= 1,
            "the join that just ran left at least one reading behind with no adopt press",
            current,
        )
        sku = next(iter(current))
        checks.equal(
            current[sku].source, run_dir.name,
            "and it is attributed to the run that was just joined",
        )
        checks.equal(
            current[sku].kind, store_readings_module.KIND_RUN,
            "as a run-table reading, not a live one",
        )

        # THE READ ROUTE AGREES, with no second write. `do_pipeline_value` is the caller
        # `_readings()` exists for; this is the seam a stale table would actually be felt on.
        payload = pipeline_routes.do_pipeline_value()
        row = next(r for r in payload["copies"] if r["sku"] == sku)
        checks.ok(
            row["market"] is not None,
            "GET /pipeline/value prices this card without anyone having pressed adopt",
            row,
        )

        # RE-JOINING SUPERSEDES ONLY THIS RUN'S OWN PRIOR ROWS. A second join of a
        # DIFFERENT run must not evict the first run's readings.
        cards2 = [(2, 1, "Articuno", "161", None)]
        run_dir2, _ = seam_run(checks, cards2, market="4.50")
        after = dict(Store().read().readings.entries)
        checks.ok(
            sku in after,
            "the first run's reading survives a second, unrelated run's join",
            after,
        )
```

Import `store_readings_module` at the top of the added function's module scope if
`store_readings` is not already a bound name in this file — check first; if it collides,
alias as e.g. `from store import readings as store_readings_module`.

**Mutation arm (manual, not committed as code):** comment out the new block in
`cli/cmd_join.py` step 3 (the `run_found, run_source = readings_walk.reading_from_table(...)`
through the `with store.write() as writable: writable.readings.replace_source(...)` lines),
run `python3 harness/run.py t7` (or the project's equivalent single-test invocation) and
confirm `check_readings_writer_after_join` is the one check that goes red — `checks.ok(len
(current) >= 1, ...)` fails because the table is empty. Restore the block before committing.
This is the standard "prove the guard sees its subject" step this repo requires of every new
assertion (`a-guard-must-see-its-subject.md` in the user's memory) — do it once by hand, note
in the PR description that it was done, and do not leave the mutated code in the tree.

### `scripts/readings-selftest.py` — extend for the extracted functions

The existing 9 fixture shapes assert `collect()` against `golden()`; they are unaffected by
the step-1 refactor (verify by running the script unmodified first — must still be 31/31).
Add one new assertion block proving `reading_from_table` and `reading_from_export` (the two
new public functions) are equivalent to what `_run_readings`/`_newest_live_reading` compute
from the same on-disk fixture, so the two new functions cannot silently drift from the
private loops that used to inline them:

```python
# NEW: the extracted per-source readers agree with the whole-directory / whole-export walk
# they were pulled out of, on the same fixture already built above for the "run-only" case.
parsed = json.loads((run_only_dir / "pricing.json").read_text("utf-8"))
at = int((run_only_dir / "pricing.json").stat().st_mtime)
direct_found, direct_source = readings.reading_from_table(parsed, at=at, source=run_only_dir.name)
whole_found, whole_sources = readings._run_readings(run_only_dir.parent)
check(direct_found == whole_found, "reading_from_table matches the whole-directory walk for one run")
check(
    [s for s in whole_sources if s.name == run_only_dir.name] == ([direct_source] if direct_source else []),
    "and its Source row matches too",
)
```

(Variable names above — `run_only_dir`, `check(...)` — are illustrative; match this script's
actual fixture-builder names and its own assertion helper, which is not necessarily called
`check`. Read the script's existing "run-only" fixture block before writing this, and place
the new assertion immediately after it so it reuses the same fixture rather than building a
second one.)

## Allowlist entries removed

**None expected.** `docs/specs/store-scaling.md` §4's allowlist (`make docs-audit`'s
`unscoped walk` row) is scoped to `.values()` / `.items()` / `to_payload()` / a filter-less
`select`/`distinct` over `inventory.cards` in `server/*.py` and `store/master.py`. Nothing
in this item touches that table or that guard's twelve tracked sites — `readings` and
`readings_sources` are not on the list and this item does not add a full-table scan over
`cards`. Confirm with `python3 scripts/docs-audit.py --json | grep unscoped_walk` before and
after — the count must be identical.

## Do not touch

- `store/db.py` — no schema change. `SCHEMA_VERSION` stays 5; `readings` and
  `readings_sources` already exist from PR #333.
- `docs/decisions/ORDER.json` — D189 is already the correct allocated number.
- `cli/cmd_readings.py` — the manual press's CLI surface is unchanged (step 5 above is a
  confirmation, not an edit).
- `pipeline/readings.py:collect()` — its signature, return shape and arbitration logic are
  untouched; only the two private loops it calls are decomposed into public helpers.
- `reconcile --live` (`cli/cmd_reconcile.py`) — ruled out above; do not add a wiring call
  there.
- Item 7's territory in `server/pipeline_routes.py` (`do_pipeline_value`'s own body past the
  `_readings()` call, `box_views`, `_release_plan`) — this item only touches the lines shown
  in step 4.
- `app/src/types.ts` / `ValueTable` / `ValueCopy` — no wire shape change. `ValueCopy.
  read_at` / `.source` and `ValueTable.sources` already exist (D79/D189) and already draw
  the reading's own age; this item makes what they draw fresher, not different.

## Measure

Two numbers, both taken on a copy of the owner's real store (`sqlite3 .backup`, per
`docs/specs/store-scaling.md`'s own measurement discipline — never the live store):

1. **Join wall-clock, before and after.** `time pkmnscan join <a real run directory> --export
   <its recorded export>` (or `--dry-run` swapped for a real run if a fresh export is not in
   hand — but the wiring only fires on a real write, so measure a real join). Before this
   item: baseline. After: the added cost is one small JSON parse of the file just written
   (kilobytes) plus one `Store().write()` transaction touching at most a few dozen rows —
   expect low milliseconds, not a measurable regression against the join's own cost (which
   already includes the store lock for the queues/`live` block). Report both numbers in the
   PR.

2. **The staleness probe this item exists to close.** On the same store copy: run a real
   join, then immediately `curl -s http://localhost:8000/pipeline/value | python3 -c "import
   sys,json; d=json.load(sys.stdin); print(d['sources'])"` (or the CLI-only equivalent —
   `python3 -c` importing `server.pipeline_routes` and calling `do_pipeline_value()` inside
   the same `PKMNSCAN_HOME`) — **before** this item lands, the newly-joined SKUs are ABSENT
   from `sources` and their `copies[*].market` is `null`/`why: no_reading` until someone
   runs `readings adopt --write`. **After** this item lands, the same call immediately after
   the join shows the fresh source and price. Screenshot or paste both JSON fragments into
   the PR description — this is the exact behavior change D189 flagged as needing "a second
   pair of eyes."

## Risks

- **`Rows` membership/iteration assumptions.** `replace_source`'s `for sku, entry in list
  (self.entries.items())` loads every row of `readings` to filter by `source`/`kind` — cheap
  today (readings is one row per SKU the store has ever priced, not one row per card), but
  worth flagging: at 50,000 cards this table could have tens of thousands of rows, and this
  loop is O(table size) per join. This is strictly better than the alternative it replaces
  (a full `collect()` re-walk is also O(runs) plus a multi-MB CSV parse), but if `readings`
  itself grows large enough to matter, a `Rows.where(source=...)` scoped query (the same
  indexed-column shape `store/master.py` already uses elsewhere) would be the next
  optimization — out of scope here, name it in the PR if the measured join wall-clock in
  "Measure" above shows anything surprising.
- **Two `Store().write()` transactions per join instead of one.** The queues/`live` block
  and the new readings block are deliberately separate (see step 3's comment) because
  `pricing.json` — the input the second block reads — is written to disk BETWEEN them, and
  D88's rule is that a sidecar file's write is never inside the sqlite transaction. This
  means a crash between the two `Store().write()` calls leaves the queues/`live` write
  committed, `pricing.json` on disk, but `readings` not yet refreshed for this run — exactly
  the state `readings adopt --write` already exists to repair, and no worse than today
  (where `readings` is ALWAYS stale until that press). Not a regression; worth one sentence
  in the PR so a reviewer does not read two transactions as a correctness gap.
- **`do_live_export`'s extra `Store().read()` call to find superseded live sources.** One
  more lock-free connection per fetch, reading only `readings_sources` (small). If this ever
  shows up in a profile, the fetch's own earlier response payload could carry the previous
  fetch's name from a module-level cache instead — not needed at today's scale, and adding
  it now would be exactly the kind of premature optimization `docs/DEBTS.md` warns against
  recording as a real cost without measuring it first.
- **`live_export_at` returning `None`.** Documented in step 4 as effectively unreachable for
  a name this function just built, but if `datetime.now(timezone.utc).strftime(...)` output
  ever failed to round-trip through `live_export_at`'s own `strptime`, the incremental
  refresh silently no-ops rather than raising — matching `pipeline/readings.py`'s existing
  rule that an unreadable age must never be guessed at. `readings adopt` remains the backstop.
- **Import cycle risk.** `pipeline/` does not import `server/` (the layering PR #333's own
  comment states explicitly at the top of `pipeline/readings.py`); this item only imports
  `pipeline.readings` INTO `server/pipeline_routes.py`, which is layered above `pipeline/`
  and already imports several other `pipeline.*` modules on the same line — no new cycle.
  `cli/cmd_join.py` importing `pipeline.readings` and `store.readings` is likewise
  consistent with the existing layering (`cli` already sits above both).
