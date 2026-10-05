"""The one UTC-second stamp every receipt writes, and the one way to read it back (DEBT86)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def now() -> datetime:
    """Now, UTC, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment: datetime) -> str:
    return moment.isoformat()


def now_iso() -> str:
    """UTC, to the second, as the stamp a receipt carries."""
    return iso(now())


def parse(stamp: Optional[str]) -> Optional[datetime]:
    """A stamp as an aware datetime, or None for an empty or unreadable one. A naive stamp is UTC."""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
