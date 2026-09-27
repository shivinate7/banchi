## 44 — pokemontcg.io is deprecated (ends 2027-03-01), and `pipeline/stockimages.py` does not call it today

**The finding.** `docs/specs/stock-images.md`'s own research recorded `api.pokemontcg.io
/v2/cards?q=set.id:<id>` as the Pokemon stock-image source. It measured 100% coverage for
ME01. A live check made while building `D-stock-images` (2026-09-26) found that endpoint
answering HTTP 500 and 502 on every query tried. That included the exact query the research
recorded working the same day. The API's own deprecation notice sets its shutdown at
2027-03-01.

**Why this is not fixed by calling the API anyway.** `pipeline/stockimages.py` resolves
Pokemon images from the vendored `vendor/pokemon-tcg-data/` tree instead (D15). It reads
`sets/en.json` for the set id, then `cards/en/<id>.json` for each card's `images.small` URL.
That tree already carries the same `images.pokemontcg.io` CDN URLs. It is committed, and
`make catalog-refresh` renews it on demand. No network call, and nothing to stub in a test.
This was the smaller, more reliable primitive on the day it was measured. This feature does
not depend on the live endpoint at all.

**The gap this leaves.** The vendored tree is refreshed by hand, not automatically. A set
released after the last `make catalog-refresh` has no vendored row. It therefore has no stock
image here — a join miss, same as any other, never a guess. It is still a real gap a fresher
catalogue would close. The live API, when it answers, would close that gap for a brand-new
set faster than a re-vendor. It cannot be the primary path while it answers 500/502 on
ordinary queries. Its own shutdown date means that it cannot be a long-term secondary path
either.

**The fix, not built.** Two independent things, either enough on its own:
1. A periodic re-clone of `vendor/pokemon-tcg-data`, on the same on-demand model as
   `catalog-refresh` itself, so a new set's images land within one refresh of its release.
2. A live-API fallback in `pipeline/stockimages.py:_PokemonImages`, tried only when the
   vendored lookup misses. It would keep the same graceful posture `StockImages.url_for`
   already gives the Riftbound/One Piece path: never raise. This is worth building only once
   the API is confirmed to answer reliably again. Building it against an endpoint that
   currently 500s on `set.id:me1` would add a socket. `CLAUDE.md`'s own hard rule keeps that
   out of every harness path: "no test or check may make a real network call."

Cites `docs/specs/stock-images.md` and `pipeline/stockimages.py`.
