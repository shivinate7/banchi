# Store

The master store: inventory, cache, standing queues, order ledger and the history, in one SQLite file since D88.

## Code files

- `store/__init__.py` — Makes `store` a package.
- `store/cache.py` — The `identifications` table — answers already paid for.
- `store/clock.py` — The one UTC-second stamp every receipt writes, and the one way to read it back.
- `store/dailyprices.py` — `daily_prices` (one row per product, printing and source update day, never deleted) and `daily_price_updates` (one row per source stamp: the groups saved and whether every group was, which is what lets a pass skip).
- `store/db.py` — The SQLite file: the schema (one payload column per row with a few indexed columns derived beside it), `SqliteSource` behind every `Rows`, the per-session flush, the events table that is the history, and the one-time lossless import of a legacy JSON store into it — under the lock, files moved to legacy-json/ with a receipt.
- `store/files.py` — Where the store lives, the lock, and the atomic replace the files still beside the database use (prices.json, codes.jsonl).
- `store/master.py` — The cards, boxes and listings tables — cards, positions, SKUs, listing states, `open_section`, which puts one divider in front of the next card at the index only the store can read (D10), and D89's `record_photo_reclaimed`.
- `store/numbers.py` — A card's number, composed (`join_key`), screen-drawn (`display_number`) and stripped of a glued set code (`strip_set_code`) — a LEAF module with no imports beyond the stdlib (D63): `store/` may not import `pipeline/`, so these three pure functions moved out of `pipeline/join.py` to where both `store/master.py` and `pipeline/join.py` (which imports them back and re-exports under the same names) can reach them.
- `store/orders.py` — The `orders` and `fulfilment` tables — one record per {source}:{order_number}, upserted.
- `store/photos.py` — Where a card's photograph lives, and the ONLY module permitted to compose that path: `<home>/photos/<aa>/<cid>.jpg`, a pure function of the card's own name.
- `store/postings.py` — `Postings`, an accumulator like `Inventory.events` and not a `Rows` table: `.record()` appends a posted `TCG Marketplace Price` to an in-memory list, flushed by `Store.write()` with `db.append_postings` into `price_postings` — one `INSERT` per row, never an `UPDATE` or a `DELETE`.
- `store/pricearchive.py` — `price_history` (one row per (sku, range, start), never `width_days` — `semiannual` and `annual` are both seven-day buckets, so a width-only key would collide two different observations, exactly the D278 collision this table exists to prevent) and `price_history_sources` beside it (one row per range last swept — requested, answered, refused).
- `store/queues.py` — The standing queues — the `queues` table, one mapping per queue name — and the cross-queue release a re-routed position needs.
- `store/readings.py` — The `readings` table (sku -> the newest market reading, one row per SKU) and `readings_sources` beside it (one row per file `collect` read, and how many SKUs it offered BEFORE arbitration — not recoverable from `readings` alone once two sources have collided on a SKU).
- `store/rows.py` — `Rows`: a keyed mapping of records that is a dict to every caller and, bound to a `Source`, loads one row, one indexed column's matches, or column values with no object built at all.
- `store/sendclaims.py` — The `send_claims` table — D174's claim shape over a send to TCGplayer.
- `store/session.py` — Lock-free read, or locked read-modify-write, over one SQLite transaction — `Snapshot` is the API and every field of it loads only the rows a caller names.
- `store/skus.py` — `skus` — one row per TCGplayer Id this repo has ever read out of a cached export: the six fact cells verbatim (`product_line`, `set_name`, `product_name`, `number`, `rarity`, `condition`), `grade`/`printing` split off `condition` at write time by `split_condition` (five recognized grades.
- `store/slabs.py` — The My Slabs tables and their writes: `slabs` (one row per cert and grader, the grader in Card Ladder's name), `slab_snapshots` (one row per slab per day, a second write that day replaces it) and `slab_sales` (keyed by Card Ladder's sale id, never deleted, shared by every slab that read it).
- `store/submissions.py` — The `submissions` table — one row per press, holding the position keys that press is about to pay to read.
