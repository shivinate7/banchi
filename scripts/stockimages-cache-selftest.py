#!/usr/bin/env python3
"""D-demo-stock-images: `StockImages` answers Riftbound offline from a pre-warmed disk
cache, and answers `None` with no cache at all — never a network call either way (`Market`
here is given no `fetcher`, so a miss that were to reach the network raises, which this test
would surface as a crash rather than a silent pass).

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

from pipeline import pricehistory, stockimages  # noqa: E402

GAME = "riftbound"
SET_NAME = "Origins"
CATEGORY_ID = 68
GROUP_ID = 12345
NUMBER = "001/240"
IMAGE_URL = "https://tcgplayer-cdn.tcgplayer.com/product/example.jpg"


def _seed(cache_dir: Path) -> None:
    def write(slug: str, payload: dict) -> None:
        path = cache_dir / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": time.time(), "payload": payload}), "utf-8")

    write("tcgcsv/categories", {"results": [{"name": "Riftbound League of Legends Trading Card Game", "categoryId": CATEGORY_ID}]})
    write(f"tcgcsv/{CATEGORY_ID}/groups", {"results": [{"name": SET_NAME, "groupId": GROUP_ID}]})
    write(
        f"tcgcsv/{CATEGORY_ID}/{GROUP_ID}/products",
        {
            "results": [
                {
                    "imageUrl": IMAGE_URL,
                    "extendedData": [{"name": "Number", "value": NUMBER}],
                }
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
