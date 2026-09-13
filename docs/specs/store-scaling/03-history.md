# Item 3 — history() scoped to the key

**CORRECTION, from the implementing session (branch `claude/scaling-03-history`): "Done
when" item 4 and the "second, cheaper win" it describes are WRONG, and were NOT built.**
The claim was that `_sell`'s and `do_retire`'s `else` branches (`undo=False`) "never read
`previous` or `origin_unknown`" — checked by reading only lines 7256-7283 / the retire
equivalent, which is the body of the `if undo: / else:` block. Both routes build their
response dict AFTER that block (`server/capture_server.py`, `_sell`'s `body = {...}` and
`do_retire`'s equivalent), and both unconditionally include `"restores_to": None if undo
else previous` — so a PLAIN sale or retirement's response DOES read `previous`, to tell the
caller what an undo would restore to before they tap it (the comment right there: "null on
a sale means the undo control should not be offered, which is worth knowing at the moment
of the sale rather than at the tap that fails"). Skipping the read on `undo=False` breaks
`restores_to` on every plain sale and retirement — confirmed by running `make harness`:
`check_mark_sold` and `check_retire` both failed with `restores_to` reading `None` instead
of the prior state. **This was caught by the harness, not merely reasoned about — the
skip was implemented, T7 was run, it failed, and the skip was reverted.** Steps 4 and 5
below are not built; `_sale_origin`/`_retirement_origin` are called unconditionally, same
as before this item, just against the new box-scoped `history_at(key)` (steps 1-3, which
stand and are the actual fix — a full-table scan on every sale/retire becomes an
indexed range scan bounded by box size). Test section C (the mock-spy skip proof) is
likewise not applicable and was not added.

## Goal and done-when

`Store.history()` (`store/db.py:1208-1225`) is `SELECT id, payload FROM events ORDER BY id`
followed by a `json.loads` per row — every row of the `events` table, unconditionally.
Measured in `docs/specs/store-scaling.md` §1: 16.5 ms at 12,654 events, 345 ms at 20x
(253,080 events, 20.9x). It is called, with zero arguments, from exactly three functions in
`server/capture_server.py`, and all three run **inside the store's write lock** on the
hottest reversal paths in the product: `_answer_origin` (line 5461), `_reverse_stand_down`
(line 6478, via `_clearing_event(store.history(), key)`), and `_origin` (line 7185, shared by
`_sale_origin` and `_retirement_origin`). Two of those four logical callers —
`_sale_origin`, read from `_sell` at line 7232, and `_retirement_origin`, read from
`do_retire` at line 7508 — are invoked **unconditionally**, including on a plain sale or a
plain retirement (`undo=False`). **This paragraph originally claimed the result is "computed
and never read" on a plain sale/retirement — that is WRONG, see the correction at the top of
this file: both routes' response bodies read `previous` unconditionally, via
`"restores_to": None if undo else previous`, to tell the caller what an undo would restore to
before they ask for one.** The read is genuinely unconditional and cannot be skipped; what
this item fixes is its SCOPE, not its frequency.

Every one of these readers wants the events of **one box**, not the whole store: each scans
backwards for lines whose `position` equals one key, plus (four of them: `_answer_before`,
`_clearing_event`, `_state_before_sale`, `_state_before_retirement`) the box's own
`renumbered` markers, which sit at a *different* position within the same box (see
"Read first" below — this is the one non-obvious fact that decides the shape of the fix).

**Done when:**

1. `store/db.py` has a new function, `events_at(conn, key)`, that reads only the events
   whose `position` shares `key`'s box — using the `events_position` index that already
   exists (`store/db.py:139`), with **no schema change and no migration** (see "Read first" —
   this is not the column-and-backfill case the umbrella task worried about, because
   `position` is already a first-class indexed column and it already encodes the box).
2. `store/session.py`'s `Store` gets a matching `history_at(key)` method, mirroring
   `history()` and `named_events()`.
3. All three call sites in `server/capture_server.py` (`_answer_origin`,
   `_reverse_stand_down`, `_origin`) call `store.history_at(key)` instead of
   `store.history()`.
4. ~~`_sell` (line ~7232) and `do_retire` (line ~7508) skip the `_sale_origin` /
   `_retirement_origin` read entirely when `undo` is `False`~~ — **NOT BUILT, see the
   correction at the top of this file: both routes' responses read `previous`
   unconditionally to populate `restores_to`, so the read cannot be skipped without
   breaking that field on every plain sale/retirement.**
5. `make harness` T7 is green, including a new assertion that the scoped read returns
   exactly the box-scoped subset of `Store().history()` (functional correctness) and a new
   assertion that the SQL it runs uses the index rather than a table scan (the performance
   claim, made checkable rather than trusted).
6. The stale prose naming these three functions as the `history()` readers
   (`server/capture_server.py:980-993`) is corrected to say they read `history_at(key)` now
   — see "Allowlist entries removed" for why the mechanical `sole reader` docs-audit row
   does not need a matching edit.
7. `docs/specs/store-scaling.md`'s row for `Store.history()` in the measured table (§1) is
   either updated with a post-fix figure or marked "fixed, see the decision entry item 3's PR adds" —
   whichever this session's own measurement supports (see "Measure").

## Depends on / conflicts with

- **No dependency on item 1 or item 2** of the plan (`Inventory.to_payload()` /
  `do_orders()`) — this item touches `store/db.py`, `store/session.py` and the
  sale/retirement/answer/stand-down paths in `server/capture_server.py` exclusively. Those
  two items touch `Rows`/`Inventory.to_payload` and `_Places`/`do_orders`. No shared function.
- **Conflicts if run concurrently with any branch editing `server/capture_server.py` lines
  5440-7600** (the `_answer_origin` / `_clearing_event` / `_sale_origin` / `_retirement_origin`
  / `_sell` / `do_retire` block) or `store/db.py` lines 1190-1260 (the `history`/
  `events_named` block). Check `git log --oneline -5 -- server/capture_server.py store/db.py`
  and `make coordinator` before starting if this plan is being split across sessions.
- **Independent of the `_copies_out` item** (item 4 in the plan) — different table
  (`cards`/`listings`, not `events`), different file region.
- Reads `docs/specs/store-scaling.md` (item 3's own paragraph, §1's table row) and
  `CLAUDE.md`'s D88 paragraph, per the umbrella task; both are read-only inputs here, not
  edited by this file (this playbook's only write is itself).

## Read first

- `store/db.py:1-52` — the module docstring (D88): one file, one transaction per
  `Store.write()`, WAL, indexed columns "derived from the object at write time" that
  "cannot disagree with the payload."
- `store/db.py:113-142` — `TABLES`, `_INTEGER`, `_INDEXES`. **`events` is not in `TABLES`**
  (it is DDL'd separately at `store/db.py:266-269`) but IS in `_INDEXES`:
  `("events", "position")` at line 139. That index already exists on every store on disk,
  fresh or upgraded — it is created unconditionally in the `stored is None` branch
  (`store/db.py:264-272`, which runs for a fresh store) and there is no `_upgrade` step that
  could have skipped it for an older one, because `_INDEXES` has never changed shape across
  `SCHEMA_VERSION` 1-4 (confirm with `git log -p --follow -- store/db.py | grep -n "events.*position"`
  before relying on this, but as of this branch it is unconditional).
- `store/db.py:264-272` — the `events` table DDL itself:
  `CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, event
  TEXT, position TEXT, payload TEXT NOT NULL)`. Four denormalised columns
  (`at`, `event`, `position`) plus the whole record as `payload` JSON — this is the general
  shape D88's docstring describes for every table, and `events` already has the column this
  task worried might not exist.
- `store/db.py:1192-1205` — `append_events`, the only writer: `position` is written from
  `event.get("position")`, which is `_history`'s own `record["position"] = key` (see next
  bullet). **It is a plain column, not something buried in `payload`.**
- `server/capture_server.py:1888-1922` — `_history(inventory, event, key, **extra)`. `key`
  becomes `record["position"]` when not `None` (line 1919-1920); `extra` values are folded in
  when not `None` (line 1921). This is the one function that ever appends an event, so
  reading it fully is reading the whole shape of every row `events_at` will have to filter.
- `store/master.py:243-244` — `position_key(box, index) -> f"{int(box)}/{int(index)}"`. Every
  `key` passed anywhere in this file is this exact shape (verified: every call in
  `server/capture_server.py` goes through `master.position_key(box, index)`, no other format
  exists). This is what makes a box-prefix `GLOB` safe and exact.
- **The one fact that decides the whole design — read this twice.**
  `server/capture_server.py:4140-4203`, inside the mid-box delete (`do_remove_card`'s body):
  the deleted card's own key is `key = master.position_key(box, index)` (bound earlier in the
  function, not shown in this range — it is the same `key` used at `del
  inventory.cards[key]`, line 4141). The `RENUMBERED` event is appended at line 4196-4203:
  ```python
  _history(
      inventory,
      RENUMBERED,
      key,                      # <- the DELETED card's key, e.g. "3/5"
      box=int(box),
      count=len(movers),
      **{"from": int(index)},
  )
  ```
  So a `renumbered` line's `position` is the **deleted** card's position — a different index
  than any of the movers it describes, but **the same box**. Every mover's own state line is
  logged separately, at *its own new key* (the "ONE STATE LINE PER SHIFTED CARD, AT ITS NEW
  POSITION" comment at `server/capture_server.py:4204-4209`). The four readers below all rely
  on being able to see the `renumbered` marker when asked about a *mover's* key — which means
  `position = key` alone is the WRONG scope. The correct scope is **the box**, because
  `renumbered`'s `position` and every mover's `position` share the same `"{box}/"` prefix.
- `server/capture_server.py:5380-5443` — `_answer_before(events, key)`. Scans `events`
  reversed; the `RENUMBERED` guard at lines 5420-5428 checks `event.get("box") == at_box`
  (not `event.get("position") == key`) — confirming the box-scope, not position-scope,
  requirement directly in the reader's own code.
- `server/capture_server.py:6263-6289+` (`_clearing_event`) — identical shape: parses
  `at_box, at_index` from `key` (line 6278), then checks `event.get("box") == at_box` for the
  `RENUMBERED` guard (line 6285).
- `server/capture_server.py:7046-7105` (`_state_before_sale`) and `:7108-7138`
  (`_state_before_retirement`) — these two do **not** have a `RENUMBERED`/box guard; they
  filter purely on `event.get("position") == key` (lines 7098, 7131). A box-wide scope is
  still correct for them (it is a superset, not a mismatch) — they simply ignore the
  extra rows for other positions in the box, exactly as `history()`'s current full-store read
  lets them ignore rows for every *other* box today.
- `server/capture_server.py:7141-7196` — `_sale_origin`, `_retirement_origin`, `_origin`.
  `_origin` is the one place that actually calls `store.history()` (line 7185) and hands the
  result to whichever reader (`_state_before_sale` or `_state_before_retirement`) it was given.
- `server/capture_server.py:7198-7297` (`_sell`) — read in full. Line 7232:
  `previous, origin_unknown = _sale_origin(Store(snapshot.directory), key)` runs **before**
  the `if undo:` branch (line 7235). The `else` branch (a plain sale, lines 7256-7283) never
  reads `previous` or `origin_unknown` — confirmed by reading every line between 7256 and
  7283 inclusive; the names appear nowhere in that range.
- `server/capture_server.py:7434-7583` (`do_retire`), specifically line 7508:
  `previous, origin_unknown = _retirement_origin(store, key)`, again before `if undo:` (line
  7511). The `else` branch (a plain retirement, lines 7546-7583) never reads either name —
  confirmed the same way.
- `store/db.py:1228-1252` — `events_named(event)`, the existing scoped-by-event-name sibling
  (D134). Its own docstring is explicit that it is an **unindexed scan** ("the events table
  has none of its own [index]") — that sentence is about a `WHERE event = ?` filter, and it
  predates the box-scoping this item adds; it does NOT mean `position` is unindexed (it is,
  per `_INDEXES` above). Do not let this docstring's framing lead you to add a migration —
  `events_named` and `events_at` are solving different problems (filter by event name, which
  has no column of its own to index cheaply without a migration, vs. filter by box, which the
  `position` column already supports).
- `store/session.py:140-209` — `Store.read()`, `Store.write()`, `Store.history()` (line 179),
  `Store.named_events()` (line 187), `Store.buried()` (line 201). Copy this file's own
  pattern: open a connection, call the `db.py` function, close it in `finally`.
- `scripts/docs-audit.py:2652-2708` — `_HISTORY_READER_ROOTS` and `_history_readers()`. **This
  AST walker counts only zero-argument `.history()` calls** (`if node.args or
  node.keywords: continue` at line 2702-2703). After this change, all three production call
  sites become `store.history_at(key)` — a call with an argument — so `_history_readers()`
  will return an **empty list** in production code (`server`, `store`, `pipeline`, `cli`,
  `identify`, `geometry`, `codes`; verified nothing outside `server/capture_server.py` calls
  bare `.history()` in production — see "Call sites"). This is fine and self-correcting: the
  row's summary string is built from `len(readers)` at run time
  (`scripts/docs-audit.py:3068`, `f"{len(readers)} history readers, every claim about them
  counts right"`) — it will print `0 history readers...` and stay green, because nothing in
  the tree currently asserts "there are exactly N" as a literal; it asserts "every claim about
  a specific function being the sole reader agrees with the live list," and there is no
  currently-passing claim of that shape that this change breaks (checked: the only
  candidate text, `server/capture_server.py:984`, says `` the only reader of `history.jsonl` ``
  — a filename with a dot, which `_SOLE_READER_RE`'s `` `([A-Za-z_][A-Za-z0-9_]*)` `` character
  class cannot match, so it was never counted as a match and stays inert). **Do not add a
  migration or a docs-audit change for this row** — verify it stays green, do not touch it.
- `server/capture_server.py:972-1000` — the comment block this item DOES need to hand-edit
  (see "Steps" #6): "The readers are `_answer_origin`, `_origin` and `_reverse_stand_down`."
  This is prose, not matched by any mechanical check (confirmed above), so it will not fail a
  commit if left stale — but it will be **wrong**, in the same way the comment it replaced in
  2026-09-05 was wrong, and this repo's own `sole reader` row exists specifically because that
  kind of drift shipped once already. Fix it in the same commit.
- `harness/tests/t7_store_and_seams.py:5166-5405` (`check_mark_sold`) and `:5494+`
  (`check_retire`, confirmed at line 5494) — the existing coverage for the two `undo`-gated
  callers this item changes. `harness/tests/t7_store_and_seams.py:5472-5480` —
  `events_for(key)` / `last_event(key)`, the test-side helpers already used throughout this
  file (`[event for event in Store().history() if event.get("position") == key]`) — this
  is your ground truth for the functional-equivalence assertion in "Tests," and it is a
  precedent for "filter the full read in Python and compare," which is exactly what the new
  test should do to prove `events_at` didn't drop or add anything a caller needs.
- `harness/tests/t7_store_and_seams.py:6210-6231` (`check_history`) — the section documenting
  the three route-written non-state events (`corrected`, `removed`, `answered`/`stood_down`
  family) and the disjointness assertion between them and `master.STATES`. Read this before
  writing new assertions nearby so the new ones sit in the right section rather than
  duplicating `check_history`'s job.
- `harness/tests/t7_store_and_seams.py:238-246` — imports already in scope: `db`, `files`,
  `master`, `Store` are all imported; `sqlite3` is imported in `store/db.py` but **not** in
  the test file — add `import sqlite3` only if you go the `set_trace_callback` route (see
  "Tests"; the recommended route uses `db.connect` + `EXPLAIN QUERY PLAN`, which needs no new
  import beyond what test file already has via `db`).
- `docs/specs/store-scaling.md` §0-§2 — the failure mode this whole plan corrects
  (`Rows.where`/`select` degrading to a Python-side filter after one unfiltered load, and
  `_copies_out`'s O(listings × cards)). `history()` is a different mechanism (a raw SQL
  query, not `Rows`), so none of that machinery applies here — this item's fix is entirely a
  SQL `WHERE` clause, not a `Rows` scoping fix.
- `CLAUDE.md`'s D88 paragraph ("THE STORE OF RECORD IS ONE SQLITE FILE...") — read for the
  transaction/lock discipline: `history_at` must be safe to call **inside** a
  `Store.write()` session exactly as `history()` is today. `store/db.py:213-230`
  (`_ensure_schema`'s docstring) explains why this matters: `Store(snapshot.directory)
  .history()` opens a **second connection** inside an open write transaction, and a
  version-check happens on every open — so a new read-only function following the same
  `db.connect()` → query → close pattern is safe by construction; nothing needs a lock
  argument, because `events_at` never writes.

## Steps

**No migration step.** Verified above: `position` is already a column on `events`
(`store/db.py:266-269`), it is already indexed (`store/db.py:139`,
`("events", "position")`, created unconditionally for every store — fresh or upgraded — since
`_INDEXES` is applied at `store/db.py:271-272` with no version gate), and it already encodes
the box (`f"{box}/{index}"`, `store/master.py:243-244`). A `GLOB` query with a literal prefix
is index-friendly in SQLite regardless of the `LIKE`/case-sensitivity caveats that would apply
to `LIKE` — confirmed on this schema:

```
$ python3 - <<'EOF'
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, event TEXT, position TEXT, payload TEXT NOT NULL)")
conn.execute("CREATE INDEX events_position ON events(position)")
for i in range(50000):
    conn.execute("INSERT INTO events (at, event, position, payload) VALUES (?,?,?,?)",
                 ("t", "captured", f"{i % 20}/{i // 20}", "{}"))
conn.commit()
print(conn.execute(
    "EXPLAIN QUERY PLAN SELECT id, payload FROM events WHERE position GLOB ? ORDER BY id",
    ("3/*",),
).fetchall())
EOF
[(4, 0, 164, 'SEARCH events USING INDEX events_position (position>? AND position<?)'), (17, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')]
```

The `SEARCH ... USING INDEX events_position` line is the proof: SQLite's `GLOB` optimiser
rewrote a literal-prefix pattern into an indexed range scan, the same mechanism `events_named`'s
own docstring describes for `LIKE`. Re-run this snippet (or the equivalent inside "Measure")
against the real store before writing code, so the plan text you cite in the new docstring is
this session's own reading and not a copy of the one above.

### 1. Add `store/db.py:events_at`

Insert immediately after `events_named` (which ends at line 1252) and before `dump_tables`
(line 1255):

```python
def events_at(conn: sqlite3.Connection, key: str) -> List[dict]:
    """Every event that could bear on one position, oldest first. `history()`'s scoped
    sibling for the reversal readers (`_answer_before`, `_clearing_event`,
    `_state_before_sale`, `_state_before_retirement`), which today load the whole table and
    filter it in Python.

    SCOPED TO THE BOX, NEVER TO THE BARE POSITION, and that is not a wider margin chosen for
    safety — it is what correctness requires. A `renumbered` line's `position` is the
    DELETED card's own key, not any mover's (`server/capture_server.py:_history`, called
    from the mid-box delete at `server/capture_server.py:4196-4203`), so a mover's own
    reversal has to see a line filed under a DIFFERENT position in the same box to learn a
    shift happened above it (D10 ruling 1). `position` is always `f"{box}/{index}"`
    (`store/master.py:position_key`), so every event that could matter to a reversal at
    `key` shares its box's prefix, and that is exactly the set `_answer_before`,
    `_clearing_event`, `_state_before_sale` and `_state_before_retirement` scan for today
    after loading everything ever written.

    GLOB, NOT LIKE. GLOB does a byte comparison and SQLite's optimiser turns a literal-prefix
    GLOB into a range scan on the `events_position` index regardless of
    `case_sensitive_like` — measured on this schema: `EXPLAIN QUERY PLAN` for
    `... WHERE position GLOB '3/*'` reports `SEARCH events USING INDEX events_position
    (position>? AND position<?)`, the same index `history()`'s unindexed full scan never
    touches. No new column and no migration: `position` has been a plain, indexed column
    since this table's DDL (`store/db.py:264-272`), unconditionally, for every schema
    version this store has ever carried.

    A `key` that is not `box/index` cannot be box-scoped, and this never guesses at one: it
    falls back to the full, slow, correct read rather than silently returning an empty or
    wrong-scoped list to a caller whose answer feeds a refusal message.

    Same one-bad-row refusal as `history()` and `events_named()`, for the identical reason.
    """
    box = str(key).split("/", 1)[0]
    if not box.isdigit():
        return history(conn)
    rows = conn.execute(
        "SELECT id, payload FROM events WHERE position GLOB ? ORDER BY id",
        (f"{box}/*",),
    ).fetchall()
    out = []
    for row_id, text in rows:
        try:
            out.append(json.loads(text))
        except ValueError as exc:
            raise files.StoreError(
                f"history event {row_id} in {DB_NAME} is not valid JSON: {exc}"
            ) from exc
    return out
```

Notes on the body:
- `str(box).isdigit()` refuses a negative or empty box rather than building a `GLOB` pattern
  that could match nothing or (worse) something unintended; `position_key` only ever
  produces non-negative integers, so a non-digit box means `key` was not produced by it, and
  the safe answer is the full read, not a guess.
- Do **not** special-case `position = key` in addition to the `GLOB` — `key` itself always
  starts with `f"{box}/"`, so `GLOB f"{box}/*"` already contains it; a second clause would be
  redundant and would invite the two clauses drifting apart later.
- Mirror `history()`'s exact error string (`f"history event {row_id} in {DB_NAME} is not
  valid JSON: {exc}"`) so a corrupt-log operator sees one wording regardless of which reader
  found the bad row.

### 2. Add `store/session.py:Store.history_at`

Insert after `history()` (ends line 185) and before `named_events()` (line 187):

```python
    def history_at(self, key: str):
        """The events that could bear on one position, oldest first. `history()`'s scoped
        sibling (the decision entry item 3's PR adds): the reversal readers each want one card's own
        lines plus its box's `renumbered` markers, not a full-table load filtered in
        Python. See `db.events_at`'s docstring for why the scope is the box and not the
        bare position.
        """
        conn = db.connect(self.directory)
        try:
            return db.events_at(conn, key)
        finally:
            conn.close()
```

Use the placeholder citation `the decision entry item 3's PR adds` verbatim (a slug, not a guessed
number) — this repo claims decision numbers at merge time (`make claim-ids`, D140, D187); do
not write a literal `D189` or similar. Add a matching entry under `docs/decisions/` with that
same heading slug in whatever this session's own step for "write the decision entry" is (this
playbook's own scope is `docs/specs/store-scaling/03-history.md` only — the implementing
session does this as an ordinary part of the change, per `CLAUDE.md`'s "Scope is argued, not
gated" rule and the decisions-as-a-directory convention, `decisions-is-a-directory.md`).

### 3. Repoint the three call sites in `server/capture_server.py`

**3a. `_answer_origin`, line 5461** (inside the `try:` at 5460-5461):

Before:
```python
    try:
        events = store.history()
```
After:
```python
    try:
        events = store.history_at(key)
```

**3b. `_reverse_stand_down`, line 6478:**

Before:
```python
        try:
            event = _clearing_event(store.history(), key)
```
After:
```python
        try:
            event = _clearing_event(store.history_at(key), key)
```

**3c. `_origin`, line 7185** (inside the `try:` at 7184-7185):

Before:
```python
    try:
        events = store.history()
```
After:
```python
    try:
        events = store.history_at(key)
```

`_origin` already receives `key` as a parameter (signature at line 7182:
`def _origin(store: Store, key: str, reader) -> ...`), so this is a pure substitution — no
signature change anywhere in this step.

### 4. Skip `_sale_origin` entirely when `undo` is false, in `_sell`

`server/capture_server.py:7223-7232`. Before:
```python
    previous, origin_unknown = _sale_origin(Store(snapshot.directory), key)
    was = card.state

    if undo:
```
After:
```python
    # Only the `if undo:` branch below ever reads either name — a plain sale never asks
    # what state to restore, because there is nothing to restore. Reading history for a
    # sale that isn't a reversal was pure waste even before it was a SCOPED read, and it is
    # measured waste now: a Fulfiller marking a hundred cards sold a day paid one events
    # read per press for an answer the route never looked at.
    previous, origin_unknown = (
        _sale_origin(Store(snapshot.directory), key) if undo else (None, None)
    )
    was = card.state

    if undo:
```
Leave every line of the surrounding comment (7223-7231) as is — it is still accurate about
why the read happens inside the lock and before either branch writes; it says nothing about
`undo`, so nothing there goes stale. Do not restructure `_sell` further than this one
substitution: `was = card.state` and the rest of the function are unchanged.

### 5. Skip `_retirement_origin` entirely when `undo` is false, in `do_retire`

`server/capture_server.py:7504-7511`. Before:
```python
        previous, origin_unknown = _retirement_origin(store, key)
        was = card.state

        if undo:
```
After:
```python
        # `_retirement_origin`'s twin optimization in `_sell` — only the `if undo:` branch
        # below reads either name. A plain retirement never asks what state to restore.
        previous, origin_unknown = _retirement_origin(store, key) if undo else (None, None)
        was = card.state

        if undo:
```

### 6. Correct the stale reader roster comment

`server/capture_server.py:980-993`. The sentence "The readers are `_answer_origin`,
`_origin` and `_reverse_stand_down`." (line 986-987) is still true about *which functions*
read the history, but it is now inaccurate about *how* — all three call `history_at(key)`,
not `history()`. Reword the sentence (keep everything else in the block, including the
"WHICH IS WHY THE ROSTER IS NOT COUNTED IN PROSE ANY MORE" argument, which stands
unaffected) to something in this shape:

```
# The readers are `_answer_origin`, `_origin` and `_reverse_stand_down`, and since
# the decision entry item 3's PR adds none of them reads the whole table any more — each calls
# `Store.history_at(key)`, scoped to the position's own box (`store/db.py:events_at`).
```

Do not touch the ordinal list below it (`corrected`, `removed`, `answered`/`stood_down`) —
that is the event-name vocabulary, unrelated to how it is read back.

### 7. Update `docs/specs/store-scaling.md`'s measured table

§1's table row for `Store.history()` currently reads the pre-fix numbers (16.5 ms / 345 ms /
20.9x). After this change, re-measure per "Measure" below and either replace the row with the
post-fix figures (expected: flat, sub-millisecond, independent of store size, dominated by
box size rather than store size) or add a note beside it naming the fix and pointing at the
new decision entry, following this file's own convention of keeping pre-fix numbers
visible with a dated correction rather than silently overwriting them (see `docs/GATES.md`'s
own rule, cited in `CLAUDE.md`: "Those numbers are evidence and are never rewritten to match a
later tree.").

## Call sites (complete)

Every production, zero-argument `Store.history()` (equivalently `store.history()` /
`db.history(conn)`) call, verified by grepping `server/`, `store/`, `pipeline/`, `cli/`,
`identify/`, `geometry/`, `codes/` for `\.history()` (the same roots
`scripts/docs-audit.py:_HISTORY_READER_ROOTS` walks):

| # | File:line | Function | Caller of the function | Undo-gated? | Action |
|---|---|---|---|---|---|
| 1 | `server/capture_server.py:5461` | `_answer_origin` | `do_answer`'s undo branch (call site at `server/capture_server.py:6639`, itself inside the route's `if undo:`) | Already gated at the call site one level up | Step 3a: `store.history_at(key)` |
| 2 | `server/capture_server.py:6478` | `_reverse_stand_down` | route body itself (this whole function is the undo of a stand-down) | The function is inherently an undo | Step 3b: `_clearing_event(store.history_at(key), key)` |
| 3 | `server/capture_server.py:7185` | `_origin` | `_sale_origin` (→ `_sell`) and `_retirement_origin` (→ `do_retire`) | See rows 4-5 | Step 3c: `store.history_at(key)` |
| 4 | `server/capture_server.py:7232` | `_sell`, via `_sale_origin` → `_origin` | `do_mark_sold` | **No — read unconditionally today** | Step 4: gate the call on `undo` |
| 5 | `server/capture_server.py:7508` | `do_retire`, via `_retirement_origin` → `_origin` | route itself | **No — read unconditionally today** | Step 5: gate the call on `undo` |

No other production call exists (`grep -rn "\.history()" server/ store/ pipeline/ cli/
identify/ geometry/ codes/` returns only the three lines above plus two `store/db.py`
docstring mentions of the phrase, which are prose, not calls). `pipeline/pricehistory.py` has
an unrelated method of the same name taking `(product, range)` — `docs-audit.py:2674-2677`
already disambiguates this by requiring zero arguments; nothing here changes that
disambiguation.

**Deliberately left on the full, unscoped read** — none, in production code. Every
production caller of `history()` is one of the three functions above, and every one of them
wants exactly one key's box. `store.history()` and `db.history(conn)` themselves are **not
deleted** — they stay for:
- `harness/tests/t7_store_and_seams.py`'s ~30 test-only call sites (ground truth for
  comparisons; several are listed in "Read first" and reused verbatim in "Tests" below —
  none of these need to change).
- Any future caller that genuinely needs the whole log (e.g. a `#/graveyard`-style report,
  though that screen already uses `Store.buried()`/`named_events()`, not `history()`).
- The CLI/audit surface, if one is ever added (none exists today — verified above).

## Tests (T7 check + assertions; mutation arm)

All new assertions belong in `harness/tests/t7_store_and_seams.py`. Two additions:

### A. Functional equivalence — `events_at` drops nothing a reader needs and adds nothing wrong

Add inside (or immediately after) `check_history` (starts line 6210), using the existing
`isolated_home()` fixture and the file's own `events_for(key)` helper (line 5472-5475) as the
comparison oracle:

```python
def check_history_scoped_read(checks: Checks) -> None:
    """`db.events_at` is a scope, not a rewrite: at any key, it must equal the box-filtered
    slice of the full log a reversal reader already gets today, one row at a time, filtered
    in Python. The one thing worth proving on purpose is the `renumbered` case (D10 ruling
    1) — the line that sits at the DELETED card's key, not any mover's, and that a
    box-narrower scope (bare `position = key`) would have dropped silently.
    """
    checks.note("")
    checks.note("HISTORY — events_at is scoped to the box, not the position")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))
        for _ in range(2):
            capture_server.do_capture(capture_payload(7))  # a second box, for cross-box isolation

        # A correction and an answer at 3/1, so the box has more than one event kind.
        capture_server.do_put_card(3, 1, {"variant": "reverse_holo"})

        # A mid-box delete of 3/1 renumbers 3/2 and 3/3 down by one and logs `renumbered` at
        # position "3/1" — the DELETED key, per server/capture_server.py:4196-4203.
        capture_server.do_remove_card(3, 1, {})

        full = Store().history()
        box3 = str(db.connect(files.inventory_dir()).close() or None)  # placeholder removed below

        conn = db.connect(files.inventory_dir())
        try:
            scoped = db.events_at(conn, master.position_key(3, 1))
        finally:
            conn.close()

        expected = [
            e for e in full
            if str(e.get("position", "")).split("/", 1)[0] == "3"
        ]
        checks.equal(
            scoped, expected,
            "events_at(3/1) equals the box-3 slice of the full history, byte for byte",
        )

        renumbered = [e for e in scoped if e.get("event") == capture_server.RENUMBERED]
        checks.ok(
            len(renumbered) == 1,
            "and the renumbered marker — filed at the DELETED key, not any mover's — is "
            "still visible: a position-only scope would have dropped it",
            f"scoped renumbered events: {renumbered!r}",
        )

        cross_box = [e for e in scoped if str(e.get("position", "")).split("/", 1)[0] == "7"]
        checks.equal(
            cross_box, [],
            "and box 7's events are absent: the scope is one box, never the whole store",
        )

        # The reversal itself still works end to end through the new path.
        checks.equal(
            capture_server._state_before_sale(
                db.events_at(db.connect(files.inventory_dir()), "3/2"), "3/2"
            ),
            capture_server._state_before_sale(Store().history(), "3/2"),
            "and the reader that actually decides an undo agrees, scoped or not",
        )
```

Delete the stray placeholder line (`box3 = ...`) above before landing this — it was left in
this playbook only to flag that no `EXPLAIN`-based assertion belongs in this function; that
goes in test B. Also confirm `capture_server.do_remove_card` is the correct route name for
the mid-box delete (grep `def do_remove_card` in `server/capture_server.py`; it is the
function whose body was read in full under "Read first" — if a rename has happened, use the
current name).

### B. The read is scoped, not merely correct — assert the SQL plan uses the index

This is the check that makes the *performance* claim testable rather than trusted, per this
plan's own §1 methodology ("nothing here was taken from a report without being re-run"):

```python
def check_history_scoped_uses_index(checks: Checks) -> None:
    """`events_at`'s scope is provable in code, but a session six months from now could
    "simplify" the WHERE clause back into a full scan and every functional test above would
    still pass — the box-3 slice of an unscoped read is still the box-3 slice. This is the
    row that would catch that: it asserts the query plan, not the query's output.
    """
    checks.note("")
    checks.note("HISTORY — events_at reads the index, not the table")

    with isolated_home():
        capture_server.do_capture(capture_payload(3))
        conn = db.connect(files.inventory_dir())
        try:
            plan = conn.execute(
                "EXPLAIN QUERY PLAN SELECT id, payload FROM events WHERE position GLOB ? "
                "ORDER BY id",
                ("3/*",),
            ).fetchall()
        finally:
            conn.close()
        plan_text = " | ".join(str(row) for row in plan)
        checks.ok(
            "USING INDEX events_position" in plan_text,
            "the scoped query plan names the events_position index",
            plan_text,
        )
        checks.ok(
            "SCAN events" not in plan_text,
            "and never falls back to a full table scan",
            plan_text,
        )
```

Register both new functions in this file's own list of checks that `run()` (or whatever this
file's dispatcher is called — grep `check_mark_sold(checks)` at line 26631 for the pattern
and add both new calls immediately after it, since they belong to the same "HISTORY" section
as `check_history` and follow `check_mark_sold`/`check_retire` in read order).

### C. The two "second win" skips, folded into existing sections

`check_mark_sold` (line 5166) already exercises a plain sale (line 5219:
`capture_server.do_mark_sold(3, 1, {})`) and its undo (line 5282). No new assertion is
strictly required for step 4's behavior change — the existing plain-sale case already
proves a plain sale still succeeds and still returns the right `previous_state` on a
*later* undo, since `_sale_origin` is still called (with `undo=True`) at that point. Add one
assertion that makes the skip itself visible rather than merely unbroken:

```python
        # A plain sale computes nothing about restoration — added for step 4's fix, so a
        # regression that starts reading history again on every sale shows up as a behavior
        # difference here rather than only as a benchmark regression nobody runs per commit.
        with unittest.mock.patch.object(
            capture_server, "_sale_origin", wraps=capture_server._sale_origin
        ) as spy:
            capture_server.do_mark_sold(3, 2, {})
            checks.equal(
                spy.call_count, 0,
                "a plain sale never calls _sale_origin — only its own undo does",
            )
```

Check whether `unittest.mock` is already imported in this test file (`grep "^import
unittest" harness/tests/t7_store_and_seams.py`); add the import if not. If this file's own
convention avoids `unittest.mock` entirely (several of this repo's tests prefer plain
functional assertions — check for existing `mock.patch` usage before introducing the first
one), use a simpler proof instead: assert that a plain sale still succeeds when
`inventory/store.sqlite`'s `events` table is temporarily made unreadable in a way that would
raise from *any* history read (e.g., corrupt one row via `append_history`/`corrupt_history`,
already present at lines 398-410, then confirm `do_mark_sold(3, 2, {})` with `undo=False`
still succeeds even though `Store().history()` now raises `StoreError`). This is the stronger
test — it proves the skip by proving a corrupt log cannot block a plain sale — and it matches
this file's existing `corrupt_history()` fixture rather than introducing a new mocking
pattern. Prefer this version if in doubt. Mirror it once more for `do_retire` in the section
`check_retire` covers (starts line 5494).

### Mutation arm

State the one mutation this repo's harness convention (per `make reap-selftest`,
`make silent-write-selftest`, etc. — "prove the guard by reproducing what it must catch")
would run, even if this session does not have a mutation-testing tool wired to this file:
**revert `events_at`'s `WHERE position GLOB ?` to `history(conn)` unconditionally** (i.e.,
make the "scoped" function a thin unscoped wrapper again). Test A (functional equivalence)
would still pass — that is the point of naming this arm — because an unscoped read is a
superset that still equals the box-filtered comparison after Python-side filtering nowhere
in test A. **Test B is the one that goes red**: `plan_text` would show
`SCAN events` (a full-table scan) with no `GLOB` predicate at all, since the mutated function
never issues that query. This is exactly why both tests are required together — a purely
functional test cannot distinguish "scoped" from "correct," and this fix is worthless if it
regresses to the latter.

## Allowlist entries removed

**None.** Checked the two candidates:

- `scripts/docs-audit-allow.txt` (the general "planned but not yet built" registry, read via
  `scripts/docs-audit.py:842-897`) has no entry naming `store/db.py`, `events`, `history`, or
  any function touched here. This change does not add, remove, or need an allowlist entry.
- The `sole reader` docs-audit row (`scripts/docs-audit.py:3017-3070`,
  `_history_readers()` at `:2671-2708`) is **not** an allowlist and needs no edit — see "Read
  first" for the full argument that its dynamic count (currently 3, becoming 0 after this
  change) self-corrects and stays green. If a future session ever needs to make this row
  aware of a *scoped* reader (e.g., to assert "every scoped reader passes a real key"), that
  would be new surface area on `docs-audit.py` itself and belongs to a session that has a
  concrete reason to want it — not manufactured here.

The events-table analogue the task template asks to name, if one were needed, would be a row
asserting every caller of `events_at` passes a real `box/index` key rather than `None` or a
malformed string — this function already degrades safely (falls back to the full read) rather
than needing a guard, so no such row is proposed.

## Do not touch

- `db.history(conn)` and `Store.history()` themselves — kept, unscoped, for the test file's
  ~30 call sites and any future full-log reader. Do not delete or rename them.
- `db.events_named(conn, event)` / `Store.named_events(event)` / `Store.buried()` — a
  different scoping axis (event name, not box); this item's `events_at` is a sibling, not a
  replacement.
- `_answer_before`, `_clearing_event`, `_state_before_sale`, `_state_before_retirement` —
  their filtering logic is unchanged; they still receive a list of events and scan it exactly
  as before. Only what produces that list changes (box-scoped now, instead of whole-store).
- `_answer_origin`'s and `_reverse_stand_down`'s callers (`do_answer`, the stand-down route) —
  both already gate their own call correctly (undo-only for `do_answer`'s branch;
  `_reverse_stand_down` is inherently an undo). Do not add a redundant `if undo:` guard around
  steps 3a/3b — there is nothing to skip there, unlike steps 4/5.
- `Rows`, `Inventory.to_payload()`, `_Places`, `_copies_out` — items 1, 2 and 4 of the plan.
  Nothing in this item touches `cards`, `boxes`, `listings`, or any table besides `events`.
- The `_ensure_schema` / `_upgrade` / `SCHEMA_VERSION` machinery in `store/db.py` — this item
  adds no migration, so `SCHEMA_VERSION` (currently 4, per `store/db.py:95`) does not change
  and no `if stored < N:` branch is added to `_upgrade`.
- `docs/specs/store-scaling.md`'s other three rows (`Inventory.to_payload()`, `do_orders()`,
  `_copies_out`) — update only the `Store.history()` row per Step 7.

## Measure

Reproduce the plan's own recipe (`docs/specs/store-scaling.md`'s methodology: a `.backup`
copy of the real store, then the same copy with every row of `cards` and `events` duplicated
20x). From the repo root, with `PKMNSCAN_HOME` pointed at a scratch copy (never the owner's
live store):

```bash
# 1. Take a live backup copy (adjust the source path to wherever the real store's
#    inventory/ directory lives on this machine; never open the original with a write mode).
mkdir -p /tmp/store-scaling-measure/base
python3 - <<'EOF'
import sqlite3, pathlib
src = pathlib.Path("<owner's real inventory dir>/store.sqlite")
dst = pathlib.Path("/tmp/store-scaling-measure/base/store.sqlite")
conn = sqlite3.connect(str(src))
bck = sqlite3.connect(str(dst))
conn.backup(bck)
bck.close(); conn.close()
EOF

# 2. Build the 20x copy alongside it (duplicate every cards and events row under new keys/ids).
python3 - <<'EOF'
import sqlite3, shutil, pathlib
base = pathlib.Path("/tmp/store-scaling-measure/base/store.sqlite")
big = pathlib.Path("/tmp/store-scaling-measure/20x/store.sqlite")
big.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(base, big)
conn = sqlite3.connect(str(big))
cards = conn.execute("SELECT key, box, idx, state, sku, condition, capture_id, name, number, "
                      "game, set_hint, run, captured_at, state_at, cid, payload FROM cards").fetchall()
for n in range(1, 20):
    for row in cards:
        key = f"{row[0]}-dup{n}"
        payload = row[-1]  # duplicate payload verbatim; key uniqueness is all that matters for this benchmark
        conn.execute(
            "INSERT INTO cards (key, box, idx, state, sku, condition, capture_id, name, "
            "number, game, set_hint, run, captured_at, state_at, cid, payload) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, *row[1:]),
        )
events = conn.execute("SELECT at, event, position, payload FROM events").fetchall()
for n in range(1, 20):
    for at, event, position, payload in events:
        conn.execute(
            "INSERT INTO events (at, event, position, payload) VALUES (?,?,?,?)",
            (at, event, position, payload),
        )
conn.commit()
conn.close()
EOF

# 3. Measure history() and history_at() on both copies, before and after the code change.
for dir in /tmp/store-scaling-measure/base /tmp/store-scaling-measure/20x; do
  PKMNSCAN_HOME="$dir/.." python3 - <<EOF
import time, statistics
from store import db, files, master
from store.session import Store

conn = db.connect(files.inventory_dir())
def bench(fn, n=5):
    times = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); times.append(time.perf_counter() - t0)
    return statistics.median(times) * 1000

print("$dir")
print("  history():   %.2f ms" % bench(lambda: db.history(conn)))
print("  events_at('3/1'): %.2f ms" % bench(lambda: db.events_at(conn, "3/1")))
conn.close()
EOF
done
```

**Expected, and what confirms the fix rather than merely running it:**
- `history()`'s two numbers should reproduce the plan's own figures approximately (16.5 ms /
  345 ms, ±normal machine variance) — if they do not, this measurement setup differs from the
  plan's and the comparison is not valid; fix the setup before trusting anything else.
- `events_at('3/1')` should be **flat across both copies** — sub-millisecond on both the base
  store and the 20x one, because it is bounded by box size, not store size. This is the actual
  claim under test: not "faster," but "independent of total store size." If the 20x figure is
  materially larger than the base figure (more than noise), box 1 in the real store is
  unusually large, or the `GLOB` scope is not actually hitting the index — re-run the `EXPLAIN
  QUERY PLAN` snippet from "Steps" §1 against this exact database file before concluding
  anything.
- Then measure the end-to-end press: `capture_server.do_mark_sold(box, index, {})` (a plain
  sale, `undo=False`) before and after step 4, on the 20x copy, with `time.perf_counter()`
  around the call. It should be **flat before and after this whole item's fix**, and it
  should be **faster after step 4 alone** than before it (since a plain sale now skips the
  events read entirely) — isolate that difference by benchmarking step 3+4 together against a
  build with only step 3 (scoped read, still called unconditionally) to see step 4's own
  contribution, if the plan wants that broken out. `docs/specs/store-scaling.md`'s own
  practice (§1's table) is to report whatever this session actually measured, so record the
  real numbers from this run rather than the illustrative figures above.

Clean up `/tmp/store-scaling-measure` when done; it is not part of the repo and must never be
committed.

## Risks

- **The box-scope, not position-scope, choice is the one place this fix can be subtly wrong,
  and it is wrong in a way that only shows up on a mid-box delete.** If a future edit
  narrows `events_at`'s `WHERE` clause from `position GLOB ?` (box) back to `position = ?`
  (exact key) — a plausible-looking "tighter is better" simplification — every read this
  item touches keeps working for every ordinary sale, retirement, answer and stand-down, and
  silently breaks the one case D10 ruling 1 exists for: an undo *above* a mid-box delete would
  stop seeing the `renumbered` marker and could restore the wrong physical card's state. Test
  A's `renumbered`-visibility assertion is the guard for this; do not let it be simplified away
  as "redundant with the equality check" — the equality check on a box with no delete in it
  would stay green even with the narrower, wrong scope.
- **`GLOB` pattern injection is not a concern here** (box is validated `str.isdigit()` before
  it reaches the query, and it is always parameterized via `?` — the pattern string itself
  contains no untrusted input beyond a digit string), but if this function is ever
  generalized to accept an arbitrary caller-supplied prefix instead of deriving it from
  `position_key`'s own format, revisit that assumption.
- **A box numbering in the tens of thousands within one box (D10's own no-longer-standing
  25-per-section default not withstanding) could, in principle, make box-scoping less of a
  win than intended** if a single box grows to hold a meaningful fraction of the whole
  store's events. This is not observed on the owner's real store (`docs/specs/store-scaling.md`
  §0: value clusters by box, boxes are hundreds to low thousands of cards) and is not worth
  guarding against speculatively — if it ever becomes real, the fix is a second index or a
  narrower scope, not a reason to hold off on this one.
- **The stale-comment fix (Step 6) is prose, not mechanically checked** — per `CLAUDE.md`'s
  own "a rule that can be mechanically enforced must be" standard, this repo would ordinarily
  want a check here too. None exists today for "does this specific comment's function list
  match which functions call `history_at` vs. `history`," and building one is out of scope
  for this item — flag it as a `docs/DEBTS.md`-shaped gap if the implementing session wants
  to record it, per that file's own stated purpose ("known gaps in the verification tooling,
  deliberately unfixed").
- **This item does not address `_copies_out` or `Inventory.to_payload()`/`do_orders()`** —
  those are separate items in the same plan (`docs/specs/store-scaling.md` §2) and are out of
  scope here by design, not by oversight.
