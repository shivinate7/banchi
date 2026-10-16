## D189 — The market reading is a table

**A live recomputation became a cache. The arbitration did not change.** `server/pipeline_routes.py:_readings()` used to walk every run's `runs/<n>/pricing.json` and the newest file under `inventory/.live` on every `GET /pipeline/value`. It compared the two sources on a clock and returned `sku -> the newest market price this machine has read for it`. `pipeline/readings.py:collect()` runs the same newest-wins comparison over the same two sources, so which reading wins did not move. What moved is when: from every request, to one explicit press, `banchi readings adopt --write`. That folds the result into a new `readings` table in `inventory/store.sqlite` (D88). `_readings()` is now a plain `SELECT` against it.

It fixes no bug, corrects no wrong price and changes no arbitration rule. It is a simplification made ahead of any complaint: nobody has reported `#/pricing`'s value screen as slow on a store with a handful of runs. The gain is that a request reads two small tables instead of re-parsing every `pricing.json` and one live-export CSV.

### Two tables, because one answer has two shapes

`readings` is `sku -> Reading` (`market`, `at`, `source`, `kind`, `name`, `set_name`, `condition`), one row per SKU. It is the exact mapping `_readings()` always returned. `readings_sources` is the accounting beside it: which files answered, and how many SKUs each one offered **before** arbitration.

The second table is needed. A run that priced 100 SKUs and lost 20 to a newer live export leaves only 80 rows in `readings` carrying its name. The old function's `sources` list reported all 100, since it counted every row a file offered on its way past. A caller asking "is this a thin STORE or a thin FETCH" needs the pre-arbitration number. Once two sources have collided on a SKU, it cannot be recovered from `readings` alone. `readings_sources` is filled by the same `readings adopt` press and keyed by `kind:name`, not `name` alone. A run directory and a live export filename do not collide in practice, but this table's contract should not depend on that staying true.

### Why `readings adopt` is a manual press

`banchi prices adopt` (D86) is a deliberate press, because folding a run's `decisions.json` into the shared pricing corpus is a real decision. Newest-wins can silently replace an operator's deliberate price hold. Three of the eight SKUs on the owner's own store were exactly that collision.

`readings adopt` previews by default too, but the reason is weaker. Nothing in this walk is an operator judgement. `readings` holds no hold, no override and no hand-typed answer. It is what the market said, arbitrated only by which file is newer. The same files give the same answer each time. A wrong answer is at worst a stale market price. The live recomputation had the same staleness between runs: the value screen was fresh to the last completed join or live fetch, never faster than the operator's own last action.

The table does not self-maintain. A join or a live fetch does not trigger `readings adopt`. Writing into `readings` from inside `do_pipeline_pricing`'s join and `do_live_export`'s fetch was considered and set aside for scope: it adds two write paths into the store's transaction from code that writes only files today. A manual press also suits a feature that nothing downstream has needed fresher than the last join or fetch. **If a stale reading costs something real, make `join` and `do_live_export` call `readings adopt`'s writer at the end of their own transactions.** That is a small, well-scoped follow-up, named here so the next session does not re-derive it. It is now done (see Amended below).

### The table is a cache, and a press replaces it wholesale

`Readings.replace()` clears every row in both tables and writes exactly the fresh set `collect()` computed. **A SKU whose only source has since been retired must disappear from the table, as it would drop out of the old live walk on its next request.** That covers a run directory deleted, or a live export superseded and removed by hand. An incremental merge that only added rows would let `readings` accumulate stale answers the live version never could. That is the one way this change could make the store worse. `store/rows.py:Rows`'s diff is baseline-based, so a full clear-then-reinsert writes only the SKUs that changed. A SKU whose reading is unchanged between two adopts costs nothing in the transaction.

### A bad input is skipped or refused, never replaced

- **A malformed run `pricing.json` makes `readings adopt --write` refuse and keep the table.**
- **A newest live export that is not a price export is skipped.** It has no SKU or Market Price column, or it cannot be read. A skipped file gives no readings, and no older export stands in for it. This stops an older export posing as the newest market reading.
- **`readings adopt` names the skipped file and the SKUs lost.** The operator can tell a bad file from a store with few valuable cards.
- **A valid export with no priced rows is not skipped.** It has the columns, and the market priced nothing. That is a reading.

### What was proved, and how

`scripts/readings-selftest.py` runs `pipeline/readings.py:collect()` against an independent reimplementation of the same walk (`golden()`, sharing no line of code with `collect()`) over a throwaway store. Cases: an empty store; only run tables; only a live export; a run and a live export disagreeing on one SKU, in both directions of which is newer; the newest-by-name live export with an unparseable filename, which must lose to everything and must not fall back to an older readable file; `readings adopt --write` followed by the exact `SELECT` `_readings()` now performs, asserted equal to what was adopted; re-running `adopt --write` twice unchanged (idempotent, no duplicate rows); a new run landing between two adopts, picked up on the next press; and a run directory deleted between two adopts, whose SKU disappears. Thirty-one assertions, all passing. `make harness` is unaffected: no harness test exercised `_readings()` directly, and the fixtures carry no `readings` expectations.

### What this does not touch

The two-source arbitration rule is newest wins by clock, never by fixed precedence. It is D86's reasoning applied to the market reading, and it is unchanged. `pipeline/pricing.py`, `pipeline/corpus.py` and `inventory/prices.json` are untouched. This entry is about where a market observation is cached, never about what an operator decided to ask for a card.

### Amended — the writer runs inside the ordinary write paths

The follow-up above is in place. `cli/cmd_join.py` calls `store.readings.Readings.replace_source()` immediately after writing `pricing.json`, in a `Store().write()` opened for that purpose alone. It is not folded into the queues/`live` transaction, because `pricing.json` is a sidecar file D88 keeps outside any sqlite transaction, and the readings refresh reads that file's own post-write mtime. `do_live_export` does the same right after validating the fetch, reusing the already-parsed export rather than re-reading the file.

Both writers are incremental. They do not call `pipeline/readings.py:collect()`, because a full recollect would re-parse every run's `pricing.json` and the newest live export (potentially large at 50,000 listings) on every join. That is the per-request cost this table exists to avoid. `store/readings.py:Readings.replace_source()` folds in one source's fresh reading. For an ordinary run it supersedes only that source's own prior rows, since two run directories coexist. For a live fetch it supersedes every existing `live`-kind row, because `_newest_live_reading` credits only the single newest file, so a fresher fetch invalidates every SKU an older one still carried.

`banchi readings adopt --write` is unchanged. It remains the hand repair for what these two writers cannot see: a run directory removed outside any command this repo runs (there is no run-delete capability), or a clock skew. The preview-by-default CLI shape does not change.
