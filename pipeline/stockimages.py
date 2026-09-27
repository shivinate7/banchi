"""Stock card images: `(game, set_name, number)` -> a hotlinked photo URL, or `None`.

`docs/specs/stock-images.md` is the spec — read it first. This module is a thin resolver,
never a mirror (the owner's own call): it answers with a URL on someone else's CDN and never
downloads or stores the bytes. A join miss answers `None`, never a guess (`CLAUDE.md`'s hard
rule against guessing an identification, applied here to a photo instead of a name).

TWO SOURCES, ONE PER PRODUCT LINE. Riftbound and One Piece go through `tcgcsv.com`, reusing
`pipeline/pricehistory.py:Market` for the categories/groups/products walk that module already
built and caches — a second HTTP client here would be the workaround `CLAUDE.md` says to
check for a primitive before writing. Pokemon goes through the vendored
`vendor/pokemon-tcg-data/` tree (D15) instead of `api.pokemontcg.io`, and that is a deliberate
departure from this feature's own research notes, not an oversight: the research found the
live API at 100% coverage for one set; a live check made while building this (2026-09-26)
found it answering HTTP 500/502 on every query, including the exact one the research recorded
working. The vendored snapshot carries the SAME `images.pokemontcg.io` CDN URLs, verbatim,
committed and refreshed on demand by `make catalog-refresh` — no network call, no flakiness,
and nothing to stub in a test. DEBT44 records the live API as the future path once the
vendored tree lags a new set, and why this module does not depend on it today.

SEVERAL SKUS SHARE ONE URL, ON PURPOSE (the owner's own addition, mid-build): a foil and a
normal printing of one card are the same physical product to both catalogs, so both resolve to
the same image. This module never dedupes a caller's rows over that — it only ever answers the
question it is asked, one `(game, set_name, number)` at a time.

CACHED PER GROUP OR SET, NEVER PER CARD: one fetch (tcgcsv) or one file read (Pokemon) answers
every card in it, so a screen asking about the second card of a set already open costs nothing
more.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from pipeline import games as game_registry
from pipeline import join
from pipeline.pricehistory import (
    CATALOG_HOST,
    EXTENDED_NUMBER,
    PriceHistoryError,
    Market,
    extended,
)

# A SHORT TTL, NEVER `pricehistory.CATALOG_TTL_SECONDS` (which is infinite): that constant is
# right for the archive sweep's own products list, which barely moves. This resolver's whole
# reason to exist is fresh art on a screen the owner is looking at right now, so it asks
# tcgcsv again well within one sitting rather than trusting a fetch from days ago forever.
TCGCSV_TTL_SECONDS = 3600.0

VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor" / "pokemon-tcg-data"

POKEMON_KEY = "pokemon"


class _PokemonImages:
    """`set_name` -> `number` -> image URL, off the vendored pokemon-tcg-data tree (D15).

    NO NETWORK, EVER. `vendor/pokemon-tcg-data/sets/en.json` and `cards/en/<id>.json` are
    committed files, and both already carry the exact CDN URLs `api.pokemontcg.io` answers
    with — this class only ever reads disk. Cached by the file's own mtime, so a
    `make catalog-refresh` while the server is up is picked up on the next request rather
    than needing a restart, and nothing here needs a TTL to go stale by.
    """

    def __init__(self, root: Path = VENDOR_ROOT) -> None:
        self._root = root
        self._set_ids: Optional[Dict[str, str]] = None
        self._numbers: Dict[str, Dict[str, str]] = {}
        self._numbers_mtime: Dict[str, float] = {}

    def _set_ids_by_name(self) -> Dict[str, str]:
        if self._set_ids is None:
            path = self._root / "sets" / "en.json"
            try:
                rows = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                rows = []
            self._set_ids = {
                join.normalize_set(str(row.get("name") or "")): str(row["id"])
                for row in rows
                if row.get("id") and row.get("name")
            }
        return self._set_ids

    def _numbers_for(self, set_id: str) -> Dict[str, str]:
        path = self._root / "cards" / "en" / f"{set_id}.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {}
        if self._numbers_mtime.get(set_id) != mtime:
            try:
                rows = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                rows = []
            index: Dict[str, str] = {}
            for row in rows:
                url = (row.get("images") or {}).get("small")
                number = row.get("number")
                if url and number:
                    index.setdefault(join.number_index_key(number), str(url))
            self._numbers[set_id] = index
            self._numbers_mtime[set_id] = mtime
        return self._numbers.get(set_id, {})

    def url_for(self, set_name: str, number: str) -> Optional[str]:
        set_id = self._set_ids_by_name().get(join.normalize_set(set_name))
        if set_id is None:
            return None
        return self._numbers_for(set_id).get(join.number_index_key(number))


class StockImages:
    """One server process's resolver, ONE INSTANCE FOR THE PROCESS'S LIFE.

    A caller that constructs a fresh one per request gets no caching at all — `market`
    defaults to `cache_dir=None` (in-memory only), which is exactly the cache this class's
    OWN instance is for. `server/pipeline_routes.py:STOCK_IMAGES` is that one instance; a
    harness test that calls a route function directly passes no resolver at all (the
    functions default to `None` and answer every `image_url` as `None`), so no test opens a
    socket.
    """

    def __init__(self, market: Optional[Market] = None, pokemon: Optional[_PokemonImages] = None) -> None:
        self._market = market if market is not None else Market(cache_dir=None)
        self._pokemon = pokemon if pokemon is not None else _PokemonImages()
        # `(categoryId, groupId) -> {number_index_key: imageUrl}`. Built here rather than
        # through `pricehistory.ProductIndex`, which does not carry `imageUrl` at all — that
        # class exists for the listing join (D254) and has no reason to grow a field only a
        # photo needs.
        self._tcgcsv_images: Dict[Tuple[int, int], Dict[str, str]] = {}

    def _tcgcsv_group_images(self, category_id: int, group_id: int) -> Dict[str, str]:
        key = (category_id, group_id)
        if key not in self._tcgcsv_images:
            payload = self._market.get(
                f"{CATALOG_HOST}/tcgplayer/{category_id}/{group_id}/products",
                f"stockimages/{category_id}/{group_id}/products",
                TCGCSV_TTL_SECONDS,
            )
            index: Dict[str, str] = {}
            for product in payload.get("results") or ():
                url = product.get("imageUrl")
                number = extended(product, EXTENDED_NUMBER)
                if url and number:
                    # `setdefault`: the first product a group lists for a number wins. A
                    # SECOND product sharing a number would be two physical cards this
                    # resolver cannot tell apart from a `(set, number)` pair alone — the
                    # same ambiguity `ProductIndex.find` refuses on, here just kept rather
                    # than raised, because a photo miss costs a blank tile and not a wrong
                    # listing.
                    index.setdefault(join.number_index_key(number), str(url))
            self._tcgcsv_images[key] = index
        return self._tcgcsv_images[key]

    def url_for(self, game: str, set_name: str, number: str) -> Optional[str]:
        """The image for one card, or `None` on a join miss or an unreachable catalogue.

        NEVER RAISES. A tcgcsv fetch that fails answers `None` exactly like a miss —
        `#/pricing` and Inventory's Sets view both draw fine with no photo, and a public
        mirror having a bad moment must not take either screen down with it (the same
        posture `_history_unreachable` already gives the price-history panel).
        """
        if not game or not set_name or not number:
            return None
        if game == POKEMON_KEY:
            return self._pokemon.url_for(set_name, number)
        try:
            product_line = str(game_registry.get(game)["product_line"])
            category_id = self._market.category_id(product_line)
            group_id = self._market.group_id(category_id, set_name)
        except (PriceHistoryError, KeyError):
            return None
        return self._tcgcsv_group_images(category_id, group_id).get(join.number_index_key(number))
