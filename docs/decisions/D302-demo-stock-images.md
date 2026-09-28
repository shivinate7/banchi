## D302 — STOCK_IMAGES gets a disk cache, and the demo mirror copies it

The owner, 2026-09-27, asked why the demo does not get the pricing thumbnails the live
server shows. Then: "Do it now."

**The premise did not hold.** `server/pipeline_routes.py:STOCK_IMAGES` (D301) was built
`Market(cache_dir=None)`. That is in-memory only. The owner's live server never
persisted a Riftbound or One Piece image to disk either. It only looks warm because the
process stays up for days, under `make launch-agent`. `scripts/demo-mirror.py`'s recorder
runs `--offline` (D295, D216). With no disk cache at all, it could only ever answer `None`.

**The fix reuses a primitive that already exists.** It does not build a second cache.
`cli/cmd_pricearchive.py`'s archive sweep (D219) already fetches and caches the same
tcgcsv products URL. The path is
`inventory/.market-cache/tcgcsv/<category>/<group>/products.json`.
`pipeline/stockimages.py:_fetch_tcgcsv` now caches under that same slug. It no longer uses
a private `stockimages/...` one. `STOCK_IMAGES` now builds its `Market` with
`cache_dir=files.inventory_dir() / ".market-cache"`. That is the same directory
`cli/cmd_pricearchive.py:market_cache_dir()` already derives. A fetch either side has
already made now answers the other. There is no second cache to keep warm, and no network
call.

**The mirror copies it, and nothing here fetches.** `scripts/demo-mirror.py`'s
`snapshot()` adds `.market-cache` to `SIDE_DIRS`, beside `.exports` and `.live`. `build()`
already copies the whole `SNAPSHOT/inventory` tree into the recorder's home. The cache
rides along with no extra wiring. The offline recorder's `StockImages` instance answers
Riftbound and One Piece images straight from disk. The owner's own `archive sweep` already
made that call, on the owner's own machine, at some earlier time.

**Proved by `scripts/stockimages-cache-selftest.py`**, offline both ways. A `Market` whose
fetcher always raises, never a live socket, answers `None` with an empty cache directory.
The same setup answers the product's `imageUrl` with a seeded one.

**A real rebuild still answered 0 of 796 rows, and the cause was a genuine race.**
`warm_stock_images()` starts `STOCK_IMAGES.warm()`'s threads and returns at once. That is
correct for a live server. A real user's first request must never wait on a disk read.

The recorder reads each route once and bakes the answer into the bundle forever. A cold
`url_for()` on that one read stays cold forever, with no later read to fix it.

Measured: the same demo home answered 795 of 796 five times in a row. Moments later, with
no code change, it answered 0 of 796 twice in a row. CPU contention at boot decided it.

**`PKMNSCAN_STOCK_IMAGES_SYNC`** is the fix. `scripts/demo-record.py` sets it, and nothing
else does. It makes `warm_stock_images()` join its own threads before the server starts
accepting requests, so the recorder's first read is already warm. The live server's own
behavior stays fire-and-forget, exactly as before.
