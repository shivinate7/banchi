# Stock card images

**Status: BUILT.** Stock photos are the main view on `#/pricing` and on the Sets view of
`#/inventory`. The owner's own photograph stays reachable through Details or the photo sheet.

## What this is

A server-side resolver, `pipeline/stockimages.py:StockImages`, answers one question:
`(game, set_name, number)` gives a hotlinked photo URL, or `None`. It is hotlinked and never
mirrored. The browser loads the photo straight from the tcgcsv or pokemontcg.io CDN, and this repo
never downloads or stores the bytes (D301, stock photos are hotlinked, never mirrored).
One exception stands in D301: the stock-photo matcher reads each image once for its fingerprint and drops the bytes (`docs/specs/identify-engine-pick.md`).

`server/pipeline_routes.py:STOCK_IMAGES` is the one instance for the server's whole life, so its
in-process cache is worth having. `GET /pipeline/sets` (`do_pipeline_sets`) and
`GET /pipeline/pricing` (`do_pipeline_worklist`) each take it as an optional parameter and add one
field, `image_url`, to every row they already draw. No new endpoint exists. The demo's static
recording bakes in whatever `image_url` held at recording time, and the browser calls neither host
itself.

## The two sources

**Riftbound and One Piece** resolve through `tcgcsv.com`. `StockImages` reuses
`pipeline/pricehistory.py:Market` for the categories, groups and products walk and builds its own
`number_index_key -> imageUrl` index per group, because `pricehistory.ProductIndex` does not carry
`imageUrl`. `TCGCSV_TTL_SECONDS` (one hour) is its own constant, and it is shorter than
`pricehistory.CATALOG_TTL_SECONDS` on purpose. The archive sweep can treat the products list as
fixed. This resolver exists to show fresh art on a screen the owner is looking at now.

**Pokemon** resolves through the vendored `vendor/pokemon-tcg-data/` tree (D15) and not through
`api.pokemontcg.io`. The vendored tree carries the identical `images.pokemontcg.io` CDN URLs, it is
committed, and `make catalog-refresh` renews it. It is read with no network call: `sets/en.json` for
the set id, and `cards/en/<id>.json` for each card's `images.small` URL. Both are keyed by
`pipeline/join.py:normalize_set` and `number_index_key`, the fold the catalog join already uses.
`docs/debts/044-pokemontcg-io-is-deprecated-and-this-repo-does-not-call-it.md` records why the live
API is not called: a live check answered HTTP 500 and 502 for a query that had measured full
coverage.

**The store's own `set_name` cell often carries a community code that the vendored tree does not.**
The cell reads "ME01: Mega Evolution" and the vendored set is named "Mega Evolution". On a real-store
copy, none of 542 Pokemon cards resolved until this was handled. `pipeline/join.py:normalize_set` is
not touched, because that fold drives the pricing join (D25) and this resolver is neither.
`_PokemonImages._set_id_for` tries the cell as given, and only on a miss strips a leading `"CODE: "`
(any text up to the first colon) and tries again. A set with a real hyphen in its name still matches
on the first try. After the fix, Pokemon resolved 542 of 542 and Riftbound 1904 of 1913. The 9
Riftbound misses are a raw-number formatting question, a stray space around the slash, left as found.

## Never blocks a request

A cold `/pipeline/sets` took about 2 seconds, because the tcgcsv walk ran on the request thread. Four
cold requests filled every one of `REQUEST_SLOTS`, and a fifth unrelated request then waited 1.8
seconds behind them.

`url_for` now reads `StockImages._cache` only, for Riftbound and One Piece. A cold key, or one past
its own TTL, calls `warm`. That schedules the walk on a background thread and returns at once. It
answers `None` on cold and the last-known URL on stale. That is serve-stale-while-revalidate, so a set
does not flicker back to no photo every hour. `warm` is the one scheduling primitive and it has two
callers. `_tcgcsv_lookup` calls it on every read past a key's TTL. `server/capture_server.py:serve`
calls it once at process start over every `(game, set_name)` pair the store holds
(`pipeline_routes.warm_stock_images`). It is never called at import, so a harness test that only
imports the module opens no socket and starts no thread. Pokemon is never scheduled this way, because
its path reads local disk in well under a millisecond.

## Several SKUs, one image

A Riftbound common's normal and foil printings are one physical product to both catalogs, so both
resolve to the same URL. That is never a reason to merge or dedupe rows. `do_pipeline_sets` already
groups by SKU, and `do_pipeline_worklist`'s merged rows are one per SKU. What keeps two same-image
rows apart on screen is a row's own `printing` field (`SetGroupCard.printing`, off the store's `skus`
table) or its existing `condition` field (`PricingSku.condition`, drawn since D137). Neither is a new
label.

## The client

`app/src/InventorySets.tsx:SetCardImage` and `app/src/Pricing.tsx:PricingThumb` each draw the stock
image as the row's main view: `<img loading="lazy">` with no crop math. The crop machinery (D125) was
built for the raw camera geometry of the owner's photograph and does not apply to a catalog's
pre-cropped art. A join miss (`image_url: null`) or a load failure (`onError`) falls back:

- **Pricing** falls back to the owner's own photograph, cropped and positioned as `PricingThumb` did
  before this feature.
- **Inventory's Sets view** falls back to nothing, because that screen has no per-row `idx` to build
  a photograph URL from. Nothing is the honest state, and no fallback is manufactured.
- **The Orders walk's thumbnail row** (`OrdersWalkPane.tsx:WalkStrip`) draws the stock image from
  `POST /inventory/copies`' `image_url`, falling back to the owner's photograph on a miss or a load
  failure. The count badge and the big `img.browse-photo` (the owner's photograph) are unchanged.
- **Inventory's card panel** (`app/src/CardHero.tsx:PhotoPanel`) draws the stock image only in
  place of a reclaimed photograph (D89). It sits in the same `.bn-photo` box and carries a stock
  photo label. The owner never mistakes it for their own copy. The URL is `image_url` on the
  `/search` group (`server/capture_server.py:do_search`, through `pipeline_routes.stock_image_url`).
  A card with its own photograph never requests it. A join miss or a load failure keeps the
  reclaimed box.

## Never a guess

A join miss answers `None` at every layer. `StockImages.url_for` never raises past its own try block.
A `tcgcsv.com` outage costs a blank tile on `#/pricing` and never a broken screen.

## Tests

`app/tests/pricing.spec.ts` and `app/tests/inventory-sets.spec.ts` each stub the exact `image_url`
their fixture carries as a `page.route` fulfillment. `sealEveryTest`'s `sealOutside` refuses every
request off this checkout's two ports, so a real CDN URL in a fixture is answered by a stub. Each
file asserts that two rows sharing one `image_url` still draw their own label (`condition` in
Pricing, `printing` in Sets), and that a join miss draws no stock image. Removing the `<img>` from
either screen turns its case red.

`harness.tests.t7.sets_stock.check_stock_images` covers the Python side, with both sources
stubbed and no real host reached. It asserts the `"CODE: "` prefix match and a miss answering `None`.
It asserts the cold-cache timing: a fetcher that sleeps 200ms still answers in under 100ms. It asserts
the route threading: `do_pipeline_sets` carries `image_url` only when handed a resolver, and carries
`None` and opens no socket when it is not.

## Not built

- **A standing disk cache for the tcgcsv walk**, unlike `pipeline/pricehistory.py`'s
  `market_cache_dir()`. The design asked for a short-TTL in-process cache, and `Market(cache_dir=None)`
  is that.
- **A live `api.pokemontcg.io` fallback** for a set the vendored tree has not caught up to. See the
  debt entry above.
