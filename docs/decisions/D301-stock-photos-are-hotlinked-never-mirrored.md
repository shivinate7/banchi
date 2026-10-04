## D301 — Stock photos are hotlinked, never mirrored

Owner, verbatim: *"if it'd be easy to live pull all the photos without much lag I'd be happy
to have the stock photos show as the main view on say set view or pricing."* And, mid-build,
one addition: several SKUs may share one stock image, and each row keeps its own label.

**The resolver is `pipeline/stockimages.py:StockImages`.** One question, answered per row:
`(game, set_name, number) -> a hotlinked photo URL, or None`. `docs/specs/stock-images.md`
carries the full design. This entry records the two calls the design made.

**Riftbound and One Piece reuse `pipeline/pricehistory.py:Market`.** No second HTTP client.
`ProductIndex` does not carry `imageUrl`, so `StockImages` builds its own small index rather
than growing that class for a field only a photo needs.

**Pokemon reads the vendored `vendor/pokemon-tcg-data/` tree (D15), not `api.pokemontcg.io`.**
This departs from the feature's own research, which measured the live
API at 100% coverage. A live check made while building this (2026-09-26) found that same
query answering HTTP 500/502. The vendored tree already carries the same CDN URLs. It is
committed, refreshed on demand, and read with no network call. DEBT44 records the gap this
leaves (a brand-new set with no vendored row yet), and the live API's own 2027-03-01
shutdown.

**Several SKUs may point at one image, and that never merges rows.** Both routes already
group or key by SKU, so a foil and a normal printing were always two rows. One field still
keeps the two apart on screen, when their image is identical. On Sets it is `SetGroupCard.
printing`, the store's own `skus` table fact. On Pricing it is the existing `PricingSku.
condition`. Neither is a new label invented for this feature.

**The image rides the existing wire, never a new route.** `image_url` is one more field on
`GET /pipeline/sets` and `GET /pipeline/pricing`'s rows — the coordinator's own constraint,
mid-build. The demo's static recording bakes it in like every other field, and the browser
never calls tcgcsv or pokemontcg.io itself.

**A join miss, or a load failure, is never a guess.** Pricing falls back to the owner's own
photograph — reachable this way, and unconditionally through Details and the photo sheet.
Sets falls back to nothing, which is what it drew before this feature existed. That screen
has no per-row index to build an owner photograph URL from.

**A first review round found three real defects, all fixed in the same branch.** Pokemon
measured 0 of 542 real cards on a store copy: the store's own `set_name` carries a code the
vendored tree does not ("ME01: Mega Evolution" against "Mega Evolution"). Fixed inside
`pipeline/stockimages.py` alone, by a second try that strips the code — never inside
`pipeline/join.py:normalize_set`, which the pricing join still depends on. Measured after:
Pokemon 100%, Riftbound 99.5% (unchanged, and already the review's own baseline). A cold
`/pipeline/sets` cost about 2 seconds, and filled every `REQUEST_SLOTS` behind it. Fixed by
moving the tcgcsv walk off the request thread entirely. `url_for` reads a cache only. A miss
or a stale entry schedules a background `warm`, never a fetch inline.
`server/capture_server.py:serve` also calls `warm` once at process start. And there were no
Python tests: `harness.tests.t7.sets_stock.check_stock_images` now covers the prefix
fix, a miss, the non-blocking read, and the route threading, both sources stubbed.

**Amended (F2, 2026-09-27): Sales uses this resolver too.** `do_skus_photos` (D298) falls
back to `url_for`/`url_for_product` for a SKU with no own photograph on hand. Sealed product
gains its own method, `url_for_product`, keyed by product name instead of a card number.
Pokemon sealed product resolves through tcgcsv, because the vendored tree names singles
only and carries no sealed row at all.

Stock images cache in the archive's market-cache directory; no second cache.

`PKMNSCAN_STOCK_IMAGES_SYNC` is set only by `scripts/demo-record.py`. It makes `warm_stock_images()` join its threads before the server accepts requests, so the recorder's first read is warm. The live server stays fire-and-forget.

**Amended, on the owner's word: one exception, a fingerprint read.** The stock-photo matcher
(`docs/specs/identify-engine-pick.md`, D2) needs one fingerprint for each stock image.
The server reads the bytes of each image once and computes that fingerprint. It then drops the bytes.

- The fingerprint is a vector of 768 numbers. The vector is the only thing stored.
- No image byte is written to disk, and no image is served from this repo. Hotlinking is unchanged.
- A change of model rebuilds every fingerprint. An old fingerprint never meets a new model.
- A fingerprint records the model file hash and the source URL.
- The read is the matcher's own step. It runs by itself when the capture server starts and anything is missing, and whenever the store holds a card from a set not yet read. The Prepare press on the runs sheet is a manual refresh. Nothing here spends money, and nothing starts with the model runtime missing.
- A printing with no image is asked again at most once a week, in the background, with no press. A `no_photo` printing is read again. A `no_url` printing has its set's catalog listing read once for a URL, then is read. A printing that gains an image is fingerprinted. The rest wait another week.
