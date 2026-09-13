# Item 8 — search on FTS5

Source: `docs/specs/store-scaling.md` §3 item 8 ("Search gets an index. 2 days... On the
owner's word over the recommendation to record it as a debt"), and §4's allowlist row
`server/capture_server.py:7970  do_search  .values()  per-keystroke  item 8`.

## Goal and done-when

Replace `do_search`'s full walk over `inventory.cards.values()`
(`server/capture_server.py:7970`) with a SQLite FTS5 index over the fields it matches on
today. The owner chose FTS5 over `LIKE` explicitly, for multi-word-any-order matching and
best-match-first ranking, and explicitly accepted losing mid-word substring matching
(`izard` -> Charizard) — traded for **prefix matching**, which must be built in so a
partial word typed from the start of a word (`chariz`) still hits. The walk is **deleted**,
not kept as a fallback: the index is built by the schema migration on first open, so no
store — real, fixture, demo-seeded, or CI's throwaway ones — is ever without it. There is no
`PKMNSCAN_*=off` escape hatch for this one; there is nothing to fall back to.

**Done when:**
1. `server/capture_server.py:do_search` no longer iterates `inventory.cards.values()` — the
   candidate set comes from an FTS5 `MATCH` query, and every downstream line (grouping by
   SKU, `positions_for_sku`, `copies_on_hand`, the `loose` bag, the wire shape) is otherwise
   byte-for-byte what it is today. `T7`'s existing search assertions (`harness/tests/t7_store_and_seams.py:7363-7500`,
   the code-ledger dispute lookup at `:9924-9945`) pass unmodified except where the ORDER of
   groups changes (see Tests).
2. A store opened by an older build's migration path (`store/db.py:_upgrade`) gets the FTS5
   table, its three sync triggers, and a populated index — automatically, once, under the
   store lock, `-9`-safe.
3. `make docs-audit`'s future `unscoped walk` allowlist (item 1's guard) has its
   `do_search` row removed in this same PR, or — if item 1 has not landed yet — this PR
   removes the row from `docs/specs/store-scaling.md` §4's plain table and says so in the
   PR description, because that table is the progress meter today and there is nowhere
   else to record the removal.
4. Multi-word queries in any order match (`"charizard ex"` and `"ex charizard"` return the
   same group). A partial word from its start matches (`chariz` finds Charizard; `izard`
   does not, and that loss is accepted, not a bug). Every T7 case that pins an exact ORDER
   of `do_search(...)["groups"]` still gets that order, or the case is updated with the
   reason (bm25 rank vs. the old insertion-order walk can reorder ties — see Tests).
5. `scripts/cid-selftest.py:table_bytes` (`:165-175`) and
   `case_the_reverse_restores_every_table_byte_identically` (`:649-684`) are updated to
   exclude the FTS5 shadow tables from the byte-exact comparison — see Call sites.

## Depends on / conflicts with

- **Item 1 (the `unscoped walk` guard).** Not yet built in this tree (`scripts/docs-audit.py`
  has no `check_unscoped_walk` today — verified: `grep -n "unscoped_walk\|unscoped walk"
  scripts/docs-audit.py` returns nothing). If item 1 has landed by the time this is built,
  remove `do_search`'s row from the guard's allowlist file in this PR. If it has not, remove
  the row from `docs/specs/store-scaling.md` §4's markdown table instead — that table is
  the plan's own progress meter ("that count is the plan's progress meter, and it may only
  go down") and leaving a stale row in it after the walk is gone is exactly the "advisory
  copy that stops being watched" failure D185/D173 exist to prevent.
- **Item 2 (the per-box read, `GET /inventory/<box>`).** Different routes
  (`do_inventory` vs. `do_search`), different functions, no line overlap. The one shared
  fact: item 2 removes `store/rows.py:177`'s degradation ("once one call in a request has
  loaded every row, every later `where()`/`select()` answers from the Python-side list").
  `do_search`'s FTS query never materialises the whole table first (see Steps 4), so it does
  not depend on item 2 landing — but if item 2 lands first and touches
  `server/capture_server.py` above line 7929, re-verify the line numbers this playbook
  cites before editing.
- **Item 3 (`history()` scoped).** No overlap — different table, different file region.
- **Item 5 (the `readings` writer, after PR #333) AND ITEM 2 (the `cards_captured_at`
  index).** THE SCHEMA VERSION IS A SHARED COUNTER, AND THIS SECTION'S OWN NUMBERS WERE
  WRONG BY THE TIME THIS ITEM WAS BUILT — CORRECTED HERE RATHER THAN LEFT MISLEADING. It
  originally reasoned about a race between item 5 and item 8 for version 5/6. By the time
  item 8 actually landed, BOTH had already resolved on `origin/main`: PR #333 (D189, the
  `readings` table) took **5**, and item 2 (D192, the `cards_captured_at` index) took **6**
  — `docs/specs/store-scaling/00-phases.md` reserved 6 for item 8 and records that item 2
  reached it first, so item 8 renumbers its own, the same D140 rule this section already
  describes for decision ids. **Item 8 is `stored < 7`, `SCHEMA_VERSION = 7`.** Before
  writing a migration's version number on ANY future item, `grep -n "SCHEMA_VERSION = " store/db.py`
  on top of current `main` rather than trusting this file's own account of a race that may
  since have settled. If a second branch is *also* proposing "the next version" concurrently
  (the same shape D174's own comment at `store/db.py:88-93` records — "Two concurrent 2→3
  steps in `_upgrade` is a conflict in the one function where taking either side silently
  loses a migration... THE RESOLUTION WAS TO ADD A STEP, NEVER TO TAKE A SIDE") — resolve it
  the same way: both `if stored < N` arms stay, the higher number is the true
  `SCHEMA_VERSION`, and a comment beside the bump says which PR took which number and why.
  Do not silently overwrite `SCHEMA_VERSION`'s value with a number that drops someone else's
  merged step.
- **Items 6/7 (`do_orders`, `_release_plan`, `box_views`, `do_pipeline_value`).** No
  overlap with `do_search` or the `cards` table's FTS shadow. Independent.

## Read first

- `docs/specs/store-scaling.md` in full, and `CLAUDE.md`'s D88 paragraph (`## Hard rules`
  is not where D88 lives — search `docs/decisions/D088-the-store-of-record-is-sqlite-and-a-write-is-one.md`
  and the "THE STORE OF RECORD IS ONE SQLITE FILE" paragraph in `CLAUDE.md`'s main body) —
  the invariant this migration must not break is **"every `Store.write()` is ONE
  transaction over all of them"**; the FTS index must be maintained *inside* that
  transaction, by triggers, never by a second write from Python after the fact.
- `CLAUDE.md`'s D45 paragraph (`#/inventory` screen description, and
  `docs/decisions/D045-the-copies-list-is-a-way-back-into-the-walk-and-the.md`) — confirms
  search narrows the box walk **client-side**: `GET /search` is store-wide with no box
  parameter (verified: `grep -n "search" app/src/server.ts` — `search(q)` at
  `app/src/server.ts:1345-1346` takes only `q`), and `BoxBrowse.tsx:710-716` intersects the
  box's own rows against the returned copy keys in a `useMemo`. **This migration does not
  add box scoping to the wire** — that would be new surface area D45 does not ask for.
- `server/capture_server.py:7929-8090` — `do_search` in full (reproduced under Call sites).
- `server/capture_server.py:7783-7857` — `_card_number_key`, `_number_display`,
  `_match_rank`, `_distinct`.
- `store/db.py:1-40` (module docstring, D88's argument), `:95-98` (`SCHEMA_VERSION` and the
  comment about the 3→4 merge collision — the precedent for this item's own version claim),
  `:112-150` (`TABLES`, `_INDEXES`, `_CID_INDEXES` — the existing pattern for a derived,
  indexed column), `:213-283` (`_ensure_schema`), `:285-345` (`_upgrade`), `:496-628`
  (`_add_card_ids`, the closest existing model: additive column, backfill loop, receipt),
  `:798-813` (`_add_submissions`, the *purest* additive step — no backfill question at all,
  which this migration's FTS *build* resembles more closely than the card-id backfill
  does), `:990-1005` (`connect`), `:1092-1136` (`SqliteSource.upsert` — **note the ON
  CONFLICT DO UPDATE form, not INSERT OR REPLACE**, which is what keeps `rowid` stable
  across a card's lifetime; see Steps 2), `:1140-1143` (`delete`).
- `store/master.py:1285-1330` (`_card_columns`), `:2480-2487` (`Inventory.CARDS`
  `TableSpec`).
- `pipeline/join.py:611-620` (`join_key`, the **composition** form `_card_number_key` uses
  — zero-padded, no D55 set-code strip), `:623-650` (`display_number`, the **screen** form —
  no padding, set code stripped per D55/D67), `:653-710` (`number_index_key`, the
  **catalog-match** form — NOT what search uses; do not confuse the three).
- `harness/tests/t7_store_and_seams.py:7183-7500` and `:9924-9945` (every existing search
  assertion).
- `scripts/cid-selftest.py:133-175` (`raw`, `table_bytes`) and `:649-684` (the reverse
  test that enumerates every table by `sqlite_master`).
- `app/src/useSearch.ts` (the one call site of `search()` on the client — `Inventory.tsx`,
  `BoxBrowse.tsx` and `Fulfillment.tsx` all go through this one hook) and
  `app/src/server.ts:1318-1346`.

## Steps

### 1. Confirm FTS5 is compiled into the runtime SQLite

Run, on the rig (this Mac) and note the result in the PR description:

```bash
.venv/bin/python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(x)'); print(sqlite3.sqlite_version)"
```

Measured 2026-09-12 on this worktree's `.venv`: **prints `3.54.0` with no error — FTS5 is
available.** If this ever prints an `OperationalError: no such module: fts5` on the rig,
STOP and read the Risks section instead of proceeding with this plan; the CI risk below is
independent of this result and must be checked separately before merging.

### 2. Two new indexed columns on `cards`, computed in Python and reused everywhere else

**Do not re-derive `join_key`/`display_number` logic in SQL.** `_card_number_key` already
composes the padded key (`join.join_key`) and `_number_display` already composes the
screen form (`join.display_number`), and `CLAUDE.md`'s own rule is "one fold, both sides" —
D55/D67 exist because this logic was written twice and drifted. Reuse the Python functions
by adding two derived, indexed columns to the `cards` table, populated at write time the
same way `cid` and `state_at` already are.

`store/master.py:1285` — extend `_card_columns`:

```python
def _card_columns(card: "Card") -> Dict[str, object]:
    return {
        "box": int_or_none(card.box),
        "idx": int_or_none(card.index),
        "state": card.state,
        "sku": card.sku,
        "condition": card.condition,
        "capture_id": card.capture_id,
        "name": card.name,
        "number": card.number,
        "game": card.game,
        "set_hint": card.set_hint,
        "run": card.run,
        "captured_at": card.captured_at,
        "state_at": card.state_at,
        "cid": card.cid,
        # ITEM 8: the two forms `_card_number_key`/`_number_display` compose in
        # `server/capture_server.py`, stored so the FTS5 index and any other reader can see
        # them without re-running join.py's rules a second time. "" rather than NULL when
        # there is no number, matching every other text column here — FTS5's external
        # content triggers read these as ordinary column values and NULL/"" both index as
        # nothing, but "" keeps `PRAGMA table_info` and a `sqlite3` CLI session boring.
        "number_key": join.join_key(card.number, card.printed_total) if (
            card.number and card.printed_total
        ) else "",
        "number_display": join.display_number(card.number, card.printed_total) or "",
    }
```

Add `join` to `store/master.py`'s imports (`from pipeline import join` — check for an
existing import cycle first: `pipeline/join.py` must not import `store/master.py`; verified
by `grep -n "^from store\|^import store" pipeline/join.py` returning nothing today, so the
import is safe in this direction).

`store/master.py:2480` — extend `Inventory.CARDS.column_names`:

```python
        column_names=(
            "box", "idx", "state", "sku", "condition", "capture_id", "name", "number",
            "game", "set_hint", "run", "captured_at", "state_at", "cid",
            "number_key", "number_display",
        ),
```

`store/db.py:117-119` — extend `TABLES["cards"]` the same way:

```python
    "cards": (
        "box", "idx", "state", "sku", "condition", "capture_id", "name", "number", "game",
        "set_hint", "run", "captured_at", "state_at", "cid", "number_key", "number_display",
    ),
```

**Why real columns and not trigger-side SQL expressions.** An FTS5 sync trigger's `INSERT
INTO cards_fts(...) SELECT ... FROM cards WHERE rowid = new.rowid` can only select what the
content table has; composing `zfill(3, ...)` and the D55 set-code strip in SQL would be a
third spelling of a rule `CLAUDE.md` says must have exactly one, and it would silently
diverge from `join.join_key`/`join.display_number` the next time either changes (both have
changed twice already, per their own docstrings). Two extra TEXT columns is the honest cost
of "one fold, both sides" holding for a fourth reader.

### 3. The migration: schema version, DDL, triggers, rebuild

`store/db.py:95` (line number drifted; grep it) — bump `SCHEMA_VERSION`. **CORRECTED: by
the time this item was actually built, both PR #333 (readings, took 5) and item 2
(`cards_captured_at`, took 6 — see "Depends on" above) had already merged to `origin/main`,
so this migration is `stored < 7`, `SCHEMA_VERSION = 7`**, not 6 as this section originally
assumed. Add a comment in the same style as the existing one at `store/db.py:88-94`
explaining which PR took which number.

```python
# SEVEN, FOR STORE-SCALING ITEM 8. Item 2 (D192) reached the 6 this file had reserved for
# search first — see store/db.py's own comment beside SCHEMA_VERSION = 6 — so this item
# renumbers its own, the D140 rule for decision ids applied to schema versions. Read
# `store/db.py:88-94`'s account of the 3->4 collision before assuming a bare bump is safe —
# two branches claiming "the next version" at once is the same shape and the resolution is
# the same: add a step, never take a side.
SCHEMA_VERSION = 7
```

`store/db.py:_upgrade` — add one `if stored < 7:` arm, following `_add_submissions`'s
shape (the purest precedent: no backfill decision, just "create the additive thing"):

```python
        conn.execute("BEGIN IMMEDIATE")
        try:
            receipt: Optional[dict] = None
            card_receipt: Optional[dict] = None
            if stored < 2:
                receipt = _add_box_ids(conn)
            if stored < 3:
                _add_submissions(conn)
            if stored < 4:
                card_receipt = _add_card_ids(conn, prehashed, directory)
            if stored < 5:
                _add_readings(conn)          # PR #333 — already landed if you are reading this
            if stored < 6:
                _add_captured_at_index(conn) # item 2 (D192) — already landed if you are reading this
            if stored < 7:
                _add_search_index(conn)      # ITEM 8
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.execute("COMMIT")
```

**ALSO CALL `_add_search_index` FROM `_ensure_schema`'S FRESH-STORE BRANCH, NOT ONLY FROM
`_upgrade` — THIS WAS MISSING FROM THE ORIGINAL PLAYBOOK AND IS LOAD-BEARING.** A brand
NEW store (every worktree, the demo seed, every harness test) never runs `_upgrade` at
all — `_ensure_schema` stamps `SCHEMA_VERSION` directly on that path — so without an
explicit call there, `cards_fts` would exist on no fresh store and `do_search` would raise
`no such table: cards_fts` on its very first query. `_CID_INDEXES`' own two
`CREATE INDEX` statements are the existing precedent for exactly this shape. Calling
`_add_search_index` unconditionally on both paths is safe and cheap: on a fresh store it
runs over zero rows.

New function, modelled on `_add_submissions` (`store/db.py:798-812`) plus the two new
columns from Step 2 (modelled on `_add_card_ids`'s `ALTER TABLE ... ADD COLUMN` idiom at
`store/db.py:515-516`):

```python
_FTS_TOKENIZE = "unicode61 remove_diacritics 2 tokenchars '/-'"

def _add_search_index(conn: sqlite3.Connection) -> None:
    """Schema N: FTS5 over the six fields `do_search` has always matched on (item 8).

    ADDITIVE LIKE `_add_submissions`: nothing here can be wrong about an existing row,
    because nothing existing is read to decide what to write — every card's own row is what
    seeds the index, via the rebuild command below, and a rebuild is idempotent by
    definition. The two new columns are backfilled by the ALTER's default (NULL) followed by
    an UPDATE that recomputes them from each row's own stored `number`/`printed_total` —
    there is no ambiguity to resolve, unlike `_add_card_ids`' photograph hashing.

    TOKENCHARS INCLUDES `/` AND `-` so a collector number (`039/236`) and a One Piece
    identifier (`OP15-079`) stay one token each rather than being split into three; without
    it `unicode61`'s default word-boundary rule tokenizes `039/236` as two tokens and a
    query for the whole string would still work (FTS5 ANDs bare terms) but a query for just
    `/236` — which nobody types, but which a prefix match on a lone `/` would otherwise
    treat as a wildcard over every row — would not mean what a person expects. Measured on
    this Mac's SQLite (3.54.0): `tokenchars '/-'` keeps `4/102` and `OP15-079` as single
    tokens, confirmed by a MATCH probe (see this playbook's Steps 1/4 for the runnable
    check).

    EXTERNAL CONTENT (`content='cards'`), NOT A COPY. `cards.key` is `TEXT PRIMARY KEY`
    (`store/db.py:187`'s `_ddl`: `body = f"key TEXT PRIMARY KEY, {typed}, "`), which does
    NOT alias SQLite's rowid — only an `INTEGER PRIMARY KEY` column does that — so `cards`
    still carries its own implicit, stable rowid, and `content_rowid='rowid'` is exactly
    right. The rowid stays stable across a card's whole life because `SqliteSource.upsert`
    (`store/db.py:1092-1136`) writes `ON CONFLICT (key) DO UPDATE`, not `INSERT OR REPLACE`
    — an UPDATE never changes a row's rowid; a REPLACE (delete+insert) would have, which
    would leave the sync triggers' `old.rowid`/`new.rowid` bookkeeping wrong on every
    ordinary write. D172 fixed exactly this defect for a different constraint (`cards_cid`,
    `store/db.py:1095-1112`) by naming the conflict target — the same property this item
    leans on was fixed for a different reason four schema versions ago.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
    for column in ("number_key", "number_display"):
        if column not in columns:
            conn.execute(f"ALTER TABLE cards ADD COLUMN {column} TEXT")

    # Backfill the two new columns for every existing row, THROUGH `pipeline.join`'s real
    # functions — never re-derived in SQL. There are at most a few tens of thousands of
    # cards even at the 50,000-card projection this whole spec is written for, and this
    # runs once, under the lock, exactly like `_add_card_ids`'s hashing pass. The NEXT
    # ordinary write to any card (always through `_card_columns`) recomputes these two
    # columns anyway, so this backfill only has to be right for cards nobody touches again.
    from pipeline import join as _join

    rows = conn.execute("SELECT key, number, payload FROM cards").fetchall()
    for key, number, payload_text in rows:
        try:
            record = json.loads(payload_text)
        except (TypeError, ValueError):
            continue
        printed_total = record.get("printed_total")
        number_key = _join.join_key(number, printed_total) if (number and printed_total) else ""
        number_display = _join.display_number(number, printed_total) or ""
        conn.execute(
            "UPDATE cards SET number_key = ?, number_display = ? WHERE key = ?",
            (number_key, number_display, key),
        )

    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5("
        "name, number, sku, set_hint, note, number_key, number_display, "
        "content='cards', content_rowid='rowid', "
        f"tokenize=\"{_FTS_TOKENIZE}\")"
    )
    # THE THREE STANDARD EXTERNAL-CONTENT SYNC TRIGGERS, AS THREE SEPARATE `conn.execute()`
    # CALLS — NOT `conn.executescript()`, WHICH THIS PLAYBOOK ORIGINALLY SPECIFIED AND WAS
    # WRONG. Python's `sqlite3` module documents — and this migration hit — that
    # `executescript()` COMMITS ANY PENDING TRANSACTION before it runs the script. This
    # whole migration runs inside `_upgrade`'s own `BEGIN IMMEDIATE`, so an `executescript`
    # call here silently closes that transaction; `_upgrade`'s own `conn.execute("COMMIT")`
    # then raises `cannot commit - no transaction is active`. Measured directly:
    # `conn.in_transaction` reads `True` immediately before this call and `False`
    # immediately after, on a store carrying real cards. Three plain `execute()` calls run
    # inside the caller's transaction like every other statement in this function.
    #
    # `note` is not an indexed column of `cards` today (store/db.py's `TABLES` has no
    # `note`), so these triggers read it out of `new.payload`/`old.payload` via
    # `json_extract` rather than off a column — the one place this migration reads the
    # payload from a trigger rather than from a dedicated column, because promoting `note`
    # to an indexed column of `cards` is new surface area this item does not need (nothing
    # else in the app filters on it).
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_ai AFTER INSERT ON cards BEGIN
          INSERT INTO cards_fts(rowid, name, number, sku, set_hint, note, number_key, number_display)
          VALUES (
            new.rowid, new.name, new.number, new.sku, new.set_hint,
            json_extract(new.payload, '$.note'), new.number_key, new.number_display
          );
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_ad AFTER DELETE ON cards BEGIN
          INSERT INTO cards_fts(cards_fts, rowid, name, number, sku, set_hint, note, number_key, number_display)
          VALUES (
            'delete', old.rowid, old.name, old.number, old.sku, old.set_hint,
            json_extract(old.payload, '$.note'), old.number_key, old.number_display
          );
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS cards_fts_au AFTER UPDATE ON cards BEGIN
          INSERT INTO cards_fts(cards_fts, rowid, name, number, sku, set_hint, note, number_key, number_display)
          VALUES (
            'delete', old.rowid, old.name, old.number, old.sku, old.set_hint,
            json_extract(old.payload, '$.note'), old.number_key, old.number_display
          );
          INSERT INTO cards_fts(rowid, name, number, sku, set_hint, note, number_key, number_display)
          VALUES (
            new.rowid, new.name, new.number, new.sku, new.set_hint,
            json_extract(new.payload, '$.note'), new.number_key, new.number_display
          );
        END
        """
    )
    # SEEDED BY 'delete-all' + AN EXPLICIT INSERT-SELECT, NOT BY 'rebuild' — THE OTHER PLACE
    # THIS PLAYBOOK WAS WRONG. `INSERT INTO cards_fts(cards_fts) VALUES('rebuild')`
    # re-populates an external-content FTS5 table by running, internally,
    # `SELECT rowid, <col1>, <col2>, ... FROM cards`, matching each `cards_fts` column to a
    # COLUMN OF THE SAME NAME on `cards` — and `note` is not a column of `cards`. Measured:
    # `rebuild` raises `sqlite3.OperationalError: no such column: T.note` the moment
    # `cards_fts`'s DDL names a virtual column the content table does not have — not a
    # corner case, it fires on the very first migration run. The fix is `delete-all`
    # (which, unlike `rebuild`, does not read back from the content table) followed by an
    # ordinary INSERT...SELECT that computes `note` the same way the triggers do:
    conn.execute("INSERT INTO cards_fts(cards_fts) VALUES('delete-all')")
    conn.execute(
        "INSERT INTO cards_fts(rowid, name, number, sku, set_hint, note, number_key, number_display) "
        "SELECT rowid, name, number, sku, set_hint, json_extract(payload, '$.note'), "
        "number_key, number_display FROM cards"
    )
```

**A PLAIN `SELECT` AGAINST `cards_fts` WITH NO `MATCH` FAILS THE SAME WAY, AND IT IS WORTH
KNOWING BEFORE YOU WRITE A TEST OR A DEBUGGING QUERY AGAINST IT.** Any bare scan —
`SELECT * FROM cards_fts`, `SELECT rowid FROM cards_fts`, even `SELECT count(*) FROM
cards_fts` — raises the identical `no such column: T.note`, because with no `MATCH`
constraint SQLite falls back to a full-table scan that reads every declared column's text
back from the content table. A query WITH a `MATCH` constraint (what `do_search` always
uses) takes a different internal path — the FTS index itself — and never hits this. Where a
test needs a row count against `cards_fts`, count `cards_fts_docsize` instead: a REAL table
(one row per indexed document, keyed by rowid), not the virtual table, so it carries none of
this restriction.

**`-9` safety.** Everything above runs inside the `BEGIN IMMEDIATE ... COMMIT` `_upgrade`
already wraps every step in. A kill mid-migration rolls the whole transaction back — no
ALTER, no trigger, no seed survives partially — and the next open re-reads `stored < 7` as
true and runs the whole thing again from a clean slate. This is
the same guarantee `_add_card_ids`/`_add_box_ids` already rely on and needs no new
mechanism; it is worth stating explicitly per this playbook's "Read first" instruction, and
worth adding one T-level case for (see Tests) because a virtual table's `CREATE` is DDL
inside a transaction, which SQLite supports but this repo has never exercised for FTS5
specifically until now.

### 4. The query function

Replace `server/capture_server.py:7929-8090`'s matching loop (`:7962-7983`) — leave the
grouping/rendering code from `:7984` onward untouched. New helper, placed beside
`_match_rank` (`server/capture_server.py:7814`):

```python
def _fts_query(text: str) -> str:
    """Turn a typed search string into an FTS5 MATCH expression.

    ONE TERM PER WHITESPACE-SEPARATED WORD, EACH QUOTED, EACH A PREFIX. Quoting
    (`"word"*`) escapes FTS5's own operators (`-`, `"`, `*`, `OR`, `NOT`, `AND`) so a query
    containing them is treated as literal text rather than as FTS5 syntax — a search for
    `note: japanese` must not become a column filter. `*` after the closing quote is FTS5's
    prefix operator and is legal directly after a quoted phrase.

    EVERY TERM IS A PREFIX, NOT ONLY THE LAST ONE. `do_search`'s existing rank order treats
    a full-word prefix as better than a mid-string substring (`_RANK_NAME_PREFIX` above
    `_RANK_SUBSTRING`), and a person typing `char ex` mid-query (both words incomplete) is
    the ordinary case while they are still typing, not an edge case — `useSearch.ts`'s
    200ms debounce means a fast typist's query is live before either word is finished.
    Prefixing only the last term would make `char ex` (before the second word completes)
    match nothing until the 'x' of "ex" lands, which reads as the search being broken for
    the length of one keystroke.

    BARE WHITESPACE SPLIT, MATCHING `_require_query`'s OWN NOTION OF "there is text here" —
    no attempt to tokenize the way FTS5 itself would (e.g. `4/102` splitting is FTS5's
    tokenizer's job, not this function's); this function's only job is turning a sentence
    into an AND of prefix terms.
    """
    terms = text.split()
    if not terms:
        return ""
    escaped = ('"' + term.replace('"', '""') + '"*' for term in terms)
    return " ".join(escaped)


def do_search(query: str) -> dict:
    """... (docstring unchanged above the matching-loop paragraphs; update the paragraph
    beginning "THE SCAN IS ONE PASS" to say the pass is now an FTS5 MATCH rather than a walk
    — see the note appended below)

    THE SCAN IS AN FTS5 QUERY AS OF ITEM 8 (docs/specs/store-scaling.md), NOT A WALK. At
    2,535 cards a single Python pass over every card was the honest answer (that PR's decision entry's
    own citation of the plan: "at 2,535 cards a single pass is the honest answer... At
    50,000 it is not"). `cards_fts` is maintained inside `Store.write()`'s own transaction
    by three triggers (store/db.py:_add_search_index), so this function never has to keep
    it in sync itself — it only ever reads. Ranking is `bm25(cards_fts)`, best match first,
    which the old walk never provided (the old order was insertion order into `ranked`,
    i.e. box-walk order of the FIRST matching copy of each SKU) — see this playbook's Tests
    section for exactly which T7 assertions this reorders.
    """
    text = _require_query(query)
    needle = text.lower()

    inventory = Store().read().inventory
    places = _Places(inventory)

    match = _fts_query(text)
    ranked: Dict[str, int] = {}
    loose: List[master.Card] = []
    if match:
        conn = db.connect(files.inventory_dir())
        try:
            hits = conn.execute(
                "SELECT cards.key, cards.sku FROM cards_fts "
                "JOIN cards ON cards.rowid = cards_fts.rowid "
                "WHERE cards_fts MATCH ? ORDER BY bm25(cards_fts)",
                (match,),
            ).fetchall()
        finally:
            conn.close()
        # RANK IS STILL COMPUTED BY `_match_rank`, NOT READ OFF `bm25`. bm25 orders which
        # SKU is the best match; it says nothing about whether a hit is an EXACT NUMBER
        # match, a NAME PREFIX, or a bare SUBSTRING — the three-tier rank the existing
        # sort key and the existing T7 assertions rely on (`_RANK_EXACT_NUMBER` before
        # `_RANK_NAME_PREFIX` before `_RANK_SUBSTRING`). So FTS narrows the CANDIDATE SET
        # (which cards are even considered — the part that used to cost O(cards)) and
        # `_match_rank` still decides the RANK of each candidate (which used to be free
        # because it ran inside the same walk). This is cheap: hits are a small fraction of
        # the store, exactly like `_copies_out`'s post-index-probe arithmetic in item 4.
        # PER TERM, NOT PER PHRASE — A CORRECTION AGAINST THE ORIGINAL PLAYBOOK, WHICH
        # CALLED `_match_rank(card, needle)` WITH THE WHOLE QUERY STRING AND WAS WRONG for
        # exactly the feature this item exists to add. `_match_rank` was written for a
        # single-term walk and tests one field for the WHOLE needle as a substring; a query
        # like "eiscue 044" has no field anywhere that contains the literal substring
        # "eiscue 044", so calling it with the whole phrase returns `None` for every FTS
        # candidate and MULTI-WORD SEARCH FINDS NOTHING. Measured: `do_search("eiscue
        # 044")` returned zero groups against the T7 fixture with the naive call above.
        # Each whitespace term (`_fts_query`'s own splitting rule) is checked separately and
        # the BEST (lowest) rank among the terms that match wins — order-independent, which
        # is what "eiscue 044" and "044 eiscue" both need to return the identical list. A
        # single-term query degrades to exactly the naive call (`terms == [needle]`).
        terms = [term.lower() for term in text.split()]
        seen_keys: set = set()
        for key, sku in hits:
            key = str(key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            card = inventory.cards.get(key)
            if card is None:
                continue
            term_ranks = [r for r in (_match_rank(card, t) for t in terms) if r is not None]
            if not term_ranks:
                # FTS5's tokenizer can match text `_match_rank` would not — e.g. a prefix
                # match inside `note`'s free prose that the substring pass would also have
                # caught, so this should be rare-to-never; kept as a filter rather than an
                # assumption, because trusting bm25's candidate set unconditionally would
                # silently drop `_match_rank`'s own exact-vs-prefix-vs-substring distinction
                # the day the two tokenizers disagree about a corner case (e.g. FTS5's
                # accent-folding via unicode61 finding a match `_match_rank`'s plain
                # substring check would not, or vice versa for a token FTS5 does not split
                # the way `_match_rank`'s `in` check would).
                continue
            rank = min(term_ranks)
            sku = str(sku).strip() if sku else ""
            if not sku:
                loose.append(card)
                continue
            ranked[sku] = min(rank, ranked.get(sku, rank))

    groups: List[dict] = []
    # ... unchanged from server/capture_server.py:7984 onward ...
```

**Do not add a `LIMIT`.** Verified: no client caller sends a page size or count
(`grep -n "search(" app/src/server.ts app/src/useSearch.ts` — `search(q: string)` takes
only the query), and `useSearch.ts`'s own docstring frames the feature as "make every
match immediately findable" (paraphrased from D45's "i want if i search for a card, all
results of that card"). A LIMIT is a new behavior change outside this item's scope; if the
50,000-card projection later makes an unbounded result set a real cost, that is a separate,
argued decision — not a side effect of the indexing change.

### 5. No client/wire change

`app/src/types.ts:SearchResult`/`SearchGroup`/`SearchCopy` are unchanged — Step 4's function
produces exactly the same shape `do_search` produces today, because everything after the
matching loop (`server/capture_server.py:7984` onward) is untouched. `app/src/server.ts:1345`
(`search(q)`), `app/src/useSearch.ts`, `app/src/BoxBrowse.tsx`, `app/src/Inventory.tsx`, and
`app/src/Fulfillment.tsx` need NO changes. Confirm this by diffing the response shape for
one fixed query before/after in a scratch script, not by inspection alone (T7's existing
assertions already do this structurally — see Tests).

## Call sites

- `server/capture_server.py:7929` `do_search` — the function this item rewrites (Step 4).
- `server/capture_server.py:9924-9945` — the code-card dispute lookup calls `do_search`
  directly (`found = capture_server.do_search(code)["groups"]`); it needs no changes since
  it consumes the same return shape, but re-run its T7 block after this change (harness
  line numbers above).
- `store/master.py:1285` `_card_columns`, `:2480` `Inventory.CARDS` — extended in Step 2.
- `store/db.py:95` `SCHEMA_VERSION`, `:117-119` `TABLES["cards"]`, `:285` `_upgrade` — the
  migration (Steps 2-3).
- `scripts/cid-selftest.py:165-175` (`table_bytes`) and `:649-684`
  (`case_the_reverse_restores_every_table_byte_identically`) — **must be updated, not
  merely re-run.** `table_bytes` enumerates every table via
  `SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'` and then
  runs `SELECT * FROM {name}` on each. After this migration that list additionally includes
  the FTS5 virtual table `cards_fts` and its shadow tables `cards_fts_data`,
  `cards_fts_idx`, `cards_fts_docsize`, `cards_fts_config` (external-content mode has no
  `_content` shadow, since `cards` itself is the content). The reverse test's byte-exact
  comparison (`identical.append((name, got == rows))`) will very likely fail on the shadow
  tables even when the two stores are logically identical: `cards_fts_idx`/`cards_fts_data`
  store compressed b-tree segment blobs whose internal layout depends on insertion order
  and page-split history, not only on logical content, so an index built once and a
  logically-identical index rebuilt independently are not guaranteed byte-identical.
  **Fix**: exclude `name.startswith("cards_fts")` from the comparison loop in
  `table_bytes`'s caller (or inside `table_bytes` itself, filtered at the `tables = sorted(...)`
  line), and add a SEPARATE assertion beside the existing one — after the reverse, run
  `do_search` for a fixed query against both the pre-reverse and post-reverse-then-migrate
  copies and assert the returned groups are equal. That is the semantic property the
  byte-exact check was standing in for on every other table; FTS5's shadow tables need a
  semantic check instead of a byte one.
- `scripts/submission-selftest.py:576,588` — enumerates tables/indexes by **exact name**
  (`name='submissions'`, `name='submissions_state'`), unaffected by new tables appearing in
  `sqlite_master`.
- `store/db.py:200` (`_stored_version`) — filters for `name = 'meta'` exactly, unaffected.
- No other `sqlite_master` reader exists in `store/`, `scripts/`, `harness/`, or `cli/` —
  verified: `grep -rn "sqlite_master" store/*.py scripts/*.py server/*.py cli/*.py
  harness/*.py` returns only the three sites above plus this migration's own new code.
- `sqlite3 .backup` (the recipe every measurement in this plan and `docs/GATES.md` uses to
  copy the owner's real store) handles a virtual table and its shadow tables the same as
  any other table — `.backup` operates at the page level below the table abstraction, so
  nothing about FTS5 changes that recipe. No `VACUUM`/`ATTACH` call exists anywhere in this
  repo today (verified, see Read first) and this item adds none.

## Tests

**T7 (`harness/tests/t7_store_and_seams.py`), existing block at `:7363-7500`:**

- The three blank-query refusals (`:7381-7387`) — unchanged; `_require_query` is untouched.
- `do_search("eiscue")["groups"] == [{"sku": "555", ...}]` (`:7389-7454`) — unchanged: one
  SKU matches "eiscue" today and will match it under FTS5 (name prefix). Copies, `on_hand`,
  the absent `cap` field, `listable`, `listed` — all unchanged, since none of that code
  moved.
- `do_search("japanese")["groups"]` finds the note-only card (`:7440-7448`) — **still
  passes**, because `note` is indexed (Step 3's triggers pull it via `json_extract`) and
  "japanese" is a whole word in the note, matched as a prefix of itself.
- `do_search("044/167")["groups"] == ["555"]` (`:7454, 7490`) — **still passes**: the
  `number_key` column stores exactly `join.join_key(...)` output, which is what
  `_card_number_key` composed for the exact-match branch of `_match_rank` before; FTS5's
  `tokenchars '/-'` keeps `044/167` one token, and the query function quotes+prefixes it as
  `"044/167"*`, an exact-or-prefix match against the stored token.
- The D67 "mixed number" case (`:7452-7490`) — glued set codes (`UNL • 044`,
  `UNL - 044`, `UNL / 044`) on three copies, searched by `044/167` — **still passes**,
  because `number_display`/`number_key` are computed the same way (`join.display_number`,
  `join.join_key`) regardless of whether the matching pass is a Python walk or an FTS
  query; the fix these fields represent (D67) lives entirely in `pipeline/join.py`, which
  this item does not touch.
- **NEW ordering risk, name it explicitly rather than assume it away**: today's
  `ranked[sku] = min(rank, ranked.get(sku, rank))` loop iterates
  `inventory.cards.values()` in whatever order `Rows.__iter__`/`_load_all` yields; under
  FTS5 the candidate set arrives in `bm25` order instead. This only matters if the RANKS
  differ between two copies of one SKU (the D67 case above), and `min()` picks the lowest
  rank regardless of which copy contributed it — so **the group's `rank` field is
  order-independent already**, and `groups.sort(key=lambda g: (g["_rank"], names[0].lower(),
  g["sku"]))` (`:8048`) is a total order with no tie left to iteration order.
  **Conclusion: no existing T7 assertion should need its expected VALUES changed, only
  re-run to confirm.** If any case proves otherwise, fix its expectation and note why in
  the PR — do not reorder `do_search`'s output to match a stale expectation.

**New T7 cases, added to the same block:**

1. `check_multiword_any_order` — seed two cards, "Charizard EX" and "EX Charizard" is not a
   real distinction on one card, so instead: seed a card named "Charizard" with `set_hint`
   "Base Set", and assert `do_search("base charizard")["groups"]` and
   `do_search("charizard base")["groups"]` return the identical SKU list — the property the
   owner specifically asked FTS5 for over `LIKE`.
2. `check_prefix_matches_from_word_start` — `do_search("chariz")` finds a card named
   "Charizard"; `do_search("izard")` (mid-word) does NOT — asserting the accepted loss
   explicitly, so a future session does not "fix" it back into a regression against the
   owner's own decision. Cite this playbook and the owner's 2026-09-12 acceptance in the
   assertion's message.
3. `check_index_stays_in_sync_across_the_four_write_shapes` — the triggers are the whole
   argument for D88 compliance here, so prove them directly rather than trusting the DDL:
   capture a card (`do_capture`), assert it is findable by name; sell it
   (`inventory.set_state(..., master.SOLD)` via `Store().write()`), assert it is STILL
   findable (search does not filter on state, matching today's behavior — copies including
   sold ones render, per the `on_hand`-excludes-sold/`copies`-includes-sold split already
   tested at `:7404-7411`); move it to another box (`do_put_card`'s box field, or
   `card.box = ...` under `Store().write()`), assert the returned copy's position reflects
   the new box; rename it (write a new `name` under `Store().write()`), assert the OLD name
   no longer finds it and the NEW name does. Each of these is a write via the ordinary
   `Store().write()` path, so if the triggers are wired correctly the index is simply
   correct after each — there is no separate "flush the index" step for the test to call.
4. `check_migration_seeds_the_index_for_pre_existing_rows` — build a schema-`N-1` store by
   hand (model on `case_the_forward_version_guard_refuses_a_newer_store`,
   `scripts/cid-selftest.py:687-700`, which already knows how to stamp an arbitrary schema
   version into `meta`), with cards written directly via SQL (bypassing `_card_columns`, so
   `number_key`/`number_display` are genuinely absent), open it through the ordinary
   `Store()` path, and assert a search finds those pre-existing cards — proving the
   migration's backfill-then-rebuild ordering (Step 3) seeds rows that predate the trigger.
5. `check_migration_survives_a_kill_mid_way` — open a connection, `BEGIN IMMEDIATE`, run the
   ALTER + trigger creation, then raise inside `_add_search_index` before the rebuild call
   (monkeypatch the rebuild statement), reopen, and assert the store is still stamped at the
   OLD schema version (rollback undid everything) and a second open completes cleanly.

**Mutation arm, spelled out per this playbook's own instruction to be explicit about what
must go red — CORRECTED AGAINST THE ORIGINAL PLAYBOOK, WHICH ATTRIBUTED THE RENAME CASE TO
THE WRONG TRIGGER.**

- **`cards_fts_ad` (DELETE), not `cards_fts_au`, is what the rename sub-case depends on.**
  `store/db.py:flush_rows` clears every touched key with a real SQL `DELETE` before it
  re-inserts it — for a reason that has nothing to do with search (the `cards_cid` UNIQUE
  index needs the transient collision room) — so an ordinary rename through
  `Store().write()` is `DELETE` then `INSERT`, never an `UPDATE`, and SQLite hands the
  `INSERT` a fresh rowid. Measured: renaming a card in a three-row table moved it from
  rowid 2 to rowid 4. Comment out `cards_fts_ad`'s body and a rename against a
  SINGLE-CARD store (so the freed rowid is deterministically reused by the very next
  insert) leaves the OLD name still matching after the rename — the plain "is the new name
  findable" assertion does NOT catch this (an orphaned row pointing at a rowid `cards` no
  longer has is silently dropped by `do_search`'s own `JOIN`, until the rowid is reused);
  only a direct `cards_fts MATCH` for the old name, or a `cards`/`cards_fts_docsize` row-count
  comparison, does.
- **`cards_fts_au` is reached ONLY by a genuine raw SQL `UPDATE` that is not preceded by a
  delete** — never by anything through `Store().write()`. `_add_search_index`'s own backfill
  loop is one such caller (though it runs before `cards_fts` exists, so it does not prove
  the trigger works); `scripts/cid-selftest.py`'s `_unname`/`_add_card_ids` raw
  manipulations are another. Prove it directly: on an already-migrated store, run
  `UPDATE cards SET name = ? WHERE key = ?` through a raw connection (bypassing the ORM
  entirely), then assert the old name is gone from `cards_fts` and the new one is present.
  Comment out `cards_fts_au`'s body and this specific case goes red; the ordinary
  capture/sell/rename sequence above does NOT go red, because it never reaches this trigger.
- Comment out the `cards_fts_ai` (INSERT) trigger's body. This is not merely a soft
  assertion failure: the very next `flush_rows` DELETE against a row `cards_fts` was never
  told about raised `sqlite3.DatabaseError: database disk image is malformed` in testing —
  the AD trigger's `'delete'` special command against a docid the index never received an
  `'insert'` for corrupts the shadow tables outright. Any write after the first capture
  reproduces this.

**`app/tests/inventory.spec.ts`.** No stub needs updating for shape (verified: the fixture's
`searchAnswer` function at `app/tests/inventory.spec.ts:564` is a hand-rolled TypeScript
mirror of `do_search` used to stub `page.route(/\/search\?/, ...)` in Playwright — it never
calls the real server, so it is unaffected by a server-side implementation change).
**Ordering IS a risk here**: if `searchAnswer`'s own grouping/sort logic assumes anything
about which physical copy of a tied-rank SKU appears first (grep its body for `.sort(` and
compare against `do_search`'s own `groups.sort` at `:8048` — if `searchAnswer` mirrors that
exact sort key, as it should, it is unaffected by this change for the same order-independence
argument given above for T7). Re-run the suite; do not hand-edit the fixture speculatively.

## Allowlist entries removed (`do_search`)

`docs/specs/store-scaling.md` §4:

```
| `server/capture_server.py:7970` `do_search` | `.values()` | per-keystroke | item 8 |
```

This row's own "Removed by" column already says "item 8" — this PR is what makes that true.
Delete the row (or strike it, per whatever convention item 1's guard settles on for a
plain-markdown table vs. a generated allowlist file) in this PR, not a follow-up. If item
1's `make docs-audit` `unscoped walk` row has landed as actual code by the time this ships,
remove `do_search`'s entry from ITS allowlist file instead (or as well, if the guard reads
`docs/specs/store-scaling.md` §4 directly rather than a separate file — check which when
item 1 exists).

## Do not touch

- `server/capture_server.py:7984` onward (grouping, `_agreed`, `_distinct`, `_copy_row`,
  the `loose` bag's rendering, the final sort) — this item changes ONLY how the candidate
  set of matching cards is discovered, never how a match becomes a group.
- `pipeline/join.py:join_key`, `display_number`, `number_index_key` — reused, not
  reimplemented (Step 2's whole argument). `number_index_key` specifically is NOT what this
  item indexes; it is the catalog-matching fold (leading zeros stripped) and has no
  relationship to search.
- `app/src/*` — no wire shape change, no client change (Step 5).
- `store/rows.py`, `store/session.py` — this item's query path (Step 4) opens its own raw
  connection for the FTS `SELECT`, exactly as `Store.history()`/`Store.buried()` already do
  (`store/session.py:172-186`) for reads that do not fit the `Rows`/`Snapshot` abstraction;
  it does not touch `Rows`, `TableSpec`, or the write path's transaction machinery beyond
  the two new columns and the migration.
- `cards_cid`, `cards_cid_missing` (D172's indexes, `store/db.py:143-150`) — untouched;
  this item adds a fourth and fifth index-like object (`cards_fts` and its shadows) beside
  them, not instead of them.
- The `queues`, `boxes`, `listings`, `identifications`, `orders`, `fulfilment`,
  `submissions`, `readings` (if #333 has landed) tables — none of them are searched by
  `do_search` today and none gain an FTS index in this item. If a future item wants box
  names or run names searchable, that is new scope, argued separately.

## Measure

Use the `.backup`-copy recipe `docs/specs/store-scaling.md` §1 already establishes ("Five
runs each, median, on the owner's store copied with `sqlite3 .backup` and the worktree's
own `PKMNSCAN_HOME`; the 20x column is the same copy with every row of `cards` and `events`
duplicated under new keys").

```bash
sqlite3 "$OLD_HOME/inventory/store.sqlite" ".backup /tmp/search-1x.sqlite"
# build the 20x copy exactly as store-scaling.md's own measurement did, into
# /tmp/search-20x.sqlite — reuse whatever script produced that plan's own 19.0x/18.7x/20.9x
# rows if one was banked; if not, duplicate every `cards` row under a new `key` (`box`/`idx`
# preserved so `_Places` still resolves them, `key` suffixed to stay unique) and re-run the
# migration against the copy so its FTS index is real, not stale.
```

Measure, five runs each, median, with `PKMNSCAN_HOME` pointed at each copy in turn:

1. **`do_search` latency, 1x store, before this change (the walk)** — call `do_search`
   with a query that matches ~1% of the store (a common set hint) and with a query that
   matches one card by exact SKU, timed the same way `store-scaling.md`'s own table was
   built (wall-clock around the call, warm store already opened).
2. **`do_search` latency, 1x store, after this change (FTS5)** — same two queries.
3. **`do_search` latency, 20x store, before and after** — this is the number that matters:
   the walk is O(cards) and FTS5 is O(matches + log(cards)), so the ratio here should be
   dramatically better than the ~19-21x seen on every other item in this plan; if it is
   NOT — if FTS5's ratio is anywhere near the walk's — something is wrong (an unindexed
   join back to `cards`, a missing `bm25` ORDER BY forcing a full scan, or a candidate set
   that is not actually narrowed) and must be diagnosed before merging, not shipped anyway.
4. **Index build time during migration, on the 20x copy** — the `_add_search_index` call's
   own wall-clock (backfill loop + rebuild), on the copy sized to what the owner expects to
   reach in two weeks. This is a ONE-TIME cost per store and belongs beside `_add_card_ids`'
   own measured 2.68-3.00s hashing figure (`store/db.py:333-336`'s comment) for scale.
5. **Store file size delta** — `store.sqlite` before and after migration, on the 1x and 20x
   copies. FTS5's shadow tables (`cards_fts_data` especially) are not free; report the
   absolute MB and the percentage of the pre-migration file size, the same way
   `docs/specs/store-scaling.md`'s own §0 photo-storage aside ("4.45 GB... 5.1 MB of
   captures and 16 MB of inventory") reports absolute figures rather than only ratios.

Record all of these in the PR description in the same table shape `store-scaling.md` §1
uses (`| Call | today | 20x rows | ratio | where it is pressed |`), so this item's own
numbers sit beside the plan's other measured rows for the next session that reads the file.

## Risks

- **FTS5 availability on CI's Linux Python.** `.github/workflows/check.yml:140-146` installs
  Python 3.11 via `actions/setup-python@v5` on `ubuntu-latest`. This playbook's Step 1
  confirms FTS5 on the rig's own `.venv` (macOS, sqlite 3.54.0) but that says nothing about
  the CI runner's interpreter, which is a *different* build of Python with its own bundled
  or system-linked SQLite. **Before merging, add the same one-line probe as an explicit CI
  step** (not buried inside T7, so a future Python-version bump on this workflow's pinned
  3.11 re-verifies automatically): `CREATE VIRTUAL TABLE ... USING fts5(x)` against an
  in-memory connection, failing loud with a clear message ("this Python's SQLite has no
  FTS5; `do_search` cannot run") rather than letting `_add_search_index` raise an opaque
  `sqlite3.OperationalError: no such module: fts5` three functions deep inside a schema
  migration on the first store open in CI. `actions/python-versions` builds have shipped
  FTS5-enabled SQLite in practice, but this repo's own standard ("measured rather than
  assumed") means CONFIRM it on the actual runner in this PR's own CI run, not by inference.
- **FTS5 and `WITHOUT ROWID`.** Nothing in this repo declares `cards` `WITHOUT ROWID` today
  (verified: `grep -n "WITHOUT ROWID" store/db.py` returns nothing), so the
  `content_rowid='rowid'` design in Step 3 is safe. If a FUTURE change ever converts `cards`
  to a `WITHOUT ROWID` table (there is no such plan; `docs/specs/store-scaling.md` does not
  propose one), this migration's external-content design breaks silently until re-keyed off
  a real integer column — worth a one-line comment at the `CREATE VIRTUAL TABLE` call site
  saying so, so the next session that touches `cards`' `_ddl` sees the dependency.
- **The reverse-migration byte-exact test.** Covered under Call sites; flagged here again
  because it is the one existing check this item is guaranteed to break if the Call sites
  fix is skipped, and `scripts/cid-selftest.py` is exercised by `make cid-selftest`, which
  IS in `make check`'s roster — a session that lands this item without updating
  `table_bytes` will see `make check` go red on an unrelated-looking table-count mismatch,
  and the failure will not obviously point back to this PR unless this risk is remembered.
- **Note is read from `payload` via `json_extract` in the triggers, not from an indexed
  column.** This is a deliberate, narrower choice than promoting `note` to a real `cards`
  column (Step 3's own comment explains why), but it means the FTS index's `note` field is
  one JSON parse away from the rest of the row rather than a plain column read — negligible
  per-write cost (one `json_extract` per insert/update/delete, already paid once per write
  regardless of FTS), flagged only so a future performance pass does not treat it as a
  puzzling asymmetry.
- **bm25's default column weighting.** The DDL in Step 3 declares seven columns
  (`name, number, sku, set_hint, note, number_key, number_display`) with no `rank=` clause,
  so `bm25(cards_fts)` weighs them equally by default. `_match_rank`'s own three-tier system
  (Step 4) is what actually decides exact/prefix/substring precedence for the FINAL sort key
  today, and bm25 only orders which SKUs are even considered "close" — so column weighting
  is unlikely to matter for correctness, but if a future session notices search feels
  mis-ordered, `bm25(cards_fts, <weights per column>)` is the first knob to reach for before
  touching `_match_rank` again.
