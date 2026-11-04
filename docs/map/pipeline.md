# Pipeline

CSV, variant ladder, pricing, join, routing, run decisions, per-game taxonomy.

## Code files

- `pipeline/__init__.py` — Makes `pipeline` a package.
- `pipeline/cardladder.py` — The Card Ladder client for My Slabs: the owner's refresh token exchanged for a one-hour ID token, then one function per read point of spec `3.1` to `3.6`.
- `pipeline/catalog.py` — Build-order step `9`, piece `2`'s READER: opens vendor/pokemon-tcg-data/catalog.sqlite (built by scripts/catalog-index.py) and answers cards_by_join_key, cards_by_name, card_by_id and set_by_id.
- `pipeline/corpus.py` — Inventory/prices.json — ONE listing answer per SKU for the whole store, plus the standing policy (rule, basis, sub_threshold) and an optional per-run policy override.
- `pipeline/dailyprices.py` — `run_pass` asks `last-updated.txt` first and skips when that update is already saved whole.
- `pipeline/decisions.py` — The pricing decision, parsed — the corpus's parser (D86): pipeline/corpus.py projects inventory/prices.json into one `Decisions` per run, this module owns what an answer MEANS, and it reads and writes no file.
- `pipeline/games.py` — The per-game taxonomy: Product Line cell, ordered Rarity cells in STACK order, finish enum, finish -> Condition map, and the rarity -> finish matrix, plus join-key/prompt/crop-band/located facts per game.
- `pipeline/holdings.py` — `on_hand_quantities`/`on_hand_names` walk the `cards` table once for every SKU not in `TERMINAL_STATES`.
- `pipeline/identity_binding.py` — §`7.2`'s ladder — T3 (a human act chose this SKU), T5 (the read disputes the row, or is blank, no human act), T4s (number disagrees, name names more than one product), T4u (the same, but exactly one — D162), T1 (name equal after the fold), T2 (a near miss, not disputed), T6 (no SKU), `sku_unknown`.
- `pipeline/identity_checks.py` — Four review-signal checks over already-stored card fields, no catalog, no network: a name too long to be a name, a denominator or digit count that disagrees with its set's own dominant reading, and a name one edit from a different name this store holds in the same set.
- `pipeline/join.py` — Catalog join by SKU, aggregation, bidirectional unmatched reporting.
- `pipeline/livecheck.py` — The whole store against one live TCGplayer export (My Pricing), both directions.
- `pipeline/merge.py` — One import file over several runs: the copies union, deduped on (box, index), and any cap the send asked for spent ONCE over that union.
- `pipeline/movers.py` — Which listed SKUs moved more than ten percent in the market since they were listed.
- `pipeline/namefold.py` — The one name fold: apostrophe and dash look-alikes to ASCII, then accents off.
- `pipeline/net.py` — The one retry home: `net.open` and `net.request` carry every network call.
- `pipeline/orders.py` — The order resolver: (sku, quantity) -> the copies that fill it, for EVERY open order in one pass over a shared per-SKU pool.
- `pipeline/pirateship.py` — The Pirate Ship import spreadsheet — the one supported entry point, because Pirate Ship has NO API.
- `pipeline/pricearchive.py` — `rows_from_store` reads the `cards` table for every distinct, non-empty SKU (and, with `include_catalog`, appends up to `CATALOG_SKUS_PER_PASS` Riftbound `skus` rows after the revenue-ranked head, stalest first by the newest bucket or `load_attempts`/`save_attempts` stamp), builds one export-shaped row per SKU.
- `pipeline/pricehistory.py` — What a SKU has been selling for: the public infinite-api price-history endpoint, reached through a LOCAL sku -> productId join against tcgcsv.com's mirror of TCGplayer's own catalog.
- `pipeline/pricerefresh.py` — The daily market read's notes and saved Trends strips.
- `pipeline/pricing.py` — Rules, rounding, floor clamp, threshold, no_market_data refusal.
- `pipeline/productview.py` — `row_for_sku` looks up one SKU's export-shaped row without walking the whole `cards` table.
- `pipeline/readings.py` — `collect()` — every run's pricing.json and the newest live export, compared on a clock, newest wins.
- `pipeline/realized.py` — `read_sales` reads an OrderWand sales export with `csv`, keeping nine columns and dropping every buyer field at parse time.
- `pipeline/reprice.py` — Which live listings are not selling, and what each would be re-priced to (D100).
- `pipeline/rosterholdings.py` — `read_roster` keeps a roster CSV's TCG purchases that are not canceled and drops every counterparty column at read, counting the rest by reason.
- `pipeline/routing.py` — Which queue a card lands in — batch script v2 section `5.4`.
- `pipeline/selection.py` — WHICH CARDS A PRESS IS OVER — one object, read by thewire and the CLI alike, and the drawer is a TERM in it rather than the unit of work.
- `pipeline/sendguard.py` — THE DOUBLE-SEND GUARD. After a send, live at TCGplayer plus Add to Quantity may never pass the copies on hand, per SKU.
- `pipeline/setnames.py` — Does this hint name this set — the one ladder the export fetch and the join both read.
- `pipeline/shipping.py` — The TCGplayer Export Shipping reader, and the router that puts one order in one of THREE lanes: a tcgtracking envelope (<$`50`, all cards), a Pirate Ship parcel (contains a non-card, OR >=$`50` because TCGplayer mandates tracking above $`49.99`), or UNJUDGED.
- `pipeline/sku_name_contradictions.py` — One SKU, two stored names.
- `pipeline/sku_number_contradictions.py` — Two copies of one SKU disagreeing about the card's stored number.
- `pipeline/skus.py` — `stamp_of` reads the UNIX second out of a fetched or live export's own filename (never its mtime — D166's own rule applied here).
- `pipeline/stockimages.py` — `(game, set_name, number) -> a hotlinked stock photo URL, or None` (D301).
- `pipeline/stockmix.py` — `GET /stock/mix`, the Mix lens of Sales: one row per card still in stock (retired and moved cards are skipped), in ONE statement over `cards` joined to `skus`, `readings` and `boxes`.
- `pipeline/suggest.py` — Pricing by suggestion, pure over plain dicts (spec docs/specs/pricing-suggest.md): `fired` names which of three triggers (market moved, unsold above market, undercut with shipping) fire on a live listing, and `review` sorts every listing into Needs you, Suggested changes or Going at the rule.
- `pipeline/tcgcsv.py` — TCGplayer Filtered CSV read/write and byte-format inspection.
- `pipeline/variant.py` — The variant ladder: four rungs that infer, under a rung `0` that does not, over a per-game finish vocabulary and a set-valued rung `1` claim.
- `pipeline/walkplan.py` — The order walk as a PLAN: the fewest SECTIONS a hand must open to fill a ticked set of orders.
- `pipeline/worklist.py` — ONE SKU as `#/pricing` draws it — the twenty-field row `pricing.json` carries, declared in one place.
