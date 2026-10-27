"""The daily read of TCGCSV's current Riftbound prices, saved once per source update (`store/dailyprices.py`).

WHY. `tcgcsv.com` withdrew its past-days archive, so a whole-market price history can only be built by reading the
current file each day and keeping it. This pass is that read. Riftbound is category 89; the price research in
`docs/specs/sales-plan.md` reads the table. FREE, public, no key, and it changes nothing at TCGplayer.

THE KEY IS THE SOURCE'S OWN UPDATE, NEVER THE CLOCK. TCGCSV refreshes once a day and says when in
`last-updated.txt`. A pass fetches that stamp first and stops there when it is a finished update already saved. Rows
are keyed on the stamp's UTC date. `now` stamps a row's `at` and nothing else, so a read at 23:00 and one at 05:15
the next day cannot save one update twice.

THE REQUEST BUDGET: the stamp, the group list, one prices file per group. Never the products files and never the
categories list. A pause of `pricehistory.COURTESY_DELAY_SECONDS` sits between requests, the stamp's included.

A FAILED GROUP LEAVES THE UPDATE UNFINISHED. The other groups go on and are saved. The next pass for the same stamp
asks for the group list and for the groups not yet saved, no others. A pass with no failed group finishes the
update.

ONE HTTP CLIENT. `pricehistory.fetch_json` and its text twin `fetch_text` go through `pipeline.net.request`. The
`Market` that composes the URLs and parses the prices is `pricehistory`'s, with no cache, because a cached price
file would hand back yesterday's update. `fetch` is a seam for a harness; `None` means the real client.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Optional

from pipeline import pricehistory
from store import clock
from store.dailyprices import DailyPrice, Update
from store.session import Store

CATEGORY_ID = 89  # Riftbound
STAMP_URL = pricehistory.CATALOG_HOST + "/last-updated.txt"


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


def run_pass(
    fetch: Optional[Callable[[str], object]] = None,
    *,
    now: Optional[datetime] = None,
    user_agent: str = pricehistory.USER_AGENT,
) -> dict:
    """One pass. Answers `{"day", "updated", "skipped", "rows", "failed": {group_id: message}}`.

    `rows` counts the rows THIS call wrote. A group whose prices fail is named in `failed`; an unreadable stamp or
    group list raises `pricehistory.PriceHistoryError`, for the caller to say."""
    raw = fetch if fetch is not None else _client(user_agent)
    at = int((now or clock.now()).timestamp())
    asked = [0]

    def paced(url: str):
        if asked[0]:
            time.sleep(pricehistory.COURTESY_DELAY_SECONDS)
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
    rows, done, failed = [], [], {}
    for group_id in group_ids:
        if group_id in update.groups:
            continue
        try:
            prices = market.prices(CATEGORY_ID, group_id)
        except pricehistory.PriceHistoryError as exc:
            failed[group_id] = str(exc)
            continue
        rows += [
            DailyPrice(
                product_id=price.product_id, sub_type=price.printing, day=day, updated=stamp,
                market=_text(price.market), low=_text(price.low), mid=_text(price.mid),
                high=_text(price.high), direct_low=_text(price.direct_low), group_id=group_id, at=at,
            )
            for price in prices.values()
        ]
        done.append(group_id)
    # One transaction for the whole pass: the rows and their marks land together or not at all.
    with Store().write() as snapshot:
        snapshot.daily_prices.save(update, rows, done, finished=not failed)
    return {"day": day, "updated": stamp, "skipped": False, "rows": len(rows), "failed": failed}


def _text(price) -> Optional[str]:
    return None if price is None else str(price)
