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

from store import files

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
    kept = (read_status() or {}).get("trends")
    _write(status_path(), {**note, **({"trends": kept} if kept else {})})
    return note


def preload(fetch: Callable[[], dict], now: Optional[int] = None) -> dict:
    """Read the waiting rows' strips once; save what came back; write the note either way.

    `fetch` answers `{"asked": n, "skus": {sku: ranges}, "refused": {sku: why}, "failed":
    [sentence]}`. A SKU that came back replaces its saved entry; one that did not keeps its old
    entry and its old date. `read` below `asked` is a partial read and the screen says so.
    """
    at = int(time.time()) if now is None else int(now)
    try:
        answer = fetch()
        saved = read_trends()
        for sku, ranges in answer["skus"].items():
            saved[sku] = {"at": at, "ranges": ranges}
        if answer["skus"]:
            _write(trends_path(), {"skus": saved})
        failed = list(answer.get("failed") or [])
        note = {
            "at": at,
            "ok": not failed,
            "asked": int(answer["asked"]),
            "read": len(answer["skus"]),
            "refused": len(answer.get("refused") or {}),
            "message": failed[0] if failed else "",
        }
    except Exception as caught:
        note = {
            "at": at, "ok": False, "asked": 0, "read": 0, "refused": 0,
            "message": str(caught) or type(caught).__name__,
        }
    _write(status_path(), {**(read_status() or {}), "trends": note})
    return note
