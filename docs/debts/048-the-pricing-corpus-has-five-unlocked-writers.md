## 48 — the pricing corpus has five unlocked writers, and a lock around one of them is not the fix

**The finding.** Lane B2 (`docs/reviews/ux-2026-09-23/PLAN-PR4-PR5.md`) named one race.
`do_pricing_restore` reads the corpus, then the clears, with no lock across both. A concurrent
restore, or a `PUT /pricing` write, can lose an unrelated price edit. The brief said to fix it
under the store lock. It said to check first whether `PUT /pricing` and the clear path already
take that lock.

They do not. Nothing that writes `inventory/prices.json` takes it. Every writer does a
whole-document read, an in-memory change, and a whole-document write. None of them take a
lock. Each takes an OPTIONAL revision digest check instead
(`_clear_revision_guard`, and the same shape inline in `do_pricing_corpus_write`). That check
only refuses a client whose own copy is stale. D105 names this guard in so many words: *"the
digest travels beside the document"*. It is optimistic concurrency against a slow client. It is
not mutual exclusion against a concurrent writer. Two requests can arrive together, with no
revision or the same current one. Both pass the check. Both write.

The store's real lock is `store/files.py:exclusive`. It is an `flock` on `inventory/LOCK_NAME`
(`store/session.py:Store.write`, `store/db.py`). It guards `inventory/store.sqlite`. Nothing
in the pricing path calls it. Five call sites write `inventory/prices.json`. None is locked:

- `server/pipeline_routes.py:do_pricing_corpus_write` (`PUT /pricing`) — `book.write()`
- `server/pipeline_routes.py:do_pricing_clear` (`POST /pricing/clear`) — `book.write()`
- `server/pipeline_routes.py:do_pricing_restore` (`POST /pricing/restore`, this lane's target)
  — `book.write()`
- `cli/cmd_reprice.py` (`pkmnscan reprice apply --write`) — `book.write()`
- `cli/cmd_join.py` (`pkmnscan join`) — `book.write()`

Locking only `do_pricing_restore` does not close the race the lane named. `flock` only
serializes callers that both take it. An unlocked `PUT /pricing` can still land its write in
the exact gap a locked restore leaves open, between its own read and its own write. That gap
is the interleaving the brief asked a test to force. The same is true the other way. It is
true for the clear route too. It is true for either CLI command racing the server. `flock`
does cross processes, so that last part already works in the store's favor once every writer
takes it.

**What would close it.** Wrap each of the five writers' read-modify-write in
`files.exclusive(files.inventory_dir())`. That is the existing primitive, reused rather than a
second lock. This is five call sites, across three files, not one. Confirm the lock is safe
from the CLI path too. It is a per-process `flock`, so a CLI run and the live server would take
turns rather than race. A harness case can then force the interleaving. The concurrent-drop
race just above this one, in `harness/tests/t7_store_and_seams.py`, already shows the pattern.
It monkeypatches a read to answer with a stale snapshot on the first call. The new case can
prove data loss RED first, then GREEN once every writer holds the lock.

**Why it is not done now.** The lane's own instruction: stop and ask, rather than widen the
lane. That applies if the fix is larger than one lock around one read-modify-write. It also
applies if other writers take no lock at all. Both are true here. The full fix touches five
call sites in three files. That is a different, larger change than the named task. It touches
money and the store's own file, so it earns its own adversarial review.
