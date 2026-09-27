## D-stock-images — A stock photo is the main view on Sets and Pricing, hotlinked, never mirrored

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
