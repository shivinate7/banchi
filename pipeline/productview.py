"""The per-product view's own read: one SKU's market history, archive-first, live-fallback
(D-a-product-price-view).

WHAT THIS ANSWERS. `docs/specs/revenue-plan.md` section 3: one page per product, showing what
it has been selling for, with the owner's own sales marked on it. The owner's fills are
already on the wire — `GET /orders` carries every line's SKU, quantity and unit price, and
`app/src/Revenue.tsx` already reshapes that same payload client-side. This module answers the
other half only: the MARKET side, which needs a server hop because it is a read off the
archive table or, failing that, a public host.

ARCHIVE FIRST, LIVE ONLY WHEN THE ARCHIVE HAS NEVER SEEN THE SKU AT ALL. `store/pricearchive.py`
never deletes a row, so a SKU the sweep has ever visited keeps every bucket it was ever read
with, past the source's own 357-day slide. This module trusts that table completely once it
has anything for a SKU — a live re-read of a SKU the archive already covers would spend a
request restating what is already on disk, and worse, would silently widen this READ-ONLY
view's job to "call a mirror on every page view," which is the rude pattern D62's own panel
was built once to avoid. Only a SKU the archive has zero rows for at all falls through to
`pipeline/pricehistory.py:Market`, the same reader `server/pipeline_routes.py:_history_for_entry`
already calls for `#/pricing`'s panel — one live read, cached the way that call already is,
never a sweep and never a write to the archive table.

NEVER WRITES. Not to `price_history`, not to `price_history_sources`, not to the corpus. A
live fallback read is answered straight to the caller and never folded back into the archive
— `pkmnscan archive sweep` is the one press that does that, and it stays a press (D62's own
statement: this reader cannot fire on its own).

THE SPREAD IS CARRIED PER BUCKET, NEVER COLLAPSED TO ONE NUMBER. Each archived bucket already
holds its own `low`/`high` alongside `market`; this module passes them through rather than
computing a single band across the whole series, which is the honest shape for what
`store/pricearchive.py` actually stores — a walk over buckets, not a re-fetch of the raw
Series object `pipeline/pricehistory.py:Bound` is computed from. The live-fallback path
reaches an actual `Series` and DOES carry `Bound` (`_history_series`'s own shape, imported
rather than re-derived, per `CLAUDE.md`'s primitive-first rule).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pipeline import pricearchive as archive_walk
from store.pricearchive import Bucket, PriceArchive
from store.session import Snapshot


class ProductNotFound(RuntimeError):
    """No card in this store has ever carried this SKU. Distinct from `not_catalogued` —
    that is a SKU this store knows but cannot look a category up by; this is a SKU this
    store has never recorded at all, which is a query typo far more often than a data gap."""


def row_for_sku(snapshot: Snapshot, sku: str) -> dict:
    """The export-shaped row `pipeline/pricearchive.py:rows_from_store` would build for this
    one SKU, without walking the whole `cards` table for a single lookup. Raises
    `ProductNotFound` when no card has ever carried it."""
    rows = archive_walk.rows_from_store(snapshot)
    row = rows.get(str(sku).strip())
    if row is None:
        raise ProductNotFound(sku)
    return row


def _bucket_payload(bucket: Bucket) -> dict:
    """One archived bucket as the chart reads it — money strings passed through untouched
    (`pipeline/pricearchive.py` already stores them as `str(Decimal(...))`), spread carried
    on the same row rather than discarded."""
    return {
        "at": bucket.start,
        "market": bucket.market,
        "quantity": bucket.quantity,
        "transactions": bucket.transactions,
        "low": bucket.low,
        "high": bucket.high,
    }


def _archive_range_series(range_: str, width_days: int, buckets: List[Bucket]) -> dict:
    """One range's own archived buckets, ascending by start — `PriceArchive.for_sku` already
    sorts by `(range, start)`, so buckets arriving here are already in order."""
    starts = [b.start for b in buckets]
    return {
        "range": range_,
        "width_days": width_days,
        "buckets": len(buckets),
        "from": starts[0] if starts else None,
        "to": starts[-1] if starts else None,
        "latest_market": buckets[-1].market if buckets else None,
        "points": [_bucket_payload(b) for b in buckets],
    }


def archive_payload(archive: PriceArchive, sku: str) -> Optional[List[dict]]:
    """Every range this archive holds for `sku`, or `None` when it has never seen this SKU
    at all — the caller's own signal to fall back to a live read."""
    buckets = archive.for_sku(sku)
    if not buckets:
        return None
    by_range: Dict[str, List[Bucket]] = {}
    for bucket in buckets:
        by_range.setdefault(bucket.range, []).append(bucket)
    return [
        _archive_range_series(range_, by_range[range_][0].width_days, by_range[range_])
        for range_ in sorted(by_range)
    ]


def history_begins(ranges: List[dict]) -> Optional[str]:
    """The earliest bucket start across every range this payload carries — the date the
    chart states as where its own history begins, computed from what was actually read
    rather than from the 357-day constant (`docs/specs/revenue-next.md`'s own rule: a year of
    local archive is not a year of market history, and the two must never be conflated)."""
    starts = [r["from"] for r in ranges if r.get("from")]
    return min(starts) if starts else None
