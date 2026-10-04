"""The few constants the background reader's watcher needs, with NO imports beyond the standard library.

THE WATCHER IS A SMALL IDLE PROCESS (`identify/sweep.py`, spec section 8). Importing the `store`
package costs about 17 MB and `identify.match` imports it, so the watcher cannot import either.
`identify/match.py` takes these names from here, so the model pin and the served games each have
one home, and `home()` here is `store.files.home()` spelled without the package (a self-test case
keeps the two equal).
"""

import os
import sys
import time
from pathlib import Path

SERVED_GAMES = ("pokemon", "riftbound", "one_piece")

MODEL_FILENAME = "marqo-b-image.onnx"
MODEL_SHA256 = "79bc0fec967bdbb695a082344a5c2b4dc8ca47f34e72bf32c90f2e99e455a003"
MODEL_BYTES = 371_700_983

REPO_ROOT = Path(__file__).resolve().parent.parent
HOME_ENV = "PKMNSCAN_HOME"
INVENTORY_DIRNAME = "inventory"


def home() -> Path:
    override = os.environ.get(HOME_ENV, "").strip()
    return Path(override).expanduser().resolve() if override else REPO_ROOT


def inventory_dir() -> Path:
    return home() / INVENTORY_DIRNAME


_RUNTIME_RETRY_SECONDS = 30.0
_runtime = {"ok": False, "at": None}


def runtime_importable() -> bool:
    """Can everything a read needs be imported. One real import, a success cached for good and
    a failure retried at most every `_RUNTIME_RETRY_SECONDS`."""
    if any(sys.modules.get(name, True) is None for name in ("numpy", "onnxruntime", "PIL")):
        return False  # an import already blocked by name: no cache says otherwise
    if _runtime["ok"]:
        return True
    now = time.monotonic()
    if _runtime["at"] is not None and now - _runtime["at"] < _RUNTIME_RETRY_SECONDS:
        return False
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import PIL  # noqa: F401
        _runtime["ok"] = True
    except Exception:  # noqa: BLE001 — a broken install can raise more than ImportError
        _runtime["at"] = now
    return _runtime["ok"]
