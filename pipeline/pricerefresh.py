"""The scheduled market read leaves a note a screen can show (DEBT69).

`run` calls the one live fetch (`server/pipeline_routes.py:do_live_export`, free: it downloads
the operator's own Pricing tab and writes nothing at TCGplayer) and records how it ended in one
small file. A failed run keeps the last good readings untouched and says so here, so `#/pricing`
can draw it. A read that never ran leaves no note, which the screen draws as nothing.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Optional

from store import files

STATUS_FILENAME = "price-refresh.json"


def status_path():
    return files.inventory_dir() / STATUS_FILENAME


def read_status() -> Optional[dict]:
    try:
        parsed = json.loads(status_path().read_text())
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


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
    target = status_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(note))
    tmp.replace(target)
    return note
