#!/usr/bin/env python3
"""D301: `StockImages` answers Riftbound offline from a pre-warmed disk
cache, and answers `None` with no cache at all — never a network call either way (`Market`
here is given no `fetcher`, so a miss that were to reach the network raises, which this test
would surface as a crash rather than a silent pass).

Protects: Stock images answer offline from a warmed disk cache and answer nothing, with no network call, when the cache is empty.
Governs: D301

Proves the one fact the demo mirror depends on: `pipeline/stockimages.py`'s own disk cache
slug (`tcgcsv/<category>/<group>/products`) is the SAME one
`cli/cmd_pricearchive.py:market_cache_dir` already warms on the owner's Mac, so copying that
directory into the mirror (`scripts/demo-mirror.py`'s `SIDE_DIRS`) is enough — no second,
private cache format to keep in step.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import games, pricehistory, stockimages  # noqa: E402

GAME = "riftbound"
SET_NAME = "Origins"
CATEGORY_ID = 68
GROUP_ID = 12345
NUMBER = "001/240"
IMAGE_URL = "https://tcgplayer-cdn.tcgplayer.com/product/example.jpg"

# F2 (the owner: "why does the sales page not pull the icons"): a SEALED product has no
# `Number` cell at all, and resolves by product name instead — `url_for_product`, keyed by
# `product_line` text rather than a `game` key, since a Sales row's SKU carries no game.
# One Pokemon case (the vendored tree has no sealed row for this at all) and one non-Pokemon
# case, in the SAME disk cache slug `url_for` already proved above.
POKEMON_PRODUCT_LINE = "Pokemon"
POKEMON_CATEGORY_ID = 3
POKEMON_SET_NAME = "Scarlet & Violet"
POKEMON_GROUP_ID = 54321
SEALED_PRODUCT_NAME = "Scarlet & Violet Elite Trainer Box"
SEALED_IMAGE_URL = "https://tcgplayer-cdn.tcgplayer.com/product/sealed-example.jpg"

# A NAME COLLISION (review round, 2026-09-27): two distinct products sharing one name in one
# group. A `setdefault`-first-wins dict would silently answer the first one's photo; the fix
# is `ProductIndex.find`'s own ambiguity refusal, which must answer `None` here instead.
COLLIDING_PRODUCT_NAME = "Booster Box"


def _seed(cache_dir: Path) -> None:
    def write(slug: str, payload: dict) -> None:
        path = cache_dir / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": time.time(), "payload": payload}), "utf-8")

    write(
        "tcgcsv/categories",
        {
            "results": [
                {"name": "Riftbound League of Legends Trading Card Game", "categoryId": CATEGORY_ID},
                {"name": POKEMON_PRODUCT_LINE, "categoryId": POKEMON_CATEGORY_ID},
            ]
        },
    )
    write(f"tcgcsv/{CATEGORY_ID}/groups", {"results": [{"name": SET_NAME, "groupId": GROUP_ID}]})
    write(
        f"tcgcsv/{CATEGORY_ID}/{GROUP_ID}/products",
        {
            "results": [
                {
                    "imageUrl": IMAGE_URL,
                    "extendedData": [{"name": "Number", "value": NUMBER}],
                    "productId": 70001,
                },
                # THE NAME-COLLISION FIXTURE — same name, two different products, no number.
                {"imageUrl": "https://tcgplayer-cdn.tcgplayer.com/product/collide-a.jpg", "name": COLLIDING_PRODUCT_NAME, "productId": 70002},
                {"imageUrl": "https://tcgplayer-cdn.tcgplayer.com/product/collide-b.jpg", "name": COLLIDING_PRODUCT_NAME, "productId": 70003},
            ]
        },
    )
    write(
        f"tcgcsv/{POKEMON_CATEGORY_ID}/groups",
        {"results": [{"name": POKEMON_SET_NAME, "groupId": POKEMON_GROUP_ID}]},
    )
    write(
        f"tcgcsv/{POKEMON_CATEGORY_ID}/{POKEMON_GROUP_ID}/products",
        {
            "results": [
                # `productId` IS REQUIRED (review round, 2026-09-27): a name-based lookup
                # resolves through `pricehistory.ProductIndex`, which is keyed by id — a
                # product with no id cannot be found by name either, matching a real tcgcsv
                # payload, where every product always carries one.
                {"imageUrl": SEALED_IMAGE_URL, "name": SEALED_PRODUCT_NAME, "productId": 90001},
            ]
        },
    )


def _offline(url: str) -> dict:
    """The same failure `demo-record.py`'s `OFFLINE_BOOT` produces for a real socket."""
    raise pricehistory.Offline("demo mirror recording is offline: refused %s" % url)


def _url_for(cache_dir: Path) -> Optional[str]:
    """Answers ONLY from disk — the fetcher always fails offline, so a non-`None` result
    proves the cache served it, never a network call this test would otherwise miss."""
    market = pricehistory.Market(cache_dir=cache_dir, fetcher=_offline)
    images = stockimages.StockImages(market=market)
    threads = images.warm([(GAME, SET_NAME)])
    for thread in threads:
        thread.join(timeout=5)
    return images.url_for(GAME, SET_NAME, NUMBER)


def _url_for_product(cache_dir: Path, product_line: str, set_name: str, product_name: str) -> Optional[str]:
    """`url_for_product`'s own disk-only round trip (F2) — same offline fetcher, same
    proof: a non-`None` answer came from the seeded cache, never a socket.

    WARMS AND JOINS FIRST, exactly like `_url_for` above: `url_for_product` itself only
    ever reads `_cache` and schedules a background refresh on a miss (never blocks), so an
    un-warmed first call would race that background thread and answer `None` even from a
    warm disk cache. `games.game_for_product_line` is `url_for_product`'s own first step,
    reused here rather than re-typed, to get the `(game, set_name)` pair `warm()` needs.

    `allow_pokemon=True` (review round, 2026-09-27): `warm()` refuses a Pokemon pair by
    default — a Pokemon CARD never needs this cache, and warming every Pokemon set at
    startup for nothing was the second finding that round caught — so the one caller
    allowed to ask for a Pokemon SEALED product's warm says so explicitly, the same way
    `_tcgcsv_name_lookup` itself does.
    """
    market = pricehistory.Market(cache_dir=cache_dir, fetcher=_offline)
    images = stockimages.StockImages(market=market)
    game = games.game_for_product_line(product_line)
    if game is not None:
        for thread in images.warm([(game, set_name)], allow_pokemon=True):
            thread.join(timeout=5)
    return images.url_for_product(product_line, set_name, product_name)


def main() -> int:
    with tempfile.TemporaryDirectory() as empty_dir:
        cold = _url_for(Path(empty_dir))
        assert cold is None, "no cache on disk must answer None, got %r" % (cold,)
    print("RED proved: no cache -> None")

    with tempfile.TemporaryDirectory() as warm_dir:
        _seed(Path(warm_dir))
        warm = _url_for(Path(warm_dir))
        assert warm == IMAGE_URL, "a warm disk cache must answer its URL, got %r" % (warm,)
    print("GREEN proved: warm cache -> %s" % IMAGE_URL)

    # F2: a SEALED product (no card number) resolves by product name instead, off the SAME
    # disk cache slug — Pokemon (no vendored sealed row exists at all) and one other game.
    with tempfile.TemporaryDirectory() as empty_dir:
        cold_sealed = _url_for_product(Path(empty_dir), POKEMON_PRODUCT_LINE, POKEMON_SET_NAME, SEALED_PRODUCT_NAME)
        assert cold_sealed is None, "no cache on disk must answer None for a sealed product too, got %r" % (cold_sealed,)
    print("RED proved: no cache -> None (sealed product)")

    with tempfile.TemporaryDirectory() as warm_dir:
        _seed(Path(warm_dir))
        pokemon_sealed = _url_for_product(Path(warm_dir), POKEMON_PRODUCT_LINE, POKEMON_SET_NAME, SEALED_PRODUCT_NAME)
        assert pokemon_sealed == SEALED_IMAGE_URL, (
            "a warm disk cache must answer a Pokemon sealed product's URL, got %r" % (pokemon_sealed,)
        )
        riftbound_sealed_miss = _url_for_product(Path(warm_dir), "Riftbound League of Legends Trading Card Game", SET_NAME, "No Such Booster Box")
        assert riftbound_sealed_miss is None, "a sealed-product NAME miss must answer None, never a guess"
        unregistered = _url_for_product(Path(warm_dir), "Not A Real Product Line", "Anywhere", "Anything")
        assert unregistered is None, "a product_line no game claims must answer None, never a guess"
        # THE NAME-COLLISION CASE (review round, 2026-09-27): two products share one name in
        # one group. A wrong fix answers the first one's photo; the right one refuses.
        colliding = _url_for_product(
            Path(warm_dir), "Riftbound League of Legends Trading Card Game", SET_NAME, COLLIDING_PRODUCT_NAME
        )
        assert colliding is None, (
            "two products sharing one name in one group must answer None, never either "
            "one's photo — got %r" % (colliding,)
        )
    print("GREEN proved: warm cache -> %s (Pokemon sealed, no vendored row needed)" % SEALED_IMAGE_URL)
    print("GREEN proved: a name collision answers None, never a guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
