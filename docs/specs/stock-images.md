# Stock card images

Owner, verbatim: *"if it'd be easy to live pull all the photos without much lag I'd be happy
to have the stock photos show as the main view on say set view or pricing."* And: *"demo full
mirror and stock images as the main view on sets and pricing go directly into pr 3 building."*

## What this is

A server-side resolver, `pipeline/stockimages.py:StockImages`, answers one question:
`(game, set_name, number) -> a hotlinked photo URL, or None`. It is hotlinked, never mirrored
(the owner's own call, and D24's own word for the code-cards feature, reused here). The
browser loads the photo straight from tcgcsv's or pokemontcg.io's CDN. This repo never
downloads or stores the bytes.

`server/pipeline_routes.py:STOCK_IMAGES` is the one instance for the server process's whole
life, so its in-process cache is worth having. `GET /pipeline/sets` (`do_pipeline_sets`) and
`GET /pipeline/pricing` (`do_pipeline_worklist`) each take it as an optional parameter. Each
adds one field, `image_url`, to every row it already draws. Neither route gained a new
endpoint. The image rides the existing wire, on the coordinator's own constraint mid-build.
The demo's static recording bakes in whatever `image_url` held at recording time. The browser
calls neither host itself, ever.

## The two sources

**Riftbound and One Piece** resolve through `tcgcsv.com`. This reuses
`pipeline/pricehistory.py:Market` for the categories/groups/products walk that module already
built and caches, rather than a second HTTP client. `StockImages` builds its own
`number_index_key -> imageUrl` index per group. `pricehistory.ProductIndex` does not carry
`imageUrl`, and growing it for a photo nobody else needs is not this class's job.
`TCGCSV_TTL_SECONDS` (one hour) is its own constant. It is deliberately shorter than
`pricehistory.CATALOG_TTL_SECONDS` (infinite). That module's products list is right to treat
as fixed, for the archive sweep. This resolver's whole reason to exist is fresh art on a
screen the owner is looking at now.

**Pokemon** resolves through the vendored `vendor/pokemon-tcg-data/` tree (D15), not
`api.pokemontcg.io`. This is a deliberate departure from this feature's own research notes.
The reasons are recorded in full in
`docs/debts/044-pokemontcg-io-is-deprecated-and-this-repo-does-not-call-it.md`. In short: the
research measured the live API at 100% image coverage for one set. A live check made while
building this (2026-09-26) found that same query answering HTTP 500/502. The vendored tree
carries the identical `images.pokemontcg.io` CDN URLs. It is committed, and
`make catalog-refresh` renews it on demand. It is read with no network call at all —
`sets/en.json` for the set id, `cards/en/<id>.json` for each card's `images.small` URL. Both
are keyed by `pipeline/join.py:normalize_set`/`number_index_key`, the same fold the catalog
join already uses, rather than a second normalizer.

**The store's own `set_name` cell often carries a community code the vendored tree does
not.** A review round measured this on a real-store copy: 0 of 542 Pokemon cards resolved.
The store's cell reads "ME01: Mega Evolution". The vendored set is named plain "Mega
Evolution". `pipeline/join.py:normalize_set` is NOT touched for this — that fold drives the
pricing join (D25) and D22's own taxonomies, and this resolver is neither.
`_PokemonImages._set_id_for` tries the cell as given first, and only on a miss strips a
leading `"CODE: "` (any text up to the first colon) and tries again. A set with a real hyphen
in its name, never a code colon, still matches on the first try. Measured after the fix, on
the same real-store copy: Pokemon 542 of 542 (100%). Riftbound, untouched by this fix,
measured 1904 of 1913 (99.5%) — the 9 misses are a raw-number formatting question (a stray
space around the slash), left as found.

## Never blocks a request

A review round measured a cold `/pipeline/sets` at about 2 seconds. Four cold requests filled
every one of `REQUEST_SLOTS`. A fifth, unrelated request then waited 1.8 seconds behind them.
The cause was the tcgcsv walk — categories, groups, products. It ran on the request thread.

**It no longer does.** `url_for`, for Riftbound and One Piece, reads `StockImages._cache`
only. A cold key, or one past its own `TCGCSV_TTL_SECONDS`, calls `warm`. That schedules the
walk on a background thread and returns at once. It answers `None` on cold, and the
last-known URL on stale — serve-stale-while-revalidate, so a set does not flicker back to no
photo every hour. `warm` is the one scheduling primitive, called two ways. `_tcgcsv_lookup`
calls it inertly, on every read past a key's own TTL. `server/capture_server.py:serve` calls
it once, explicitly, at process start, over every `(game, set_name)` pair the store holds
(`pipeline_routes.warm_stock_images`). Never at import: a harness test that only imports the
module opens no socket and starts no thread. Pokemon is never scheduled this way. Its own
path reads local disk in well under a millisecond, and was never the slow one this exists
for.

## Several SKUs, one image

The owner's own addition, mid-build: a Riftbound common's normal and foil printings are one
physical product to both catalogs. Both resolve to the same URL. This is never treated as a
reason to merge or dedupe rows. `do_pipeline_sets` already groups by SKU — a foil and a normal
print carry different SKUs, so they were already two rows before this feature existed.
`do_pipeline_worklist`'s merged rows are one per SKU the same way. What changes is which field
keeps two same-image rows apart on screen: a row's own `printing` field (`SetGroupCard.
printing`, off the store's `skus` table, identity-follows-sku.md §3.2), or its existing
`condition` field (`PricingSku.condition`, always drawn since D137). Neither is a new,
invented label.

## The client

`app/src/InventorySets.tsx:SetCardImage` and `app/src/Pricing.tsx:PricingThumb` each draw the
stock image as the row's MAIN view: `<img loading="lazy">`, no crop math. That machinery is
D125's own. It was built for the owner's photograph's raw camera geometry, and it does not
apply to a catalog's own pre-cropped art. A join miss (`image_url: null`) or a load failure
(`onError`) falls back:

- **Pricing** falls back to the owner's own photograph. That is exactly the crop-and-position
  `PricingThumb` already drew before this feature existed. The owner's own photo stays
  reachable this way, and again through Details or the photo sheet, unconditionally.
- **Inventory's Sets view** falls back to nothing. That is what it drew before this feature
  existed. This screen has no per-row `idx` to build an owner photograph URL from. "Nothing"
  is the honest state here, rather than a manufactured fallback.

## Never a guess

A join miss answers `None`, at every layer. `StockImages.url_for` never raises past its own
try block. A `tcgcsv.com` outage costs a blank tile on `#/pricing`, never a broken screen.

## Tests

`app/tests/pricing.spec.ts` and `app/tests/inventory-sets.spec.ts` each stub the exact
`image_url` the fixture carries, as a `page.route` fulfillment. `sealEveryTest`'s own
`sealOutside` refuses every request off this checkout's two ports. A real CDN URL in a
fixture is therefore answered by a stub, the same way `/photo/` already is. Each file's new
case asserts two rows sharing one `image_url` still draw their own label — `condition` in
Pricing, `printing` in Sets. Each also asserts that a join miss draws no stock image at all.
Removing the `<img>` from either screen turns its case red.

`harness/tests/t7_store_and_seams.py:check_stock_images` covers the Python side. Both
sources are stubbed — a throwaway `vendor/pokemon-tcg-data/`-shaped tree for Pokemon, a fake
`fetcher` for the tcgcsv walk. Neither ever reaches a real host. It asserts the "CODE: "
prefix match, and a miss answering `None`. It asserts the cold-cache timing: a fetcher that
sleeps 200ms still answers in under 100ms. It asserts the route threading too —
`do_pipeline_sets` carries `image_url` only when handed a resolver, and carries `None` and
opens no socket when it is not.

## What was not built

No standing disk cache for the tcgcsv walk, unlike `pipeline/pricehistory.py`'s own
`market_cache_dir()`. The brief asked for a short-TTL in-process cache. `Market(cache_dir=
None)` is exactly that. No live `api.pokemontcg.io` fallback for a set the vendored tree has
not caught up to yet. See the debt entry above.
