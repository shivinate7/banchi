"""Which listed SKUs have moved more than 10% in the market since they were listed (DEBT69).

A READ, NEVER A DECISION. This names what moved, the direction and the amount, and nothing
that calls it changes a price. An automatic push of new prices is a separate decision.

THE BASELINE IS THE ARCHIVE'S BUCKET THAT COVERS THE LISTING DAY (D219), NEVER A GUESS. A SKU
listed before the archive's first bucket, or in a week the archive never read, has no baseline
and is COUNTED as unmeasured, never dropped and never filled in. "Now" is the newest reading
(`store/readings.py`, D189), which the scheduled refresh keeps current.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

#: "More than 10%", strictly. Owner's figure (DEBT69).
THRESHOLD = Decimal("0.10")

#: `(start "YYYY-MM-DD", market, width_days)` as `store.pricearchive.Point` carries it.
PointLike = Sequence


@dataclass(frozen=True)
class Mover:
    sku: str
    then: Decimal
    now: Decimal
    #: Signed fraction, `(now - then) / then`. 0.14 is up fourteen percent.
    change: Decimal

    @property
    def direction(self) -> str:
        return "up" if self.change > 0 else "down"


def _money(text: object) -> Optional[Decimal]:
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() and value > 0 else None


def baseline_at(points: Iterable[PointLike], listed: date) -> Optional[Decimal]:
    """The market of the bucket that COVERS `listed`, finest width first; None when none does."""
    covering: List[Tuple[int, Decimal]] = []
    for start, market, width in points:
        price = _money(market) if market is not None else None
        try:
            begins = date.fromisoformat(str(start))
        except ValueError:
            continue
        if price is not None and begins <= listed < begins + timedelta(days=int(width)):
            covering.append((int(width), price))
    return min(covering, key=lambda c: c[0])[1] if covering else None


def movers(
    listed: Dict[str, date],
    now: Dict[str, str],
    points_of: Callable[[str], Iterable[PointLike]],
    threshold: Decimal = THRESHOLD,
) -> Tuple[List[Mover], int]:
    """`(movers largest first, count of listed SKUs with no baseline or no current reading)`."""
    found: List[Mover] = []
    unmeasured = 0
    for sku, day in sorted(listed.items()):
        then = baseline_at(points_of(sku), day)
        current = _money(now[sku]) if sku in now else None
        if then is None or current is None:
            unmeasured += 1
            continue
        change = (current - then) / then
        if abs(change) > threshold:
            found.append(Mover(sku, then, current, change))
    found.sort(key=lambda m: (-abs(m.change), m.sku))
    return found, unmeasured
