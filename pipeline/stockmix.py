"""`GET /stock/mix`, the Mix lens of Sales (docs/specs/sales-screen.md): one row per card in stock.

ONE HOME, CALLED BY `server/capture_server.py` ONLY. Card rows and nothing else: no order is read
and no revenue is carried, because the refund rule lives in `salesOf` in the browser (D225) and a
server sum would be a second home for it. The browser pivots (`app/src/mixPivot.ts`).

ONE STATEMENT, NO PER-CARD WALK. `cards` joined to `skus`, `readings` and `boxes`. The claim
fields that live only in a card's payload are read with `json_extract` and `json_each`, a week
start is `date()` arithmetic and the 14-day window is `julianday`. A `retired` or `moved` card left
the stock and is never selected. No photograph and no buyer is selected, so none can reach the wire.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from pipeline.games import DEFAULT_GAME
from store import Store, master

# Monday of the week holding a date: back up six days, then forward to the next Monday.
_WEEK = "date(substr({col}, 1, 10), '-6 days', 'weekday 1')"

# A claim stored as a one-member string or as a list reads as its members joined with ' or '.
# `json_extract` hands a list back as minified JSON text, so the brackets and quotes come off
# with `replace`, which keeps the read to one statement with no table-valued function.
_JOINED = (
    "CASE json_type(cards.payload, '$.{f}') WHEN 'array' THEN "
    "replace(replace(substr(json_extract(cards.payload, '$.{f}'), 2, "
    "length(json_extract(cards.payload, '$.{f}')) - 2), '\",\"', ' or '), '\"', '') "
    "ELSE json_extract(cards.payload, '$.{f}') END"
)

# NO ALIASES AND NO WHERE: the read budget's index check reads both (`read_budget.scans`). The
# `retired` and `moved` cards are skipped in `read`, after the one statement.
_SQL = f"""
SELECT cards.game,
       COALESCE(NULLIF(skus.set_name, ''), NULLIF(cards.set_name, ''), NULLIF(cards.set_hint, '')),
       COALESCE(NULLIF(skus.rarity, ''), NULLIF(cards.rarity, ''), NULLIF({_JOINED.format(f='rarity_claim')}, '')),
       COALESCE(NULLIF(skus.condition, ''), NULLIF({_JOINED.format(f='metadata_finish')}, '')),
       cards.state, cards.sku, boxes.name, cards.box,
       {_WEEK.format(col='cards.captured_at')},
       {_WEEK.format(col='cards.state_at')},
       CAST(NULLIF(readings.market, '') AS REAL),
       CASE WHEN cards.state = ? AND julianday(cards.state_at) > julianday(?) THEN 1 ELSE 0 END
FROM cards
LEFT JOIN skus ON skus.key = cards.sku
LEFT JOIN readings ON readings.key = cards.sku
LEFT JOIN boxes ON boxes.box = cards.box
ORDER BY cards.box, cards.idx
"""


def read(now: Optional[datetime] = None) -> dict:
    """`{asOf, cards: [...]}` over one read snapshot. `now` is the as-of time, the server clock."""
    now = now or datetime.now(timezone.utc)
    conn = Store().read().inventory.cards.source.conn
    since = (now - timedelta(days=14)).isoformat()
    cards = []
    for game, set_name, rarity, finish, state, sku, box_name, box, cap_week, sold_week, price, recent in conn.execute(
        _SQL, (master.SOLD, since)
    ):
        if state in (master.RETIRED, master.MOVED):
            continue
        sold = state == master.SOLD
        cards.append({
            "game": game or DEFAULT_GAME,
            "set": set_name or "No set yet",
            "rarity": rarity or ("Unread" if sku else "No claim"),
            "finish": finish or "Unknown",
            "state": "Sold" if sold else ("On hand" if sku else "Not listed yet"),
            "box": box_name or (f"Box {box}" if box is not None else "No box"),
            "capturedWeek": cap_week,
            "soldWeek": sold_week if sold else None,
            "sku": sku or None,
            "price": price,
            "soldRecent": recent,
        })
    return {"asOf": now.isoformat(), "cards": cards}
