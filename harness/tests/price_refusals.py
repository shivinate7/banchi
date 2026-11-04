"""The refusal texts the price reader really writes, taken from its own raise paths.

One home for `scripts/pricearchive-selftest.py`, `scripts/archive-review-selftest.py` and the T7
price-moves group (`harness/tests/t7/price_moves.py`). A test that needs a refusal calls one of
these and never types the sentence: a typed copy goes stale the day the reader's sentence changes,
and the test then proves a message nobody sees any more.

NO SOCKET AND NO SLEEP. The only thing stubbed is `pipeline/net.py:request`, which the reader calls
for every network read: it raises the error a host or a dropped connection would, or hands back a
body. Everything above it (`fetch_json`, `Market.get`, `readings_for_rows`, the catalogue walk)
runs as shipped. The catalogue walk's payloads come from a stub fetcher, and `courtesy_delay` is 0,
so no clock is read.
"""

from __future__ import annotations

import io
import urllib.error
from contextlib import redirect_stderr
from typing import Dict, Optional
from unittest import mock

from pipeline import net, pricehistory, tcgcsv

# Only `fetch_json` reads this URL, and the stub sends it nowhere.
PRICE_URL = "https://infinite-api.tcgplayer.com/price/history/652771/detailed?range=month"


def net_error(status: int) -> net.NetError:
    """The error `net.request` raises for an HTTP answer with this status."""
    return net.NetError(f"The host answered with status {status}.", status=status)


def _failure(cls, message: str, cause: BaseException) -> net.NetError:
    """A `net` error as `net.open` raises it: its `__cause__` is what urllib (or the socket) raised."""
    error = cls(message)
    error.__cause__ = cause
    return error


def _stub(outcome) -> mock.Mock:
    """`net.request` as a stub: it raises `outcome` when that is an exception, else returns it."""
    if isinstance(outcome, BaseException):
        return mock.Mock(side_effect=outcome)
    return mock.Mock(return_value=outcome)


def fetch_refusal(outcome) -> Optional[BaseException]:
    """What the real `pricehistory.fetch_json` raises when `net.request` does `outcome`.

    `outcome` is an exception (the request failed) or bytes (the host answered with that body).
    Returns whatever was raised, or None when nothing was. Any exception is returned rather than
    re-raised, so a caller checks its type first and a wrong type is a failed assertion, not a crash.
    """
    with mock.patch.object(net, "request", _stub(outcome)), redirect_stderr(io.StringIO()):
        try:
            pricehistory.fetch_json(PRICE_URL)
        except Exception as caught:  # noqa: BLE001 - returned, so the caller asserts on its type
            return caught
    return None


def network_refusals() -> Dict[str, Optional[BaseException]]:
    """Each network failure the reader can meet, by name, as `fetch_json` raised it."""
    return {
        "403": fetch_refusal(net_error(403)),
        "500": fetch_refusal(net_error(500)),
        "offline": fetch_refusal(_failure(net.Offline, "no connection", urllib.error.URLError("refused"))),
        "dropped": fetch_refusal(_failure(net.Dropped, "read stalled", TimeoutError("timed out"))),
        "unreadable": fetch_refusal(b"not json"),
        "undecodable": fetch_refusal(b"\xff\xfe"),
    }


def folded_history_refusal(outcome=None, *, sku: str = "652771", product_id: int = 652771) -> Optional[str]:
    """The text `Market.readings_for_rows` folds a history refusal to (`str(exc)`, no URL).

    `outcome` is what `net.request` does; the default is an HTTP 403. The productId is given, so no
    catalogue walk runs. Returns None when the history read did not refuse.
    """
    if outcome is None:
        outcome = net_error(403)
    row = {tcgcsv.SKU_COLUMN: sku}
    market = pricehistory.Market(courtesy_delay=0.0)
    with mock.patch.object(net, "request", _stub(outcome)), redirect_stderr(io.StringIO()):
        _, refusals = market.readings_for_rows([row], ranges=("month",), product_ids={sku: product_id})
    return refusals.get(sku)


def _catalog(url: str) -> Dict:
    """A stub fetcher for the catalogue walk. The product line `Riftbound` and the set `Vendetta`
    exist; no product is listed in the set, so the walk finds nothing and refuses."""
    if url.endswith("/categories"):
        return {"results": [{"name": "Riftbound", "categoryId": 3}]}
    if url.endswith("/groups"):
        return {"results": [{"name": "Vendetta", "groupId": 24}]}
    return {"results": []}


def not_resolvable_refusals() -> Dict[str, Optional[BaseException]]:
    """What each identification step raises with no network, by the stage that raised it.

    Each value is the exception (a `NotResolvable` when the reader is right), or None when that
    stage answered. `ProductIndex.find` returns None and never raises, so its refusal reaches a
    caller as the one `Market.product_id_for_row` writes after the find misses: the `product` entry.
    """
    market = pricehistory.Market(cache_dir=None, fetcher=_catalog, courtesy_delay=0.0)
    row = {
        tcgcsv.PRODUCT_LINE_COLUMN: "Riftbound",
        tcgcsv.SET_COLUMN: "Vendetta",
        tcgcsv.NUMBER_COLUMN: "",
        tcgcsv.NAME_COLUMN: "Shadbow Temple",
        tcgcsv.SKU_COLUMN: "AAA",
        tcgcsv.CONDITION_COLUMN: "Near Mint",
    }
    unsold = {**row, tcgcsv.SKU_COLUMN: ""}
    calls = {
        "product line": lambda: market.category_id("No Such Line"),
        "set": lambda: market.group_id(3, "No Such Set"),
        "product": lambda: market.product_id_for_row(row),
        "no sku": lambda: market.reading_for_row(unsold),
        "product id": lambda: pricehistory.history_url("not-a-product", "month"),
    }
    raised: Dict[str, Optional[BaseException]] = {}
    for stage, call in calls.items():
        try:
            call()
        except Exception as caught:  # noqa: BLE001 - returned, so the caller asserts on its type
            raised[stage] = caught
        else:
            raised[stage] = None
    return raised
