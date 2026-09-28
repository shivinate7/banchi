## 48 — ~~the pricing corpus has five unlocked writers~~ — CLOSED 2026-09-27, fixed as recommended

**Closed by the fix this entry recommended.** All five writers of `inventory/prices.json` now
share one lock, `store/files.py:exclusive`, around their whole read-modify-write:

- `server/pipeline_routes.py:do_pricing_corpus_write` (`PUT /pricing`)
- `server/pipeline_routes.py:do_pricing_clear` (`POST /pricing/clear`)
- `server/pipeline_routes.py:do_pricing_restore` (`POST /pricing/restore`, lane B2's target)
- `cli/cmd_reprice.py` (`pkmnscan reprice apply --write`). This runs as a subprocess of
  `POST /pipeline/markdowns/<stamp>/apply`. The server never holds the lock while it waits
  for that subprocess. The two never nest.
- `cli/cmd_join.py` (`pkmnscan join`). It used to write back the SAME `Corpus` object it read
  at the top of the command. That read happened before the whole matching pass ran, with no
  lock held. It now re-reads fresh, inside the lock, right before the write. The earlier read
  stays where it was, read-only, for the threshold that shapes matching.

**One nesting risk, found and avoided.** `cli/cmd_join.py` already opens the identical lock
twice, through `store/session.py:Store.write()`, for the SKU table and the queues. `flock` is
not re-entrant. A second acquisition from the same process, on a fresh handle, blocks until
the first releases. Both existing acquisitions close before the corpus lock opens. Nothing
nests. `cli/cmd_reprice.py` USED TO have the same shape: one `Store().write()` block for the
posting, closed, then the corpus lock. See "the fourth guard's own nesting risk, closed"
below — lane B2's re-review found it, and lane B3 closed it the same round.

**Four revision guards, all moved inside the lock.** `_clear_revision_guard` (used by
`do_pricing_clear` and `do_pricing_restore`), the same shape inline in
`do_pricing_corpus_write`, and `cli/cmd_reprice.py:_apply`'s own `--corpus-revision` check.
All four used to run BEFORE the lock. Picture a caller that read a revision. It then waited
for another writer's lock. Then it wrote. It was checking a revision already stale by the time
its wait ended. The check passed. The wait happened. The write still landed on top of
whatever the lock's holder had just written.

**The fourth guard's own nesting risk, closed.** Lane B2's strict review found the fourth
guard, in `cmd_reprice.py`. The first three were already fixed and closed by then. CSV
building and a `Store().write()` block for the sale posting both sat between its early check
and the corpus lock. Lane B2's own fix gave it a second, fresh check too, right before the
corpus write. But by then `import.csv` and the posting were already on disk. The CSV build and
the `Store().write()` block both ran before that second check. A revision that moved in that
gap made the second check refuse the corpus answer alone. The file and the posting stayed,
already sent to a corpus that had refused them.

Lane B2's own re-review, the same round, named the cause. `cmd_reprice.py`'s
`files.exclusive(files.inventory_dir())`, taken for the corpus half, is `Store().write()`'s
OWN lock, taken a second time. `flock` is not re-entrant across two open file descriptions,
even in one process — the same fact the nesting-risk paragraph above already states for
`cmd_join.py`. The two happened not to deadlock, only because the first `Store().write()`
closed, and released the flock, before the second opened it again.

Lane B3 closed it. One `Store().write()` hold now covers everything. Inside it, in order: the
fresh revision check, the corpus write, the posting, `import.csv` last. A refusal now writes
none of the three. `git log` on `cli/cmd_reprice.py` has both rounds.

**The check.** Three harness cases in `harness/tests/t7_store_and_seams.py`
(`check_undo_until_built_on`), named `T7-RACE (DEBT48)`.

Two patch a real `Corpus.read()`. Each sleeps for exactly as long as its own call now holds
the lock. Both run on real threads, against the real flock, never a stubbed lock. One forces a
restore against a `PUT /pricing` write. One forces the same shape against a real `pkmnscan
join`. Both writer-B calls use a fresh revision. Each retries once on `corpus_moved` — the
real client's own recovery path, never a silent overwrite.

The third needs no thread. It patches `corpus.revision()` itself. On its first call it answers
the value `pkmnscan reprice apply --corpus-revision` was offered. It then lands a real,
concurrent corpus edit. On every call after, it answers the real, moved revision. This proves
the command refuses once the second check runs, where the first alone would have let it
through.

Lane B3 extended this case. After the refusal, no `import.csv` exists. No posting row landed.
The corpus holds exactly the concurrent edit. None of the three is left half-written, which is
what the old nesting once allowed. A separate run, with no race, checks the ordinary case: all
three land.

Proven RED against a `.bak` copy of the pre-fix files, never `git checkout`. All three cases
failed on the code as it stood before each fix. The extended assertions also failed against
lane B2's own fix, before lane B3's. Proven GREEN against the fix. `make harness` passes, all
ten tests.

**The finding, as it was recorded.** Lane B2
(`docs/reviews/ux-2026-09-23/PLAN-PR4-PR5.md`) named one race. `do_pricing_restore` read the
corpus, then the clears, with no lock across both. A concurrent restore, or a `PUT /pricing`
write, could lose an unrelated price edit. Checking first, as the brief asked, found the race
was wider than one route. Nothing that wrote `inventory/prices.json` took a lock. Every writer
did a whole-document read, an in-memory change, and a whole-document write, guarded only by
the optional revision digest above. That digest is optimistic concurrency against a slow
client, never mutual exclusion against a concurrent writer. Locking only `do_pricing_restore`
would not have closed the named race. The other side of every pairing it named stayed
unlocked and could still land its write in the same gap. The lane's own instruction was to
stop and ask, rather than widen the lane, when the fix is larger than one lock around one
read-modify-write. That applied, so the fix waited for the owner's word: `yes build now`.

Cites D86 (the pricing answer is one file for the store), D88 (the store lock, one
transaction per write) and D105 (one file may not have two unguarded writers).
