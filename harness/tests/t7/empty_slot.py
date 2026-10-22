"""T7 group: a photograph of an empty slot is read as `empty_slot`, before any paid read.

`identify.match.empty_slot` takes the 99th-percentile luminance of a photograph. Under
`EMPTY_SLOT_P99` the slot is empty, and `read` answers the code `empty_slot` without cropping,
embedding or ranking. The fixtures are synthetic JPEGs written to a temporary folder at run time,
so no photograph is committed.

INTERFACE ASSUMED (the builder may rename, then re-point here): `match.empty_slot(Path) -> bool`
and `match.read(requests, index, model, aspect, log, promo_games)`, which reads `index.meta` once.
The code is asserted as the wire literal `"empty_slot"`, so this file imports on a tree that
lacks the constant.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from harness.tests import Checks
from identify import match

CODE = "empty_slot"
DARK = 20  # a uniform dark slot: its 99th percentile sits here
BRIGHT = 230  # a bright card face
FRAME = (1434, 1024)  # tall, past the 256 draft size, so the JPEG draft decode runs


def _jpeg(path: Path, grid: np.ndarray) -> Path:
    Image.fromarray(grid).save(path, "JPEG", quality=90)
    return path


def _dark_slot(folder: Path) -> Path:
    return _jpeg(folder / "dark.jpg", np.full(FRAME, DARK, np.uint8))


def _dark_with_bright_patch(folder: Path) -> Path:
    grid = np.full(FRAME, DARK, np.uint8)
    grid[: FRAME[0] // 2, : FRAME[1] // 2] = BRIGHT  # a quarter of the frame, far over 1% of pixels
    return _jpeg(folder / "patch.jpg", grid)


def _read_one(photo: Path, stub_crop: bool) -> tuple:
    """One request through `match.read`. The pool is fixed, so only the photograph decides the code.
    `stub_crop` makes the crop find nothing, so a read that gets past the empty check ends there;
    without it the real crop runs and names a missing photograph."""
    index = mock.Mock()
    index.meta.return_value = match.MODEL_SHA256
    request = match.Request("k", photo, "riftbound", "tcg")
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set",), None, "")))
        embed = stack.enter_context(mock.patch.object(match, "embed"))
        crop = stack.enter_context(mock.patch.object(match, "_crop", return_value=None)) if stub_crop else None
        result = match.read([request], index, None, 0.716, lambda _m: None, promo_games=set())[0]
    return result, crop, embed


def check_empty_slot_fixtures(checks: Checks) -> None:
    fn = getattr(match, "empty_slot", None)
    if not checks.ok(callable(fn), "identify.match exposes empty_slot", "no empty_slot in identify/match.py"):
        return
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        checks.ok(fn(_dark_slot(folder)) is True, "a dark uniform JPEG is an empty slot")
        checks.ok(fn(_dark_with_bright_patch(folder)) is False,
                  "a dark JPEG with a bright quarter is not an empty slot")
        try:
            answer = fn(folder / "absent.jpg")
        except Exception as exc:  # a photograph that will not open is a named failure, never a crash
            checks.ok(False, "a missing photograph does not crash empty_slot", repr(exc))
        else:
            checks.ok(answer is False, "a missing photograph is not an empty slot", f"got {answer!r}")


def check_read_names_empty_slot(checks: Checks) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        result, crop, embed = _read_one(_dark_slot(folder), stub_crop=True)
        checks.equal(result.code, CODE, "read answers the code empty_slot for a dark crop")
        checks.ok(not result.accepted, "the empty slot is not accepted")
        checks.ok(not crop.called and not embed.called,
                  "the empty slot never reaches the crop or the embed")
        result, crop, _ = _read_one(_dark_with_bright_patch(folder), stub_crop=True)
        checks.ok(result.code != CODE, "a photograph with a bright quarter is not read as empty",
                  f"code={result.code}")
        checks.ok(crop.called, "and it goes on to the crop")
        result, _, _ = _read_one(folder / "absent.jpg", stub_crop=False)
        checks.equal(result.code, "photo_unreadable",
                     "a missing photograph is the named photo_unreadable failure")


CHECKS = (check_empty_slot_fixtures, check_read_names_empty_slot)
