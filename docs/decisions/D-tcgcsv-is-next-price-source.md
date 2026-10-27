## D-tcgcsv-is-next-price-source — TCGCSV is the next outside price source

Kind: process
Home: pipeline/pricehistory.py

**The owner ruled it** (waiting-page item 70). `tcgcsv.com` is the next outside source of current
TCGplayer prices. It is free and needs no key. `pipeline.pricehistory`'s `Market` already reads its
catalog and its current-price listing (`CATALOG_HOST`).

**What it serves.** The current daily prices, for every product in a group. A row is
product-level: it names a printing (`Normal` or `Foil`), never a condition, and it carries no SKU.
It supplements an export and never replaces one.

**What it does not serve.** Its past-days archive is withdrawn. A request for a past day answers
HTTP 403. The site owner's notice says the archive was removed over server costs. There is no
workaround.

**The gap it half fills.** `store.pricearchive`'s `price_history` table (D219, the price archive
never deletes) holds only the SKUs this store has held or sold. Price research over it sees
survivors only. TCGCSV's current prices cover cards this store never held. They hold no history.
Backtest history has no source. It is an open question (waiting-page item 52).

**Other sources.** PriceCharting, PSA and eBay are research only. Nothing is wired.

**What it protects.** The owner reads market prices from a free, keyless source that Banchi
already uses, with no new account, key or cost.

**Reopen when** the owner wants a single-sale source, when item 52 names a backtest source, or when
TCGCSV stops serving current prices.
