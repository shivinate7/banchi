## 44 — pokemontcg.io is deprecated (ends 2027-03-01), and `pipeline/stockimages.py` does not call it today

`pipeline/stockimages.py` resolves Pokemon stock images from the vendored `vendor/pokemon-tcg-data/` tree (D15): `sets/en.json` for the set id, then `cards/en/<id>.json` for `images.small`. It makes no network call. The live `api.pokemontcg.io` answered HTTP 500 and 502 to every query tried, including the one the stock-images research recorded working, and its own notice sets shutdown at 2027-03-01. The gap is that the vendored tree is refreshed by hand (`make catalog-refresh`), so a set released after the last refresh has no row and no stock image. It is a join miss, never a guess.

**Outcome at risk.** A new set's cards show no stock photo until someone re-vendors.

**Closes when.** Either a periodic re-clone on the same on-demand model as `catalog-refresh`, or a live-API fallback in `pipeline/stockimages.py:_PokemonImages` tried only on a vendored miss. Build the fallback only once the API answers reliably, and know it cannot outlive its shutdown date. No test or check may make a real network call.
