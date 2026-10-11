## D88 — SQLite is the store of record

**`inventory/store.sqlite` is the master store, every `Store.write()` is one transaction over every table, and a session loads only the rows it names.** Built 2026-09-01, from the owner's plan for a 100,000-card run. The pile is 100,000 raw cards. Scanning is the highest-margin activity on the table, measured at $0.00105 per card in API cost against $138–921 of gross value discovered per scan-hour. Two things blocked the run, neither of them strategy. This entry is the first. **This reopens D13**, which said "server-side JSON" without ever arguing for it. D13 carries the amendment, and the rest of that entry stands.

### The argument is correctness first, and speed second on purpose

`store/session.py` made the case against itself for a week. Its header said the five JSON files were each replaced atomically and *"the set of them is not one transaction. A kill between two `write_json` calls leaves the store internally inconsistent... The exposure is real at Ctrl-C frequency rather than theoretical"*. It named the two honest fixes: *"a staged directory swapped by a single `os.replace`, or a real embedded store"*. It called choosing between them *"a decision nobody has argued"*. D138's supervisor drains in-flight requests before a restart for exactly this hole. D63's ledger was written LAST so a torn write lost the order feed rather than the inventory. That is a preference among losses, which that entry says in as many words. **A transaction closes the hole; an ordering only chooses what falls into it.**

The speed argument is real and is deliberately second. **Every capture re-read, re-parsed and re-serialised every card in the store, and synced the whole file to disk.** Measured on a copy of the owner's store grown synthetically, one capture's store cycle under the JSON files:

| cards | read + parse | write | total |
|---|---|---|---|
| 1,560 (the store on 2026-09-01) | 13 ms | 57 ms | 70 ms |
| 10,000 | 67 ms | 309 ms | 374 ms |
| 20,000 | 167 ms | 611 ms | 770 ms |
| 50,000 | 498 ms | 1,616 ms | 2,112 ms |
| 100,000 | 1,203 ms | 3,234 ms | 4,366 ms |

The feeder's measured cadence is 623 ms per card. The client awaits this write inside the capture loop. So past roughly 20,000 cards, capture was store-limited rather than feeder-limited. At 100,000 cards it was running at a seventh of the feeder's pace. Write-behind would have fixed that alone, and more cheaply. It would cost durability on data that names photographs nothing can regenerate. It was not taken, because it does nothing for the first argument.

### Why SQLite, on this repo's own bar

`requirements.txt` refused `requests` for *"one fewer dependency between a clean clone and a green harness"* and refused opencv twice on measurements. Against that bar, `sqlite3` is stdlib. It has no new dependency, O(row) writes, one transaction over everything, and a query language a person can use. JSON-per-card or JSONL-with-compaction add no dependency and close no transaction. `dbm` closes neither. LMDB is a C extension with no index a person can query. DuckDB is tens of megabytes of OLAP. Postgres is a service that must be running for `make harness` to pass. **D15 already made this argument for the catalog**: *"SQLite, not Postgres. ~20k rows, read-only after load, one machine... `sqlite3` is stdlib."* Same machine, same single writer. This applies a choice the project had already made to the place that needed it.

### The shape: one payload column, a few indexed columns beside it, and a mapping that is a dict until it is asked to be a database

**Every record is stored whole as JSON text in a `payload` column, exactly the dict `asdict` produces.** The record classes under `store/` gain and lose fields the way they always have. `Inventory.parse` filters on `__annotations__`, and `store/db.py` never learns a field's name. So a schema migration is not what a new field costs. Beside the payload sit the INDEXED columns each `TableSpec.columns` derives from the object at write time (`box`, `idx`, `state`, `sku`, `capture_id`...). They cannot disagree with the payload, because they are computed from it. They are what a person queries:

    sqlite3 inventory/store.sqlite "select key, name, state from cards where box = 3"

**`Snapshot` is still the API and `inventory.cards` is still a dict to every caller.** `store/rows.py`'s `Rows` is a `MutableMapping`. It is memory-backed for `Inventory()`, `Inventory.parse` and everything T7 drives directly. It is bound to a `Source` inside a session. There, a point lookup is one row. `where(sku=...)` is one indexed query. `select(("box", "idx"), box=3)` returns column values with no object built. **The allocator's high-water scan, the capture-id replay, the SKU walk and the box-number allocator ask the mapping for the rows they want.** They do not walk every card. `Inventory.next_index` keeps its refusal on a record that will not coerce. It does so by asking for the rows whose `box` or `idx` column is NULL. That is exactly the set `int()` refuses, since the columns are derived by the same coercion. Iterating the whole mapping loads the whole table, which is what iterating a whole table should cost. **A flush is a diff**: every loaded object is re-dumped and compared to the shape it had when it was read. So a session that read one card and changed nothing writes nothing.

Measured after, same synthetic store, one capture's `Store.write()` with `allocate_capture`:

| cards | capture cycle | card objects built | whole-store read |
|---|---|---|---|
| 1,560 | 2.4 ms | 1 | 11 ms |
| 10,000 | 2.7 ms | 1 | 77 ms |
| 20,000 | 2.8 ms | 1 | 154 ms |
| 50,000 | 2.9 ms | 1 | 420 ms |
| 100,000 | 3.3 ms | 1 | 978 ms |

At 100,000 cards the capture cycle is **~1,300 times faster** and stops growing with the store. The whole-store read (`GET /inventory`, a join, an emit) is still O(cards), which is what those operations are. **`synchronous=FULL`**. Every commit reaches the disk before the request answers. That is the durability the per-file `fsync` had, and the 3 ms includes it. WAL mode is what lets `Store.read()` stay lock-free. A reader sees the last commit and never a torn one. It holds nothing a writer waits on.

**The flock stays, and the transaction is inside it.** `files.exclusive` guards more than the tables. Callers unlink photographs, rename sidecars and upsert `codes.jsonl` inside `Store.write()` on the strength of that lock. None of that is in a table. A crash between a file write and the commit still leaves a file the store does not describe, exactly as before. `do_delete_box`'s money rule is unchanged. D138's drain is still a prerequisite for the watcher for that reason.

**The history is the `events` table, still append-only, and it commits with the change.** `history.jsonl` was appended after the files. So a crash between the two under-reported history. A row now lands in the same transaction as the state it describes. `Store.history()` still refuses the whole log over one unreadable row. So `_sale_origin`'s degrade-to-unknown path is unchanged, and T7 still holds it there.

### The migration is automatic, lossless, reversible, and never a fallback

**The first open of a legacy store imports it**. It does this under the lock, through `Inventory.parse`. That is where the D10 v1→v2 card-state migration has always lived. So a v1 file crosses both in one read. It then moves the six JSON files to `inventory/legacy-json/`. A `MIGRATED.json` receipt names each file's digest and byte count. The database is built under a temporary name. It is renamed into place before any file moves. So a crash at any point before the rename leaves the JSON exactly where it was. **Reversing it is deleting `store.sqlite*` and moving `legacy-json/*` back up one level**, and the receipt says so. **Measured on a copy of the owner's real store**: 1,560 cards, 443 listings and 1,560 paid answers. There were also 232 queue entries and 7,450 history events. All of it imported in 0.13 s. Every part read back through the database compares equal to `parse()` of the original file. The T7 case that pins this uses a record carrying a field no dataclass declares. The same filter drops it on both paths.

Automatic rather than a command, unlike D86's `prices adopt`. There is no decision inside it. D86's fold had eight SKUs answered two ways and three holds that lost to a price. A person had to see that. This is a re-encoding. The receipt is what a person sees.

**A legacy file beside a live database is never read** — D86's rule for a legacy run file, applied here. `make status` reports one. Nothing else notices it. A hand-restored `inventory.json` does nothing until the database is deleted. D86 accepted the same cost, for the same reason. A fallback that is sometimes read is a duplication waiting to disagree.

### What is enforced

`harness.tests.t7.store_core.check_store_of_record` holds the three claims. The first is that the queue table's write raising after the card table's leaves NEITHER row committed and no history row either. The second is that a capture into a 61-card store builds at most two card objects and never loads the table. The third is that the legacy import reads back equal, moves every file, receipts the counts, and ignores a file put back beside the database. Every case in that file that used to compare a store file's bytes compares the table's rows now. Every case that seeded `history.jsonl` by hand seeds the `events` table instead. The argument for each is unchanged, and it is in the case.

### What it costs, and what is deliberately not done

**State stops being greppable as text.** The owner ruled `sqlite3 .dump` and a `SELECT` sufficient. The owner also ruled that no JSON export target is wanted. `to_payload()` is still the wire shape of `GET /inventory`. So a JSON view of the inventory is one request away, and that is not a target.

**`Store.history()` still returns every event.** The sale and retirement reversals read the whole log to find one position's last state. That was O(history) under the file, and it is O(history) now, at 42 ms on the owner's store. A position-scoped read is one indexed query away when it matters. Not built here, because nothing measured it mattering.

**The whole-store read is still O(cards)**, and `GET /inventory` at 100,000 cards is ~1 s. That route is polled. The honest fix when it bites is a box-scoped read, which the `cards` table's index already supports.

**What would reopen this: a second writer that is not this process.** The flock and the WAL both assume one machine and a local filesystem. That is the assumption the NAS entry under Someday already refuses to break. SQLite over a network filesystem is the classic way to corrupt one.
