"""The scheduled market read leaves notes a screen can show (DEBT69).

Two reads fire overnight, each through one server function handed in by the caller (this layer
never imports `server/`):

  `run`      the live listings, the one live fetch (`do_live_export`). Free: it downloads the
             operator's own Pricing tab and writes nothing at TCGplayer.
  `preload`  the Trends strip for every row still waiting (`do_price_trends_preload`), at the
             market reader's own courtesy pace. Free and read-only.

Each records how it ended in `inventory/price-refresh.json` (top-level keys for `run`, the
`trends` key for `preload`), so `#/pricing` can draw a failed or partial read and never a silent
stale state. The saved strips live in `inventory/price-trends.json`, one entry per SKU with the
second it was read. A failed read keeps the last good readings and strips untouched.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Optional

from pipeline import pricehistory
from store import files

#: THE ONE SPELLING of "this row has no product to read a history for". `server/pipeline_routes.py`
#: builds the refusal sentence from it and `preload` below counts it: a refusal that is NOT this is
#: a read the mirror or the network failed, and the screen says so differently.
NO_PRODUCT_LINE = "is not in a catalogued product line"

STATUS_FILENAME = "price-refresh.json"
TRENDS_FILENAME = "price-trends.json"


def status_path():
    return files.inventory_dir() / STATUS_FILENAME


def trends_path():
    return files.inventory_dir() / TRENDS_FILENAME


def _read(path) -> Optional[dict]:
    try:
        parsed = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _write(path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(document))
    tmp.replace(path)


def read_status() -> Optional[dict]:
    return _read(status_path())


def read_trends() -> dict:
    """`{sku: {"at": second, "ranges": [...]}}`, empty when nothing was ever saved."""
    skus = (_read(trends_path()) or {}).get("skus")
    return skus if isinstance(skus, dict) else {}


def entry_facts(series: "pricehistory.Series") -> dict:
    """What a saved SKU carries beside its strip: `facts` (the row's and the sheet's figures, all
    from `Series.window`), `days` (the newest 30 buckets: date, units, sales, low, high, market)
    and `through` (the date of the newest bucket). Money is text, exact like every price here."""
    def money(value):
        return None if value is None else str(value)

    week, month = series.window(7), series.window(30)
    newest = series.buckets[-30:]
    best = max((b for b in newest if b.sold), key=lambda b: b.quantity, default=None)
    priced = [b.market for b in newest if b.market is not None]
    change = None
    if len(priced) > 1 and priced[0]:
        change = str(((priced[-1] - priced[0]) / priced[0]).quantize(pricehistory.RATIO))
    facts = {
        "sold_7d": week.units, "sales_7d": week.sales, "avg_7d": money(week.average),
        "low_7d": money(week.low), "high_7d": money(week.high),
        "sold_30d": month.units, "sales_30d": month.sales, "avg_30d": money(month.average),
        "low_30d": money(month.low), "high_30d": money(month.high),
        "best_day": None if best is None or best.start is None else [best.start.isoformat(), best.quantity],
        "change_30d": change,
    }
    days = [
        [b.start.isoformat() if b.start else None, b.quantity, b.transactions, money(b.low), money(b.high), money(b.market)]
        for b in newest
    ]
    dated = [b.start for b in series.buckets if b.start is not None]
    return {"facts": facts, "days": days, "through": dated[-1].isoformat() if dated else None}


def note_step(name: str, ok: bool, at: Optional[int] = None, **info) -> dict:
    """Record how one step of the refresh ended in `steps.<name>`: `at`, `ok` and its own counts or
    sentence. A failed step names itself here and never blanks a figure."""
    status = read_status() or {}
    when = int(time.time()) if at is None else int(at)
    # `last_ok_at` is what "Prices as of" keeps drawing while a later try fails.
    last_ok = when if ok else ((status.get("steps") or {}).get(name) or {}).get("last_ok_at")
    note = {"at": when, "ok": bool(ok), **({"last_ok_at": last_ok} if last_ok else {}), **info}
    _write(status_path(), {**status, "steps": {**(status.get("steps") or {}), name: note}})
    return note


def run(fetch: Callable[[], dict], now: Optional[int] = None) -> dict:
    """Fetch once; write the note either way; return it. Never raises on a refused fetch."""
    at = int(time.time()) if now is None else int(now)
    try:
        answer = fetch()
        note = {"at": at, "ok": True, "live_rows": int(answer.get("live_rows", 0))}
    except Exception as caught:  # a refusal carries its own sentence; anything else is named
        note = {
            "at": at,
            "ok": False,
            "code": str(getattr(caught, "code", type(caught).__name__)),
            "message": str(caught),
        }
    status = read_status() or {}
    kept = {key: status[key] for key in ("trends", "steps") if status.get(key)}
    _write(status_path(), {**note, **kept})
    return note


def save_strips(strips: dict, at: Optional[int] = None, keep: Optional[set] = None, extras: Optional[dict] = None) -> None:
    """THE ONE SAVE for a strip, used by the overnight preload and by the Trends press alike.

    `strips` is `{sku: ranges}` for strips that were READ. A SKU not named keeps its saved entry
    and its old date, so a refused read never replaces a good strip. `keep`, when given, prunes
    every saved SKU not in it (the overnight job passes the current worklist). `extras` is
    `{sku: entry_facts(...)}`; a SKU saved again without it keeps the facts it had.
    """
    when = int(time.time()) if at is None else int(at)
    saved = read_trends()
    for sku, ranges in strips.items():
        saved[sku] = {**saved.get(sku, {}), "at": when, "ranges": ranges, **((extras or {}).get(sku) or {})}
    if keep is not None:
        saved = {sku: entry for sku, entry in saved.items() if sku in keep}
    _write(trends_path(), {"skus": saved})


def preload(fetch: Callable[[], dict], now: Optional[int] = None) -> dict:
    """Read the waiting rows' strips once; save what came back; write the note either way.

    `fetch` answers `{"asked": n, "skus": {sku: ranges}, "refused": {sku: why}, "failed":
    [sentence], "current": [every SKU on the worklist]}`. The note splits the asked rows three
    ways that add up to `asked`: `read` (a strip with sales), `no_history` (read, but no sales, or
    no product line to look up) and `unreadable` (the mirror or the network refused). `failed`
    counts chunks that raised. Only `no_history` is "no history"; the rest is a read that failed.
    """
    at = int(time.time()) if now is None else int(now)
    try:
        answer = fetch()
        strips = answer["skus"]
        refused = answer.get("refused") or {}
        failed = list(answer.get("failed") or [])
        keep = answer.get("current")
        save_strips(strips, at, None if keep is None else set(keep))
        no_product = sum(1 for why in refused.values() if NO_PRODUCT_LINE in why)
        empty = sum(1 for ranges in strips.values() if not ranges)
        note = {
            "at": at,
            "ok": not failed,
            "asked": int(answer["asked"]),
            "read": len(strips) - empty,
            "no_history": empty + no_product,
            "unreadable": len(refused) - no_product,
            "failed": len(failed),
            "message": failed[0] if failed else "",
        }
    except Exception as caught:
        note = {
            "at": at, "ok": False, "asked": 0, "read": 0, "no_history": 0, "unreadable": 0,
            "failed": 1, "message": str(caught) or type(caught).__name__,
        }
    _write(status_path(), {**(read_status() or {}), "trends": note})
    return note
