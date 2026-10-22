"""The My Slabs routes (D320): add a slab by its cert, list the slabs, read one.

    POST /slabs                    read a slab from Card Ladder and write it, today's snapshot and its sales
    GET  /slabs                    every slab with its newest snapshot
    GET  /slabs/<grader>/<cert>    one slab: snapshots, sales and the grade ladder
    DELETE /slabs/<grader>/<cert>  take a slab off the list; its snapshots and sales stay, so adding it again brings them back

There is no sweep route. The owner deferred it: it waits for the owner's word.

THIRD OUTBOUND MODULE, AND THE ONLY ONE THAT HOLDS A LOGIN FOR CARD LADDER. The login is
`CARDLADDER_REFRESH_TOKEN`, read through `envfile.get_live` on every add so a token replaced in the
settings file works on the next press. No token, response body or host reaches an answer, a log
line or a refusal: every sentence below is written here, never relayed from the client.

ONE `pipeline.cardladder.Client` LIVES FOR THE PROCESS, because the 8 second pace and the
rate-limit stop are the client's. ONE ADD RUNS AT A TIME: a second add is refused at once (409),
because the client's pace would queue it behind 16 seconds or more of another add's reads.

A rate-limit answer stops adds for that day (`TODAY`). The day is a `meta` row of the store, so a
restart the same day is stopped too and sends nothing. The client's own stop never clears, so a
limited client is dropped and the next day builds a new one.

AN ADD READS 3.1, 3.2 AND 3.4 OUTSIDE THE STORE LOCK (they are paced and take 16 seconds or
more), then makes ONE store write: the slab, today's snapshot and the sales. Any refusal writes
nothing, because a same-day snapshot replaces every field and a failed read stored as empty
would erase a good value.

The seams are module attributes read at call time: `TRANSPORT`, `CLOCK`, `SLEEP` and `TODAY`.
"""

from __future__ import annotations

import datetime
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from typing import Any, List, Optional

import envfile
from store import db, files
from pipeline import cardladder
from pipeline.pricing import round_money
from server.refusal import BadRequest
from store.session import Store
from store.slabs import GRADERS, SlabSnapshot

TRANSPORT = None  # (method, url, headers, body) -> (status, bytes); None is the client's own
CLOCK = time.monotonic
SLEEP = time.sleep


def TODAY() -> str:  # noqa: N802 - a seam, assigned like the other three
    return datetime.date.today().isoformat()


# The five sales-speed windows of 3.4, the only keys read from them.
_WINDOWS = ("twoWeekData", "oneMonthData", "oneQuarterData", "sixMonthData", "oneYearData")
_ISO_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
_EPOCH_MS = 1e11  # a number at or above this is milliseconds: as seconds it would be the year 5138

_inflight = threading.Lock()  # held for the whole of one add, taken without waiting
_client: Optional[cardladder.Client] = None
LIMITED_DAY = "slabs_rate_limited_day"  # the `meta` key: the day Card Ladder last said to slow down


class _Unreadable(ValueError):
    """An answer from Card Ladder this module cannot turn into a stored value."""


def _refuse(status: HTTPStatus, code: str, message: str):
    raise BadRequest(status, code, message)


def _grader(raw: Any) -> str:
    try:
        return GRADERS[str(raw).lower()]
    except KeyError:
        _refuse(HTTPStatus.BAD_REQUEST, "grader_unknown",
                "That grader is not one this app reads. Use PSA, Beckett, BGS, BVG, SGC or CGC.")


def _rate_limited():
    _refuse(HTTPStatus.TOO_MANY_REQUESTS, "cardladder_rate_limited",
            "Card Ladder asked us to slow down. Nothing was saved. Try again tomorrow.")


def _limited_day() -> Optional[str]:
    conn = db.connect(files.inventory_dir())
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (LIMITED_DAY,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _limit(day: str) -> None:
    conn = db.connect(files.inventory_dir())
    try:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (LIMITED_DAY, day))
    finally:
        conn.close()


def _client_for(token: str, day: str) -> cardladder.Client:
    global _client
    limited = _limited_day()
    if limited is not None and limited >= day:
        _rate_limited()
    if _client is None:
        _client = cardladder.Client(
            refresh_token=token,
            transport=lambda *a: (TRANSPORT or cardladder.net_transport)(*a),
            clock=lambda: CLOCK(),
            sleep=lambda seconds: SLEEP(seconds),
        )
    else:
        _client.use_refresh_token(token)
    return _client


# ---------------------------------------------------------------------------- Card Ladder's numbers


def _money(value: Any) -> Optional[str]:
    """Text money with two decimals: 26.400000000000002 is "26.40". None stays None."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise _Unreadable("money")
    try:
        number = Decimal(repr(value) if isinstance(value, float) else str(value).strip())
        if not number.is_finite():
            raise _Unreadable("money")
        return str(round_money(number))
    except (InvalidOperation, ValueError):
        raise _Unreadable("money") from None


def _whole(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise _Unreadable("whole")
    return int(value)


def _fraction(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _Unreadable("fraction")
    return float(value)


def _day(value: Any) -> str:
    """One ISO day, YYYY-MM-DD, from an ISO date or time, epoch seconds or milliseconds, or a
    seconds object. Card Ladder's form is unmeasured, so anything else is unreadable."""
    if isinstance(value, dict):
        value = value.get("_seconds", value.get("seconds"))
    if isinstance(value, str):
        found = _ISO_DAY.match(value.strip())
        if found:
            try:
                return datetime.date(*(int(part) for part in found.groups())).isoformat()
            except ValueError:
                pass
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1000 if value >= _EPOCH_MS else value
        try:
            return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    raise _Unreadable("date")


def _stored_sale(raw: dict) -> dict:
    if not raw.get("id"):
        raise _Unreadable("sale")
    sale = dict(raw)
    sale["id"] = str(raw["id"])
    sale["date"] = _day(raw.get("date"))
    if "price" in raw:
        sale["price"] = _money(raw["price"])
    return sale


def _same_grader(raw: Any, grader: str) -> bool:
    text = str(raw).lower()
    return GRADERS.get(text, text) == grader


def _ladder(profile: dict, grader: str) -> Optional[List[dict]]:
    """The card's grade ladder at this slab's grader, in Card Ladder's order."""
    for entry in profile.get("graders") or ():
        if isinstance(entry, dict) and _same_grader(entry.get("grader"), grader):
            return [
                {"grade": row.get("grade"), "label": row.get("label"),
                 "cl_value": _money(row.get("clValue")), "cl_confidence": _whole(row.get("clValueConfidence"))}
                for row in entry.get("grades") or () if isinstance(row, dict)
            ]
    return None


def _speed(estimate: dict) -> Optional[dict]:
    speed = {
        window: {"velocity": estimate[window].get("velocity"), "averagePrice": _money(estimate[window].get("averagePrice"))}
        for window in _WINDOWS if isinstance(estimate.get(window), dict)
    }
    return speed or None


# ---------------------------------------------------------------------------- add


def do_slab_add(body: dict) -> dict:
    if not _inflight.acquire(blocking=False):
        _refuse(HTTPStatus.CONFLICT, "slab_add_busy", "A slab is being added right now. Wait for it to finish, then try again.")
    try:
        return _add(body)
    finally:
        _inflight.release()


def _add(body: dict) -> dict:
    global _client
    grader = _grader(body.get("grader"))
    cert = str(body.get("cert") if body.get("cert") is not None else "").strip()
    if not cert:
        _refuse(HTTPStatus.BAD_REQUEST, "cert_required", "Send the slab's cert number.")
    token = envfile.get_live(cardladder.KEY_NAME)
    if not token:
        _refuse(HTTPStatus.CONFLICT, "cardladder_token_missing",
                f"Card Ladder cannot be read yet. Add {cardladder.KEY_NAME} to the settings file, then try again.")
    day = TODAY()
    client = _client_for(token, day)
    try:
        look = cardladder.cert_lookup(client, cert, grader)
        if not look:
            _refuse(HTTPStatus.NOT_FOUND, "cert_not_found",
                    "Card Ladder has no slab with that cert number for that grader. Nothing was saved.")
        if not isinstance(look, dict) or not look.get("profileId") or not look.get("grade"):
            raise _Unreadable("lookup")
        profile = cardladder.profile(client, look["profileId"])
        estimate = cardladder.card_estimate(
            client, look["profileId"], grader, look["grade"], look.get("label") or "",
            look.get("qualifierType"), look.get("autographGrade"))
    except cardladder.RateLimited:
        _limit(day)
        _client = None  # its stop never clears; the next day builds a new one
        _rate_limited()
    except cardladder.TokenRejected:
        _refuse(HTTPStatus.CONFLICT, "cardladder_token_rejected",
                f"Card Ladder did not accept the saved login. Copy {cardladder.KEY_NAME} again, then try again.")
    except cardladder.CardLadderError:
        _refuse(HTTPStatus.BAD_GATEWAY, "cardladder_failed",
                "Card Ladder could not be read just now. Nothing was saved. Try again later.")
    except _Unreadable:
        _unreadable()
    if not isinstance(profile, dict) or not isinstance(estimate, dict):
        _unreadable()

    grade = look["grade"]
    try:
        sales = [_stored_sale(sale) for sale in profile.get("sales") or ()
                 if isinstance(sale, dict) and _same_grader(sale.get("grader"), grader) and sale.get("grade") == grade]
    except _Unreadable as exc:
        if str(exc) == "date":
            _refuse(HTTPStatus.BAD_GATEWAY, "sale_date_unreadable",
                    "Card Ladder gave a sale a date this app could not read. Nothing was saved.")
        _unreadable()
    try:
        ladder = _ladder(profile, grader)
        newest = max(sales, key=lambda sale: (sale["date"], sale["id"]), default=None)
        row = next((r for r in ladder or () if r["grade"] == grade), {})
        has_sale = newest is not None
        values = dict(
            cl_value=row.get("cl_value"), cl_confidence=row.get("cl_confidence"),
            estimated_value=_money(estimate.get("estimatedValue")), estimated_confidence=_whole(estimate.get("confidence")),
            last_sale_price=newest["price"] if newest else None, last_sale_date=newest["date"] if newest else None,
            speed=_speed(estimate))
        if not has_sale:  # no sale at the grade, no value: whatever Card Ladder sent is not stored
            values = dict.fromkeys(values)
            ladder = [{**r, "cl_value": None, "cl_confidence": None} if r["grade"] == grade else r for r in ladder or ()] or ladder
        identity = {
            "label": look.get("label"), "grade": grade, "qualifier_type": look.get("qualifierType"),
            "autograph_grade": look.get("autographGrade"), "date_graded": look.get("dateGraded"),
            **{key: (look.get("profile") or {}).get(key)
               for key in ("category", "year", "set", "subject", "number", "variation")},
        }
        population = _whole(look.get("population"))
        gem_rate = _fraction((look.get("profile") or {}).get("gemRate"))
    except _Unreadable:
        _unreadable()

    with Store().write() as snap:
        table = snap.slabs
        # A slab out of the list that still has snapshots was removed: it comes back with its first day.
        history = table.snapshots_for(cert, grader)
        fresh = table.get(cert, grader) is None
        restored = fresh and bool(history)
        added = fresh and not history
        slab = table.add(cert, grader, profile_id=look["profileId"], identity=identity,
                         subgrades=look.get("subGrades"), added=history[0].day if restored else day)
        table.record_snapshot(cert, grader, day, population=population, gem_rate=gem_rate, ladder=ladder, **values)
        # The store replaces a sale whole, so what only an earlier read gave (3.3's fields) is merged in first.
        table.record_sales(cert, grader, [
            {**table.sales[sale["id"]].data, **sale} if sale["id"] in table.sales else sale for sale in sales])
    label = (slab.identity or {}).get("label") or f"slab {cert}"
    return {"cert": slab.cert, "grader": slab.grader, "label": label, "day": day, "added": added,
            "restored": restored, "message": f"{'Added' if added else 'Restored' if restored else 'Updated'} {label}."}


def _unreadable():
    _refuse(HTTPStatus.BAD_GATEWAY, "cardladder_unreadable",
            "Card Ladder sent an answer this app could not read. Nothing was saved. Try again later.")


# ---------------------------------------------------------------------------- remove


def do_slab_remove(grader: str, cert: str) -> dict:
    """No Card Ladder call and no login, so it works on a rate-limited day. Refused while an add runs:
    that add's final write would put the slab back. The lock is checked before the lookup."""
    if not _inflight.acquire(blocking=False):
        _refuse(HTTPStatus.CONFLICT, "slab_add_busy", "A slab is being added right now. Wait for it to finish, then try again.")
    try:
        grader = _grader(grader)
        with Store().write() as snap:
            slab = snap.slabs.remove(cert, grader)
        if slab is None:
            _refuse(HTTPStatus.NOT_FOUND, "slab_unknown", "That slab is not in the list, so there is nothing to remove.")
        label = (slab.identity or {}).get("label") or f"slab {slab.cert}"
        return {"cert": slab.cert, "grader": slab.grader, "label": label, "message": f"Removed {label}."}
    finally:
        _inflight.release()


# ---------------------------------------------------------------------------- list and detail


def _snapshot(row: SlabSnapshot) -> dict:
    return {name: getattr(row, name) for name in SlabSnapshot._fields if name not in ("cert", "grader", "ladder")}


def _slab_row(slab) -> dict:
    return {"cert": slab.cert, "grader": slab.grader, "label": (slab.identity or {}).get("label"),
            "grade": (slab.identity or {}).get("grade"), "added": slab.added}


def do_slabs() -> dict:
    table = Store().read().slabs
    rows = []
    for slab in table.list():
        snapshots = table.snapshots_for(slab.cert, slab.grader)
        rows.append({
            **_slab_row(slab),
            "snapshot": _snapshot(snapshots[-1]) if snapshots else None,
            "note": None if table.sales_for(slab.cert, slab.grader) else "no sales",
        })
    return {"slabs": rows}


def do_slab(grader: str, cert: str) -> dict:
    grader = _grader(grader)
    table = Store().read().slabs
    slab = table.get(cert, grader)
    if slab is None:
        _refuse(HTTPStatus.NOT_FOUND, "slab_unknown", "That slab is not in the list. Add it by its cert number first.")
    snapshots = table.snapshots_for(slab.cert, slab.grader)
    sales = [dict(sale.data) for sale in table.sales_for(slab.cert, slab.grader)]
    return {
        "slab": _slab_row(slab),
        "snapshots": [_snapshot(row) for row in snapshots],
        "sales": sales,
        "ladder": (snapshots[-1].ladder if snapshots else None) or [],
        "note": None if sales else "no sales",
    }
