"""The few constants the background reader's watcher needs, with NO imports beyond the standard library.

THE WATCHER IS A SMALL IDLE PROCESS (`identify/sweep.py`, spec section 8). Importing the `store`
package costs about 17 MB and `identify.match` imports it, so the watcher cannot import either.
`identify/match.py` takes these names from here, so the model pin and the served games each have
one home, and `home()` here is `store.files.home()` spelled without the package (a self-test case
keeps the two equal).
"""

import importlib.util
import os
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


def runtime_importable() -> bool:
    """Can the model runtime be imported. The one answer; it loads nothing."""
    try:
        return importlib.util.find_spec("onnxruntime") is not None
    except (ImportError, ValueError):
        return False
