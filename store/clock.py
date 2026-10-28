"""The one UTC-second stamp every receipt writes, and the one way to read it back (DEBT86)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

#: The owner's calendar. A price is "from today" by the US Central day, whatever zone this Mac is set to.
CENTRAL = ZoneInfo("America/Chicago")


def now() -> datetime:
    """Now, UTC, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0)


_current = now  # `now` is also a parameter name below


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


def central_day(moment: datetime) -> date:
    """The US Central calendar day an aware moment falls on."""
    return moment.astimezone(CENTRAL).date()


def before_today(moment: datetime, now: Optional[datetime] = None) -> bool:
    """THE ONE FRESHNESS TEST for anything a send prices from: whether `moment` is on an earlier
    US Central day than `now` (default: now). Midnight and the two daylight-saving shifts fall out of
    comparing calendar days, never a count of seconds."""
    return central_day(moment) < central_day(now or _current())


def seconds_into_today(now: Optional[datetime] = None) -> int:
    """How long ago today's US Central day began, in real seconds (a 23 or 25 hour day included)."""
    moment = (now or _current()).astimezone(CENTRAL)
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((moment.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds())

_RED_PROOF_MYPY: int = "red proof"
