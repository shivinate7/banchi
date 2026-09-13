## D-history-scoped-to-box — `Store.history()` gets a box-scoped sibling

**The problem, measured in `docs/specs/store-scaling.md` §1.** `Store.history()` is `SELECT
id, payload FROM events ORDER BY id`, unconditionally, on every call: 16.5 ms at 12,654
events, 345 ms at 20x (253,080 events, 20.9x). It runs inside the store's write lock, on the
hottest reversal paths in the product — a mark-sold press, a retirement, a review answer, a
stand-down reversal — and every one of its callers runs it unconditionally, on a plain sale
or retirement (`undo=False`) as much as on their reversal: both routes' response bodies
carry `"restores_to": None if undo else previous`, telling the caller whether an undo would
be offered before they ask for one. What is wasteful is not the frequency of the read — it
is genuinely needed on every press — it is reading the WHOLE STORE to answer it.

**Every reader wants one box's events, not the whole store.** `store/master.py:position_key`
composes every key in this file as `f"{box}/{index}"`, and the `events` table's `position`
column already carries it, unconditionally indexed (`_INDEXES`, `("events", "position")`) on
every store on disk since the table's own DDL — no schema change, no migration, no version
gate to add.

**The scope is the box, never the bare position.** That is not a wider margin chosen for
safety — it is what correctness requires. A mid-box delete's `renumbered` marker is logged
at the DELETED card's own position, not any mover's (D10 ruling 1) — so a mover's own
reversal has to see a line filed under a *different* position in the same box to learn a
shift happened above it. A position-only scope would answer every ordinary sale, retirement,
answer and stand-down correctly and silently drop the one case D10 ruling 1 exists for.

**`db.events_at(conn, key)`** answers this with `SELECT id, payload FROM events WHERE
position GLOB ? ORDER BY id`, `?` bound to `f"{box}/*"`. GLOB, not LIKE: SQLite's optimiser
turns a literal-prefix GLOB into a range scan on the `events_position` index regardless of
`case_sensitive_like` — confirmed with `EXPLAIN QUERY PLAN` on this schema, which reports
`SEARCH events USING INDEX events_position (position>? AND position<?)`. A key that is not
`box/index` cannot be box-scoped and is never guessed at: it falls back to the full, slow,
correct read rather than returning an empty or wrong-scoped list to a caller whose answer
feeds a refusal message.

**`Store.history_at(key)`** mirrors `history()` and `named_events()`. All three production
call sites that took zero arguments (`_answer_origin`, `_reverse_stand_down`, `_origin`) now
call `store.history_at(key)` instead of `store.history()` — a pure substitution, since all
three already had `key` in scope.

**A second, cheaper win was proposed and is NOT built: it is wrong.** The plan called for
`_sell` and `do_retire` to skip the read entirely when `undo` is `False`, on the premise
that a plain sale or retirement never reads `previous` or `origin_unknown`. It does: both
routes' response bodies carry `"restores_to": None if undo else previous` unconditionally,
so the caller can be told whether an undo would be offered *before* they tap it, on the very
same press. Implementing the skip broke exactly that — `restores_to` came back `None` on
every plain sale and retirement — and `make harness` caught it (`check_mark_sold`,
`check_retire`). The skip was reverted; both routes call `_sale_origin`/`_retirement_origin`
unconditionally, same as before this decision, now against the box-scoped read.

**`db.history(conn)` / `Store.history()` are not deleted.** They stay for the harness's own
~30 test-only call sites (ground truth for comparisons), any future full-log reader, and the
CLI/audit surface, if one is ever added. `events_at` is a sibling, not a replacement — the
same relationship `events_named` (D134) already has to `history()`, on a different scoping
axis (event name there, box here).

**Covered by:** `harness/tests/t7_store_and_seams.py:check_history_scoped_read` (functional
equivalence against the box-filtered slice of a full read, including the `renumbered`
cross-box-isolation case) and `check_history_scoped_uses_index` (asserts the `EXPLAIN QUERY
PLAN` names `events_position` and never falls back to a table scan). `check_mark_sold` and
`check_retire`'s existing corrupt-log cases (`corrupt_history`) were widened to accept a
`position` argument, so a corrupted row lands inside the box the reversal under test reads
from — a `None`-position row (the fixture's prior, worst-case default) is invisible to a
box-scoped `GLOB` and would have let those two reversals silently succeed through a corrupt
log instead of refusing.

**Risk carried forward, not resolved here:** a future edit that narrows `events_at`'s `WHERE`
clause from `position GLOB ?` (box) to `position = ?` (exact key) would keep every ordinary
reversal working and silently break the one case this decision exists for — an undo above a
mid-box delete losing sight of the `renumbered` marker. `check_history_scoped_read`'s
`renumbered`-visibility assertion is the guard; it must not be simplified away as redundant
with the equality check, which would stay green even under the narrower, wrong scope.

**A second risk, real and accepted rather than carried forward as a gap:** a corrupt row
whose own `position` column is unreadable or absent (`NULL`, from a hand-edit or a write
this server never made — `_history` always sets a real `position`) is now invisible to
every box-scoped read, since `position GLOB '<box>/*'` cannot match `NULL`. Before this
change, ANY corrupt row anywhere blocked EVERY reversal in the store, box-scoped or not —
a wide blast radius that was also, incidentally, the only thing that made a position-less
corrupt row detectable at all. After this change, a corrupt row inside a box still blocks
that box's own reversals exactly as before; a corrupt row with no recoverable position
blocks nothing, box-scoped. This is a real narrowing of what a hand-corrupted store gets
caught doing, traded for what the whole point of this decision is — not paying the whole
store's read cost for every press. Accepted rather than fixed here because closing it would
mean either keeping an unscoped fallback scan for exactly the rows that can't say what box
they're in (defeating the box-scope for the corruption case that most needs it) or refusing
every reversal whenever ANY row in the whole table is corrupt regardless of position (which
is the full-table-read cost this decision removes, reintroduced as a full-table integrity
check on every press).
