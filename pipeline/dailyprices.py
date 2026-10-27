"""The daily read of TCGCSV's current Riftbound prices, saved once per source update (`store/dailyprices.py`).

WHY. `tcgcsv.com` withdrew its past-days archive, so a whole-market price history can only be built by reading the
current file each day and keeping it. This pass is that read. Riftbound is category 89. FREE, public, no key, and it
changes nothing at TCGplayer. The decision is D-tcgcsv-daily-read; no screen reads the rows yet.

THE KEY IS THE SOURCE'S OWN UPDATE, NEVER THE CLOCK. TCGCSV refreshes once a day and says when in
`last-updated.txt`. A pass fetches that stamp first and stops there when it is a finished update already saved. Rows
are keyed on the stamp's UTC date. `now` stamps a row's `at` and nothing else, so a read at 23:00 and one at 05:15
the next day cannot save one update twice.

THE SITE'S RULES. The request budget is the stamp, the group list and one prices file per group: never the products
files, never the categories list, no file twice in a pass. A pause of `pricehistory.COURTESY_DELAY_SECONDS` sits
between requests, the stamp's included. After a throttle answer (HTTP 429) the pause is the larger of that delay and
`net.retry_after`, and a second throttle answer in one pass stops the pass: the update stays open and the next start
goes on from there.

A GROUP FAILS, and the others go on, when its prices raise a `PriceHistoryError`, when its payload is not a dict or
has no list under `results`, or when it says `"success": false`. A reply of `"success": true` with no results is a
real, empty group and is saved. A FAILED GROUP LEAVES THE UPDATE UNFINISHED. The next pass for the same stamp asks
for the group list and for the groups not yet saved, no others. A pass with no failed group finishes the update.

ONE WRITE PER PASS, at its end (D88, one transaction per write): the rows of every group that did not fail and their
marks land together. A crash keeps no row of the pass, and the next pass for the same stamp reads every group again.
Rows are never deleted
(D219).

ONE HTTP CLIENT. `pricehistory.fetch_json` and its text twin `fetch_text` go through `pipeline.net.request`. The
`Market` that reads the URLs is `pricehistory`'s, with no cache, because a cached price file would hand back
yesterday's update. `fetch` is a seam for a harness; `None` means the real client.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Optional

from pipeline import net, pricehistory
from store import clock
from store.dailyprices import DailyPrice, Update
from store.session import Store

CATEGORY_ID = 89  # Riftbound
STAMP_URL = pricehistory.CATALOG_HOST + "/last-updated.txt"
THROTTLES_THAT_STOP_A_PASS = 2


def _client(user_agent: str) -> Callable[[str], object]:
    """The real client: text for the stamp, JSON for every other URL. Looked up when it runs."""
    def fetch(url: str):
        if url == STAMP_URL:
            return pricehistory.fetch_text(url, user_agent=user_agent)
        return pricehistory.fetch_json(url, user_agent=user_agent)
    return fetch


def _day_of(stamp: str) -> str:
    """The stamp's UTC date, never its Central date."""
    moment = clock.parse(stamp)
    if moment is None:
        raise pricehistory.Unreachable("The price service sent a last-updated time that could not be read.")
    return moment.astimezone(timezone.utc).date().isoformat()


def _throttled(exc: pricehistory.PriceHistoryError) -> bool:
    return isinstance(exc.__cause__, net.NetError) and exc.__cause__.status == 429


def _unreadable(payload) -> Optional[str]:
    """Why a group's payload cannot be trusted, or None. An empty list of results is a real, empty group."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return "The price service sent back a set's prices in a shape that could not be read. Try again in a moment."
    if payload.get("success") is False:
        return "The price service said it could not give a set's prices. Try again in a moment."
    return None


def run_pass(
    fetch: Optional[Callable[[str], object]] = None,
    *,
    now: Optional[datetime] = None,
    user_agent: str = pricehistory.USER_AGENT,
) -> dict:
    """One pass. Answers `{"day", "updated", "skipped", "rows", "failed": {group_id: message}}`.

    `rows` counts the rows THIS call wrote. A group that fails is named in `failed`; an unreadable stamp or
    group list raises `pricehistory.PriceHistoryError`, for the caller to say."""
    raw = fetch if fetch is not None else _client(user_agent)
    at = int((now or clock.now()).timestamp())
    asked = [0]

    def paced(url: str):
        if asked[0]:
            time.sleep(max(pricehistory.COURTESY_DELAY_SECONDS, net.retry_after(url)))
        asked[0] += 1
        return raw(url)

    stamp = str(paced(STAMP_URL)).strip()
    day = _day_of(stamp)
    saved = Store().read().daily_prices.update(stamp)
    if saved is not None and saved.finished:
        return {"day": day, "updated": stamp, "skipped": True, "rows": 0, "failed": {}}

    market = pricehistory.Market(fetcher=paced, courtesy_delay=0)
    # The raw list, not `Market.groups`: that one is keyed by name, and two groups with one name would drop one.
    listing = market.get(
        f"{pricehistory.CATALOG_HOST}/tcgplayer/{CATEGORY_ID}/groups", f"tcgcsv/{CATEGORY_ID}/groups", 0
    )
    group_ids = [int(group["groupId"]) for group in listing.get("results") or ()]
    if not group_ids:
        raise pricehistory.Unreachable("The price service listed no sets. Try again in a moment.")
    update = saved or Update(stamp, day, (), False, at)
    rows, done, failed, throttles = [], [], {}, 0
    for group_id in group_ids:
        if group_id in update.groups:
            continue
        url = f"{pricehistory.CATALOG_HOST}/tcgplayer/{CATEGORY_ID}/{group_id}/prices"
        try:
            payload = market.get(url, f"tcgcsv/{CATEGORY_ID}/{group_id}/prices", pricehistory.PRICE_TTL_SECONDS)
        except pricehistory.PriceHistoryError as exc:
            failed[group_id] = str(exc)
            throttles += _throttled(exc)
            if throttles >= THROTTLES_THAT_STOP_A_PASS:
                break
            continue
        reason = _unreadable(payload)
        if reason:
            failed[group_id] = reason
            continue
        rows += [
            DailyPrice(
                product_id=price.product_id, sub_type=price.printing, day=day, updated=stamp,
                market=_text(price.market), low=_text(price.low), mid=_text(price.mid),
                high=_text(price.high), direct_low=_text(price.direct_low), group_id=group_id, at=at,
            )
            for price in pricehistory.parse_prices(payload).values()
        ]
        done.append(group_id)
    # One transaction for the pass: every good group's rows and marks land together or not at all.
    with Store().write() as snapshot:
        snapshot.daily_prices.save(update, rows, done, finished=not failed)
    return {"day": day, "updated": stamp, "skipped": False, "rows": len(rows), "failed": failed}


def _text(price) -> Optional[str]:
    return None if price is None else str(price)
